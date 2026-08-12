import pytest
import json
from app.models.patient import VaultProfile, User, VaultAccess
from app.services.crypto_qr_service import crypto_qr_service
from app.services.password_service import password_service
from app.services.auth_service import AuthService


def test_ecdsa_offline_payload_lifecycle(db):
    user = User(username="crypto_patient", password_hash=password_service.hash_password("Password123!"), role="family_member")
    db.add(user)
    db.commit()

    vault = VaultProfile(
        owner_user_id=user.id,
        relation="Self",
        full_name="Aarav Mukherjee",
        blood_group="O+",
        allergies="Peanuts, Shellfish, Penicillin",
        medical_conditions="Type 1 Diabetes",
        medications="Insulin Glargine 20u",
        emergency_1_name="Rina Mukherjee",
        emergency_1_relation="Mother",
        emergency_1_phone="+919876543210",
        emergency_2_name="Debu Mukherjee",
        emergency_2_relation="Father",
        emergency_2_phone="+919876543211",
        is_emergency_ready=True
    )
    db.add(vault)
    db.commit()

    # 1. Generate signed offline QR payload
    signed_payload = crypto_qr_service.generate_signed_qr_payload(vault)
    assert signed_payload.startswith("AHB1.")
    assert len(signed_payload.split(".")) == 3
    # Payload length must be ultra-dense for high-reliability optical scanning (< 600 bytes)
    assert len(signed_payload) < 600

    # 2. Verify legitimate signed payload
    is_valid, data, err = crypto_qr_service.verify_signed_qr_payload(signed_payload)
    assert is_valid is True
    assert err is None
    assert data["name"] == "Aarav Mukherjee"
    assert data["bg"] == "O+"
    assert "Penicillin" in data["alg"]
    assert data["c1_name"] == "Rina Mukherjee"
    assert data["c1_ph"] == "+919876543210"

    # 3. Tamper Detection Test (Attacker attempts modifying blood group or payload bytes)
    parts = signed_payload.split(".")
    tampered_payload_b64 = parts[1][:-2] + "AA"
    tampered_string = f"AHB1.{tampered_payload_b64}.{parts[2]}"
    is_valid_t, data_t, err_t = crypto_qr_service.verify_signed_qr_payload(tampered_string)
    assert is_valid_t is False
    assert "tampered" in err_t.lower() or "failed" in err_t.lower()


def test_public_key_jwk_and_pem_export():
    jwk = crypto_qr_service.get_public_key_jwk()
    assert jwk["kty"] == "EC"
    assert jwk["crv"] == "P-256"
    assert "x" in jwk and "y" in jwk
    assert jwk["alg"] == "ES256"

    pem = crypto_qr_service.get_public_key_pem()
    assert "-----BEGIN PUBLIC KEY-----" in pem
    assert "-----END PUBLIC KEY-----" in pem


def test_crypto_qr_api_endpoints(client, db):
    user = User(username="crypto_api_user", password_hash=password_service.hash_password("Password123!"), role="family_member")
    db.add(user)
    db.commit()

    vault = VaultProfile(
        owner_user_id=user.id,
        relation="Self",
        full_name="Kavita Nair",
        blood_group="AB-",
        allergies="Aspirin",
        medical_conditions="Hypertension",
        medications="Amlodipine 5mg",
        is_emergency_ready=True
    )
    db.add(vault)
    db.commit()

    access = VaultAccess(user_id=user.id, vault_id=vault.id, access_type="owner")
    db.add(access)
    db.commit()

    token_bundle = AuthService(db).issue_oauth_bundle(user)
    token = token_bundle["access_token"] if isinstance(token_bundle, dict) else token_bundle.access_token
    auth_header = {"Authorization": f"Bearer {token}"}

    # 1. Fetch public key endpoint
    res_pk = client.get("/api/v1/auth/public-key")
    assert res_pk.status_code == 200
    pk_data = res_pk.json()
    assert pk_data["algorithm"] == "ECDSA-SHA256 (SECP256R1)"
    assert pk_data["jwk"]["crv"] == "P-256"

    # 2. Get signed cryptographic QR payload for vault
    res_qr = client.get(f"/api/v1/vaults/{vault.id}/crypto-qr", headers=auth_header)
    assert res_qr.status_code == 200
    qr_data = res_qr.json()
    assert qr_data["status"] == "success"
    raw_payload = qr_data["signed_qr_payload"]
    assert raw_payload.startswith("AHB1.")

    # 3. Verify signed offline payload via scan endpoint
    res_verify = client.post("/api/v1/scan/verify-offline", json={"raw_payload": raw_payload})
    assert res_verify.status_code == 200
    v_data = res_verify.json()
    assert v_data["cryptographic_verification"] == "VALID_ECDSA_P256_SEAL"
    assert v_data["triage_profile"]["name"] == "Kavita Nair"
    assert v_data["triage_profile"]["bg"] == "AB-"
