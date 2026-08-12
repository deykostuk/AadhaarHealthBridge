from enum import Enum
from typing import List, Optional, Tuple, Set
from fastapi import Depends, HTTPException, status, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.patient import User, VaultProfile, VaultAccess, Document
from app.middleware.auth import get_current_user_hybrid


class Role(str, Enum):
    ADMIN = "admin"
    DOCTOR = "doctor"
    FAMILY_MEMBER = "family_member"
    CAREGIVER = "caregiver"
    EMERGENCY_RESPONDER = "emergency_responder"


class Permission(str, Enum):
    # Vault permissions
    VAULT_READ = "vault:read"
    VAULT_WRITE = "vault:write"
    VAULT_DELETE = "vault:delete"
    VAULT_ADMIN = "vault:admin"

    # Document permissions
    DOC_READ = "document:read"
    DOC_WRITE = "document:write"
    DOC_DELETE = "document:delete"

    # Clinical data permissions
    METRICS_READ = "metrics:read"
    METRICS_WRITE = "metrics:write"
    CHAT_QUERY = "chat:query"
    AUDIT_READ = "audit:read"


# Access type to permissions mapping for resource-level access
RESOURCE_PERMISSIONS: dict[str, Set[Permission]] = {
    "owner": {
        Permission.VAULT_READ,
        Permission.VAULT_WRITE,
        Permission.VAULT_DELETE,
        Permission.VAULT_ADMIN,
        Permission.DOC_READ,
        Permission.DOC_WRITE,
        Permission.DOC_DELETE,
        Permission.METRICS_READ,
        Permission.METRICS_WRITE,
        Permission.CHAT_QUERY,
        Permission.AUDIT_READ,
    },
    "caregiver": {
        Permission.VAULT_READ,
        Permission.VAULT_WRITE,
        Permission.DOC_READ,
        Permission.DOC_WRITE,
        Permission.DOC_DELETE,
        Permission.METRICS_READ,
        Permission.METRICS_WRITE,
        Permission.CHAT_QUERY,
        Permission.AUDIT_READ,
    },
    "viewer": {
        Permission.VAULT_READ,
        Permission.DOC_READ,
        Permission.METRICS_READ,
    },
}


def require_roles(*allowed_roles: Role):
    """Enforces system-level RBAC role checks."""
    role_values = {r.value if isinstance(r, Role) else str(r) for r in allowed_roles}

    async def role_checker(current_user: User = Depends(get_current_user_hybrid)) -> User:
        if current_user.role == Role.ADMIN.value:
            return current_user  # Super-admin bypass

        if current_user.role not in role_values:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "status": "error",
                    "message": f"Access denied: Required role in {list(role_values)}, but user has role '{current_user.role}'."
                }
            )
        return current_user

    return role_checker


class RequireVaultPermission:
    """Resource-level authorization dependency on a specific VaultProfile instance."""

    def __init__(self, permission: Permission):
        self.permission = permission

    async def __call__(
        self,
        vault_id: int,
        current_user: User = Depends(get_current_user_hybrid),
        db: Session = Depends(get_db)
    ) -> Tuple[VaultProfile, str]:
        # 1. Check if user is system admin
        if current_user.role == Role.ADMIN.value:
            vault = db.query(VaultProfile).filter(VaultProfile.id == vault_id).first()
            if not vault:
                raise HTTPException(status_code=404, detail={"status": "error", "message": "Vault not found."})
            return vault, "owner"

        # 2. Check resource-level access in VaultAccess table
        access = db.query(VaultAccess).filter(
            VaultAccess.user_id == current_user.id,
            VaultAccess.vault_id == vault_id
        ).first()

        if not access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"status": "error", "message": "Unauthorized access to this medical vault."}
            )

        # 3. Check if granted access_type allows requested permission
        allowed_perms = RESOURCE_PERMISSIONS.get(access.access_type, set())
        if self.permission not in allowed_perms:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "status": "error",
                    "message": f"Forbidden: Access type '{access.access_type}' lacks permission '{self.permission.value}' on this vault."
                }
            )

        vault = db.query(VaultProfile).filter(VaultProfile.id == vault_id).first()
        if not vault:
            raise HTTPException(status_code=404, detail={"status": "error", "message": "Vault not found."})

        return vault, access.access_type


class RequireDocumentPermission:
    """Resource-level authorization dependency on a specific Document instance."""

    def __init__(self, permission: Permission):
        self.permission = permission

    async def __call__(
        self,
        vault_id: int,
        document_id: int,
        current_user: User = Depends(get_current_user_hybrid),
        db: Session = Depends(get_db)
    ) -> Tuple[Document, VaultProfile]:
        # 1. Verify vault permission first
        vault_checker = RequireVaultPermission(self.permission)
        vault, access_type = await vault_checker(vault_id=vault_id, current_user=current_user, db=db)

        # 2. Retrieve document
        document = db.query(Document).filter(
            Document.id == document_id,
            Document.vault_id == vault_id
        ).first()

        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"status": "error", "message": "Document not found in this vault."}
            )

        # 3. If deleting, non-admin caregivers can only delete if they have owner or caregiver access
        if self.permission == Permission.DOC_DELETE and access_type not in ["owner", "caregiver"] and current_user.role != Role.ADMIN.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"status": "error", "message": "Only vault owners and caregivers can delete documents."}
            )

        return document, vault
