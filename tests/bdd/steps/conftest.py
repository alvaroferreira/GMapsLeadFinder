"""Fixtures especificas para testes BDD - Geoscout Pro."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.api.google_places import GooglePlacesClient
from src.api.models import Place, SearchResponse
from src.api.overpass import OSMElement, OverpassClient
from src.database.models import Business
from src.services.leads_service import LeadsService
from src.services.osm_discovery import OSMDiscoveryService
from src.services.search import SearchService


# =============================================================================
# BDD Context Fixture
# =============================================================================


@pytest.fixture
def bdd_context():
    """
    Contexto compartilhado entre steps BDD.

    Este contexto permite passar dados entre Given/When/Then steps.
    """
    return {
        # Search Feature
        "search_service": None,
        "search_query": None,
        "search_filters": {},
        "search_result": None,
        "search_error": None,
        "found_businesses": [],
        # OSM Feature
        "osm_service": None,
        "osm_area": None,
        "osm_query": None,
        "osm_result": None,
        "osm_error": None,
        "osm_elements": [],
        # Pipeline Feature
        "leads_service": None,
        "current_lead": None,
        "lead_id": None,
        "update_data": {},
        "update_result": None,
        "update_error": None,
        "filtered_leads": [],
        # Common
        "db_session": None,
        "exception": None,
    }


# =============================================================================
# Mock Google Places API
# =============================================================================


@pytest.fixture
def mock_google_places_client():
    """Mock do GooglePlacesClient para testes BDD."""
    from src.api.models import DisplayName, Location

    mock = MagicMock(spec=GooglePlacesClient)

    # Mock search_all_pages - retorna async generator
    async def mock_search_generator(*args, **kwargs):
        places = [
            Place(
                id="place_001",
                displayName=DisplayName(text="Restaurante BDD", languageCode="pt"),
                formattedAddress="Rua BDD 123, Lisboa, Portugal",
                location=Location(latitude=38.7223, longitude=-9.1393),
                types=["restaurant", "food"],
                businessStatus="OPERATIONAL",
                nationalPhoneNumber="+351 912 345 678",
                internationalPhoneNumber="+351 912 345 678",
                websiteUri=None,
                googleMapsUri="https://maps.google.com/?cid=123",
                rating=4.2,
                userRatingCount=25,
                priceLevel="PRICE_LEVEL_MODERATE",
            ),
            Place(
                id="place_002",
                displayName=DisplayName(text="Cafe Premium", languageCode="pt"),
                formattedAddress="Av. Premium 456, Lisboa, Portugal",
                location=Location(latitude=38.7300, longitude=-9.1400),
                types=["cafe", "food"],
                businessStatus="OPERATIONAL",
                nationalPhoneNumber="+351 912 345 679",
                internationalPhoneNumber="+351 912 345 679",
                websiteUri="https://cafe-premium.pt",
                googleMapsUri="https://maps.google.com/?cid=456",
                rating=4.8,
                userRatingCount=150,
                priceLevel="PRICE_LEVEL_EXPENSIVE",
            ),
        ]
        for place in places:
            yield place

    mock.search_all_pages = mock_search_generator

    # Mock nearby_search
    mock.nearby_search = AsyncMock(
        return_value=SearchResponse(
            places=[
                Place(
                    id="place_nearby_001",
                    displayName=DisplayName(text="Negocio Proximo", languageCode="pt"),
                    formattedAddress="Rua Proxima 789, Lisboa, Portugal",
                    location=Location(latitude=38.7250, longitude=-9.1420),
                    types=["store"],
                    businessStatus="OPERATIONAL",
                    rating=4.0,
                    userRatingCount=50,
                )
            ],
            nextPageToken=None,
        )
    )

    return mock


@pytest.fixture
def mock_google_api_error():
    """Mock para simular erro de API key invalida."""
    mock = MagicMock(spec=GooglePlacesClient)

    async def error_generator(*args, **kwargs):
        raise Exception("API_KEY_INVALID")
        yield  # pragma: no cover

    mock.search_all_pages = error_generator
    return mock


@pytest.fixture
def mock_google_rate_limit_error():
    """Mock para simular rate limit excedido."""
    mock = MagicMock(spec=GooglePlacesClient)

    async def rate_limit_generator(*args, **kwargs):
        raise Exception("RATE_LIMIT_EXCEEDED")
        yield  # pragma: no cover

    mock.search_all_pages = rate_limit_generator
    return mock


@pytest.fixture
def mock_google_empty_results():
    """Mock para retornar resultados vazios."""
    mock = MagicMock(spec=GooglePlacesClient)

    async def empty_generator(*args, **kwargs):
        return
        yield  # pragma: no cover

    mock.search_all_pages = empty_generator
    return mock


# =============================================================================
# Mock Overpass/OSM API
# =============================================================================


@pytest.fixture
def mock_overpass_client():
    """Mock do OverpassClient para testes BDD."""
    mock = MagicMock(spec=OverpassClient)

    mock.discover_new_businesses = AsyncMock(
        return_value=[
            OSMElement(
                type="node",
                id=123456789,
                lat=38.7223,
                lon=-9.1393,
                tags={
                    "name": "Cafe OSM BDD",
                    "amenity": "cafe",
                    "phone": "+351 912 345 680",
                    "website": "https://cafe-osm-bdd.pt",
                    "opening_hours": "Mo-Fr 08:00-20:00",
                },
            ),
            OSMElement(
                type="node",
                id=987654321,
                lat=38.7300,
                lon=-9.1400,
                tags={
                    "name": "Loja OSM BDD",
                    "shop": "clothes",
                    "addr:street": "Rua OSM BDD",
                },
            ),
        ]
    )

    mock.discover_by_location_text = AsyncMock(
        return_value=(
            [
                OSMElement(
                    type="node",
                    id=111222333,
                    lat=38.7400,
                    lon=-9.1500,
                    tags={
                        "name": "Restaurante OSM Texto",
                        "amenity": "restaurant",
                    },
                )
            ],
            {"display_name": "Lisboa, Portugal"},
        )
    )

    return mock


@pytest.fixture
def mock_overpass_timeout_error():
    """Mock para simular timeout da Overpass API."""
    from src.api.overpass import OverpassError

    mock = MagicMock(spec=OverpassClient)
    mock.discover_new_businesses = AsyncMock(side_effect=OverpassError("Query timeout exceeded"))
    return mock


@pytest.fixture
def mock_overpass_area_too_large():
    """Mock para simular area muito grande."""
    from src.api.overpass import OverpassError

    mock = MagicMock(spec=OverpassClient)
    mock.discover_new_businesses = AsyncMock(side_effect=OverpassError("Area too large for query"))
    return mock


@pytest.fixture
def mock_overpass_invalid_location():
    """Mock para elementos sem localizacao valida."""
    mock = MagicMock(spec=OverpassClient)

    mock.discover_new_businesses = AsyncMock(
        return_value=[
            OSMElement(
                type="node",
                id=999888777,
                lat=None,
                lon=None,
                tags={"name": "Sem Localizacao"},
            ),
        ]
    )
    return mock


# =============================================================================
# Service Fixtures
# =============================================================================


@pytest.fixture
def search_service(db_session, mock_google_places_client):
    """SearchService com mock do client."""
    from src.services.scorer import LeadScorer

    return SearchService(client=mock_google_places_client, scorer=LeadScorer())


@pytest.fixture
def osm_service(db_session, mock_overpass_client):
    """OSMDiscoveryService com mock do client."""
    from src.services.scorer import LeadScorer

    return OSMDiscoveryService(client=mock_overpass_client, scorer=LeadScorer())


@pytest.fixture
def leads_service(db_session):
    """LeadsService real para testes de pipeline."""
    return LeadsService()


# =============================================================================
# Sample Business Data
# =============================================================================


@pytest.fixture
def sample_businesses_in_db(db_session):
    """Cria businesses de exemplo na DB para testes."""
    businesses = [
        Business(
            id="bdd_place_001",
            name="Lead Novo BDD",
            formatted_address="Rua BDD 1, Lisboa, Portugal",
            latitude=38.7223,
            longitude=-9.1393,
            place_types=["restaurant"],
            business_status="OPERATIONAL",
            lead_status="new",
            lead_score=60,
            has_website=False,
        ),
        Business(
            id="bdd_place_002",
            name="Lead Qualificado BDD",
            formatted_address="Rua BDD 2, Lisboa, Portugal",
            latitude=38.7300,
            longitude=-9.1400,
            place_types=["cafe"],
            business_status="OPERATIONAL",
            lead_status="qualified",
            lead_score=80,
            has_website=True,
            website="https://lead-qualificado.pt",
            tags=["premium", "tech"],
        ),
        Business(
            id="bdd_place_003",
            name="Lead Contactado BDD",
            formatted_address="Rua BDD 3, Porto, Portugal",
            latitude=41.1579,
            longitude=-8.6291,
            place_types=["store"],
            business_status="OPERATIONAL",
            lead_status="contacted",
            lead_score=70,
            has_website=True,
            website="https://lead-contactado.pt",
        ),
    ]

    for business in businesses:
        db_session.add(business)

    db_session.commit()

    # Expunge para uso posterior
    for business in businesses:
        db_session.expunge(business)

    return businesses


# =============================================================================
# Utility Fixtures
# =============================================================================


@pytest.fixture
def capture_exception():
    """Helper para capturar excecoes em steps."""
    captured = {"exception": None}

    def capture(func, *args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            captured["exception"] = e
            return None

    return capture, captured


@pytest.fixture
async def async_capture_exception():
    """Helper para capturar excecoes async em steps."""
    captured = {"exception": None}

    async def capture(func, *args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            captured["exception"] = e
            return None

    return capture, captured
