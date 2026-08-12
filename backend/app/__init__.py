import os
from contextlib import asynccontextmanager
from typing import Optional, Mapping, Any
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse, FileResponse, Response, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.cors import CORSMiddleware

from config import settings
from app.database import engine, Base

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

# Configure Jinja2 Templates
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# Add custom Jinja2 helpers to mirror Flask template behaviors seamlessly
def jinja_url_for(request: Optional[Request], name: str, **kwargs) -> str:
    """Supports both Flask url_for('static', filename='...') and FastAPI url_for('static', path='...')."""
    if name == "static":
        filename = kwargs.get("filename") or kwargs.get("path") or ""
        return f"/static/{filename.lstrip('/')}"
    try:
        if request:
            return str(request.url_for(name, **kwargs))
    except Exception:
        pass
    return f"/api/v1/{name}"

def jinja_get_flashed_messages(request: Optional[Request], with_categories: bool = False):
    """Retrieve and clear session flash messages inside Jinja templates."""
    if request and hasattr(request, "session"):
        flashes = request.session.pop("_flashes", [])
        if with_categories:
            return flashes
        return [msg for _, msg in flashes]
    return []

templates.env.globals["url_for"] = lambda name, **kwargs: jinja_url_for(None, name, **kwargs)
templates.env.globals["get_flashed_messages"] = lambda **kwargs: []
templates.env.globals["csrf_token"] = lambda: ""

