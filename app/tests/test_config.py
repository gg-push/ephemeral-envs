"""Tests for module-level configuration and startup behaviour."""

import importlib

import pytest


def _reload_main(monkeypatch, **env):
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    import main

    return importlib.reload(main)


def test_hue_is_derived_from_the_pr_number(monkeypatch):
    main = _reload_main(monkeypatch, PR_NUMBER="3")
    assert main.pr_hue == (3 * 137) % 360


def test_non_numeric_pr_number_does_not_crash_the_process(monkeypatch):
    """A non-numeric PR_NUMBER used to raise ValueError at import time."""
    main = _reload_main(monkeypatch, PR_NUMBER="not-a-number")
    assert 0 <= main.pr_hue < 360


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
