import pytest
import time
from app.middleware.rate_limiter import limiter

def test_rate_limit_headers_present(client):
    # Ensure fresh storage for test
    limiter.storage.clear()

    res = client.get("/api/v1/health")
    assert res.status_code == 200
    assert "X-RateLimit-Limit" in res.headers
    assert "X-RateLimit-Remaining" in res.headers
    assert "X-RateLimit-Reset" in res.headers


def test_auth_tier_rate_limit_triggers_429(client):
    limiter.storage.clear()
    client_ip = "192.168.1.55"
    headers = {"X-Forwarded-For": client_ip}

    # Auth tier has a strict limit of 5 requests/min
    for i in range(5):
        res = client.post("/api/v1/auth/login", json={"username": "kostuk", "password": "wrong_password"}, headers=headers)
        assert res.status_code in [200, 401]

    # 6th request from same IP must be throttled with 429
    res = client.post("/api/v1/auth/login", json={"username": "kostuk", "password": "wrong_password"}, headers=headers)
    assert res.status_code == 429
    data = res.json()
    assert data["status"] == "error"
    assert "Rate limit exceeded" in data["message"]
    assert "Retry-After" in res.headers
    assert res.headers["X-RateLimit-Remaining"] == "0"


def test_rate_limit_ip_isolation(client):
    limiter.storage.clear()
    ip_a = "10.0.0.1"
    ip_b = "10.0.0.2"

    # Exhaust quota for IP A
    for _ in range(5):
        client.post("/api/v1/auth/login", json={"username": "kostuk", "password": "pwd"}, headers={"X-Forwarded-For": ip_a})

    # IP A gets 429
    res_a = client.post("/api/v1/auth/login", json={"username": "kostuk", "password": "pwd"}, headers={"X-Forwarded-For": ip_a})
    assert res_a.status_code == 429

    # IP B is fresh and should not be throttled with 429
    res_b = client.post("/api/v1/auth/login", json={"username": "kostuk", "password": "Demo1234!"}, headers={"X-Forwarded-For": ip_b})
    assert res_b.status_code != 429
