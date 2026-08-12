from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import Optional, List, Any, Dict
from datetime import datetime
from app.utils.sanitizer import InputSanitizer

# --- Base Strict Input Model (Defends against Mass Assignment OWASP API3:2023) ---
class StrictInputModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


# --- Auth & OAuth 2.0 / OIDC Schemas ---
class UserBase(StrictInputModel):
    username: str

    @field_validator("username", mode="before")
    @classmethod
    def validate_username(cls, v):
        return InputSanitizer.sanitize_username(v)


class UserCreate(UserBase):
    password: str = Field(..., description="Account master password (minimum 6 characters)", examples=["SecurePassword123!"])

    @field_validator("password", mode="before")
    @classmethod
    def validate_password(cls, v):
        if not v or len(str(v)) < 6:
            raise ValueError("Password must be at least 6 characters long.")
        # Strip null bytes
        return str(v).replace("\x00", "")

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        json_schema_extra={
            "example": {
                "username": "kostuk",
                "password": "SecurePassword123!"
            }
        }
    )


class LoginRequest(StrictInputModel):
    username: str = Field(..., description="Registered username or ABHA ID", examples=["kostuk"])
    password: str = Field(..., description="Account master password", examples=["SecurePassword123!"])

    @field_validator("username", mode="before")
    @classmethod
    def validate_username(cls, v):
        return InputSanitizer.sanitize_username(v)

    @field_validator("password", mode="before")
    @classmethod
    def validate_password(cls, v):
        if not v:
            raise ValueError("Password cannot be empty.")
        return str(v).replace("\x00", "")

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        json_schema_extra={
            "example": {
                "username": "kostuk",
                "password": "SecurePassword123!"
            }
        }
    )


class ChangePasswordRequest(StrictInputModel):
    old_password: str = Field(..., description="Current password for verification", examples=["OldPassword123!"])
    new_password: str = Field(..., description="New replacement password (min 6 chars)", examples=["NewSecurePassword123!"])

    @field_validator("old_password", "new_password", mode="before")
    @classmethod
    def validate_password_field(cls, v):
        if not v or len(str(v)) < 6:
            raise ValueError("Password must be at least 6 characters long.")
        return str(v).replace("\x00", "")

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        json_schema_extra={
            "example": {
                "old_password": "OldPassword123!",
                "new_password": "NewSecurePassword123!"
            }
        }
    )


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


class RefreshTokenRequest(StrictInputModel):
    refresh_token: str

    @field_validator("refresh_token", mode="before")
    @classmethod
    def validate_refresh_token(cls, v):
        if not v or not isinstance(v, str):
            raise ValueError("Invalid refresh token.")
        return v.strip().replace("\x00", "")


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


class UserOut(BaseModel):
    id: int
    username: str
    role: str
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# --- Vault Schemas ---
class VaultProfileBase(StrictInputModel):
    full_name: str
    relation: str
    blood_group: Optional[str] = None
    allergies: Optional[str] = None
    medical_conditions: Optional[str] = None
    medications: Optional[str] = None
    personal_contact: Optional[str] = None
    address: Optional[str] = None
    emergency_1_name: Optional[str] = None
    emergency_1_relation: Optional[str] = None
    emergency_1_phone: Optional[str] = None
    emergency_2_name: Optional[str] = None
    emergency_2_relation: Optional[str] = None
    emergency_2_phone: Optional[str] = None
    emergency_3_name: Optional[str] = None
    emergency_3_relation: Optional[str] = None
    emergency_3_phone: Optional[str] = None

    @field_validator("full_name", "relation", "allergies", "medical_conditions", "medications", "address",
                     "emergency_1_name", "emergency_1_relation", "emergency_2_name", "emergency_2_relation",
                     "emergency_3_name", "emergency_3_relation", mode="before")
    @classmethod
    def sanitize_text_fields(cls, v):
        return InputSanitizer.sanitize_text(v, max_length=500)

    @field_validator("blood_group", mode="before")
    @classmethod
    def validate_blood_group(cls, v):
        return InputSanitizer.sanitize_blood_group(v)

    @field_validator("personal_contact", "emergency_1_phone", "emergency_2_phone", "emergency_3_phone", mode="before")
    @classmethod
    def validate_phone_fields(cls, v):
        return InputSanitizer.sanitize_phone(v)


