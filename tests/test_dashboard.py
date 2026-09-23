from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_dashboard_is_served() -> None:
    response = client.get("/dashboard")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "SentinelStream Operations" in response.text
    assert 'id="event-form"' in response.text


def test_dashboard_integrates_with_operational_endpoints() -> None:
    response = client.get("/dashboard")

    assert "fetch('/events'" in response.text
    assert "fetch('/events/stats')" in response.text
    assert "fetch('/events/reliability')" in response.text
    assert "fetch('/events/recent?limit=12')" in response.text
