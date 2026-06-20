"""Input sanitization utilities.

Provides defense-in-depth sanitization beyond Pydantic validation.
Handles HTML escaping, dangerous pattern stripping, and length enforcement.
"""

import html
import re

# Precompiled patterns — compiled once, O(1) reuse
_XSS_PATTERNS: list[re.Pattern] = [
    re.compile(r"<script[^>]*>.*?</script>", re.IGNORECASE | re.DOTALL),
    re.compile(r"javascript\s*:", re.IGNORECASE),
    re.compile(r"on\w+\s*=", re.IGNORECASE),
    re.compile(r"eval\s*\(", re.IGNORECASE),
    re.compile(r"expression\s*\(", re.IGNORECASE),
    re.compile(r"data\s*:\s*text/html", re.IGNORECASE),
    re.compile(r"vbscript\s*:", re.IGNORECASE),
]

_SQL_INJECTION_PATTERNS: list[re.Pattern] = [
    re.compile(
        r"\b(UNION\s+SELECT|DROP\s+TABLE|INSERT\s+INTO|DELETE\s+FROM)\b",
        re.IGNORECASE,
    ),
    re.compile(r"(--|;|/\*|\*/)", re.IGNORECASE),
    re.compile(r"'\s*(OR|AND)\s+'", re.IGNORECASE),
]


def sanitize_html(text: str, max_length: int = 2000) -> str:
    """Sanitize text by escaping HTML entities and stripping XSS vectors.

    Args:
        text: Raw user input string.
        max_length: Maximum allowed character length.

    Returns:
        Sanitized string safe for rendering.
    """
    if not text:
        return ""

    # Truncate first to avoid processing oversized input
    truncated = text[:max_length]

    # Strip XSS patterns before escaping
    cleaned = truncated
    for pattern in _XSS_PATTERNS:
        cleaned = pattern.sub("", cleaned)

    # HTML-escape remaining content
    escaped = html.escape(cleaned, quote=True)

    return escaped.strip()


def check_sql_injection(text: str) -> bool:
    """Check if text contains SQL injection patterns.

    Args:
        text: Input string to check.

    Returns:
        True if suspicious SQL patterns detected.
    """
    return any(pattern.search(text) for pattern in _SQL_INJECTION_PATTERNS)


def sanitize_filename(filename: str) -> str:
    """Sanitize a filename to prevent path traversal attacks.

    Args:
        filename: Raw filename string.

    Returns:
        Safe filename with only alphanumeric, dash, underscore, dot.
    """
    # Remove path separators and null bytes
    safe = re.sub(r"[/\\:\x00]", "", filename)
    # Keep only safe characters
    safe = re.sub(r"[^a-zA-Z0-9._-]", "_", safe)
    # Prevent hidden files
    safe = safe.lstrip(".")
    return safe[:255] if safe else "unnamed"
