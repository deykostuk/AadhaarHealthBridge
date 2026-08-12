import os
import sys
import pytest
from io import BytesIO
from unittest.mock import patch, MagicMock

pytestmark = pytest.mark.unit

# Bypass azure-storage-blob library installation dependency in testing
mock_blob = MagicMock()
sys.modules["azure"] = MagicMock()
sys.modules["azure.storage"] = MagicMock()
sys.modules["azure.storage.blob"] = mock_blob

from app.services import (
    AuthService,
    VaultService,
    DocumentService,
    HealthMetricService,
    ChatService,
    storage_service,
    semantic_service,
)
from app.models.patient import User, VaultProfile, VaultAccess, Document, HealthMetric
from config import settings

def test_auth_service_registration_and_login(db):
    auth_service = AuthService(db)
    
    # Registration success
    user, err = auth_service.register_user("service_user", "pass123")
    assert err is None
    assert user is not None
    assert user.username == "service_user"
    
    # Check self vault created
    vault = db.query(VaultProfile).filter(VaultProfile.owner_user_id == user.id).first()
    assert vault is not None
    assert vault.relation == "Self"
    
    # Duplicate username error
    dup_user, dup_err = auth_service.register_user("service_user", "pass123")
    assert dup_user is None
    assert "already exists" in dup_err
    
    # Login success
    auth_user, token = auth_service.authenticate_user("service_user", "pass123")
    assert auth_user is not None
    assert token is not None
    
    # OAuth2 Token Bundle
    bundle = auth_service.issue_oauth_bundle(user, scopes="openid profile health_records")
    assert "access_token" in bundle
    assert "id_token" in bundle
    assert "refresh_token" in bundle
    assert bundle["token_type"] == "bearer"
    
    # Verify Refresh Token
    refresh_user = auth_service.verify_refresh_token(bundle["refresh_token"])
    assert refresh_user is not None
    assert refresh_user.id == user.id
    
    # OIDC UserInfo
    userinfo = auth_service.get_oidc_userinfo(user)
    assert userinfo["sub"] == str(user.id)
    assert userinfo["preferred_username"] == "service_user"
    
    # OIDC Discovery & JWKS
    config = auth_service.get_oidc_configuration("http://localhost:5000")
    assert "authorization_endpoint" in config
    assert "jwks_uri" in config
    jwks = auth_service.get_jwks()
    assert len(jwks["keys"]) > 0
    
    # Login failure
    fail_user, fail_token = auth_service.authenticate_user("service_user", "wrongpass")
    assert fail_user is None
    assert fail_token is None


def test_vault_service_management(db):
    auth_service = AuthService(db)
    vault_service = VaultService(db)
    
    user, _ = auth_service.register_user("parent_user", "pass123")
    
    # User vaults
    vaults = vault_service.get_user_vaults(user.id)
    assert len(vaults) == 1
    assert vaults[0]["full_name"] == "parent_user"
    
    # Add family member
    family_data = {
        "username": "child_user",
        "password": "childpass",
        "relation": "Daughter",
        "full_name": "Child Name",
        "blood_group": "A+"
    }
    child_vault, err = vault_service.create_family_member_vault(user.id, family_data)
    assert err is None
    assert child_vault.relation == "Daughter"
    
    # Verify caregiver access
    user_vaults_updated = vault_service.get_user_vaults(user.id)
    assert len(user_vaults_updated) == 2
    
    # Update vault profile
    update_data = {
        "full_name": "Updated Child Name",
        "blood_group": "O+",
        "allergies": "Dust"
    }
    success, update_err = vault_service.update_vault_profile(child_vault.id, user.id, update_data)
    assert success is True
    assert update_err is None
    assert child_vault.full_name == "Updated Child Name"
    
    # Verify viewer access cannot update vault profile
    viewer_user, _ = auth_service.register_user("viewer_user", "viewer123")
    from app.models.patient import VaultAccess
    db.add(VaultAccess(user_id=viewer_user.id, vault_id=child_vault.id, access_type="viewer"))
    db.commit()

    v_success, v_err = vault_service.update_vault_profile(child_vault.id, viewer_user.id, {"full_name": "Hacked Name"})
    assert v_success is False
    assert "cannot modify vault profile" in v_err

    # Log QR scan
    scanned_vault, loc = vault_service.log_qr_scan(child_vault.qr_token, "127.0.0.1", "Mozilla/5.0 (iPhone)")
    assert scanned_vault.id == child_vault.id
    logs = vault_service.get_recent_scan_logs(child_vault.id)
    assert len(logs) == 1
    assert logs[0]["ip_address"] == "127.0.0.1"

