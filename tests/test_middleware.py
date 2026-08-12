import jwt
import asyncio
import datetime
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from app.middleware.auth import get_current_user_from_token
from app.models.patient import User
from config import settings

def run_async(coro):
    return asyncio.run(coro)

def test_token_required_missing_header(db):
    with pytest.raises(HTTPException) as exc_info:
        run_async(get_current_user_from_token(token=None, db=db))
    assert exc_info.value.status_code == 401
    assert "Missing Bearer token" in exc_info.value.detail["message"]

def test_token_required_success(db):
    user = User(username="auth_user", password_hash="hashed")
    db.add(user)
    db.commit()
    
    payload = {
        "user_id": user.id,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=1)
    }
    token = jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")
    
    current_user = run_async(get_current_user_from_token(token=token, db=db))
    assert current_user.username == "auth_user"

def test_token_required_invalid_token(db):
    with pytest.raises(HTTPException) as exc_info:
        run_async(get_current_user_from_token(token="invalid_token_value", db=db))
    assert exc_info.value.status_code == 401
    assert "Invalid authentication token" in exc_info.value.detail["message"]

def test_token_required_expired_token(db):
    user = User(username="auth_user_expired", password_hash="hashed")
    db.add(user)
    db.commit()
    
    payload = {
        "user_id": user.id,
        "exp": datetime.datetime.utcnow() - datetime.timedelta(seconds=10)
    }
    token = jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")
    
    with pytest.raises(HTTPException) as exc_info:
        run_async(get_current_user_from_token(token=token, db=db))
    assert exc_info.value.status_code == 401
    assert "Token has expired" in exc_info.value.detail["message"]

def test_token_required_user_not_found(db):
    payload = {
        "user_id": 9999,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=1)
    }
    token = jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")
    
    with pytest.raises(HTTPException) as exc_info:
        run_async(get_current_user_from_token(token=token, db=db))
    assert exc_info.value.status_code == 401
    assert "User not found" in exc_info.value.detail["message"]
