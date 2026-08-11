import pytest
import bcrypt
from werkzeug.security import generate_password_hash
from app.services.password_service import PasswordService, password_service

def test_argon2id_hashing_and_verification():
    ps = PasswordService()
    raw_password = "SuperSecretMedicalPassword!2026"

    # 1. Generate Argon2id hash
    hashed = ps.hash_password(raw_password)
    assert hashed.startswith("$argon2id$")
    assert raw_password not in hashed

    # 2. Correct password verification
    assert ps.verify_password(raw_password, hashed) is True

    # 3. Incorrect password rejection
    assert ps.verify_password("WrongPassword!", hashed) is False

    # 4. Empty password handling
    assert ps.verify_password("", hashed) is False
    assert ps.verify_password(raw_password, "") is False


def test_bcrypt_fallback_verification():
    ps = PasswordService()
    raw_password = "BcryptPassword#456"

    # Generate standard bcrypt hash ($2b$)
    salt = bcrypt.gensalt(rounds=10)
    bcrypt_hash = bcrypt.hashpw(raw_password.encode("utf-8"), salt).decode("utf-8")
    assert bcrypt_hash.startswith("$2b$")

    # Verify bcrypt hash via PasswordService
    assert ps.verify_password(raw_password, bcrypt_hash) is True
    assert ps.verify_password("InvalidBcryptPassword", bcrypt_hash) is False

    # Needs rehash detection for bcrypt to upgrade to Argon2id
    assert ps.needs_rehash(bcrypt_hash) is True


def test_legacy_werkzeug_hash_and_rehash_migration(db):
    from app.services.auth_service import AuthService
    from app.models.patient import User

    auth_service = AuthService(db)
    raw_password = "LegacyPbkdf2Password@789"

    # Create user with legacy Werkzeug hash (pbkdf2:sha256 or scrypt)
    legacy_hash = generate_password_hash(raw_password)
    legacy_user = User(username="legacy_user", password_hash=legacy_hash, role="family_member")
    db.add(legacy_user)
    db.commit()

    # User starts with legacy hash
    assert not legacy_user.password_hash.startswith("$argon2id$")

    # 1. Login with correct credentials
    user, token = auth_service.authenticate_user("legacy_user", raw_password)
    assert user is not None
    assert token is not None

    # 2. Verify user hash was transparently upgraded to Argon2id in the database!
    db.refresh(user)
    assert user.password_hash.startswith("$argon2id$")

    # 3. Verify that next login works with upgraded Argon2id hash
    user_second, token_second = auth_service.authenticate_user("legacy_user", raw_password)
    assert user_second is not None
    assert token_second is not None
