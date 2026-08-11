import pytest
import datetime
from app.models.patient import User, VaultProfile, VaultAccess, ProvenanceRecord
from app.services.provenance_service import ProvenanceService

def test_provenance_recording_and_fhir_serialization(db):
    user = User(username="prov_owner", password_hash="hash")
    db.add(user)
    db.commit()

    vault = VaultProfile(owner_user_id=user.id, relation="Self", full_name="Nilanjan Dutta")
    db.add(vault)
    db.commit()

    service = ProvenanceService(db)

    # 1. Record document upload provenance with SHA-256 integrity hash
    sample_file_content = b"PDF Blood Report Data for Nilanjan Dutta"
    doc_prov = service.record_provenance(
        vault_id=vault.id,
        target_type="DocumentReference",
        target_id="doc-101",
        activity="CREATE",
        agent_type="author",
        agent_name="Dr. S. Mukherjee (Apollo Clinic)",
        file_bytes=sample_file_content
    )

    assert doc_prov.id is not None
    assert doc_prov.activity == "CREATE"
    assert doc_prov.integrity_hash is not None
    assert len(doc_prov.integrity_hash) == 64

    # 2. Record AI Extraction lineage linking derived Observation back to source Document
    obs_prov = service.record_provenance(
        vault_id=vault.id,
        target_type="Observation",
        target_id="obs-202",
        activity="EXTRACT",
        agent_type="ai-extractor",
        agent_name="AadhaarHealthBridge PyMuPDF Clinical Extraction Engine",
        source_reference="DocumentReference/doc-101"
    )

    assert obs_prov.activity == "EXTRACT"
    assert obs_prov.source_reference == "DocumentReference/doc-101"

    # 3. Verify FHIR R4 Provenance Serialization
    fhir_doc_prov = ProvenanceService.to_fhir_provenance(doc_prov, vault)
    assert fhir_doc_prov["resourceType"] == "Provenance"
    assert fhir_doc_prov["id"] == f"provenance-{doc_prov.id}"
    assert fhir_doc_prov["target"][0]["reference"] == "DocumentReference/doc-101"
    assert fhir_doc_prov["activity"]["coding"][0]["code"] == "CREATE"
    assert fhir_doc_prov["agent"][0]["type"]["coding"][0]["code"] == "author"
    assert fhir_doc_prov["signature"][0]["data"] == doc_prov.integrity_hash

    fhir_obs_prov = ProvenanceService.to_fhir_provenance(obs_prov, vault)
    assert fhir_obs_prov["target"][0]["reference"] == "Observation/obs-202"
    assert fhir_obs_prov["entity"][0]["role"] == "source"
    assert fhir_obs_prov["entity"][0]["what"]["reference"] == "DocumentReference/doc-101"


def test_provenance_api_endpoints(client, db):
    # Register & Login
    client.post("/api/v1/auth/signup", json={"username": "prov_api_user", "password": "Password123!"})
    login_res = client.post("/api/v1/auth/login", json={"username": "prov_api_user", "password": "Password123!"})
    token = login_res.json().get("access_token") or login_res.json().get("token")
    headers = {"Authorization": f"Bearer {token}"}

    # Fetch user vault
    vaults_res = client.get("/api/v1/vaults", headers=headers)
    vault_id = vaults_res.json()[0]["id"]

    # Record sample provenance via service
    service = ProvenanceService(db)
    p1 = service.record_provenance(
        vault_id=vault_id,
        target_type="DocumentReference",
        target_id="doc-50",
        activity="CREATE",
        agent_name="Lab Technician",
        file_bytes=b"sample lab report"
    )

    # 1. GET /api/v1/vaults/{vault_id}/provenance
    list_res = client.get(f"/api/v1/vaults/{vault_id}/provenance", headers=headers)
    assert list_res.status_code == 200
    assert len(list_res.json()) >= 1
    assert "fhir_provenance" in list_res.json()[0]

    # 2. GET /api/v1/fhir/Provenance?patient={vault_id}
    fhir_search = client.get(f"/api/v1/fhir/Provenance?patient={vault_id}", headers=headers)
    assert fhir_search.status_code == 200
    assert fhir_search.json()["resourceType"] == "Bundle"
    assert fhir_search.json()["type"] == "searchset"
    assert len(fhir_search.json()["entry"]) >= 1

    # 3. GET /api/v1/fhir/Provenance/{provenance_id}
    single_res = client.get(f"/api/v1/fhir/Provenance/{p1.id}", headers=headers)
    assert single_res.status_code == 200
    assert single_res.json()["resourceType"] == "Provenance"
    assert single_res.json()["id"] == f"provenance-{p1.id}"
