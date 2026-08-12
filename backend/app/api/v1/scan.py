from fastapi import APIRouter, Request, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Dict, Any

from app.database import get_db
from app.services.vault_service import VaultService
from app.services.sos_service import sos_service
from app.schemas.patient import VaultDetailOut, SOSDispatchIn

router = APIRouter(prefix="/scan", tags=["Emergency QR Scan & SOS Alerts"])


@router.get("/{token}/data", response_model=VaultDetailOut)
async def get_emergency_scan_data(
    token: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """REST API: Retrieve patient emergency medical data via zero-auth QR token."""
    ip = request.client.host if request.client else "127.0.0.1"
    if request.headers.get("X-Forwarded-For"):
        ip = request.headers.get("X-Forwarded-For").split(",")[0].strip()

    vault_service = VaultService(db)
    vault, _ = vault_service.log_qr_scan(token, ip, request.headers.get('User-Agent'))
    if not vault:
        raise HTTPException(status_code=404, detail={"status": "error", "message": "Emergency profile not found."})

    if not vault.is_emergency_ready:
        raise HTTPException(
            status_code=403,
            detail={"status": "error", "message": "Emergency access is disabled for this medical profile."}
        )

    return vault


@router.post("/{token}/sos", status_code=status.HTTP_200_OK)
async def trigger_emergency_scan_sos(
    token: str,
    payload: SOSDispatchIn,
    request: Request,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Paramedic / First Responder Emergency SOS & GPS Broadcast.
    Dispatches instant alerts with GPS location to all registered emergency contacts.
    """
    ip = request.headers.get("X-Forwarded-For", request.client.host if request.client else "unknown").split(",")[0].strip()
    user_agent = request.headers.get("User-Agent", "")

    vault_service = VaultService(db)
    vault, _ = vault_service.log_qr_scan(token, ip, user_agent)
    if not vault:
        raise HTTPException(status_code=404, detail={"status": "error", "message": "Emergency profile not found."})

    if not vault.is_emergency_ready:
        raise HTTPException(
            status_code=403,
            detail={"status": "error", "message": "Emergency access is disabled for this medical profile."}
        )

    result = sos_service.dispatch_sos(
        vault=vault,
        db=db,
        latitude=payload.latitude,
        longitude=payload.longitude,
        accuracy_meters=payload.accuracy_meters,
        trigger_source=payload.trigger_source or "qr_scan",
        ip_address=ip,
        user_agent=user_agent
    )
    return result


@router.get("/{token}/contacts")
async def get_emergency_scan_contacts(
    token: str,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Retrieves emergency contacts and instant 1-tap WhatsApp broadcast links."""
    from app.models.patient import VaultProfile
    vault = db.query(VaultProfile).filter(VaultProfile.qr_token == token).first()
    if not vault:
        raise HTTPException(status_code=404, detail={"status": "error", "message": "Emergency profile not found."})

    contacts = sos_service.get_emergency_contacts(vault)
    maps_url = sos_service.build_maps_url(None, None)
    alert_msg = sos_service.compose_emergency_message(vault, maps_url)

    return {
        "vault_id": vault.id,
        "patient_name": vault.full_name,
        "blood_group": vault.blood_group,
        "emergency_contacts": contacts,
        "default_alert_message": alert_msg
    }


@router.post("/verify-offline")
async def verify_offline_qr_payload(
    payload: Dict[str, str]
) -> Dict[str, Any]:
    """
    Verifies an ECDSA-P256 digitally signed offline emergency QR string (AHB1...).
    Returns decoded triage profile and cryptographic authenticity status.
    """
    from app.services.crypto_qr_service import crypto_qr_service
    raw_payload = payload.get("raw_payload", "").strip()
    if not raw_payload:
        raise HTTPException(status_code=400, detail={"status": "error", "message": "Missing raw_payload field."})

    is_valid, data, err = crypto_qr_service.verify_signed_qr_payload(raw_payload)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"status": "error", "message": err or "Cryptographic signature invalid or data tampered."}
        )

    return {
        "status": "success",
        "cryptographic_verification": "VALID_ECDSA_P256_SEAL",
        "triage_profile": data,
        "warning": err
    }

