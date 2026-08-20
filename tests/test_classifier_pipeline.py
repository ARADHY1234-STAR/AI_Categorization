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
from app.database.repository import DomainRepository


# ==============================================================================
# REQUIREMENT 11 SPECIFIC TESTS (TEST 1 to TEST 11)
# ==============================================================================

@pytest.mark.asyncio
async def test_1_confidence_0_95_communication(in_memory_db, test_settings):
    """TEST 1: confidence = 0.95, category = Communication -> Communication"""
    mock_fetcher = MagicMock(spec=HTTPMetadataFetcher)
    mock_fetcher.fetch = AsyncMock(
        return_value=FetchResult(
            url="https://some-chat-app.com",
            domain="some-chat-app.com",
            final_url="https://some-chat-app.com",
            http_status=200,
            fetch_status=FetchStatus.SUCCESS,
            metadata=StructuredMetadata(title="Team Chat App", description="Real-time messaging"),
        )
    )
    mock_llm = MagicMock(spec=OpenRouterLLMClient)
    mock_llm.generate_classification = AsyncMock(
        return_value=(
            LLMClassificationOutput(
                domain="some-chat-app.com",
                category="Communication",
                category_id=1,
                confidence=0.95,
                rule_applied="TB1",
                status=ClassificationStatus.CLASSIFIED,
                reason="Core product is messaging.",
            ),
            {"model": "test-model"},
        )
    )

    pipeline = DomainClassificationPipeline(
        settings=test_settings,
        llm_client=mock_llm,
        fetcher=mock_fetcher,
    )

    res = await pipeline.classify("https://some-chat-app.com", db_session=in_memory_db)
    assert res.category == "Communication"
    assert res.category_id == 1
    assert res.confidence == 0.95
    assert res.status == "CLASSIFIED"


@pytest.mark.asyncio
async def test_2_confidence_0_80_inclusive_threshold(in_memory_db, test_settings):
    """TEST 2: confidence = 0.80, category = Communication -> Communication (inclusive)."""
    mock_fetcher = MagicMock(spec=HTTPMetadataFetcher)
    mock_fetcher.fetch = AsyncMock(
        return_value=FetchResult(
            url="https://borderline-chat.com",
            domain="borderline-chat.com",
            final_url="https://borderline-chat.com",
            http_status=200,
            fetch_status=FetchStatus.SUCCESS,
            metadata=StructuredMetadata(title="Chat Tool", description="Messaging tool"),
        )
    )
    mock_llm = MagicMock(spec=OpenRouterLLMClient)
    mock_llm.generate_classification = AsyncMock(
        return_value=(
            LLMClassificationOutput(
                domain="borderline-chat.com",
                category="Communication",
                category_id=1,
                confidence=0.80,
                rule_applied="TB1",
                status=ClassificationStatus.CLASSIFIED,
                reason="Borderline confidence at exact threshold.",
            ),
            {"model": "test-model"},
        )
    )

    pipeline = DomainClassificationPipeline(
        settings=test_settings,
        llm_client=mock_llm,
        fetcher=mock_fetcher,
    )

    res = await pipeline.classify("https://borderline-chat.com", db_session=in_memory_db)
    assert res.category == "Communication"
    assert res.category_id == 1
    assert res.confidence == 0.80
    assert res.status == "CLASSIFIED"


@pytest.mark.asyncio
async def test_3_confidence_0_79_falls_back_to_miscellaneous(in_memory_db, test_settings):
    """TEST 3: confidence = 0.79, category = Communication -> Miscellaneous (Category 11)."""
    mock_fetcher = MagicMock(spec=HTTPMetadataFetcher)
    mock_fetcher.fetch = AsyncMock(
        return_value=FetchResult(
            url="https://uncertain-chat.com",
            domain="uncertain-chat.com",
            final_url="https://uncertain-chat.com",
            http_status=200,
            fetch_status=FetchStatus.SUCCESS,
            metadata=StructuredMetadata(title="Uncertain Site", description="Some communication text"),
        )
    )
    mock_llm = MagicMock(spec=OpenRouterLLMClient)
    mock_llm.generate_classification = AsyncMock(
        return_value=(
            LLMClassificationOutput(
                domain="uncertain-chat.com",
                category="Communication",
                category_id=1,
                confidence=0.79,
                rule_applied="TB1",
                status=ClassificationStatus.CLASSIFIED,
                reason="Slightly below confidence threshold.",
            ),
            {"model": "test-model"},
        )
    )

    pipeline = DomainClassificationPipeline(
        settings=test_settings,
        llm_client=mock_llm,
        fetcher=mock_fetcher,
    )

    res = await pipeline.classify("https://uncertain-chat.com", db_session=in_memory_db)
    assert res.category == "Miscellaneous"
    assert res.category_id == 11
    assert res.confidence == 0.79
    assert res.status == "LOW_CONFIDENCE"


