import pytest
import datetime
from app.models.patient import User, VaultProfile, VaultAccess, HealthMetric, Document
from app.services.fhir_service import FHIRService, fhir_service

def test_fhir_patient_mapping(db):
    user = User(username="fhir_user", password_hash="hash")
    db.add(user)
    db.commit()

    vault = VaultProfile(
        owner_user_id=user.id,
        relation="Self",
        full_name="Rajesh Sharma",
        blood_group="B+",
        personal_contact="9876543210",
        emergency_1_name="Pooja Sharma",
        emergency_1_relation="Spouse",
        emergency_1_phone="9876543211",
        allergies="Aspirin, Ibuprofen",
        medical_conditions="Type 2 Diabetes, Hypertension"
    )
    db.add(vault)
    db.commit()

    # 1. Patient Resource Verification
    patient_res = fhir_service.to_fhir_patient(vault)
    assert patient_res["resourceType"] == "Patient"
    assert patient_res["id"] == f"vault-{vault.id}"
    assert patient_res["name"][0]["text"] == "Rajesh Sharma"
    assert patient_res["active"] is True
    assert len(patient_res["contact"]) >= 1
    assert patient_res["contact"][0]["name"]["text"] == "Pooja Sharma"
    assert patient_res["contact"][0]["relationship"][0]["text"] == "Spouse"
    assert patient_res["telecom"][0]["value"] == "9876543210"

    # Blood group extension
    assert any(ext["valueString"] == "B+" for ext in patient_res.get("extension", []))

    # 2. AllergyIntolerance Resources
    allergies = fhir_service.to_fhir_allergies(vault)
    assert len(allergies) == 2
    assert allergies[0]["resourceType"] == "AllergyIntolerance"
    assert allergies[0]["code"]["text"] in ["Aspirin", "Ibuprofen"]
    assert allergies[0]["clinicalStatus"]["coding"][0]["code"] == "active"

    # 3. Condition Resources
    conditions = fhir_service.to_fhir_conditions(vault)
    assert len(conditions) == 2
    assert conditions[0]["resourceType"] == "Condition"
    assert conditions[0]["clinicalStatus"]["coding"][0]["code"] == "active"


def test_fhir_observation_loinc_mapping(db):
    user = User(username="obs_user", password_hash="hash")
    db.add(user)
    db.commit()

    vault = VaultProfile(owner_user_id=user.id, relation="Self", full_name="Sneha Roy")
    db.add(vault)
    db.commit()

    metric = HealthMetric(
        vault_id=vault.id,
        metric_name="creatinine",
        metric_value=1.15,
        metric_unit="mg/dL",
        observed_date=datetime.datetime(2026, 4, 15, 10, 30)
    )
    db.add(metric)
    db.commit()

    obs_res = fhir_service.to_fhir_observation(metric, vault)
    assert obs_res["resourceType"] == "Observation"
    assert obs_res["status"] == "final"
    assert obs_res["category"][0]["coding"][0]["code"] == "laboratory"
    # LOINC code for Creatinine
    assert obs_res["code"]["coding"][0]["code"] == "2160-0"
    assert obs_res["code"]["coding"][0]["system"] == "http://loinc.org"
    assert obs_res["valueQuantity"]["value"] == 1.15
    assert obs_res["valueQuantity"]["unit"] == "mg/dL"
    assert obs_res["subject"]["reference"] == f"Patient/vault-{vault.id}"


def test_fhir_document_reference_and_bundle(db):
    user = User(username="bundle_user", password_hash="hash")
    db.add(user)
    db.commit()

    vault = VaultProfile(owner_user_id=user.id, relation="Self", full_name="Amit Patel")
    db.add(vault)
    db.commit()

    doc = Document(
        vault_id=vault.id,
        file_name="blood_report.pdf",
        file_path="uploads/blood_report.pdf",
        category="Lab Report"
    )
    metric = HealthMetric(
        vault_id=vault.id,
        metric_name="sugar",
        metric_value=98.0,
        metric_unit="mg/dL"
    )
    db.add_all([doc, metric])
    db.commit()

    # 1. DocumentReference mapping
    doc_res = fhir_service.to_fhir_document_reference(doc, vault)
    assert doc_res["resourceType"] == "DocumentReference"
    assert doc_res["status"] == "current"
    assert doc_res["content"][0]["attachment"]["contentType"] == "application/pdf"
    assert "blood_report.pdf" in doc_res["content"][0]["attachment"]["title"]

    # 2. FHIR $everything Collection Bundle
    bundle = fhir_service.build_patient_bundle(vault, [metric], [doc])
    assert bundle["resourceType"] == "Bundle"
    assert bundle["type"] == "collection"
    assert bundle["total"] >= 3  # Patient + Observation + DocumentReference
    types = [entry["resource"]["resourceType"] for entry in bundle["entry"]]
    assert "Patient" in types
    assert "Observation" in types
    assert "DocumentReference" in types


