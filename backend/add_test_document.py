from app import create_app, db
from app.models.patient import Document, HealthMetric
from app.services import semantic_service
from datetime import datetime

app = create_app()

with app.app_context():
    # 1. Create the Document
    ocr_text = (
        "Report Date: 05/06/2026\n"
        "Creatinine: 1.2 mg/dL\n"
        "Urea: 22 mg/dL\n"
        "Uric Acid: 5.6 mg/dL\n"
        "Hemoglobin: 14.2 g/dL\n"
        "Sugar: 95 mg/dL"
    )
    
    doc = Document(
        vault_id=1,
        file_path="vault_docs/vault_1/test_report.pdf",
        file_name="Verification Lab Report",
        category="Diagnostic Lab Report",
        ocr_text=ocr_text,
        ai_summary="Baseline health metrics check.",
        uploaded_by=1,
        is_encrypted=False
    )
    db.session.add(doc)
    db.session.flush()

    # 2. Extract and insert HealthMetric rows
    metric_rows = semantic_service.extract_health_metric_rows(ocr_text, doc.id)
    for row in metric_rows:
        metric = HealthMetric(
            vault_id=1,
            metric_name=row["metric_name"],
            metric_value=row["metric_value"],
            metric_unit=row["metric_unit"],
            observed_date=row["observed_date"],
            source_document_id=row["source_document_id"]
        )
        db.session.add(metric)
    
    db.session.commit()
    print("SUCCESS: Injected verification lab report and metrics successfully!")
