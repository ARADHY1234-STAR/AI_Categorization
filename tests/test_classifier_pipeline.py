import pytest
from unittest.mock import AsyncMock, MagicMock
from app.classifier.client import OpenRouterLLMClient
from app.classifier.pipeline import DomainClassificationPipeline
from app.enrichment.fetcher import HTTPMetadataFetcher
from app.models.schemas import (
    ClassificationSource,
    ClassificationStatus,
    FetchResult,
    FetchStatus,
    LLMClassificationOutput,
    StructuredMetadata,
)


@pytest.mark.asyncio
async def test_brand_override_pipeline_path(in_memory_db, test_settings):
    pipeline = DomainClassificationPipeline(settings=test_settings)
    # youtube.com is in brand_overrides.json
    res = await pipeline.classify("https://www.youtube.com/watch?v=abc", db_session=in_memory_db)

    assert res.category == "Entertainment & Media"
    assert res.category_id == 7
    assert res.source == ClassificationSource.BRAND_OVERRIDE.value


@pytest.mark.asyncio
async def test_cached_db_pipeline_path(in_memory_db, test_settings):
    pipeline = DomainClassificationPipeline(settings=test_settings)

    # First call
    res1 = await pipeline.classify("discord.com", db_session=in_memory_db)
    assert res1.category == "Communication"

    # Second call hits cache
    res2 = await pipeline.classify("https://discord.com/channels", db_session=in_memory_db)
    assert res2.category == "Communication"
    assert res2.source == ClassificationSource.DATABASE.value


@pytest.mark.asyncio
async def test_strict_two_layer_flow_http_then_llm(in_memory_db, test_settings):
    # Mock Layer 1 HTTP Fetcher
    mock_fetcher = MagicMock(spec=HTTPMetadataFetcher)
    mock_fetcher.fetch = AsyncMock(
        return_value=FetchResult(
            url="https://asana.com",
            domain="asana.com",
            final_url="https://asana.com/",
            http_status=200,
            fetch_status=FetchStatus.SUCCESS,
            metadata=StructuredMetadata(
                title="Asana: Work management platform",
                description="Manage team tasks and projects easily.",
                headings=["Manage your work", "Features"],
            ),
        )
    )

    # Mock Layer 2 LLM Categorizer
    mock_llm = MagicMock(spec=OpenRouterLLMClient)
    mock_llm.generate_classification = AsyncMock(
        return_value=(
            LLMClassificationOutput(
                domain="asana.com",
                category="Productivity & Office",
                category_id=3,
                confidence=0.96,
                rule_applied="TB7",
                status=ClassificationStatus.CLASSIFIED,
                reason="Task and project management tool per TB7.",
            ),
            {"model": "test-model"},
        )
    )

    pipeline = DomainClassificationPipeline(
        settings=test_settings,
        llm_client=mock_llm,
        fetcher=mock_fetcher,
    )

    res = await pipeline.classify("https://asana.com", db_session=in_memory_db)

    # Verify Layer 1 was called FIRST with raw URL
    mock_fetcher.fetch.assert_called_once_with("https://asana.com")

    # Verify Layer 2 LLM was called
    mock_llm.generate_classification.assert_called_once()

    assert res.category == "Productivity & Office"
    assert res.category_id == 3
    assert res.confidence == 0.96
    assert res.source == ClassificationSource.LLM_CATEGORIZER.value
    assert res.rule_applied == "TB7"


@pytest.mark.asyncio
async def test_sparse_metadata_handled_gracefully(in_memory_db, test_settings):
    # Test JS-heavy or sparse HTML page
    mock_fetcher = MagicMock(spec=HTTPMetadataFetcher)
    mock_fetcher.fetch = AsyncMock(
        return_value=FetchResult(
            url="https://my-spa-app.io",
            domain="my-spa-app.io",
            final_url="https://my-spa-app.io",
            http_status=200,
            fetch_status=FetchStatus.SUCCESS,
            metadata=StructuredMetadata(
                title="My SPA Tool",
                is_js_heavy=True,
                body_sample="",
            ),
        )
    )

    mock_llm = MagicMock(spec=OpenRouterLLMClient)
    mock_llm.generate_classification = AsyncMock(
        return_value=(
            LLMClassificationOutput(
                domain="my-spa-app.io",
                category="Productivity & Office",
                category_id=3,
                confidence=0.82,
                rule_applied="general_taxonomy",
                status=ClassificationStatus.CLASSIFIED,
                reason="Categorized based on sparse title and domain context.",
            ),
            {"model": "test-model"},
        )
    )

    pipeline = DomainClassificationPipeline(
        settings=test_settings,
        llm_client=mock_llm,
        fetcher=mock_fetcher,
    )

    res = await pipeline.classify("https://my-spa-app.io", db_session=in_memory_db)
    assert res.category == "Productivity & Office"
    assert res.confidence == 0.82


@pytest.mark.asyncio
async def test_low_confidence_needs_review_not_saved_to_db(in_memory_db, test_settings):
    from app.database.repository import DomainRepository

    mock_fetcher = MagicMock(spec=HTTPMetadataFetcher)
    mock_fetcher.fetch = AsyncMock(
        return_value=FetchResult(
            url="https://ambiguous-parked-domain.xyz",
            domain="ambiguous-parked-domain.xyz",
            final_url="https://ambiguous-parked-domain.xyz",
            http_status=200,
            fetch_status=FetchStatus.SUCCESS,
            metadata=StructuredMetadata(title="Parked Domain"),
        )
    )

    # Mock low confidence prediction (e.g. 0.50 < 0.80 threshold)
    mock_llm = MagicMock(spec=OpenRouterLLMClient)
    mock_llm.generate_classification = AsyncMock(
        return_value=(
            LLMClassificationOutput(
                domain="ambiguous-parked-domain.xyz",
                category="Development & IT",
                category_id=4,
                confidence=0.50,
                rule_applied="general_taxonomy",
                status=ClassificationStatus.CLASSIFIED,
                reason="Low confidence guess on parked domain",
            ),
            {"model": "test-model"},
        )
    )

    pipeline = DomainClassificationPipeline(
        settings=test_settings,
        llm_client=mock_llm,
        fetcher=mock_fetcher,
    )

    res = await pipeline.classify("https://ambiguous-parked-domain.xyz", db_session=in_memory_db)

    # Verify status is flagged as NEEDS_REVIEW
    assert res.status == "NEEDS_REVIEW"
    assert res.confidence == 0.50

    # Verify domain was NOT saved to the SQLite database
    repo = DomainRepository(in_memory_db)
    in_db = repo.get_by_fqdn("ambiguous-parked-domain.xyz")
    assert in_db is None

