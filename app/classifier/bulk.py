import asyncio
import csv
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from sqlalchemy.orm import Session

from app.config.settings import Settings, get_settings
from app.database.connection import get_db_session
from app.database.repository import DomainRepository
from app.classifier.pipeline import DomainClassificationPipeline
from app.models.schemas import ClassificationResponse, ClassificationSource, NormalizedDomain
from app.normalization.normalizer import normalize_domain

logger = logging.getLogger(__name__)


@dataclass
class BulkSummary:
    total_input_rows: int
    unique_domains_count: int
    cached_hits_count: int
    brand_override_count: int
    llm_classified_count: int
    miscellaneous_count: int
    error_count: int
    processing_time_seconds: float


class BulkClassifier:
    """High-throughput batch classifier with deduplication, per-host politeness, and DB caching."""

    def __init__(
        self,
        pipeline: Optional[DomainClassificationPipeline] = None,
        settings: Optional[Settings] = None,
    ):
        self.settings = settings or get_settings()
        self.pipeline = pipeline or DomainClassificationPipeline(self.settings)

    async def process_items(
        self,
        items: List[Dict[str, Optional[str]]],
        db_session: Optional[Session] = None,
    ) -> Tuple[List[ClassificationResponse], BulkSummary]:
        """Process a list of input dictionaries with deduplication and two-layer classification."""
        start_time = time.time()
        total_input_rows = len(items)
        if total_input_rows == 0:
            return [], BulkSummary(0, 0, 0, 0, 0, 0, 0, 0.0)

        # 1. Normalization & Deduplication
        unique_fqdns: Dict[str, NormalizedDomain] = {}
        row_to_fqdn: List[str] = []

        for idx, item in enumerate(items):
            raw = item.get("domain") or item.get("url") or ""
            sub = item.get("subdomain")
            app = item.get("app_name") or item.get("application") or item.get("website")

            if not raw or not raw.strip():
                row_to_fqdn.append("")
                continue

            try:
                norm = normalize_domain(raw, explicit_subdomain=sub, app_name=app)
                row_to_fqdn.append(norm.fqdn)
                if norm.fqdn not in unique_fqdns:
                    unique_fqdns[norm.fqdn] = norm
            except Exception as e:
                logger.warning(f"Row {idx} normalization failed for '{raw}': {e}")
                row_to_fqdn.append("")

        unique_count = len(unique_fqdns)
        logger.info(
            f"Bulk classification: {total_input_rows} rows deduplicated to {unique_count} unique domains"
        )

        session_created = False
        if db_session is None:
            db_session = get_db_session()
            session_created = True

        try:
            repo = DomainRepository(db_session)

            # 2. Batch Database Lookup (Cache Hit check)
            cached_records = repo.get_many_by_fqdns(list(unique_fqdns.keys()))
            classification_results: Dict[str, ClassificationResponse] = {}

            cached_hits = 0
            unresolved_norms: List[NormalizedDomain] = []

            for fqdn, norm in unique_fqdns.items():
                if fqdn in cached_records:
                    rec = cached_records[fqdn]
                    classification_results[fqdn] = repo.to_response(
                        rec,
                        source_override=ClassificationSource.DATABASE.value,
                        original_url=norm.raw_input,
                    )
                    cached_hits += 1
                else:
                    # 3. Check Brand Override (F1 fast-path)
                    override_match = self.pipeline.override_engine.match(norm)
                    if override_match:
                        repo.save_classification(
                            norm=norm,
                            category=override_match.category,
                            confidence=override_match.confidence,
                            source=ClassificationSource.BRAND_OVERRIDE,
                            status=override_match.status,
                            original_url=norm.raw_input,
                            final_url=norm.raw_input,
                            metadata_fetch_status="BYPASSED_OVERRIDE",
                            rule_applied="F1 / Brand Override",
                            reason=override_match.reason,
                        )
                        override_match.original_url = norm.raw_input
                        classification_results[fqdn] = override_match
                    else:
                        unresolved_norms.append(norm)

            override_hits = len(unique_fqdns) - cached_hits - len(unresolved_norms)
            logger.info(
                f"Resolved from DB Cache: {cached_hits}, Brand Overrides: {override_hits}. "
                f"Unresolved domains requiring Layer 1 & 2: {len(unresolved_norms)}"
            )

            # 4. Asynchronous Concurrent Classification with Worker Pool
            semaphore = asyncio.Semaphore(self.settings.MAX_CONCURRENT_LLM_CALLS)

            async def process_single_norm(norm_item: NormalizedDomain):
                async with semaphore:
                    try:
                        res = await self.pipeline.classify(
                            raw_input=norm_item.raw_input,
                            subdomain=norm_item.normalized_subdomain,
                            app_name=norm_item.app_name,
                            db_session=db_session,
                        )
                        return norm_item.fqdn, res
                    except Exception as e:
                        logger.error(f"Error classifying {norm_item.fqdn}: {e}")
                        fallback = ClassificationResponse(
                            original_url=norm_item.raw_input,
                            domain=norm_item.fqdn,
                            subdomain=norm_item.normalized_subdomain,
                            category=None,
                            category_id=None,
                            source="error",
                            confidence=0.0,
                            status="ERROR",
                            reason=str(e),
                        )
                        return norm_item.fqdn, fallback

            if unresolved_norms:
                tasks = [process_single_norm(norm) for norm in unresolved_norms]
                resolved_items = await asyncio.gather(*tasks)
                for fqdn, resp in resolved_items:
                    classification_results[fqdn] = resp

            # Metrics
            llm_classified = sum(
                1 for r in classification_results.values()
                if r.source == ClassificationSource.LLM_CATEGORIZER.value and r.category_id in range(1, 11)
            )
            misc_count = sum(
                1 for r in classification_results.values()
                if r.category_id == 11 or r.category == "Miscellaneous"
            )
            error_count = sum(
                1 for r in classification_results.values()
                if r.status in ("ERROR", "UNKNOWN")
            )

            # 5. Map classifications back to every original input row
            final_responses: List[ClassificationResponse] = []
            for idx, fqdn in enumerate(row_to_fqdn):
                if fqdn and fqdn in classification_results:
                    final_responses.append(classification_results[fqdn])
                else:
                    final_responses.append(
                        ClassificationResponse(
                            original_url=items[idx].get("domain", ""),
                            domain=items[idx].get("domain", ""),
                            category="Miscellaneous",
                            category_id=11,
                            source="error",
                            confidence=0.0,
                            status="ERROR",
                            reason="Invalid or empty input domain",
                        )
                    )

            duration = time.time() - start_time
            summary = BulkSummary(
                total_input_rows=total_input_rows,
                unique_domains_count=unique_count,
                cached_hits_count=cached_hits,
                brand_override_count=override_hits,
                llm_classified_count=llm_classified,
                miscellaneous_count=misc_count,
                error_count=error_count,
                processing_time_seconds=round(duration, 2),
            )

            return final_responses, summary

        finally:
            if session_created and db_session is not None:
                db_session.close()

    async def process_csv(
        self,
        input_csv_path: str,
        output_csv_path: Optional[str] = None,
    ) -> Tuple[List[ClassificationResponse], BulkSummary]:
        """Read URLs from CSV, run deduplicated bulk classification, and save results."""
        path = Path(input_csv_path)
        if not path.exists():
            raise FileNotFoundError(f"CSV file not found at: {input_csv_path}")

        items: List[Dict[str, Optional[str]]] = []
        with open(path, mode="r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                clean_row = {k.strip().lower(): v.strip() if v else None for k, v in row.items() if k}
                domain_val = clean_row.get("url") or clean_row.get("domain") or clean_row.get("website")
                subdomain_val = clean_row.get("subdomain")
                app_val = clean_row.get("app_name") or clean_row.get("application") or clean_row.get("website") or clean_row.get("name")
                if domain_val:
                    items.append({
                        "domain": domain_val,
                        "subdomain": subdomain_val,
                        "app_name": app_val,
                    })

        results, summary = await self.process_items(items)

        if output_csv_path:
            out_path = Path(output_csv_path)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with open(out_path, mode="w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "original_url",
                    "normalized_fqdn",
                    "final_url",
                    "category",
                    "category_id",
                    "confidence",
                    "source",
                    "status",
                    "rule_applied",
                    "metadata_fetch_status",
                    "reason",
                ])
                for res in results:
                    writer.writerow([
                        res.original_url or "",
                        res.domain,
                        res.final_url or "",
                        res.category or "",
                        res.category_id or "",
                        f"{res.confidence:.2f}",
                        res.source,
                        res.status,
                        res.rule_applied or "",
                        res.metadata_fetch_status or "",
                        res.reason or "",
                    ])
            logger.info(f"Wrote {len(results)} bulk results to {output_csv_path}")

        return results, summary
