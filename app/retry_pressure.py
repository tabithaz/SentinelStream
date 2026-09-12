def analyze_retry_pressure(attempted: int, retried: int, exhausted: int) -> dict:
    values = (attempted, retried, exhausted)
    if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in values):
        raise ValueError("retry counters must be non-negative integers")
    if retried > attempted or exhausted > retried:
        raise ValueError("retry counters are inconsistent")

    retry_rate = 0.0 if attempted == 0 else retried / attempted
    exhaustion_rate = 0.0 if retried == 0 else exhausted / retried
    pressure_score = min(100.0, retry_rate * 70 + exhaustion_rate * 30)

    if attempted == 0 or pressure_score < 15:
        status = "healthy"
    elif pressure_score < 40:
        status = "elevated"
    else:
        status = "critical"

    return {
        "retry_rate": round(retry_rate, 4),
        "exhaustion_rate": round(exhaustion_rate, 4),
        "pressure_score": round(pressure_score, 2),
        "status": status,
    }
