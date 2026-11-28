"""Tests for module-level configuration and startup behaviour."""

import pytest


def test_wait_for_database_gives_up_after_the_timeout(monkeypatch):
    import main

    monkeypatch.setattr(main.time, "sleep", lambda _seconds: None)

    def explode():
        raise RuntimeError("connection refused")

    monkeypatch.setattr(main.engine, "connect", explode)

    with pytest.raises(RuntimeError):
        main.wait_for_database(timeout=0)


def test_wait_for_database_returns_once_the_database_answers(monkeypatch):
    import main

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def execute(self, *args, **kwargs):
            return None

    monkeypatch.setattr(main.engine, "connect", FakeConnection)
    main.wait_for_database(timeout=1)
