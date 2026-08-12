import os
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Request, Depends, HTTPException, Form, UploadFile, File, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response, JSONResponse, FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.patient import User, Document
from app.services import (
    AuthService,
    VaultService,
    DocumentService,
    HealthMetricService,
    ChatService,
)
from app.middleware.auth import get_current_user_from_token, get_current_user_hybrid
from app import render_template
from config import settings

bridge_bp = APIRouter(include_in_schema=False)

# --- Flash Message Helpers ---
def flash(request: Request, message: str, category: str = "message"):
    if "_flashes" not in request.session:
        request.session["_flashes"] = []
    request.session["_flashes"].append((category, message))


# --- Service Worker ---
@bridge_bp.get("/sw.js")
async def serve_sw():
    """Serves the Service Worker with the correct MIME type."""
    sw_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "sw.js")
    if os.path.exists(sw_path):
        with open(sw_path, "r", encoding="utf-8") as f:
            content = f.read()
        return Response(content=content, media_type="application/javascript")
    return Response(content="// sw not found", media_type="application/javascript")


# --- Auth & UI Routes ---
@bridge_bp.get("/signup", response_class=HTMLResponse)
async def signup_page(request: Request):
    return render_template(request, "signup.html")


@bridge_bp.post("/signup")
async def signup(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    auth_service = AuthService(db)
    user, err = auth_service.register_user(username, password)
    if err:
        flash(request, err, "error")
        return RedirectResponse(url="/api/v1/signup", status_code=status.HTTP_303_SEE_OTHER)

    flash(request, "Account created successfully.", "success")
    return RedirectResponse(url="/api/v1/login", status_code=status.HTTP_303_SEE_OTHER)


@bridge_bp.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return render_template(request, "login.html")


@bridge_bp.post("/login")
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    auth_service = AuthService(db)
    user, token = auth_service.authenticate_user(username, password)
    if not user:
        flash(request, "Invalid credentials.", "error")
        return RedirectResponse(url="/api/v1/login", status_code=status.HTTP_303_SEE_OTHER)

    request.session["user_id"] = user.id
    request.session["username"] = user.username
    request.session["token"] = token

    return RedirectResponse(url="/api/v1/vault", status_code=status.HTTP_303_SEE_OTHER)


@bridge_bp.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/api/v1/login", status_code=status.HTTP_303_SEE_OTHER)


# --- Vault & Family Management Routes ---
@bridge_bp.get("/vault", response_class=HTMLResponse)
async def vault_dashboard(request: Request, db: Session = Depends(get_db)):
    user_id = request.session.get("user_id")
    if not user_id:
        return RedirectResponse(url="/api/v1/login", status_code=status.HTTP_303_SEE_OTHER)

    vault_service = VaultService(db)
    vaults = vault_service.get_user_vaults(user_id)

    return render_template(request, "vault.html", {
        "vaults": vaults,
        "current_user_id": user_id
    })


@bridge_bp.post("/family/add-member")
async def add_family_member(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    relation: str = Form(...),
    full_name: str = Form(...),
    blood_group: Optional[str] = Form(None),
    allergies: Optional[str] = Form(None),
    personal_contact: Optional[str] = Form(None),
    emergency_1_name: Optional[str] = Form(None),
    emergency_1_relation: Optional[str] = Form(None),
    emergency_1_phone: Optional[str] = Form(None),
    emergency_2_name: Optional[str] = Form(None),
    emergency_2_relation: Optional[str] = Form(None),
    emergency_2_phone: Optional[str] = Form(None),
    emergency_3_name: Optional[str] = Form(None),
    emergency_3_relation: Optional[str] = Form(None),
    emergency_3_phone: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    current_user_id = request.session.get("user_id")
    if not current_user_id:
        return RedirectResponse(url="/api/v1/login", status_code=status.HTTP_303_SEE_OTHER)

    vault_service = VaultService(db)
    form_data = {
        "username": username,
        "password": password,
        "relation": relation,
        "full_name": full_name,
        "blood_group": blood_group,
        "allergies": allergies,
        "personal_contact": personal_contact,
        "emergency_1_name": emergency_1_name,
        "emergency_1_relation": emergency_1_relation,
        "emergency_1_phone": emergency_1_phone,
        "emergency_2_name": emergency_2_name,
        "emergency_2_relation": emergency_2_relation,
        "emergency_2_phone": emergency_2_phone,
        "emergency_3_name": emergency_3_name,
        "emergency_3_relation": emergency_3_relation,
        "emergency_3_phone": emergency_3_phone,
    }
    vault, err = vault_service.create_family_member_vault(current_user_id, form_data)
    if err:
        flash(request, err, "error")
        return RedirectResponse(url="/api/v1/vault", status_code=status.HTTP_303_SEE_OTHER)

    flash(request, f"{vault.relation} vault created successfully.", "success")
    return RedirectResponse(url="/api/v1/vault", status_code=status.HTTP_303_SEE_OTHER)


@bridge_bp.get("/vault/{vault_id}", response_class=HTMLResponse)
async def view_single_vault(
    vault_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    user_id = request.session.get("user_id")
    if not user_id:
        return RedirectResponse(url="/api/v1/login", status_code=status.HTTP_303_SEE_OTHER)

    vault_service = VaultService(db)
    metric_service = HealthMetricService(db)

    vault, access_type = vault_service.get_vault_by_id_and_user(vault_id, user_id)
    if not vault:
        flash(request, "Unauthorized access.", "error")
        return RedirectResponse(url="/api/v1/vault", status_code=status.HTTP_303_SEE_OTHER)

    documents = db.query(Document).filter(Document.vault_id == vault.id).all()

    config_base = settings.APP_BASE_URL.rstrip('/')
    if config_base and not any(x in config_base for x in ["localhost", "127.0.0.1", "10.0.2.2"]):
        scan_base = config_base
    else:
        host_url = str(request.base_url).rstrip('/')
        scan_base = host_url

    scan_url = f"{scan_base}/api/v1/scan/{vault.qr_token}"
    formatted_logs = vault_service.get_recent_scan_logs(vault.id, limit=10)
    raw_metrics = metric_service.get_vault_metrics(vault.id)

    metrics = [
        {
            "metric_name": m["metric_name"],
            "metric_value": float(m["metric_value"]) if m["metric_value"] and str(m["metric_value"]).replace('.', '', 1).isdigit() else 0.0,
            "metric_unit": m["metric_unit"],
            "observed_date": m["observed_date"][:10] if m["observed_date"] else ""
        }
        for m in raw_metrics
    ]

    return render_template(request, "vault_detail.html", {
        "vault": vault,
        "documents": documents,
        "access_type": access_type,
        "scan_url": scan_url,
        "scan_logs": formatted_logs,
        "parse_user_agent": vault_service.parse_user_agent,
        "metrics": metrics
    })


@bridge_bp.post("/vault/update/{vault_id}")
async def update_vault(
    vault_id: int,
    request: Request,
    full_name: str = Form(...),
    blood_group: Optional[str] = Form(None),
    allergies: Optional[str] = Form(None),
    medical_conditions: Optional[str] = Form(None),
    medications: Optional[str] = Form(None),
    personal_contact: Optional[str] = Form(None),
    emergency_1_name: Optional[str] = Form(None),
    emergency_1_relation: Optional[str] = Form(None),
    emergency_1_phone: Optional[str] = Form(None),
    emergency_2_name: Optional[str] = Form(None),
    emergency_2_relation: Optional[str] = Form(None),
    emergency_2_phone: Optional[str] = Form(None),
    emergency_3_name: Optional[str] = Form(None),
    emergency_3_relation: Optional[str] = Form(None),
    emergency_3_phone: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    user_id = request.session.get("user_id")
    if not user_id:
        return RedirectResponse(url="/api/v1/login", status_code=status.HTTP_303_SEE_OTHER)

    vault_service = VaultService(db)
    form_data = {
        "full_name": full_name,
        "blood_group": blood_group,
        "allergies": allergies,
        "medical_conditions": medical_conditions,
        "medications": medications,
        "personal_contact": personal_contact,
        "emergency_1_name": emergency_1_name,
        "emergency_1_relation": emergency_1_relation,
        "emergency_1_phone": emergency_1_phone,
        "emergency_2_name": emergency_2_name,
        "emergency_2_relation": emergency_2_relation,
        "emergency_2_phone": emergency_2_phone,
        "emergency_3_name": emergency_3_name,
        "emergency_3_relation": emergency_3_relation,
        "emergency_3_phone": emergency_3_phone,
    }
    success, err = vault_service.update_vault_profile(vault_id, user_id, form_data)
    if not success:
        flash(request, err or "Failed to update vault.", "error")
        return RedirectResponse(url="/api/v1/vault", status_code=status.HTTP_303_SEE_OTHER)

    flash(request, "Vault updated successfully.", "success")
    return RedirectResponse(url=f"/api/v1/vault/{vault_id}", status_code=status.HTTP_303_SEE_OTHER)


# --- Document Ingestion & File Serving ---
@bridge_bp.get("/vault/{vault_id}/document/{document_id}/serve")
async def serve_document(
    vault_id: int,
    document_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    current_user_id = request.session.get("user_id")
    if not current_user_id:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            import jwt
            token = auth_header.split(" ")[1]
            try:
                data = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
                current_user_id = data.get("user_id")
            except Exception:
                pass

    if not current_user_id:
        return JSONResponse(status_code=401, content={"error": "unauthorized"})

    vault_service = VaultService(db)
    vault, _ = vault_service.get_vault_by_id_and_user(vault_id, current_user_id)
    if not vault:
        return JSONResponse(status_code=403, content={"error": "unauthorized"})

    document = db.query(Document).filter(Document.id == document_id, Document.vault_id == vault_id).first()
    if not document:
        return JSONResponse(status_code=404, content={"error": "document not found"})

    upload_base = settings.UPLOAD_FOLDER
    full_path = os.path.join(upload_base, document.file_path)
    if not os.path.exists(full_path):
        static_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", document.file_path)
        if os.path.exists(static_path):
            full_path = static_path
        else:
            return JSONResponse(status_code=404, content={"error": "file not found"})

    filename = os.path.basename(document.file_path)
    ext = os.path.splitext(filename)[1].lower()
    disposition = "inline" if ext in [".pdf", ".png", ".jpg", ".jpeg", ".gif", ".txt"] else f"attachment; filename=\"{filename}\""

    headers = {
        "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none';",
        "Content-Disposition": disposition
    }
    return FileResponse(full_path, headers=headers)


@bridge_bp.post("/vault/upload/{vault_id}")
async def upload_document(
    vault_id: int,
    request: Request,
    file: UploadFile = File(...),
    file_name: Optional[str] = Form(""),
    category: Optional[str] = Form("Diagnostic Lab Report"),
    ocr_text: Optional[str] = Form(""),
    is_encrypted: Optional[str] = Form("false"),
    db: Session = Depends(get_db)
):
    user_id = request.session.get("user_id")
    if not user_id:
        return RedirectResponse(url="/api/v1/login", status_code=status.HTTP_303_SEE_OTHER)

    vault_service = VaultService(db)
    vault, _ = vault_service.get_vault_by_id_and_user(vault_id, user_id)
    if not vault:
        return RedirectResponse(url="/api/v1/vault", status_code=status.HTTP_303_SEE_OTHER)

    file_bytes = await file.read()
    doc_service = DocumentService(db)
    doc, err = doc_service.process_and_upload_document(
        vault_id=vault_id,
        user_id=user_id,
        filename=file.filename or "",
        file_bytes=file_bytes,
        file_name=file_name,
        category=category,
        ocr_text=ocr_text,
        is_encrypted=(is_encrypted == "true")
    )
    if err:
        flash(request, err, "error")
        return RedirectResponse(url=f"/api/v1/vault/{vault_id}", status_code=status.HTTP_303_SEE_OTHER)

    flash(request, "Document uploaded successfully!", "success")
    return RedirectResponse(url=f"/api/v1/vault/{vault_id}", status_code=status.HTTP_303_SEE_OTHER)


@bridge_bp.post("/vault/document/delete/{document_id}")
async def delete_document(
    document_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    user_id = request.session.get("user_id")
    if not user_id:
        return RedirectResponse(url="/api/v1/login", status_code=status.HTTP_303_SEE_OTHER)

    doc_service = DocumentService(db)
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    vault_id = document.vault_id
    success, err = doc_service.delete_document(document_id, user_id)
    if not success:
        flash(request, err or "Failed to delete document.", "error")
        return RedirectResponse(url="/api/v1/vault", status_code=status.HTTP_303_SEE_OTHER)

    flash(request, "Medical record deleted successfully.", "success")
    return RedirectResponse(url=f"/api/v1/vault/{vault_id}", status_code=status.HTTP_303_SEE_OTHER)


# --- Emergency Public Scan ---
@bridge_bp.get("/scan/{token}", response_class=HTMLResponse)
async def emergency_scan(
    token: str,
    request: Request,
    db: Session = Depends(get_db)
):
    ip = request.client.host if request.client else "127.0.0.1"
    if request.headers.get("X-Forwarded-For"):
        ip = request.headers.get("X-Forwarded-For").split(",")[0].strip()

    vault_service = VaultService(db)
    vault, location = vault_service.log_qr_scan(token, ip, request.headers.get('User-Agent'))
    if not vault:
        raise HTTPException(status_code=404, detail="Medical profile not found")

    return render_template(request, "patient_view.html", {
        "vault": vault,
        "location": location
    })


# --- AI Chat UI ---
@bridge_bp.get("/vault/{vault_id}/chat", response_class=HTMLResponse)
async def vault_chat_page(
    vault_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    user_id = request.session.get("user_id")
    if not user_id:
        return RedirectResponse(url="/api/v1/login", status_code=status.HTTP_303_SEE_OTHER)

    vault_service = VaultService(db)
    vault, _ = vault_service.get_vault_by_id_and_user(vault_id, user_id)
    if not vault:
        flash(request, "Unauthorized access.", "error")
        return RedirectResponse(url="/api/v1/vault", status_code=status.HTTP_303_SEE_OTHER)

    documents = db.query(Document).filter(Document.vault_id == vault_id).all()
    docs_data = [
        {
            "id": d.id,
            "file_name": d.file_name or "document",
            "category": d.category or "",
            "is_encrypted": d.is_encrypted,
            "ocr_text": d.ocr_text or ""
        }
        for d in documents
    ]
    return render_template(request, "vault_chat.html", {
        "vault": vault,
        "documents": docs_data
    })
