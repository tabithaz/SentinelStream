from fastapi.testclient import TestClient

from app.main import app
from app.provenance import MAX_METADATA_LENGTH, runtime_provenance


def test_health_identifies_running_release(monkeypatch) -> None:
    monkeypatch.setenv("SENTINELSTREAM_RELEASE", "1.4.0-rc.2")
    monkeypatch.setenv("SENTINELSTREAM_REVISION", "5f7a9c1")

    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy",
        "service": "sentinelstream",
        "version": "1.4.0-rc.2",
        "revision": "5f7a9c1",
    }


def test_provenance_rejects_control_characters_and_bounds_labels(monkeypatch) -> None:
    monkeypatch.setenv("SENTINELSTREAM_RELEASE", "unsafe\nrelease")
    monkeypatch.setenv("SENTINELSTREAM_REVISION", "a" * 200)

    provenance = runtime_provenance()

    assert provenance["version"] == "1.4.0"
    assert provenance["revision"] == "a" * MAX_METADATA_LENGTH