@pytest.mark.asyncio
async def test_4_confidence_0_30_entertainment_media_falls_back_to_miscellaneous(in_memory_db, test_settings):
    """TEST 4: confidence = 0.30, category = Entertainment & Media -> Miscellaneous (Category 11)."""
    mock_fetcher = MagicMock(spec=HTTPMetadataFetcher)
    mock_fetcher.fetch = AsyncMock(
        return_value=FetchResult(
            url="https://low-confidence-media.tv",
            domain="low-confidence-media.tv",
            final_url="https://low-confidence-media.tv",
            http_status=200,
            fetch_status=FetchStatus.SUCCESS,
            metadata=StructuredMetadata(title="Media Hub", description="Videos and streams"),
        )
    )
    mock_llm = MagicMock(spec=OpenRouterLLMClient)
    mock_llm.generate_classification = AsyncMock(
        return_value=(
            LLMClassificationOutput(
                domain="low-confidence-media.tv",
                category="Entertainment & Media",
                category_id=7,
                confidence=0.30,
                rule_applied="TB2",
                status=ClassificationStatus.CLASSIFIED,
                reason="Low confidence media prediction.",
            ),
            {"model": "test-model"},
        )
    )

    pipeline = DomainClassificationPipeline(
        settings=test_settings,
        llm_client=mock_llm,
        fetcher=mock_fetcher,
    )

    res = await pipeline.classify("https://low-confidence-media.tv", db_session=in_memory_db)
    assert res.category == "Miscellaneous"
    assert res.category_id == 11
    assert res.confidence == 0.30


@pytest.mark.asyncio
async def test_5_llm_cannot_determine_category_returns_miscellaneous(in_memory_db, test_settings):
    """TEST 5: LLM cannot determine category -> Miscellaneous (Category 11)."""
    mock_fetcher = MagicMock(spec=HTTPMetadataFetcher)
    mock_fetcher.fetch = AsyncMock(
        return_value=FetchResult(
            url="https://unknown-opaque-site.net",
            domain="unknown-opaque-site.net",
            final_url="https://unknown-opaque-site.net",
            http_status=200,
            fetch_status=FetchStatus.SUCCESS,
            metadata=StructuredMetadata(title="Welcome"),
        )
    )
    mock_llm = MagicMock(spec=OpenRouterLLMClient)
    mock_llm.generate_classification = AsyncMock(
        return_value=(
            LLMClassificationOutput(
                domain="unknown-opaque-site.net",
                category=None,
                category_id=None,
                confidence=0.0,
                rule_applied="unclassifiable",
                status=ClassificationStatus.UNCLASSIFIED,
                reason="Insufficient evidence to determine category.",
            ),
            {"model": "test-model"},
        )
    )

    pipeline = DomainClassificationPipeline(
        settings=test_settings,
        llm_client=mock_llm,
        fetcher=mock_fetcher,
    )

    res = await pipeline.classify("https://unknown-opaque-site.net", db_session=in_memory_db)
    assert res.category == "Miscellaneous"
    assert res.category_id == 11
    assert res.status == "UNCLASSIFIED"


@pytest.mark.asyncio
async def test_6_llm_returns_invalid_category_safe_fallback_miscellaneous(in_memory_db, test_settings):
    """TEST 6: LLM returns invalid category -> Safe fallback to Miscellaneous (Category 11)."""
    mock_fetcher = MagicMock(spec=HTTPMetadataFetcher)
    mock_fetcher.fetch = AsyncMock(
        return_value=FetchResult(
            url="https://hallucinated-category-site.com",
            domain="hallucinated-category-site.com",
            final_url="https://hallucinated-category-site.com",
            http_status=200,
            fetch_status=FetchStatus.SUCCESS,
            metadata=StructuredMetadata(title="Random Site"),
        )
    )
    mock_llm = MagicMock(spec=OpenRouterLLMClient)
    # The client parser handles or passes invalid category
    mock_llm.generate_classification = AsyncMock(
        return_value=(
            LLMClassificationOutput.model_construct(
                domain="hallucinated-category-site.com",
                category="Nonexistent Fancy Category",
                category_id=999,
                confidence=0.90,
                rule_applied="hallucination",
                status=ClassificationStatus.CLASSIFIED,
                reason="Invalid category returned.",
            ),
            {"model": "test-model"},
        )
    )

    pipeline = DomainClassificationPipeline(
        settings=test_settings,
        llm_client=mock_llm,
        fetcher=mock_fetcher,
    )

    res = await pipeline.classify("https://hallucinated-category-site.com", db_session=in_memory_db)
    assert res.category == "Miscellaneous"
    assert res.category_id == 11


