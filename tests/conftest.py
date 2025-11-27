"""Fixtures compartilhadas para testes."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.models import Base, Business


@pytest.fixture
def test_engine():
    """Cria engine de teste em memoria."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def test_session(test_engine):
    """Cria sessao de teste."""
    Session = sessionmaker(bind=test_engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def sample_business():
    """Business de exemplo para testes."""
    return Business(
        id="test_place_123",
        name="Restaurante Teste",
        formatted_address="Rua Teste 123, Lisboa, Portugal",
        latitude=38.7223,
        longitude=-9.1393,
        place_types=["restaurant", "food"],
        business_status="OPERATIONAL",
        phone_number="+351 912 345 678",
        website=None,
        rating=4.2,
        review_count=25,
        has_website=False,
        has_photos=True,
        photo_count=3,
        lead_score=0,
        lead_status="new",
    )


@pytest.fixture
def sample_business_with_website():
    """Business com website para testes."""
    return Business(
        id="test_place_456",
        name="Clinica Dentaria Premium",
        formatted_address="Av. Liberdade 456, Lisboa, Portugal",
        latitude=38.7200,
        longitude=-9.1400,
        place_types=["dentist", "health"],
        business_status="OPERATIONAL",
        phone_number="+351 912 345 679",
        website="https://clinica-premium.pt",
        rating=4.8,
        review_count=150,
        has_website=True,
        has_photos=True,
        photo_count=15,
        price_level=3,
        lead_score=0,
        lead_status="new",
    )


@pytest.fixture
def sample_business_low_visibility():
    """Business com baixa visibilidade (ideal para marketing)."""
    return Business(
        id="test_place_789",
        name="Cafe Novo",
        formatted_address="Rua Nova 789, Porto, Portugal",
        latitude=41.1579,
        longitude=-8.6291,
        place_types=["cafe", "restaurant"],
        business_status="OPERATIONAL",
        phone_number="+351 912 345 680",
        website=None,
        rating=3.5,
        review_count=5,
        has_website=False,
        has_photos=False,
        photo_count=2,
        lead_score=0,
        lead_status="new",
    )
