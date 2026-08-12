from fastapi import APIRouter
from app.api.v1.auth import router as auth_router
from app.api.v1.vaults import router as vaults_router
from app.api.v1.documents import router as documents_router
from app.api.v1.metrics import router as metrics_router
from app.api.v1.chat import router as chat_router
from app.api.v1.scan import router as scan_router
from app.api.v1.health import router as health_router
from app.api.v1.fhir import router as fhir_router
from app.api.v1.consent import router as consent_router
from app.api.v1.audit import router as audit_router
from app.api.v1.provenance import router as provenance_router
from app.api.v1.locales import router as locales_router
from app.api.v1.compliance import router as compliance_router

api_v1_router = APIRouter()

api_v1_router.include_router(auth_router)
api_v1_router.include_router(vaults_router)
api_v1_router.include_router(documents_router)
api_v1_router.include_router(metrics_router)
api_v1_router.include_router(chat_router)
api_v1_router.include_router(scan_router)
api_v1_router.include_router(health_router)
api_v1_router.include_router(fhir_router)
api_v1_router.include_router(consent_router)
api_v1_router.include_router(audit_router)
api_v1_router.include_router(provenance_router)
api_v1_router.include_router(locales_router)
api_v1_router.include_router(compliance_router)

