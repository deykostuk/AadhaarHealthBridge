import datetime
from typing import Dict, Any, List, Optional
from app.models.patient import VaultProfile, HealthMetric, Document, QRScanLog
from config import settings

# --- Standard LOINC & UCUM Clinical Code Mapping ---
LOINC_MAPPINGS: Dict[str, Dict[str, str]] = {
    "creatinine": {
        "code": "2160-0",
        "display": "Creatinine [Mass/volume] in Serum or Plasma",
        "system": "http://loinc.org",
        "unit": "mg/dL",
        "ucum": "mg/dL"
    },
    "urea": {
        "code": "3094-0",
        "display": "Urea nitrogen [Mass/volume] in Serum or Plasma",
        "system": "http://loinc.org",
        "unit": "mg/dL",
        "ucum": "mg/dL"
    },
    "uric_acid": {
        "code": "3086-6",
        "display": "Urate [Mass/volume] in Serum or Plasma",
        "system": "http://loinc.org",
        "unit": "mg/dL",
        "ucum": "mg/dL"
    },
    "hemoglobin": {
        "code": "718-7",
        "display": "Hemoglobin [Mass/volume] in Blood",
        "system": "http://loinc.org",
        "unit": "g/dL",
        "ucum": "g/dL"
    },
    "sugar": {
        "code": "2339-0",
        "display": "Glucose [Mass/volume] in Blood",
        "system": "http://loinc.org",
        "unit": "mg/dL",
        "ucum": "mg/dL"
    },
    "glucose": {
        "code": "2339-0",
        "display": "Glucose [Mass/volume] in Blood",
        "system": "http://loinc.org",
        "unit": "mg/dL",
        "ucum": "mg/dL"
    },
    "hba1c": {
        "code": "4548-4",
        "display": "Hemoglobin A1c/Hemoglobin.total in Blood",
        "system": "http://loinc.org",
        "unit": "%",
        "ucum": "%"
    }
}


