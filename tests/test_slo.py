from fastapi.testclient import TestClient
import pytest

import app.main as main
from app.processor import EventProcessor
from app.slo import summarize_event_slo


def _events(total: int, bad: int) -> list[dict]:
    return [
        {"anomaly": index < bad, "out_of_order": False}
        for index in range(total)
    ]


def test_slo_reports_no_data_without_inventing_reliability() -> None:
    result = summarize_event_slo([], target_percent=99, window_events=500)

    assert result["status"] == "no_data"
    assert result["reliability_percent"] is None
    assert result["error_budget_consumed_percent"] is None
    assert result["window_events"] == 500


def test_slo_reports_healthy_remaining_error_budget() -> None:
    result = summarize_event_slo(_events(100, 1), target_percent=95)

    assert result["status"] == "healthy"
    assert result["reliability_percent"] == 99.0
    assert result["allowed_bad_events"] == 5.0
    assert result["remaining_error_budget_events"] == 4.0
    assert result["error_budget_consumed_percent"] == 20.0


def test_slo_flags_at_risk_and_exhausted_budgets() -> None:
    at_risk = summarize_event_slo(_events(20, 3), target_percent=80)
    exhausted = summarize_event_slo(_events(10, 2), target_percent=90)

    assert at_risk["status"] == "at_risk"
    assert at_risk["error_budget_consumed_percent"] == 75.0
    assert exhausted["status"] == "exhausted"
    assert exhausted["error_budget_consumed_percent"] == 200.0
    assert exhausted["remaining_error_budget_events"] == 0.0


def test_slo_handles_a_perfect_target_without_dividing_by_zero() -> None:
    healthy = summarize_event_slo(_events(10, 0), target_percent=100)
    exhausted = summarize_event_slo(_events(10, 1), target_percent=100)

    assert healthy["status"] == "healthy"
    assert healthy["error_budget_consumed_percent"] == 0.0
    assert exhausted["status"] == "exhausted"
    assert exhausted["error_budget_consumed_percent"] is None


def test_slo_rejects_invalid_configuration() -> None:
    with pytest.raises(ValueError, match="target_percent"):
        summarize_event_slo([], target_percent=0)
    with pytest.raises(ValueError, match="window_events"):
        summarize_event_slo([], window_events=0)


def test_slo_endpoint_uses_a_bounded_recent_window() -> None:
    main.processor = EventProcessor()
    client = TestClient(main.app)
    events = [
        {
            "source": "sensor-a",
            "metric": "temperature",
            "value": value,
            "timestamp": f"2026-10-01T12:00:0{index}Z",
        }
        for index, value in enumerate([150.0, 70.0, 72.0])
    ]
    assert client.post("/events/batch", json=events).status_code == 200

    response = client.get("/events/slo?target_percent=90&window_events=2")

    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy",
        "target_percent": 90.0,
        "window_events": 2,
        "events_evaluated": 2,
        "good_events": 2,
        "bad_events": 0,
        "reliability_percent": 100.0,
        "allowed_bad_events": 0.2,
        "remaining_error_budget_events": 0.2,
        "error_budget_consumed_percent": 0.0,
    }


def test_slo_endpoint_validates_query_bounds() -> None:
    main.processor = EventProcessor()
    client = TestClient(main.app)

    assert client.get("/events/slo?target_percent=0").status_code == 422
    assert client.get("/events/slo?window_events=1001").status_code == 422
