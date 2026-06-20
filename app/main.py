"""FastAPI application entry point.

Configures middleware stack (security headers, CORS, rate limiting, CSRF),
registers API routes, and serves the static frontend.
"""

import logging
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import (
    BaseHTTPMiddleware,
    RequestResponseEndpoint,
)

from app.config import settings
from app.models import HealthResponse
from app.routes import auth, carbon, chat, insights
from app.security.csrf import CSRFMiddleware, generate_csrf_token
from app.security.rate_limiter import RateLimiterMiddleware
from app.services.http_client import close_http_client


class CachedStaticFiles(StaticFiles):
    """StaticFiles subclass that appends Cache-Control headers for asset caching."""

    def file_response(self, *args, **kwargs) -> Response:
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = "public, max-age=31536000"
        return response


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Resolve static files directory
_STATIC_DIR = Path(__file__).parent / "static"


# --- Security Headers Middleware ---


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses.

    Implements OWASP recommended headers to prevent:
    - XSS (Content-Security-Policy)
    - Clickjacking (X-Frame-Options)
    - MIME sniffing (X-Content-Type-Options)
    - Information leakage (Server, X-Powered-By)
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """Add security headers to response.

        Args:
            request: Incoming request.
            call_next: Next handler.

        Returns:
            Response with security headers.
        """
        response = await call_next(request)

        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=()"
        )
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data:; "
            "connect-src 'self'"
        )
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains; preload"
        )
        # Remove server identification headers
        if "Server" in response.headers:
            del response.headers["Server"]
        if "X-Powered-By" in response.headers:
            del response.headers["X-Powered-By"]

        return response


# --- Request Size Limiter ---


class RequestSizeLimiterMiddleware(BaseHTTPMiddleware):
    """Limit request body size to prevent DoS via payload inflation."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """Check content length before processing.

        Args:
            request: Incoming request.
            call_next: Next handler.

        Returns:
            Response or 413 if body too large.
        """
        content_length = request.headers.get("content-length")
        if content_length:
            if int(content_length) > settings.max_request_body_bytes:
                return JSONResponse(
                    status_code=413,
                    content={"detail": "Request body too large"},
                )
        return await call_next(request)


# --- Application Factory ---


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        Configured FastAPI instance.
    """
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "Platform to understand, track, and reduce your "
            "carbon footprint through personalized insights."
        ),
        docs_url="/docs" if settings.debug else None,
        redoc_url=None,
    )

    # --- Middleware Stack (applied bottom-up) ---
    # Order matters: outermost middleware runs first

    # 1. CORS — must be outermost
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "X-CSRF-Token"],
        max_age=3600,
    )

    # 2. Security headers
    app.add_middleware(SecurityHeadersMiddleware)

    # 3. Request size limiter
    app.add_middleware(RequestSizeLimiterMiddleware)

    # 4. Rate limiter
    app.add_middleware(RateLimiterMiddleware)

    # 5. CSRF protection
    app.add_middleware(CSRFMiddleware)

    # --- Routes ---
    app.include_router(auth.router)
    app.include_router(carbon.router)
    app.include_router(chat.router)
    app.include_router(insights.router)

    @app.on_event("shutdown")
    async def shutdown_event():
        """Shutdown event handler to clean up resources."""
        await close_http_client()

    # --- Health Check ---
    @app.get(
        "/api/health",
        response_model=HealthResponse,
        tags=["system"],
        summary="Health check",
    )
    async def health_check() -> HealthResponse:
        """Return application health status."""
        return HealthResponse(version=settings.app_version)

    # --- CSRF Token Endpoint ---
    @app.get(
        "/api/csrf-token",
        tags=["system"],
        summary="Get CSRF token",
    )
    async def get_csrf_token(request: Request, response: Response) -> dict:
        """Generate and return a CSRF token.

        Sets the token as a cookie and returns it in the response body
        so the frontend can include it in request headers.
        """
        token = generate_csrf_token()
        is_secure = (request.url.scheme == "https") or (
            request.headers.get("x-forwarded-proto") == "https"
        )
        response.set_cookie(
            key="csrf_token",
            value=token,
            httponly=False,
            samesite="strict",
            secure=is_secure,
            max_age=3600,
        )
        return {"csrf_token": token}

    # --- Google Analytics Configuration Endpoint ---
    @app.get(
        "/api/analytics/config",
        tags=["system"],
        summary="Get Google Analytics configuration",
    )
    async def get_analytics_config() -> dict:
        """Return Google Analytics measurement ID for client integration."""
        return {
            "ga_measurement_id": settings.google.ga_measurement_id,
            "simulator_enabled": settings.google.auth_simulator_enabled,
        }

    # --- Static Files ---
    if _STATIC_DIR.exists():
        app.mount(
            "/static",
            CachedStaticFiles(directory=str(_STATIC_DIR)),
            name="static",
        )

        @app.get("/", include_in_schema=False)
        async def serve_index() -> FileResponse:
            """Serve the main frontend page."""
            response = FileResponse(str(_STATIC_DIR / "index.html"))
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            return response

    logger.info(
        "Application started: %s v%s",
        settings.app_name,
        settings.app_version,
    )

    return app


# Create the application instance
app = create_app()
