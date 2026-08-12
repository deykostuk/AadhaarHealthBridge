import pytest
from app.utils.sanitizer import InputSanitizer
from app.schemas.patient import (
    UserCreate,
    LoginRequest,
    VaultProfileBase,
    VaultUpdateRequest,
    ChatQueryRequest
)
from pydantic import ValidationError

def test_sanitizer_xss_neutralization():
    raw_text = "<script>alert('XSS attack')</script>Patient condition normal."
    sanitized = InputSanitizer.sanitize_text(raw_text)
    assert "<script>" not in sanitized
    assert "alert" not in sanitized or "&lt;" in sanitized
    assert "Patient condition normal." in sanitized


def test_sanitizer_null_bytes_and_control_characters():
    raw = "Header\x00Name\x08With\x1fControl"
    clean = InputSanitizer.sanitize_text(raw)
    assert "\x00" not in clean
    assert "\x08" not in clean
    assert clean == "HeaderNameWithControl"


def test_sanitizer_path_traversal_filename():
    unsafe_1 = "../../../etc/passwd"
    unsafe_2 = "..\\..\\windows\\system32\\cmd.exe"
    unsafe_3 = "my_report\x00.pdf"

    assert InputSanitizer.sanitize_filename(unsafe_1) == "passwd"
    assert ".." not in InputSanitizer.sanitize_filename(unsafe_2)
    assert "\x00" not in InputSanitizer.sanitize_filename(unsafe_3)


def test_blood_group_validation():
    assert InputSanitizer.sanitize_blood_group("o+") == "O+"
    assert InputSanitizer.sanitize_blood_group("AB-") == "AB-"
    
    with pytest.raises(ValueError):
        InputSanitizer.sanitize_blood_group("XYZ+")


def test_phone_validation():
    assert InputSanitizer.sanitize_phone("+91 98765 43210") == "+919876543210"
    
    with pytest.raises(ValueError):
        InputSanitizer.sanitize_phone("123-malicious<script>")


def test_pydantic_schema_mass_assignment_defense(client, auth_headers):
    # Attempting to inject extra unauthorized fields on vault update
    res = client.put(
        "/api/v1/vaults/1",
        json={
            "full_name": "Updated Kostuk",
            "is_admin": True,               # Rogue field
            "owner_user_id": 999,           # Rogue field
            "bypass_auth": True             # Rogue field
        },
        headers=auth_headers
    )
    # Must reject with 422 Unprocessable Entity due to extra="forbid"
    assert res.status_code == 422
    data = res.json()
    assert data["status"] == "error"
    assert "Input validation failed" in data["message"]
    error_fields = [e["field"] for e in data["errors"]]
    assert any("is_admin" in f or "owner_user_id" in f for f in error_fields)


def test_pydantic_schema_invalid_blood_group_rejection(client, auth_headers):
    res = client.put(
        "/api/v1/vaults/1",
        json={
            "blood_group": "INVALID_GROUP"
        },
        headers=auth_headers
    )
    assert res.status_code == 422
    data = res.json()
    assert data["status"] == "error"
