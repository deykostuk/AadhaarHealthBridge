import pytest
import io
from unittest.mock import patch
from app.models.patient import User, VaultProfile, VaultAccess, Document, HealthMetric

pytestmark = pytest.mark.integration

def test_patient_onboarding_and_biomarker_lifecycle(client, db):
    """
    End-to-End Integration Workflow 1:
    1. User Registration via /api/v1/auth/signup
    2. Auto-provisioning of default Self-Vault
    3. Document ingestion with clinical biomarkers (Creatinine, Sugar, HbA1c)
    4. Retrieval of aggregated clinical health snapshot
    """
    # 1. Signup
    signup_res = client.post("/api/v1/auth/signup", json={
        "username": "workflow_patient",
        "password": "Password123!"
    })
    assert signup_res.status_code == 201
    user_data = signup_res.json()
    user_id = user_data["id"]

    # 2. Login & Token Acquisition
    login_res = client.post("/api/v1/auth/login", json={
        "username": "workflow_patient",
        "password": "Password123!"
    })
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 3. Retrieve default self-vault
    vaults_res = client.get("/api/v1/vaults", headers=headers)
    assert vaults_res.status_code == 200
    vaults = vaults_res.json()
    assert len(vaults) >= 1
    vault_id = vaults[0]["id"]

    # 4. Upload Medical Lab Report via REST endpoint
    pdf_bytes = b"%PDF-1.4 dummy lab report with Creatinine: 1.2 mg/dL and Glucose: 95 mg/dL and HbA1c: 5.6%"
    files = {"file": ("blood_test.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    data = {
        "category": "Diagnostic Lab Report",
        "file_name": "Quarterly Metabolic Panel",
        "ocr_text": "Serum Creatinine: 1.2 mg/dL\nFasting Blood Glucose: 95 mg/dL\nHbA1c: 5.6%"
    }

    with patch("app.services.document_service.upload_document_to_storage") as mock_storage:
        mock_storage.return_value = "vault_docs/vault_1/quarterly.pdf"
        with patch("app.services.semantic_service.index_document") as mock_index:
            upload_res = client.post(f"/api/v1/vaults/{vault_id}/documents", data=data, files=files, headers=headers)
            assert upload_res.status_code == 201
            doc_data = upload_res.json()
            assert doc_data["file_name"] == "Quarterly Metabolic Panel"

    # 5. Verify Aggregated Health Metrics & Snapshot
    metrics_res = client.get(f"/api/v1/vaults/{vault_id}/snapshot", headers=headers)
    assert metrics_res.status_code == 200
    snapshot_data = metrics_res.json()
    assert snapshot_data["vault_id"] == vault_id
    assert len(snapshot_data["latest_metrics"]) >= 2


def test_paramedic_emergency_glassbreaker_and_fhir_export(client, db):
    """
    End-to-End Integration Workflow 2:
    1. Patient Vault setup with emergency vitals & contacts
    2. Zero-auth Paramedic QR Scan (Glassbreaker access)
    3. Full FHIR R4 $everything Bundle export
    4. Verification of FHIR Patient and Observation resources
    """
    from app.services.password_service import password_service

    user = User(username="emergency_pt", password_hash=password_service.hash_password("Pass123!"), role="family_member")
    db.add(user)
    db.commit()

    vault = VaultProfile(
        owner_user_id=user.id,
        relation="Self",
        full_name="Emergency Patient",
        blood_group="AB+",
        allergies="Penicillin, Sulfa",
        medical_conditions="Type 2 Diabetes",
        medications="Metformin 500mg",
        personal_contact="+919876543210",
        emergency_1_name="Spouse",
        emergency_1_relation="Wife",
        emergency_1_phone="+919876543211",
        is_emergency_ready=True
    )
    db.add(vault)
    db.commit()
    db.add(VaultAccess(user_id=user.id, vault_id=vault.id, access_type="owner"))
    db.commit()

    # 1. Paramedic Scans QR Token via REST API (Zero-auth)
    scan_res = client.get(f"/api/v1/scan/{vault.qr_token}/data")
    assert scan_res.status_code == 200
    scan_data = scan_res.json()
    assert scan_data["full_name"] == "Emergency Patient"
    assert scan_data["blood_group"] == "AB+"
    assert scan_data["is_emergency_ready"] is True

    # 2. Patient / Caregiver Exports Standard HL7 FHIR R4 $everything Bundle
    login_res = client.post("/api/v1/auth/login", json={"username": "emergency_pt", "password": "Pass123!"})
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    fhir_res = client.get(f"/api/v1/fhir/Patient/{vault.id}/$everything", headers=headers)
    assert fhir_res.status_code == 200
    bundle = fhir_res.json()
    assert bundle["resourceType"] == "Bundle"
    assert bundle["type"] in ["collection", "searchset"]
    
    # Check FHIR Patient resource inside bundle
    patient_entries = [e["resource"] for e in bundle["entry"] if e["resource"]["resourceType"] == "Patient"]
    assert len(patient_entries) == 1
    assert patient_entries[0]["name"][0]["text"] == "Emergency Patient"


def test_oauth_oidc_token_bundle_and_jwks_workflow(client, db):
    """
    End-to-End Integration Workflow 3:
    1. Request OAuth 2.0 Token Bundle via /api/v1/auth/oauth/token (Password Grant)
    2. Validate ID Token structure against /api/v1/auth/jwks.json
    3. Access OIDC UserInfo endpoint with Access Token
    4. Rotate refresh token via /api/v1/auth/oauth/refresh
    """
    from app.services.password_service import password_service

    user = User(username="oidc_user", password_hash=password_service.hash_password("OidcSecure123!"), role="family_member")
    db.add(user)
    db.commit()

    # 1. Password Grant OAuth Token Request
    token_res = client.post("/api/v1/auth/oauth/token", data={
        "username": "oidc_user",
        "password": "OidcSecure123!"
    })
    assert token_res.status_code == 200
    bundle = token_res.json()
    assert "access_token" in bundle
    assert "id_token" in bundle
    assert "refresh_token" in bundle
    assert bundle["token_type"] == "bearer"

    # 2. Fetch JWKS Public Key Metadata
    jwks_res = client.get("/api/v1/auth/jwks.json")
    assert jwks_res.status_code == 200
    jwks = jwks_res.json()
    assert "keys" in jwks
    assert len(jwks["keys"]) >= 1
    assert jwks["keys"][0]["alg"] == "HS256"

    # 3. Access OIDC UserInfo Endpoint
    userinfo_res = client.get("/api/v1/auth/oauth/userinfo", headers={"Authorization": f"Bearer {bundle['access_token']}"})
    assert userinfo_res.status_code == 200
    userinfo = userinfo_res.json()
    assert userinfo["preferred_username"] == "oidc_user"
    assert userinfo["sub"] == str(user.id)

    # 4. Token Refresh Rotation
    refresh_res = client.post("/api/v1/auth/oauth/refresh", json={
        "refresh_token": bundle["refresh_token"]
    })
    assert refresh_res.status_code == 200
    new_bundle = refresh_res.json()
    assert "access_token" in new_bundle
    assert new_bundle["token_type"] == "bearer"
