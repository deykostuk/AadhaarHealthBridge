from typing import Optional, List, Dict, Any, Tuple
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.fhir_service import fhir_service
from app.middleware.rbac import RequireVaultPermission, Permission
from app.models.patient import VaultProfile, HealthMetric, Document, QRScanLog

router = APIRouter(tags=["HL7 FHIR R4 Healthcare Standard"])

@router.get("/fhir/Patient/{vault_id}")
async def get_fhir_patient(
    vault_id: int,
    vault_and_access: Tuple[VaultProfile, str] = Depends(RequireVaultPermission(Permission.VAULT_READ))
) -> Dict[str, Any]:
    """HL7 FHIR R4: Retrieve Patient resource by Vault ID."""
    vault, _ = vault_and_access
    return fhir_service.to_fhir_patient(vault)


@router.get("/fhir/Observation")
async def get_fhir_observations(
    patient: int = Query(..., description="Vault ID of the patient"),
    code: Optional[str] = Query(None, description="Filter by LOINC code or metric name"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """HL7 FHIR R4: Search observations for a patient."""
    vault = db.query(VaultProfile).filter(VaultProfile.id == patient).first()
    if not vault:
        raise HTTPException(status_code=404, detail="Patient not found.")

    query = db.query(HealthMetric).filter(HealthMetric.vault_id == patient)
    if code:
        query = query.filter(HealthMetric.metric_name == code.lower())
    metrics = query.order_by(HealthMetric.observed_date.desc()).all()

    entries = [
        {
            "fullUrl": f"urn:uuid:observation-{m.id}",
            "resource": fhir_service.to_fhir_observation(m, vault)
        }
        for m in metrics
    ]

    return {
        "resourceType": "Bundle",
        "type": "searchset",
        "total": len(entries),
        "entry": entries
    }


@router.get("/fhir/DiagnosticReport")
async def get_fhir_diagnostic_reports(
    patient: int = Query(..., description="Vault ID of the patient"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """HL7 FHIR R4: Search diagnostic laboratory and radiology reports for a patient."""
    vault = db.query(VaultProfile).filter(VaultProfile.id == patient).first()
    if not vault:
        raise HTTPException(status_code=404, detail="Patient not found.")

    docs = db.query(Document).filter(Document.vault_id == patient).all()
    metrics = db.query(HealthMetric).filter(HealthMetric.vault_id == patient).all()

    entries = [
        {
            "fullUrl": f"urn:uuid:report-{d.id}",
            "resource": fhir_service.to_fhir_diagnostic_report(d, metrics, vault)
        }
        for d in docs
    ]

    return {
        "resourceType": "Bundle",
        "type": "searchset",
        "total": len(entries),
        "entry": entries
    }


@router.get("/fhir/MedicationRequest")
async def get_fhir_medication_requests(
    patient: int = Query(..., description="Vault ID of the patient"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """HL7 FHIR R4: Search active medication prescriptions for a patient."""
    vault = db.query(VaultProfile).filter(VaultProfile.id == patient).first()
    if not vault:
        raise HTTPException(status_code=404, detail="Patient not found.")

    meds = fhir_service.to_fhir_medication_requests(vault)
    entries = [
        {
            "fullUrl": f"urn:uuid:{m['id']}",
            "resource": m
        }
        for m in meds
    ]

    return {
        "resourceType": "Bundle",
        "type": "searchset",
        "total": len(entries),
        "entry": entries
    }


@router.get("/fhir/Encounter")
async def get_fhir_encounters(
    patient: int = Query(..., description="Vault ID of the patient"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """HL7 FHIR R4: Search clinical encounters and emergency QR scans for a patient."""
    vault = db.query(VaultProfile).filter(VaultProfile.id == patient).first()
    if not vault:
        raise HTTPException(status_code=404, detail="Patient not found.")

    logs = db.query(QRScanLog).filter(QRScanLog.vault_id == patient).order_by(QRScanLog.timestamp.desc()).all()
    encounters = fhir_service.to_fhir_encounters(logs, vault)

    entries = [
        {
            "fullUrl": f"urn:uuid:{e['id']}",
            "resource": e
        }
        for e in encounters
    ]

    return {
        "resourceType": "Bundle",
        "type": "searchset",
        "total": len(entries),
        "entry": entries
    }


@router.get("/fhir/DocumentReference")
async def get_fhir_document_references(
    patient: int = Query(..., description="Vault ID of the patient"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """HL7 FHIR R4: Search document references for a patient."""
    vault = db.query(VaultProfile).filter(VaultProfile.id == patient).first()
    if not vault:
        raise HTTPException(status_code=404, detail="Patient not found.")

    docs = db.query(Document).filter(Document.vault_id == patient).all()
    entries = [
        {
            "fullUrl": f"urn:uuid:document-{d.id}",
            "resource": fhir_service.to_fhir_document_reference(d, vault)
        }
        for d in docs
    ]

    return {
        "resourceType": "Bundle",
        "type": "searchset",
        "total": len(entries),
        "entry": entries
    }


@router.get("/fhir/AllergyIntolerance")
async def get_fhir_allergies(
    patient: int = Query(..., description="Vault ID of the patient"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """HL7 FHIR R4: Search allergies for a patient."""
    vault = db.query(VaultProfile).filter(VaultProfile.id == patient).first()
    if not vault:
        raise HTTPException(status_code=404, detail="Patient not found.")

    allergies = fhir_service.to_fhir_allergies(vault)
    entries = [
        {
            "fullUrl": f"urn:uuid:{a['id']}",
            "resource": a
        }
        for a in allergies
    ]

    return {
        "resourceType": "Bundle",
        "type": "searchset",
        "total": len(entries),
        "entry": entries
    }


@router.get("/fhir/Condition")
async def get_fhir_conditions(
    patient: int = Query(..., description="Vault ID of the patient"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """HL7 FHIR R4: Search medical conditions for a patient."""
    vault = db.query(VaultProfile).filter(VaultProfile.id == patient).first()
    if not vault:
        raise HTTPException(status_code=404, detail="Patient not found.")

    conditions = fhir_service.to_fhir_conditions(vault)
    entries = [
        {
            "fullUrl": f"urn:uuid:{c['id']}",
            "resource": c
        }
        for c in conditions
    ]

    return {
        "resourceType": "Bundle",
        "type": "searchset",
        "total": len(entries),
        "entry": entries
    }


@router.get("/fhir/Consent")
async def get_fhir_consents(
    patient: int = Query(..., description="Vault ID of the patient"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """HL7 FHIR R4: Search consent policies for a patient."""
    vault = db.query(VaultProfile).filter(VaultProfile.id == patient).first()
    if not vault:
        raise HTTPException(status_code=404, detail="Patient not found.")

    from app.models.patient import ConsentRecord
    from app.services.consent_service import ConsentService
    consents = db.query(ConsentRecord).filter(ConsentRecord.vault_id == patient).all()

    entries = [
        {
            "fullUrl": f"urn:uuid:consent-{c.id}",
            "resource": ConsentService.to_fhir_consent(c, vault)
        }
        for c in consents
    ]

    return {
        "resourceType": "Bundle",
        "type": "searchset",
        "total": len(entries),
        "entry": entries
    }


@router.get("/fhir/Consent/{consent_id}")
async def get_fhir_consent_by_id(
    consent_id: int,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """HL7 FHIR R4: Retrieve a specific Consent resource by ID."""
    from app.models.patient import ConsentRecord
    from app.services.consent_service import ConsentService
    consent = db.query(ConsentRecord).filter(ConsentRecord.id == consent_id).first()
    if not consent:
        raise HTTPException(status_code=404, detail="Consent resource not found.")

    vault = db.query(VaultProfile).filter(VaultProfile.id == consent.vault_id).first()
    return ConsentService.to_fhir_consent(consent, vault)


@router.get("/fhir/Patient/{vault_id}/$everything")
async def get_fhir_patient_everything(
    vault_id: int,
    vault_and_access: Tuple[VaultProfile, str] = Depends(RequireVaultPermission(Permission.VAULT_READ)),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """HL7 FHIR R4: Patient $everything operation returning complete patient collection bundle."""
    vault, _ = vault_and_access
    from app.models.patient import ConsentRecord
    metrics = db.query(HealthMetric).filter(HealthMetric.vault_id == vault.id).all()
    docs = db.query(Document).filter(Document.vault_id == vault.id).all()
    logs = db.query(QRScanLog).filter(QRScanLog.vault_id == vault.id).all()
    consents = db.query(ConsentRecord).filter(ConsentRecord.vault_id == vault.id).all()

    return fhir_service.build_patient_bundle(vault, metrics, docs, logs, consents)


@router.get("/fhir/AuditEvent")
async def get_fhir_audit_events(
    patient: int = Query(..., description="Vault ID of the patient"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """HL7 FHIR R4: Search AuditEvents for a patient vault."""
    vault = db.query(VaultProfile).filter(VaultProfile.id == patient).first()
    if not vault:
        raise HTTPException(status_code=404, detail="Patient not found.")

    from app.services.audit_service import AuditService
    service = AuditService(db)
    return service.get_audit_events_bundle(vault.id, limit=limit)


@router.get("/fhir/AuditEvent/{event_id}")
async def get_fhir_audit_event_by_id(
    event_id: int,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """HL7 FHIR R4: Retrieve a specific AuditEvent resource by ID."""
    from app.models.patient import AuditLog
    from app.services.audit_service import AuditService
    log = db.query(AuditLog).filter(AuditLog.id == event_id).first()
    if not log:
        raise HTTPException(status_code=404, detail="AuditEvent resource not found.")

    vault = db.query(VaultProfile).filter(VaultProfile.id == log.vault_id).first() if log.vault_id else None
    return AuditService.to_fhir_audit_event(log, vault)


@router.get("/fhir/Provenance")
async def get_fhir_provenance(
    patient: int = Query(..., description="Vault ID of the patient"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """HL7 FHIR R4: Search Provenance lineage records for a patient vault."""
    vault = db.query(VaultProfile).filter(VaultProfile.id == patient).first()
    if not vault:
        raise HTTPException(status_code=404, detail="Patient not found.")

    from app.services.provenance_service import ProvenanceService
    service = ProvenanceService(db)
    return service.get_provenance_bundle(vault.id, limit=limit)


@router.get("/fhir/Provenance/{provenance_id}")
async def get_fhir_provenance_by_id(
    provenance_id: int,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """HL7 FHIR R4: Retrieve a specific Provenance resource by ID."""
    from app.models.patient import ProvenanceRecord
    from app.services.provenance_service import ProvenanceService
    record = db.query(ProvenanceRecord).filter(ProvenanceRecord.id == provenance_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Provenance resource not found.")

    vault = db.query(VaultProfile).filter(VaultProfile.id == record.vault_id).first()
    return ProvenanceService.to_fhir_provenance(record, vault)


@router.get("/vaults/{vault_id}/fhir")
async def export_vault_fhir(
    vault_id: int,
    vault_and_access: Tuple[VaultProfile, str] = Depends(RequireVaultPermission(Permission.VAULT_READ)),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Export complete patient locker in HL7 FHIR R4 Bundle format for EHR/ABDM interoperability."""
    vault, _ = vault_and_access
    from app.models.patient import ConsentRecord
    metrics = db.query(HealthMetric).filter(HealthMetric.vault_id == vault.id).all()
    docs = db.query(Document).filter(Document.vault_id == vault.id).all()
    logs = db.query(QRScanLog).filter(QRScanLog.vault_id == vault.id).all()
    consents = db.query(ConsentRecord).filter(ConsentRecord.vault_id == vault.id).all()

    return fhir_service.build_patient_bundle(vault, metrics, docs, logs, consents)



