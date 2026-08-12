import os
import base64
import hashlib
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv

load_dotenv()

def _get_or_derive_key(env_var: str, default_seed: str) -> str:
    val = os.getenv(env_var)
    if val:
        return val
    # Derive deterministic 32-byte urlsafe base64 key from default seed
    derived = hashlib.sha256(default_seed.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(derived).decode("utf-8")

class Settings:
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development").lower()
    
    SECRET_KEY: str = os.getenv("SECRET_KEY", "ahb-dev-secret-key-change-in-production")
    JWT_SECRET: str = os.getenv("JWT_SECRET", "ahb-dev-jwt-secret-change-in-production")
    FERNET_KEY: str = _get_or_derive_key("FERNET_KEY", "ahb-fernet-key-seed-dev")
    DATABASE_ENCRYPTION_KEY: str = _get_or_derive_key("DATABASE_ENCRYPTION_KEY", "ahb-db-encryption-seed-dev")
    KMS_MASTER_KEY_256: str = _get_or_derive_key("KMS_MASTER_KEY_256", "ahb-kms-master-seed-dev")
    
    # Key Management Service (KMS) & HashiCorp Vault Settings
    KMS_PROVIDER: str = os.getenv("KMS_PROVIDER", "local").lower() # "local" | "vault" | "aws" | "azure"
    VAULT_ADDR: str = os.getenv("VAULT_ADDR", "http://127.0.0.1:8200")
    VAULT_TOKEN: str = os.getenv("VAULT_TOKEN", "")
    VAULT_SECRET_PATH: str = os.getenv("VAULT_SECRET_PATH", "secret/data/ahb/encryption-keys")
    VAULT_TRANSIT_KEY: str = os.getenv("VAULT_TRANSIT_KEY", "ahb-master-key")
    
    # Base URL for QR generation and absolute links
    APP_BASE_URL: str = os.getenv("APP_BASE_URL", "http://localhost:5000")
    
    # Transport Security: HTTPS / TLS 1.3 & 1.2 Settings
    ENFORCE_HTTPS: bool = os.getenv("ENFORCE_HTTPS", "false").lower() in ["true", "1", "yes"]
    SSL_CERT_PATH: Optional[str] = os.getenv("SSL_CERT_PATH", None)
    SSL_KEY_PATH: Optional[str] = os.getenv("SSL_KEY_PATH", None)
    HSTS_MAX_AGE: int = int(os.getenv("HSTS_MAX_AGE", "63072000")) # 2-year RFC 6797 HSTS preload
    
    # Upload folder
    UPLOAD_FOLDER: str = os.getenv(
        "UPLOAD_FOLDER", 
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
    )
    
    # Chroma Directory
    CHROMA_DIR: str = os.getenv(
        "CHROMA_DIR",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "chroma_db")
    )

    # Distributed Cache & Rate Limiting (Redis)
    REDIS_URL: Optional[str] = os.getenv("REDIS_URL", None)

    # Cloud Storage Credentials
    AZURE_STORAGE_ACCOUNT: str = os.getenv("AZURE_STORAGE_ACCOUNT", "")
    AZURE_STORAGE_CONTAINER: str = os.getenv("AZURE_STORAGE_CONTAINER", "health-vault")
    AZURE_STORAGE_SAS_TOKEN: str = os.getenv("AZURE_STORAGE_SAS_TOKEN", "")
    AZURE_STORAGE_CONNECTION_STRING: str = os.getenv("AZURE_STORAGE_CONNECTION_STRING", "")
    
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "")
    SUPABASE_BUCKET: str = os.getenv("SUPABASE_BUCKET", "health-vault")

    # Zero-Cost Local AI & Sentence Transformers Settings
    ALLOW_EXTERNAL_AI_APIS: bool = os.getenv("ALLOW_EXTERNAL_AI_APIS", "false").lower() == "true" # Strict $0 cost guardrail
    AI_API_MODE: str = os.getenv("AI_API_MODE", "local").lower() # "local" | "cloud"
    RAG_MODE: str = os.getenv("RAG_MODE", "local").lower() # "local" | "cloud"
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "ollama").lower() # "ollama" | "grok" | "groq"
    VECTOR_STORE: str = os.getenv("VECTOR_STORE", "auto").lower() # "auto" | "chroma" | "pgvector"
    SENTENCE_TRANSFORMER_MODEL: str = os.getenv("SENTENCE_TRANSFORMER_MODEL", "all-MiniLM-L6-v2")
    EMBEDDING_DIM: int = int(os.getenv("EMBEDDING_DIM", "384"))
    LOCAL_EMBEDDING_DIM: int = int(os.getenv("LOCAL_EMBEDDING_DIM", "384"))
    OLLAMA_HOST: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "gemma2:2b")
    OLLAMA_TIMEOUT: int = int(os.getenv("OLLAMA_TIMEOUT", "15"))
    XAI_API_KEY: str = os.getenv("XAI_API_KEY", "")
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")

    # PostgreSQL Connection Pooling Properties
    DB_POOL_SIZE: int = int(os.getenv("DB_POOL_SIZE", "10"))
    DB_MAX_OVERFLOW: int = int(os.getenv("DB_MAX_OVERFLOW", "20"))
    DB_POOL_TIMEOUT: int = int(os.getenv("DB_POOL_TIMEOUT", "30"))
    DB_POOL_RECYCLE: int = int(os.getenv("DB_POOL_RECYCLE", "300"))
    DB_POOL_PRE_PING: bool = os.getenv("DB_POOL_PRE_PING", "true").lower() in ["true", "1", "yes"]

    @property
    def DATABASE_URL(self) -> str:
        """
        Resolves PostgreSQL database URL with fallback to local SQLite.
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

        if url:
            url = url.strip()
            if url.startswith("postgres://"):
                url = url.replace("postgres://", "postgresql://", 1)
            return url

        return f"sqlite:///{os.path.join(os.path.dirname(os.path.abspath(__file__)), 'health_bridge.db')}"

settings = Settings()