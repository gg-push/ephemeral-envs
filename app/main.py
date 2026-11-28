import os
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import sqlalchemy
from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import Base, engine, get_db
from models import Task

# ── Environment Info ──────────────────────────────────────────────────────────
ENV_NAME = os.getenv("ENV_NAME", "local")
PR_NUMBER = os.getenv("PR_NUMBER", "0")
APP_VERSION = os.getenv("APP_VERSION", "dev")

# How long to wait for Postgres on boot. The database pod frequently starts
# after the app pod, and crash-looping until it appears makes the rollout look
# broken when it is merely slow.
DB_WAIT_SECONDS = int(os.getenv("DB_WAIT_SECONDS", "60"))


def wait_for_database(timeout: int = DB_WAIT_SECONDS) -> None:
    """Block until the database accepts a connection, or give up after timeout."""
    deadline = time.monotonic() + timeout
    delay = 0.5
    while True:
        try:
            with engine.connect() as conn:
                conn.execute(sqlalchemy.text("SELECT 1"))
            return
        except Exception:
            if time.monotonic() >= deadline:
                raise
            time.sleep(delay)
            delay = min(delay * 2, 5)


# ── Startup ───────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    wait_for_database()
    Base.metadata.create_all(bind=engine)
    db = next(get_db())
    try:
        existing = db.query(Task).filter(Task.title.like("[System] Environment%")).first()
        if not existing:
            started = datetime.now(timezone.utc).strftime("%b %d %Y %H:%M UTC")
            seed = Task(
                title=f"[System] Environment {ENV_NAME} initialized — {started}",
                done=False,
            )
            db.add(seed)
            db.commit()
    finally:
        db.close()
    yield


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="DevBoard",
    description="Ephemeral task board — one per pull request",
    version=APP_VERSION,
    lifespan=lifespan,
)

# Start Prometheus metrics instrumentator
Instrumentator().instrument(app).expose(app)


# ── Schemas ───────────────────────────────────────────────────────────────────
class TaskCreate(BaseModel):
    title: str


class TaskResponse(BaseModel):
    id: int
    title: str
    done: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Routes ────────────────────────────────────────────────────────────────────
@app.get("/api/live")
def live():
    """Liveness: is the process itself healthy? Deliberately touches nothing."""
    return {"status": "alive", "version": APP_VERSION}


@app.get("/api/health")
def health(db: Session = Depends(get_db)):
    """Readiness: can this instance actually serve requests?

    Returns 503 when the database is unreachable so that Kubernetes pulls the
    pod out of the Service endpoints instead of routing traffic into errors.
    """
    try:
        db.execute(sqlalchemy.text("SELECT 1"))
        db_status = "connected"
    except Exception:
        db_status = "error"

    payload = {
        "status": "ok" if db_status == "connected" else "degraded",
        "env": ENV_NAME,
        "pr": PR_NUMBER,
        "db": db_status,
        "version": APP_VERSION,
    }

    if db_status != "connected":
        return JSONResponse(payload, status_code=503)
    return payload


@app.get("/api/db/info")
def db_info(db: Session = Depends(get_db)):
    count = db.query(Task).count()
    return {
        "env_name": ENV_NAME,
        "pr_number": PR_NUMBER,
        "db_host": f"postgres.{ENV_NAME}.svc",
        "record_count": count,
    }


@app.get("/api/tasks", response_model=list[TaskResponse])
def list_tasks(db: Session = Depends(get_db)):
    return db.query(Task).order_by(Task.created_at).all()


@app.post("/api/tasks", response_model=TaskResponse, status_code=201)
def create_task(payload: TaskCreate, db: Session = Depends(get_db)):
    task = Task(title=payload.title)
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@app.post("/api/tasks/{task_id}/toggle", response_model=TaskResponse)
def toggle_task(task_id: int, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    task.done = not task.done
    db.commit()
    db.refresh(task)
    return task


@app.delete("/api/tasks/{task_id}", status_code=204)
def delete_task(task_id: int, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    db.delete(task)
    db.commit()
