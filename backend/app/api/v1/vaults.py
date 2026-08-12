from fastapi import APIRouter, Depends, HTTPException, status, Request
from typing import List, Tuple, Dict, Any
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.vault_service import VaultService
from app.schemas.patient import (
    VaultListItemOut,
    VaultDetailOut,
    VaultUpdateRequest,
    FamilyMemberCreateRequest,
    QRScanLogOut,
    SOSDispatchIn,
    SOSAlertLogOut
)
from app.middleware.auth import get_current_user_hybrid
from app.middleware.rbac import RequireVaultPermission, Permission
from app.models.patient import User, VaultProfile

router = APIRouter(prefix="/vaults", tags=["Vaults"])

@router.get("", response_model=List[VaultListItemOut])
async def list_vaults(
    current_user: User = Depends(get_current_user_hybrid),
    db: Session = Depends(get_db)
):
    """REST API: List all vaults accessible to the authenticated user."""
    vault_service = VaultService(db)
    return vault_service.get_user_vaults(current_user.id)

@router.post("/family", response_model=VaultDetailOut, status_code=status.HTTP_201_CREATED)
async def create_family_vault(
    payload: FamilyMemberCreateRequest,
    current_user: User = Depends(get_current_user_hybrid),
    db: Session = Depends(get_db)
):
    """REST API: Create a family member user, dedicated vault, and caregiver permissions."""
    vault_service = VaultService(db)
    vault, err = vault_service.create_family_member_vault(current_user.id, payload.model_dump())
    if err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": err}
        )
    return vault

@router.get("/{vault_id}", response_model=VaultDetailOut)
async def get_vault(
    vault_and_access: Tuple[VaultProfile, str] = Depends(RequireVaultPermission(Permission.VAULT_READ))
):
    """REST API: Retrieve a specific vault profile with resource-level authorization."""
    vault, _ = vault_and_access
    return vault

@router.put("/{vault_id}", response_model=VaultDetailOut)
async def update_vault(
    vault_id: int,
    payload: VaultUpdateRequest,
    current_user: User = Depends(get_current_user_hybrid),
    vault_and_access: Tuple[VaultProfile, str] = Depends(RequireVaultPermission(Permission.VAULT_WRITE)),
    db: Session = Depends(get_db)
):
    """REST API: Update clinical variables and emergency contacts with resource-level authorization."""
    vault_service = VaultService(db)
    success, err = vault_service.update_vault_profile(
        vault_id,
        current_user.id,
        payload.model_dump(exclude_unset=True)
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": err or "Failed to update vault profile."}
        )
    vault, _ = vault_service.get_vault_by_id_and_user(vault_id, current_user.id)
    return vault

@router.get("/{vault_id}/scan-logs", response_model=List[QRScanLogOut])
async def get_vault_scan_logs(
    vault_id: int,
    limit: int = 10,
    vault_and_access: Tuple[VaultProfile, str] = Depends(RequireVaultPermission(Permission.AUDIT_READ)),
    db: Session = Depends(get_db)
):
    """REST API: Retrieve QR emergency scan audit logs with resource-level authorization."""
    vault_service = VaultService(db)
    return vault_service.get_recent_scan_logs(vault_id, limit=limit)

@router.delete("/{vault_id}")
async def delete_vault(
    vault_id: int,
    current_user: User = Depends(get_current_user_hybrid),
    vault_and_access: Tuple[VaultProfile, str] = Depends(RequireVaultPermission(Permission.VAULT_DELETE)),
    db: Session = Depends(get_db)
):
    """REST API: Delete medical vault profile with owner permissions."""
    vault, _ = vault_and_access
    db.delete(vault)
    db.commit()
    return {"status": "success", "message": f"Vault profile {vault_id} deleted successfully."}


@router.post("/{vault_id}/sos", status_code=status.HTTP_200_OK)
async def trigger_vault_sos_broadcast(
    vault_id: int,
    payload: SOSDispatchIn,
    request: Request,
    vault_and_access: Tuple[VaultProfile, str] = Depends(RequireVaultPermission(Permission.VAULT_READ)),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Patient / Caregiver One-Tap Emergency SOS Broadcast.
    Dispatches instant notifications with current GPS coordinates to all registered contacts.
    """
    from app.services.sos_service import sos_service
    vault, _ = vault_and_access
    ip = request.headers.get("X-Forwarded-For", request.client.host if request.client else "unknown").split(",")[0].strip()
    user_agent = request.headers.get("User-Agent", "")

    return sos_service.dispatch_sos(
        vault=vault,
        db=db,
        latitude=payload.latitude,
        longitude=payload.longitude,
        accuracy_meters=payload.accuracy_meters,
        trigger_source=payload.trigger_source or "one_tap_pwa",
        ip_address=ip,
        user_agent=user_agent
    )


@router.get("/{vault_id}/sos/history", response_model=List[SOSAlertLogOut])
async def get_vault_sos_history(
    vault_id: int,
    limit: int = 20,
    vault_and_access: Tuple[VaultProfile, str] = Depends(RequireVaultPermission(Permission.AUDIT_READ)),
    db: Session = Depends(get_db)
):
    """Retrieves chronological SOS incident broadcast history for a vault."""
    from app.models.patient import SOSAlertLog
    return db.query(SOSAlertLog).filter(
        SOSAlertLog.vault_id == vault_id
    ).order_by(SOSAlertLog.created_at.desc()).limit(limit).all()

