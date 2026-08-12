import os
import json
import zlib
import base64
import time
from typing import Dict, Any, Tuple, Optional
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.backends import default_backend
from cryptography.exceptions import InvalidSignature

from app.models.patient import VaultProfile
from config import settings


class CryptoQRService:
    """
    ECDSA-P256 Asymmetric Cryptographic Offline QR Engine.
    Generates ultra-compact, tamper-proof, digitally signed emergency passes
    that can be verified 100% offline in rural/zero-connectivity environments.
    """

    def __init__(self):
        self._private_key, self._public_key = self._initialize_key_pair()

    def _initialize_key_pair(self) -> Tuple[ec.EllipticCurvePrivateKey, ec.EllipticCurvePublicKey]:
        """Derives a deterministic, high-entropy ECDSA-P256 key pair from application secret key."""
        seed = settings.SECRET_KEY.encode()
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b"ahb-crypto-qr-offline-seed-v1",
            info=b"ecdsa-secp256r1-offline-qr-signing",
            backend=default_backend()
        )
        derived_scalar_bytes = hkdf.derive(seed)
        
        # Derive private key scalar
        private_value = int.from_bytes(derived_scalar_bytes, byteorder="big")
        # Standard SECP256R1 / P-256 curve order
        curve_order = 0xFFFFFFFF00000000FFFFFFFFFFFFFFFFBCE6FAADA7179E84F3B9CAC2FC632551
        private_value = (private_value % (curve_order - 1)) + 1

        private_key = ec.derive_private_key(private_value, ec.SECP256R1(), default_backend())
        public_key = private_key.public_key()
        return private_key, public_key

    def get_public_key_pem(self) -> str:
        """Exports public key in PEM format."""
        return self._public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode("utf-8")

    def get_public_key_jwk(self) -> Dict[str, Any]:
        """Exports public key in JSON Web Key (JWK) format for in-browser Web Crypto API."""
        public_numbers = self._public_key.public_numbers()
        x_bytes = public_numbers.x.to_bytes(32, byteorder="big")
        y_bytes = public_numbers.y.to_bytes(32, byteorder="big")

        def b64url(b: bytes) -> str:
            return base64.urlsafe_b64encode(b).decode("utf-8").rstrip("=")

        return {
            "kty": "EC",
            "crv": "P-256",
            "x": b64url(x_bytes),
            "y": b64url(y_bytes),
            "use": "sig",
            "alg": "ES256",
            "kid": "ahb-offline-qr-v1"
        }

    def generate_signed_qr_payload(self, vault: VaultProfile, valid_duration_days: int = 365) -> str:
        """
        Creates a compact, zlib-compressed, ECDSA-P256 signed emergency payload string:
        Format: AHB1.<compressed_payload_b64>.<signature_b64>
        """
        now = int(time.time())
        exp = now + (valid_duration_days * 86400)

        # 1. Compact clinical payload
        compact_data = {
            "v": 1,
            "id": vault.id,
            "token": vault.qr_token,
            "name": vault.full_name,
            "bg": vault.blood_group or "Unknown",
            "alg": vault.allergies or "None",
            "cnd": vault.medical_conditions or "None",
            "med": vault.medications or "None",
            "c1_name": vault.emergency_1_name or "",
            "c1_rel": vault.emergency_1_relation or "",
            "c1_ph": vault.emergency_1_phone or "",
            "c2_name": vault.emergency_2_name or "",
            "c2_rel": vault.emergency_2_relation or "",
            "c2_ph": vault.emergency_2_phone or "",
            "iat": now,
            "exp": exp
        }

        # 2. JSON + Zlib Compression + Base64-URL
        raw_json = json.dumps(compact_data, separators=(",", ":")).encode("utf-8")
        compressed_bytes = zlib.compress(raw_json, level=9)
        payload_b64 = base64.urlsafe_b64encode(compressed_bytes).decode("utf-8").rstrip("=")

        # 3. ECDSA-P256 Signing
        signature_der = self._private_key.sign(
            payload_b64.encode("utf-8"),
            ec.ECDSA(hashes.SHA256())
        )
        sig_b64 = base64.urlsafe_b64encode(signature_der).decode("utf-8").rstrip("=")

        return f"AHB1.{payload_b64}.{sig_b64}"

    def verify_signed_qr_payload(self, raw_qr_string: str) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
        """
        Verifies the digital signature and decompresses the emergency triage payload.
        Returns: (is_valid, decoded_data_dict, error_message)
        """
        try:
            parts = raw_qr_string.strip().split(".")
            if len(parts) != 3 or parts[0] != "AHB1":
                return False, None, "Invalid AHB QR header or format (expected AHB1.<payload>.<sig>)"

            payload_b64 = parts[1]
            sig_b64 = parts[2]

            # Re-pad Base64
            def pad_b64(s: str) -> str:
                return s + "=" * ((4 - len(s) % 4) % 4)

            sig_der = base64.urlsafe_b64decode(pad_b64(sig_b64))

            # 1. Verify ECDSA signature
            self._public_key.verify(
                sig_der,
                payload_b64.encode("utf-8"),
                ec.ECDSA(hashes.SHA256())
            )

            # 2. Decompress and parse JSON payload
            compressed_bytes = base64.urlsafe_b64decode(pad_b64(payload_b64))
            decompressed_json = zlib.decompress(compressed_bytes).decode("utf-8")
            data = json.loads(decompressed_json)

            # 3. Check expiration
            exp = data.get("exp", 0)
            if exp and exp < time.time():
                return True, data, "WARNING: Emergency pass cryptographic certificate has expired."

            return True, data, None

        except InvalidSignature:
            return False, None, "Digital signature verification failed. Tampered or counterfeit QR code."
        except Exception as e:
            return False, None, f"Payload decoding error: {str(e)}"


# Singleton instance
crypto_qr_service = CryptoQRService()
