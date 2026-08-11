import os
import jwt
import datetime
import pytest
from io import BytesIO
from unittest.mock import patch, MagicMock
from app.models.patient import User, VaultProfile, VaultAccess, Document, HealthMetric, QRScanLog
from werkzeug.security import generate_password_hash
from config import settings

# --- Health Probes ---
def test_health_routes(client):
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"

    res = client.get("/api/v1/health/db")
    assert res.status_code == 200
    assert res.json()["database"] == "connected"


# --- RESTful API v1: Auth & OAuth2 / OIDC Endpoints ---
def test_rest_auth_endpoints(client, db):
    # 1. Signup via REST JSON
    signup_payload = {"username": "rest_user", "password": "securepassword"}
    res = client.post("/api/v1/auth/signup", json=signup_payload)
    assert res.status_code == 201
    data = res.json()
    assert data["username"] == "rest_user"
    assert "id" in data

    # 2. Login via REST JSON (OAuth Token Bundle)
    login_payload = {"username": "rest_user", "password": "securepassword"}
    res = client.post("/api/v1/auth/login", json=login_payload)
    assert res.status_code == 200
    login_data = res.json()
    assert "access_token" in login_data
    assert "id_token" in login_data
    assert "refresh_token" in login_data
    token = login_data["access_token"]
    refresh_token = login_data["refresh_token"]

    # 3. Get /me profile
    headers = {"Authorization": f"Bearer {token}"}
    res = client.get("/api/v1/auth/me", headers=headers)
    assert res.status_code == 200
    assert res.json()["username"] == "rest_user"

    # 4. OIDC Discovery
    res = client.get("/api/v1/auth/.well-known/openid-configuration")
    assert res.status_code == 200
    assert "token_endpoint" in res.json()
    assert "userinfo_endpoint" in res.json()

    # 5. JWKS Endpoint
    res = client.get("/api/v1/auth/jwks.json")
    assert res.status_code == 200
    assert "keys" in res.json()

    # 6. OAuth2 Password Form Token
    res = client.post("/api/v1/auth/oauth/token", data={
        "username": "rest_user",
        "password": "securepassword",
        "scope": "openid profile health_records"
    })
    assert res.status_code == 200
    oauth_data = res.json()
    assert "access_token" in oauth_data
    assert "id_token" in oauth_data

    # 7. OIDC UserInfo
    res = client.get("/api/v1/auth/oauth/userinfo", headers=headers)
    assert res.status_code == 200
    assert res.json()["preferred_username"] == "rest_user"

    # 8. OAuth2 Refresh Token
    res = client.post("/api/v1/auth/oauth/refresh", json={"refresh_token": refresh_token})
    assert res.status_code == 200
    assert "access_token" in res.json()

    # 9. OAuth2 Authorize Code Flow
    res = client.get("/api/v1/auth/oauth/authorize?response_type=code&redirect_uri=https://example.com/cb")
    assert res.status_code in [302, 303, 307]
    assert "code=" in res.headers["location"]



