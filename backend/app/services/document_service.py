import os
import uuid
import logging
from typing import Optional, Tuple, List, Dict, Any
import fitz
from sqlalchemy.orm import Session
from werkzeug.utils import secure_filename

from app.models.patient import Document, VaultProfile, VaultAccess, HealthMetric
from app.services.storage_service import upload_document_to_storage, delete_document_from_storage
from app.services import semantic_service
from app.services.metric_service import HealthMetricService

logger = logging.getLogger(__name__)

WHITELISTED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".gif", ".txt", ".enc"}
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB

class DocumentService:
    """Modular service handling medical document ingestion, OCR extraction, and storage coordination."""

    def __init__(self, db: Session):
        self.db = db
        self.metric_service = HealthMetricService(db)

    def validate_file(self, filename: str, file_size: int) -> Tuple[bool, Optional[str]]:
        """Validates file extension and size limits."""
        if not filename:
            return False, "No file selected."

        clean_name = secure_filename(filename)
        ext = os.path.splitext(clean_name)[1].lower()
        if ext not in WHITELISTED_EXTENSIONS:
            return False, "Upload failed: File extension not allowed. Only PDFs, text files, and images are permitted."

        if file_size > MAX_FILE_SIZE_BYTES:
            return False, "Upload failed: File size exceeds the 10MB limit."

        return True, None

    def process_and_upload_document(
        self,
        vault_id: int,
        user_id: int,
        filename: str,
        file_bytes: bytes,
        file_name: Optional[str] = None,
        category: Optional[str] = "Diagnostic Lab Report",
        ocr_text: Optional[str] = None,
        is_encrypted: bool = False
    ) -> Tuple[Optional[Document], Optional[str]]:
        """Coordinates file upload, OCR extraction, Chroma vector indexing, and structured metric extraction."""
        is_valid, err = self.validate_file(filename, len(file_bytes))
        if not is_valid:
            return None, err

        ext = os.path.splitext(secure_filename(filename))[1].lower()
        final_filename = f"{uuid.uuid4().hex}{ext}"

        try:
            storage_url = upload_document_to_storage(
                file_bytes,
                final_filename,
                folder=f"vault_docs/vault_{vault_id}"
            )
        except Exception as e:
            logger.error(f"Storage upload error: {e}")
            return None, f"Document upload failed: {str(e)}"

        doc_display_name = file_name.strip() if file_name and file_name.strip() else category or "Diagnostic Lab Report"

        from app.services.pdf_processor import local_pdf_processor
        parsed_doc = local_pdf_processor.extract_text_and_metadata(file_bytes, filename)
        
        extracted_text = ocr_text.strip() if ocr_text and ocr_text.strip() else parsed_doc["text"]
        doc_category = category or local_pdf_processor.classify_document_category(extracted_text, filename)

        document = Document(
            vault_id=vault_id,
            file_path=storage_url,
            file_name=doc_display_name,
            category=doc_category,
            ocr_text=extracted_text,
            ai_summary="",
            uploaded_by=user_id,
            is_encrypted=is_encrypted
        )
        self.db.add(document)
        self.db.commit()

        # 1. Index in Vector Store (Chroma MVP / pgvector Production)
        try:
            semantic_service.index_document(
                vault_id=vault_id,
                document_id=document.id,
                text=document.ocr_text or "",
                file_name=document.file_name,
                db=self.db
            )
        except Exception:
            logger.exception("Failed to index document into semantic vector store")

        # 2. Extract structured health metrics
        try:
            self.metric_service.extract_and_persist_metrics_from_text(
                vault_id=vault_id,
                document_id=document.id,
                text=document.ocr_text or ""
            )
        except Exception:
            logger.exception("Failed to extract structured health metrics from document")

        # 3. Record Data Provenance with SHA-256 Integrity Checksum
        try:
            from app.services.provenance_service import ProvenanceService
            prov_service = ProvenanceService(self.db)
            prov_service.record_provenance(
                vault_id=vault_id,
                target_type="DocumentReference",
                target_id=str(document.id),
                activity="CREATE",
                agent_type="author",
                agent_name=f"User-{user_id}",
                file_bytes=file_bytes,
                integrity_hash=parsed_doc["sha256"]
            )
        except Exception:
            logger.exception("Failed to record document provenance")

        # 4. Record Audit Log
        try:
            from app.services.audit_service import AuditService
            audit_service = AuditService(self.db)
            audit_service.log_event(
                action="CREATE",
                event_type="document-upload",
                vault_id=vault_id,
                user_id=user_id,
                resource_type="Document",
                resource_id=str(document.id),
                outcome="SUCCESS",
                details=f"Uploaded {document.file_name} (SHA-256: {parsed_doc['sha256'][:16]}...)"
            )
        except Exception:
            logger.exception("Failed to record document upload audit event")

        return document, None

    def delete_document(self, document_id: int, user_id: int) -> Tuple[bool, Optional[str]]:
        """Deletes a document from cloud/local storage and database with access checks."""
        document = self.db.query(Document).filter(Document.id == document_id).first()
        if not document:
            return False, "Document not found."

        access = self.db.query(VaultAccess).filter(
            VaultAccess.user_id == user_id,
            VaultAccess.vault_id == document.vault_id
        ).first()
        if not access:
            return False, "Unauthorized access."

        delete_document_from_storage(document.file_path)
        self.db.delete(document)
        self.db.commit()

        return True, None
