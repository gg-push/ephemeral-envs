import os
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import sqlalchemy
from fastapi import Depends, FastAPI, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
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

# Generate a unique hue per PR number so every environment has its own color.
# ENV_NAME is not always numeric (local runs, ad-hoc deploys), so fall back
# rather than crashing the process at import time.
try:
    pr_hue = (int(PR_NUMBER) * 47) % 360
except ValueError:
    pr_hue = 210


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
            seed = Task(
                title=f"[System] Environment {ENV_NAME} initialized — {datetime.now(timezone.utc).strftime('%b %d %Y %H:%M UTC')}",
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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


# ── HTML Landing Page ─────────────────────────────────────────────────────────
def render_page(tasks: list[Task]) -> str:
    env_color = f"hsl({pr_hue}, 65%, 52%)"
    env_color_soft = f"hsla({pr_hue}, 65%, 52%, 0.12)"
    env_color_border = f"hsla({pr_hue}, 65%, 52%, 0.25)"

    task_rows = ""
    for t in tasks:
        seed_class = "seed-task" if t.title.startswith("[System]") else ""
        done_class = "done" if t.done else ""
        checkmark = '<svg width="10" height="10" viewBox="0 0 10 10"><polyline points="1.5,5 4,7.5 8.5,2.5" stroke="white" stroke-width="1.5" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>' if t.done else ""
        checked_class = "checked" if t.done else ""
        task_rows += f"""
        <li class="task-item {seed_class}">
          <form method="post" action="/api/tasks/{t.id}/toggle" style="display:contents">
            <button type="submit" class="check-btn {checked_class}">{checkmark}</button>
          </form>
          <span class="task-label {done_class}">{t.title}</span>
          <form method="post" action="/api/tasks/{t.id}/delete" style="display:contents">
            <button type="submit" class="delete-btn" title="Delete">
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                <line x1="1" y1="1" x2="11" y2="11" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
                <line x1="11" y1="1" x2="1" y2="11" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
              </svg>
            </button>
          </form>
        </li>"""

    task_html = f"<ul class='task-list'>{task_rows}</ul>" if tasks else "<div class='empty-state'>No tasks yet</div>"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>DevBoard — {ENV_NAME}</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Helvetica Neue', sans-serif;
      background: #e8e8ed;
      min-height: 100vh;
      display: flex;
      align-items: flex-start;
      justify-content: center;
      padding: 48px 16px 80px;
      color: #1d1d1f;
      -webkit-font-smoothing: antialiased;
    }}

    .window {{
      width: 100%;
      max-width: 580px;
      background: rgba(255,255,255,0.78);
      backdrop-filter: blur(40px) saturate(180%);
      -webkit-backdrop-filter: blur(40px) saturate(180%);
      border-radius: 16px;
      border: 1px solid rgba(255,255,255,0.85);
      box-shadow:
        0 0 0 0.5px rgba(0,0,0,0.1),
        0 4px 6px rgba(0,0,0,0.04),
        0 20px 50px rgba(0,0,0,0.16);
      overflow: hidden;
    }}

    .titlebar {{
      display: flex;
      align-items: center;
      padding: 13px 16px;
      background: rgba(248,248,250,0.85);
      border-bottom: 1px solid rgba(0,0,0,0.06);
      user-select: none;
    }}

    .traffic {{ display: flex; gap: 6px; }}
    .dot {{
      width: 12px; height: 12px; border-radius: 50%;
      box-shadow: inset 0 0 0 0.5px rgba(0,0,0,0.18);
    }}
    .dot-red    {{ background: #ff5f57; }}
    .dot-yellow {{ background: #ffbd2e; }}
    .dot-green  {{ background: #28c840; }}

    .titlebar-center {{
      flex: 1; text-align: center; font-size: 12.5px;
      font-weight: 500; color: #3a3a3c; margin-right: 42px;
    }}

    .content {{ padding: 20px; display: flex; flex-direction: column; gap: 12px; }}

    .env-pill {{
      display: inline-flex; align-items: center; gap: 7px;
      background: {env_color_soft};
      border: 1px solid {env_color_border};
      border-radius: 100px; padding: 5px 12px 5px 7px; align-self: flex-start;
    }}

    .env-dot {{
      width: 7px; height: 7px; border-radius: 50%;
      background: {env_color};
      animation: pulse 2.5s ease-in-out infinite;
    }}

    @keyframes pulse {{
      0%, 100% {{ box-shadow: 0 0 0 2px {env_color_soft}; }}
      50%       {{ box-shadow: 0 0 0 5px transparent; }}
    }}

    .env-pill-text {{ font-size: 12px; font-weight: 500; color: {env_color}; }}

    .section {{
      background: rgba(255,255,255,0.5); border-radius: 10px;
      border: 1px solid rgba(0,0,0,0.055); overflow: hidden;
    }}

    .section-header {{
      padding: 10px 14px; border-bottom: 1px solid rgba(0,0,0,0.045);
      display: flex; align-items: center; justify-content: space-between;
      background: rgba(0,0,0,0.015);
    }}

    .section-title {{
      font-size: 11px; font-weight: 600; color: #8e8e93;
      text-transform: uppercase; letter-spacing: 0.07em;
    }}

    .count-badge {{
      font-size: 11px; font-weight: 500; color: #8e8e93;
      background: rgba(0,0,0,0.06); border-radius: 20px; padding: 1px 7px;
    }}

    .section-body {{ padding: 12px 14px; }}

    .add-form {{ display: flex; gap: 7px; }}

    .add-input {{
      flex: 1; background: rgba(255,255,255,0.9);
      border: 1px solid rgba(0,0,0,0.1); border-radius: 7px;
      padding: 7px 11px; font-size: 13px; font-family: inherit;
      color: #1d1d1f; outline: none;
      transition: border-color 0.15s, box-shadow 0.15s;
    }}
    .add-input::placeholder {{ color: #c7c7cc; }}
    .add-input:focus {{
      border-color: {env_color};
      box-shadow: 0 0 0 3px {env_color_soft};
    }}

    .add-btn {{
      background: {env_color}; color: white; border: none;
      border-radius: 7px; padding: 7px 15px; font-size: 13px;
      font-weight: 500; font-family: inherit; cursor: pointer;
      transition: filter 0.15s, transform 0.1s; white-space: nowrap;
    }}
    .add-btn:hover  {{ filter: brightness(1.08); }}
    .add-btn:active {{ transform: scale(0.96); }}

    .task-list {{ list-style: none; }}

    .task-item {{
      display: flex; align-items: center; gap: 9px;
      padding: 9px 0; border-bottom: 1px solid rgba(0,0,0,0.04);
    }}
    .task-item:last-child {{ border-bottom: none; }}

    .check-btn {{
      width: 18px; height: 18px; min-width: 18px; border-radius: 50%;
      border: 1.5px solid rgba(0,0,0,0.18); background: white;
      cursor: pointer; display: flex; align-items: center;
      justify-content: center; padding: 0; transition: all 0.15s;
    }}
    .check-btn.checked {{ background: {env_color}; border-color: {env_color}; }}
    .check-btn:hover:not(.checked) {{
      border-color: {env_color}; box-shadow: 0 0 0 3px {env_color_soft};
    }}

    .task-label {{ flex: 1; font-size: 13px; color: #1d1d1f; line-height: 1.4; }}
    .task-label.done {{ color: #aeaeb2; text-decoration: line-through; }}
    .seed-task .task-label {{ color: #8e8e93; font-style: italic; }}

    .delete-btn {{
      background: none; border: none; color: #c7c7cc; cursor: pointer;
      padding: 4px; border-radius: 5px; display: flex; align-items: center;
      justify-content: center; transition: color 0.12s, background 0.12s; min-width: 20px;
    }}
    .delete-btn:hover {{ color: #ff3b30; background: rgba(255,59,48,0.08); }}

    .empty-state {{
      text-align: center; color: #c7c7cc; font-size: 13px; padding: 24px 0;
    }}

    .meta-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 7px; }}

    .meta-item {{
      background: rgba(0,0,0,0.025); border-radius: 7px;
      padding: 9px 11px; border: 1px solid rgba(0,0,0,0.04);
    }}

    .meta-label {{
      font-size: 10.5px; font-weight: 500; color: #aeaeb2;
      text-transform: uppercase; letter-spacing: 0.06em;
    }}

    .meta-value {{
      font-size: 12.5px; font-weight: 500; color: #3a3a3c;
      margin-top: 2px; word-break: break-all;
    }}

    .window-footer {{
      padding: 10px 20px; border-top: 1px solid rgba(0,0,0,0.055);
      display: flex; align-items: center; justify-content: space-between;
      background: rgba(248,248,250,0.5);
    }}
    .footer-text {{ font-size: 11px; color: #c7c7cc; }}
    .docs-link {{
      font-size: 11px; color: {env_color}; text-decoration: none; font-weight: 500;
    }}
    .docs-link:hover {{ text-decoration: underline; }}
  </style>
</head>
<body>
  <div class="window">

    <div class="titlebar">
      <div class="traffic">
        <div class="dot dot-red"></div>
        <div class="dot dot-yellow"></div>
        <div class="dot dot-green"></div>
      </div>
      <div class="titlebar-center">DevBoard — {ENV_NAME}</div>
    </div>

    <div class="content">

      <div class="env-pill">
        <div class="env-dot"></div>
        <span class="env-pill-text">PR #{PR_NUMBER} · Live Preview</span>
      </div>

      <div class="section">
        <div class="section-header"><span class="section-title">New Task</span></div>
        <div class="section-body">
          <form class="add-form" method="post" action="/api/tasks/create">
            <input class="add-input" name="title" type="text"
              placeholder="What needs to be done?" required autocomplete="off" />
            <button class="add-btn" type="submit">Add</button>
          </form>
        </div>
      </div>

      <div class="section">
        <div class="section-header">
          <span class="section-title">PR Preview</span>
          <span class="count-badge">{len(tasks)}</span>
        </div>
        <div class="section-body">{task_html}</div>
      </div>

      <div class="section">
        <div class="section-header"><span class="section-title">Environment Info</span></div>
        <div class="section-body">
          <div class="meta-grid">
            <div class="meta-item">
              <div class="meta-label">Environment</div>
              <div class="meta-value">{ENV_NAME}</div>
            </div>
            <div class="meta-item">
              <div class="meta-label">Pull Request</div>
              <div class="meta-value">#{PR_NUMBER}</div>
            </div>
            <div class="meta-item">
              <div class="meta-label">Tasks</div>
              <div class="meta-value">{len(tasks)}</div>
            </div>
            <div class="meta-item">
              <div class="meta-label">Database</div>
              <div class="meta-value">postgres-{ENV_NAME}</div>
            </div>
          </div>
        </div>
      </div>

    </div>

    <div class="window-footer">
      <span class="footer-text">v{APP_VERSION}</span>
      <a class="docs-link" href="/docs">API Docs →</a>
    </div>

  </div>
</body>
</html>"""


# ── Routes ────────────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
def index(db: Session = Depends(get_db)):
    tasks = db.query(Task).order_by(Task.created_at).all()
    return render_page(tasks)


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
        "db_host": f"postgres-{ENV_NAME}",
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


@app.post("/api/tasks/create")
def create_task_form(title: str = Form(...), db: Session = Depends(get_db)):
    task = Task(title=title)
    db.add(task)
    db.commit()
    return RedirectResponse(url="/", status_code=303)


@app.post("/api/tasks/{task_id}/toggle")
def toggle_task(task_id: int, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    task.done = not task.done
    db.commit()
    return RedirectResponse(url="/", status_code=303)


@app.delete("/api/tasks/{task_id}", status_code=204)
def delete_task(task_id: int, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    db.delete(task)
    db.commit()


@app.post("/api/tasks/{task_id}/delete")
def delete_task_form(task_id: int, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if task:
        db.delete(task)
        db.commit()
    return RedirectResponse(url="/", status_code=303)