class VaultUpdateRequest(StrictInputModel):
    full_name: Optional[str] = Field(None, description="Patient's legal full name", examples=["Kostuk Dey"])
    blood_group: Optional[str] = Field(None, description="ABO/Rh Blood Group (e.g. B+, O-, AB+)", examples=["B+"])
    allergies: Optional[str] = Field(None, description="Known drug and environmental allergies", examples=["Peanuts, Penicillin"])
    medical_conditions: Optional[str] = Field(None, description="Chronic or acute medical history", examples=["Type 2 Diabetes, Hypertension"])
    medications: Optional[str] = Field(None, description="Active prescriptions and dosage instructions", examples=["Metformin 500mg daily"])
    personal_contact: Optional[str] = Field(None, description="Patient primary phone number", examples=["+918604530535"])
    address: Optional[str] = Field(None, description="Residential residential address", examples=["123 Civil Lines, Kanpur, UP"])
    emergency_1_name: Optional[str] = Field(None, examples=["Rajesh Dey"])
    emergency_1_relation: Optional[str] = Field(None, examples=["Father"])
    emergency_1_phone: Optional[str] = Field(None, examples=["+919876543210"])
    emergency_2_name: Optional[str] = Field(None, examples=["Sunita Dey"])
    emergency_2_relation: Optional[str] = Field(None, examples=["Mother"])
    emergency_2_phone: Optional[str] = Field(None, examples=["+919876543211"])
    emergency_3_name: Optional[str] = Field(None, examples=["Amit Verma"])
    emergency_3_relation: Optional[str] = Field(None, examples=["Friend"])
    emergency_3_phone: Optional[str] = Field(None, examples=["+919876543212"])
    is_emergency_ready: Optional[bool] = Field(None, description="Ready status for emergency QR retrieval", examples=[True])

    @field_validator("full_name", "allergies", "medical_conditions", "medications", "address",
                     "emergency_1_name", "emergency_1_relation", "emergency_2_name", "emergency_2_relation",
                     "emergency_3_name", "emergency_3_relation", mode="before")
    @classmethod
    def sanitize_text_fields(cls, v):
        return InputSanitizer.sanitize_text(v, max_length=500)

    @field_validator("blood_group", mode="before")
    @classmethod
    def validate_blood_group(cls, v):
        return InputSanitizer.sanitize_blood_group(v)

    @field_validator("personal_contact", "emergency_1_phone", "emergency_2_phone", "emergency_3_phone", mode="before")
    @classmethod
    def validate_phone_fields(cls, v):
        return InputSanitizer.sanitize_phone(v)

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        json_schema_extra={
            "example": {
                "full_name": "Kostuk Dey",
                "blood_group": "B+",
                "allergies": "Peanuts, Penicillin",
                "medical_conditions": "Hypertension",
                "medications": "Telmisartan 40mg",
                "personal_contact": "+918604530535",
                "address": "123 Civil Lines, Kanpur, UP",
                "emergency_1_name": "Rajesh Dey",
                "emergency_1_relation": "Father",
                "emergency_1_phone": "+919876543210",
                "is_emergency_ready": True
            }
        }
    )


class FamilyMemberCreateRequest(VaultProfileBase):
    username: str = Field(..., description="Unique login handle for family caregiver", examples=["mother_user"])
    password: str = Field(..., description="Caregiver account password", examples=["SecureMember123!"])
    is_emergency_ready: Optional[bool] = Field(False, description="Emergency QR enabled status")

    @field_validator("username", mode="before")
    @classmethod
    def validate_member_username(cls, v):
        return InputSanitizer.sanitize_username(v)

    @field_validator("password", mode="before")
    @classmethod
    def validate_member_password(cls, v):
        if not v or len(str(v)) < 6:
            raise ValueError("Password must be at least 6 characters long.")
        return str(v).replace("\x00", "")

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        json_schema_extra={
            "example": {
                "full_name": "Sunita Dey",
                "relation": "Mother",
                "username": "sunita_dey",
                "password": "SecureMember123!",
                "blood_group": "O+",
                "allergies": "None",
                "medical_conditions": "Mild Arthritis",
                "is_emergency_ready": True
            }
        }
    )

class VaultListItemOut(BaseModel):
    id: int
    relation: str
    full_name: str
    blood_group: Optional[str] = None
    allergies: Optional[str] = None
    qr_token: str
    owner_user_id: int
    access_type: str

    model_config = ConfigDict(from_attributes=True)


class VaultDetailOut(BaseModel):
    id: int
    full_name: str
    relation: str
    blood_group: Optional[str] = None
    allergies: Optional[str] = None
    medical_conditions: Optional[str] = None
    medications: Optional[str] = None
    personal_contact: Optional[str] = None
    address: Optional[str] = None
    emergency_1_name: Optional[str] = None
    emergency_1_relation: Optional[str] = None
    emergency_1_phone: Optional[str] = None
    emergency_2_name: Optional[str] = None
    emergency_2_relation: Optional[str] = None
    emergency_2_phone: Optional[str] = None
    emergency_3_name: Optional[str] = None
    emergency_3_relation: Optional[str] = None
    emergency_3_phone: Optional[str] = None
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
class ChatQueryRequest(StrictInputModel):
    query: str = Field(..., description="Natural language medical or clinical inquiry", examples=["What were my latest blood sugar and creatinine readings?"])
    document_id: Optional[int] = Field(None, description="Optional target report document ID to constrain query context", examples=[1])
    context: Optional[str] = Field(None, description="Optional supplemental patient health notes")
    sources: Optional[List[Dict[str, Any]]] = Field(None, description="Optional pre-filtered retrieval sources")

    @field_validator("query", mode="before")
    @classmethod
    def sanitize_query(cls, v):
        if not v or not str(v).strip():
            raise ValueError("Query cannot be empty.")
        return InputSanitizer.sanitize_text(str(v), max_length=2000)

    @field_validator("context", mode="before")
    @classmethod
    def sanitize_context(cls, v):
        return InputSanitizer.sanitize_text(v, max_length=5000) if v else None

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        json_schema_extra={
            "example": {
                "query": "What were my latest blood sugar and creatinine readings?",
                "document_id": 1
            }
        }
    )


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
