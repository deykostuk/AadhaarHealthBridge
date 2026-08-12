import json
import logging
import sys
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Optional, Dict, Any

# Thread-safe ContextVar to propagate correlation_id across async request execution
correlation_id_ctx: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)


def get_correlation_id() -> Optional[str]:
    """Returns the current request's correlation ID."""
    return correlation_id_ctx.get()


def set_correlation_id(correlation_id: str) -> None:
    """Sets the correlation ID for the current request context."""
    correlation_id_ctx.set(correlation_id)


class CorrelationFilter(logging.Filter):
    """Ensures every log record contains a 'correlation_id' attribute."""
    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "correlation_id") or not record.correlation_id:
            record.correlation_id = get_correlation_id() or "system"
        return True


class JSONLogFormatter(logging.Formatter):
    """
    High-performance Structured JSON Log Formatter for cloud-native observability
    (Datadog, AWS CloudWatch, Azure Monitor, GCP Cloud Logging, ELK Stack).
    """

    def format(self, record: logging.LogRecord) -> str:
        log_entry: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "line": record.lineno,
            "correlation_id": get_correlation_id() or getattr(record, "correlation_id", "system"),
        }

        # Include exception tracebacks if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        # Include custom extra attributes
        if hasattr(record, "extra_data") and isinstance(record.extra_data, dict):
            log_entry.update(record.extra_data)

        return json.dumps(log_entry, default=str)


def setup_logging(level: str = "INFO", json_format: bool = False) -> None:
    """Configures application-wide logging handlers and formatters."""
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Remove existing handlers to avoid duplicates
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.addFilter(CorrelationFilter())

    if json_format:
        stream_handler.setFormatter(JSONLogFormatter())
    else:
        # Clean human-readable development format with correlation ID
        dev_formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] [%(name)s] [corr:%(correlation_id)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        stream_handler.setFormatter(dev_formatter)

    root_logger.addHandler(stream_handler)