def test_document_service_pipeline(db):
    auth_service = AuthService(db)
    user, _ = auth_service.register_user("doc_user", "pass123")
    vault = db.query(VaultProfile).filter(VaultProfile.owner_user_id == user.id).first()
    
    doc_service = DocumentService(db)
    
    # Validation failure
    is_valid, err = doc_service.validate_file("bad.exe", 100)
    assert is_valid is False
    assert "not allowed" in err
    
    # Ingestion success with mock storage & semantic
    with patch("app.services.document_service.upload_document_to_storage") as mock_storage:
        mock_storage.return_value = "vault_docs/vault_1/report.pdf"
        with patch("app.services.semantic_service.index_document") as mock_idx:
            mock_idx.return_value = True
            doc, upload_err = doc_service.process_and_upload_document(
                vault_id=vault.id,
                user_id=user.id,
                filename="report.pdf",
                file_bytes=b"fake content",
                file_name="Lab Test",
                category="Diagnostic Lab Report",
                ocr_text="Creatinine: 1.2 mg/dL\nReport Date: 12/04/2026"
            )
            assert upload_err is None
            assert doc is not None
            assert doc.file_name == "Lab Test"
            
    # Check metric auto-extraction
    metrics = db.query(HealthMetric).filter(HealthMetric.vault_id == vault.id).all()
    assert len(metrics) == 1
    assert metrics[0].metric_name == "creatinine"
    assert metrics[0].metric_value == "1.2"
    
    # Delete document
    with patch("app.services.document_service.delete_document_from_storage"):
        del_success, del_err = doc_service.delete_document(doc.id, user.id)
        assert del_success is True
        assert db.query(Document).filter(Document.id == doc.id).first() is None

def test_health_metric_service(db):
    metric_service = HealthMetricService(db)
    auth_service = AuthService(db)
    user, _ = auth_service.register_user("metric_user", "pass123")
    vault = db.query(VaultProfile).filter(VaultProfile.owner_user_id == user.id).first()
    
    text = "Report Date: 12/04/2026\nSugar: 105 mg/dL\nUrea: 28 mg/dL"
    metric_service.extract_and_persist_metrics_from_text(vault.id, document_id=1, text=text)
    
    metrics = metric_service.get_vault_metrics(vault.id)
    assert len(metrics) == 2
    
    snapshot_data = metric_service.get_vault_snapshot_data(vault.id)
    assert snapshot_data["vault_id"] == vault.id
    assert "sugar" in snapshot_data["health_snapshot"]
    
    trend_resp = metric_service.build_trend_response_for_query(vault.id, "how is my blood sugar history?")
    assert trend_resp is not None
    assert "Clinical Trend Report" in trend_resp["answer"]

