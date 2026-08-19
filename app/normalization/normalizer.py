import json
import logging
import re
from pathlib import Path
from urllib.parse import urlparse
from typing import Optional, Set
import tldextract

from app.models.schemas import NormalizedDomain

logger = logging.getLogger(__name__)

# Configure tldextract without automatic network fetches for offline stability and speed
_extract = tldextract.TLDExtract(suffix_list_urls=(), cache_dir=None)

# Default lists
DEFAULT_MEANINGFUL_SUBDOMAINS = {
    "docs", "drive", "sheets", "slides", "forms", "mail", "calendar",
    "meet", "teams", "onedrive", "outlook", "sharepoint", "workspace",
    "portal", "app", "dashboard", "admin", "console", "api", "dev", "cloud"
}

DEFAULT_COLLAPSED_SUBDOMAINS = {
    "www", "www1", "www2", "www3", "m", "mobile", "web", "en", "us", "global"
}


class SubdomainConfigManager:
    """Manages configurable list of meaningful vs default-collapsed subdomains."""

    def __init__(self, config_path: Optional[str] = "data/meaningful_subdomains.json"):
        self.config_path = config_path
        self.meaningful_subdomains: Set[str] = set(DEFAULT_MEANINGFUL_SUBDOMAINS)
        self.collapsed_subdomains: Set[str] = set(DEFAULT_COLLAPSED_SUBDOMAINS)
        self._load_config()

    def _load_config(self) -> None:
        if not self.config_path:
            return
        path = Path(self.config_path)
        if not path.exists():
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if "meaningful_subdomains" in data:
                self.meaningful_subdomains = {s.lower().strip() for s in data["meaningful_subdomains"]}
            if "default_collapsed_subdomains" in data:
                self.collapsed_subdomains = {s.lower().strip() for s in data["default_collapsed_subdomains"]}
        except Exception as e:
            logger.warning(f"Could not load meaningful_subdomains config from {self.config_path}: {e}")

    def is_meaningful(self, sub: str) -> bool:
        if not sub:
            return False
        sub_lower = sub.lower().strip()
        if sub_lower in self.collapsed_subdomains:
            return False
        # If in explicit list or not a generic www/m prefix
        return True


subdomain_manager = SubdomainConfigManager()


def normalize_domain(
    raw_input: str,
    explicit_subdomain: Optional[str] = None,
    app_name: Optional[str] = None,
    final_url: Optional[str] = None,
) -> NormalizedDomain:
    """Normalize input domain/URL into clean domain, subdomain, and FQDN.

    Handles:
    - Stripping schemes (http://, https://, etc.)
    - Stripping default/collapsed subdomains (www, www1, m, etc.)
    - Preserving meaningful subdomains (per TB6 and configurable table)
    - Stripping ports, query params, fragments, userinfo, trailing slashes
    - Discarding URL paths (per TB4)
    - Post-redirect resolution if final_url is provided
    - Lowercasing and striping whitespace

    Examples:
    - https://www.youtube.com/watch?v=123 -> fqdn: youtube.com
    - https://mail.google.com/some/path -> fqdn: mail.google.com
    - https://docs.google.com/document/d/123 -> fqdn: docs.google.com
    - drive.google.com -> fqdn: drive.google.com
    """
    target_input = final_url if final_url and final_url.strip() else raw_input
    if not target_input or not target_input.strip():
        raise ValueError("Domain input cannot be empty")

    text = target_input.strip().lower()

    # Prepend scheme if not present to ensure standard urlparse behavior
    if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", text):
        text_with_scheme = "http://" + text
    else:
        text_with_scheme = text

    parsed = urlparse(text_with_scheme)

    # Netloc contains host[:port] and userinfo@
    netloc = parsed.netloc or parsed.path.split("/")[0]

    # Strip userinfo (user:pass@)
    if "@" in netloc:
        netloc = netloc.split("@", 1)[1]

    # Strip port (:8080)
    if ":" in netloc:
        netloc = netloc.split(":", 1)[0]

    netloc = netloc.strip().rstrip(".").strip("/")

    # If explicit subdomain was passed separately
    if explicit_subdomain and explicit_subdomain.strip():
        explicit_sub = explicit_subdomain.strip().lower().rstrip(".").strip("/")
        if not netloc.startswith(explicit_sub + "."):
            netloc = f"{explicit_sub}.{netloc}"

    # Extract using tldextract
    extracted = _extract(netloc)
    root_domain = f"{extracted.domain}.{extracted.suffix}".strip(".")
    raw_subdomain = extracted.subdomain.strip(".")

    # Filter subdomain parts against collapsed subdomains
    if raw_subdomain:
        sub_parts = raw_subdomain.split(".")
        filtered_sub_parts = [
            p for p in sub_parts if p not in subdomain_manager.collapsed_subdomains and not re.match(r"^www\d*$", p)
        ]
        subdomain = ".".join(filtered_sub_parts)
    else:
        subdomain = None

    if subdomain:
        fqdn = f"{subdomain}.{root_domain}"
        is_subdomain = True
    else:
        fqdn = root_domain
        subdomain = None
        is_subdomain = False

    # Edge-case fallback
    if not fqdn or fqdn == ".":
        cleaned = re.sub(r"^www\d*\.", "", netloc)
        fqdn = cleaned
        root_domain = cleaned
        subdomain = None
        is_subdomain = False

    return NormalizedDomain(
        raw_input=raw_input,
        normalized_domain=root_domain,
        normalized_subdomain=subdomain,
        fqdn=fqdn,
        is_subdomain=is_subdomain,
        app_name=app_name.strip() if app_name and app_name.strip() else None,
    )
