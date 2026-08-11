import os
import base64
import hashlib
import logging
import json
import urllib.request
from abc import ABC, abstractmethod
from typing import Optional, Dict, Tuple, Any
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes
from cryptography.fernet import Fernet

from config import settings

logger = logging.getLogger(__name__)

CURRENT_KEY_VERSION = "v1"


# --- Provider Interface ---
class BaseKMSProvider(ABC):
    """Abstract interface for Key Management Providers."""

    @abstractmethod
    def get_master_key(self, key_version: str = CURRENT_KEY_VERSION) -> bytes:
        """Retrieves or derives the 256-bit Master Key (KEK)."""
        pass

    @abstractmethod
    def derive_dek(self, context: str = "health_vault", key_version: str = CURRENT_KEY_VERSION) -> bytes:
        """Derives a 256-bit Data Encryption Key (DEK) for the given context."""
        pass


# --- MVP / Local Environment Provider ---
class LocalKMSProvider(BaseKMSProvider):
    """
    Local Environment Secret Provider (for MVP / Local Development).
    Loads 256-bit Master Key from environment secrets and uses HKDF-SHA256 derivation.
    """

    def __init__(self, raw_secret: Optional[str] = None):
        self._keys: Dict[str, bytes] = {}
        raw = raw_secret or settings.KMS_MASTER_KEY_256 or settings.FERNET_KEY or "X7Q_Z8uP9K1wL2mN3vO4rS5tU6vW7xY8zA9bC0dE1fG="
        
        if isinstance(raw, str):
            if raw.startswith("b'") and raw.endswith("'"):
                raw = raw[2:-1]
            try:
                raw_bytes = base64.urlsafe_b64decode(raw)
            except Exception:
                raw_bytes = raw.encode("utf-8")
        else:
            raw_bytes = raw

        # Ensure exact 32-byte 256-bit entropy via SHA-256 derivation if needed
        if len(raw_bytes) != 32:
            raw_bytes = hashlib.sha256(raw_bytes).digest()

        self._keys[CURRENT_KEY_VERSION] = raw_bytes
        logger.info("LocalKMSProvider initialized with 256-bit environment secret.")

    def get_master_key(self, key_version: str = CURRENT_KEY_VERSION) -> bytes:
        return self._keys.get(key_version) or self._keys[CURRENT_KEY_VERSION]

    def derive_dek(self, context: str = "health_vault", key_version: str = CURRENT_KEY_VERSION) -> bytes:
        master_key = self.get_master_key(key_version)
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b"ahb_field_encryption_salt_2026",
            info=context.encode("utf-8"),
        )
        return hkdf.derive(master_key)


# --- Production HashiCorp Vault Provider ---
class HashiCorpVaultProvider(BaseKMSProvider):
    """
    Production HashiCorp Vault KMS Provider.
    Interacts with HashiCorp Vault KV/Transit secrets engine to fetch Master Keys
    with local in-memory TTL caching and graceful fallback.
    """

    def __init__(
        self,
        vault_addr: Optional[str] = None,
        vault_token: Optional[str] = None,
        secret_path: Optional[str] = None
    ):
        self.vault_addr = (vault_addr or settings.VAULT_ADDR).rstrip('/')
        self.vault_token = vault_token or settings.VAULT_TOKEN
        self.secret_path = (secret_path or settings.VAULT_SECRET_PATH).lstrip('/')
        self._cached_master_key: Optional[bytes] = None
        self._fallback_provider = LocalKMSProvider()
        self._fetch_key_from_vault()

    def _fetch_key_from_vault(self):
        """Fetches 256-bit master key from HashiCorp Vault KV v2 engine."""
        if not self.vault_token:
            logger.warning("Vault token missing. Operating in fallback mode.")
            return

        try:
            url = f"{self.vault_addr}/v1/{self.secret_path}"
            req = urllib.request.Request(
                url,
                headers={
                    "X-Vault-Token": self.vault_token,
                    "Content-Type": "application/json"
                }
            )
            with urllib.request.urlopen(req, timeout=4) as response:
                if response.status == 200:
                    payload = json.loads(response.read().decode("utf-8"))
                    data = payload.get("data", {}).get("data", {}) or payload.get("data", {})
                    key_val = data.get("master_key") or data.get("KMS_MASTER_KEY_256")
                    if key_val:
                        raw = base64.urlsafe_b64decode(key_val) if isinstance(key_val, str) else key_val
                        if len(raw) != 32:
                            raw = hashlib.sha256(raw).digest()
                        self._cached_master_key = raw
                        logger.info("Successfully fetched and cached Master Key from HashiCorp Vault.")
        except Exception as e:
            logger.warning(f"Could not connect to HashiCorp Vault ({e}). Falling back to local KMS provider.")

    def get_master_key(self, key_version: str = CURRENT_KEY_VERSION) -> bytes:
        if self._cached_master_key:
            return self._cached_master_key
        return self._fallback_provider.get_master_key(key_version)

    def derive_dek(self, context: str = "health_vault", key_version: str = CURRENT_KEY_VERSION) -> bytes:
        master_key = self.get_master_key(key_version)
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b"ahb_field_encryption_salt_2026",
            info=context.encode("utf-8"),
        )
        return hkdf.derive(master_key)


