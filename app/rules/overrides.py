import json
import logging
from pathlib import Path
from typing import Dict, Optional
from pydantic import BaseModel

from app.models.category import CategoryEnum, get_category_id_by_name
from app.models.schemas import ClassificationResponse, ClassificationSource, NormalizedDomain

logger = logging.getLogger(__name__)


class BrandOverrideEntry(BaseModel):
    domain: str
    category: str
    reason: str = "Brand override rule"


class BrandOverrideEngine:
    """Fast, in-memory brand override table loaded from configuration."""

    def __init__(self, override_file_path: Optional[str] = None):
        self.override_file_path = override_file_path
        self._overrides: Dict[str, BrandOverrideEntry] = {}
        if override_file_path:
            self.load_from_file(override_file_path)

    def load_from_file(self, file_path: str) -> None:
        path = Path(file_path)
        if not path.exists():
            logger.warning(f"Brand overrides file not found at: {file_path}")
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            overrides = data.get("overrides", [])
            for item in overrides:
                entry = BrandOverrideEntry(**item)
                # Store normalized domain key (lower case, stripped)
                self._overrides[entry.domain.lower().strip()] = entry
            logger.info(f"Loaded {len(self._overrides)} brand overrides from {file_path}")
        except Exception as e:
            logger.error(f"Failed to load brand overrides from {file_path}: {e}")

    def add_override(self, domain: str, category: str, reason: str = "Dynamic override") -> None:
        key = domain.lower().strip()
        self._overrides[key] = BrandOverrideEntry(domain=key, category=category, reason=reason)

    def match(self, norm: NormalizedDomain) -> Optional[ClassificationResponse]:
        """Check if normalized domain or FQDN matches a brand override."""
        # 1. Exact FQDN match (e.g. docs.google.com or youtube.com)
        entry = self._overrides.get(norm.fqdn)
        
        # 2. If subdomain was not specifically overridden, match root domain ONLY if not a functional subdomain
        # Per F1 and TB6: meaningful subdomains must not blindly inherit root override if it changes function.
        # But if root domain is in override table and norm is not a subdomain, it matches.
        if not entry and not norm.is_subdomain:
            entry = self._overrides.get(norm.normalized_domain)

        if entry:
            cat_id = get_category_id_by_name(entry.category)
            if cat_id is not None:
                return ClassificationResponse(
                    domain=norm.fqdn,
                    subdomain=norm.normalized_subdomain,
                    category=entry.category,
                    category_id=cat_id,
                    source=ClassificationSource.BRAND_OVERRIDE.value,
                    confidence=1.0,
                    status="CLASSIFIED",
                    enrichment_used=False,
                    rule_applied="F1 / Brand Override",
                    reason=entry.reason,
                )
        return None
