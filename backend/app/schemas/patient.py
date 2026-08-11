from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Any, Dict
from datetime import datetime

# --- Auth & OAuth 2.0 / OIDC Schemas ---
class UserBase(BaseModel):
    username: str

class UserCreate(UserBase):
    password: str

class LoginRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    username: str

class OAuthTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 86400
    refresh_token: Optional[str] = None
    id_token: Optional[str] = None
    scope: str = "openid profile health_records"

class RefreshTokenRequest(BaseModel):
    refresh_token: str

class OIDCDiscoveryResponse(BaseModel):
    issuer: str
    authorization_endpoint: str
    token_endpoint: str
    userinfo_endpoint: str
    jwks_uri: str
    response_types_supported: List[str]
    subject_types_supported: List[str]
    id_token_signing_alg_values_supported: List[str]
    scopes_supported: List[str]
    token_endpoint_auth_methods_supported: List[str]
    claims_supported: List[str]

class OIDCUserInfoResponse(BaseModel):
    sub: str
    name: str
    preferred_username: str
    role: str
    vault_id: Optional[int] = None
    updated_at: Optional[str] = None

class JWKKey(BaseModel):
    kty: str
    alg: str
    use: str
    kid: str
    n: Optional[str] = None
    e: Optional[str] = None

class JWKSResponse(BaseModel):
    keys: List[JWKKey]

class UserOut(UserBase):
    id: int
    role: str
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# --- Vault Schemas ---
class VaultProfileBase(BaseModel):
    full_name: str
    relation: str
    blood_group: Optional[str] = None
    allergies: Optional[str] = None
    medical_conditions: Optional[str] = None
    medications: Optional[str] = None
    personal_contact: Optional[str] = None
    emergency_1_name: Optional[str] = None
    emergency_1_relation: Optional[str] = None
    emergency_1_phone: Optional[str] = None
    emergency_2_name: Optional[str] = None
    emergency_2_relation: Optional[str] = None
    emergency_2_phone: Optional[str] = None
    emergency_3_name: Optional[str] = None
    emergency_3_relation: Optional[str] = None
    emergency_3_phone: Optional[str] = None

class VaultUpdateRequest(BaseModel):
    full_name: Optional[str] = None
    blood_group: Optional[str] = None
    allergies: Optional[str] = None
    medical_conditions: Optional[str] = None
    medications: Optional[str] = None
    personal_contact: Optional[str] = None
    emergency_1_name: Optional[str] = None
    emergency_1_relation: Optional[str] = None
    emergency_1_phone: Optional[str] = None
    emergency_2_name: Optional[str] = None
    emergency_2_relation: Optional[str] = None
    emergency_2_phone: Optional[str] = None
    emergency_3_name: Optional[str] = None
    emergency_3_relation: Optional[str] = None
    emergency_3_phone: Optional[str] = None

class FamilyMemberCreateRequest(VaultProfileBase):
    username: str
    password: str

class VaultListItemOut(BaseModel):
    id: int
    relation: str
    full_name: str
    blood_group: Optional[str] = None
    allergies: Optional[str] = None
    qr_token: str
    owner_user_id: int
    access_type: str

class VaultDetailOut(VaultProfileBase):
    id: int
    owner_user_id: int
    qr_token: str
    is_emergency_ready: bool
    created_at: Optional[datetime] = None
    health_snapshot: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# --- Document Schemas ---
class DocumentOut(BaseModel):
    id: int
    vault_id: int
    file_name: Optional[str] = None
    file_path: str
    category: Optional[str] = None
    upload_date: Optional[datetime] = None
    is_encrypted: Optional[bool] = False
    ocr_text: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# --- Health Metric Schemas ---
class HealthMetricOut(BaseModel):
    metric_name: str
    metric_value: Any
    metric_unit: Optional[str] = ""
    observed_date: Optional[str] = None
    source_document_id: Optional[int] = None

class HealthSnapshotResponse(BaseModel):
    vault_id: int
    health_snapshot: Dict[str, Any] = {}
    latest_metrics: List[HealthMetricOut] = []


# --- QR Scan Schemas ---
class QRScanLogOut(BaseModel):
    id: int
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    location_data: Optional[str] = None
    timestamp: Optional[datetime] = None


# --- Chat Schemas ---
class ChatQueryRequest(BaseModel):
    query: str
    document_id: Optional[int] = None
    context: Optional[str] = None
    sources: Optional[List[Dict[str, Any]]] = None

class ChatSourceOut(BaseModel):
    doc_id: Optional[int] = None
    file_name: Optional[str] = None
    excerpt: Optional[str] = None

class ChatQueryResponse(BaseModel):
    answer: str
    sources: List[ChatSourceOut] = []
    ai_source: Optional[str] = ""
    metric_response: Optional[Dict[str, Any]] = None


# --- Status Schemas ---
class HealthStatusResponse(BaseModel):
    status: str
    service: str
    version: str
    timestamp: str

class ApiResponse(BaseModel):
    status: str = "success"
    message: str
