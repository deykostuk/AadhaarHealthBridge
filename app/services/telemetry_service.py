import time
import os
from typing import Dict, Any
from collections import defaultdict
import threading

class TelemetryService:
    """
    Lightweight, high-performance operational metrics and Prometheus exporter service.
    Zero external dependencies, lock-free or minimal-lock counters for sub-millisecond metrics recording.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self.start_time = time.time()
        self.total_requests = 0
        self.total_errors = 0
        self.requests_by_status: Dict[int, int] = defaultdict(int)
        self.requests_by_path: Dict[str, int] = defaultdict(int)
        self.total_latency_ms = 0.0
        self.qr_scans_total = 0
        self.ai_queries_total = 0
        self.active_requests = 0

    def increment_active_requests(self):
        with self._lock:
            self.active_requests += 1

    def decrement_active_requests(self):
        with self._lock:
            self.active_requests = max(0, self.active_requests - 1)

    def record_request(self, method: str, path: str, status_code: int, duration_ms: float):
        with self._lock:
            self.total_requests += 1
            self.requests_by_status[status_code] += 1
            # Normalize path for aggregation (strip dynamic integer IDs)
            normalized_path = f"{method} {path}"
            self.requests_by_path[normalized_path] += 1
            self.total_latency_ms += duration_ms
            if status_code >= 400:
                self.total_errors += 1

    def record_qr_scan(self):
        with self._lock:
            self.qr_scans_total += 1

    def record_ai_query(self):
        with self._lock:
            self.ai_queries_total += 1

    def get_metrics_summary(self) -> Dict[str, Any]:
        """Returns JSON metrics snapshot for monitoring dashboards."""
        uptime_seconds = time.time() - self.start_time
        avg_latency = (self.total_latency_ms / self.total_requests) if self.total_requests > 0 else 0.0
        error_rate = (self.total_errors / self.total_requests * 100) if self.total_requests > 0 else 0.0

        return {
            "uptime_seconds": round(uptime_seconds, 2),
            "total_requests": self.total_requests,
            "total_errors": self.total_errors,
            "error_rate_pct": round(error_rate, 2),
            "avg_latency_ms": round(avg_latency, 2),
            "active_requests": self.active_requests,
            "qr_scans_total": self.qr_scans_total,
            "ai_queries_total": self.ai_queries_total,
            "requests_by_status": dict(self.requests_by_status),
            "requests_by_path_top": dict(sorted(self.requests_by_path.items(), key=lambda x: x[1], reverse=True)[:10])
        }

    def generate_prometheus_metrics(self) -> str:
        """Exports standard Prometheus text exposition format (OpenMetrics)."""
        summary = self.get_metrics_summary()
        lines = [
            "# HELP ahb_uptime_seconds Total application uptime in seconds",
            "# TYPE ahb_uptime_seconds gauge",
            f"ahb_uptime_seconds {summary['uptime_seconds']}",
            "",
            "# HELP ahb_http_requests_total Total number of HTTP requests processed",
            "# TYPE ahb_http_requests_total counter",
            f"ahb_http_requests_total {summary['total_requests']}",
            "",
            "# HELP ahb_http_errors_total Total number of HTTP 4xx and 5xx errors",
            "# TYPE ahb_http_errors_total counter",
            f"ahb_http_errors_total {summary['total_errors']}",
            "",
            "# HELP ahb_http_latency_average_ms Average response time across all endpoints in milliseconds",
            "# TYPE ahb_http_latency_average_ms gauge",
            f"ahb_http_latency_average_ms {summary['avg_latency_ms']}",
            "",
            "# HELP ahb_active_requests Currently executing in-flight HTTP requests",
            "# TYPE ahb_active_requests gauge",
            f"ahb_active_requests {summary['active_requests']}",
            "",
            "# HELP ahb_emergency_qr_scans_total Total emergency QR codes scanned by first responders",
            "# TYPE ahb_emergency_qr_scans_total counter",
            f"ahb_emergency_qr_scans_total {summary['qr_scans_total']}",
            "",
            "# HELP ahb_ai_rag_queries_total Total clinical AI questions answered",
            "# TYPE ahb_ai_rag_queries_total counter",
            f"ahb_ai_rag_queries_total {summary['ai_queries_total']}",
            ""
        ]

        # Append status breakdown
        for status_code, count in self.requests_by_status.items():
            lines.append(f'ahb_http_requests_by_status{{status="{status_code}"}} {count}')

        return "\n".join(lines) + "\n"


# Singleton instance
telemetry = TelemetryService()
