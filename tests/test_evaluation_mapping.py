import pytest
from scripts.evaluate_dataset import load_category_mapping
from app.models.category import ALLOWED_CATEGORY_NAMES


def test_evaluation_category_mapping():
    mapping = load_category_mapping("data/evaluation_category_mapping.json")
    assert len(mapping) > 0

    # Test key expected categories in dataset map to our 10 canonical categories
    test_cases = [
        ("Video Streaming", "Entertainment & Media"),
        ("Office Suite", "Productivity & Office"),
        ("Cloud Storage", "File Storage & Data Sharing"),
        ("Messaging", "Communication"),
        ("Collaboration / Team Chat", "Communication"),
        ("Version Control", "Development & IT"),
        ("CRM / ERP", "Business & Enterprise"),
        ("Reference / Encyclopedia", "Research & Learning"),
        ("Online Marketplace", "Shopping & E-commerce"),
        ("Security & Antivirus", "System Utilities & Security"),
    ]

    for raw_cat, expected_canonical in test_cases:
        mapped = mapping.get(raw_cat)
        assert mapped == expected_canonical, f"Mapping failed for '{raw_cat}': got '{mapped}', expected '{expected_canonical}'"
        assert mapped in ALLOWED_CATEGORY_NAMES
