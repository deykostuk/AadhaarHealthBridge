from typing import List, Optional, Dict, Any, Tuple
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.vault_service import VaultService
from app.services.metric_service import HealthMetricService
from app.schemas.patient import HealthMetricOut, HealthSnapshotResponse
from app.middleware.rbac import RequireVaultPermission, Permission
from app.models.patient import VaultProfile

router = APIRouter(prefix="/vaults/{vault_id}", tags=["Health Metrics"])

@router.get("/metrics")
async def get_metrics(
    vault_id: int,
    metric: Optional[str] = None,
    vault_and_access: Tuple[VaultProfile, str] = Depends(RequireVaultPermission(Permission.METRICS_READ)),
    db: Session = Depends(get_db)
):
    """REST API: Get time-series health metrics with resource-level authorization."""
    metric_service = HealthMetricService(db)
    metrics = metric_service.get_vault_metrics(vault_id, metric)

    return {
        "vault_id": vault_id,
        "metric_name": metric,
        "metrics": metrics
    }

@router.get("/snapshot", response_model=HealthSnapshotResponse)
async def get_snapshot(
    vault_id: int,
    vault_and_access: Tuple[VaultProfile, str] = Depends(RequireVaultPermission(Permission.METRICS_READ)),
    db: Session = Depends(get_db)
):
    """REST API: Get latest vitals and JSON health snapshot with resource-level authorization."""
    metric_service = HealthMetricService(db)
    return metric_service.get_vault_snapshot_data(vault_id)
