import pytest
import jwt
import datetime
from config import settings
from app.models.patient import User, VaultProfile, VaultAccess
from app.middleware.security import SSRFValidator

def test_owasp_security_headers_present(client):
    res = client.get("/api/v1/health")
    assert res.status_code == 200

    # 1. Clickjacking Protection (OWASP A05)
    assert res.headers.get("X-Frame-Options") == "DENY"

    # 2. MIME Sniffing Defense (OWASP A05)
    assert res.headers.get("X-Content-Type-Options") == "nosniff"

    # 3. HSTS Header (OWASP A02 / Transport Security)
    assert "Strict-Transport-Security" in res.headers
    assert "max-age=" in res.headers["Strict-Transport-Security"]

    # 4. Content Security Policy (OWASP A03/A05)
    assert "Content-Security-Policy" in res.headers
    assert "frame-ancestors 'none'" in res.headers["Content-Security-Policy"]

    # 5. Referrer Policy & Permissions Policy
    assert res.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert "geolocation" in res.headers.get("Permissions-Policy", "")


def test_owasp_ssrf_validator():
    # 1. Dangerous / Internal Loopback Addresses (MUST be blocked)
    unsafe_targets = [
        "http://127.0.0.1:8080/admin",
        "http://localhost:5000/internal",
        "http://169.254.169.254/latest/meta-data/",
        "http://10.0.0.5/api",
        "http://192.168.1.1/router",
        "ftp://example.com/file"  # non-http scheme
    ]

    for target in unsafe_targets:
        is_safe, reason = SSRFValidator.is_safe_url(target)
        assert is_safe is False, f"SSRF Validator failed to block unsafe target: {target}"
        assert reason is not None

    # 2. Public Safe URL (Must be allowed)
    is_safe, _ = SSRFValidator.is_safe_url("https://hl7.org/fhir/R4/patient.html")
    assert is_safe is True


def test_owasp_bola_cross_tenant_rejection(client, db):
    # Setup User A with Vault A
    user_a = User(username="victim_user", password_hash="hash")
    db.add(user_a)
    db.commit()
    vault_a = VaultProfile(owner_user_id=user_a.id, relation="Self", full_name="Victim Vault")
    db.add(vault_a)
    db.commit()

    # Setup User B (Attacker)
    user_b = User(username="attacker_user", password_hash="hash")
    db.add(user_b)
    db.commit()

    # Authenticate as User B using JWT
    payload = {
        "sub": str(user_b.id),
        "username": user_b.username,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=1)
    }
    token_b = jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")

    # Attacker tries to read Victim's Vault (BOLA / IDOR attack)
    headers = {"Authorization": f"Bearer {token_b}"}
    res = client.get(f"/api/v1/vaults/{vault_a.id}", headers=headers)

    # Must reject with 403 Forbidden
    assert res.status_code == 403
    assert "Unauthorized" in str(res.json().get("detail", "")) or "Forbidden" in str(res.json().get("detail", ""))
