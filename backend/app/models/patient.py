from datetime import datetime
import uuid
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.types import TypeDecorator
from cryptography.fernet import Fernet
from app.database import Base
from config import settings

from app.services.kms_service import kms_service

class EncryptedText(TypeDecorator):
    """
    SQLAlchemy TypeDecorator providing transparent AES-256-GCM (AEAD) encryption
    backed by the Key Management Service (KMS) with HKDF key derivation and tamper verification.
    """
    impl = Text
    cache_ok = True

    def __init__(self, context: str = "health_vault", *args, **kwargs):
        self.context = context
        super().__init__(*args, **kwargs)

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return kms_service.encrypt(str(value), context=self.context)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        try:
            return kms_service.decrypt(value, context=self.context)
        except Exception:
            return value

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(80), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(30), default="family_member")
    created_at = Column(DateTime, default=datetime.utcnow)

    owned_vaults = relationship("VaultProfile", back_populates="owner", cascade="all, delete-orphan")
    vault_access = relationship("VaultAccess", back_populates="user", cascade="all, delete-orphan")

class VaultProfile(Base):
    __tablename__ = "vault_profiles"
    id = Column(Integer, primary_key=True, index=True)
    owner_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    relation = Column(String(30), nullable=False)
    full_name = Column(String(120), nullable=False)
    blood_group = Column(String(10))
    allergies = Column(EncryptedText)
    medical_conditions = Column(EncryptedText)
    medications = Column(EncryptedText)
    personal_contact = Column(EncryptedText)
    
    emergency_1_name = Column(String(120))
    emergency_1_relation = Column(String(50))
    emergency_1_phone = Column(EncryptedText)
    emergency_2_name = Column(String(120))
    emergency_2_relation = Column(String(50))
    emergency_2_phone = Column(EncryptedText)
    emergency_3_name = Column(String(120))
    emergency_3_relation = Column(String(50))
    emergency_3_phone = Column(EncryptedText)
    
    address = Column(Text)
    qr_token = Column(String(120), unique=True, default=lambda: str(uuid.uuid4()))
    is_emergency_ready = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    health_snapshot = Column(Text, nullable=True)

    owner = relationship("User", back_populates="owned_vaults")
    documents = relationship("Document", back_populates="vault", cascade="all, delete-orphan")
    access_users = relationship("VaultAccess", back_populates="vault_profile", cascade="all, delete-orphan")
    health_metrics = relationship("HealthMetric", back_populates="vault", cascade="all, delete-orphan")
    scan_logs = relationship("QRScanLog", back_populates="vault", cascade="all, delete-orphan")
    consents = relationship("ConsentRecord", back_populates="vault", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="vault", cascade="all, delete-orphan")
    provenance_records = relationship("ProvenanceRecord", back_populates="vault", cascade="all, delete-orphan")
    embeddings = relationship("DocumentEmbedding", back_populates="vault", cascade="all, delete-orphan")

class VaultAccess(Base):
    __tablename__ = "vault_access"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    vault_id = Column(Integer, ForeignKey("vault_profiles.id", ondelete="CASCADE"), nullable=False)
    access_type = Column(String(30), default="caregiver")
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="vault_access")
    vault_profile = relationship("VaultProfile", back_populates="access_users")

class Document(Base):
    __tablename__ = "documents"
    id = Column(Integer, primary_key=True, index=True)
    vault_id = Column(Integer, ForeignKey("vault_profiles.id", ondelete="CASCADE"), nullable=False)
    file_path = Column(String(255), nullable=False)
    file_name = Column(String(255), nullable=True)
    category = Column(String(100))
    ocr_text = Column(Text, nullable=True)
    uploaded_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    upload_date = Column(DateTime, default=datetime.utcnow)
    is_encrypted = Column(Boolean, default=False, nullable=True)
    ai_summary = Column(Text, nullable=True)

    vault = relationship("VaultProfile", back_populates="documents")
    embeddings = relationship("DocumentEmbedding", back_populates="document", cascade="all, delete-orphan")

