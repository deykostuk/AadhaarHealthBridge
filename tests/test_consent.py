import pytest
import datetime
from app.models.patient import User, VaultProfile, VaultAccess, ConsentRecord
from app.services.consent_service import ConsentService

def test_consent_creation_and_fhir_serialization(db):
    user = User(username="consent_owner", password_hash="hash")
    db.add(user)
    db.commit()

    vault = VaultProfile(owner_user_id=user.id, relation="Self", full_name="Sunil Sengupta")
    db.add(vault)
    db.commit()

    service = ConsentService(db)

    # 1. Create a 30-minute consent policy for a doctor
    consent = service.create_consent(
        vault_id=vault.id,
        granter_user_id=user.id,
        grantee_identifier="dr_sharma",
        consent_type="patient-privacy",
        purpose="TREAT",
        duration_minutes=30,
        allowed_resources="Observation,DiagnosticReport"
    )

    assert consent.id is not None
    assert consent.status == "active"
    assert consent.valid_to is not None

    # 2. Serialize to FHIR R4 Consent
    fhir_consent = ConsentService.to_fhir_consent(consent, vault)
    assert fhir_consent["resourceType"] == "Consent"
    assert fhir_consent["status"] == "active"
    assert fhir_consent["patient"]["reference"] == f"Patient/vault-{vault.id}"
    assert fhir_consent["provision"]["type"] == "permit"
    assert fhir_consent["provision"]["purpose"][0]["code"] == "TREAT"
    assert "start" in fhir_consent["provision"]["period"]


def test_consent_verification_and_expiry(db):
    user = User(username="verify_user", password_hash="hash")
    db.add(user)
    db.commit()

    vault = VaultProfile(owner_user_id=user.id, relation="Self", full_name="Ananya Sen")
    db.add(vault)
    db.commit()

    service = ConsentService(db)

    # 1. Active policy for specific doctor
    service.create_consent(
        vault_id=vault.id,
        granter_user_id=user.id,
        grantee_identifier="dr_mukherjee",
        purpose="TREAT",
        allowed_resources="Observation"
    )

    # Valid doctor + matching resource
    allowed, msg = service.verify_consent(vault.id, "dr_mukherjee", purpose="TREAT", resource_type="Observation")
    assert allowed is True

    # Unauthorized doctor
    denied, msg = service.verify_consent(vault.id, "unauthorized_doc", purpose="TREAT", resource_type="Observation")
    assert denied is False

    # Emergency glass-breaker override always permitted and creates immutable audit record
    emerg_allowed, emerg_msg = service.verify_consent(vault.id, "paramedic_108", purpose="EMERGENCY")
    assert emerg_allowed is True
    assert "Emergency protocol" in emerg_msg

    from app.models.patient import AuditLog
    audit_entry = db.query(AuditLog).filter(
        AuditLog.vault_id == vault.id,
        AuditLog.event_type == "emergency-override"
    ).first()
    assert audit_entry is not None
    assert "paramedic_108" in audit_entry.details
    assert audit_entry.outcome == "SUCCESS"


def test_consent_revocation(db):
    user = User(username="revoke_user", password_hash="hash")
    db.add(user)
    db.commit()

    vault = VaultProfile(owner_user_id=user.id, relation="Self", full_name="Manish Roy")
    db.add(vault)
    db.commit()

    service = ConsentService(db)
    consent = service.create_consent(
        vault_id=vault.id,
        granter_user_id=user.id,
        grantee_identifier="dr_test",
        purpose="TREAT"
    )

    # Before revocation
    allowed, _ = service.verify_consent(vault.id, "dr_test", purpose="TREAT")
    assert allowed is True

    # Revoke
    success, err = service.revoke_consent(consent.id, user.id)
    assert success is True

    # After revocation
    allowed_after, _ = service.verify_consent(vault.id, "dr_test", purpose="TREAT")
    assert allowed_after is False


def test_consent_api_endpoints(client, db):
    # Register & Login
    client.post("/api/v1/auth/signup", json={"username": "consent_api_user", "password": "Password123!"})
    login_res = client.post("/api/v1/auth/login", json={"username": "consent_api_user", "password": "Password123!"})
    token = login_res.json().get("access_token") or login_res.json().get("token")
    headers = {"Authorization": f"Bearer {token}"}

    # Fetch user vault
    vaults_res = client.get("/api/v1/vaults", headers=headers)
    vault_id = vaults_res.json()[0]["id"]

    # 1. POST /api/v1/vaults/{vault_id}/consents
    post_res = client.post(
        f"/api/v1/vaults/{vault_id}/consents",
        json={
            "grantee_identifier": "apollo_hospital_doc",
            "consent_type": "patient-privacy",
            "purpose": "TREAT",
            "duration_minutes": 60,
            "allowed_resources": "all"
        },
        headers=headers
    )
    assert post_res.status_code == 200
    consent_id = post_res.json()["consent"]["id"].replace("consent-", "")

    # 2. GET /api/v1/vaults/{vault_id}/consents
    list_res = client.get(f"/api/v1/vaults/{vault_id}/consents", headers=headers)
    assert list_res.status_code == 200
    assert len(list_res.json()) >= 1

    # 3. GET /api/v1/fhir/Consent?patient={vault_id}
    fhir_search = client.get(f"/api/v1/fhir/Consent?patient={vault_id}", headers=headers)
    assert fhir_search.status_code == 200
    assert fhir_search.json()["resourceType"] == "Bundle"
    assert len(fhir_search.json()["entry"]) >= 1

    # 4. DELETE /api/v1/vaults/{vault_id}/consents/{consent_id}
    del_res = client.delete(f"/api/v1/vaults/{vault_id}/consents/{consent_id}", headers=headers)
    assert del_res.status_code == 200
