import logging
from typing import Any, Dict, List, Optional
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.database.models import DomainClassificationModel, utcnow
from app.models.category import get_category_id_by_name
from app.models.schemas import ClassificationResponse, ClassificationSource, NormalizedDomain

logger = logging.getLogger(__name__)


class DomainRepository:
    """Data access layer for domain classifications with human-override safety and auto-migration."""

    def __init__(self, db: Session):
        self.db = db
        self._ensure_schema_migrated()

    def _ensure_schema_migrated(self) -> None:
        """Lightweight SQLite schema migration helper to add new columns if they do not exist."""
        try:
            # Check existing columns in table
            result = self.db.execute(text("PRAGMA table_info(domain_classifications)"))
            existing_cols = {row[1] for row in result.fetchall()}
            if not existing_cols:
                return

            columns_to_add = [
                ("original_url", "VARCHAR(1024)"),
                ("final_url", "VARCHAR(1024)"),
                ("enrichment_used", "BOOLEAN DEFAULT 0"),
                ("metadata_fetch_status", "VARCHAR(50)"),
                ("http_status", "INTEGER"),
                ("metadata_used", "JSON"),
                ("rule_applied", "VARCHAR(100)"),
            ]

            for col_name, col_type in columns_to_add:
                if col_name not in existing_cols:
                    logger.info(f"Migrating database: adding column '{col_name}'")
                    self.db.execute(text(f"ALTER TABLE domain_classifications ADD COLUMN {col_name} {col_type}"))
            self.db.commit()
        except Exception as e:
            # Not fatal if already exists or non-sqlite
            logger.debug(f"Schema check/migration notice: {e}")

    def get_by_fqdn(self, fqdn: str) -> Optional[DomainClassificationModel]:
        """Fetch classification record by exact FQDN."""
        return (
            self.db.query(DomainClassificationModel)
            .filter(DomainClassificationModel.fqdn == fqdn.lower().strip())
            .first()
        )

    def get_many_by_fqdns(self, fqdns: List[str]) -> Dict[str, DomainClassificationModel]:
        """Batch lookup for multiple FQDNs."""
        cleaned_fqdns = [f.lower().strip() for f in fqdns]
        records = (
            self.db.query(DomainClassificationModel)
            .filter(DomainClassificationModel.fqdn.in_(cleaned_fqdns))
            .all()
        )
        return {r.fqdn: r for r in records}

    def delete_by_fqdn(self, fqdn: str) -> bool:
        """Delete classification record by exact FQDN. Returns True if deleted, False if not found."""
        record = self.get_by_fqdn(fqdn)
        if record:
            self.db.delete(record)
            self.db.commit()
            return True
        return False

    def save_classification(
        self,
        norm: NormalizedDomain,
        category: Optional[str],
        confidence: float,
        source: ClassificationSource,
        status: str = "CLASSIFIED",
        enrichment_used: bool = False,
        original_url: Optional[str] = None,
        final_url: Optional[str] = None,
        metadata_fetch_status: Optional[str] = None,
        http_status: Optional[int] = None,
        metadata_used: Optional[Dict[str, Any]] = None,
        model_name: Optional[str] = None,
        model_version: Optional[str] = None,
        rule_applied: Optional[str] = None,
        rule_version: Optional[str] = None,
        reason: Optional[str] = None,
        evidence_summary: Optional[dict] = None,
        is_human_override: bool = False,
        **kwargs: Any,
    ) -> DomainClassificationModel:
        """Save or update classification record, strictly protecting human overrides."""
        existing = self.get_by_fqdn(norm.fqdn)
        cat_id = get_category_id_by_name(category) if category else None

        if existing:
            # Human override protection
            if existing.is_human_override and not is_human_override:
                logger.warning(
                    f"Blocked automated overwrite of human override for {norm.fqdn}. "
                    f"Preserved category: {existing.category_name}"
                )
                return existing

            existing.category_id = cat_id
            existing.category_name = category
            existing.confidence = confidence
            existing.status = status
            existing.classification_source = source.value
            existing.enrichment_used = enrichment_used
            if original_url:
                existing.original_url = original_url
            if final_url:
                existing.final_url = final_url
            if metadata_fetch_status:
                existing.metadata_fetch_status = metadata_fetch_status
            if http_status is not None:
                existing.http_status = http_status
            if metadata_used:
                existing.metadata_used = metadata_used
            if model_name:
                existing.model_name = model_name
            if model_version:
                existing.model_version = model_version
            if rule_applied:
                existing.rule_applied = rule_applied
            if rule_version:
                existing.rule_version = rule_version
            if reason:
                existing.reason = reason
            if evidence_summary:
                existing.evidence_summary = evidence_summary
            if is_human_override:
                existing.is_human_override = True

            existing.updated_at = utcnow()
            self.db.commit()
            self.db.refresh(existing)
            return existing
        else:
            new_record = DomainClassificationModel(
                original_url=original_url or norm.raw_input,
                final_url=final_url,
                normalized_domain=norm.normalized_domain,
                normalized_subdomain=norm.normalized_subdomain,
                fqdn=norm.fqdn,
                category_id=cat_id,
                category_name=category,
                confidence=confidence,
                status=status,
                classification_source=source.value,
                is_human_override=is_human_override,
                enrichment_used=enrichment_used,
                metadata_fetch_status=metadata_fetch_status,
                http_status=http_status,
                metadata_used=metadata_used,
                model_name=model_name,
                model_version=model_version,
                rule_applied=rule_applied,
                rule_version=rule_version,
                reason=reason,
                evidence_summary=evidence_summary,
            )
            self.db.add(new_record)
            self.db.commit()
            self.db.refresh(new_record)
            return new_record

    def to_response(
        self,
        record: DomainClassificationModel,
        source_override: Optional[str] = None,
        original_url: Optional[str] = None,
    ) -> ClassificationResponse:
        return ClassificationResponse(
            original_url=original_url or record.original_url or record.fqdn,
            domain=record.fqdn,
            subdomain=record.normalized_subdomain,
            category=record.category_name,
            category_id=record.category_id,
            source=source_override or record.classification_source,
            confidence=record.confidence,
            status=record.status,
            reason=record.reason,
            rule_applied=record.rule_applied or record.rule_version,
            enrichment_used=bool(record.enrichment_used) if record.enrichment_used is not None else False,
            final_url=record.final_url,
            http_status=record.http_status,
            metadata_fetch_status=record.metadata_fetch_status,
            metadata_used=record.metadata_used or record.evidence_summary,
            model_name=record.model_name,
        )
