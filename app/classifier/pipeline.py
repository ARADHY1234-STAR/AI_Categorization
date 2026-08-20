import asyncio
import logging
import threading
from typing import Dict, Optional, Tuple
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
from app.models.category import (
    CATEGORIES_REGISTRY,
    get_category_id_by_name,
    MISCELLANEOUS_CATEGORY_ID,
    MISCELLANEOUS_CATEGORY_NAME,
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

CATEGORIES_1_TO_10_NAMES = {
    meta.name.value for cat_id, meta in CATEGORIES_REGISTRY.items() if cat_id != 11
}


class DomainClassificationPipeline:
    """Two-Layer hierarchical domain classification pipeline orchestrator.

    Architecture:
    URL -> Normalizer -> DB Cache -> Brand Overrides -> Layer 1 HTTP Fetch -> Layer 2 LLM -> Confidence Threshold Validation -> DB Persistence
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

    @property
    def confidence_threshold(self) -> float:
        return self.settings.CONFIDENCE_THRESHOLD

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
            logger.info(f"[HTTP] Fetching metadata: {norm.fqdn}")
            fetch_result = await self.fetcher.fetch(raw_input)
            http_log_status = (
                fetch_result.http_status
                if fetch_result.http_status is not None
                else fetch_result.fetch_status.value
            )
            logger.info(f"[HTTP] Status: {http_log_status}")

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

            logger.info(f"[LLM] Classifying: {norm.fqdn}")
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

            threshold = self.confidence_threshold

            # 6. Backend Authoritative Confidence Threshold & Categorization Logic
            if llm_output and llm_output.category:
                candidate_category = llm_output.category
                candidate_conf = float(llm_output.confidence)

                logger.info(f"[LLM] Candidate: {candidate_category}")
                logger.info(f"[LLM] Confidence: {candidate_conf:.2f}")

                # Check if candidate is in Categories 1–10
                if candidate_category in CATEGORIES_1_TO_10_NAMES:
                    # If website had no meaningful content / failed to resolve, reject low/unsupported confidence
                    if not has_meaningful_content and candidate_conf < threshold:
                        logger.info(
                            f"[CLASSIFIER] Insufficient metadata/content and confidence {candidate_conf:.2f} < {threshold:.2f}"
                        )
                        logger.info("[CLASSIFIER] Assigned Category 11: Miscellaneous")
                        final_category = MISCELLANEOUS_CATEGORY_NAME
                        final_cat_id = MISCELLANEOUS_CATEGORY_ID
                        final_confidence = candidate_conf
                        final_status = ClassificationStatus.UNCLASSIFIED.value
                        final_rule = llm_output.rule_applied or "insufficient_metadata_fallback"
                        default_fallback_msg = (
                            "The domain failed to respond (request timed out) and returned no identifiable content or metadata, making classification into Categories 1-10 impossible."
                            if fetch_result.fetch_status == FetchStatus.TIMEOUT
                            else "The domain failed to resolve and returned no identifiable content or metadata, making classification into Categories 1-10 impossible."
                        )
                        final_reason = llm_output.reason or default_fallback_msg
                    elif candidate_conf >= threshold:
                        # ACCEPT Category 1-10
                        final_cat_id = get_category_id_by_name(candidate_category) or llm_output.category_id
                        logger.info(f"[CLASSIFIER] Accepted category {final_cat_id}")
                        final_category = candidate_category
                        final_confidence = candidate_conf
                        final_status = ClassificationStatus.CLASSIFIED.value
                        final_rule = llm_output.rule_applied or "general_taxonomy"
                        final_reason = llm_output.reason or f"Confidently classified into '{candidate_category}'."
                    else:
                        # LOW CONFIDENCE (< threshold): Category 11 Miscellaneous
                        logger.info(f"[CLASSIFIER] Confidence below {threshold:.2f}")
                        logger.info("[CLASSIFIER] Assigned Category 11: Miscellaneous")
                        final_category = MISCELLANEOUS_CATEGORY_NAME
                        final_cat_id = MISCELLANEOUS_CATEGORY_ID
                        final_confidence = candidate_conf
                        final_status = ClassificationStatus.LOW_CONFIDENCE.value
                        final_rule = llm_output.rule_applied or "confidence_threshold_fallback"
                        final_reason = (
                            llm_output.reason
                            or f"Confidence {candidate_conf:.2f} is below threshold {threshold:.2f} for candidate '{candidate_category}'. Assigned to Miscellaneous."
                        )
                elif candidate_category == MISCELLANEOUS_CATEGORY_NAME:
                    logger.info("[CLASSIFIER] Assigned Category 11: Miscellaneous")
                    final_category = MISCELLANEOUS_CATEGORY_NAME
                    final_cat_id = MISCELLANEOUS_CATEGORY_ID
                    final_confidence = candidate_conf
                    final_status = (
                        llm_output.status.value
                        if isinstance(llm_output.status, ClassificationStatus)
                        else str(llm_output.status or ClassificationStatus.CLASSIFIED.value)
                    )
                    final_rule = llm_output.rule_applied or "miscellaneous_classification"
                    final_reason = (
                        llm_output.reason
                        or "Available evidence is insufficient to confidently classify the domain into Categories 1–10."
                    )
                else:
                    # Invalid category returned by LLM: Safe fallback to Category 11
                    logger.warning(
                        f"[CLASSIFIER] Invalid category '{candidate_category}' returned. Safe fallback to Category 11: Miscellaneous."
                    )
                    logger.info("[CLASSIFIER] Assigned Category 11: Miscellaneous")
                    final_category = MISCELLANEOUS_CATEGORY_NAME
                    final_cat_id = MISCELLANEOUS_CATEGORY_ID
                    final_confidence = candidate_conf
                    final_status = ClassificationStatus.UNCLASSIFIED.value
                    final_rule = "invalid_category_fallback"
                    final_reason = f"Invalid category '{candidate_category}' returned by LLM. Safe fallback to Miscellaneous."
            else:
                # LLM could not determine category / returned null / unresolvable / error
                candidate_conf = float(llm_output.confidence) if llm_output else 0.0
                logger.info("[CLASSIFIER] Assigned Category 11: Miscellaneous")
                final_category = MISCELLANEOUS_CATEGORY_NAME
                final_cat_id = MISCELLANEOUS_CATEGORY_ID
                final_confidence = candidate_conf
                final_status = ClassificationStatus.UNCLASSIFIED.value
                final_rule = (llm_output.rule_applied if llm_output else None) or "unclassifiable"
                default_msg = (
                    "The domain failed to respond (request timed out) and returned no identifiable content or metadata, making classification into Categories 1-10 impossible."
                    if fetch_result.fetch_status == FetchStatus.TIMEOUT
                    else "The domain failed to resolve and returned no identifiable content or metadata, making classification into Categories 1-10 impossible."
                )
                final_reason = (llm_output.reason if (llm_output and llm_output.reason) else default_msg)

            # Persist classification result to database cache
            record = repo.save_classification(
                norm=norm,
                category=final_category,
                confidence=final_confidence,
                source=ClassificationSource.LLM_CATEGORIZER,
                status=final_status,
                enrichment_used=True,
                original_url=raw_input,
                final_url=fetch_result.final_url,
                metadata_fetch_status=fetch_result.fetch_status.value,
                http_status=fetch_result.http_status,
                metadata_used=metadata_used_dict,
                model_name=metadata.get("model"),
                rule_applied=final_rule,
                reason=final_reason,
            )
            return repo.to_response(record, original_url=raw_input)

        finally:
            if session_created and db_session is not None:
                db_session.close()
