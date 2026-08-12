import os
import base64
import hashlib
import logging
from typing import Optional, List
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

def _derive_key_from_seed(default_seed: str) -> str:
    """Derives a deterministic 32-byte urlsafe base64 key from a seed string for development/testing."""
    derived = hashlib.sha256(default_seed.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(derived).decode("utf-8")


class AppSettings(BaseSettings):
    """
    Enterprise Secure Application Settings for Aadhaar Health Bridge.
    Uses Pydantic v2 BaseSettings with custom secret masking and strict production validation.
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False
    )

    # 1. Environment & Base Configuration
    ENVIRONMENT: str = Field(default="development", description="Runtime environment: development | testing | production")
    APP_BASE_URL: str = Field(default="http://localhost:5000", description="Base public URL for QR generation and absolute links")

    # 2. Cryptographic Secrets & Authentication
    SECRET_KEY: str = Field(
        default_factory=lambda: os.getenv("SECRET_KEY", "ahb-dev-secret-key-change-in-production")
    )
    JWT_SECRET: str = Field(
        default_factory=lambda: os.getenv("JWT_SECRET", "ahb-dev-jwt-secret-change-in-production")
    )
    FERNET_KEY: str = Field(
        default_factory=lambda: os.getenv("FERNET_KEY", _derive_key_from_seed("ahb-fernet-key-seed-dev"))
    )
    DATABASE_ENCRYPTION_KEY: str = Field(
        default_factory=lambda: os.getenv("DATABASE_ENCRYPTION_KEY", _derive_key_from_seed("ahb-db-encryption-seed-dev"))
    )
    KMS_MASTER_KEY_256: str = Field(
        default_factory=lambda: os.getenv("KMS_MASTER_KEY_256", _derive_key_from_seed("ahb-kms-master-seed-dev"))
    )

    # 3. KMS & HashiCorp Vault Settings
    KMS_PROVIDER: str = Field(default="local", description="local | vault | aws | azure")
    VAULT_ADDR: str = Field(default="http://127.0.0.1:8200")
    VAULT_TOKEN: str = Field(default="")
    VAULT_SECRET_PATH: str = Field(default="secret/data/ahb/encryption-keys")
    VAULT_TRANSIT_KEY: str = Field(default="ahb-master-key")

    # 4. Transport Security: HTTPS / TLS 1.3 & 1.2
    ENFORCE_HTTPS: bool = Field(default=False)
    SSL_CERT_PATH: Optional[str] = None
    SSL_KEY_PATH: Optional[str] = None
    HSTS_MAX_AGE: int = Field(default=63072000, description="2-year RFC 6797 HSTS Preload validity")

    # 5. Local Storage Directories
    UPLOAD_FOLDER: str = Field(
        default_factory=lambda: os.getenv("UPLOAD_FOLDER", os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads"))
    )
    CHROMA_DIR: str = Field(
        default_factory=lambda: os.getenv("CHROMA_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "chroma_db"))
    )

    # 6. Distributed Cache & Rate Limiting (Redis)
    REDIS_URL: Optional[str] = None

    # 7. Cloud Storage Credentials
    AZURE_STORAGE_ACCOUNT: str = Field(default="")
    AZURE_STORAGE_CONTAINER: str = Field(default="health-vault")
    AZURE_STORAGE_SAS_TOKEN: str = Field(default="")
    AZURE_STORAGE_CONNECTION_STRING: str = Field(default="")

    SUPABASE_URL: str = Field(default="")
    SUPABASE_KEY: str = Field(default="")
    SUPABASE_BUCKET: str = Field(default="health-vault")

    # 8. Zero-Cost Local AI & Sentence Transformers Settings
    ALLOW_EXTERNAL_AI_APIS: bool = Field(default=False, description="Strict $0 cost guardrail")
    AI_API_MODE: str = Field(default="local", description="local | cloud")
    RAG_MODE: str = Field(default="local", description="local | cloud")
    LLM_PROVIDER: str = Field(default="ollama", description="ollama | grok | groq")
    VECTOR_STORE: str = Field(default="auto", description="auto | chroma | pgvector")
    SENTENCE_TRANSFORMER_MODEL: str = Field(default="all-MiniLM-L6-v2")
    EMBEDDING_DIM: int = Field(default=384)
    LOCAL_EMBEDDING_DIM: int = Field(default=384)
    OLLAMA_HOST: str = Field(default="http://localhost:11434")
    OLLAMA_MODEL: str = Field(default="gemma2:2b")
    OLLAMA_TIMEOUT: int = Field(default=15)
    XAI_API_KEY: str = Field(default="")
    GROQ_API_KEY: str = Field(default="")

    # 9. PostgreSQL Connection Pooling Settings
    DB_POOL_SIZE: int = Field(default=10)
    DB_MAX_OVERFLOW: int = Field(default=20)
    DB_POOL_TIMEOUT: int = Field(default=30)
    DB_POOL_RECYCLE: int = Field(default=300)
    DB_POOL_PRE_PING: bool = Field(default=True)

    @property
    def DATABASE_URL(self) -> str:
        """
        Resolves PostgreSQL database URL with automatic fallback to local SQLite.
        """
        url = (
            os.getenv("DATABASE_URL")
            or os.getenv("POSTGRES_URL")
            or os.getenv("SUPABASE_DB_URL")
        )

        if not url:
            pghost = os.getenv("PGHOST")
            pguser = os.getenv("PGUSER")
            pgpassword = os.getenv("PGPASSWORD", "")
            pgdatabase = os.getenv("PGDATABASE")
            pgport = os.getenv("PGPORT", "5432")
            pgsslmode = os.getenv("PGSSLMODE", "prefer")

            if pghost and pguser and pgdatabase:
                auth = f"{pguser}:{pgpassword}@" if pgpassword else f"{pguser}@"
                url = f"postgresql://{auth}{pghost}:{pgport}/{pgdatabase}?sslmode={pgsslmode}"

        if not url:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            db_path = os.path.join(base_dir, "app", "app.db")
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
            url = f"sqlite:///{db_path}"

        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)

        return url

    def __repr__(self) -> str:
        return f"<AppSettings environment={self.ENVIRONMENT!r} app_url={self.APP_BASE_URL!r} (secrets masked)>"

    def __str__(self) -> str:
        return self.__repr__()

    @model_validator(mode="after")
    def validate_production_security(self) -> "AppSettings":
        """Enforce strict production security checks."""
        if self.ENVIRONMENT == "production":
            insecure_defaults = [
                "ahb-dev-secret-key-change-in-production",
                "ahb-dev-jwt-secret-change-in-production",
                "prod-super-secret-key-12345-secure",
                "prod-jwt-secret-key-67890-secure"
            ]
            if self.SECRET_KEY in insecure_defaults:
                raise ValueError("PRODUCTION SECURITY VIOLATION: SECRET_KEY must be securely set via environment variable.")
            if self.JWT_SECRET in insecure_defaults:
                raise ValueError("PRODUCTION SECURITY VIOLATION: JWT_SECRET must be securely set via environment variable.")
        return self


# Create singleton instance
settings = AppSettings()