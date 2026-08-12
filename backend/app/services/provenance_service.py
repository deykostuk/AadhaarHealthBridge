import hashlib
import datetime
from datetime import timezone
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

from app.models.patient import ProvenanceRecord, VaultProfile
from config import settings

class ProvenanceService:
    """
    Data Provenance Service conforming to HL7 FHIR Release 4 (R4) Provenance specifications.
    Tracks:
    - Data origin & creator authorship
    - SHA-256 cryptographic integrity hashes of medical documents
    - AI extraction lineage (linking extracted Observations back to source DocumentReference)
    - FHIR R4 Provenance searchset bundle generation
    """

    def __init__(self, db: Session):
        self.db = db

    def record_provenance(
        self,
        vault_id: int,
        target_type: str,
        target_id: str,
        activity: str = "CREATE",
        agent_type: str = "author",
        agent_name: str = "AadhaarHealthBridge System",
        source_reference: Optional[str] = None,
        file_bytes: Optional[bytes] = None,
        integrity_hash: Optional[str] = None
    ) -> ProvenanceRecord:
        """Records an immutable data provenance event with optional SHA-256 hash."""
        sha256_hash = integrity_hash
        if file_bytes and not sha256_hash:
            sha256_hash = hashlib.sha256(file_bytes).hexdigest()

        record = ProvenanceRecord(
            vault_id=vault_id,
            target_type=target_type,
            target_id=str(target_id),
            activity=activity.upper(),
            agent_type=agent_type.lower(),
            agent_name=agent_name,
            source_reference=source_reference,
            integrity_hash=sha256_hash,
            recorded_at=datetime.datetime.now(timezone.utc).replace(tzinfo=None)
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def get_vault_provenance(self, vault_id: int, limit: int = 50) -> List[ProvenanceRecord]:
        """Retrieves provenance records for a vault."""
        return (
            self.db.query(ProvenanceRecord)
            .filter(ProvenanceRecord.vault_id == vault_id)
            .order_by(ProvenanceRecord.recorded_at.desc())
            .limit(limit)
            .all()
        )

    def get_provenance_for_target(self, target_type: str, target_id: str) -> List[ProvenanceRecord]:
        """Retrieves lineage for a specific resource target."""
        return (
            self.db.query(ProvenanceRecord)
            .filter(
                ProvenanceRecord.target_type == target_type,
                ProvenanceRecord.target_id == str(target_id)
            )
            .all()
        )

    @staticmethod
    def to_fhir_provenance(record: ProvenanceRecord, vault: Optional[VaultProfile] = None) -> Dict[str, Any]:
        """Maps a ProvenanceRecord to an HL7 FHIR Release 4 (R4) Provenance Resource."""
        provenance_id = f"provenance-{record.id}"

        # Target Reference
        target_ref = f"{record.target_type}/{record.target_id}"

        # Entity / Source mapping
        entities = []
        if record.source_reference:
            entities.append({
                "role": "source",
                "what": {
                    "reference": record.source_reference,
                    "display": f"Source {record.source_reference}"
                }
            })

        # Cryptographic Signature / Hash
        signatures = []
        if record.integrity_hash:
            signatures.append({
                "type": [
                    {
                        "system": "urn:iso-astm:E1762-95:2013",
                        "code": "1.2.840.10065.1.12.1.14",
                        "display": "Verification Signature / SHA-256 Digest"
                    }
                ],
                "when": record.recorded_at.isoformat() + "Z" if record.recorded_at else datetime.datetime.now(timezone.utc).isoformat(),
                "who": {
                    "display": record.agent_name
                },
                "data": record.integrity_hash
            })

        fhir_provenance: Dict[str, Any] = {
            "resourceType": "Provenance",
            "id": provenance_id,
            "target": [
                {
                    "reference": target_ref
                }
            ],
            "recorded": record.recorded_at.isoformat() + "Z" if record.recorded_at else datetime.datetime.now(timezone.utc).isoformat(),
            "activity": {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/v3-DataOperation",
                        "code": record.activity,
                        "display": record.activity.title()
                    }
                ]
            },
            "agent": [
                {
                    "type": {
                        "coding": [
                            {
                                "system": "http://terminology.hl7.org/CodeSystem/provenance-participant-type",
                                "code": record.agent_type,
                                "display": record.agent_type.replace('-', ' ').title()
                            }
                        ]
                    },
                    "who": {
                        "display": record.agent_name
                    }
                }
            ]
        }

        if entities:
            fhir_provenance["entity"] = entities
        if signatures:
            fhir_provenance["signature"] = signatures

        return fhir_provenance

    def get_provenance_bundle(self, vault_id: int, limit: int = 50) -> Dict[str, Any]:
        """Returns standard FHIR R4 searchset Bundle of Provenance resources for a vault."""
        records = self.get_vault_provenance(vault_id, limit=limit)
        vault = self.db.query(VaultProfile).filter(VaultProfile.id == vault_id).first()

        entries = [
            {
                "fullUrl": f"urn:uuid:provenance-{r.id}",
                "resource": self.to_fhir_provenance(r, vault)
            }
            for r in records
        ]

        return {
            "resourceType": "Bundle",
            "type": "searchset",
            "total": len(entries),
            "entry": entries
        }
