from typing import Optional, List, Dict, Any, Tuple
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.services.consent_service import ConsentService
from app.middleware.rbac import RequireVaultPermission, Permission
from app.models.patient import VaultProfile, User
from app.middleware.auth import get_current_user

router = APIRouter(prefix="/vaults/{vault_id}/consents", tags=["Consent Management"])

from app.schemas.patient import StrictInputModel
from app.utils.sanitizer import InputSanitizer
from pydantic import field_validator

class CreateConsentRequest(StrictInputModel):
    grantee_identifier: str
    consent_type: str = "patient-privacy"
    purpose: str = "TREAT"
    duration_minutes: Optional[int] = None
    allowed_resources: str = "all"

    @field_validator("grantee_identifier", "consent_type", "purpose", "allowed_resources", mode="before")
    @classmethod
    def sanitize_consent_inputs(cls, v):
        return InputSanitizer.sanitize_text(v, max_length=150)

@router.post("")
async def create_vault_consent(
    vault_id: int,
    request: CreateConsentRequest,
    vault_and_access: Tuple[VaultProfile, str] = Depends(RequireVaultPermission(Permission.VAULT_WRITE)),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Issues a new active FHIR consent policy for the vault."""
    vault, _ = vault_and_access
    service = ConsentService(db)
    
    consent = service.create_consent(
        vault_id=vault.id,
        granter_user_id=current_user.id,
        grantee_identifier=request.grantee_identifier,
        consent_type=request.consent_type,
        purpose=request.purpose,
        duration_minutes=request.duration_minutes,
        allowed_resources=request.allowed_resources
    )

    return {
        "message": "Consent policy successfully issued.",
        "consent": ConsentService.to_fhir_consent(consent, vault)
    }

@router.get("")
async def list_vault_consents(
    vault_id: int,
    vault_and_access: Tuple[VaultProfile, str] = Depends(RequireVaultPermission(Permission.VAULT_READ)),
    db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:
    """Returns all FHIR consent policies for the vault."""
    vault, _ = vault_and_access
    service = ConsentService(db)
    consents = service.get_vault_consents(vault.id)
    return [ConsentService.to_fhir_consent(c, vault) for c in consents]

@router.delete("/{consent_id}")
async def revoke_vault_consent(
    vault_id: int,
    consent_id: int,
    vault_and_access: Tuple[VaultProfile, str] = Depends(RequireVaultPermission(Permission.VAULT_WRITE)),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Revokes an active consent policy."""
    vault, _ = vault_and_access
    service = ConsentService(db)
    success, error = service.revoke_consent(consent_id, current_user.id)
    if not success:
        raise HTTPException(status_code=400, detail=error or "Failed to revoke consent.")
    return {"message": f"Consent policy {consent_id} has been revoked."}
