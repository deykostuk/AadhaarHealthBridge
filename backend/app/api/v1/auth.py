from fastapi import APIRouter, Depends, HTTPException, Request, Response, status, Form
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.services.auth_service import AuthService
from app.schemas.patient import (
    UserCreate,
    UserOut,
    LoginRequest,
    ChangePasswordRequest,
    TokenResponse,
    OAuthTokenResponse,
    RefreshTokenRequest,
    OIDCDiscoveryResponse,
    OIDCUserInfoResponse,
    JWKSResponse
)
from app.middleware.auth import get_current_user_from_token, get_current_user_hybrid
from app.models.patient import User
from config import settings

router = APIRouter(prefix="/auth", tags=["Authentication"])

# --- OpenID Connect (OIDC) Discovery & JWKS ---
@router.get("/.well-known/openid-configuration", response_model=OIDCDiscoveryResponse)
async def openid_configuration(request: Request, db: Session = Depends(get_db)):
    """OIDC Core 1.0 Provider Discovery Document."""
    auth_service = AuthService(db)
    base_url = str(request.base_url).rstrip('/')
    return auth_service.get_oidc_configuration(base_url)


@router.get("/jwks.json", response_model=JWKSResponse)
async def jwks(db: Session = Depends(get_db)):
    """JSON Web Key Set (JWKS) public key metadata."""
    auth_service = AuthService(db)
    return auth_service.get_jwks()


# --- OAuth 2.0 Token Endpoint ---
@router.post("/oauth/token", response_model=OAuthTokenResponse)
async def oauth_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """Standard OAuth 2.0 Token Endpoint supporting password grant and issuing ID tokens."""
    auth_service = AuthService(db)
    user, _ = auth_service.authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid_grant: Invalid username or password.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    scopes = " ".join(form_data.scopes) if form_data.scopes else "openid profile health_records"
    return auth_service.issue_oauth_bundle(user, scopes=scopes)


@router.post("/oauth/refresh", response_model=OAuthTokenResponse)
async def refresh_oauth_token(
    payload: RefreshTokenRequest,
    db: Session = Depends(get_db)
):
    """OAuth 2.0 Token Refresh endpoint."""
    auth_service = AuthService(db)
    user = auth_service.verify_refresh_token(payload.refresh_token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid_grant: Invalid or expired refresh token."
        )

    return auth_service.issue_oauth_bundle(user)


# --- OpenID Connect UserInfo ---
@router.get("/oauth/userinfo", response_model=OIDCUserInfoResponse)
async def oidc_userinfo(
    current_user: User = Depends(get_current_user_hybrid),
    db: Session = Depends(get_db)
):
    """OIDC Core 1.0 UserInfo Endpoint."""
    auth_service = AuthService(db)
    return auth_service.get_oidc_userinfo(current_user)


# --- OAuth 2.0 Authorize Flow ---
@router.get("/oauth/authorize")
async def oauth_authorize(
    response_type: str = "code",
    client_id: Optional[str] = None,
    redirect_uri: Optional[str] = None,
    scope: str = "openid profile health_records",
    state: Optional[str] = None
):
    """OAuth 2.0 Authorization Endpoint."""
    if redirect_uri:
        sep = "&" if "?" in redirect_uri else "?"
        code = "ahb_auth_code_sample"
        target = f"{redirect_uri}{sep}code={code}"
        if state:
            target += f"&state={state}"
        return RedirectResponse(url=target)

    return JSONResponse(content={
        "status": "success",
        "message": "Authorization code issued.",
        "code": "ahb_auth_code_sample",
        "state": state
    })


# --- JSON REST Authentication ---
@router.post("/signup", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def signup(payload: UserCreate, db: Session = Depends(get_db)):
    """REST API: Register a new user and create default self-vault."""
    auth_service = AuthService(db)
    user, err = auth_service.register_user(payload.username, payload.password)
    if err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": err}
        )
    return user


@router.post("/login", response_model=OAuthTokenResponse)
async def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    """REST API: Authenticate user and issue OAuth 2.0 + OIDC Token bundle with anti-brute-force lockout."""
    from app.services.lockout_service import lockout_service
    client_ip = request.headers.get("X-Forwarded-For", request.client.host if request.client else "unknown").split(",")[0].strip()

    # 1. Check account lockout state
    is_locked, remaining = lockout_service.is_locked(payload.username, ip=client_ip)
    if is_locked:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "status": "error",
                "message": f"Account is temporarily locked due to excessive failed attempts. Please retry in {remaining} seconds."
            }
        )

    auth_service = AuthService(db)
    user, _ = auth_service.authenticate_user(payload.username, payload.password)
    if not user:
        attempts, is_now_locked, lock_secs = lockout_service.record_failed_attempt(payload.username, ip=client_ip)
        if is_now_locked:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "status": "error",
                    "message": f"Account has been locked for {lock_secs // 60} minutes due to {attempts} consecutive failed attempts."
                }
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"status": "error", "message": "Invalid username or password."}
        )

    # 2. Reset lockout attempts upon successful authentication
    lockout_service.reset_attempts(payload.username, ip=client_ip)
    return auth_service.issue_oauth_bundle(user)


@router.get("/me", response_model=UserOut)
async def get_current_user_profile(current_user: User = Depends(get_current_user_hybrid)):
    """REST API: Get current authenticated user details."""
    return current_user


@router.post("/change-password")
async def change_password(
    payload: ChangePasswordRequest,
    current_user: User = Depends(get_current_user_hybrid),
    db: Session = Depends(get_db)
):
    """REST API: Change password for currently authenticated user."""
    from app.services.password_service import password_service

    if not password_service.verify_password(payload.old_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": "Incorrect existing password."}
        )

    current_user.password_hash = password_service.hash_password(payload.new_password)
    db.commit()

    return {"status": "success", "message": "Password changed successfully."}


@router.get("/public-key")
async def get_offline_qr_public_key():
    """
    Public Key Distribution for Offline Cryptographic QR Verification.
    Returns ECDSA-P256 public key in PEM and JWK format for browser Web Crypto API.
    """
    from app.services.crypto_qr_service import crypto_qr_service
    return {
        "status": "active",
        "algorithm": "ECDSA-SHA256 (SECP256R1)",
        "jwk": crypto_qr_service.get_public_key_jwk(),
        "pem": crypto_qr_service.get_public_key_pem()
    }

