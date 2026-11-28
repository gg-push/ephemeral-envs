"""Tests for the DevBoard API.

These exist mainly to catch regressions in the two contracts the platform
depends on: the health endpoint's status code (which gates readiness and the
post-deploy smoke test) and the JSON task API the React frontend calls.
"""


def test_live_does_not_touch_the_database(broken_client):
    """Liveness must stay green when only the database is broken."""
    response = broken_client.get("/api/live")
    assert response.status_code == 200
    assert response.json()["status"] == "alive"


def test_health_reports_ok_when_database_is_reachable(client):
    response = client.get("/api/health")
    assert response.status_code == 200

    body = response.json()
    assert body["status"] == "ok"
    assert body["db"] == "connected"
    assert body["env"] == "pr-42"
    assert body["pr"] == "42"


def test_health_returns_503_when_database_is_down(broken_client):
    """Readiness must fail so Kubernetes stops routing traffic to this pod."""
    response = broken_client.get("/api/health")
    assert response.status_code == 503
    assert response.json()["db"] == "error"


def test_tasks_start_empty(client):
    response = client.get("/api/tasks")
    assert response.status_code == 200
    assert response.json() == []


def test_create_and_list_task(client):
    created = client.post("/api/tasks", json={"title": "Ship the reconciler"})
    assert created.status_code == 201

    body = created.json()
    assert body["title"] == "Ship the reconciler"
    assert body["done"] is False
    assert "created_at" in body

    listed = client.get("/api/tasks").json()
    assert [t["title"] for t in listed] == ["Ship the reconciler"]


def test_toggle_flips_done(client):
    task_id = client.post("/api/tasks", json={"title": "Toggle me"}).json()["id"]

    response = client.post(f"/api/tasks/{task_id}/toggle")
    assert response.status_code == 200
    assert response.json()["done"] is True
    assert client.get("/api/tasks").json()[0]["done"] is True

    assert client.post(f"/api/tasks/{task_id}/toggle").json()["done"] is False
    assert client.get("/api/tasks").json()[0]["done"] is False


def test_delete_removes_task(client):
    task_id = client.post("/api/tasks", json={"title": "Delete me"}).json()["id"]

    response = client.delete(f"/api/tasks/{task_id}")
    assert response.status_code == 204
    assert client.get("/api/tasks").json() == []


def test_missing_task_returns_404(client):
    assert client.delete("/api/tasks/9999").status_code == 404
    assert client.post("/api/tasks/9999/toggle").status_code == 404


def test_db_info_reports_record_count(client):
    client.post("/api/tasks", json={"title": "One"})
    client.post("/api/tasks", json={"title": "Two"})

    body = client.get("/api/db/info").json()
    assert body["record_count"] == 2
    assert body["pr_number"] == "42"
    assert body["db_host"] == "postgres.pr-42.svc"