class FHIRService:
    """
    Comprehensive Service for transforming clinical models into HL7 FHIR Release 4 (R4) Resources:
    - Patient
    - Observation (with LOINC codes)
    - DiagnosticReport (linking observations & attachments)
    - MedicationRequest (prescriptions & active dosages)
    - Encounter (clinical doctor interactions & emergency QR scans)
    - AllergyIntolerance
    - Condition
    - Bundle ($everything composite)
    """

    @staticmethod
    def to_fhir_patient(vault: VaultProfile) -> Dict[str, Any]:
        """Maps VaultProfile to HL7 FHIR R4 Patient resource."""
        patient_id = f"vault-{vault.id}"
        
        # Emergency Contacts mapping
        contacts = []
        for i in [1, 2, 3]:
            name = getattr(vault, f"emergency_{i}_name", None)
            relation = getattr(vault, f"emergency_{i}_relation", None)
            phone = getattr(vault, f"emergency_{i}_phone", None)
            if name or phone:
                contact_entry = {
                    "relationship": [
                        {
                            "coding": [
                                {
                                    "system": "http://terminology.hl7.org/CodeSystem/v2-0131",
                                    "code": "C",
                                    "display": "Emergency Contact"
                                }
                            ],
                            "text": relation or "Emergency Contact"
                        }
                    ],
                    "name": {"text": name or "Emergency Contact"}
                }
                if phone:
                    contact_entry["telecom"] = [
                        {"system": "phone", "value": phone, "use": "mobile"}
                    ]
                contacts.append(contact_entry)

        telecom = []
        if vault.personal_contact:
            telecom.append({"system": "phone", "value": vault.personal_contact, "use": "mobile"})

        # Extensions (e.g. Blood Group)
        extensions = []
        if vault.blood_group:
            extensions.append({
                "url": "http://hl7.org/fhir/StructureDefinition/patient-bloodGroup",
                "valueString": vault.blood_group
            })

        patient_resource: Dict[str, Any] = {
            "resourceType": "Patient",
            "id": patient_id,
            "identifier": [
                {
                    "use": "official",
                    "system": "https://aadhaarhealthbridge.in/qr-token",
                    "value": vault.qr_token
                }
            ],
            "active": True,
            "name": [
                {
                    "use": "official",
                    "text": vault.full_name
                }
            ],
            "telecom": telecom,
            "contact": contacts
        }

        if extensions:
            patient_resource["extension"] = extensions

        return patient_resource

    @staticmethod
    def to_fhir_observation(metric: HealthMetric, vault: VaultProfile) -> Dict[str, Any]:
        """Maps HealthMetric to HL7 FHIR R4 Observation resource."""
        obs_id = f"obs-{metric.id}"
        metric_key = (metric.metric_name or "").lower()
        loinc_info = LOINC_MAPPINGS.get(metric_key, {
            "code": "generic-obs",
            "display": metric.metric_name or "Observation",
            "system": "https://aadhaarhealthbridge.in/clinical-metrics",
            "unit": metric.metric_unit or "",
            "ucum": metric.metric_unit or ""
        })

        val = None
        try:
            val = float(metric.metric_value)
        except Exception:
            pass

        value_field = {}
        if val is not None:
            value_field = {
                "valueQuantity": {
                    "value": val,
                    "unit": metric.metric_unit or loinc_info.get("unit", ""),
                    "system": "http://unitsofmeasure.org",
                    "code": loinc_info.get("ucum", "")
                }
            }
        else:
            value_field = {"valueString": str(metric.metric_value)}

        observation: Dict[str, Any] = {
            "resourceType": "Observation",
            "id": obs_id,
            "status": "final",
            "category": [
                {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                            "code": "laboratory",
                            "display": "Laboratory"
                        }
                    ]
                }
            ],
            "code": {
                "coding": [
                    {
                        "system": loinc_info["system"],
                        "code": loinc_info["code"],
                        "display": loinc_info["display"]
                    }
                ],
                "text": metric.metric_name.replace('_', ' ').title()
            },
            "subject": {
                "reference": f"Patient/vault-{vault.id}",
                "display": vault.full_name
            },
            "effectiveDateTime": metric.observed_date.isoformat() if metric.observed_date else datetime.datetime.utcnow().isoformat(),
            **value_field
        }

        if metric.source_document_id:
            observation["derivedFrom"] = [
                {"reference": f"DocumentReference/doc-{metric.source_document_id}"}
            ]

        return observation

    @staticmethod
    def to_fhir_diagnostic_report(
        doc: Document,
        metrics: List[HealthMetric],
        vault: VaultProfile
    ) -> Dict[str, Any]:
        """Maps a Document and its extracted metrics to an HL7 FHIR R4 DiagnosticReport resource."""
        report_id = f"report-{doc.id}"
        ext = doc.file_path.split('.')[-1].lower() if doc.file_path else "pdf"
        mime_type = "application/pdf" if ext == "pdf" else f"image/{ext}" if ext in ["png", "jpg", "jpeg"] else "application/octet-stream"
        doc_url = f"{settings.APP_BASE_URL.rstrip('/')}/api/v1/vaults/{vault.id}/documents/{doc.id}/serve"

        # Link child observations extracted from this report
        results = [
            {"reference": f"Observation/obs-{m.id}", "display": m.metric_name.title()}
            for m in metrics if m.source_document_id == doc.id
        ]

        return {
            "resourceType": "DiagnosticReport",
            "id": report_id,
            "status": "final",
            "category": [
                {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/v2-0074",
                            "code": "LAB",
                            "display": "Laboratory Report"
                        }
                    ]
                }
            ],
            "code": {
                "coding": [
                    {
                        "system": "http://loinc.org",
                        "code": "11502-2",
                        "display": doc.category or "Laboratory Report"
                    }
                ],
                "text": doc.file_name or "Diagnostic Laboratory Report"
            },
            "subject": {
                "reference": f"Patient/vault-{vault.id}",
                "display": vault.full_name
            },
            "effectiveDateTime": doc.upload_date.isoformat() if hasattr(doc, "upload_date") and doc.upload_date else datetime.datetime.utcnow().isoformat(),
            "issued": datetime.datetime.utcnow().isoformat() + "Z",
            "result": results,
            "presentedForm": [
                {
                    "contentType": mime_type,
                    "url": doc_url,
                    "title": doc.file_name or "Diagnostic Report PDF"
                }
            ]
        }

    @staticmethod
    def to_fhir_medication_requests(vault: VaultProfile) -> List[Dict[str, Any]]:
        """Maps active medications to HL7 FHIR R4 MedicationRequest resources."""
        if not vault.medications or vault.medications.lower() in ["none", "nil", "n/a"]:
            return []

        meds = [m.strip() for m in vault.medications.split(",") if m.strip()]
        resources = []
        for idx, item in enumerate(meds, 1):
            resources.append({
                "resourceType": "MedicationRequest",
                "id": f"medreq-{vault.id}-{idx}",
                "status": "active",
                "intent": "order",
                "medicationCodeableConcept": {
                    "text": item
                },
                "subject": {
                    "reference": f"Patient/vault-{vault.id}",
                    "display": vault.full_name
                },
                "authoredOn": datetime.datetime.utcnow().date().isoformat(),
                "dosageInstruction": [
                    {
                        "text": f"Take {item} as prescribed by physician."
                    }
                ]
            })
        return resources

    @staticmethod
    def to_fhir_encounters(scan_logs: List[QRScanLog], vault: VaultProfile) -> List[Dict[str, Any]]:
        """Maps QR scan and clinical access logs to HL7 FHIR R4 Encounter resources."""
        resources = []
        for log in scan_logs:
            enc_id = f"encounter-{log.id}"
            loc_text = log.location_data or "India (Clinic/Hospital Access)"
            
            resources.append({
                "resourceType": "Encounter",
                "id": enc_id,
                "status": "finished",
                "class": {
                    "system": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
                    "code": "AMB",
                    "display": "Ambulatory / Outpatient Access"
                },
                "subject": {
                    "reference": f"Patient/vault-{vault.id}",
                    "display": vault.full_name
                },
                "period": {
                    "start": log.timestamp.isoformat() if log.timestamp else datetime.datetime.utcnow().isoformat()
                },
                "reasonCode": [
                    {
                        "text": f"QR Scan Interaction ({log.user_agent or 'Healthcare Scanner'})"
                    }
                ],
                "location": [
                    {
                        "location": {
                            "display": loc_text
                        }
                    }
                ]
            })
        return resources

    @staticmethod
    def to_fhir_document_reference(doc: Document, vault: VaultProfile) -> Dict[str, Any]:
        """Maps Document to HL7 FHIR R4 DocumentReference resource."""
        doc_id = f"doc-{doc.id}"
        ext = doc.file_path.split('.')[-1].lower() if doc.file_path else "pdf"
        mime_type = "application/pdf" if ext == "pdf" else f"image/{ext}" if ext in ["png", "jpg", "jpeg"] else "application/octet-stream"

        doc_url = f"{settings.APP_BASE_URL.rstrip('/')}/api/v1/vaults/{vault.id}/documents/{doc.id}/serve"

        return {
            "resourceType": "DocumentReference",
            "id": doc_id,
            "status": "current",
            "category": [
                {
                    "coding": [
                        {
                            "system": "http://loinc.org",
                            "code": "11502-2",
                            "display": doc.category or "Diagnostic Lab Report"
                        }
                    ]
                }
            ],
            "subject": {
                "reference": f"Patient/vault-{vault.id}",
                "display": vault.full_name
            },
            "date": doc.upload_date.isoformat() if hasattr(doc, "upload_date") and doc.upload_date else datetime.datetime.utcnow().isoformat(),
            "description": doc.file_name or "Medical Report",
            "content": [
                {
                    "attachment": {
                        "contentType": mime_type,
                        "url": doc_url,
                        "title": doc.file_name or "Medical Record"
                    }
                }
            ]
        }

    @staticmethod
    def to_fhir_allergies(vault: VaultProfile) -> List[Dict[str, Any]]:
        """Maps vault allergies string to HL7 FHIR R4 AllergyIntolerance resources."""
        if not vault.allergies or vault.allergies.lower() in ["none", "nil", "n/a"]:
            return []

        allergies = [a.strip() for a in vault.allergies.split(",") if a.strip()]
        resources = []
        for idx, item in enumerate(allergies, 1):
            resources.append({
                "resourceType": "AllergyIntolerance",
                "id": f"allergy-{vault.id}-{idx}",
                "clinicalStatus": {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/allergyintolerance-clinical",
                            "code": "active",
                            "display": "Active"
                        }
                    ]
                },
                "verificationStatus": {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/allergyintolerance-verification",
                            "code": "confirmed",
                            "display": "Confirmed"
                        }
                    ]
                },
                "criticality": "high",
                "code": {
                    "text": item
                },
                "patient": {
                    "reference": f"Patient/vault-{vault.id}",
                    "display": vault.full_name
                }
            })
        return resources

    @staticmethod
    def to_fhir_conditions(vault: VaultProfile) -> List[Dict[str, Any]]:
        """Maps vault medical conditions to HL7 FHIR R4 Condition resources."""
        if not vault.medical_conditions or vault.medical_conditions.lower() in ["none", "nil", "n/a"]:
            return []

        conditions = [c.strip() for c in vault.medical_conditions.split(",") if c.strip()]
        resources = []
        for idx, item in enumerate(conditions, 1):
            resources.append({
                "resourceType": "Condition",
                "id": f"condition-{vault.id}-{idx}",
                "clinicalStatus": {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
                            "code": "active",
                            "display": "Active"
                        }
                    ]
                },
                "verificationStatus": {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/condition-ver-status",
                            "code": "confirmed",
                            "display": "Confirmed"
                        }
                    ]
                },
                "code": {
                    "text": item
                },
                "subject": {
                    "reference": f"Patient/vault-{vault.id}",
                    "display": vault.full_name
                }
            })
        return resources

    @staticmethod
    def to_fhir_consents(consents: List[Any], vault: VaultProfile) -> List[Dict[str, Any]]:
        """Maps vault ConsentRecords to HL7 FHIR R4 Consent resources."""
        from app.services.consent_service import ConsentService
        return [ConsentService.to_fhir_consent(c, vault) for c in consents]

    def build_patient_bundle(
        self,
        vault: VaultProfile,
        metrics: List[HealthMetric],
        docs: List[Document],
        scan_logs: Optional[List[QRScanLog]] = None,
        consents: Optional[List[Any]] = None
    ) -> Dict[str, Any]:
        """Aggregates all clinical resources into an HL7 FHIR R4 Patient $everything Collection Bundle."""
        entries = []

        # 1. Patient Resource
        patient_res = self.to_fhir_patient(vault)
        entries.append({
            "fullUrl": f"urn:uuid:patient-{vault.id}",
            "resource": patient_res
        })

        # 2. Observations
        for m in metrics:
            obs_res = self.to_fhir_observation(m, vault)
            entries.append({
                "fullUrl": f"urn:uuid:observation-{m.id}",
                "resource": obs_res
            })

        # 3. DiagnosticReports
        for d in docs:
            rep_res = self.to_fhir_diagnostic_report(d, metrics, vault)
            entries.append({
                "fullUrl": f"urn:uuid:report-{d.id}",
                "resource": rep_res
            })

        # 4. DocumentReferences
        for d in docs:
            doc_res = self.to_fhir_document_reference(d, vault)
            entries.append({
                "fullUrl": f"urn:uuid:document-{d.id}",
                "resource": doc_res
            })

        # 5. MedicationRequests
        for med in self.to_fhir_medication_requests(vault):
            entries.append({
                "fullUrl": f"urn:uuid:{med['id']}",
                "resource": med
            })

        # 6. Encounters (QR Scan Access Logs)
        if scan_logs:
            for enc in self.to_fhir_encounters(scan_logs, vault):
                entries.append({
                    "fullUrl": f"urn:uuid:{enc['id']}",
                    "resource": enc
                })

        # 7. Consents
        if consents:
            for con in self.to_fhir_consents(consents, vault):
                entries.append({
                    "fullUrl": f"urn:uuid:{con['id']}",
                    "resource": con
                })

        # 8. AllergyIntolerances
        for a in self.to_fhir_allergies(vault):
            entries.append({
                "fullUrl": f"urn:uuid:{a['id']}",
                "resource": a
            })

        # 9. Conditions
        for c in self.to_fhir_conditions(vault):
            entries.append({
                "fullUrl": f"urn:uuid:{c['id']}",
                "resource": c
            })

        return {
            "resourceType": "Bundle",
            "id": f"bundle-vault-{vault.id}",
            "type": "collection",
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
            "total": len(entries),
            "entry": entries
        }


# Default singleton instance
fhir_service = FHIRService()
