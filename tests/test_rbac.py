import jwt
import datetime
import pytest
from fastapi import HTTPException
from werkzeug.security import generate_password_hash
from app.models.patient import User, VaultProfile, VaultAccess, Document
from app.middleware.rbac import (
    Role,
    Permission,
    require_roles,
    RequireVaultPermission,
    RequireDocumentPermission
)
from config import settings

def test_system_role_authorization(db):
    admin_user = User(username="admin_user", password_hash="hash", role=Role.ADMIN.value)
    family_user = User(username="family_user", password_hash="hash", role=Role.FAMILY_MEMBER.value)
    db.add_all([admin_user, family_user])
    db.commit()

    # Admin passes doctor/admin requirement
    checker = require_roles(Role.DOCTOR, Role.ADMIN)
    import asyncio
    res_admin = asyncio.run(checker(current_user=admin_user))
    assert res_admin.username == "admin_user"

    # Family member denied on doctor requirement
    doc_checker = require_roles(Role.DOCTOR)
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(doc_checker(current_user=family_user))
    assert exc_info.value.status_code == 403
    assert "Access denied" in exc_info.value.detail["message"]


def test_resource_level_vault_permissions(db):
    user_a = User(username="user_a", password_hash="hash", role=Role.FAMILY_MEMBER.value)
    user_b = User(username="user_b", password_hash="hash", role=Role.FAMILY_MEMBER.value)
    db.add_all([user_a, user_b])
    db.commit()

    vault_a = VaultProfile(owner_user_id=user_a.id, relation="Self", full_name="User A Vault")
    db.add(vault_a)
    db.commit()

    db.add(VaultAccess(user_id=user_a.id, vault_id=vault_a.id, access_type="owner"))
    db.commit()

    import asyncio
    read_checker = RequireVaultPermission(Permission.VAULT_READ)
    write_checker = RequireVaultPermission(Permission.VAULT_WRITE)

    # 1. Owner has read and write permission
    v_res, access = asyncio.run(read_checker(vault_id=vault_a.id, current_user=user_a, db=db))
    assert v_res.id == vault_a.id
    assert access == "owner"

    v_res, _ = asyncio.run(write_checker(vault_id=vault_a.id, current_user=user_a, db=db))
    assert v_res.id == vault_a.id

    # 2. User B has no access to Vault A (403 Forbidden)
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(read_checker(vault_id=vault_a.id, current_user=user_b, db=db))
    assert exc_info.value.status_code == 403

    # 3. Grant User B viewer access
    db.add(VaultAccess(user_id=user_b.id, vault_id=vault_a.id, access_type="viewer"))
    db.commit()

    # User B can now read
    v_res, access = asyncio.run(read_checker(vault_id=vault_a.id, current_user=user_b, db=db))
    assert access == "viewer"

    # User B cannot write (viewer lacks VAULT_WRITE permission)
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(write_checker(vault_id=vault_a.id, current_user=user_b, db=db))
    assert exc_info.value.status_code == 403


def test_resource_level_document_permissions(db):
    user_owner = User(username="doc_owner", password_hash="hash", role=Role.FAMILY_MEMBER.value)
    user_caregiver = User(username="doc_caregiver", password_hash="hash", role=Role.CAREGIVER.value)
    user_stranger = User(username="doc_stranger", password_hash="hash", role=Role.FAMILY_MEMBER.value)
    db.add_all([user_owner, user_caregiver, user_stranger])
    db.commit()

    vault = VaultProfile(owner_user_id=user_owner.id, relation="Self", full_name="Doc Vault")
    db.add(vault)
    db.commit()

    db.add(VaultAccess(user_id=user_owner.id, vault_id=vault.id, access_type="owner"))
    db.add(VaultAccess(user_id=user_caregiver.id, vault_id=vault.id, access_type="caregiver"))
    db.commit()

    doc = Document(vault_id=vault.id, file_path="sample.pdf", file_name="Sample PDF", uploaded_by=user_owner.id)
    db.add(doc)
    db.commit()

    import asyncio
    doc_read_checker = RequireDocumentPermission(Permission.DOC_READ)
    doc_delete_checker = RequireDocumentPermission(Permission.DOC_DELETE)

    # Owner can read and delete
    d_res, _ = asyncio.run(doc_read_checker(vault_id=vault.id, document_id=doc.id, current_user=user_owner, db=db))
    assert d_res.id == doc.id

    d_res, _ = asyncio.run(doc_delete_checker(vault_id=vault.id, document_id=doc.id, current_user=user_owner, db=db))
    assert d_res.id == doc.id

    # Caregiver can read and delete
    d_res, _ = asyncio.run(doc_read_checker(vault_id=vault.id, document_id=doc.id, current_user=user_caregiver, db=db))
    assert d_res.id == doc.id

    # Stranger denied
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(doc_read_checker(vault_id=vault.id, document_id=doc.id, current_user=user_stranger, db=db))
    assert exc_info.value.status_code == 403
