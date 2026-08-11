import logging
from typing import Optional
import argon2
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError
import bcrypt
from werkzeug.security import check_password_hash as werkzeug_check_hash

logger = logging.getLogger(__name__)

class PasswordService:
    """
    Enterprise Password Security Service.
    Standard: Argon2id (OWASP Recommended) with bcrypt & legacy Werkzeug fallback.
    Features:
    - Argon2id with memory-hard parameters (GPU / ASIC cracking resistance)
    - Fallback verification for bcrypt ($2b$, $2a$)
    - Fallback verification for legacy pbkdf2 / scrypt hashes
    - Transparent rehash detection for automatic user hash migration
    """

    def __init__(self):
        # OWASP recommended parameters: time_cost=3, memory_cost=65536 KiB (64MB), parallelism=4
        self.hasher = argon2.PasswordHasher(
            time_cost=3,
            memory_cost=65536,
            parallelism=4,
            hash_len=32,
            salt_len=16,
            type=argon2.Type.ID
        )

    def hash_password(self, plain_password: str) -> str:
        """Hashes password using Argon2id with salt."""
        if not plain_password:
            raise ValueError("Password cannot be empty.")
        return self.hasher.hash(plain_password)

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verifies plain password against Argon2id, bcrypt, or legacy Werkzeug hash."""
        if not plain_password or not hashed_password:
            return False

        # 1. Try Argon2id verification
        if hashed_password.startswith("$argon2"):
            try:
                return self.hasher.verify(hashed_password, plain_password)
            except (VerifyMismatchError, VerificationError, InvalidHashError):
                return False
            except Exception as e:
                logger.warning(f"Argon2 verification error: {e}")
                return False

        # 2. Try bcrypt verification
        if hashed_password.startswith(("$2b$", "$2a$", "$2y$")):
            try:
                return bcrypt.checkpw(
                    plain_password.encode("utf-8"),
                    hashed_password.encode("utf-8")
                )
            except Exception as e:
                logger.warning(f"bcrypt verification error: {e}")
                return False

        # 3. Try legacy Werkzeug (scrypt / pbkdf2:sha256) verification
        try:
            return werkzeug_check_hash(hashed_password, plain_password)
        except Exception:
            return False

    def needs_rehash(self, hashed_password: str) -> bool:
        """Detects if a hash is not using current Argon2id parameters and needs an upgrade."""
        if not hashed_password:
            return True

        if not hashed_password.startswith("$argon2id"):
            return True

        try:
            return self.hasher.check_needs_rehash(hashed_password)
        except Exception:
            return True


# Default singleton instance
password_service = PasswordService()