def test_fhir_api_endpoints(client, db):
    # Register & Login
    client.post("/api/v1/auth/signup", json={"username": "fhir_api_user", "password": "Password123!"})
    login_res = client.post("/api/v1/auth/login", json={"username": "fhir_api_user", "password": "Password123!"})
    token = login_res.json().get("access_token") or login_res.json().get("token")
    headers = {"Authorization": f"Bearer {token}"}

    # Fetch user vault
    vaults_res = client.get("/api/v1/vaults", headers=headers)
    vault_id = vaults_res.json()[0]["id"]

    # 1. GET /api/v1/fhir/Patient/{vault_id}
    res_patient = client.get(f"/api/v1/fhir/Patient/{vault_id}", headers=headers)
    assert res_patient.status_code == 200
    assert res_patient.json()["resourceType"] == "Patient"

    # 2. GET /api/v1/fhir/Patient/{vault_id}/$everything
    res_bundle = client.get(f"/api/v1/fhir/Patient/{vault_id}/$everything", headers=headers)
    assert res_bundle.status_code == 200
    assert res_bundle.json()["resourceType"] == "Bundle"
    assert res_bundle.json()["type"] == "collection"

    # 3. GET /api/v1/vaults/{vault_id}/fhir
    res_export = client.get(f"/api/v1/vaults/{vault_id}/fhir", headers=headers)
    assert res_export.status_code == 200
    assert res_export.json()["resourceType"] == "Bundle"

def test_fhir_diagnostic_report_and_encounter(db):
    from app.models.patient import QRScanLog
    
    user = User(username="full_fhir_user", password_hash="hash")
    db.add(user)
    db.commit()

    vault = VaultProfile(
        owner_user_id=user.id,
        relation="Self",
        full_name="Kavita Krishnan",
        medications="Metformin 500mg, Atorvastatin 20mg"
    )
    db.add(vault)
    db.commit()

    doc = Document(
        vault_id=vault.id,
        file_name="liver_function_test.pdf",
        file_path="uploads/lft.pdf",
        category="Lab Report"
    )
    db.add(doc)
    db.commit()

    metric = HealthMetric(
        vault_id=vault.id,
        metric_name="urea",
        metric_value=28.5,
        metric_unit="mg/dL",
        source_document_id=doc.id
    )
    scan_log = QRScanLog(
        vault_id=vault.id,
        ip_address="103.21.244.2",
        user_agent="Emergency Clinic App/1.0",
        location_data="Kolkata, India"
    )
    db.add_all([metric, scan_log])
    db.commit()

    # 1. DiagnosticReport Resource
    diag_res = fhir_service.to_fhir_diagnostic_report(doc, [metric], vault)
    assert diag_res["resourceType"] == "DiagnosticReport"
    assert diag_res["status"] == "final"
    assert len(diag_res["result"]) == 1
    assert diag_res["result"][0]["reference"] == f"Observation/obs-{metric.id}"

    # 2. MedicationRequest Resource
    med_res_list = fhir_service.to_fhir_medication_requests(vault)
    assert len(med_res_list) == 2
    assert med_res_list[0]["resourceType"] == "MedicationRequest"
    assert med_res_list[0]["status"] == "active"
    assert "Metformin" in med_res_list[0]["medicationCodeableConcept"]["text"]

    # 3. Encounter Resource
    enc_list = fhir_service.to_fhir_encounters([scan_log], vault)
    assert len(enc_list) == 1
    assert enc_list[0]["resourceType"] == "Encounter"
    assert enc_list[0]["class"]["code"] == "AMB"
    assert "Kolkata" in enc_list[0]["location"][0]["location"]["display"]

    # 4. Comprehensive Bundle containing all 7 resource types
    bundle = fhir_service.build_patient_bundle(vault, [metric], [doc], [scan_log])
    assert bundle["resourceType"] == "Bundle"
    types = [entry["resource"]["resourceType"] for entry in bundle["entry"]]
    assert "Patient" in types
    assert "Observation" in types
    assert "DiagnosticReport" in types
    assert "DocumentReference" in types
    assert "MedicationRequest" in types
    assert "Encounter" in types

