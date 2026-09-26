import json
import logging
import re

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_request_id_is_preserved_and_logged(caplog) -> None:
    with caplog.at_level(logging.INFO, logger="sentinelstream.access"):
        response = client.get("/health", headers={"X-Request-ID": "deploy-2026.09.26:42"})

    assert response.status_code == 200
    assert response.headers["x-request-id"] == "deploy-2026.09.26:42"
    record = json.loads(caplog.records[-1].message)
    assert record["request_id"] == "deploy-2026.09.26:42"
    assert record["method"] == "GET"
    assert record["path"] == "/health"
    assert record["status_code"] == 200
    assert record["duration_ms"] >= 0


def test_invalid_request_id_is_replaced() -> None:
    response = client.get("/health", headers={"X-Request-ID": "unsafe id with spaces"})

    assert response.status_code == 200
    assert re.fullmatch(r"[0-9a-f]{32}", response.headers["x-request-id"])


def test_validation_errors_include_request_id() -> None:
    response = client.get("/events/recent?limit=0")

    assert response.status_code == 422
    assert re.fullmatch(r"[0-9a-f]{32}", response.headers["x-request-id"])
