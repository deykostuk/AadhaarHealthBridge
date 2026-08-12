import pytest
import io
import fitz
from app.services.pdf_processor import LocalPDFProcessor

def test_local_pdf_creation_and_text_extraction():
    # 1. Generate in-memory PDF using PyMuPDF (fitz)
    doc = fitz.open()
    page = doc.new_page()
    rect = fitz.Rect(50, 50, 500, 700)
    sample_text = (
        "Diagnostic Clinical Laboratory Report\n"
        "Patient Name: Aniket Sen\n"
        "Report Date: 15/07/2026\n"
        "Fasting Blood Glucose: 98 mg/dL\n"
        "Serum Creatinine: 1.0 mg/dL\n"
        "HbA1c: 5.4 %\n"
        "Hemoglobin: 14.2 g/dL\n"
        "Blood Urea: 15 mg/dL\n"
    )
    page.insert_textbox(rect, sample_text)
    pdf_bytes = doc.tobytes()
    doc.close()

    # 2. Extract using LocalPDFProcessor
    result = LocalPDFProcessor.extract_text_and_metadata(pdf_bytes, "aniket_lab_report.pdf")
    assert result["page_count"] == 1
    assert result["sha256"] is not None
    assert len(result["sha256"]) == 64
    assert "Fasting Blood Glucose" in result["text"]

    # 3. Extract Clinical Biomarkers
    biomarkers = LocalPDFProcessor.extract_clinical_biomarkers(result["text"])
    assert len(biomarkers) >= 4

    names = [b["name"] for b in biomarkers]
    assert "Blood Glucose (Fasting)" in names
    assert "Creatinine" in names
    assert "HbA1c" in names
    assert "Hemoglobin" in names


def test_plain_text_and_markdown_processing():
    text_content = (
        "Prescription Summary\n"
        "Rx:\n"
        "1. Metformin 500mg (1-0-1)\n"
        "2. Atorvastatin 10mg (0-0-1)\n"
    ).encode("utf-8")

    result = LocalPDFProcessor.extract_text_and_metadata(text_content, "prescription.txt")
    assert result["format"] == "TXT"
    assert "Metformin" in result["text"]
    assert result["sha256"] == LocalPDFProcessor.calculate_sha256(text_content)


def test_document_category_classification():
    assert LocalPDFProcessor.classify_document_category("Complete Blood Count (CBC) and lipid profile", "cbc.pdf") == "Lab Report"
    assert LocalPDFProcessor.classify_document_category("Rx: Paracetamol 650mg tablet twice daily", "rx_slip.pdf") == "Prescription"
    assert LocalPDFProcessor.classify_document_category("Hospital Discharge Summary and surgical notes", "discharge.pdf") == "Discharge Summary"
    assert LocalPDFProcessor.classify_document_category("MRI Lumbar Spine with contrast study", "mri_scan.pdf") == "Diagnostic Imaging"
