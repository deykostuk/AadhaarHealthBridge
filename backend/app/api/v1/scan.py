from fastapi import APIRouter, Request, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.vault_service import VaultService
from app.schemas.patient import VaultDetailOut

router = APIRouter(prefix="/scan", tags=["Emergency QR Scan"])

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

    return vault
