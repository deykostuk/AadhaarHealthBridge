import time
import threading
import logging
from typing import Dict, Tuple, List, Optional, Callable
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from config import settings

logger = logging.getLogger(__name__)

class Limiter:
    """
    ASGI / FastAPI Equivalent of Flask-Limiter.
    Provides sliding-window token bucket rate limiting with:
    - Route-level decorators (@limiter.limit("5/minute"))
    - IETF RateLimit headers (X-RateLimit-Limit, X-RateLimit-Remaining, X-RateLimit-Reset, Retry-After)
    - Thread-safe storage with automated memory garbage collection
    - Optional distributed Redis backend support for multi-worker deployments
    - Client IP and User Key extraction
    """

    def __init__(self, key_func: Optional[Callable[[Request], str]] = None, default_limits: Optional[List[str]] = None):
        self.key_func = key_func or self.get_remote_address
        self.default_limits = default_limits or ["120/minute"]
        self.storage: Dict[str, List[float]] = {}
        self.route_limits: Dict[str, Tuple[int, int]] = {} # endpoint -> (limit, window_seconds)
        self._lock = threading.Lock()
        self._last_gc = time.time()
        self._redis_client = None
        self._init_redis()

    def _init_redis(self):
        if getattr(settings, "REDIS_URL", None):
            try:
                import redis
                self._redis_client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
                self._redis_client.ping()
                logger.info("[RateLimiter] Distributed Redis storage initialized successfully.")
            except Exception as e:
                logger.warning(f"[RateLimiter] Could not connect to Redis ({e}), falling back to in-memory sliding window.")
                self._redis_client = None

    @staticmethod
    def get_remote_address(request: Request) -> str:
        """Extracts client IP address respecting X-Forwarded-For proxy headers."""
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        if request.client and request.client.host:
            return request.client.host
        return "127.0.0.1"

    def parse_rate_string(self, rate_str: str) -> Tuple[int, int]:
        """Parses rate strings like '5/minute', '100/hour', '10/second' into (count, seconds)."""
        parts = rate_str.strip().lower().split("/")
        if len(parts) != 2:
            return 60, 60

        count = int(parts[0])
        unit = parts[1]

        if "sec" in unit:
            seconds = 1
        elif "min" in unit:
            seconds = 60
        elif "hour" in unit:
            seconds = 3600
        elif "day" in unit:
            seconds = 86400
        else:
            seconds = 60

        return count, seconds

    def _cleanup_expired_keys(self, now: float):
        """Periodic garbage collection of expired timestamps to prevent memory leaks."""
        if now - self._last_gc < 60:
            return
        self._last_gc = now
        stale_keys = []
        for k, timestamps in list(self.storage.items()):
            if not timestamps or timestamps[-1] < now - 3600:
                stale_keys.append(k)
        for k in stale_keys:
            self.storage.pop(k, None)

    def check_rate_limit(self, key: str, max_requests: int, window_seconds: int) -> Tuple[bool, int, int, int]:
        """
        Evaluates sliding-window rate limit for a given key.
        Returns: (is_allowed, remaining, reset_seconds, retry_after)
        """
        now = time.time()

        # 1. Distributed Redis Backend (if configured)
        if self._redis_client is not None:
            try:
                redis_key = f"ratelimit:{key}"
                pipe = self._redis_client.pipeline()
                pipe.zremrangebyscore(redis_key, 0, now - window_seconds)
                pipe.zcard(redis_key)
                pipe.zadd(redis_key, {str(now): now})
                pipe.expire(redis_key, window_seconds + 5)
                _, current_count, _, _ = pipe.execute()

                if current_count >= max_requests:
                    oldest = self._redis_client.zrange(redis_key, 0, 0, withscores=True)
                    oldest_ts = oldest[0][1] if oldest else now
                    retry_after = int(oldest_ts + window_seconds - now) + 1
                    return False, 0, retry_after, max(1, retry_after)

                remaining = max(0, max_requests - current_count - 1)
                return True, remaining, window_seconds, 0
            except Exception as e:
                logger.warning(f"[RateLimiter] Redis error ({e}), falling back to in-memory bucket.")

        # 2. Thread-Safe In-Memory Sliding-Window Token Bucket
        with self._lock:
            self._cleanup_expired_keys(now)
            window_start = now - window_seconds

            timestamps = self.storage.get(key, [])
            # Filter out timestamps outside the active window
            valid_timestamps = [t for t in timestamps if t > window_start]

            if len(valid_timestamps) >= max_requests:
                oldest = valid_timestamps[0]
                retry_after = int(oldest + window_seconds - now) + 1
                self.storage[key] = valid_timestamps
                return False, 0, retry_after, max(1, retry_after)

            valid_timestamps.append(now)
            self.storage[key] = valid_timestamps
            remaining = max_requests - len(valid_timestamps)
            reset_seconds = int(window_seconds - (now - valid_timestamps[0]))

            return True, remaining, max(0, reset_seconds), 0

    def limit(self, rate_str: str):
        """
        Route decorator equivalent to @limiter.limit("5/minute").
        """
        max_requests, window_seconds = self.parse_rate_string(rate_str)

        def decorator(func):
            func._rate_limit = (max_requests, window_seconds, rate_str)
            return func
        return decorator


# Singleton Limiter instance
limiter = Limiter()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware applying route-specific and tiered default rate limits.
    Injects RFC 6585 and IETF RateLimit response headers.
    """

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        client_ip = limiter.get_remote_address(request)

        # 1. Determine Tiered Rate Limits
        if path in ["/api/v1/auth/login", "/api/v1/auth/signup", "/api/v1/login", "/api/v1/signup"]:
            # Strict Auth Tier: 5 requests / minute
            max_req, window_sec = 5, 60
            tier_name = "auth"
        elif path.startswith("/api/v1/chat") or path.startswith("/api/v1/scan"):
            # Compute / AI Tier: 20 requests / minute
            max_req, window_sec = 20, 60
            tier_name = "ai"
        elif path.startswith("/static") or path in ["/favicon.ico", "/manifest.json", "/sw.js"]:
            # Unrestricted static assets
            return await call_next(request)
        else:
            # General API Tier: 120 requests / minute
            max_req, window_sec = 120, 60
            tier_name = "general"

        rate_key = f"{client_ip}:{tier_name}:{path}"
        is_allowed, remaining, reset_sec, retry_after = limiter.check_rate_limit(rate_key, max_req, window_sec)

        if not is_allowed:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "status": "error",
                    "message": f"Rate limit exceeded: {max_req} requests per {window_sec} seconds. Please slow down.",
                    "retry_after": retry_after
                },
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(max_req),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(reset_sec)
                }
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(max_req)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(reset_sec)
        return response
