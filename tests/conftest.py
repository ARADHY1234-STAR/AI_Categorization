import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database.connection import Base
from app.database.models import DomainClassificationModel
from app.rules.overrides import BrandOverrideEngine
from app.config.settings import Settings


@pytest.fixture
def in_memory_db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def test_settings():
    return Settings(
        OPENROUTER_API_KEY="test-mock-key",
        OPENROUTER_MODEL="anthropic/claude-3.5-sonnet",
        CONFIDENCE_THRESHOLD=0.80,
        CLASSIFIER_CONFIDENCE_THRESHOLD=0.80,
        DATABASE_URL="sqlite:///:memory:",
        BRAND_OVERRIDES_PATH="data/brand_overrides.json",
    )


@pytest.fixture
def override_engine():
    return BrandOverrideEngine("data/brand_overrides.json")
