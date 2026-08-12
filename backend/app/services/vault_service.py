import datetime
from datetime import timedelta, timezone
import json
import urllib.request
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.orm import Session

from app.models.patient import User, VaultProfile, VaultAccess, QRScanLog, HealthMetric, Document
from app.services.password_service import password_service
from config import settings

class VaultService:
    """Modular service handling medical vault management, family members, and QR scan tracking."""

    def __init__(self, db: Session):
        self.db = db

    def get_user_vaults(self, user_id: int) -> List[Dict[str, Any]]:
        """Returns all vaults accessible to the user (owned or shared caregiver access) via a single JOIN query."""
        results = self.db.query(VaultProfile, VaultAccess.access_type).join(
            VaultAccess, VaultAccess.vault_id == VaultProfile.id
        ).filter(VaultAccess.user_id == user_id).all()

        vaults = []
        for vault, access_type in results:
            vaults.append({
                "id": vault.id,
                "relation": vault.relation,
                "full_name": vault.full_name,
                "blood_group": vault.blood_group,
                "allergies": vault.allergies,
                "qr_token": vault.qr_token,
                "owner_user_id": vault.owner_user_id,
                "access_type": access_type
            })
        return vaults

    def get_vault_by_id_and_user(self, vault_id: int, user_id: int) -> Tuple[Optional[VaultProfile], Optional[str]]:
        """Verifies access and returns vault profile with access type."""
        access = self.db.query(VaultAccess).filter(
            VaultAccess.user_id == user_id,
            VaultAccess.vault_id == vault_id
        ).first()
        if not access:
            return None, None

        vault = self.db.query(VaultProfile).filter(VaultProfile.id == vault_id).first()
        return vault, access.access_type

    def create_family_member_vault(
        self,
        current_user_id: int,
        form_data: Dict[str, Any]
    ) -> Tuple[Optional[VaultProfile], Optional[str]]:
        """Creates a family member account, their dedicated vault profile, and caregiver access."""
        username = form_data.get("username", "").strip()
        password = form_data.get("password", "")

        if not username or not password:
            return None, "Username and password required for family member."

        if self.db.query(User).filter(User.username == username).first():
            return None, "Username for the family member already exists."

        parent_user = User(
            username=username,
            password_hash=password_service.hash_password(password),
            role="family_member"
        )
        self.db.add(parent_user)
        self.db.flush()

        vault = VaultProfile(
            owner_user_id=parent_user.id,
            relation=form_data.get("relation", "Family Member"),
            full_name=form_data.get("full_name", username),
            blood_group=form_data.get("blood_group"),
            allergies=form_data.get("allergies"),
            personal_contact=form_data.get("personal_contact"),
            emergency_1_name=form_data.get("emergency_1_name"),
            emergency_1_relation=form_data.get("emergency_1_relation"),
            emergency_1_phone=form_data.get("emergency_1_phone"),
            emergency_2_name=form_data.get("emergency_2_name"),
            emergency_2_relation=form_data.get("emergency_2_relation"),
            emergency_2_phone=form_data.get("emergency_2_phone"),
            emergency_3_name=form_data.get("emergency_3_name"),
            emergency_3_relation=form_data.get("emergency_3_relation"),
            emergency_3_phone=form_data.get("emergency_3_phone"),
            is_emergency_ready=bool(form_data.get("is_emergency_ready", False))
        )
        self.db.add(vault)
        self.db.flush()

        self.db.add(VaultAccess(user_id=parent_user.id, vault_id=vault.id, access_type="owner"))
        self.db.add(VaultAccess(user_id=current_user_id, vault_id=vault.id, access_type="caregiver"))
        self.db.commit()

        return vault, None

    def update_vault_profile(self, vault_id: int, user_id: int, form_data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Updates clinical and emergency contact fields on a vault with strict RBAC."""
        access = self.db.query(VaultAccess).filter(
            VaultAccess.user_id == user_id,
            VaultAccess.vault_id == vault_id
        ).first()
        if not access:
            return False, "Unauthorized access."

        if access.access_type not in ["owner", "caregiver"]:
            return False, f"Unauthorized: Access type '{access.access_type}' cannot modify vault profile."

        vault = self.db.query(VaultProfile).filter(VaultProfile.id == vault_id).first()
        if not vault:
            return False, "Vault not found."

        vault.full_name = form_data.get("full_name", vault.full_name)
        vault.blood_group = form_data.get("blood_group", vault.blood_group)
        vault.allergies = form_data.get("allergies", vault.allergies)
        vault.medical_conditions = form_data.get("medical_conditions", vault.medical_conditions)
        vault.medications = form_data.get("medications", vault.medications)
        vault.personal_contact = form_data.get("personal_contact", vault.personal_contact)

        vault.emergency_1_name = form_data.get("emergency_1_name", vault.emergency_1_name)
        vault.emergency_1_relation = form_data.get("emergency_1_relation", vault.emergency_1_relation)
        vault.emergency_1_phone = form_data.get("emergency_1_phone", vault.emergency_1_phone)
        vault.emergency_2_name = form_data.get("emergency_2_name", vault.emergency_2_name)
        vault.emergency_2_relation = form_data.get("emergency_2_relation", vault.emergency_2_relation)
        vault.emergency_2_phone = form_data.get("emergency_2_phone", vault.emergency_2_phone)
        vault.emergency_3_name = form_data.get("emergency_3_name", vault.emergency_3_name)
        vault.emergency_3_relation = form_data.get("emergency_3_relation", vault.emergency_3_relation)
        vault.emergency_3_phone = form_data.get("emergency_3_phone", vault.emergency_3_phone)

        if "is_emergency_ready" in form_data and form_data["is_emergency_ready"] is not None:
            vault.is_emergency_ready = bool(form_data["is_emergency_ready"])

        self.db.commit()
        return True, None

    def log_qr_scan(self, token: str, ip: str, user_agent: Optional[str]) -> Tuple[Optional[VaultProfile], str]:
        """Resolves patient by QR token, resolves scanner location, and logs scan entry."""
        vault = self.db.query(VaultProfile).filter(VaultProfile.qr_token == token).first()
        if not vault:
            return None, "Unknown Location"

        location = self.resolve_ip_location(ip)

        new_log = QRScanLog(
            vault_id=vault.id,
            ip_address=ip,
            user_agent=user_agent,
            location_data=location,
            timestamp=datetime.datetime.now(timezone.utc).replace(tzinfo=None)
        )
        self.db.add(new_log)
        self.db.commit()

        return vault, location

    def get_recent_scan_logs(self, vault_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """Retrieves and formats recent scan audit logs with IST timestamps."""
        scan_logs = self.db.query(QRScanLog).filter(
            QRScanLog.vault_id == vault_id
        ).order_by(QRScanLog.timestamp.desc()).limit(limit).all()

        formatted_logs = []
        for log in scan_logs:
            ist_time = log.timestamp + timedelta(hours=5, minutes=30)
            formatted_logs.append({
                "id": log.id,
                "ip_address": log.ip_address,
                "user_agent": log.user_agent,
                "location_data": log.location_data,
                "timestamp": ist_time
            })
        return formatted_logs

    @staticmethod
    def resolve_ip_location(ip: Optional[str]) -> str:
        """Resolves Geo-IP location using external API with local IP fallback."""
        if not ip or ip in ["127.0.0.1", "localhost", "::1"] or ip.startswith("192.168.") or ip.startswith("10.") or ip.startswith("172.16."):
            return "Kanpur, Uttar Pradesh (Local Host)"

        import re
        # Validate that IP contains only valid IPv4/IPv6 characters
        clean_ip = re.sub(r"[^0-9a-fA-F:\.]", "", ip.strip())
        if not clean_ip:
            return "Unknown Location"

        try:
            url = f"https://ip-api.com/json/{clean_ip}"
            req = urllib.request.Request(url, headers={'User-Agent': 'AadhaarHealthBridge/1.0'})
            with urllib.request.urlopen(req, timeout=3) as response:  # nosec B310
                data = json.loads(response.read().decode())
                if data.get("status") == "success":
                    city = data.get("city", "")
                    region = data.get("regionName", "")
                    country = data.get("country", "")
                    if city and region:
                        return f"{city}, {region}"
                    elif city:
                        return f"{city}, {country}"
                    return country or "Unknown Location"
        except Exception:
            pass

        return "Unknown Location"

    @staticmethod
    def parse_user_agent(ua: Optional[str]) -> Tuple[str, str]:
        """Classifies client device and browser from User-Agent string."""
        if not ua:
            return "Unknown Device", "Unknown Browser"

        ua_lower = ua.lower()

        if "iphone" in ua_lower:
            device = "iPhone"
        elif "android" in ua_lower:
            device = "Android Phone" if "mobile" in ua_lower else "Android Tablet"
        elif "ipad" in ua_lower:
            device = "iPad"
        elif "windows" in ua_lower:
            device = "Windows PC"
        elif "macintosh" in ua_lower or "mac os x" in ua_lower:
            device = "MacBook / macOS"
        elif "linux" in ua_lower:
            device = "Linux OS"
        else:
            device = "Generic Device"

        if "edg/" in ua_lower or "edge" in ua_lower:
            browser = "Microsoft Edge"
        elif "chrome" in ua_lower or "crios" in ua_lower:
            browser = "Google Chrome"
        elif "firefox" in ua_lower or "fxios" in ua_lower:
            browser = "Mozilla Firefox"
        elif "safari" in ua_lower and "chrome" not in ua_lower:
            browser = "Apple Safari"
        else:
            browser = "Web Browser"

        return device, browser
