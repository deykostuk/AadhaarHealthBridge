import io
import re
import hashlib
import datetime
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

# Standard Biomarker Parsers with Regex and LOINC mapping
BIOMARKER_PATTERNS = [
    {
        "name": "Creatinine",
        "loinc": "2160-0",
        "default_unit": "mg/dL",
        "normal_range": "0.7 - 1.3",
        "pattern": r"(?:serum\s+)?creatinine(?:\s*level)?[:\-]?\s*(\d+(?:\.\d+)?)\s*(mg\/dL|mg%|umol\/L)?",
    },
    {
        "name": "Blood Glucose (Fasting)",
        "loinc": "2339-0",
        "default_unit": "mg/dL",
        "normal_range": "70 - 99",
        "pattern": r"(?:fasting\s+blood\s+(?:sugar|glucose)|fbs)[:\-]?\s*(\d+(?:\.\d+)?)\s*(mg\/dL|mmol\/L)?",
    },
    {
        "name": "HbA1c",
        "loinc": "4548-4",
        "default_unit": "%",
        "normal_range": "< 5.7",
        "pattern": r"(?:glycated\s+hemoglobin|hba1c|hb1ac)[:\-]?\s*(\d+(?:\.\d+)?)\s*(%)?",
    },
    {
        "name": "Hemoglobin",
        "loinc": "718-7",
        "default_unit": "g/dL",
        "normal_range": "13.8 - 17.2",
        "pattern": r"(?:hemoglobin|hb|hgb)[:\-]?\s*(\d+(?:\.\d+)?)\s*(g\/dL|gm%|g\/L)?",
    },
    {
        "name": "Blood Urea",
        "loinc": "3094-0",
        "default_unit": "mg/dL",
        "normal_range": "7 - 20",
        "pattern": r"(?:blood\s+urea(?:\s+nitrogen)?|bun|urea)[:\-]?\s*(\d+(?:\.\d+)?)\s*(mg\/dL)?",
    },
    {
        "name": "Uric Acid",
        "loinc": "3086-6",
        "default_unit": "mg/dL",
        "normal_range": "3.5 - 7.2",
        "pattern": r"(?:serum\s+)?uric\s+acid[:\-]?\s*(\d+(?:\.\d+)?)\s*(mg\/dL)?",
    }
]


