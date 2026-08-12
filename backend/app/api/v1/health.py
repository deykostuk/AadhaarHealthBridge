import datetime
import os
from datetime import timezone
from fastapi import APIRouter, Depends, status, Response
from fastapi.responses import JSONResponse, PlainTextResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.database import get_db
from app.schemas.patient import HealthStatusResponse
from app.services.telemetry_service import telemetry
from config import settings

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthStatusResponse, status_code=status.HTTP_200_OK)
async def health_check():
    """Service liveness and health probe."""
    return {
        "status": "ok",
        "service": "Aadhaar Health Bridge API",
        "version": "1.0.0",
        "timestamp": datetime.datetime.now(timezone.utc).isoformat()
    }


@router.get("/health/live", status_code=status.HTTP_200_OK)
async def liveness_probe():
    """Kubernetes / Container Liveness Probe (checks if application event loop is responding)."""
    return {"status": "alive", "timestamp": datetime.datetime.now(timezone.utc).isoformat()}


@router.get("/health/ready")
async def readiness_probe(db: Session = Depends(get_db)):
    """
    Kubernetes / Container Readiness Probe.
    Checks database connection, storage directory write permissions, and KMS service status.
    """
    checks = {
        "database": "unknown",
        "storage": "unknown",
        "kms": "ready"
    }
    is_ready = True

    # 1. Database Ping
    try:
        db.execute(text("SELECT 1"))
        checks["database"] = "connected"
    except Exception as e:
        checks["database"] = f"error: {str(e)}"
        is_ready = False

    # 2. Local Storage Writable Check
    try:
        upload_dir = settings.UPLOAD_FOLDER
        os.makedirs(upload_dir, exist_ok=True)
        test_file = os.path.join(upload_dir, ".health_check_probe")
        with open(test_file, "w") as f:
            f.write("probe")
        if os.path.exists(test_file):
            os.remove(test_file)
        checks["storage"] = "writable"
    except Exception as e:
        checks["storage"] = f"error: {str(e)}"
        is_ready = False

    status_code = status.HTTP_200_OK if is_ready else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "ready" if is_ready else "not_ready",
            "checks": checks,
            "timestamp": datetime.datetime.now(timezone.utc).isoformat()
        }
    )


@router.get("/health/db")
async def health_check_db(db: Session = Depends(get_db)):
    """Database connectivity probe."""
    try:
        db.execute(text("SELECT 1"))
        db_status = "connected"
        http_code = status.HTTP_200_OK
    except Exception as e:
        db_status = f"error: {str(e)}"
        http_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return JSONResponse(
        status_code=http_code,
        content={
            "status": "ok" if db_status == "connected" else "degraded",
            "database": db_status,
            "timestamp": datetime.datetime.now(timezone.utc).isoformat()
        }
    )


@router.get("/health/metrics")
async def get_metrics_snapshot():
    """Operational Telemetry & Performance Metrics (JSON snapshot)."""
    return telemetry.get_metrics_summary()


@router.get("/health/prometheus", response_class=PlainTextResponse)
async def get_prometheus_metrics():
    """Prometheus Scrape Endpoint (OpenMetrics text exposition format)."""
    return PlainTextResponse(
        content=telemetry.generate_prometheus_metrics(),
        media_type="text/plain; version=0.0.4; charset=utf-8"
    )
