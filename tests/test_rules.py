import pytest
from app.models.category import CategoryEnum, CATEGORIES_REGISTRY
from app.rules.base import rule_registry
from app.rules.locked_rules import register_locked_rules


def test_locked_rules_registered():
    register_locked_rules()
    rules = rule_registry.list_rules()
    rule_ids = {r.rule_id for r in rules}

    # Verify F1 and TB1-TB8 exist
    expected_ids = {"F1", "TB1", "TB2", "TB3", "TB4", "TB5", "TB6", "TB7", "TB8"}
    assert expected_ids.issubset(rule_ids), f"Missing locked rules: {expected_ids - rule_ids}"

    # Verify rule prompt text contains locked business rule instructions
    prompt_text = rule_registry.generate_prompt_rules_text()
    assert "TB1" in prompt_text
    assert "TB2" in prompt_text
    assert "TB3" in prompt_text
    assert "TB5" in prompt_text
    assert "TB6" in prompt_text
    assert "TB7" in prompt_text
    assert "TB8" in prompt_text


def test_eleven_categories_intact():
    assert len(CATEGORIES_REGISTRY) == 11
    names = {meta.name.value for meta in CATEGORIES_REGISTRY.values()}
    expected = {
        "Communication",
        "Social Media",
        "Productivity & Office",
        "Development & IT",
        "Business & Enterprise",
        "Research & Learning",
        "Entertainment & Media",
        "Shopping & E-commerce",
        "System Utilities & Security",
        "File Storage & Data Sharing",
        "Miscellaneous",
    }
    assert names == expected
    assert CATEGORIES_REGISTRY[11].name == CategoryEnum.MISCELLANEOUS
    assert CATEGORIES_REGISTRY[11].id == 11