@pytest.mark.asyncio
async def test_7_youtube_entertainment_media(in_memory_db, test_settings):
    """TEST 7: youtube.com -> Entertainment & Media (confidence >= 0.80)."""
    pipeline = DomainClassificationPipeline(settings=test_settings)
    res = await pipeline.classify("https://www.youtube.com/watch?v=dQw4w9WgXcQ", db_session=in_memory_db)

    assert res.category == "Entertainment & Media"
    assert res.category_id == 7
    assert res.confidence >= 0.80


@pytest.mark.asyncio
async def test_8_discord_communication_tb1(in_memory_db, test_settings):
    """TEST 8: discord.com -> Communication according to TB1."""
    pipeline = DomainClassificationPipeline(settings=test_settings)
    res = await pipeline.classify("https://discord.com/channels/@me", db_session=in_memory_db)

    assert res.category == "Communication"
    assert res.category_id == 1


@pytest.mark.asyncio
async def test_9_reddit_social_media_tb4(in_memory_db, test_settings):
    """TEST 9: reddit.com -> Social Media according to TB4."""
    mock_fetcher = MagicMock(spec=HTTPMetadataFetcher)
    mock_fetcher.fetch = AsyncMock(
        return_value=FetchResult(
            url="https://www.reddit.com/r/programming",
            domain="reddit.com",
            final_url="https://www.reddit.com/r/programming",
            http_status=200,
            fetch_status=FetchStatus.SUCCESS,
            metadata=StructuredMetadata(
                title="Reddit: Dive into anything",
                description="Community forum and social discussions",
                headings=["Trending Communities"],
            ),
        )
    )
    mock_llm = MagicMock(spec=OpenRouterLLMClient)
    mock_llm.generate_classification = AsyncMock(
        return_value=(
            LLMClassificationOutput(
                domain="reddit.com",
                category="Social Media",
                category_id=2,
                confidence=0.98,
                rule_applied="TB4",
                status=ClassificationStatus.CLASSIFIED,
                reason="Discussion forum and social platform per TB4.",
            ),
            {"model": "test-model"},
        )
    )

    pipeline = DomainClassificationPipeline(
        settings=test_settings,
        llm_client=mock_llm,
        fetcher=mock_fetcher,
    )

    res = await pipeline.classify("https://www.reddit.com/r/programming", db_session=in_memory_db)
    assert res.category == "Social Media"
    assert res.category_id == 2
    assert res.confidence >= 0.80
    assert res.rule_applied == "TB4"


@pytest.mark.asyncio
async def test_10_drive_google_file_storage_tb6(in_memory_db, test_settings):
    """TEST 10: drive.google.com -> File Storage & Data Sharing according to TB6."""
    mock_fetcher = MagicMock(spec=HTTPMetadataFetcher)
    mock_fetcher.fetch = AsyncMock(
        return_value=FetchResult(
            url="https://drive.google.com/drive/my-drive",
            domain="drive.google.com",
            final_url="https://drive.google.com/drive/my-drive",
            http_status=200,
            fetch_status=FetchStatus.SUCCESS,
            metadata=StructuredMetadata(
                title="Google Drive: Cloud Storage & File Backup",
                description="Access and share files securely.",
            ),
        )
    )
    mock_llm = MagicMock(spec=OpenRouterLLMClient)
    mock_llm.generate_classification = AsyncMock(
        return_value=(
            LLMClassificationOutput(
                domain="drive.google.com",
                category="File Storage & Data Sharing",
                category_id=10,
                confidence=0.99,
                rule_applied="TB6",
                status=ClassificationStatus.CLASSIFIED,
                reason="Cloud file storage subdomain per TB6.",
            ),
            {"model": "test-model"},
        )
    )

    pipeline = DomainClassificationPipeline(
        settings=test_settings,
        llm_client=mock_llm,
        fetcher=mock_fetcher,
    )

    res = await pipeline.classify("https://drive.google.com/drive/my-drive", db_session=in_memory_db)
    assert res.category == "File Storage & Data Sharing"
    assert res.category_id == 10
    assert res.confidence >= 0.80
    assert res.domain == "drive.google.com"


