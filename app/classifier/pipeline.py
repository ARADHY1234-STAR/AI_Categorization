import asyncio
import logging
from typing import Dict, Optional
from sqlalchemy.orm import Session

from app.config.settings import Settings, get_settings
from app.database.connection import get_db_session
from app.database.repository import DomainRepository
from app.enrichment.fetcher import HTTPMetadataFetcher
from app.classifier.client import OpenRouterLLMClient
from app.classifier.prompts import (
    build_layer2_user_prompt,
    build_system_prompt,
)
from app.models.schemas import (
    ClassificationResponse,
    ClassificationSource,
    ClassificationStatus,
    FetchResult,
    FetchStatus,
    NormalizedDomain,
)
from app.normalization.normalizer import normalize_domain
from app.rules.overrides import BrandOverrideEngine

logger = logging.getLogger(__name__)


class DomainClassificationPipeline:
    """Two-Layer hierarchical domain classification pipeline orchestrator.

    Architecture:
    URL -> Normalizer -> DB Cache -> Brand Overrides -> Layer 1 HTTP Fetch -> Layer 2 LLM -> DB Persistence
    """

    def __init__(
        self,
        settings: Optional[Settings] = None,
        llm_client: Optional[OpenRouterLLMClient] = None,
        fetcher: Optional[HTTPMetadataFetcher] = None,
        override_engine: Optional[BrandOverrideEngine] = None,
    ):
        self.settings = settings or get_settings()
        self.llm_client = llm_client or OpenRouterLLMClient(self.settings)
        self.fetcher = fetcher or HTTPMetadataFetcher(self.settings)
        self.override_engine = (
            override_engine or BrandOverrideEngine(self.settings.BRAND_OVERRIDES_PATH)
        )
        self._in_flight_locks: Dict[str, asyncio.Lock] = {}
        self._lock_guard = asyncio.Lock()

    async def _get_domain_lock(self, fqdn: str) -> asyncio.Lock:
        """Single-flight lock for in-flight requests on the same domain."""
        async with self._lock_guard:
            if fqdn not in self._in_flight_locks:
                self._in_flight_locks[fqdn] = asyncio.Lock()
            return self._in_flight_locks[fqdn]

    async def classify(
        self,
        raw_input: str,
        subdomain: Optional[str] = None,
        app_name: Optional[str] = None,
        db_session: Optional[Session] = None,
        force_refresh: bool = False,
    ) -> ClassificationResponse:
        """Execute strict two-layer classification pipeline for a single URL or domain."""
        # 1. Initial Normalization
        norm = normalize_domain(
            raw_input=raw_input,
            explicit_subdomain=subdomain,
            app_name=app_name,
        )

        domain_lock = await self._get_domain_lock(norm.fqdn)
        async with domain_lock:
            session_created = False
            if db_session is None:
                db_session = get_db_session()
                session_created = True

            try:
                repo = DomainRepository(db_session)

                # 2. Database Lookup (Cache Hit)
                if not force_refresh:
                    existing = repo.get_by_fqdn(norm.fqdn)
                    if existing:
                        logger.info(
                            f"Database cache hit for '{norm.fqdn}' -> '{existing.category_name}' (source: {existing.classification_source})"
                        )
                        return repo.to_response(
                            existing,
                            source_override=ClassificationSource.DATABASE.value,
                            original_url=raw_input,
                        )

                # 3. Brand Override Table Lookup (F1 - zero token fast-path)
                override_match = self.override_engine.match(norm)
                if override_match and not force_refresh:
                    logger.info(
                        f"Brand override matched for '{norm.fqdn}' -> '{override_match.category}'"
                    )
                    repo.save_classification(
                        norm=norm,
                        category=override_match.category,
                        confidence=override_match.confidence,
                        source=ClassificationSource.BRAND_OVERRIDE,
                        status=override_match.status,
                        enrichment_used=False,
                        original_url=raw_input,
                        final_url=raw_input,
                        metadata_fetch_status="BYPASSED_OVERRIDE",
                        rule_applied="F1 / Brand Override",
                        reason=override_match.reason,
                    )
                    override_match.original_url = raw_input
                    return override_match

                # 4. LAYER 1: HTTP Metadata Fetcher (With redirect following & SSRF protection)
                logger.info(f"Layer 1: Fetching HTTP metadata for '{norm.fqdn}' ({raw_input})...")
                fetch_result = await self.fetcher.fetch(raw_input)

                # If redirect crossed domains, compute post-redirect normalized domain
                if fetch_result.final_url and fetch_result.final_url != raw_input:
                    try:
                        redirect_norm = normalize_domain(
                            raw_input=raw_input,
                            final_url=fetch_result.final_url,
                            app_name=app_name,
                        )
                        # Use final destination domain if valid
                        if redirect_norm.fqdn:
                            norm = redirect_norm
                    except Exception as e:
                        logger.debug(f"Post-redirect normalization notice: {e}")

                # Check if final redirected domain is in cache
                if not force_refresh:
                    existing_after_redirect = repo.get_by_fqdn(norm.fqdn)
                    if existing_after_redirect:
                        logger.info(f"Database cache hit for post-redirect domain '{norm.fqdn}'")
                        return repo.to_response(
                            existing_after_redirect,
                            source_override=ClassificationSource.DATABASE.value,
                            original_url=raw_input,
                        )

                # 5. LAYER 2: LLM Categorizer via OpenRouter
                system_prompt = build_system_prompt()
                user_prompt = build_layer2_user_prompt(norm, fetch_result)

                logger.info(f"Layer 2: Invoking LLM Categorizer for '{norm.fqdn}'...")
                llm_output, metadata = await self.llm_client.generate_classification(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                )

                metadata_used_dict = {
                    "title": fetch_result.metadata.title,
                    "description": fetch_result.metadata.description,
                    "og_title": fetch_result.metadata.og_title,
                    "og_description": fetch_result.metadata.og_description,
                    "site_name": fetch_result.metadata.site_name,
                    "canonical_url": fetch_result.metadata.canonical_url,
                    "headings": fetch_result.metadata.headings[:3] if fetch_result.metadata.headings else [],
                    "is_js_heavy": fetch_result.metadata.is_js_heavy,
                    "http_status": fetch_result.http_status,
                    "fetch_status": fetch_result.fetch_status.value,
                    "final_url": fetch_result.final_url,
                }

                has_meaningful_content = bool(
                    fetch_result.metadata.title
                    or fetch_result.metadata.description
                    or (fetch_result.metadata.headings and len(fetch_result.metadata.headings) > 0)
                    or (fetch_result.metadata.body_sample and len(fetch_result.metadata.body_sample.strip()) > 10)
                )

                if llm_output and llm_output.category:
                    # If domain is unresolvable / has no meaningful content and confidence is below threshold, treat as UNCLASSIFIED
                    if not has_meaningful_content and llm_output.confidence < self.settings.CLASSIFIER_CONFIDENCE_THRESHOLD:
                        logger.info(
                            f"Domain '{norm.fqdn}' has no meaningful content and confidence {llm_output.confidence:.2f} < {self.settings.CLASSIFIER_CONFIDENCE_THRESHOLD}. Returning UNCLASSIFIED (No Category Found)."
                        )
                        fallback_msg = (
                            "The domain timed out and returned no identifiable content or metadata, making classification impossible."
                            if fetch_result.fetch_status == FetchStatus.TIMEOUT
                            else "The domain failed to resolve and returned no identifiable content or metadata, making classification impossible."
                        )
                        unclass_reason = llm_output.reason or fallback_msg
                        return ClassificationResponse(
                            original_url=raw_input,
                            domain=norm.fqdn,
                            subdomain=norm.normalized_subdomain,
                            category="No Category Found",
                            category_id=None,
                            confidence=llm_output.confidence,
                            status=ClassificationStatus.UNCLASSIFIED.value,
                            source=ClassificationSource.LLM_CATEGORIZER.value,
                            rule_applied=llm_output.rule_applied or "unclassifiable",
                            reason=unclass_reason,
                            enrichment_used=True,
                            final_url=fetch_result.final_url,
                            http_status=fetch_result.http_status,
                            metadata_fetch_status=fetch_result.fetch_status.value,
                            metadata_used=metadata_used_dict,
                            model_name=metadata.get("model"),
                        )

                    # Enforce confidence threshold: Low-confidence items need review and are NOT cached to database
                    if llm_output.confidence < self.settings.CLASSIFIER_CONFIDENCE_THRESHOLD:
                        logger.info(
                            f"Layer 2 confidence {llm_output.confidence:.2f} < threshold {self.settings.CLASSIFIER_CONFIDENCE_THRESHOLD}. Flagged as NEEDS_REVIEW (Not saved to DB)."
                        )
                        # If confidence is very low (< 0.50) without strong evidence, treat as unclassified
                        is_very_low = llm_output.confidence < 0.50
                        cat_res = "No Category Found" if is_very_low else llm_output.category
                        cat_id_res = None if is_very_low else llm_output.category_id
                        status_res = ClassificationStatus.UNCLASSIFIED.value if is_very_low else ClassificationStatus.NEEDS_REVIEW.value

                        return ClassificationResponse(
                            original_url=raw_input,
                            domain=norm.fqdn,
                            subdomain=norm.normalized_subdomain,
                            category=cat_res,
                            category_id=cat_id_res,
                            confidence=llm_output.confidence,
                            status=status_res,
                            source=ClassificationSource.LLM_CATEGORIZER.value,
                            rule_applied=llm_output.rule_applied or "low_confidence_review",
                            reason=llm_output.reason or f"Low confidence ({llm_output.confidence:.2f} < {self.settings.CLASSIFIER_CONFIDENCE_THRESHOLD}) requiring human review.",
                            enrichment_used=True,
                            final_url=fetch_result.final_url,
                            http_status=fetch_result.http_status,
                            metadata_fetch_status=fetch_result.fetch_status.value,
                            metadata_used=metadata_used_dict,
                            model_name=metadata.get("model"),
                        )

                    # High confidence (>= threshold): Persist to database cache
                    logger.info(
                        f"Layer 2 classified '{norm.fqdn}' -> '{llm_output.category}' (confidence: {llm_output.confidence:.2f}, status: CLASSIFIED)"
                    )
                    record = repo.save_classification(
                        norm=norm,
                        category=llm_output.category,
                        confidence=llm_output.confidence,
                        source=ClassificationSource.LLM_CATEGORIZER,
                        status=ClassificationStatus.CLASSIFIED.value,
                        enrichment_used=True,
                        original_url=raw_input,
                        final_url=fetch_result.final_url,
                        metadata_fetch_status=fetch_result.fetch_status.value,
                        http_status=fetch_result.http_status,
                        metadata_used=metadata_used_dict,
                        model_name=metadata.get("model"),
                        rule_applied=llm_output.rule_applied,
                        reason=llm_output.reason,
                    )
                    return repo.to_response(record, original_url=raw_input)

                # Fallback / Unclassifiable (No category, unresolvable, or error) - Do NOT save to DB
                logger.warning(f"Could not classify '{norm.fqdn}'. Returning UNCLASSIFIED without saving to DB.")
                default_msg = (
                    "The domain timed out and returned no identifiable content or metadata, making classification impossible."
                    if fetch_result.fetch_status == FetchStatus.TIMEOUT
                    else "The domain failed to resolve and returned no identifiable content or metadata, making classification impossible."
                )
                fail_reason = (llm_output.reason if (llm_output and llm_output.reason) else default_msg)
                return ClassificationResponse(
                    original_url=raw_input,
                    domain=norm.fqdn,
                    subdomain=norm.normalized_subdomain,
                    category="No Category Found",
                    category_id=None,
                    confidence=llm_output.confidence if llm_output else 0.0,
                    status=ClassificationStatus.UNCLASSIFIED.value,
                    source=ClassificationSource.LLM_CATEGORIZER.value,
                    rule_applied=llm_output.rule_applied if llm_output else "unclassifiable",
                    reason=fail_reason,
                    enrichment_used=True,
                    final_url=fetch_result.final_url,
                    http_status=fetch_result.http_status,
                    metadata_fetch_status=fetch_result.fetch_status.value,
                    metadata_used=metadata_used_dict,
                    model_name=metadata.get("model"),
                )

            finally:
                if session_created and db_session is not None:
                    db_session.close()
