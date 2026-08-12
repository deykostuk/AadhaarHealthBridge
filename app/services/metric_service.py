import json
import re
import logging
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

from app.models.patient import HealthMetric, VaultProfile
from app.services import semantic_service

logger = logging.getLogger(__name__)

class HealthMetricService:
    """Modular service handling biomarker metrics extraction, snapshot management, and trends."""

    def __init__(self, db: Session):
        self.db = db

    def extract_and_persist_metrics_from_text(self, vault_id: int, document_id: int, text: str):
        """Extracts structured values from text, persists HealthMetric rows, and updates Vault snapshot."""
        if not text:
            return

        structured = semantic_service.extract_structured_info(text)
        metric_rows = semantic_service.extract_health_metric_rows(text, source_document_id=document_id)

        for row in metric_rows:
            metric = HealthMetric(
                vault_id=vault_id,
                metric_name=row["metric_name"],
                metric_value=row["metric_value"],
                metric_unit=row["metric_unit"],
                observed_date=row["observed_date"],
                source_document_id=row["source_document_id"]
            )
            self.db.add(metric)

        if structured:
            vault = self.db.query(VaultProfile).filter(VaultProfile.id == vault_id).first()
            if vault:
                try:
                    existing = json.loads(vault.health_snapshot) if vault.health_snapshot else {}
                except Exception:
                    existing = {}
                existing.update(structured)
                vault.health_snapshot = json.dumps(existing)

        self.db.commit()

    def get_vault_metrics(self, vault_id: int, metric_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieves history of health metrics for a vault."""
        query = self.db.query(HealthMetric).filter(HealthMetric.vault_id == vault_id)
        if metric_name:
            query = query.filter(HealthMetric.metric_name == metric_name)
        metrics = query.order_by(HealthMetric.observed_date.asc()).all()

        return [
            {
                "metric_name": m.metric_name,
                "metric_value": m.metric_value,
                "metric_unit": m.metric_unit or "",
                "observed_date": m.observed_date.isoformat() if m.observed_date else None,
                "source_document_id": m.source_document_id
            }
            for m in metrics
        ]

    def get_vault_snapshot_data(self, vault_id: int) -> Dict[str, Any]:
        """Retrieves structured JSON health snapshot and latest 5 recorded metrics."""
        vault = self.db.query(VaultProfile).filter(VaultProfile.id == vault_id).first()
        snapshot = {}
        if vault and vault.health_snapshot:
            try:
                snapshot = json.loads(vault.health_snapshot)
            except Exception:
                snapshot = {}

        latest_metrics = self.db.query(HealthMetric).filter(
            HealthMetric.vault_id == vault_id
        ).order_by(HealthMetric.observed_date.desc()).limit(5).all()

        return {
            "vault_id": vault_id,
            "health_snapshot": snapshot,
            "latest_metrics": [
                {
                    "metric_name": m.metric_name,
                    "metric_value": m.metric_value,
                    "metric_unit": m.metric_unit or "",
                    "observed_date": m.observed_date.isoformat() if m.observed_date else None,
                    "source_document_id": m.source_document_id
                }
                for m in latest_metrics
            ]
        }

    def build_trend_response_for_query(self, vault_id: int, query: str) -> Optional[Dict[str, Any]]:
        """Generates clinical trend table/narrative if the query targets biomarkers."""
        metric_name = semantic_service.metric_key_from_query(query)
        metrics_q = self.db.query(HealthMetric).filter(HealthMetric.vault_id == vault_id)
        if metric_name:
            metrics_q = metrics_q.filter(HealthMetric.metric_name == metric_name)
        metrics = metrics_q.order_by(HealthMetric.observed_date.asc()).all()

        rows = [
            {
                "metric_name": m.metric_name,
                "metric_value": m.metric_value,
                "metric_unit": m.metric_unit or "",
                "observed_date": m.observed_date.isoformat() if m.observed_date else None,
                "source_document_id": m.source_document_id
            }
            for m in metrics
        ]

        if not rows:
            return None

        if metric_name:
            answer = semantic_service.format_metric_trend_answer(metric_name, rows)
        else:
            latest_map = {}
            for r in rows:
                latest_map[r["metric_name"]] = r

            summary_lines = []
            for name, r in latest_map.items():
                pretty_name = name.replace('_', ' ').title()
                obs_date = r["observed_date"][:10] if r["observed_date"] else "Unknown"
                ref_info = semantic_service.BIOMARKER_RANGES.get(name, {"minNormal": 0.0, "maxNormal": 999.0})
                val = None
                try:
                    if re.match(r"^\d+(\.\d+)?$", str(r["metric_value"])):
                        val = float(r["metric_value"])
                except Exception:
                    pass
                status_str = "✅ Normal"
                if val is not None:
                    if val < ref_info.get("minNormal", 0.0):
                        status_str = "⚠️ Low"
                    elif val > ref_info.get("maxNormal", 999.0):
                        status_str = "⚠️ High"
                summary_lines.append(f"| {pretty_name} | {r['metric_value']} {r['metric_unit']} | {ref_info.get('minNormal')} - {ref_info.get('maxNormal')} {r['metric_unit']} | {status_str} | {obs_date} |")

            answer = (
                "### 📋 Current Health Dashboard Summary\n\n"
                "Here are the latest recorded values for all your health biomarkers:\n\n"
                "| Biomarker | Value | Reference Range | Status | Observed Date |\n"
                "| :--- | :--- | :--- | :--- | :--- |\n"
                + "\n".join(summary_lines)
            )

        return {"answer": answer, "metrics": rows}
