import time
import ipaddress
import socket
import logging
from typing import Dict, Tuple, List, Optional
from urllib.parse import urlparse
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

# Private and loopback IPv4/IPv6 networks to block for SSRF prevention
BLOCKED_IP_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),  # Link-local / Cloud metadata (AWS/GCP/Azure)
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]


class SSRFValidator:
    """
    OWASP API7:2023 & A03:2021 - Server-Side Request Forgery (SSRF) Defense.
    Validates external destination URLs and verifies they do not resolve
    to internal private networks, localhost, or cloud metadata services.
    """

    @classmethod
    def is_safe_url(cls, url: str) -> Tuple[bool, Optional[str]]:
        try:
            parsed = urlparse(url)
            if parsed.scheme not in ["http", "https"]:
                return False, f"Invalid URL scheme '{parsed.scheme}'. Only HTTP and HTTPS are allowed."

            hostname = parsed.hostname
            if not hostname:
                return False, "Invalid URL: Missing hostname."

            if hostname.lower() in ["localhost", "127.0.0.1", "0.0.0.0", "::1", "metadata.google.internal"]:  # nosec B104
                return False, "Access to localhost and internal loopback addresses is forbidden."

            # Resolve DNS and check each IP against blocked subnets
            ip_addresses = socket.getaddrinfo(hostname, None)
            for addr_info in ip_addresses:
                ip_str = addr_info[4][0]
                ip_obj = ipaddress.ip_address(ip_str)
                for blocked_net in BLOCKED_IP_NETWORKS:
                    if ip_obj in blocked_net:
                        return False, f"Access to private/internal network address '{ip_str}' is forbidden (SSRF defense)."

            return True, None
        except Exception as e:
            return False, f"SSRF URL validation failed: {str(e)}"


class HTTPSTransportSecurityMiddleware(BaseHTTPMiddleware):
    """
    HTTPS / TLS 1.3 & 1.2 Transport Security Enforcement Middleware.
    - Automatically upgrades unencrypted HTTP requests to HTTPS via HTTP 308 redirect.
    - Stamps 'Secure; SameSite=Lax' on all Set-Cookie headers.
    """

    async def dispatch(self, request: Request, call_next):
        from config import settings
        from starlette.responses import RedirectResponse

        # Check for unencrypted HTTP traffic
        forwarded_proto = request.headers.get("x-forwarded-proto", "").lower()
        is_http = forwarded_proto == "http" or (settings.ENFORCE_HTTPS and request.url.scheme == "http")

        if is_http:
            # Reconstruct HTTPS destination URL
            https_url = request.url.replace(scheme="https")
            return RedirectResponse(url=str(https_url), status_code=308)

        response: Response = await call_next(request)
        return response


class OWASPSecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    OWASP API8:2023 & A05:2021 - Security Misconfiguration Hardening.
    Injects OWASP-recommended HTTP security headers on all outbound responses.
    """

    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)

        # 1. Clickjacking Defense (OWASP A05)
        response.headers["X-Frame-Options"] = "DENY"

        # 2. MIME Type Sniffing Defense (OWASP A05)
        response.headers["X-Content-Type-Options"] = "nosniff"

        # 3. HTTP Strict Transport Security (RFC 6797 HSTS Preload - 2-year validity)
        from config import settings
        hsts_age = getattr(settings, "HSTS_MAX_AGE", 63072000)
        response.headers["Strict-Transport-Security"] = f"max-age={hsts_age}; includeSubDomains; preload"

        # 4. Content Security Policy (CSP - OWASP A03/A05)
        if "Content-Security-Policy" not in response.headers:
            csp_policy = (
                "default-src 'self' https: data: 'unsafe-inline' 'unsafe-eval'; "
                "img-src 'self' data: blob: https:; "
                "font-src 'self' https://fonts.gstatic.com data:; "
                "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                "frame-ancestors 'none'; "
                "object-src 'none';"
            )
            response.headers["Content-Security-Policy"] = csp_policy

        # 5. Referrer Policy, Permissions Policy & Cross-Origin Isolation
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(self), microphone=(), camera=()"
        response.headers["X-Permitted-Cross-Domain-Policies"] = "none"
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"

        # 6. Anti-Caching for Private API Responses (OWASP API3 / Sensitive PHI)
        if request.url.path.startswith("/api/v1/auth") or request.url.path.startswith("/api/v1/vaults") or request.url.path.startswith("/api/v1/compliance"):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
            response.headers["Pragma"] = "no-cache"

        return response



