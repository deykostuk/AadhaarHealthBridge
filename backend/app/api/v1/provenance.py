from typing import Optional, List, Dict, Any, Tuple
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.provenance_service import ProvenanceService
from app.middleware.rbac import RequireVaultPermission, Permission
from app.models.patient import VaultProfile

router = APIRouter(prefix="/vaults/{vault_id}/provenance", tags=["Data Provenance"])

@router.get("")
async def get_vault_provenance(
    vault_id: int,
    limit: int = Query(50, ge=1, le=200),
    vault_and_access: Tuple[VaultProfile, str] = Depends(RequireVaultPermission(Permission.VAULT_READ)),
    db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:
    """Returns data lineage and provenance records for a medical vault."""
    vault, _ = vault_and_access
    service = ProvenanceService(db)
    records = service.get_vault_provenance(vault.id, limit=limit)

    return [
        {
            "id": r.id,
            "target_type": r.target_type,
            "target_id": r.target_id,
            "activity": r.activity,
            "agent_type": r.agent_type,
            "agent_name": r.agent_name,
            "source_reference": r.source_reference,
            "integrity_hash": r.integrity_hash,
            "recorded_at": r.recorded_at.isoformat() + "Z" if r.recorded_at else None,
            "fhir_provenance": ProvenanceService.to_fhir_provenance(r, vault)
        }
        for r in records
    ]
