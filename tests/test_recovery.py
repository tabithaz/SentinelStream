from app.recovery import recommend_recovery


def test_normal_operation_requires_no_recovery():
    assert recommend_recovery(0.01, 0.2, 0).action == "normal"


def test_backoff_for_early_pressure():
    result = recommend_recovery(0.2, 0.55, 1)
    assert result.action == "backoff"
    assert result.retry_delay_seconds == 2.0


def test_throttle_for_sustained_pressure():
    result = recommend_recovery(0.3, 0.75, 3)
    assert result.action == "throttle"
    assert result.shed_load_percent == 25.0


def test_open_circuit_for_severe_error_rate():
    result = recommend_recovery(0.95, 0.4, 1)
    assert result.action == "open_circuit"
    assert result.retry_delay_seconds == 30.0
