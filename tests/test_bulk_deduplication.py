import pytest
from unittest.mock import AsyncMock, MagicMock
from app.classifier.bulk import BulkClassifier
from app.classifier.client import OpenRouterLLMClient
from app.classifier.pipeline import DomainClassificationPipeline
from app.enrichment.fetcher import HTTPMetadataFetcher
from app.models.schemas import (
    ClassificationStatus,
    FetchResult,
    FetchStatus,
    LLMClassificationOutput,
    StructuredMetadata,
)


@pytest.mark.asyncio
async def test_5000_duplicate_domains_classified_exactly_once(in_memory_db, test_settings):
    # Mock Layer 1 HTTP Fetcher
    mock_fetcher = MagicMock(spec=HTTPMetadataFetcher)
    mock_fetcher.fetch = AsyncMock(
        return_value=FetchResult(
            url="https://popular-service.com",
            domain="popular-service.com",
            final_url="https://popular-service.com/",
            http_status=200,
            fetch_status=FetchStatus.SUCCESS,
            metadata=StructuredMetadata(
                title="Popular Office Service",
                description="Productivity tool",
            ),
        )
    )

    # Mock Layer 2 LLM Client
    mock_llm = MagicMock(spec=OpenRouterLLMClient)
    mock_llm.generate_classification = AsyncMock(
        return_value=(
            LLMClassificationOutput(
                domain="popular-service.com",
                category="Productivity & Office",
                category_id=3,
                confidence=0.96,
                rule_applied="general_taxonomy",
                status=ClassificationStatus.CLASSIFIED,
                reason="Office tool.",
            ),
            {"model": "test-model"},
        )
    )

    pipeline = DomainClassificationPipeline(
        settings=test_settings,
        llm_client=mock_llm,
        fetcher=mock_fetcher,
    )
    bulk = BulkClassifier(pipeline=pipeline, settings=test_settings)

    # Generate 5,000 items with variations of popular-service.com
    items = []
    for i in range(5000):
        url_variant = f"https://www.popular-service.com/item/{i}?query=123"
        items.append({"domain": url_variant, "app_name": "Popular Service"})

    results, summary = await bulk.process_items(items, db_session=in_memory_db)

    # 1. Total rows must be 5000
    assert summary.total_input_rows == 5000
    # 2. Unique domains must be 1
    assert summary.unique_domains_count == 1
    # 3. Layer 1 HTTP fetcher called exactly once
    assert mock_fetcher.fetch.call_count == 1
    # 4. Layer 2 LLM classification called exactly once
    assert mock_llm.generate_classification.call_count == 1
    # 5. All 5,000 output results mapped properly
    assert len(results) == 5000
    assert all(r.category == "Productivity & Office" for r in results)
    assert all(r.category_id == 3 for r in results)
    assert all(r.domain == "popular-service.com" for r in results)
