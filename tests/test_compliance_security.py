import pytest
from app.utils.pii_masker import PIIMasker
from app.services.lockout_service import AccountLockoutService

def test_pii_masking_compliance():
    """Verifies DPDP Act & UIDAI compliant PII data minimization."""
    # Aadhaar masking (only last 4 digits)
    assert PIIMasker.mask_aadhaar("123456789012") == "XXXX-XXXX-9012"
    assert PIIMasker.mask_aadhaar("1234 5678 9012") == "XXXX-XXXX-9012"
    assert PIIMasker.mask_aadhaar("123") == "XXXX-XXXX-XXXX"

    # Phone masking
    assert PIIMasker.mask_phone("+918604530535") == "+91******0535"
    assert PIIMasker.mask_phone("9876543210") == "98****3210"

    # Email masking
    assert PIIMasker.mask_email("kostuk@example.com") == "k****k@example.com"
    assert PIIMasker.mask_email("a@b.com") == "a*@b.com"


def test_account_lockout_brute_force_defense():
    """Verifies anti-brute-force account lockout logic (OWASP A07:2021)."""
    svc = AccountLockoutService(max_attempts=3, lockout_duration_seconds=60)
    user = "target_user_lockout_test"

    # Initial state: not locked
    is_locked, _ = svc.is_locked(user)
    assert not is_locked

    # 1st and 2nd failed attempts
    svc.record_failed_attempt(user)
    svc.record_failed_attempt(user)
    is_locked, _ = svc.is_locked(user)
    assert not is_locked

    # 3rd failed attempt -> triggers lockout
    attempts, is_now_locked, lock_secs = svc.record_failed_attempt(user)
    assert is_now_locked
    assert attempts == 3
    assert lock_secs == 60

    # Verification of locked state
    is_locked, remaining = svc.is_locked(user)
    assert is_locked
    assert remaining > 0

    # Reset on successful login
    svc.reset_attempts(user)
    is_locked, _ = svc.is_locked(user)
    assert not is_locked


def test_dpdp_dpo_and_privacy_notice_endpoints(client):
    """Verifies DPO contact and DPDP Act 2023 Section 5 privacy notice endpoints."""
    # DPO
    dpo_res = client.get("/api/v1/compliance/dpo")
    assert dpo_res.status_code == 200
    dpo_data = dpo_res.json()
    assert "data_protection_officer" in dpo_data
    assert dpo_data["data_protection_officer"]["email"] == "dpo@aadhaarhealthbridge.in"
    assert "DPDP Act 2023" in dpo_data["compliance_framework"]

    # Privacy Notice
    notice_res = client.get("/api/v1/compliance/privacy-notice")
    assert notice_res.status_code == 200
    notice_data = notice_res.json()
    assert "purposes_of_processing" in notice_data
    assert "categories_of_data_collected" in notice_data
    assert "AES-256-GCM" in notice_data["encryption_standards"]


def test_dpdp_data_portability_and_erasure(client, auth_headers, db):
    """Verifies Data Portability export and Right to be Forgotten (Erasure) endpoints."""
    from app.models.patient import VaultProfile, User

    user = db.query(User).filter(User.username == "test_auth_user").first()
    vault = db.query(VaultProfile).filter(VaultProfile.owner_user_id == user.id).first()

    # 1. Test Data Portability Export
    export_res = client.post(f"/api/v1/compliance/export-data-bundle/{vault.id}", headers=auth_headers)
    assert export_res.status_code == 200
    export_data = export_res.json()
    assert "fhir_r4_bundle" in export_data
    assert export_data["export_metadata"]["vault_id"] == vault.id
    assert "verification_sha256" in export_data["export_metadata"]

    # 2. Test Right to Erasure without confirmation header -> 400 or 422
    fail_purge = client.delete(f"/api/v1/compliance/purge-vault/{vault.id}", headers=auth_headers)
    assert fail_purge.status_code in [400, 422]

    # 3. Test Right to Erasure with confirmation header
    purge_headers = {**auth_headers, "confirmation": "PERMANENTLY_DELETE"}
    purge_res = client.delete(f"/api/v1/compliance/purge-vault/{vault.id}", headers=purge_headers)
    assert purge_res.status_code == 200
    purge_data = purge_res.json()
    assert purge_data["status"] == "success"
    assert "proof_of_erasure" in purge_data
    assert "cryptographic_receipt_sha256" in purge_data["proof_of_erasure"]

    # Verify vault is deleted from database
    deleted_vault = db.query(VaultProfile).filter(VaultProfile.id == vault.id).first()
    assert deleted_vault is None


def test_hardened_security_headers(client):
    """Verifies all OWASP and browser isolation security headers are present."""
    res = client.get("/api/v1/health")
    assert res.headers["X-Frame-Options"] == "DENY"
    assert res.headers["X-Content-Type-Options"] == "nosniff"
    assert "Strict-Transport-Security" in res.headers
    assert "Content-Security-Policy" in res.headers
    assert res.headers["Cross-Origin-Opener-Policy"] == "same-origin"
    assert res.headers["Cross-Origin-Resource-Policy"] == "same-origin"