# --- RESTful API v1: Vaults & Documents Endpoints ---
def test_rest_vaults_and_documents_crud(client, db):
    # Setup user & token
    user = User(username="rest_vault_owner", password_hash=generate_password_hash("pass123"))
    db.add(user)
    db.commit()

    payload = {"user_id": user.id, "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=1)}
    token = jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Create family vault via REST POST
    family_payload = {
        "username": "rest_family_member",
        "password": "familypass123",
        "relation": "Mother",
        "full_name": "Mom Name",
        "blood_group": "B+",
        "allergies": "None"
    }
    res = client.post("/api/v1/vaults/family", json=family_payload, headers=headers)
    assert res.status_code == 201
    vault_data = res.json()
    vault_id = vault_data["id"]
    assert vault_data["relation"] == "Mother"
    assert vault_data["full_name"] == "Mom Name"

    # 2. List vaults via REST GET
    res = client.get("/api/v1/vaults", headers=headers)
    assert res.status_code == 200
    vaults = res.json()
    assert any(v["id"] == vault_id for v in vaults)

    # 3. Get single vault via REST GET
    res = client.get(f"/api/v1/vaults/{vault_id}", headers=headers)
    assert res.status_code == 200
    assert res.json()["full_name"] == "Mom Name"

    # 4. Update vault via REST PUT
    update_payload = {"full_name": "Updated Mom Name", "blood_group": "AB+"}
    res = client.put(f"/api/v1/vaults/{vault_id}", json=update_payload, headers=headers)
    assert res.status_code == 200
    assert res.json()["full_name"] == "Updated Mom Name"
    assert res.json()["blood_group"] == "AB+"

    # 5. Upload document via REST POST
    files = {"file": ("report.pdf", BytesIO(b"fake lab pdf"), "application/pdf")}
    data = {"category": "Diagnostic Lab Report", "file_name": "REST Blood Test"}
    with patch("app.services.document_service.upload_document_to_storage") as mock_up:
        mock_up.return_value = "vault_docs/vault_1/report.pdf"
        with patch("app.services.semantic_service.index_document") as mock_idx:
            mock_idx.return_value = True
            res = client.post(f"/api/v1/vaults/{vault_id}/documents", data=data, files=files, headers=headers)
    assert res.status_code == 201
    doc_data = res.json()
    doc_id = doc_data["id"]
    assert doc_data["file_name"] == "REST Blood Test"

    # 6. List documents via REST GET
    res = client.get(f"/api/v1/vaults/{vault_id}/documents", headers=headers)
    assert res.status_code == 200
    docs = res.json()
    assert len(docs) == 1
    assert docs[0]["id"] == doc_id

    # 7. AI Chat via REST POST
    chat_payload = {"query": "What is the diagnosis?", "context": "[report.pdf] Normal."}
    with patch.dict(os.environ, {"XAI_API_KEY": "", "GROQ_API_KEY": ""}):
        with patch("requests.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"response": "All parameters are normal."}
            mock_post.return_value = mock_resp
            res = client.post(f"/api/v1/vaults/{vault_id}/chat", json=chat_payload, headers=headers)
    assert res.status_code == 200
    assert "All parameters are normal." in res.json()["answer"]

    # 8. Delete document via REST DELETE
    with patch("app.services.document_service.delete_document_from_storage"):
        res = client.delete(f"/api/v1/vaults/{vault_id}/documents/{doc_id}", headers=headers)
    assert res.status_code == 200
    assert res.json()["status"] == "success"

    # 9. Emergency QR scan data endpoint
    res = client.get(f"/api/v1/scan/{vault_data['qr_token']}/data")
    assert res.status_code == 200
    assert res.json()["full_name"] == "Updated Mom Name"


# --- HTML & Form UI View Tests ---
def test_signup_html(client, db):
    res = client.get("/api/v1/signup")
    assert res.status_code == 200
    assert "signup" in res.text.lower() or "sign up" in res.text.lower()
    
    res = client.post("/api/v1/signup", data={"username": "newuser", "password": "password123"})
    assert res.status_code in [302, 303]
    
    user = db.query(User).filter(User.username == "newuser").first()
    assert user is not None
    
    vault = db.query(VaultProfile).filter(VaultProfile.owner_user_id == user.id).first()
    assert vault is not None
    assert vault.relation == "Self"

def test_login_logout_html(client, db):
    user = User(username="loginuser", password_hash=generate_password_hash("password123"))
    db.add(user)
    db.commit()
    
    res = client.post("/api/v1/login", data={"username": "loginuser", "password": "password123"})
    assert res.status_code in [302, 303]
    
    res = client.get("/api/v1/logout")
    assert res.status_code in [302, 303]

def test_vault_dashboard_access_control(client, db):
    # Try access dashboard without logging in
    res = client.get("/api/v1/vault")
    assert res.status_code in [302, 303]
    
    # Create user
    user = User(username="dashuser", password_hash=generate_password_hash("password123"))
    db.add(user)
    db.commit()
    
    vault = VaultProfile(owner_user_id=user.id, relation="Self", full_name="Dashboard User")
    db.add(vault)
    db.commit()
    
    db.add(VaultAccess(user_id=user.id, vault_id=vault.id, access_type="owner"))
    db.commit()
    
    # Login
    client.post("/api/v1/login", data={"username": "dashuser", "password": "password123"})
    res = client.get("/api/v1/vault")
    assert res.status_code == 200
    assert "Dashboard User" in res.text

def test_add_family_member_html(client, db):
    user = User(username="mainuser", password_hash=generate_password_hash("password123"))
    db.add(user)
    db.commit()
    
    client.post("/api/v1/login", data={"username": "mainuser", "password": "password123"})
    
    res = client.post("/api/v1/family/add-member", data={
        "username": "familymember",
        "password": "familypassword",
        "relation": "Father",
        "full_name": "Father Name",
        "blood_group": "A+",
        "allergies": "None",
        "personal_contact": "9999999999",
        "emergency_1_name": "Emergency User",
        "emergency_1_relation": "Son",
        "emergency_1_phone": "1111111111"
    })
    assert res.status_code in [302, 303]
    
    family_user = db.query(User).filter(User.username == "familymember").first()
    assert family_user is not None
    
    family_vault = db.query(VaultProfile).filter(VaultProfile.owner_user_id == family_user.id).first()
    assert family_vault is not None
    assert family_vault.relation == "Father"
    assert family_vault.full_name == "Father Name"

def test_view_single_vault_html(client, db):
    user = User(username="user_single", password_hash=generate_password_hash("password123"))
    db.add(user)
    db.commit()
    
    vault = VaultProfile(owner_user_id=user.id, relation="Self", full_name="Single Vault")
    db.add(vault)
    db.commit()
    
    db.add(VaultAccess(user_id=user.id, vault_id=vault.id, access_type="owner"))
    db.commit()
    
    client.post("/api/v1/login", data={"username": "user_single", "password": "password123"})
    res = client.get(f"/api/v1/vault/{vault.id}")
    assert res.status_code == 200
    assert "Single Vault" in res.text

def test_update_vault_html(client, db):
    user = User(username="user_update", password_hash=generate_password_hash("password123"))
    db.add(user)
    db.commit()
    
    vault = VaultProfile(owner_user_id=user.id, relation="Self", full_name="Old Name")
    db.add(vault)
    db.commit()
    
    db.add(VaultAccess(user_id=user.id, vault_id=vault.id, access_type="owner"))
    db.commit()
    
    client.post("/api/v1/login", data={"username": "user_update", "password": "password123"})
    res = client.post(f"/api/v1/vault/update/{vault.id}", data={
        "full_name": "New Name",
        "blood_group": "B-",
        "allergies": "Gluten",
        "medical_conditions": "Hypertension",
        "medications": "Lisinopril",
        "personal_contact": "8888888888",
        "emergency_1_name": "E1",
        "emergency_1_relation": "R1",
        "emergency_1_phone": "999999"
    })
    assert res.status_code in [302, 303]
    
    db.refresh(vault)
    assert vault.full_name == "New Name"
    assert vault.blood_group == "B-"
    assert vault.allergies == "Gluten"

def test_upload_document_html(client, db):
    user = User(username="user_upload", password_hash=generate_password_hash("password123"))
    db.add(user)
    db.commit()
    
    vault = VaultProfile(owner_user_id=user.id, relation="Self", full_name="Upload Vault")
    db.add(vault)
    db.commit()
    
    db.add(VaultAccess(user_id=user.id, vault_id=vault.id, access_type="owner"))
    db.commit()
    
    client.post("/api/v1/login", data={"username": "user_upload", "password": "password123"})
    
    files = {
        "file": ("report.pdf", BytesIO(b"dummy pdf content"), "application/pdf")
    }
    data = {
        "category": "Diagnostic Lab Report",
        "ocr_text": "Creatinine: 1.0 mg/dL\nSugar: 90 mg/dL",
        "file_name": "My Lab Report"
    }
    
    with patch("app.services.document_service.upload_document_to_storage") as mock_upload:
        mock_upload.return_value = "vault_docs/vault_1/report.pdf"
        with patch("app.services.semantic_service.index_document") as mock_index:
            res = client.post(f"/api/v1/vault/upload/{vault.id}", data=data, files=files)
              
    assert res.status_code in [302, 303]
    
    doc = db.query(Document).filter(Document.vault_id == vault.id).first()
    assert doc is not None
    assert doc.file_name == "My Lab Report"
    assert doc.ocr_text == "Creatinine: 1.0 mg/dL\nSugar: 90 mg/dL"

def test_delete_document_html(client, db):
    user = User(username="user_delete", password_hash=generate_password_hash("password123"))
    db.add(user)
    db.commit()
    
    vault = VaultProfile(owner_user_id=user.id, relation="Self", full_name="Vault")
    db.add(vault)
    db.commit()
    
    db.add(VaultAccess(user_id=user.id, vault_id=vault.id, access_type="owner"))
    db.commit()
    
    doc = Document(vault_id=vault.id, file_path="path", file_name="doc.pdf", uploaded_by=user.id)
    db.add(doc)
    db.commit()
    
    client.post("/api/v1/login", data={"username": "user_delete", "password": "password123"})
    res = client.post(f"/api/v1/vault/document/delete/{doc.id}")
    assert res.status_code in [302, 303]
    
    assert db.query(Document).filter(Document.id == doc.id).first() is None

def test_scan_qr_token_html(client, db):
    user = User(username="user_qr", password_hash=generate_password_hash("password123"))
    db.add(user)
    db.commit()
    
    vault = VaultProfile(owner_user_id=user.id, relation="Self", full_name="QR Vault", is_emergency_ready=True)
    db.add(vault)
    db.commit()
    
    res = client.get(f"/api/v1/scan/{vault.qr_token}")
    assert res.status_code == 200
    assert "QR Vault" in res.text
    
    log = db.query(QRScanLog).filter(QRScanLog.vault_id == vault.id).first()
    assert log is not None

def test_serve_document_authorization(client, db):
    user = User(username="user_serve", password_hash="hash")
    db.add(user)
    db.commit()
    
    vault = VaultProfile(owner_user_id=user.id, relation="Self", full_name="Serve Vault")
    db.add(vault)
    db.commit()
    
    db.add(VaultAccess(user_id=user.id, vault_id=vault.id, access_type="owner"))
    db.commit()
    
    doc = Document(vault_id=vault.id, file_name="report.pdf", ocr_text="text", file_path=f"vault_docs/vault_{vault.id}/report.pdf")
    db.add(doc)
    db.commit()
    
    upload_base = settings.UPLOAD_FOLDER
    full_path = os.path.join(upload_base, doc.file_path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, "wb") as f:
        f.write(b"fake pdf content")
        
    res = client.get(f"/api/v1/vault/{vault.id}/document/{doc.id}/serve")
    assert res.status_code == 401
    
    other_user = User(username="other_user", password_hash="hash")
    db.add(other_user)
    db.commit()
    
    payload = {
        "user_id": other_user.id,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=1)
    }
    token = jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")
    headers = {"Authorization": f"Bearer {token}"}
    
    res = client.get(f"/api/v1/vault/{vault.id}/document/{doc.id}/serve", headers=headers)
    assert res.status_code == 403
    
    payload = {
        "user_id": user.id,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=1)
    }
    token = jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")
    headers = {"Authorization": f"Bearer {token}"}
    
    res = client.get(f"/api/v1/vault/{vault.id}/document/{doc.id}/serve", headers=headers)
    assert res.status_code == 200
    assert res.content == b"fake pdf content"
    assert "default-src 'none'" in res.headers.get("Content-Security-Policy", "")
    assert "inline" in res.headers.get("Content-Disposition", "")
    
    try:
        os.remove(full_path)
    except Exception:
        pass