class LocalPDFProcessor:
    """
    100% On-Device Python Document and PDF Processing Engine.
    Powered by PyMuPDF (fitz) with layout parsing, metadata extraction,
    cryptographic SHA-256 calculation, and clinical biomarker structuring.
    """

    @staticmethod
    def calculate_sha256(file_bytes: bytes) -> str:
        """Computes SHA-256 cryptographic digest of document bytes."""
        return hashlib.sha256(file_bytes).hexdigest()

    @classmethod
    def extract_text_and_metadata(cls, file_bytes: bytes, file_name: str = "document.pdf") -> Dict[str, Any]:
        """
        Extracts full plain text and structural metadata from PDF or text documents.
        Uses PyMuPDF (fitz) with graceful stream fallback.
        """
        sha256_hash = cls.calculate_sha256(file_bytes)
        ext = file_name.lower().rsplit(".", 1)[-1] if "." in file_name else ""

        # 1. Plain Text / Markdown Files
        if ext in ["txt", "text", "csv", "json", "md"]:
            try:
                text = file_bytes.decode("utf-8", errors="replace")
            except Exception:
                text = str(file_bytes)
            return {
                "text": text.strip(),
                "page_count": 1,
                "sha256": sha256_hash,
                "file_name": file_name,
                "file_size": len(file_bytes),
                "format": ext.upper(),
                "metadata": {"title": file_name}
            }

        # 2. PDF Processing via PyMuPDF (fitz)
        extracted_pages = []
        metadata = {}
        page_count = 0

        try:
            import fitz  # PyMuPDF
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            page_count = len(doc)
            metadata = {
                "title": doc.metadata.get("title") or file_name,
                "author": doc.metadata.get("author") or "",
                "subject": doc.metadata.get("subject") or "",
                "creator": doc.metadata.get("creator") or "PyMuPDF",
                "producer": doc.metadata.get("producer") or "",
                "creation_date": doc.metadata.get("creationDate") or ""
            }

            for page_num in range(page_count):
                page = doc.load_page(page_num)
                page_text = page.get_text("text")
                if page_text and page_text.strip():
                    extracted_pages.append(page_text.strip())

            doc.close()
        except Exception as e:
            logger.debug(f"[LocalPDFProcessor] PyMuPDF extraction note: {e}")
            extracted_pages = []

        full_text = "\n\n".join(extracted_pages).strip()

        return {
            "text": full_text,
            "page_count": max(page_count, 1),
            "sha256": sha256_hash,
            "file_name": file_name,
            "file_size": len(file_bytes),
            "format": "PDF",
            "metadata": metadata
        }

    @staticmethod
    def extract_observed_date(text: str) -> datetime.datetime:
        """Parses report observation date from clinical text with support for obfuscated PUA fonts and text months."""
        # Clean PUA obfuscated characters
        chars = []
        for char in text or "":
            o = ord(char)
            if 0xf000 <= o <= 0xf0ff:
                chars.append(chr(o - 0xf000))
            else:
                chars.append(char)
        clean_text = "".join(chars)

        # Regex for various date formats (e.g. 20-Feb-2023, 23/7/2024, 2023-02-20)
        date_regex = r"\b(?:\d{1,2}[ \/\-.]+(?:\d{1,2}|[a-zA-Z]{3,9})[ \/\-.]+\d{2,4}|\d{4}-\d{1,2}-\d{1,2}|[a-zA-Z]{3,9}\s+\d{1,2},\s*\d{4})\b"
        
        formats = [
            "%d-%b-%Y", "%d %b %Y", "%d/%b/%Y",
            "%d-%B-%Y", "%d %B %Y", "%d/%B/%Y",
            "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y",
            "%Y-%m-%d", "%m/%d/%Y",
            "%b %d, %Y", "%B %d, %Y",
            "%d-%b-%y", "%d %b %y", "%d/%b/%y",
            "%d/%m/%y", "%d-%m-%y"
        ]
        
        found_dates = []
        for m in re.finditer(date_regex, clean_text, re.I):
            date_str = m.group(0).strip()
            # Clean up duplicate whitespace
            date_str = re.sub(r"\s+", " ", date_str)
            for fmt in formats:
                try:
                    parsed_dt = datetime.datetime.strptime(date_str, fmt)
                    found_dates.append((m.start(), parsed_dt))
                    break
                except ValueError:
                    continue

        if not found_dates:
            return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)

        # Prioritize dates that appear close to key clinical report words
        keywords = ["collected", "reported", "approved", "received", "date of", "report date"]
        scored_dates = []
        for pos, d in found_dates:
            # Skip DOBs and future bounds
            if d.year < 2010 or d.year > 2030:
                continue
            context = clean_text[max(0, pos - 100):min(len(clean_text), pos + 100)].lower()
            score = sum(1 for kw in keywords if kw in context)
            scored_dates.append((score, d))

        if scored_dates:
            # Sort by score descending, then by date descending (latest preferred)
            scored_dates.sort(key=lambda x: (x[0], x[1]), reverse=True)
            return scored_dates[0][1]

        # Fallback to first parsed date with year in normal range
        normal_dates = [d for pos, d in found_dates if 2010 <= d.year <= 2030]
        if normal_dates:
            return normal_dates[0]

        return found_dates[0][1]

    @classmethod
    def extract_clinical_biomarkers(cls, text: str) -> List[Dict[str, Any]]:
        """
        Parses structured clinical biomarkers from text using regex and normal intervals.
        Returns list of structured observation items ready for HL7 FHIR Observation creation.
        """
        if not text:
            return []

        observed_date = cls.extract_observed_date(text)
        biomarkers = []

        for spec in BIOMARKER_PATTERNS:
            match = re.search(spec["pattern"], text, re.I)
            if match:
                value_str = match.group(1)
                unit = match.group(2) if len(match.groups()) >= 2 and match.group(2) else spec["default_unit"]

                biomarkers.append({
                    "name": spec["name"],
                    "loinc_code": spec["loinc"],
                    "value": value_str,
                    "unit": unit,
                    "reference_range": spec["normal_range"],
                    "observed_date": observed_date
                })

        return biomarkers

    @staticmethod
    def classify_document_category(text: str, file_name: str = "") -> str:
        """Classifies document into standard clinical categories."""
        combined = f"{file_name} {text}".lower()

        if any(k in combined for k in ["blood", "urine", "lab", "pathology", "cbc", "lft", "kft", "hba1c", "glucose"]):
            return "Lab Report"
        if any(k in combined for k in ["rx", "prescription", "dosage", "tablet", "capsule", "syrup", "sig:"]):
            return "Prescription"
        if any(k in combined for k in ["discharge", "admission", "hospital", "diagnosis", "operative summary"]):
            return "Discharge Summary"
        if any(k in combined for k in ["mri", "x-ray", "ct scan", "ultrasound", "radiology", "ecg", "echo"]):
            return "Diagnostic Imaging"

        return "General Health Record"


# Singleton Instance
local_pdf_processor = LocalPDFProcessor()
