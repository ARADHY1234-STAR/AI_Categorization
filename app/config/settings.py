from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    # OpenRouter LLM Configuration
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_MODEL: str = "google/gemini-3.7-flash"
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"

    # Classification Thresholds & Logic
    CLASSIFIER_CONFIDENCE_THRESHOLD: float = 0.80

    # Database
    DATABASE_URL: str = "sqlite:///data/domains.db"

    # HTTP Enrichment Controls
    ENRICHMENT_TIMEOUT_SECONDS: float = 5.0
    ENRICHMENT_MAX_RESPONSE_BYTES: int = 524288  # 512 KB
    ENRICHMENT_MAX_REDIRECTS: int = 3
    ENRICHMENT_USER_AGENT: str = (
        "DomainCategorizationBot/1.0 (+https://internal.service)"
    )
    ENRICHMENT_RESPECT_ROBOTS_TXT: bool = False
    ENRICHMENT_MAX_EXTRACT_CHARS: int = 4000

    # Paths
    BRAND_OVERRIDES_PATH: str = "data/brand_overrides.json"

    # Concurrency
    MAX_CONCURRENT_ENRICHMENTS: int = 20
    MAX_CONCURRENT_LLM_CALLS: int = 10

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache()
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
