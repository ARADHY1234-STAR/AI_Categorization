from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator
from app.models.category import ALLOWED_CATEGORY_NAMES, get_category_id_by_name


class ClassificationStatus(str, Enum):
    CLASSIFIED = "CLASSIFIED"
    UNKNOWN = "UNKNOWN"
    ERROR = "ERROR"
    OVERRIDE = "OVERRIDE"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class ClassificationSource(str, Enum):
    DATABASE = "database"
    BRAND_OVERRIDE = "brand_override"
    LLM_CATEGORIZER = "llm_categorizer"
    HUMAN_OVERRIDE = "human_override"


class FetchStatus(str, Enum):
    SUCCESS = "SUCCESS"
    TIMEOUT = "TIMEOUT"
    SSRF_BLOCKED = "SSRF_BLOCKED"
    DNS_FAILURE = "DNS_FAILURE"
    HTTP_ERROR = "HTTP_ERROR"
    ERROR = "ERROR"


class NormalizedDomain(BaseModel):
    raw_input: str
    normalized_domain: str
    normalized_subdomain: Optional[str] = None
    fqdn: str  # fully qualified normalized domain (e.g. docs.google.com or youtube.com)
    is_subdomain: bool = False
    app_name: Optional[str] = None
    final_url: Optional[str] = None


class StructuredMetadata(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    og_title: Optional[str] = None
    og_description: Optional[str] = None
    site_name: Optional[str] = None
    canonical_url: Optional[str] = None
    headings: List[str] = Field(default_factory=list)
    structured_data: List[Dict[str, Any]] = Field(default_factory=list)
    body_sample: Optional[str] = None
    is_js_heavy: bool = False


class FetchResult(BaseModel):
    url: str
    domain: str
    http_status: Optional[int] = None
    final_url: Optional[str] = None
    fetch_status: FetchStatus
    metadata: StructuredMetadata = Field(default_factory=StructuredMetadata)
    error_message: Optional[str] = None


class LLMClassificationOutput(BaseModel):
    """Strict output schema expected from LLM."""
    domain: str
    category_id: Optional[int] = None
    category: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0)
    reason: Optional[str] = None
    rule_applied: Optional[str] = None
    status: ClassificationStatus = ClassificationStatus.CLASSIFIED

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        if v not in ALLOWED_CATEGORY_NAMES:
            raise ValueError(f"Category '{v}' is not one of the 10 allowed categories: {ALLOWED_CATEGORY_NAMES}")
        return v

    def model_post_init(self, __context: Any) -> None:
        if self.category and not self.category_id:
            self.category_id = get_category_id_by_name(self.category)


class ClassificationResponse(BaseModel):
    """API & Pipeline classification response model."""
    original_url: Optional[str] = None
    domain: str
    subdomain: Optional[str] = None
    category: Optional[str] = None
    category_id: Optional[int] = None
    confidence: float = 0.0
    status: str = "CLASSIFIED"
    source: str
    reason: Optional[str] = None
    rule_applied: Optional[str] = None
    enrichment_used: bool = False
    final_url: Optional[str] = None
    http_status: Optional[int] = None
    metadata_fetch_status: Optional[str] = None
    metadata_used: Optional[Dict[str, Any]] = None
    model_name: Optional[str] = None


class BatchClassifyRequest(BaseModel):
    domains: List[str]
    app_names: Optional[List[Optional[str]]] = None


class ClassifyRequest(BaseModel):
    domain: str
    subdomain: Optional[str] = None
    app_name: Optional[str] = None
