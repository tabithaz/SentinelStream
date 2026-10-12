from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


EXPECTED_HEADERS = {
    "content-security-policy": (
        "base-uri 'self'; form-action 'self'; frame-ancestors 'none'; "
        "object-src 'none'"
    ),
    "permissions-policy": "camera=(), geolocation=(), microphone=()",
    "referrer-policy": "no-referrer",
    "x-content-type-options": "nosniff",
    "x-frame-options": "DENY",
}


def _assert_security_headers(response) -> None:
    for name, value in EXPECTED_HEADERS.items():
        assert response.headers[name] == value


def test_security_headers_protect_api_and_dashboard_responses() -> None:
    for path in ("/health", "/dashboard", "/does-not-exist"):
        _assert_security_headers(client.get(path))


def test_security_headers_protect_early_authentication_rejections(monkeypatch) -> None:
    monkeypatch.setenv("SENTINELSTREAM_API_KEY", "expected-secret")

    response = client.post(
        "/events",
        json={
            "source": "sensor-alpha",
            "metric": "temperature",
            "value": 72.4,
            "timestamp": "2026-09-22T18:00:00Z",
        },
    )

    assert response.status_code == 401
    _assert_security_headers(response)