class HealthMetric(Base):
    __tablename__ = 'health_metrics'
    id = Column(Integer, primary_key=True, index=True)
    vault_id = Column(Integer, ForeignKey('vault_profiles.id', name='fk_metric_vault_id', ondelete="CASCADE"))
    metric_name = Column(String(120))
    metric_value = Column(String(120))
    metric_unit = Column(String(50))
    observed_date = Column(DateTime)
    source_document_id = Column(Integer, ForeignKey('documents.id', ondelete="SET NULL"), nullable=True)

    vault = relationship("VaultProfile", back_populates="health_metrics")

class QRScanLog(Base):
    __tablename__ = 'qr_scan_logs'
    id = Column(Integer, primary_key=True, index=True)
    vault_id = Column(Integer, ForeignKey('vault_profiles.id', name='fk_qrscanlog_vault_id', ondelete="CASCADE"))
    timestamp = Column(DateTime, default=datetime.utcnow)
    ip_address = Column(String(45))
    user_agent = Column(String(255))
    location_data = Column(String(255))

    vault = relationship("VaultProfile", back_populates="scan_logs")

class ConsentRecord(Base):
    __tablename__ = 'consent_records'
    id = Column(Integer, primary_key=True, index=True)
    vault_id = Column(Integer, ForeignKey('vault_profiles.id', ondelete="CASCADE"), nullable=False)
    granter_user_id = Column(Integer, ForeignKey('users.id', ondelete="CASCADE"), nullable=False)
    grantee_identifier = Column(String(120), nullable=False)
    consent_type = Column(String(50), default="patient-privacy")
    purpose = Column(String(50), default="TREAT")
    status = Column(String(50), default="active")
    valid_from = Column(DateTime, default=datetime.utcnow)
    valid_to = Column(DateTime, nullable=True)
    allowed_resources = Column(String(255), default="all")
    created_at = Column(DateTime, default=datetime.utcnow)

    vault = relationship("VaultProfile", back_populates="consents")
    granter = relationship("User")

class AuditLog(Base):
    __tablename__ = 'audit_logs'
    id = Column(Integer, primary_key=True, index=True)
    vault_id = Column(Integer, ForeignKey('vault_profiles.id', ondelete="CASCADE"), nullable=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete="SET NULL"), nullable=True)
    action = Column(String(30), default="READ")  # CREATE, READ, UPDATE, DELETE, EXECUTE
    event_type = Column(String(60), default="rest-operation")
    resource_type = Column(String(60), default="Patient")
    resource_id = Column(String(120), nullable=True)
    outcome = Column(String(30), default="SUCCESS")  # SUCCESS, FAILURE, DENIED
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(255), nullable=True)
    details = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)

    vault = relationship("VaultProfile", back_populates="audit_logs")
    user = relationship("User")

class ProvenanceRecord(Base):
    __tablename__ = 'provenance_records'
    id = Column(Integer, primary_key=True, index=True)
    vault_id = Column(Integer, ForeignKey('vault_profiles.id', ondelete="CASCADE"), nullable=False)
    target_type = Column(String(60), default="DocumentReference")
    target_id = Column(String(120), nullable=False)
    activity = Column(String(50), default="CREATE")  # CREATE, UPDATE, EXTRACT, TRANSIT
    agent_type = Column(String(50), default="author")  # author, assembler, custodian, ai-extractor
    agent_name = Column(String(120), nullable=False)
    source_reference = Column(String(120), nullable=True)
    integrity_hash = Column(String(64), nullable=True)  # SHA-256
    recorded_at = Column(DateTime, default=datetime.utcnow)

    vault = relationship("VaultProfile", back_populates="provenance_records")

class DocumentEmbedding(Base):
    __tablename__ = 'document_embeddings'
    id = Column(Integer, primary_key=True, index=True)
    vault_id = Column(Integer, ForeignKey('vault_profiles.id', ondelete="CASCADE"), nullable=False, index=True)
    document_id = Column(Integer, ForeignKey('documents.id', ondelete="CASCADE"), nullable=False, index=True)
    chunk_index = Column(Integer, default=0)
    chunk_text = Column(Text, nullable=False)
    file_name = Column(String(255), nullable=True)
    embedding_json = Column(Text, nullable=False)  # Stores 384-dim normalized vector as JSON
    created_at = Column(DateTime, default=datetime.utcnow)

    vault = relationship("VaultProfile", back_populates="embeddings")
    document = relationship("Document", back_populates="embeddings")