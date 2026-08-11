import pytest

def test_pwa_manifest_endpoint(client):
    res = client.get("/manifest.json")
    assert res.status_code == 200
    manifest = res.json()
    assert manifest["short_name"] == "HealthBridge"
    assert manifest["display"] == "standalone"
    assert manifest["start_url"] == "/"
    assert len(manifest["icons"]) >= 2


def test_pwa_service_worker_secure_caching(client):
    res = client.get("/sw.js")
    assert res.status_code == 200
    assert "javascript" in res.headers.get("content-type", "").lower()
    
    # 1. Partitioned Cache Namespaces
    assert "healthbridge-static-v2" in res.text
    assert "healthbridge-emergency-v2" in res.text

    # 2. Sensitive PHI / Auth Cache Denial Rules
    assert "/api/v1/auth" in res.text
    assert "/api/v1/vaults" in res.text
    assert "Authorization" in res.text
    assert "no-store" in res.text

    # 3. Secure Cache Purge on Logout
    assert "PURGE_SECURE_CACHE" in res.text


def test_pwa_app_shell_root(client):
    res = client.get("/")
    assert res.status_code == 200
    assert "text/html" in res.headers.get("content-type", "").lower()
    assert "manifest.json" in res.text
    assert "app.js" in res.text
    assert "Aadhaar Health Bridge" in res.text


def test_pwa_offline_emergency_page(client):
    res = client.get("/static/offline_emergency.html")
    assert res.status_code == 200
    assert "text/html" in res.headers.get("content-type", "").lower()
    assert "Offline Medical Card" in res.text or "Emergency" in res.text
