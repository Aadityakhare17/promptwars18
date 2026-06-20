"""Unit tests for input sanitization utilities."""

from app.security.sanitizer import (
    check_sql_injection,
    sanitize_filename,
    sanitize_html,
)


def test_sanitize_html_empty():
    """Verify empty input returns empty string."""
    assert sanitize_html("") == ""
    assert sanitize_html(None) == ""


def test_sanitize_html_normal():
    """Verify safe strings are preserved and trimmed."""
    assert sanitize_html("  Hello World!  ") == "Hello World!"


def test_sanitize_html_truncation():
    """Verify inputs are truncated to max_length."""
    text = "a" * 100
    assert sanitize_html(text, max_length=10) == "a" * 10


def test_sanitize_html_xss_patterns():
    """Verify XSS patterns are stripped."""
    assert "<script>" not in sanitize_html("<script>alert('xss')</script>")
    assert "javascript:" not in sanitize_html("javascript:alert(1)")
    assert "onerror=" not in sanitize_html("<img src=x onerror=alert(1)>")
    assert "eval(" not in sanitize_html("eval('alert(1)')")
    assert "expression(" not in sanitize_html("expression(alert(1))")
    assert "data:text/html" not in sanitize_html("data:text/html,<html>")
    assert "vbscript:" not in sanitize_html("vbscript:alert(1)")


def test_sanitize_html_escaping():
    """Verify special HTML characters are escaped."""
    assert (
        sanitize_html("<div>Hello & Welcome</div>")
        == "&lt;div&gt;Hello &amp; Welcome&lt;/div&gt;"
    )
    assert sanitize_html("Hello 'World'") == "Hello &#x27;World&#x27;"
    assert sanitize_html('Hello "World"') == "Hello &quot;World&quot;"


def test_check_sql_injection_safe():
    """Verify safe strings do not trigger SQL injection warnings."""
    assert check_sql_injection("select a seat") is False
    assert check_sql_injection("drop the mic") is False


def test_check_sql_injection_unsafe():
    """Verify SQL injection patterns are caught."""
    assert check_sql_injection("UNION SELECT username, password FROM users") is True
    assert check_sql_injection("DROP TABLE users;") is True
    assert check_sql_injection("INSERT INTO logs VALUES (1)") is True
    assert check_sql_injection("DELETE FROM orders") is True
    assert check_sql_injection("admin' OR '1'='1") is True
    assert check_sql_injection("select * from user; -- comment") is True
    assert check_sql_injection("select * from user/* comment */") is True


def test_sanitize_filename_normal():
    """Verify safe filenames are unchanged."""
    assert sanitize_filename("report.pdf") == "report.pdf"
    assert sanitize_filename("carbon-stats_2026.csv") == "carbon-stats_2026.csv"


def test_sanitize_filename_path_traversal():
    """Verify path traversal characters are removed or replaced."""
    # / and \ and : and \x00 are stripped
    assert sanitize_filename("../../etc/passwd") == "etcpasswd"
    assert sanitize_filename("..\\..\\windows\\system32") == "windowssystem32"
    assert sanitize_filename("C:\\file.txt") == "Cfile.txt"


def test_sanitize_filename_invalid_chars():
    """Verify invalid characters are replaced with underscores."""
    assert sanitize_filename("my*file?.txt") == "my_file_.txt"
    assert sanitize_filename("hello world.txt") == "hello_world.txt"


def test_sanitize_filename_leading_dots():
    """Verify leading dots are removed to prevent hidden files."""
    assert sanitize_filename(".hidden_file.txt") == "hidden_file.txt"
    assert sanitize_filename("...") == "unnamed"


def test_sanitize_filename_empty_or_dots():
    """Verify empty or invalid names fallback to 'unnamed'."""
    assert sanitize_filename("") == "unnamed"
    assert sanitize_filename("/") == "unnamed"


def test_sanitize_filename_long():
    """Verify filename is truncated to 255 characters."""
    long_name = "a" * 300 + ".txt"
    sanitized = sanitize_filename(long_name)
    assert len(sanitized) == 255
    assert sanitized.endswith("a")
