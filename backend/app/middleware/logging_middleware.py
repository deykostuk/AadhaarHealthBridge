import time
import uuid
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from app.utils.logger import set_correlation_id
from app.services.telemetry_service import telemetry

logger = logging.getLogger("app.access")

class RequestLoggingAndTracingMiddleware(BaseHTTPMiddleware):
    """
    Operational Visibility & Request Tracing Middleware.
    1. Injects or extracts 'X-Correlation-ID' / 'X-Request-ID'.
    2. Records precise response duration in milliseconds.
    3. Emits structured access logs for every request.
    4. Reports metrics to TelemetryService for Prometheus / APM.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        # Extract or generate correlation ID
        correlation_id = request.headers.get("X-Correlation-ID") or request.headers.get("X-Request-ID") or str(uuid.uuid4())
        set_correlation_id(correlation_id)

        start_time = time.time()
        client_ip = request.headers.get("X-Forwarded-For", request.client.host if request.client else "unknown").split(",")[0].strip()
        method = request.method
        path = request.url.path

        telemetry.increment_active_requests()
        try:
            response = await call_next(request)
            duration_ms = round((time.time() - start_time) * 1000, 2)
            status_code = response.status_code

            # Inject tracing and performance headers
            response.headers["X-Correlation-ID"] = correlation_id
            response.headers["X-Response-Time"] = f"{duration_ms}ms"

            # Record telemetry metrics
            telemetry.record_request(method, path, status_code, duration_ms)

            # Emit structured access log (suppress static asset noise if 200 OK)
            if not path.startswith("/static") or status_code >= 400:
                log_level = logging.INFO if status_code < 400 else (logging.WARNING if status_code < 500 else logging.ERROR)
                logger.log(
                    log_level,
                    f"{method} {path} -> {status_code} ({duration_ms}ms) [ip:{client_ip}] [corr:{correlation_id}]",
                    extra={
                        "correlation_id": correlation_id,
                        "extra_data": {
                            "method": method,
                            "path": path,
                            "status_code": status_code,
                            "duration_ms": duration_ms,
                            "client_ip": client_ip,
                            "user_agent": request.headers.get("user-agent", "")
                        }
                    }
                )

            return response
        except Exception as exc:
            duration_ms = round((time.time() - start_time) * 1000, 2)
            telemetry.record_request(method, path, 500, duration_ms)
            logger.error(
                f"UNHANDLED EXCEPTION on {method} {path} ({duration_ms}ms) [ip:{client_ip}] [corr:{correlation_id}]: {exc}",
                exc_info=True,
                extra={"correlation_id": correlation_id}
            )
            raise
        finally:
            telemetry.decrement_active_requests()
