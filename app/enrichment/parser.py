import json
import re
from typing import Any, Dict, List, Optional
from bs4 import BeautifulSoup
from app.models.schemas import StructuredMetadata


def sanitize_text(text: Optional[str], max_len: int = 500) -> Optional[str]:
    """Clean and sanitize untrusted text extracted from HTML.

    - Removes control characters and excessive whitespace.
    - Truncates to max_len.
    - Prevents prompt injection formatting tricks.
    """
    if not text:
        return None
    # Strip null bytes and non-printable control chars except standard whitespace
    cleaned = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", text)
    # Collapse excessive whitespaces and newlines
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if len(cleaned) > max_len:
        cleaned = cleaned[:max_len] + "..."
    return cleaned if cleaned else None


def parse_html_metadata(html_content: str, max_chars: int = 4000) -> StructuredMetadata:
    """Parse HTML and extract safe, structured Layer 1 metadata."""
    if not html_content or not html_content.strip():
        return StructuredMetadata(is_js_heavy=True)

    try:
        soup = BeautifulSoup(html_content, "html.parser")
    except Exception:
        return StructuredMetadata(is_js_heavy=True)

    # 1. Title
    title = None
    if soup.title and soup.title.string:
        title = sanitize_text(soup.title.string, max_len=250)

    # 2. Meta Tags, OpenGraph, and Canonical URL
    description = None
    og_title = None
    og_description = None
    site_name = None
    canonical_url = None

    for link in soup.find_all("link", rel=True):
        rel = [r.lower() for r in link.get("rel", [])]
        if "canonical" in rel and link.get("href"):
            canonical_url = sanitize_text(link.get("href"), max_len=300)
            break

    for meta in soup.find_all("meta"):
        name = meta.get("name", "").lower()
        prop = meta.get("property", "").lower()
        content = meta.get("content", "")

        if name == "description" and not description:
            description = sanitize_text(content, max_len=400)
        elif prop in ("og:title", "twitter:title") and not og_title:
            og_title = sanitize_text(content, max_len=250)
        elif prop in ("og:description", "twitter:description") and not og_description:
            og_description = sanitize_text(content, max_len=400)
        elif prop in ("og:site_name", "site_name") and not site_name:
            site_name = sanitize_text(content, max_len=150)

    # 3. Headings (h1, h2, h3 - up to 6 total)
    headings: List[str] = []
    for tag in soup.find_all(["h1", "h2", "h3"], limit=10):
        h_text = sanitize_text(tag.get_text(), max_len=150)
        if h_text and h_text not in headings:
            headings.append(h_text)
            if len(headings) >= 6:
                break

    # 4. Schema.org JSON-LD structured data
    structured_data: List[Dict[str, Any]] = []
    for script in soup.find_all("script", type="application/ld+json", limit=3):
        try:
            if script.string:
                raw_json = json.loads(script.string.strip())
                if isinstance(raw_json, dict):
                    filtered = {
                        k: str(v)[:200]
                        for k, v in raw_json.items()
                        if k in ("@type", "name", "description", "headline", "genre", "applicationCategory")
                    }
                    if filtered:
                        structured_data.append(filtered)
        except Exception:
            pass

    # 5. Extract Visible Text Sample
    for element in soup(["script", "style", "nav", "footer", "header", "noscript", "svg"]):
        element.extract()

    body_text = soup.get_text(separator=" ", strip=True)
    body_sample = sanitize_text(body_text, max_len=800)

    # 6. JS-heavy / SPA indicator
    is_js_heavy = False
    if not body_sample or len(body_sample) < 80:
        lower_html = html_content.lower()
        if any(
            marker in lower_html
            for marker in (
                "id=\"root\"", "id=\"app\"", "id=\"__next\"", "id=\"__nuxt\"",
                "enable javascript", "javascript is disabled", "noscript"
            )
        ):
            is_js_heavy = True

    return StructuredMetadata(
        title=title,
        description=description,
        og_title=og_title,
        og_description=og_description,
        site_name=site_name,
        canonical_url=canonical_url,
        headings=headings,
        structured_data=structured_data,
        body_sample=body_sample,
        is_js_heavy=is_js_heavy,
    )