@pytest.mark.asyncio
async def test_11_docs_google_productivity_office_tb6(in_memory_db, test_settings):
    """TEST 11: docs.google.com -> Productivity & Office according to TB6."""
    mock_fetcher = MagicMock(spec=HTTPMetadataFetcher)
    mock_fetcher.fetch = AsyncMock(
        return_value=FetchResult(
            url="https://docs.google.com/document/d/123",
            domain="docs.google.com",
            final_url="https://docs.google.com/document/d/123",
            http_status=200,
            fetch_status=FetchStatus.SUCCESS,
            metadata=StructuredMetadata(
                title="Google Docs: Online Document Editor",
                description="Create and edit documents online.",
            ),
        )
    )
    mock_llm = MagicMock(spec=OpenRouterLLMClient)
    mock_llm.generate_classification = AsyncMock(
        return_value=(
            LLMClassificationOutput(
                domain="docs.google.com",
                category="Productivity & Office",
                category_id=3,
                confidence=0.99,
                rule_applied="TB6",
                status=ClassificationStatus.CLASSIFIED,
                reason="Document creation and editing subdomain per TB6.",
            ),
            {"model": "test-model"},
        )
    )

    pipeline = DomainClassificationPipeline(
        settings=test_settings,
        llm_client=mock_llm,
        fetcher=mock_fetcher,
    )

    res = await pipeline.classify("https://docs.google.com/document/d/123", db_session=in_memory_db)
    assert res.category == "Productivity & Office"
    assert res.category_id == 3
    assert res.confidence >= 0.80
    assert res.domain == "docs.google.com"


# ==============================================================================
# PIPELINE ARCHITECTURE & DATABASE INTEGRATION TESTS
# ==============================================================================

@pytest.mark.asyncio
async def test_strict_two_layer_flow_http_then_llm(in_memory_db, test_settings):
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
    mock_llm.generate_classification.assert_called_once()

    assert res.category == "Productivity & Office"
    assert res.category_id == 3
    assert res.confidence == 0.96
    assert res.source == ClassificationSource.LLM_CATEGORIZER.value
    assert res.rule_applied == "TB7"


@pytest.mark.asyncio
async def test_sparse_metadata_handled_gracefully(in_memory_db, test_settings):
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
async def test_low_confidence_saved_as_miscellaneous_with_audit_status(in_memory_db, test_settings):
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

    assert res.category == "Miscellaneous"
    assert res.category_id == 11
    assert res.status == "LOW_CONFIDENCE"
    assert res.confidence == 0.50

    # Verify domain was saved to SQLite database with category 11 and audit status
    repo = DomainRepository(in_memory_db)
    in_db = repo.get_by_fqdn("ambiguous-parked-domain.xyz")
    assert in_db is not None
    assert in_db.category_id == 11
    assert in_db.category_name == "Miscellaneous"
    assert in_db.status == "LOW_CONFIDENCE"
    assert in_db.confidence == 0.50


@pytest.mark.asyncio
async def test_unresolvable_dns_failure_returns_miscellaneous(in_memory_db, test_settings):
    mock_fetcher = MagicMock(spec=HTTPMetadataFetcher)
    mock_fetcher.fetch = AsyncMock(
        return_value=FetchResult(
            url="https://gibberish9823471029384.xyz",
            domain="gibberish9823471029384.xyz",
            final_url=None,
            http_status=None,
            fetch_status=FetchStatus.DNS_FAILURE,
            metadata=StructuredMetadata(),
            error_message="DNS resolution failed",
        )
    )
    mock_llm = MagicMock(spec=OpenRouterLLMClient)
    mock_llm.generate_classification = AsyncMock(
        return_value=(
            LLMClassificationOutput(
                domain="gibberish9823471029384.xyz",
                category="Miscellaneous",
                category_id=11,
                confidence=0.0,
                rule_applied="unclassifiable",
                status=ClassificationStatus.UNCLASSIFIED,
                reason="Domain failed to resolve.",
            ),
            {"model": "test-model"},
        )
    )

    pipeline = DomainClassificationPipeline(
        settings=test_settings,
        llm_client=mock_llm,
        fetcher=mock_fetcher,
    )

    res = await pipeline.classify("https://gibberish9823471029384.xyz", db_session=in_memory_db)

    assert res.category == "Miscellaneous"
    assert res.category_id == 11
    assert res.status == "UNCLASSIFIED"
    assert res.confidence == 0.0
