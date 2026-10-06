import csv
from io import StringIO

from fastapi.testclient import TestClient
import pytest

import app.main as main
from app.processor import EventProcessor


client = TestClient(main.app)


@pytest.fixture(autouse=True)
def isolated_processor(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(main, "processor", EventProcessor())


def event(source: str, value: float, minute: int, correlation_id: str | None = None) -> dict:
    payload = {
        "source": source,
        "metric": "temperature",
        "value": value,
        "timestamp": f"2026-10-06T12:{minute:02d}:00Z",
    }
    if correlation_id is not None:
        payload["correlation_id"] = correlation_id
    return payload


def rows(response) -> list[dict[str, str]]:
    return list(csv.DictReader(StringIO(response.text)))


def test_csv_export_is_filtered_bounded_and_newest_first() -> None:
    client.post("/events", json=event("sensor-alpha", 70.0, 0, "incident-1"))
    client.post("/events", json=event("sensor-alpha", 150.0, 1, "incident-1"))
    client.post("/events", json=event("sensor-beta", 160.0, 2, "incident-2"))

    response = client.get(
        "/events/export.csv",
        params={"source": "sensor-alpha", "anomalies_only": "true", "limit": 1},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert response.headers["content-disposition"] == (
        'attachment; filename="sentinelstream-events.csv"'
    )
    assert response.headers["x-event-count"] == "1"
    exported = rows(response)[0]
    assert exported == {
        "event_id": exported["event_id"],
        "source": "sensor-alpha",
        "metric": "temperature",
        "correlation_id": "incident-1",
        "value": "150.0",
        "timestamp": "2026-10-06T12:01:00+00:00",
        "anomaly": "True",
        "out_of_order": "False",
    }


def test_csv_export_quotes_fields_and_neutralizes_formulas() -> None:
    client.post(
        "/events",
        json=event('=HYPERLINK("https://example.com")', 70.0, 0, "+incident"),
    )

    exported = rows(client.get("/events/export.csv"))[0]

    assert exported["source"] == "'=HYPERLINK(\"https://example.com\")"
    assert exported["correlation_id"] == "'+incident"


def test_csv_export_empty_history_returns_only_header() -> None:
    response = client.get("/events/export.csv")

    assert response.status_code == 200
    assert response.headers["x-event-count"] == "0"
    assert response.text.splitlines() == [
        "event_id,source,metric,correlation_id,value,timestamp,anomaly,out_of_order"
    ]


def test_csv_export_validates_bounds_and_time_window() -> None:
    assert client.get("/events/export.csv", params={"limit": 1001}).status_code == 422
    response = client.get(
        "/events/export.csv",
        params={
            "since": "2026-10-06T13:00:00Z",
            "until": "2026-10-06T12:00:00Z",
        },
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "since must be earlier than or equal to until"
