import pytest
from app.normalization.normalizer import normalize_domain


def test_required_normalization_cases():
    # Exact required tests from prompt
    res1 = normalize_domain("https://www.youtube.com/watch?v=123")
    assert res1.fqdn == "youtube.com"
    assert res1.normalized_domain == "youtube.com"
    assert res1.normalized_subdomain is None
    assert res1.is_subdomain is False

    res2 = normalize_domain("https://mail.google.com/some/path")
    assert res2.fqdn == "mail.google.com"
    assert res2.normalized_domain == "google.com"
    assert res2.normalized_subdomain == "mail"
    assert res2.is_subdomain is True

    res3 = normalize_domain("https://docs.google.com/document/d/123")
    assert res3.fqdn == "docs.google.com"
    assert res3.normalized_domain == "google.com"
    assert res3.normalized_subdomain == "docs"
    assert res3.is_subdomain is True


def test_subdomain_preservation_tb6():
    res_drive = normalize_domain("https://drive.google.com/drive/my-drive")
    assert res_drive.fqdn == "drive.google.com"
    assert res_drive.normalized_subdomain == "drive"

    res_onedrive = normalize_domain("http://onedrive.live.com")
    assert res_onedrive.fqdn == "onedrive.live.com"
    assert res_onedrive.normalized_subdomain == "onedrive"


def test_stripping_ports_queries_fragments_casing():
    res = normalize_domain("HTTPS://WWW.Example.COM:8080/path/to/page?param=val#section")
    assert res.fqdn == "example.com"
    assert res.normalized_domain == "example.com"


def test_www_subdomain_handling():
    res = normalize_domain("https://www.docs.google.com")
    assert res.fqdn == "docs.google.com"
    assert res.normalized_subdomain == "docs"


def test_explicit_subdomain_param():
    res = normalize_domain("google.com", explicit_subdomain="docs", app_name="Google Docs")
    assert res.fqdn == "docs.google.com"
    assert res.normalized_subdomain == "docs"
    assert res.app_name == "Google Docs"


def test_empty_input_raises_value_error():
    with pytest.raises(ValueError):
        normalize_domain("   ")
