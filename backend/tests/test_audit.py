import pytest
import datetime
from app.models.patient import User, VaultProfile, VaultAccess, AuditLog
from app.services.audit_service import AuditService

def test_audit_log_and_fhir_serialization(db):
    user = User(username="audit_owner", password_hash="hash")
    db.add(user)
    db.commit()

    vault = VaultProfile(owner_user_id=user.id, relation="Self", full_name="Subhashish Bose")
    db.add(vault)
    db.commit()

    service = AuditService(db)

    # 1. Log a clinical document upload event
    log = service.log_event(
        action="CREATE",
        event_type="document-upload",
        vault_id=vault.id,
        user_id=user.id,
        resource_type="Document",
        resource_id="doc-42",
        outcome="SUCCESS",
        ip_address="49.37.12.98",
        user_agent="Mozilla/5.0 (Windows NT 10.0)",
        details="Uploaded MRI Scan report PDF"
    )

    assert log.id is not None
    assert log.action == "CREATE"
    assert log.outcome == "SUCCESS"

    # 2. Serialize to FHIR R4 AuditEvent
    fhir_event = AuditService.to_fhir_audit_event(log, vault)
    assert fhir_event["resourceType"] == "AuditEvent"
    assert fhir_event["id"] == f"audit-{log.id}"
    assert fhir_event["action"] == "C"  # Create
    assert fhir_event["outcome"] == "0"  # Success
    assert fhir_event["agent"][0]["network"]["address"] == "49.37.12.98"
    assert fhir_event["entity"][0]["what"]["reference"] == f"Patient/vault-{vault.id}"
    assert fhir_event["entity"][1]["what"]["reference"] == "Document/doc-42"


def test_emergency_scan_audit_event(db):
    user = User(username="patient_emergency", password_hash="hash")
    db.add(user)
    db.commit()

    vault = VaultProfile(owner_user_id=user.id, relation="Self", full_name="Debolina Roy")
    db.add(vault)
    db.commit()

    service = AuditService(db)

    # Log emergency scan from paramedic
    log = service.log_event(
        action="EXECUTE",
        event_type="emergency-qr-scan",
        vault_id=vault.id,
        user_id=None,  # Paramedic / Public Scanner
        resource_type="Patient",
        resource_id=f"vault-{vault.id}",
        outcome="SUCCESS",
        ip_address="103.45.67.89",
        user_agent="Ambulance Scanner Device v2",
        details="Emergency medical access granted via glass-breaker protocol"
    )

    fhir_event = AuditService.to_fhir_audit_event(log, vault)
    assert fhir_event["action"] == "E"
    assert fhir_event["outcome"] == "0"
    assert "Emergency Scanner" in fhir_event["agent"][0]["who"]["display"]
    assert fhir_event["agent"][0]["network"]["address"] == "103.45.67.89"


def test_audit_api_endpoints(client, db):
    # Register & Login
    client.post("/api/v1/auth/signup", json={"username": "audit_api_user", "password": "Password123!"})
    login_res = client.post("/api/v1/auth/login", json={"username": "audit_api_user", "password": "Password123!"})
    token = login_res.json().get("access_token") or login_res.json().get("token")
    headers = {"Authorization": f"Bearer {token}"}

    # Fetch user vault
    vaults_res = client.get("/api/v1/vaults", headers=headers)
    vault_id = vaults_res.json()[0]["id"]

    # Log sample events via service
    service = AuditService(db)
    user = db.query(User).filter(User.username == "audit_api_user").first()
    log1 = service.log_event(action="READ", event_type="rest-read", vault_id=vault_id, user_id=user.id, details="Viewed vault")
    log2 = service.log_event(action="UPDATE", event_type="profile-edit", vault_id=vault_id, user_id=user.id, details="Updated emergency contact")

    # 1. GET /api/v1/vaults/{vault_id}/audit-trail
    trail_res = client.get(f"/api/v1/vaults/{vault_id}/audit-trail", headers=headers)
    assert trail_res.status_code == 200
    assert len(trail_res.json()) >= 2
    assert "fhir_audit_event" in trail_res.json()[0]

    # 2. GET /api/v1/fhir/AuditEvent?patient={vault_id}
    fhir_bundle_res = client.get(f"/api/v1/fhir/AuditEvent?patient={vault_id}", headers=headers)
    assert fhir_bundle_res.status_code == 200
    assert fhir_bundle_res.json()["resourceType"] == "Bundle"
    assert fhir_bundle_res.json()["type"] == "searchset"
    assert len(fhir_bundle_res.json()["entry"]) >= 2

    # 3. GET /api/v1/fhir/AuditEvent/{event_id}
    single_res = client.get(f"/api/v1/fhir/AuditEvent/{log1.id}", headers=headers)
    assert single_res.status_code == 200
    assert single_res.json()["resourceType"] == "AuditEvent"
    assert single_res.json()["id"] == f"audit-{log1.id}"
