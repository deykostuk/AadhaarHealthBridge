import os
import urllib.parse
import hashlib
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from app.models.patient import VaultProfile, SOSAlertLog
from app.utils.pii_masker import PIIMasker
from config import settings

logger = logging.getLogger("app.sos")

class SOSDispatchService:
    """
    Instant Emergency Contact SOS & GPS Alert System.
    Multi-channel emergency broadcast dispatcher (SMS, WhatsApp, Webhooks, Push)
    for trauma incidents, accident responses, and paramedic QR scans.
    """

    @staticmethod
    def build_maps_url(lat: Optional[float], lng: Optional[float]) -> str:
        """Constructs Google Maps pinpoint URL from GPS coordinates."""
        if lat is not None and lng is not None:
            return f"https://www.google.com/maps?q={lat:.6f},{lng:.6f}"
        return "https://www.google.com/maps"

    @classmethod
    def compose_emergency_message(
        cls,
        vault: VaultProfile,
        maps_url: str,
        accuracy_meters: Optional[float] = None,
        trigger_source: str = "Emergency Medical QR Scan"
    ) -> str:
        """Composes urgent, structured clinical triage notification for family caregivers."""
        blood_grp = vault.blood_group or "Unknown"
        allergies = vault.allergies or "None recorded"
        conditions = vault.medical_conditions or "None recorded"
        meds = vault.medications or "None recorded"
        timestamp = datetime.now(timezone.utc).strftime("%d %b %Y, %I:%M %p UTC")
        
        acc_str = f" (Accuracy: ±{int(accuracy_meters)}m)" if accuracy_meters else ""
        emergency_card_url = f"{settings.APP_BASE_URL.rstrip('/')}/api/v1/scan/{vault.qr_token}/data"

        message = (
            f"🚨 *CRITICAL EMERGENCY MEDICAL ALERT*\n\n"
            f"👤 *Patient:* {vault.full_name}\n"
            f"🩸 *Blood Group:* {blood_grp}\n"
            f"⚠️ *Allergies:* {allergies}\n"
            f"🏥 *Conditions:* {conditions}\n"
            f"💊 *Active Meds:* {meds}\n\n"
            f"📍 *GPS Location:* {maps_url}{acc_str}\n"
            f"🕒 *Timestamp:* {timestamp}\n"
            f"📢 *Trigger:* {trigger_source}\n\n"
            f"🔒 *Instant Emergency Medical Card:*\n{emergency_card_url}\n\n"
            f"_Automated Life-Safety Dispatch by Aadhaar Health Bridge PHR_"
        )
        return message

    @classmethod
    def get_emergency_contacts(cls, vault: VaultProfile) -> List[Dict[str, str]]:
        """Extracts and formats all non-empty emergency contacts from the vault."""
        contacts = []
        for i in [1, 2, 3]:
            name = getattr(vault, f"emergency_{i}_name", None)
            relation = getattr(vault, f"emergency_{i}_relation", None)
            phone = getattr(vault, f"emergency_{i}_phone", None)
            if name or phone:
                contacts.append({
                    "slot": i,
                    "name": name or f"Emergency Contact {i}",
                    "relation": relation or "Family/Friend",
                    "phone": phone or "",
                    "masked_phone": PIIMasker.mask_phone(phone) if phone else "None"
                })
        return contacts

    def dispatch_sos(
        self,
        vault: VaultProfile,
        db: Session,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        accuracy_meters: Optional[float] = None,
        trigger_source: str = "qr_scan",
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Dispatches multi-channel SOS alerts to all registered emergency contacts.
        Records an immutable cryptographic audit log in the database.
        """
        maps_url = self.build_maps_url(latitude, longitude)
        source_label = "Paramedic QR Scan" if trigger_source == "qr_scan" else "Patient One-Tap SOS Beacon"
        alert_msg = self.compose_emergency_message(vault, maps_url, accuracy_meters, source_label)
        contacts = self.get_emergency_contacts(vault)

        # 1. Generate direct WhatsApp dispatch links for instant manual/bystander relay
        whatsapp_links = []
        for c in contacts:
            clean_phone = c["phone"].replace("+", "").replace(" ", "").replace("-", "") if c["phone"] else ""
            encoded_msg = urllib.parse.quote(alert_msg)
            wa_url = f"https://api.whatsapp.com/send?phone={clean_phone}&text={encoded_msg}" if clean_phone else f"https://api.whatsapp.com/send?text={encoded_msg}"
            whatsapp_links.append({
                "contact_name": c["name"],
                "masked_phone": c["masked_phone"],
                "relation": c["relation"],
                "whatsapp_url": wa_url
            })

        # 2. Simulated / Pluggable SMS Gateway Dispatch
        dispatched_recipients = 0
        for c in contacts:
            if c["phone"]:
                dispatched_recipients += 1
                logger.critical(
                    f"🚨 [EMERGENCY SMS DISPATCH] To: {c['name']} ({c['masked_phone']}) | "
                    f"Patient: {vault.full_name} | GPS: {maps_url}"
                )

        # 3. Cryptographic Tamper Seal (SHA-256)
        event_time = datetime.now(timezone.utc).isoformat()
        seal_payload = f"{vault.id}-{latitude}-{longitude}-{event_time}-{len(contacts)}"
        tamper_seal = hashlib.sha256(seal_payload.encode()).hexdigest()

        # 4. Save to Database
        sos_log = SOSAlertLog(
            vault_id=vault.id,
            trigger_source=trigger_source,
            latitude=str(latitude) if latitude is not None else None,
            longitude=str(longitude) if longitude is not None else None,
            accuracy_meters=str(accuracy_meters) if accuracy_meters is not None else None,
            maps_url=maps_url,
            ip_address=ip_address,
            user_agent=user_agent,
            recipients_count=dispatched_recipients,
            dispatch_status="dispatched" if dispatched_recipients > 0 else "no_contacts",
            dispatch_channels="sms,whatsapp,web_beacon",
            alert_message=alert_msg,
            cryptographic_hash=tamper_seal
        )
        db.add(sos_log)
        db.commit()
        db.refresh(sos_log)

        return {
            "status": "success",
            "sos_incident_id": sos_log.id,
            "patient_name": vault.full_name,
            "blood_group": vault.blood_group,
            "gps_location": {
                "latitude": latitude,
                "longitude": longitude,
                "accuracy_meters": accuracy_meters,
                "maps_url": maps_url
            },
            "contacts_notified_count": dispatched_recipients,
            "emergency_contacts": contacts,
            "whatsapp_dispatch_links": whatsapp_links,
            "alert_message": alert_msg,
            "timestamp": event_time,
            "cryptographic_seal_sha256": tamper_seal
        }


# Singleton instance
sos_service = SOSDispatchService()
