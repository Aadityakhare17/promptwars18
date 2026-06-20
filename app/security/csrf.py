"""CSRF protection using double-submit cookie pattern.

Generates a CSRF token, sets it as a cookie, and validates
that the token in the request header matches the cookie value.
"""

import secrets

from fastapi import Request, Response
from starlette.middleware.base import (
    BaseHTTPMiddleware,
    RequestResponseEndpoint,
)
from starlette.responses import JSONResponse

# CSRF-exempt paths (read-only endpoints and static files)
_EXEMPT_PATHS: frozenset[str] = frozenset(
    {
        "/",
        "/api/health",
        "/api/csrf-token",
        "/docs",
        "/openapi.json",
    }
)

_SAFE_METHODS: frozenset[str] = frozenset({"GET", "HEAD", "OPTIONS"})

_CSRF_COOKIE_NAME = "csrf_token"
_CSRF_HEADER_NAME = "x-csrf-token"


def generate_csrf_token() -> str:
    """Generate a cryptographically secure CSRF token.

    Returns:
        Hex-encoded 32-byte random token.
    """
    return secrets.token_hex(32)


def _constant_time_compare(val1: str, val2: str) -> bool:
    """Compare two strings in constant time to prevent timing attacks.

    Args:
        val1: First string.
        val2: Second string.

    Returns:
        True if strings match.
    """
    return hmac_compare(val1.encode(), val2.encode())


def hmac_compare(a: bytes, b: bytes) -> bool:
    """Constant-time byte comparison using hashlib.

    Args:
        a: First byte string.
        b: Second byte string.

    Returns:
        True if byte strings match.
    """
    # Use hmac.compare_digest for constant-time comparison
    import hmac

    return hmac.compare_digest(a, b)


class CSRFMiddleware(BaseHTTPMiddleware):
    """CSRF protection middleware using double-submit cookie pattern."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """Validate CSRF token for state-changing requests.

        Args:
            request: Incoming HTTP request.
            call_next: Next middleware/handler.

        Returns:
            Response or 403 if CSRF validation fails.
        """
        # Skip CSRF for safe methods and exempt paths
        if request.method in _SAFE_METHODS:
            response = await call_next(request)
            # Set CSRF cookie on GET requests if not present
            # (except for the /api/csrf-token endpoint)
            if (
                _CSRF_COOKIE_NAME not in request.cookies
                and request.url.path != "/api/csrf-token"
            ):
                token = generate_csrf_token()
                is_secure = (request.url.scheme == "https") or (
                    request.headers.get("x-forwarded-proto") == "https"
                )
                response.set_cookie(
                    key=_CSRF_COOKIE_NAME,
                    value=token,
                    httponly=False,  # JS needs to read this
                    samesite="strict",
                    secure=is_secure,
                    max_age=3600,
                )
            return response

        # Skip CSRF for exempt paths
        if request.url.path in _EXEMPT_PATHS:
            return await call_next(request)

        # Skip CSRF for static files
        if request.url.path.startswith("/static"):
            return await call_next(request)

        # Validate CSRF token
        cookie_token = request.cookies.get(_CSRF_COOKIE_NAME)
        header_token = request.headers.get(_CSRF_HEADER_NAME)

        if not cookie_token or not header_token:
            return JSONResponse(
                status_code=403,
                content={"detail": "CSRF token missing"},
            )

        if not _constant_time_compare(cookie_token, header_token):
            return JSONResponse(
                status_code=403,
                content={"detail": "CSRF token mismatch"},
            )

        return await call_next(request)