def test_chat_service_orchestration(db):
    auth_service = AuthService(db)
    user, _ = auth_service.register_user("chat_user", "pass123")
    vault = db.query(VaultProfile).filter(VaultProfile.owner_user_id == user.id).first()
    
    chat_service = ChatService(db)
    
    # Custom context query
    with patch.dict(os.environ, {"XAI_API_KEY": "", "GROQ_API_KEY": ""}):
        with patch("requests.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"response": "Patient is in stable health."}
            mock_post.return_value = mock_resp
            
            result = chat_service.process_chat_query(
                vault_id=vault.id,
                query="Summarize patient health condition",
                custom_context="[report.pdf] Normal findings."
            )
            assert result["answer"] == "Patient is in stable health."
            assert "Ollama" in result["ai_source"]

def test_storage_service_local_fallback():
    with patch.dict(os.environ, {
        "AZURE_STORAGE_ACCOUNT": "",
        "AZURE_STORAGE_SAS_TOKEN": "",
        "AZURE_STORAGE_CONNECTION_STRING": "",
        "SUPABASE_URL": "",
        "SUPABASE_KEY": ""
    }):
        file_bytes = b"dummy file content"
        filename = "test_file.txt"
        
        url = storage_service.upload_document_to_storage(file_bytes, filename, folder="test_vault")
        assert url == "test_vault/test_file.txt"
        
        upload_base = settings.UPLOAD_FOLDER
        expected_path = os.path.join(upload_base, "test_vault", filename)
        assert os.path.exists(expected_path)
        
        # Clean up
        if os.path.exists(expected_path):
            os.remove(expected_path)
            os.rmdir(os.path.dirname(expected_path))

def test_storage_service_azure_mock():
    with patch.dict(os.environ, {
        "AZURE_STORAGE_ACCOUNT": "testaccount",
        "AZURE_STORAGE_CONTAINER": "testcontainer",
        "AZURE_STORAGE_CONNECTION_STRING": "BlobEndpoint=https://testaccount.blob.core.windows.net/;SharedAccessSignature=sas"
    }):
        mock_client = MagicMock()
        mock_client.account_name = "testaccount"
        mock_blob_client = MagicMock()
        mock_blob.BlobServiceClient.from_connection_string.return_value = mock_client
        mock_client.get_blob_client.return_value = mock_blob_client
        
        file_bytes = b"dummy content"
        filename = "test.txt"
        url = storage_service.upload_document_to_storage(file_bytes, filename, folder="test")
        
        mock_blob_client.upload_blob.assert_called_once()
        assert "testaccount.blob.core.windows.net/testcontainer/test/test.txt" in url

def test_semantic_service_extract_structured_info():
    text = (
        "Report Date: 12/04/2026\n"
        "Creatinine: 1.1 mg/dL\n"
        "Urea: 35 mg/dL\n"
        "Uric Acid: 6.2 mg/dL\n"
        "Hemoglobin: 13.8 g/dL\n"
        "Sugar: 110 mg/dL\n"
        "HbA1c: 5.4%\n"
        "Medications: Metformin 500mg, Aspirin 75mg\n"
        "Allergies: Penicillin"
    )
    
    info = semantic_service.extract_structured_info(text)
    
    assert info["observed_date"] == "2026-04-12T00:00:00"
    assert info["creatinine"]["value"] == 1.1
    assert info["urea"]["value"] == 35.0
    assert info["uric_acid"]["value"] == 6.2
    assert info["hemoglobin"]["value"] == 13.8
    assert info["sugar"]["value"] == 110.0
    assert info["hba1c"]["value"] == 5.4
    assert "Metformin 500mg" in info["medications"]
    assert "Aspirin 75mg" in info["medications"]
    assert "Penicillin" in info["allergies"]

def test_semantic_service_trend_detection():
    assert semantic_service.is_trend_query("how is my blood sugar history?") is True
    assert semantic_service.is_trend_query("what are the latest creatinine changes?") is True
    assert semantic_service.is_trend_query("when should I take my medication?") is False

def test_semantic_service_chroma_mock(tmp_path):
    test_chroma_dir = str(tmp_path / "test_chroma")
    with patch.dict(os.environ, {"CHROMA_DIR": test_chroma_dir}):
        with patch("app.services.semantic_service._embed_texts") as mock_embed:
            mock_embed.return_value = [[0.1] * 1536]
            
            res_idx = semantic_service.index_document(
                vault_id=999,
                document_id=1,
                text="The patient should take Paracetamol twice a day.",
                file_name="prescription.txt"
            )
            assert res_idx is True
            
            res_query = semantic_service.semantic_query(vault_id=999, query="Paracetamol")
            assert len(res_query) > 0
            assert "Paracetamol" in res_query[0]["document"]

def test_kms_service_aes_256_gcm():
    from app.services.kms_service import KMSService
    
    kms = KMSService()
    plaintext = "Patient is allergic to Penicillin and Shellfish."
    
    # 1. Encryption
    encrypted = kms.encrypt(plaintext, context="allergies")
    assert encrypted.startswith("v1$")
    assert plaintext not in encrypted
    
    # 2. Nonce Uniqueness (identical plaintexts produce different ciphertexts)
    encrypted_second = kms.encrypt(plaintext, context="allergies")
    assert encrypted != encrypted_second
    
    # 3. Decryption
    decrypted = kms.decrypt(encrypted, context="allergies")
    assert decrypted == plaintext
    
    # 4. Tamper Resistance (tampered ciphertext fails authentication check)
    parts = encrypted.split("$")
    tampered_cipher = parts[2][:-4] + "AAAA"
    tampered_envelope = f"{parts[0]}${parts[1]}${tampered_cipher}"
    with pytest.raises(ValueError) as exc_info:
        kms.decrypt(tampered_envelope, context="allergies")
    assert "Decryption failed" in str(exc_info.value)
    
    # 5. HKDF Context Separation (same ciphertext with wrong context fails)
    with pytest.raises(ValueError):
        kms.decrypt(encrypted, context="wrong_context")

def test_kms_providers_vault_and_local():
    import json
    import base64
    import urllib.request
    from app.services.kms_service import LocalKMSProvider, HashiCorpVaultProvider, KMSService
    
    # 1. Local KMS Provider (MVP)
    local_prov = LocalKMSProvider()
    key_local = local_prov.get_master_key()
    assert len(key_local) == 32
    dek_local = local_prov.derive_dek(context="patient_data")
    assert len(dek_local) == 32
    
    # 2. HashiCorp Vault Provider (Mock Production API)
    fake_master_key_b64 = base64.urlsafe_b64encode(b"01234567890123456789012345678901").decode()
    mock_vault_response = MagicMock()
    mock_vault_response.status = 200
    mock_vault_response.read.return_value = json.dumps({
        "data": {
            "data": {
                "master_key": fake_master_key_b64
            }
        }
    }).encode("utf-8")
    
    mock_cm = MagicMock()
    mock_cm.__enter__.return_value = mock_vault_response
    
    with patch.object(urllib.request, "urlopen", return_value=mock_cm):
        vault_prov = HashiCorpVaultProvider(
            vault_addr="http://vault.internal:8200",
            vault_token="s.mocktoken123",
            secret_path="secret/data/ahb/keys"
        )
        assert vault_prov.get_master_key() == b"01234567890123456789012345678901"
        
    # 3. HashiCorp Vault Provider Fallback when unreachable
    with patch.object(urllib.request, "urlopen", side_effect=Exception("Connection refused")):
        fallback_prov = HashiCorpVaultProvider(
            vault_addr="http://unreachable:8200",
            vault_token="s.token",
            secret_path="secret/data/keys"
        )
        # Should gracefully fall back to local provider key
        assert len(fallback_prov.get_master_key()) == 32


