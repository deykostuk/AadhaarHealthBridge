import pytest
from app.models.patient import VaultProfile, User, SOSAlertLog
from app.services.sos_service import sos_service
from app.services.password_service import password_service


def test_sos_message_composition(db):
    user = User(username="sos_user", password_hash=password_service.hash_password("Password123!"), role="family_member")
    db.add(user)
    db.commit()

    vault = VaultProfile(
        owner_user_id=user.id,
        relation="Self",
        full_name="Rajesh Sharma",
        blood_group="B+",
        allergies="Penicillin, Sulfa drugs",
        medical_conditions="Type 2 Diabetes, Hypertension",
        medications="Metformin 500mg, Telmisartan 40mg",
        emergency_1_name="Pooja Sharma",
        emergency_1_relation="Wife",
        emergency_1_phone="+919876543210",
        emergency_2_name="Amit Sharma",
        emergency_2_relation="Brother",
        emergency_2_phone="+919811223344",
        is_emergency_ready=True
    )
    db.add(vault)
    db.commit()

    maps_url = sos_service.build_maps_url(28.6139, 77.2090)
    assert "https://www.google.com/maps?q=28.613900,77.209000" == maps_url

    msg = sos_service.compose_emergency_message(vault, maps_url, accuracy_meters=10.0, trigger_source="QR Scan")
    assert "Rajesh Sharma" in msg
    assert "B+" in msg
    assert "Penicillin" in msg
    assert "28.613900,77.209000" in msg
    assert "Accuracy: ±10m" in msg


def test_paramedic_qr_sos_endpoint(client, db):
    user = User(username="paramedic_test_user", password_hash=password_service.hash_password("Password123!"), role="family_member")
    db.add(user)
    db.commit()

    vault = VaultProfile(
        owner_user_id=user.id,
        relation="Self",
        full_name="Vikram Verma",
        blood_group="AB+",
        allergies="Peanuts",
        medical_conditions="Asthma",
        medications="Inhaler",
        emergency_1_name="Suman Verma",
        emergency_1_relation="Mother",
        emergency_1_phone="+919988776655",
        is_emergency_ready=True
    )
    db.add(vault)
    db.commit()

    # 1. Paramedic triggers SOS on QR scan with GPS
    res = client.post(
        f"/api/v1/scan/{vault.qr_token}/sos",
        json={
            "latitude": 19.0760,
            "longitude": 72.8777,
            "accuracy_meters": 5.5,
            "trigger_source": "qr_scan"
        },
        headers={"X-Forwarded-For": "49.36.120.45"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["patient_name"] == "Vikram Verma"
    assert data["blood_group"] == "AB+"
    assert data["contacts_notified_count"] == 1
    assert "19.076000,72.877700" in data["gps_location"]["maps_url"]
    assert len(data["whatsapp_dispatch_links"]) == 1
    assert "api.whatsapp.com" in data["whatsapp_dispatch_links"][0]["whatsapp_url"]
    assert "cryptographic_seal_sha256" in data

    # 2. Query emergency contacts
    res_contacts = client.get(f"/api/v1/scan/{vault.qr_token}/contacts")
    assert res_contacts.status_code == 200
    c_data = res_contacts.json()
    assert c_data["patient_name"] == "Vikram Verma"
    assert len(c_data["emergency_contacts"]) == 1
    assert c_data["emergency_contacts"][0]["name"] == "Suman Verma"


def test_one_tap_pwa_sos_endpoint(client, db):
    user = User(username="pwa_sos_user", password_hash=password_service.hash_password("Password123!"), role="family_member")
    db.add(user)
    db.commit()

    vault = VaultProfile(
        owner_user_id=user.id,
        relation="Self",
        full_name="Sunita Rao",
        blood_group="O-",
        emergency_1_name="Kiran Rao",
        emergency_1_relation="Spouse",
        emergency_1_phone="+919123456789",
        is_emergency_ready=True
    )
    db.add(vault)
    db.commit()

    from app.models.patient import VaultAccess
    access = VaultAccess(user_id=user.id, vault_id=vault.id, access_type="owner")
    db.add(access)
    db.commit()

    from app.services.auth_service import AuthService
    token_bundle = AuthService(db).issue_oauth_bundle(user)
    token = token_bundle["access_token"] if isinstance(token_bundle, dict) else token_bundle.access_token
    auth_header = {"Authorization": f"Bearer {token}"}

    # 1. Trigger SOS broadcast from PWA
    res = client.post(
        f"/api/v1/vaults/{vault.id}/sos",
        json={
            "latitude": 12.9716,
            "longitude": 77.5946,
            "accuracy_meters": 12.0,
            "trigger_source": "one_tap_pwa"
        },
        headers=auth_header
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["patient_name"] == "Sunita Rao"
    assert data["contacts_notified_count"] == 1

    # 2. Retrieve SOS history
    res_history = client.get(f"/api/v1/vaults/{vault.id}/sos/history", headers=auth_header)
    assert res_history.status_code == 200
    history = res_history.json()
    assert len(history) >= 1
    assert history[0]["vault_id"] == vault.id
    assert history[0]["trigger_source"] == "one_tap_pwa"
    assert history[0]["latitude"] == "12.9716"
    assert history[0]["longitude"] == "77.5946"
