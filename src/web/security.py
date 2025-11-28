"""
Security utilities and middleware for the FastAPI application.

This module provides:
- CSRF protection
- Security headers
- Rate limiting
- Input validation
- Security logging

OWASP Top 10 2021 Coverage:
- A01:2021 - Broken Access Control
- A02:2021 - Cryptographic Failures
- A03:2021 - Injection
- A05:2021 - Security Misconfiguration
- A07:2021 - Identification and Authentication Failures
"""

import logging
import os
import secrets
import time
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Callable, Dict, Optional

from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

# Security Logging Setup
security_logger = logging.getLogger("security")
security_logger.setLevel(logging.INFO)
handler = logging.FileHandler("security.log")
handler.setFormatter(
    logging.Formatter("%(asctime)s - %(levelname)s - %(message)s - %(extra)s")
)
security_logger.addHandler(handler)


# ============ CSRF PROTECTION ============


def generate_csrf_token() -> str:
    """
    Generate a cryptographically secure CSRF token.

    Returns:
        str: 32-byte URL-safe token
    """
    return secrets.token_urlsafe(32)


def get_csrf_token(request: Request) -> str:
    """
    Get or create CSRF token for the session.

    Args:
        request: FastAPI request object with session

    Returns:
        str: CSRF token for this session
    """
    if "csrf_token" not in request.session:
        request.session["csrf_token"] = generate_csrf_token()
    return request.session["csrf_token"]


def verify_csrf_token(request: Request, token: str) -> bool:
    """
    Verify CSRF token from form matches session token.

    Uses constant-time comparison to prevent timing attacks.

    Args:
        request: FastAPI request object
        token: Token from form submission

    Returns:
        bool: True if token is valid

    Raises:
        HTTPException: 403 if token is invalid
    """
    session_token = request.session.get("csrf_token")
    if not session_token or not secrets.compare_digest(session_token, token):
        security_logger.warning(
            f"CSRF validation failed",
            extra={
                "path": request.url.path,
                "method": request.method,
                "ip": request.client.host if request.client else "unknown",
            },
        )
        raise HTTPException(status_code=403, detail="CSRF token validation failed")
    return True


