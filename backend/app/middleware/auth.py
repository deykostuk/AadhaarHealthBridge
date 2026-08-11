import jwt
from typing import Optional, List
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer, SecurityScopes
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.patient import User
from config import settings

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/oauth/token",
    scopes={
        "openid": "OpenID Connect user authentication",
        "profile": "Access user identity and vault profile",
        "health_records": "Read and write clinical medical locker records"
    },
    auto_error=False
)

async def get_current_user_from_token(
    security_scopes: Optional[SecurityScopes] = None,
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
    **kwargs
) -> User:
    """OAuth 2.0 / OIDC Bearer Token verification dependency."""
    # Allow credentials or token keyword arguments for flexible testing
    if not token and "credentials" in kwargs and kwargs["credentials"]:
        creds = kwargs["credentials"]
        token = creds.credentials if hasattr(creds, "credentials") else str(creds)

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"status": "error", "message": "Authentication required. Missing Bearer token."},
            headers={"WWW-Authenticate": 'Bearer'}
        )

    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=["HS256"],
            options={"verify_aud": False}
        )
        user_id = payload.get("user_id") or payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"status": "error", "message": "Invalid token payload."},
                headers={"WWW-Authenticate": "Bearer"}
            )
        user_id = int(user_id)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"status": "error", "message": "Token has expired. Please refresh token or log in again."},
            headers={"WWW-Authenticate": "Bearer"}
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"status": "error", "message": "Invalid authentication token."},
            headers={"WWW-Authenticate": "Bearer"}
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"status": "error", "message": "User not found."},
            headers={"WWW-Authenticate": "Bearer"}
        )

    # Validate scopes if required
    if security_scopes and security_scopes.scopes:
        token_scopes = payload.get("scope", "").split()
        for scope in security_scopes.scopes:
            if scope not in token_scopes and "openid" not in token_scopes:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={"status": "error", "message": f"Insufficient scope: required {scope}"},
                    headers={"WWW-Authenticate": f'Bearer scope="{security_scopes.scope_str}"'}
                )

    return user


async def get_current_user_hybrid(
    request: Request,
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    """Hybrid authentication: verifies OAuth 2.0 Bearer token or session cookie."""
    # 1. Check Bearer Token first
    if token:
        try:
            payload = jwt.decode(
                token,
                settings.JWT_SECRET,
                algorithms=["HS256"],
                options={"verify_aud": False}
            )
            user_id = payload.get("user_id") or payload.get("sub")
            if user_id:
                user = db.query(User).filter(User.id == int(user_id)).first()
                if user:
                    return user
        except Exception:
            pass

    # 2. Check Session Cookie fallback
    if hasattr(request, "session") and request.session.get("user_id"):
        user_id = request.session.get("user_id")
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            return user

    # 3. Check raw Authorization header fallback
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        raw_token = auth_header.split(" ")[1]
        try:
            payload = jwt.decode(
                raw_token,
                settings.JWT_SECRET,
                algorithms=["HS256"],
                options={"verify_aud": False}
            )
            user_id = payload.get("user_id") or payload.get("sub")
            if user_id:
                user = db.query(User).filter(User.id == int(user_id)).first()
                if user:
                    return user
        except Exception:
            pass

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"status": "error", "message": "Unauthorized. Please authenticate with Bearer token or login session."}
    )

# Alias for standard dependency injection
get_current_user = get_current_user_hybrid

