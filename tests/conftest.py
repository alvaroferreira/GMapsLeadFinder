"""Fixtures compartilhadas para testes - Geoscout Pro."""

from collections.abc import Generator
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from faker import Faker
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.database.models import (
    Base,
    Business,
    TrackedSearch,
)


# Initialize faker
fake = Faker("pt_PT")


# =============================================================================
# Database Fixtures
# =============================================================================


@pytest.fixture
def test_engine():
    """Cria engine de teste em memoria."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def test_session(test_engine) -> Generator[Session, None, None]:
    """Cria sessao de teste."""
    Session = sessionmaker(bind=test_engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def db_session(test_session) -> Session:
    """Alias para test_session - compatibilidade com servicos."""
    return test_session


# =============================================================================
# Business Factories & Fixtures
# =============================================================================


class BusinessFactory:
    """Factory para criar instancias de Business."""

    @staticmethod
    def create(
        id: str = None,
        name: str = None,
        has_website: bool = True,
        lead_status: str = "new",
        lead_score: int = 50,
        **kwargs,
    ) -> Business:
        """Cria um Business com valores padrao ou customizados."""
        return Business(
            id=id or f"place_{fake.uuid4()[:8]}",
            name=name or fake.company(),
            formatted_address=kwargs.get(
                "formatted_address", f"{fake.street_address()}, {fake.city()}, Portugal"
            ),
            latitude=kwargs.get("latitude", fake.latitude()),
            longitude=kwargs.get("longitude", fake.longitude()),
            place_types=kwargs.get("place_types", ["restaurant", "food"]),
            business_status=kwargs.get("business_status", "OPERATIONAL"),
            phone_number=kwargs.get("phone_number", fake.phone_number()),
            website=kwargs.get("website", fake.url() if has_website else None),
            rating=kwargs.get("rating", round(fake.pyfloat(min_value=3.0, max_value=5.0), 1)),
            review_count=kwargs.get("review_count", fake.random_int(min=1, max=500)),
            has_website=has_website,
            has_photos=kwargs.get("has_photos", True),
            photo_count=kwargs.get("photo_count", fake.random_int(min=0, max=20)),
            lead_score=lead_score,
            lead_status=lead_status,
            email=kwargs.get("email"),
            emails_scraped=kwargs.get("emails_scraped", []),
            social_linkedin=kwargs.get("social_linkedin"),
            social_facebook=kwargs.get("social_facebook"),
            social_instagram=kwargs.get("social_instagram"),
            enrichment_status=kwargs.get("enrichment_status", "pending"),
            tags=kwargs.get("tags", []),
            notes=kwargs.get("notes"),
            first_seen_at=kwargs.get("first_seen_at", datetime.utcnow()),
            last_updated_at=kwargs.get("last_updated_at", datetime.utcnow()),
        )

    @staticmethod
    def create_batch(count: int, **kwargs) -> list[Business]:
        """Cria multiplos Business."""
        return [BusinessFactory.create(**kwargs) for _ in range(count)]


class TrackedSearchFactory:
    """Factory para criar instancias de TrackedSearch."""

    @staticmethod
    def create(
        name: str = None, query_type: str = "text", is_active: bool = True, **kwargs
    ) -> TrackedSearch:
        """Cria um TrackedSearch com valores padrao."""
        return TrackedSearch(
            name=name or f"Pesquisa {fake.word()}",
            query_type=query_type,
            query_params=kwargs.get("query_params", {"query": fake.city(), "radius": 5000}),
            is_active=is_active,
            interval_hours=kwargs.get("interval_hours", 24),
            notify_on_new=kwargs.get("notify_on_new", True),
            notify_threshold_score=kwargs.get("notify_threshold_score", 50),
            total_runs=kwargs.get("total_runs", 0),
            total_new_found=kwargs.get("total_new_found", 0),
        )


# Business fixtures usando factories
@pytest.fixture
def sample_business() -> Business:
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
def sample_business_with_website() -> Business:
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
def sample_business_low_visibility() -> Business:
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


@pytest.fixture
def sample_business_enriched() -> Business:
    """Business com dados enriquecidos."""
    return Business(
        id="test_place_enriched",
        name="Empresa Enriquecida",
        formatted_address="Av. Principal 100, Lisboa, Portugal",
        latitude=38.7300,
        longitude=-9.1500,
        place_types=["company", "point_of_interest"],
        business_status="OPERATIONAL",
        phone_number="+351 912 345 681",
        website="https://empresa-teste.pt",
        rating=4.5,
        review_count=100,
        has_website=True,
        has_photos=True,
        photo_count=10,
        lead_score=75,
        lead_status="qualified",
        email="info@empresa-teste.pt",
        emails_scraped=["info@empresa-teste.pt", "contacto@empresa-teste.pt"],
        social_linkedin="https://linkedin.com/company/empresa-teste",
        social_facebook="https://facebook.com/empresateste",
        social_instagram="https://instagram.com/empresateste",
        enrichment_status="completed",
        enriched_at=datetime.utcnow(),
        tags=["premium", "tech"],
    )


@pytest.fixture
def business_factory() -> type[BusinessFactory]:
    """Retorna a factory de Business."""
    return BusinessFactory


@pytest.fixture
def tracked_search_factory() -> type[TrackedSearchFactory]:
    """Retorna a factory de TrackedSearch."""
    return TrackedSearchFactory


# =============================================================================
# TrackedSearch Fixtures
# =============================================================================


@pytest.fixture
def sample_tracked_search() -> TrackedSearch:
    """TrackedSearch de exemplo."""
    return TrackedSearch(
        name="Restaurantes Lisboa",
        query_type="text",
        query_params={"query": "restaurantes Lisboa", "radius": 5000},
        is_active=True,
        interval_hours=24,
        notify_on_new=True,
        notify_threshold_score=50,
    )


# =============================================================================
# Mock Fixtures
# =============================================================================


@pytest.fixture
def mock_httpx_client():
    """Mock do httpx.AsyncClient para testes de API."""
    mock = AsyncMock()
    mock.post = AsyncMock()
    mock.get = AsyncMock()
    return mock


@pytest.fixture
def mock_google_places_response():
    """Resposta mock da Google Places API."""
    return {
        "places": [
            {
                "id": "ChIJ1234567890",
                "displayName": {"text": "Restaurante Mock", "languageCode": "pt"},
                "formattedAddress": "Rua Mock 123, Lisboa, Portugal",
                "location": {"latitude": 38.7223, "longitude": -9.1393},
                "types": ["restaurant", "food"],
                "businessStatus": "OPERATIONAL",
                "nationalPhoneNumber": "+351 912 345 678",
                "rating": 4.5,
                "userRatingCount": 100,
            }
        ],
        "nextPageToken": None,
    }


@pytest.fixture
def mock_overpass_response():
    """Resposta mock da Overpass API (OSM)."""
    return {
        "elements": [
            {
                "type": "node",
                "id": 123456789,
                "lat": 38.7223,
                "lon": -9.1393,
                "tags": {
                    "name": "Cafe OSM",
                    "amenity": "cafe",
                    "phone": "+351 912 345 678",
                    "website": "https://cafe-osm.pt",
                },
            },
            {
                "type": "node",
                "id": 987654321,
                "lat": 38.7300,
                "lon": -9.1400,
                "tags": {
                    "name": "Loja OSM",
                    "shop": "clothes",
                    "addr:street": "Rua OSM",
                },
            },
        ],
    }


@pytest.fixture
def mock_notion_client():
    """Mock do Notion Client."""
    mock = MagicMock()
    mock.databases = MagicMock()
    mock.databases.query = MagicMock(return_value={"results": []})
    mock.pages = MagicMock()
    mock.pages.create = MagicMock(return_value={"id": "page_123"})
    mock.pages.update = MagicMock(return_value={"id": "page_123"})
    return mock


@pytest.fixture
def mock_website_html():
    """HTML mock para scraping."""
    return """
    <!DOCTYPE html>
    <html>
    <head><title>Empresa Teste</title></head>
    <body>
        <div class="contact">
            <a href="mailto:info@empresa.pt">info@empresa.pt</a>
            <a href="mailto:vendas@empresa.pt">vendas@empresa.pt</a>
        </div>
        <div class="social">
            <a href="https://facebook.com/empresa">Facebook</a>
            <a href="https://linkedin.com/company/empresa">LinkedIn</a>
            <a href="https://instagram.com/empresa">Instagram</a>
        </div>
        <footer>
            Tel: +351 912 345 678
        </footer>
    </body>
    </html>
    """


# =============================================================================
# FastAPI TestClient Fixtures
# =============================================================================


@pytest.fixture
def test_client():
    """TestClient para testes de API FastAPI."""
    from fastapi.testclient import TestClient

    from src.web.server import app

    with TestClient(app) as client:
        yield client


@pytest.fixture
async def async_test_client():
    """Async TestClient para testes assincronos."""
    import httpx

    from src.web.server import app

    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        yield client


# =============================================================================
# Service Mocks
# =============================================================================


@pytest.fixture
def mock_search_service():
    """Mock do SearchService."""
    mock = MagicMock()
    mock.search_text = AsyncMock(return_value=[])
    mock.search_nearby = AsyncMock(return_value=[])
    return mock


@pytest.fixture
def mock_enrichment_service():
    """Mock do EnrichmentService."""
    mock = MagicMock()
    mock.enrich_business = AsyncMock(return_value=None)
    mock.enrich_batch = AsyncMock(return_value=[])
    return mock


@pytest.fixture
def mock_notion_service():
    """Mock do NotionService."""
    mock = MagicMock()
    mock.test_connection = AsyncMock(return_value=True)
    mock.sync_leads = AsyncMock(return_value={"synced": 0, "created": 0, "updated": 0})
    return mock


# =============================================================================
# BDD Support Fixtures
# =============================================================================


@pytest.fixture
def bdd_context():
    """Contexto compartilhado para steps BDD."""
    return {
        "businesses": [],
        "search_results": [],
        "response": None,
        "error": None,
        "session": None,
    }


# =============================================================================
# Utility Fixtures
# =============================================================================


@pytest.fixture
def clean_exports_dir(tmp_path):
    """Directorio temporario para exports."""
    exports = tmp_path / "exports"
    exports.mkdir()
    return exports


@pytest.fixture
def fake_api_key():
    """API key falsa para testes."""
    return "AIzaSy_FAKE_API_KEY_FOR_TESTING_123"


@pytest.fixture
def notion_test_config():
    """Configuracao de teste para Notion."""
    return {
        "api_key": "secret_FAKE_NOTION_KEY_FOR_TESTING",
        "database_id": "fake-database-id-12345",
    }
