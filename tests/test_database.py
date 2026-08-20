import pytest
from app.database.repository import DomainRepository
from app.models.schemas import ClassificationSource
from app.normalization.normalizer import normalize_domain


def test_database_save_and_retrieve(in_memory_db):
    repo = DomainRepository(in_memory_db)
    norm = normalize_domain("https://example.com")

    saved = repo.save_classification(
        norm=norm,
        category="Research & Learning",
        confidence=0.95,
        source=ClassificationSource.LLM_CATEGORIZER,
        status="CLASSIFIED",
        reason="Test reason",
        metadata_fetch_status="SUCCESS",
        http_status=200,
    )

    assert saved.id is not None
    assert saved.fqdn == "example.com"
    assert saved.category_name == "Research & Learning"
    assert saved.category_id == 6
    assert saved.metadata_fetch_status == "SUCCESS"

    fetched = repo.get_by_fqdn("example.com")
    assert fetched is not None
    assert fetched.category_name == "Research & Learning"


def test_human_override_is_never_overwritten_by_ai(in_memory_db):
    repo = DomainRepository(in_memory_db)
    norm = normalize_domain("https://special-enterprise-tool.com")

    # Step 1: Human marks domain as "Business & Enterprise"
    human_record = repo.save_classification(
        norm=norm,
        category="Business & Enterprise",
        confidence=1.0,
        source=ClassificationSource.HUMAN_OVERRIDE,
        status="OVERRIDE",
        is_human_override=True,
        reason="Manually reviewed by compliance officer",
    )
    assert human_record.is_human_override is True
    assert human_record.category_name == "Business & Enterprise"

    # Step 2: Automated AI pipeline attempts to classify the domain as "Productivity & Office"
    attempted_ai_save = repo.save_classification(
        norm=norm,
        category="Productivity & Office",
        confidence=0.90,
        source=ClassificationSource.LLM_CATEGORIZER,
        status="CLASSIFIED",
        is_human_override=False,
        reason="AI hallucination / prediction",
    )

    # Step 3: Verify the record was NOT overwritten and retained Human Override
    assert attempted_ai_save.category_name == "Business & Enterprise"
    assert attempted_ai_save.is_human_override is True
    assert attempted_ai_save.classification_source == ClassificationSource.HUMAN_OVERRIDE.value

    # Verify directly from DB query
    current_in_db = repo.get_by_fqdn(norm.fqdn)
    assert current_in_db.category_name == "Business & Enterprise"
    assert current_in_db.is_human_override is True


def test_enrichment_used_flag_persistence(in_memory_db):
    repo = DomainRepository(in_memory_db)
    norm = normalize_domain("https://miro.com")

    saved = repo.save_classification(
        norm=norm,
        category="Productivity & Office",
        confidence=0.98,
        source=ClassificationSource.LLM_CATEGORIZER,
        status="CLASSIFIED",
        enrichment_used=True,
        reason="Visual collaboration workspace",
        metadata_fetch_status="SUCCESS",
        http_status=200,
    )

    assert saved.enrichment_used is True
    res = repo.to_response(saved)
    assert res.enrichment_used is True
    assert res.domain == "miro.com"


def test_delete_domain_by_fqdn(in_memory_db):
    repo = DomainRepository(in_memory_db)
    norm = normalize_domain("https://example-to-delete.com")

    repo.save_classification(
        norm=norm,
        category="Entertainment & Media",
        confidence=0.90,
        source=ClassificationSource.LLM_CATEGORIZER,
    )

    assert repo.get_by_fqdn("example-to-delete.com") is not None

    deleted = repo.delete_by_fqdn("example-to-delete.com")
    assert deleted is True
    assert repo.get_by_fqdn("example-to-delete.com") is None

    # Deleting again returns False
    assert repo.delete_by_fqdn("example-to-delete.com") is False


def test_database_category_11_miscellaneous_save_and_retrieve(in_memory_db):
    repo = DomainRepository(in_memory_db)
    norm = normalize_domain("https://unknown-ambiguous-example.org")

    saved = repo.save_classification(
        norm=norm,
        category="Miscellaneous",
        confidence=0.62,
        source=ClassificationSource.LLM_CATEGORIZER,
        status="LOW_CONFIDENCE",
        reason="Available metadata is insufficient to confidently classify the domain into categories 1-10.",
        metadata_fetch_status="SUCCESS",
        http_status=200,
    )

    assert saved.id is not None
    assert saved.category_id == 11
    assert saved.category_name == "Miscellaneous"
    assert saved.status == "LOW_CONFIDENCE"
    assert saved.confidence == 0.62

    fetched = repo.get_by_fqdn("unknown-ambiguous-example.org")
    assert fetched is not None
    assert fetched.category_id == 11
    assert fetched.category_name == "Miscellaneous"
    assert fetched.status == "LOW_CONFIDENCE"