# Wrapper to support render_template(request, name, context) or templates.TemplateResponse
def render_template(
    request: Request,
    template_name: str,
    context: Optional[dict] = None,
    status_code: int = 200,
    headers: Optional[Mapping[str, str]] = None
):
    ctx = dict(context) if context else {}
    ctx["request"] = request
    ctx["url_for"] = lambda endpoint, **kw: jinja_url_for(request, endpoint, **kw)
    ctx["get_flashed_messages"] = lambda **kw: jinja_get_flashed_messages(request, **kw)
    ctx["session"] = request.session if hasattr(request, "session") else {}
    ctx["csrf_token"] = lambda: ""
    
    return templates.TemplateResponse(
        request=request,
        name=template_name,
        context=ctx,
        status_code=status_code,
        headers=headers
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Ensure database tables are created
    from app.models.patient import User, VaultProfile, VaultAccess, Document, HealthMetric, QRScanLog
    Base.metadata.create_all(bind=engine)
    yield


API_DESCRIPTION = """
# 🩺 Aadhaar Health Bridge API

**Aadhaar Health Bridge** provides high-performance, secure emergency medical records management, zero-authentication emergency QR profile access, automated biomarker extraction, and an AI Clinical Document Assistant.

---

## 🔐 Authentication & Authorization
* **Bearer Token**: Send `Authorization: Bearer <JWT_TOKEN>` header for API endpoints.
* **Tokens**: Issued via `/api/v1/auth/login`.

---

## ⚡ Core Modules & Features
* **Authentication**: User registration, credential verification, and profile introspection.
* **Vaults**: Comprehensive management of patient medical lockers and family caregiver access.
* **Documents**: Secure upload of diagnostics reports with PyMuPDF digital text extraction and Chroma DB vector indexing.
* **Health Metrics**: Structured clinical biomarker parsing (Creatinine, Urea, Uric Acid, Hemoglobin, Glucose, HbA1c).
* **AI Clinical Assistant**: RAG question-answering with tiered cascading LLMs (Grok-beta, Groq Llama, Local Ollama, Offline RAG).
* **Emergency QR Scan**: Zero-login immediate retrieval for paramedics and doctors with Geo-IP audit logging.
"""

TAGS_METADATA = [
    {
        "name": "Authentication",
        "description": "User registration, JWT token generation, and account profile endpoints.",
    },
    {
        "name": "Vaults",
        "description": "Family medical locker management, member provisioning, and QR audit trails.",
    },
    {
        "name": "Documents",
        "description": "Medical record upload, OCR digital text extraction, streaming, and deletion.",
    },
    {
        "name": "Health Metrics",
        "description": "Structured biomarker time-series queries and JSON health snapshots.",
    },
    {
        "name": "AI Clinical Assistant",
        "description": "RAG-powered conversational medical assistant with biomarker trend interpretation.",
    },
    {
        "name": "Emergency QR Scan",
        "description": "Zero-authentication emergency data access endpoint for first responders.",
    },
    {
        "name": "Health",
        "description": "System liveness and database connectivity probes.",
    },
]


def create_app() -> FastAPI:
    app = FastAPI(
        title="Aadhaar Health Bridge API",
        description=API_DESCRIPTION,
        version="1.0.0",
        openapi_tags=TAGS_METADATA,
        openapi_url="/api/v1/openapi.json",
        docs_url="/docs",
        redoc_url="/redoc",
        swagger_ui_parameters={
            "defaultModelsExpandDepth": 2,
            "displayRequestDuration": True,
            "docExpansion": "list",
            "filter": True,
            "showExtensions": True
        },
        lifespan=lifespan
    )

    # Session Middleware (for cookie state and flash messages)
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.SECRET_KEY,
        session_cookie="ahb_session",
        max_age=86400 * 7,
        same_site="lax",
        https_only=settings.ENFORCE_HTTPS or (settings.ENVIRONMENT == "production")
    )

    # OWASP Top 10 & API Security Middlewares
    from app.middleware.security import OWASPSecurityHeadersMiddleware, HTTPSTransportSecurityMiddleware
    from app.middleware.rate_limiter import RateLimitMiddleware

    # CORS Middleware (placed before security headers/rate limiter to properly handle preflight and error responses)
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
        allow_origins=[
            "http://localhost:5000",
            "http://127.0.0.1:5000",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:8080",
            "http://127.0.0.1:8080",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            settings.APP_BASE_URL.rstrip("/")
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_middleware(HTTPSTransportSecurityMiddleware)
    app.add_middleware(OWASPSecurityHeadersMiddleware)
    app.add_middleware(RateLimitMiddleware)

    # Standardized Pydantic v2 Validation Exception Handler
    from fastapi.exceptions import RequestValidationError
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        formatted_errors = []
        for err in exc.errors():
            loc = " -> ".join([str(l) for l in err.get("loc", []) if l != "body"])
            formatted_errors.append({
                "field": loc or "payload",
                "message": err.get("msg", "Invalid input value"),
                "type": err.get("type", "validation_error")
            })
        return JSONResponse(
            status_code=422,
            content={
                "status": "error",
                "message": "Input validation failed. Please check your payload parameters.",
                "errors": formatted_errors
            }
        )

    # Static Files Mounting
    if os.path.exists(STATIC_DIR):
        app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    # 1. Versioned RESTful API Router (/api/v1)
    from app.api.v1 import api_v1_router
    app.include_router(api_v1_router, prefix="/api/v1")

    # 2. Web UI / Form Action Bridge Router
    from app.routes.bridge import bridge_bp
    app.include_router(bridge_bp, prefix="/api/v1")

    # 3. PWA Endpoints: Manifest, Service Worker, and App Shell Delivery
    @app.get("/manifest.json", include_in_schema=False)
    async def get_manifest():
        manifest_path = os.path.join(STATIC_DIR, "manifest.json")
        if os.path.exists(manifest_path):
            return FileResponse(manifest_path, media_type="application/manifest+json")
        return Response(status_code=404)

    @app.get("/sw.js", include_in_schema=False)
    async def get_service_worker():
        sw_path = os.path.join(STATIC_DIR, "sw.js")
        if os.path.exists(sw_path):
            return FileResponse(sw_path, media_type="application/javascript")
        return Response(status_code=404)

    @app.get("/", include_in_schema=False)
    async def root_pwa():
        index_path = os.path.join(STATIC_DIR, "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path, media_type="text/html")
        return RedirectResponse(url="/api/v1/login")

    @app.get("/favicon.ico", include_in_schema=False)
    async def favicon():
        icon_path = os.path.join(STATIC_DIR, "icon-192.png")
        if os.path.exists(icon_path):
            return FileResponse(icon_path)
        return Response(status_code=404)

    return app

# Module-level app instance for ASGI servers
app = create_app()