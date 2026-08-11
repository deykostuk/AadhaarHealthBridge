from typing import Tuple
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.chat_service import ChatService
from app.schemas.patient import ChatQueryRequest, ChatQueryResponse
from app.middleware.rbac import RequireVaultPermission, Permission
from app.models.patient import VaultProfile

router = APIRouter(prefix="/vaults/{vault_id}/chat", tags=["AI Clinical Assistant"])

@router.post("", response_model=ChatQueryResponse)
async def query_clinical_assistant(
    vault_id: int,
    payload: ChatQueryRequest,
    vault_and_access: Tuple[VaultProfile, str] = Depends(RequireVaultPermission(Permission.CHAT_QUERY)),
    db: Session = Depends(get_db)
):
    """REST API: Ask questions about medical records with resource-level authorization."""
    chat_service = ChatService(db)
    return chat_service.process_chat_query(
        vault_id=vault_id,
        query=payload.query,
        document_id=payload.document_id,
        custom_context=payload.context,
        client_sources=payload.sources
    )
