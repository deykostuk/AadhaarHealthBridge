from typing import Optional, List, Dict, Any, Tuple
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.audit_service import AuditService
from app.middleware.rbac import RequireVaultPermission, Permission
from app.models.patient import VaultProfile, User

router = APIRouter(prefix="/vaults/{vault_id}/audit-trail", tags=["Audit Trail"])

@router.get("")
async def get_vault_audit_trail(
    vault_id: int,
    limit: int = Query(50, ge=1, le=200),
    vault_and_access: Tuple[VaultProfile, str] = Depends(RequireVaultPermission(Permission.VAULT_READ)),
    db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:
    """Returns application audit log history for a medical vault."""
    vault, _ = vault_and_access
    service = AuditService(db)
    logs = service.get_vault_audit_logs(vault.id, limit=limit)

    return [
        {
            "id": log.id,
            "action": log.action,
            "event_type": log.event_type,
            "resource_type": log.resource_type,
            "resource_id": log.resource_id,
            "outcome": log.outcome,
            "ip_address": log.ip_address,
            "details": log.details,
            "timestamp": log.timestamp.isoformat() + "Z" if log.timestamp else None,
            "fhir_audit_event": AuditService.to_fhir_audit_event(log, vault)
        }
        for log in logs
    ]
