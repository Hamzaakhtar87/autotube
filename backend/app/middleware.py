"""
Security middleware for rate limiting, headers, and error sanitization.
Uses in-memory token bucket - no external dependencies.
"""

import time
import os
from collections import defaultdict
from threading import Lock
from typing import Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


# ============================================================================
# RATE LIMITER (in-memory token bucket)
# ============================================================================

class RateLimitBucket:
    """Token bucket rate limiter per IP address."""

    def __init__(self, max_requests: int = 60, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window = window_seconds
        self.requests = defaultdict(list)
        self.lock = Lock()

    def is_allowed(self, key: str) -> bool:
        now = time.time()
        with self.lock:
            # Clean old entries
            self.requests[key] = [
                t for t in self.requests[key] if now - t < self.window
            ]
            if len(self.requests[key]) >= self.max_requests:
                return False
            self.requests[key].append(now)
            return True

    def remaining(self, key: str) -> int:
        now = time.time()
        with self.lock:
            active = [t for t in self.requests.get(key, []) if now - t < self.window]
            return max(0, self.max_requests - len(active))


# Global limiters
general_limiter = RateLimitBucket(max_requests=120, window_seconds=60)    # 120/min general
auth_limiter = RateLimitBucket(max_requests=10, window_seconds=60)        # 10/min auth
job_limiter = RateLimitBucket(max_requests=5, window_seconds=60)          # 5/min job creation


def get_client_ip(request: Request) -> str:
    """Extract real client IP from X-Forwarded-For or connection."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Apply rate limiting based on endpoint type."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        client_ip = get_client_ip(request)
        path = request.url.path.lower()

        # Skip health checks
        if path in ("/health", "/"):
            return await call_next(request)

        # Strict limit on auth endpoints (login/register)
        if path.startswith("/auth/"):
            if not auth_limiter.is_allowed(client_ip):
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Too many requests. Try again in a minute."}
                )

        # Strict limit on job creation
        elif path == "/jobs" and request.method == "POST":
            if not job_limiter.is_allowed(client_ip):
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Too many video generation requests. Please wait."}
                )

        # General rate limit
        else:
            if not general_limiter.is_allowed(client_ip):
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Rate limit exceeded. Slow down."}
                )

        response = await call_next(request)
        remaining = general_limiter.remaining(client_ip)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response


# ============================================================================
# SECURITY HEADERS
# ============================================================================

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"

        # HSTS only in production
        if os.getenv("ENVIRONMENT", "development") == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        return response


# ============================================================================
# ERROR SANITIZATION
# ============================================================================

class ErrorSanitizationMiddleware(BaseHTTPMiddleware):
    """Catch unhandled exceptions, never leak stack traces to users."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        try:
            return await call_next(request)
        except Exception:
            import logging
            logging.getLogger(__name__).exception("Unhandled error")
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal server error. Please try again later."}
            )
