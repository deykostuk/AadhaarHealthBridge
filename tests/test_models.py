from app.models.patient import User, VaultProfile, VaultAccess, Document, HealthMetric, QRScanLog
from datetime import datetime
from sqlalchemy import text

def test_user_creation(db):
    user = User(username="testuser", password_hash="hashed_password", role="family_member")
    db.add(user)
    db.commit()
    
    saved_user = db.query(User).filter(User.username == "testuser").first()
    assert saved_user is not None
    assert saved_user.password_hash == "hashed_password"
    assert saved_user.role == "family_member"
    assert isinstance(saved_user.created_at, datetime)

def test_vault_profile_and_encryption(db):
    # Create owner user first
    user = User(username="owner", password_hash="hashed")
    db.add(user)
    db.commit()
    
    # Create vault profile with encrypted text fields
    profile = VaultProfile(
        owner_user_id=user.id,
        relation="Self",
        full_name="Owner Name",
        blood_group="O+",
        allergies="Peanuts",
        medical_conditions="Asthma",
        medications="Inhaler",
        personal_contact="1234567890",
        emergency_1_phone="0987654321"
    )
    db.add(profile)
    db.commit()
    
    saved_profile = db.query(VaultProfile).filter(VaultProfile.owner_user_id == user.id).first()
    assert saved_profile is not None
    assert saved_profile.relation == "Self"
    assert saved_profile.full_name == "Owner Name"
    # Verify transparent decryption
    assert saved_profile.allergies == "Peanuts"
    assert saved_profile.medical_conditions == "Asthma"
    assert saved_profile.medications == "Inhaler"
    assert saved_profile.personal_contact == "1234567890"
    assert saved_profile.emergency_1_phone == "0987654321"
    
    # Verify that it is actually encrypted in the database (raw SQL check)
    result = db.execute(text("SELECT allergies, medical_conditions FROM vault_profiles WHERE id = :id"), {"id": saved_profile.id}).fetchone()
    # Check that they don't match the plaintext anymore and use AES-256-GCM versioned envelope
    assert result[0] != "Peanuts"
    assert result[0].startswith("v1$")
    assert result[1] != "Asthma"
    assert result[1].startswith("v1$")

def test_vault_access_and_relationships(db):
    owner = User(username="owner_user", password_hash="hash")
    caregiver = User(username="caregiver_user", password_hash="hash")
    db.add_all([owner, caregiver])
    db.commit()
    
    profile = VaultProfile(owner_user_id=owner.id, relation="Father", full_name="Father Name")
    db.add(profile)
    db.commit()
    
    access1 = VaultAccess(user_id=owner.id, vault_id=profile.id, access_type="owner")
    access2 = VaultAccess(user_id=caregiver.id, vault_id=profile.id, access_type="caregiver")
    db.add_all([access1, access2])
    db.commit()
    
    assert len(profile.access_users) == 2
    assert len(owner.owned_vaults) == 1
    assert len(caregiver.vault_access) == 1

def test_document_and_metrics(db):
    user = User(username="user1", password_hash="hash")
    db.add(user)
    db.commit()
    
    profile = VaultProfile(owner_user_id=user.id, relation="Self", full_name="My Vault")
    db.add(profile)
    db.commit()
    
    doc = Document(
        vault_id=profile.id,
        file_path="vault_docs/vault_1/report.pdf",
        file_name="report.pdf",
        category="Diagnostic Lab Report",
        ocr_text="Glucose: 95 mg/dL",
        uploaded_by=user.id
    )
    db.add(doc)
    db.commit()
    
    metric = HealthMetric(
        vault_id=profile.id,
        metric_name="sugar",
        metric_value="95",
        metric_unit="mg/dL",
        observed_date=datetime.utcnow(),
        source_document_id=doc.id
    )
    db.add(metric)
    db.commit()
    
    assert len(profile.documents) == 1
    assert profile.documents[0].file_name == "report.pdf"
    
    saved_metric = db.query(HealthMetric).filter(HealthMetric.vault_id == profile.id).first()
    assert saved_metric is not None
    assert saved_metric.metric_name == "sugar"
    assert saved_metric.metric_value == "95"
    assert saved_metric.source_document_id == doc.id

def test_qr_scan_log(db):
    user = User(username="user2", password_hash="hash")
    db.add(user)
    db.commit()
    
    profile = VaultProfile(owner_user_id=user.id, relation="Self", full_name="My Vault")
    db.add(profile)
    db.commit()
    
    log = QRScanLog(
        vault_id=profile.id,
        ip_address="127.0.0.1",
        user_agent="Mozilla",
        location_data="Kanpur"
    )
    db.add(log)
    db.commit()
    
    saved_log = db.query(QRScanLog).filter(QRScanLog.vault_id == profile.id).first()
    assert saved_log is not None
    assert saved_log.ip_address == "127.0.0.1"
    assert saved_log.location_data == "Kanpur"

def test_postgres_database_url_resolution(monkeypatch):
    from config import Settings
    
    # 1. Normalizes postgres:// to postgresql://
    monkeypatch.setenv("DATABASE_URL", "postgres://user:pass@host:5432/dbname")
    s = Settings()
    assert s.DATABASE_URL == "postgresql://user:pass@host:5432/dbname"
    
    # 2. Discrete PG variables
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("PGHOST", "pg.example.com")
    monkeypatch.setenv("PGPORT", "5432")
    monkeypatch.setenv("PGUSER", "dbuser")
    monkeypatch.setenv("PGPASSWORD", "dbpass")
    monkeypatch.setenv("PGDATABASE", "healthdb")
    monkeypatch.setenv("PGSSLMODE", "require")
    
    s2 = Settings()
    assert s2.DATABASE_URL == "postgresql://dbuser:dbpass@pg.example.com:5432/healthdb?sslmode=require"

