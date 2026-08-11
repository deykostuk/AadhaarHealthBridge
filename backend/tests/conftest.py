import sys
import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Ensure the backend directory is in the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from app.database import Base, get_db

TEST_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope='function', autouse=True)
def reset_rate_limiter():
    from app.middleware.rate_limiter import limiter
    limiter.storage.clear()
    yield
    limiter.storage.clear()

@pytest.fixture(scope='function')
def db():
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope='function')
def app(db):
    app_instance = create_app()
    
    def override_get_db():
        try:
            yield db
        finally:
            pass
            
    app_instance.dependency_overrides[get_db] = override_get_db
    return app_instance

@pytest.fixture(scope='function')
def client(app):
    return TestClient(app, follow_redirects=False)

@pytest.fixture(scope='function')
def auth_headers(client, db):
    from app.models.patient import User, VaultProfile, VaultAccess
    from app.services.password_service import password_service
    import jwt
    import datetime
    from config import settings

    user = User(
        username="test_auth_user",
        password_hash=password_service.hash_password("password123"),
        role="family_member"
    )
    db.add(user)
    db.commit()

    vault = VaultProfile(owner_user_id=user.id, relation="Self", full_name="Test User")
    db.add(vault)
    db.commit()

    db.add(VaultAccess(user_id=user.id, vault_id=vault.id, access_type="owner"))
    db.commit()

    payload = {
        "sub": str(user.id),
        "user_id": user.id,
        "username": user.username,
        "role": user.role,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=1)
    }
    token = jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}

