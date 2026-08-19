import pytest
from app.enrichment.parser import parse_html_metadata, sanitize_text
from app.enrichment.ssrf import is_ip_blocked, is_safe_url, resolve_and_validate_hostname


def test_ssrf_blocks_private_and_metadata_ips():
    # Loopback
    assert is_ip_blocked("127.0.0.1") is True
    assert is_ip_blocked("127.0.1.1") is True
    assert is_ip_blocked("::1") is True

    # Cloud Metadata (AWS, GCP, Azure, DigitalOcean)
    assert is_ip_blocked("169.254.169.254") is True
    assert is_ip_blocked("169.254.1.1") is True

    # Private IPv4 ranges
    assert is_ip_blocked("10.0.0.1") is True
    assert is_ip_blocked("10.255.255.255") is True
    assert is_ip_blocked("172.16.0.1") is True
    assert is_ip_blocked("172.31.255.255") is True
    assert is_ip_blocked("192.168.1.1") is True

    # Public Safe IPs
    assert is_ip_blocked("8.8.8.8") is False
    assert is_ip_blocked("1.1.1.1") is False
    assert is_ip_blocked("142.250.190.46") is False


def test_ssrf_blocks_dangerous_hostnames():
    is_safe, ips, err = resolve_and_validate_hostname("localhost")
    assert is_safe is False
    assert "Blocked" in err

    is_safe_u, err_u = is_safe_url("http://127.0.0.1:8000/secret")
    assert is_safe_u is False

    is_safe_meta, err_meta = is_safe_url("http://169.254.169.254/latest/meta-data/")
    assert is_safe_meta is False


def test_html_metadata_parsing():
    sample_html = """
    <!DOCTYPE html>
    <html>
      <head>
        <title>FastAPI - Modern High-Performance Python Web Framework</title>
        <meta name="description" content="FastAPI framework, high performance, easy to learn, fast to code, ready for production">
        <meta property="og:title" content="FastAPI Framework">
        <meta property="og:description" content="Build APIs with Python 3.8+">
        <script type="application/ld+json">
          {"@type": "SoftwareApplication", "name": "FastAPI", "description": "Web framework"}
        </script>
      </head>
      <body>
        <h1>FastAPI Documentation</h1>
        <h2>Key Features</h2>
        <p>FastAPI is a modern, fast (high-performance), web framework for building APIs with Python.</p>
      </body>
    </html>
    """
    data = parse_html_metadata(sample_html)
    assert data.title == "FastAPI - Modern High-Performance Python Web Framework"
    assert "FastAPI framework" in (data.description or "")
    assert data.og_title == "FastAPI Framework"
    assert "FastAPI Documentation" in data.headings
    assert data.is_js_heavy is False
    assert len(data.structured_data) > 0


def test_js_heavy_detection():
    spa_html = """
    <!DOCTYPE html>
    <html>
      <head><title>Loading React App...</title></head>
      <body>
        <div id="root"></div>
        <noscript>You need to enable JavaScript to run this app.</noscript>
      </body>
    </html>
    """
    data = parse_html_metadata(spa_html)
    assert data.is_js_heavy is True


def test_text_sanitization_removes_control_chars_and_truncates():
    dirty_text = "Hello\x00World!\x08\x0e  This   is a    test.  " + ("A" * 1000)
    cleaned = sanitize_text(dirty_text, max_len=50)
    assert "\x00" not in cleaned
    assert len(cleaned) <= 53  # 50 + '...'
    assert cleaned.startswith("HelloWorld! This is a test. AAA")
