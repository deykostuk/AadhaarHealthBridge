import pytest
import json
import logging
from app.utils.logger import JSONLogFormatter, get_correlation_id, set_correlation_id
from app.services.telemetry_service import telemetry

def test_correlation_id_and_response_time_headers(client):
    """Verifies that every response includes X-Correlation-ID and X-Response-Time headers."""
    # 1. Without client-provided correlation ID
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    assert "X-Correlation-ID" in res.headers
    assert len(res.headers["X-Correlation-ID"]) > 0
    assert "X-Response-Time" in res.headers
    assert "ms" in res.headers["X-Response-Time"]

    # 2. With client-provided correlation ID
    custom_corr_id = "test-corr-uuid-12345"
    res2 = client.get("/api/v1/health", headers={"X-Correlation-ID": custom_corr_id})
    assert res2.status_code == 200
    assert res2.headers["X-Correlation-ID"] == custom_corr_id


def test_liveness_and_readiness_probes(client):
    """Verifies Kubernetes / container liveness and readiness probe responses."""
    # Liveness
    live_res = client.get("/api/v1/health/live")
    assert live_res.status_code == 200
    assert live_res.json()["status"] == "alive"

    # Readiness
    ready_res = client.get("/api/v1/health/ready")
    assert ready_res.status_code == 200
    data = ready_res.json()
    assert data["status"] == "ready"
    assert data["checks"]["database"] == "connected"
    assert data["checks"]["storage"] == "writable"


def test_telemetry_metrics_json_and_prometheus(client):
    """Verifies JSON telemetry metrics and Prometheus scraping endpoints."""
    # Send sample request
    client.get("/api/v1/health")

    # JSON Snapshot
    metrics_res = client.get("/api/v1/health/metrics")
    assert metrics_res.status_code == 200
    metrics_data = metrics_res.json()
    assert "total_requests" in metrics_data
    assert metrics_data["total_requests"] >= 1
    assert "uptime_seconds" in metrics_data
    assert "avg_latency_ms" in metrics_data

    # Prometheus OpenMetrics format
    prom_res = client.get("/api/v1/health/prometheus")
    assert prom_res.status_code == 200
    assert "text/plain" in prom_res.headers["content-type"]
    assert "ahb_http_requests_total" in prom_res.text
    assert "ahb_uptime_seconds" in prom_res.text
    assert "ahb_http_latency_average_ms" in prom_res.text


def test_structured_json_log_formatter():
    """Verifies that JSONLogFormatter outputs valid, parseable JSON with correlation context."""
    formatter = JSONLogFormatter()
    set_correlation_id("test-context-corr-999")

    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="test_path.py",
        lineno=42,
        msg="Test structured log message",
        args=(),
        exc_info=None
    )
    formatted = formatter.format(record)
    parsed = json.loads(formatted)

    assert parsed["level"] == "INFO"
    assert parsed["logger"] == "test_logger"
    assert parsed["message"] == "Test structured log message"
    assert parsed["correlation_id"] == "test-context-corr-999"
    assert "timestamp" in parsed
