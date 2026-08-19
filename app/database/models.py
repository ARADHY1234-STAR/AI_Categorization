from datetime import datetime, timezone
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    JSON,
    String,
    Text,
)
from app.database.connection import Base


def utcnow():
    return datetime.now(timezone.utc)


class DomainClassificationModel(Base):
    """Database model for storing domain classification records with migration support."""

    __tablename__ = "domain_classifications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    original_url = Column(String(1024), nullable=True)
    final_url = Column(String(1024), nullable=True)

    normalized_domain = Column(String(255), nullable=False, index=True)
    normalized_subdomain = Column(String(255), nullable=True, index=True)
    fqdn = Column(String(512), nullable=False, unique=True, index=True)

    category_id = Column(Integer, nullable=True)
    category_name = Column(String(100), nullable=True)
    confidence = Column(Float, nullable=False, default=0.0)
    status = Column(String(50), nullable=False, default="CLASSIFIED")

    classification_source = Column(String(50), nullable=False)
    is_human_override = Column(Boolean, nullable=False, default=False)
    enrichment_used = Column(Boolean, nullable=False, default=False)

    metadata_fetch_status = Column(String(50), nullable=True)
    http_status = Column(Integer, nullable=True)
    metadata_used = Column(JSON, nullable=True)

    model_name = Column(String(100), nullable=True)
    model_version = Column(String(50), nullable=True)
    rule_applied = Column(String(100), nullable=True)
    rule_version = Column(String(50), nullable=True)

    reason = Column(Text, nullable=True)
    evidence_summary = Column(JSON, nullable=True)

    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    def __repr__(self):
        return (
            f"<DomainClassification fqdn='{self.fqdn}' "
            f"category='{self.category_name}' source='{self.classification_source}' "
            f"confidence={self.confidence}>"
        )
