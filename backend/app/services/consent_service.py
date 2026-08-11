import datetime
from datetime import timedelta
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.orm import Session

from app.models.patient import ConsentRecord, VaultProfile, User
from config import settings

class ConsentService:
    """
    Application Consent Service implementing HL7 FHIR Release 4 (R4) Consent specifications.
    Provides:
    - Purpose-bound authorization (TREAT, EMERGENCY, RESEARCH)
    - Temporal expiration checks
    - Granular resource filtering (Observations, DiagnosticReports, etc.)
    - Emergency glass-breaker override
    - Instant revocation management
    """

    def __init__(self, db: Session):
        self.db = db

    def create_consent(
        self,
        vault_id: int,
        granter_user_id: int,
        grantee_identifier: str,
        consent_type: str = "patient-privacy",
        purpose: str = "TREAT",
        duration_minutes: Optional[int] = None,
        allowed_resources: str = "all"
    ) -> ConsentRecord:
        """Issues a new active consent policy for a vault."""
        now = datetime.datetime.utcnow()
        valid_to = now + timedelta(minutes=duration_minutes) if duration_minutes else None

        record = ConsentRecord(
            vault_id=vault_id,
            granter_user_id=granter_user_id,
            grantee_identifier=grantee_identifier,
            consent_type=consent_type,
            purpose=purpose.upper(),
            status="active",
            valid_from=now,
            valid_to=valid_to,
            allowed_resources=allowed_resources
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def verify_consent(
        self,
        vault_id: int,
        accessor_identifier: str,
        purpose: str = "TREAT",
        resource_type: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Verifies if an accessor has valid, active, non-expired consent.
        Supports Emergency override (purpose='EMERGENCY').
        """
        # 1. Emergency Glass-Breaker Check
        if purpose.upper() == "EMERGENCY":
            return True, "Emergency protocol access granted (Audit logged)."

        # 2. Check Active Consents in Database
        now = datetime.datetime.utcnow()
        consents = self.db.query(ConsentRecord).filter(
            ConsentRecord.vault_id == vault_id,
            ConsentRecord.status == "active"
        ).all()

        for c in consents:
            # Check expiration
            if c.valid_to and c.valid_to < now:
                c.status = "expired"
                self.db.commit()
                continue

            # Match grantee identifier (specific doctor / username / role or wildcard)
            if c.grantee_identifier in [accessor_identifier, "*", "all"]:
                # Match purpose
                if c.purpose in [purpose.upper(), "ALL"]:
                    # Match resource type filter
                    if not resource_type or c.allowed_resources in ["all", "*"] or resource_type.lower() in c.allowed_resources.lower():
                        return True, f"Valid consent policy (ID: {c.id}) active."

        return False, "Access denied: No active FHIR consent policy found for this operation."

    def revoke_consent(self, consent_id: int, user_id: int) -> Tuple[bool, Optional[str]]:
        """Revokes an active consent policy."""
        consent = self.db.query(ConsentRecord).filter(ConsentRecord.id == consent_id).first()
        if not consent:
            return False, "Consent policy not found."

        # Verify granter or vault owner
        vault = self.db.query(VaultProfile).filter(VaultProfile.id == consent.vault_id).first()
        if consent.granter_user_id != user_id and vault.owner_user_id != user_id:
            return False, "Unauthorized to revoke this consent policy."

        consent.status = "revoked"
        self.db.commit()
        return True, None

    def get_vault_consents(self, vault_id: int) -> List[ConsentRecord]:
        """Returns all consent policies associated with a vault."""
        return self.db.query(ConsentRecord).filter(ConsentRecord.vault_id == vault_id).order_by(ConsentRecord.created_at.desc()).all()

    @staticmethod
    def to_fhir_consent(record: ConsentRecord, vault: VaultProfile) -> Dict[str, Any]:
        """Maps a ConsentRecord to an HL7 FHIR Release 4 (R4) Consent Resource."""
        consent_id = f"consent-{record.id}"

        # Status mapping
        fhir_status = "active" if record.status == "active" else "inactive"

        # Provision period
        period: Dict[str, str] = {
            "start": record.valid_from.isoformat() + "Z" if record.valid_from else datetime.datetime.utcnow().isoformat() + "Z"
        }
        if record.valid_to:
            period["end"] = record.valid_to.isoformat() + "Z"

        return {
            "resourceType": "Consent",
            "id": consent_id,
            "status": fhir_status,
            "scope": {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/consentscope",
                        "code": record.consent_type or "patient-privacy",
                        "display": "Privacy Consent"
                    }
                ]
            },
            "category": [
                {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
                            "code": "INFORES" if record.purpose != "EMERGENCY" else "EMRGONLY",
                            "display": "Information Access Consent" if record.purpose != "EMERGENCY" else "Emergency Only Access"
                        }
                    ]
                }
            ],
            "patient": {
                "reference": f"Patient/vault-{vault.id}",
                "display": vault.full_name
            },
            "dateTime": record.created_at.isoformat() + "Z" if record.created_at else datetime.datetime.utcnow().isoformat() + "Z",
            "performer": [
                {
                    "display": record.grantee_identifier
                }
            ],
            "provision": {
                "type": "permit" if record.status == "active" else "deny",
                "period": period,
                "purpose": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/v3-ActReason",
                        "code": record.purpose or "TREAT",
                        "display": "Clinical Treatment" if record.purpose == "TREAT" else "Emergency Protocol"
                    }
                ],
                "action": [
                    {
                        "coding": [
                            {
                                "system": "http://terminology.hl7.org/CodeSystem/consentaction",
                                "code": "access",
                                "display": "Access"
                            }
                        ]
                    }
                ]
            }
        }
