import os
import hashlib
import datetime
from datetime import timezone
from typing import Optional, Tuple, Dict, Any, List
import jwt
from sqlalchemy.orm import Session

from app.models.patient import User, VaultProfile, VaultAccess
from app.services.password_service import password_service
from config import settings

class AuthService:
    """Modular service handling OAuth 2.0, OpenID Connect (OIDC), JWT tokens, and user credentials."""

    def __init__(self, db: Session):
        self.db = db
        self.issuer = settings.APP_BASE_URL.rstrip('/') or "https://aadhaarhealthbridge.in"
        self.audience = "aadhaar-health-bridge-client"

    def register_user(self, username: str, password: str) -> Tuple[Optional[User], Optional[str]]:
        """Registers a new user with Argon2id password hash and creates default self-vault profile."""
        username = username.strip()
        if not username or not password:
            return None, "Username and password cannot be empty."

        existing_user = self.db.query(User).filter(User.username == username).first()
        if existing_user:
            return None, "Username already exists."

        user = User(
            username=username,
            password_hash=password_service.hash_password(password),
            role="family_member"
        )
        self.db.add(user)
        self.db.flush()

        self_vault = VaultProfile(
            owner_user_id=user.id,
            relation="Self",
            full_name=username
        )
        self.db.add(self_vault)
        self.db.flush()

        access = VaultAccess(
            user_id=user.id,
            vault_id=self_vault.id,
            access_type="owner"
        )
        self.db.add(access)
        self.db.commit()

        return user, None

    def authenticate_user(self, username: str, password: str) -> Tuple[Optional[User], Optional[str]]:
        """Verifies credentials with Argon2id/bcrypt and transparently rehashes legacy credentials."""
        username = username.strip()
        user = self.db.query(User).filter(User.username == username).first()

        if not user or not password_service.verify_password(password, user.password_hash):
            return None, None

        # Transparent rehash to Argon2id if using older hash
        if password_service.needs_rehash(user.password_hash):
            try:
                user.password_hash = password_service.hash_password(password)
                self.db.commit()
            except Exception:
                pass

        token = self.generate_access_token(user)
        return user, token

    def generate_access_token(self, user: User, scopes: str = "openid profile health_records") -> str:
        """Generates an RFC 7519 compliant OAuth 2.0 JWT Access Token."""
        now = datetime.datetime.now(timezone.utc)
        payload = {
            "iss": self.issuer,
            "sub": str(user.id),
            "aud": self.audience,
            "user_id": user.id,
            "username": user.username,
            "role": user.role,
            "scope": scopes,
            "iat": now,
            "exp": now + datetime.timedelta(hours=24)
        }
        return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")

    def generate_id_token(self, user: User, nonce: Optional[str] = None) -> str:
        """Generates an OpenID Connect (OIDC Core 1.0) ID Token containing user identity claims."""
        now = datetime.datetime.now(timezone.utc)
        self_vault = self.db.query(VaultProfile).filter(
            VaultProfile.owner_user_id == user.id,
            VaultProfile.relation == "Self"
        ).first()

        payload = {
            "iss": self.issuer,
            "sub": str(user.id),
            "aud": self.audience,
            "iat": now,
            "exp": now + datetime.timedelta(hours=24),
            "auth_time": int(now.timestamp()),
            "preferred_username": user.username,
            "name": self_vault.full_name if self_vault else user.username,
            "role": user.role,
            "vault_id": self_vault.id if self_vault else None
        }
        if nonce:
            payload["nonce"] = nonce

        return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")

    def generate_refresh_token(self, user: User) -> str:
        """Generates a long-lived signed Refresh Token."""
        now = datetime.datetime.now(timezone.utc)
        payload = {
            "iss": self.issuer,
            "sub": str(user.id),
            "token_type": "refresh_token",
            "iat": now,
            "exp": now + datetime.timedelta(days=30)
        }
        return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")

    def issue_oauth_bundle(self, user: User, scopes: str = "openid profile health_records", nonce: Optional[str] = None) -> Dict[str, Any]:
        """Issues complete OAuth 2.0 + OIDC token bundle."""
        access_token = self.generate_access_token(user, scopes=scopes)
        id_token = self.generate_id_token(user, nonce=nonce)
        refresh_token = self.generate_refresh_token(user)

        return {
            "access_token": access_token,
            "id_token": id_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": 86400,
            "scope": scopes
        }

    def verify_refresh_token(self, refresh_token: str) -> Optional[User]:
        """Validates a refresh token and returns the corresponding User."""
        try:
            payload = jwt.decode(
                refresh_token,
                settings.JWT_SECRET,
                algorithms=["HS256"],
                options={"verify_aud": False}
            )
            if payload.get("token_type") != "refresh_token":
                return None
            user_id = int(payload.get("sub") or payload.get("user_id"))
            return self.db.query(User).filter(User.id == user_id).first()
        except Exception:
            return None

    def get_oidc_userinfo(self, user: User) -> Dict[str, Any]:
        """Standard OpenID Connect UserInfo claims."""
        self_vault = self.db.query(VaultProfile).filter(
            VaultProfile.owner_user_id == user.id,
            VaultProfile.relation == "Self"
        ).first()

        return {
            "sub": str(user.id),
            "preferred_username": user.username,
            "name": self_vault.full_name if self_vault else user.username,
            "role": user.role,
            "vault_id": self_vault.id if self_vault else None,
            "updated_at": user.created_at.isoformat() if hasattr(user, "created_at") and user.created_at else None
        }

    def get_oidc_configuration(self, base_url: str) -> Dict[str, Any]:
        """Generates OpenID Connect Discovery document (.well-known/openid-configuration)."""
        base = base_url.rstrip('/')
        return {
            "issuer": base,
            "authorization_endpoint": f"{base}/api/v1/auth/oauth/authorize",
            "token_endpoint": f"{base}/api/v1/auth/oauth/token",
            "userinfo_endpoint": f"{base}/api/v1/auth/oauth/userinfo",
            "jwks_uri": f"{base}/api/v1/auth/jwks.json",
            "response_types_supported": ["code", "token", "id_token", "token id_token"],
            "subject_types_supported": ["public"],
            "id_token_signing_alg_values_supported": ["HS256"],
            "scopes_supported": ["openid", "profile", "health_records", "offline_access"],
            "token_endpoint_auth_methods_supported": ["client_secret_post", "client_secret_basic", "none"],
            "claims_supported": ["sub", "iss", "aud", "exp", "iat", "preferred_username", "name", "role", "vault_id"]
        }

    def get_jwks(self) -> Dict[str, Any]:
        """Public JWKS descriptor with RFC 7517 compliant metadata."""
        kid = hashlib.sha256(settings.JWT_SECRET.encode()).hexdigest()[:16]
        return {
            "keys": [
                {
                    "kty": "oct",
                    "alg": "HS256",
                    "use": "sig",
                    "kid": kid,
                    "key_ops": ["verify"]
                }
            ]
        }
