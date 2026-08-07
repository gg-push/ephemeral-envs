import os
import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP_DIR))

# The app builds its engine at import time from DATABASE_URL, so this has to be
# set before anything under test is imported. SQLite keeps CI free of a
# Postgres service container.
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("ENV_NAME", "pr-42")
os.environ.setdefault("PR_NUMBER", "42")
os.environ.setdefault("APP_VERSION", "test")


def _make_client(session_factory):
    """Build a TestClient with get_db overridden.

    TestClient is constructed directly rather than used as a context manager so
    that the real lifespan never runs: it waits on a live database and seeds a
    row, neither of which belongs in a unit test.
    """
    from fastapi.testclient import TestClient

    import main
    from database import get_db

    main.app.dependency_overrides[get_db] = session_factory
    return TestClient(main.app)


@pytest.fixture
def client():
    """A TestClient backed by a fresh in-memory database per test."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    import main
    from database import Base

    # StaticPool keeps every session on the same in-memory database, which
    # would otherwise be discarded when the first connection closes.
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    yield _make_client(override_get_db)

    main.app.dependency_overrides.clear()
    engine.dispose()


@pytest.fixture
def broken_client():
    """A TestClient whose database raises on every query."""
    import main

    class ExplodingSession:
        def execute(self, *args, **kwargs):
            raise RuntimeError("database is down")

        def query(self, *args, **kwargs):
            raise RuntimeError("database is down")

    def override_get_db():
        yield ExplodingSession()

    yield _make_client(override_get_db)

    main.app.dependency_overrides.clear()
