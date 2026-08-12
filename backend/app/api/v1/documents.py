import os
from typing import List, Optional, Tuple
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.vault_service import VaultService
from app.services.document_service import DocumentService
from app.schemas.patient import DocumentOut, ApiResponse
from app.middleware.auth import get_current_user_hybrid
from app.middleware.rbac import RequireVaultPermission, RequireDocumentPermission, Permission
from app.models.patient import User, Document, VaultProfile
from config import settings

router = APIRouter(prefix="/vaults/{vault_id}/documents", tags=["Documents"])

@router.get("", response_model=List[DocumentOut])
async def list_vault_documents(
    vault_id: int,
    vault_and_access: Tuple[VaultProfile, str] = Depends(RequireVaultPermission(Permission.DOC_READ)),
    db: Session = Depends(get_db)
):
    """REST API: List medical documents with resource-level authorization."""
    return db.query(Document).filter(Document.vault_id == vault_id).all()

@router.post("", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def upload_document(
    vault_id: int,
    file: UploadFile = File(...),
    file_name: Optional[str] = Form(None),
    category: Optional[str] = Form("Diagnostic Lab Report"),
    ocr_text: Optional[str] = Form(None),
    is_encrypted: Optional[bool] = Form(False),
    current_user: User = Depends(get_current_user_hybrid),
    vault_and_access: Tuple[VaultProfile, str] = Depends(RequireVaultPermission(Permission.DOC_WRITE)),
    db: Session = Depends(get_db)
):
    """REST API: Upload and index a medical document with resource-level authorization."""
    file_bytes = await file.read()
    doc_service = DocumentService(db)
    document, err = doc_service.process_and_upload_document(
        vault_id=vault_id,
        user_id=current_user.id,
        filename=file.filename or "",
        file_bytes=file_bytes,
        file_name=file_name,
        category=category,
        ocr_text=ocr_text,
        is_encrypted=bool(is_encrypted)
    )
    if err:
        raise HTTPException(status_code=400, detail={"status": "error", "message": err})

    return document

@router.get("/{document_id}/serve")
async def serve_document(
    vault_id: int,
    document_id: int,
    doc_and_vault: Tuple[Document, VaultProfile] = Depends(RequireDocumentPermission(Permission.DOC_READ))
):
    """REST API: Stream medical document file with resource-level authorization and CSP protection."""
    document, _ = doc_and_vault

    upload_base = settings.UPLOAD_FOLDER
    full_path = os.path.join(upload_base, document.file_path)
    if not os.path.exists(full_path):
        static_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "static", document.file_path)
        if os.path.exists(static_path):
            full_path = static_path
        else:
            raise HTTPException(status_code=404, detail={"status": "error", "message": "File not found on disk."})

    filename = os.path.basename(document.file_path)
    ext = os.path.splitext(filename)[1].lower()
    disposition = "inline" if ext in [".pdf", ".png", ".jpg", ".jpeg", ".gif", ".txt"] else f"attachment; filename=\"{filename}\""

    headers = {
        "Content-Security-Policy": "default-src 'none'; frame-ancestors 'self';",
        "Content-Disposition": disposition
    }
    return FileResponse(full_path, headers=headers)

@router.delete("/{document_id}", response_model=ApiResponse)
async def delete_document(
    vault_id: int,
    document_id: int,
    current_user: User = Depends(get_current_user_hybrid),
    doc_and_vault: Tuple[Document, VaultProfile] = Depends(RequireDocumentPermission(Permission.DOC_DELETE)),
    db: Session = Depends(get_db)
):
    """REST API: Delete medical document with resource-level authorization."""
    doc_service = DocumentService(db)
    success, err = doc_service.delete_document(document_id, current_user.id)
    if not success:
        raise HTTPException(status_code=400, detail={"status": "error", "message": err or "Failed to delete document."})

    return {"status": "success", "message": "Medical record deleted successfully."}
