"""Token bucket rate limiter middleware.

Provides per-IP rate limiting with configurable limits.
Uses in-memory storage — suitable for single-instance deployments.
"""

import time
from collections import defaultdict
from dataclasses import dataclass, field

from fastapi import Request, Response
from starlette.middleware.base import (
    BaseHTTPMiddleware,
    RequestResponseEndpoint,
)
from starlette.responses import JSONResponse

from app.config import settings


@dataclass
class TokenBucket:
    """Token bucket for rate limiting a single client."""

    capacity: int
    tokens: float = 0.0
    last_refill: float = field(default_factory=time.monotonic)

    def __post_init__(self) -> None:
        """Initialize tokens to full capacity."""
        self.tokens = float(self.capacity)

    def consume(self, refill_rate_per_second: float) -> bool:
        """Try to consume one token. Returns True if allowed.

        Args:
            refill_rate_per_second: Rate at which tokens refill.

        Returns:
            True if request is allowed, False if rate limited.
        """
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.last_refill = now

        # Refill tokens based on elapsed time
        self.tokens = min(
            self.capacity,
            self.tokens + elapsed * refill_rate_per_second,
        )

        if self.tokens >= 1.0:
            self.tokens -= 1.0
            return True
        return False


class RateLimiterMiddleware(BaseHTTPMiddleware):
    """Per-IP rate limiting middleware using token bucket algorithm."""

    def __init__(self, app: object) -> None:
        """Initialize rate limiter with config settings."""
        super().__init__(app)
        self._buckets: dict[str, TokenBucket] = defaultdict(
            lambda: TokenBucket(capacity=settings.rate_limit.requests_per_minute)
        )
        self._chat_buckets: dict[str, TokenBucket] = defaultdict(
            lambda: TokenBucket(capacity=settings.rate_limit.chat_requests_per_minute)
        )
        self._refill_rate = settings.rate_limit.requests_per_minute / 60.0
        self._chat_refill_rate = settings.rate_limit.chat_requests_per_minute / 60.0

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP from request, handling proxies.

        Args:
            request: Incoming HTTP request.

        Returns:
            Client IP address string.
        """
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            # Take the first IP (original client)
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """Process request through rate limiter.

        Args:
            request: Incoming HTTP request.
            call_next: Next middleware/handler in chain.

        Returns:
            Response or 429 if rate limited.
        """
        # Skip rate limiting for static files
        if request.url.path.startswith("/static"):
            return await call_next(request)

        client_ip = self._get_client_ip(request)
        is_chat = request.url.path == "/api/chat"

        if is_chat:
            bucket = self._chat_buckets[client_ip]
            allowed = bucket.consume(self._chat_refill_rate)
        else:
            bucket = self._buckets[client_ip]
            allowed = bucket.consume(self._refill_rate)

        if not allowed:
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Try again later."},
                headers={"Retry-After": "60"},
            )

        return await call_next(request)
