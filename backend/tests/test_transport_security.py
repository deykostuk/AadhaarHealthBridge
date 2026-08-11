import pytest
from config import settings

def test_hsts_preload_header_present(client):
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    hsts = res.headers.get("Strict-Transport-Security", "")
    assert "max-age=" in hsts
    assert "includeSubDomains" in hsts
    assert "preload" in hsts


def test_https_redirect_on_forwarded_http(client):
    headers = {"X-Forwarded-Proto": "http"}
    res = client.get("/api/v1/health", headers=headers, follow_redirects=False)
    
    # Must return 308 Permanent Redirect to HTTPS
    assert res.status_code == 308
    assert res.headers.get("location", "").startswith("https://")


def test_transport_security_configuration():
    assert hasattr(settings, "ENFORCE_HTTPS")
    assert hasattr(settings, "HSTS_MAX_AGE")
    assert settings.HSTS_MAX_AGE >= 31536000