# ============ SECURITY HEADERS MIDDLEWARE ============


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Add security headers to all responses.

    Implements OWASP Secure Headers Project recommendations:
    - Content-Security-Policy
    - X-Frame-Options
    - X-Content-Type-Options
    - X-XSS-Protection
    - Strict-Transport-Security (in production)
    - Referrer-Policy
    - Permissions-Policy
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Add security headers to response."""
        response = await call_next(request)

        # SECURITY: Content Security Policy - restrict resource loading
        # Relaxed for development with Tailwind CDN and external resources
        # In production, consider hosting these assets yourself
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com https://unpkg.com; "
            "style-src 'self' 'unsafe-inline' https://unpkg.com; "
            "img-src 'self' data: https:; "
            "font-src 'self' data:; "
            "connect-src 'self'; "
            "frame-ancestors 'none';"
        )

        # SECURITY: Prevent clickjacking attacks (OWASP: A05)
        response.headers["X-Frame-Options"] = "DENY"

        # SECURITY: Prevent MIME type sniffing (OWASP: A05)
        response.headers["X-Content-Type-Options"] = "nosniff"

        # SECURITY: Enable XSS protection in older browsers (OWASP: A03)
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # SECURITY: Enforce HTTPS in production (OWASP: A02)
        if os.getenv("RAILWAY_ENVIRONMENT"):
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains; preload"
            )

        # SECURITY: Control referrer information
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # SECURITY: Permissions policy - disable unnecessary features
        response.headers["Permissions-Policy"] = (
            "geolocation=(), microphone=(), camera=()"
        )

        return response


# ============ RATE LIMITING ============


class RateLimiter:
    """
    Simple in-memory rate limiter.

    SECURITY NOTE: In production, use Redis or similar for distributed rate limiting.

    Protects against:
    - Brute force attacks (OWASP: A07)
    - DoS attacks
    - API abuse
    """

    def __init__(self, requests: int = 100, window: int = 60):
        """
        Initialize rate limiter.

        Args:
            requests: Maximum requests allowed per window
            window: Time window in seconds
        """
        self.requests = requests
        self.window = window
        self.clients: Dict[str, list] = defaultdict(list)

    def is_allowed(self, client_id: str) -> bool:
        """
        Check if client is allowed to make request.

        Args:
            client_id: Unique client identifier (usually IP address)

        Returns:
            bool: True if request is allowed
        """
        now = time.time()
        # Clean old entries
        self.clients[client_id] = [
            req_time for req_time in self.clients[client_id] if now - req_time < self.window
        ]

        if len(self.clients[client_id]) >= self.requests:
            security_logger.warning(
                f"Rate limit exceeded for client {client_id}",
                extra={"client_id": client_id, "requests": len(self.clients[client_id])},
            )
            return False

        self.clients[client_id].append(now)
        return True


# Global rate limiter instances
rate_limiter = RateLimiter(requests=100, window=60)  # 100 requests per minute
strict_rate_limiter = RateLimiter(requests=10, window=60)  # 10 requests per minute for sensitive endpoints


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware."""

    def __init__(self, app, limiter: RateLimiter):
        super().__init__(app)
        self.limiter = limiter

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Check rate limit before processing request."""
        client_id = request.client.host if request.client else "unknown"

        if not self.limiter.is_allowed(client_id):
            return Response(
                content="Rate limit exceeded. Please try again later.",
                status_code=429,
                headers={"Retry-After": "60"},
            )

        return await call_next(request)


# ============ INPUT VALIDATION ============


def sanitize_html_input(text: str) -> str:
    """
    Sanitize HTML input to prevent XSS attacks.

    Note: Jinja2 auto-escaping should handle most cases,
    but this provides defense in depth.

    Args:
        text: User input text

    Returns:
        str: Sanitized text with dangerous characters escaped
    """
    if not text:
        return text

    # Replace dangerous characters
    replacements = {
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#x27;",
        "&": "&amp;",
    }

    for char, replacement in replacements.items():
        text = text.replace(char, replacement)

    return text


def validate_place_id(place_id: str) -> bool:
    """
    Validate Google Place ID format.

    Args:
        place_id: Place ID to validate

    Returns:
        bool: True if valid format

    Raises:
        HTTPException: 400 if invalid format
    """
    # Place IDs are typically alphanumeric with underscores and hyphens
    if not place_id or len(place_id) > 500:
        raise HTTPException(status_code=400, detail="Invalid place_id format")

    # Check for SQL injection attempts or other malicious patterns
    dangerous_patterns = ["--", ";", "/*", "*/", "xp_", "sp_", "DROP", "DELETE", "INSERT"]
    place_id_upper = place_id.upper()

    for pattern in dangerous_patterns:
        if pattern in place_id_upper:
            security_logger.error(
                f"Potential SQL injection attempt in place_id: {place_id}",
                extra={"place_id": place_id},
            )
            raise HTTPException(status_code=400, detail="Invalid place_id format")

    return True


def validate_pagination(page: int, limit: int) -> tuple[int, int]:
    """
    Validate and sanitize pagination parameters.

    Args:
        page: Page number
        limit: Items per page

    Returns:
        tuple: Validated (page, limit)
    """
    # Prevent negative or excessive pagination
    page = max(1, min(page, 10000))
    limit = max(1, min(limit, 1000))

    return page, limit


# ============ SECURITY AUDIT LOGGING ============


def log_security_event(
    event_type: str,
    request: Request,
    details: Optional[Dict] = None,
    severity: str = "INFO",
):
    """
    Log security-relevant events.

    Args:
        event_type: Type of security event
        request: FastAPI request object
        details: Additional event details
        severity: Log severity (INFO, WARNING, ERROR)
    """
    log_data = {
        "event_type": event_type,
        "timestamp": datetime.utcnow().isoformat(),
        "path": request.url.path,
        "method": request.method,
        "ip": request.client.host if request.client else "unknown",
        "user_agent": request.headers.get("user-agent", "unknown"),
    }

    if details:
        log_data.update(details)

    log_method = getattr(security_logger, severity.lower(), security_logger.info)
    log_method(f"Security Event: {event_type}", extra=log_data)


# ============ API KEY VALIDATION ============


def mask_api_key(api_key: str, visible_chars: int = 8) -> str:
    """
    Mask an API key for safe display.

    Args:
        api_key: Full API key
        visible_chars: Number of characters to show

    Returns:
        str: Masked key (e.g., "AIzaSyD••••••••")
    """
    if not api_key or len(api_key) < visible_chars:
        return ""
    return api_key[:visible_chars] + "•" * 12


def is_masked_key(value: str) -> bool:
    """
    Check if a value is a masked key.

    Args:
        value: Value to check

    Returns:
        bool: True if value contains mask characters
    """
    return "•" in value or "*" in value