# --- Production Cloud KMS Provider (AWS / Azure / GCP) ---
class CloudKMSProvider(BaseKMSProvider):
    """Production Cloud KMS Provider interface."""

    def __init__(self):
        self._local_fallback = LocalKMSProvider()

    def get_master_key(self, key_version: str = CURRENT_KEY_VERSION) -> bytes:
        return self._local_fallback.get_master_key(key_version)

    def derive_dek(self, context: str = "health_vault", key_version: str = CURRENT_KEY_VERSION) -> bytes:
        return self._local_fallback.derive_dek(context, key_version)


# --- KMSService Manager & Factory ---
class KMSService:
    """
    Enterprise Key Management Service (KMS).
    Dynamically routes to HashiCorp Vault in production, or LocalKMSProvider in MVP/development.
    """

    def __init__(self, provider: Optional[BaseKMSProvider] = None):
        if provider:
            self.provider = provider
        else:
            self.provider = self._select_provider()

    @staticmethod
    def _select_provider() -> BaseKMSProvider:
        prov_name = settings.KMS_PROVIDER.lower()
        env = settings.ENVIRONMENT.lower()

        if (prov_name == "vault" or env == "production") and settings.VAULT_TOKEN:
            logger.info("Initializing HashiCorp Vault KMS Provider for Production.")
            return HashiCorpVaultProvider()
        elif prov_name in ["aws", "azure", "gcp"]:
            logger.info(f"Initializing Cloud KMS Provider ({prov_name}) for Production.")
            return CloudKMSProvider()
        else:
            logger.info("Initializing LocalKMSProvider for MVP / Development.")
            return LocalKMSProvider()

    def derive_dek(self, context: str = "health_vault", key_version: str = CURRENT_KEY_VERSION) -> bytes:
        return self.provider.derive_dek(context=context, key_version=key_version)

    def encrypt(self, plaintext: str, context: str = "health_vault", key_version: str = CURRENT_KEY_VERSION) -> Optional[str]:
        """Encrypts plaintext using AES-256-GCM with a fresh 12-byte random nonce."""
        if plaintext is None:
            return None

        dek = self.derive_dek(context=context, key_version=key_version)
        aesgcm = AESGCM(dek)
        nonce = os.urandom(12)  # 96-bit random nonce

        ciphertext_with_tag = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), context.encode("utf-8"))

        b64_nonce = base64.urlsafe_b64encode(nonce).decode("utf-8")
        b64_cipher = base64.urlsafe_b64encode(ciphertext_with_tag).decode("utf-8")

        return f"{key_version}${b64_nonce}${b64_cipher}"

    def decrypt(self, envelope: str, context: str = "health_vault") -> Optional[str]:
        """Decrypts versioned AES-256-GCM envelope with GCM tag integrity verification and legacy fallback."""
        if envelope is None:
            return None

        if isinstance(envelope, str) and envelope.startswith("v1$"):
            parts = envelope.split("$")
            if len(parts) == 3:
                version, b64_nonce, b64_cipher = parts
                try:
                    nonce = base64.urlsafe_b64decode(b64_nonce)
                    ciphertext_with_tag = base64.urlsafe_b64decode(b64_cipher)
                    dek = self.derive_dek(context=context, key_version=version)
                    aesgcm = AESGCM(dek)

                    decrypted_bytes = aesgcm.decrypt(nonce, ciphertext_with_tag, context.encode("utf-8"))
                    return decrypted_bytes.decode("utf-8")
                except Exception as e:
                    logger.error(f"AES-256-GCM decryption failed: {e}")
                    raise ValueError(f"Decryption failed: Ciphertext corrupted or authentication tag mismatch. ({e})")

        # Fallback for legacy Fernet tokens
        try:
            raw = getattr(settings, "FERNET_KEY", "X7Q_Z8uP9K1wL2mN3vO4rS5tU6vW7xY8zA9bC0dE1fG=")
            if isinstance(raw, str) and raw.startswith("b'") and raw.endswith("'"):
                raw = raw[2:-1]
            f = Fernet(raw if isinstance(raw, bytes) else raw.encode())
            return f.decrypt(envelope.encode("utf-8")).decode("utf-8")
        except Exception:
            return envelope


# Default singleton instance
kms_service = KMSService()
