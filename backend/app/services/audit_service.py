import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

from app.models.patient import AuditLog, VaultProfile, User
from config import settings

class AuditService:
    """
    Application Audit Service compliant with HL7 FHIR Release 4 (R4) AuditEvent specifications.
    Provides:
    - Immutable event logging across REST APIs, QR scans, and consent policies
    - Mapping to standard FHIR R4 AuditEvent schema
    - Searchset bundle generation for security and ABDM audits
    """

    def __init__(self, db: Session):
        self.db = db

    def log_event(
        self,
        action: str,  # CREATE, READ, UPDATE, DELETE, EXECUTE
        event_type: str = "rest-operation",
        vault_id: Optional[int] = None,
        user_id: Optional[int] = None,
        resource_type: str = "Patient",
        resource_id: Optional[str] = None,
        outcome: str = "SUCCESS",
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        details: Optional[str] = None
    ) -> AuditLog:
        """Records an immutable audit event in the database."""
        log = AuditLog(
            vault_id=vault_id,
            user_id=user_id,
            action=action.upper(),
            event_type=event_type,
            resource_type=resource_type,
            resource_id=resource_id,
            outcome=outcome.upper(),
            ip_address=ip_address or "127.0.0.1",
            user_agent=user_agent or "AadhaarHealthBridge/1.0",
            details=details,
            timestamp=datetime.datetime.utcnow()
        )
        self.db.add(log)
        self.db.commit()
        self.db.refresh(log)
        return log

    def get_vault_audit_logs(self, vault_id: int, limit: int = 50) -> List[AuditLog]:
        """Retrieves recent audit log records for a medical vault."""
        return (
            self.db.query(AuditLog)
            .filter(AuditLog.vault_id == vault_id)
            .order_by(AuditLog.timestamp.desc())
            .limit(limit)
            .all()
        )

    @staticmethod
    def to_fhir_audit_event(log: AuditLog, vault: Optional[VaultProfile] = None) -> Dict[str, Any]:
        """Maps an AuditLog database record to an HL7 FHIR Release 4 (R4) AuditEvent Resource."""
        event_id = f"audit-{log.id}"

        # Action code mapping (C=Create, R=Read, U=Update, D=Delete, E=Execute)
        action_map = {
            "CREATE": "C",
            "READ": "R",
            "UPDATE": "U",
            "DELETE": "D",
            "EXECUTE": "E"
        }
        action_code = action_map.get(log.action.upper(), "E")

        # Outcome code mapping (0=Success, 4=Minor failure/denied, 8=Serious failure)
        outcome_code = "0" if log.outcome == "SUCCESS" else "4" if log.outcome == "DENIED" else "8"

        # Agent role & who reference
        who_display = f"User-{log.user_id}" if log.user_id else "Emergency Scanner / Public Client"
        agent_network = {}
        if log.ip_address:
            agent_network = {
                "address": log.ip_address,
                "type": "2"  # IP Address
            }

        # Entity target mapping
        entities = []
        if log.vault_id:
            entities.append({
                "what": {
                    "reference": f"Patient/vault-{log.vault_id}",
                    "display": vault.full_name if vault else f"Vault {log.vault_id}"
                },
                "type": {
                    "system": "http://terminology.hl7.org/CodeSystem/audit-entity-type",
                    "code": "1",
                    "display": "Person"
                }
            })

        if log.resource_type and log.resource_id:
            entities.append({
                "what": {
                    "reference": f"{log.resource_type}/{log.resource_id}",
                    "display": f"{log.resource_type} {log.resource_id}"
                },
                "type": {
                    "system": "http://terminology.hl7.org/CodeSystem/audit-entity-type",
                    "code": "2",
                    "display": "System Object"
                },
                "detail": [
                    {
                        "type": "user-agent",
                        "valueString": log.user_agent or "Unknown Client"
                    }
                ]
            })

        return {
            "resourceType": "AuditEvent",
            "id": event_id,
            "type": {
                "system": "http://terminology.hl7.org/CodeSystem/audit-event-type",
                "code": "rest",
                "display": "RESTful Operation"
            },
            "subtype": [
                {
                    "system": "http://hl7.org/fhir/restful-interaction",
                    "code": log.event_type.lower(),
                    "display": log.event_type.replace('-', ' ').title()
                }
            ],
            "action": action_code,
            "recorded": log.timestamp.isoformat() + "Z" if log.timestamp else datetime.datetime.utcnow().isoformat() + "Z",
            "outcome": outcome_code,
            "outcomeDesc": log.details or f"{log.action} on {log.resource_type} ({log.outcome})",
            "agent": [
                {
                    "who": {
                        "display": who_display
                    },
                    "requestor": True,
                    "network": agent_network
                }
            ],
            "source": {
                "observer": {
                    "display": "AadhaarHealthBridge Application Server"
                },
                "type": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/security-source-type",
                        "code": "4",
                        "display": "Application Server"
                    }
                ]
            },
            "entity": entities
        }

    def get_audit_events_bundle(self, vault_id: int, limit: int = 50) -> Dict[str, Any]:
        """Returns standard FHIR R4 searchset Bundle of AuditEvents for a patient vault."""
        logs = self.get_vault_audit_logs(vault_id, limit=limit)
        vault = self.db.query(VaultProfile).filter(VaultProfile.id == vault_id).first()

        entries = [
            {
                "fullUrl": f"urn:uuid:audit-{log.id}",
                "resource": self.to_fhir_audit_event(log, vault)
            }
            for log in logs
        ]

        return {
            "resourceType": "Bundle",
            "type": "searchset",
            "total": len(entries),
            "entry": entries
        }
