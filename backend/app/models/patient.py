from app import db
from datetime import datetime
import uuid
from sqlalchemy.types import TypeDecorator, Text
from cryptography.fernet import Fernet
from flask import current_app

class EncryptedText(TypeDecorator):
    impl = Text

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def _get_fernet(self):
        key = current_app.config.get("DATABASE_ENCRYPTION_KEY")
        if not key:
            key = b"c3RhcnR1cF9zZWNyZXRfa2V5X3ZhbGlkYXRpb25fdHI="
        else:
            if isinstance(key, str):
                key = key.encode()
        return Fernet(key)

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        f = self._get_fernet()
        return f.encrypt(value.encode()).decode()

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        try:
            f = self._get_fernet()
            return f.decrypt(value.encode()).decode()
        except Exception:
            return value

class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(30), default="family_member")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    owned_vaults = db.relationship("VaultProfile", backref="owner", lazy=True, cascade="all, delete-orphan")
    vault_access = db.relationship("VaultAccess", backref="user", lazy=True, cascade="all, delete-orphan")

class VaultProfile(db.Model):
    __tablename__ = "vault_profiles"
    id = db.Column(db.Integer, primary_key=True)
    owner_user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    relation = db.Column(db.String(30), nullable=False)
    full_name = db.Column(db.String(120), nullable=False)
    blood_group = db.Column(db.String(10))
    allergies = db.Column(EncryptedText)
    medical_conditions = db.Column(EncryptedText)
    medications = db.Column(EncryptedText)
    personal_contact = db.Column(EncryptedText)
    
    emergency_1_name = db.Column(db.String(120))
    emergency_1_relation = db.Column(db.String(50))
    emergency_1_phone = db.Column(EncryptedText)
    emergency_2_name = db.Column(db.String(120))
    emergency_2_relation = db.Column(db.String(50))
    emergency_2_phone = db.Column(EncryptedText)
    emergency_3_name = db.Column(db.String(120))
    emergency_3_relation = db.Column(db.String(50))
    emergency_3_phone = db.Column(EncryptedText)
    
    address = db.Column(db.Text)
    qr_token = db.Column(db.String(120), unique=True, default=lambda: str(uuid.uuid4()))
    is_emergency_ready = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    documents = db.relationship("Document", backref="vault", lazy=True, cascade="all, delete-orphan")
    access_users = db.relationship("VaultAccess", backref="vault_profile", lazy=True, cascade="all, delete-orphan")
    # JSON snapshot of latest metrics for quick access
    health_snapshot = db.Column(db.Text, nullable=True)




class VaultAccess(db.Model):
    __tablename__ = "vault_access"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    vault_id = db.Column(db.Integer, db.ForeignKey("vault_profiles.id", ondelete="CASCADE"), nullable=False)
    access_type = db.Column(db.String(30), default="caregiver")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Document(db.Model):
    __tablename__ = "documents"
    id = db.Column(db.Integer, primary_key=True)
    vault_id = db.Column(db.Integer, db.ForeignKey("vault_profiles.id", ondelete="CASCADE"), nullable=False)
    file_path = db.Column(db.String(255), nullable=False)
    file_name = db.Column(db.String(255), nullable=True)
    category = db.Column(db.String(100))
    ocr_text = db.Column(db.Text, nullable=True)
    uploaded_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)
    is_encrypted = db.Column(db.Boolean, default=False, nullable=True)
    ai_summary = db.Column(db.Text, nullable=True)


class HealthMetric(db.Model):
    __tablename__ = 'health_metrics'
    id = db.Column(db.Integer, primary_key=True)
    vault_id = db.Column(db.Integer, db.ForeignKey('vault_profiles.id', name='fk_metric_vault_id'))
    metric_name = db.Column(db.String(120))
    metric_value = db.Column(db.String(120))
    metric_unit = db.Column(db.String(50))
    observed_date = db.Column(db.DateTime)
    source_document_id = db.Column(db.Integer, db.ForeignKey('documents.id'))




class QRScanLog(db.Model):
    __tablename__ = 'qr_scan_logs'
    id = db.Column(db.Integer, primary_key=True)
    vault_id = db.Column(db.Integer, db.ForeignKey('vault_profiles.id', name='fk_qrscanlog_vault_id'))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.String(255))
    location_data = db.Column(db.String(255))