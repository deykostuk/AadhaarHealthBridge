import datetime
from datetime import timezone
from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.database import get_db

health_bp = APIRouter(tags=["Health"])

@health_bp.get("/health", status_code=status.HTTP_200_OK)
async def health_check():
    return {
        "status": "ok",
        "service": "Aadhaar Health Bridge API",
        "version": "0.1.0",
        "timestamp": datetime.datetime.now(timezone.utc).isoformat()
    }

@health_bp.get("/health/db")
async def health_check_db(db: Session = Depends(get_db)):
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