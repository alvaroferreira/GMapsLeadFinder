"""Testes unitarios para servicos de descoberta OSM - Geoscout Pro."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api.overpass import (
    OSMElement,
    OverpassClient,
    OverpassError,
    OverpassRateLimitError,
    OverpassTimeoutError,
)
from src.services.osm_discovery import DiscoveryResult, OSMDiscoveryService


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_osm_element():
    """Cria um OSMElement de exemplo."""
    return OSMElement(
        {
            "type": "node",
            "id": 123456789,
            "lat": 38.7223,
            "lon": -9.1393,
            "tags": {
                "name": "Cafe Teste",
                "amenity": "cafe",
                "phone": "+351 912 345 678",
                "website": "https://cafe-teste.pt",
                "email": "info@cafe-teste.pt",
                "addr:street": "Rua Teste",
                "addr:housenumber": "123",
                "addr:city": "Lisboa",
                "opening_hours": "Mo-Fr 08:00-20:00",
            },
            "timestamp": "2025-01-15T10:30:00Z",
            "version": 1,
            "changeset": 999,
        }
    )


@pytest.fixture
def mock_osm_element_minimal():
    """OSMElement com dados minimos."""
    return OSMElement(
        {
            "type": "node",
            "id": 987654321,
            "lat": 38.7300,
            "lon": -9.1400,
            "tags": {
                "name": "Loja Simples",
                "shop": "clothes",
            },
            "timestamp": "2025-01-15T12:00:00Z",
        }
    )


@pytest.fixture
def mock_osm_response_success():
    """Resposta bem-sucedida da Overpass API."""
    return {
        "elements": [
            {
                "type": "node",
                "id": 111,
                "lat": 38.7223,
                "lon": -9.1393,
                "tags": {"name": "Cafe A", "amenity": "cafe", "phone": "+351 911111111"},
            },
            {
                "type": "way",
                "id": 222,
                "center": {"lat": 38.7300, "lon": -9.1400},
                "tags": {
                    "name": "Restaurante B",
                    "amenity": "restaurant",
                    "website": "https://rest-b.pt",
                },
            },
            {
                "type": "node",
                "id": 333,
                "lat": 38.7400,
                "lon": -9.1500,
                "tags": {
                    "name": "Farmacia C",
                    "amenity": "pharmacy",
                    "email": "info@farmacia-c.pt",
                },
            },
        ]
    }


@pytest.fixture
def overpass_client():
    """Cliente OverpassClient para testes."""
    return OverpassClient(timeout=60)


@pytest.fixture
def osm_discovery_service(overpass_client):
    """Servico OSMDiscoveryService para testes."""
    return OSMDiscoveryService(client=overpass_client)


# =============================================================================
# Testes: OSMElement
# =============================================================================


def test_osm_element_properties(mock_osm_element):
    """Testa propriedades basicas do OSMElement."""
    elem = mock_osm_element

    assert elem.name == "Cafe Teste"
    assert elem.amenity == "cafe"
    assert elem.business_type == "cafe"
    assert elem.phone == "+351 912 345 678"
    assert elem.website == "https://cafe-teste.pt"
    assert elem.email == "info@cafe-teste.pt"
    assert elem.has_website is True
    assert elem.has_phone is True
    assert elem.lat == 38.7223
    assert elem.lon == -9.1393


def test_osm_element_address_formatting(mock_osm_element):
    """Testa formatacao de endereco."""
    elem = mock_osm_element
    address = elem.address

    assert "Rua Teste" in address
    assert "123" in address
    assert "Lisboa" in address


def test_osm_element_minimal_data(mock_osm_element_minimal):
    """Testa OSMElement com dados minimos."""
    elem = mock_osm_element_minimal

    assert elem.name == "Loja Simples"
    assert elem.shop == "clothes"
    assert elem.business_type == "clothes"
    assert elem.phone is None
    assert elem.website is None
    assert elem.has_website is False
    assert elem.address == ""


def test_osm_element_to_dict(mock_osm_element):
    """Testa conversao para dicionario."""
    elem = mock_osm_element
    data = elem.to_dict()

    assert data["osm_id"] == 123456789
    assert data["osm_type"] == "node"
    assert data["name"] == "Cafe Teste"
    assert data["business_type"] == "cafe"
    assert data["latitude"] == 38.7223
    assert data["longitude"] == -9.1393
    assert "https://www.openstreetmap.org/node/123456789" in data["osm_url"]


def test_osm_element_without_coordinates():
    """Testa OSMElement sem coordenadas (caso edge)."""
    elem = OSMElement(
        {
            "type": "relation",
            "id": 999,
            "tags": {"name": "Area Sem Coords", "amenity": "parking"},
        }
    )

    assert elem.name == "Area Sem Coords"
    assert elem.lat is None
    assert elem.lon is None


# =============================================================================
# Testes: OverpassClient
# =============================================================================


@pytest.mark.asyncio
async def test_overpass_client_build_query(overpass_client):
    """Testa construcao de query Overpass QL."""
    bbox = (38.691, -9.230, 38.796, -9.087)
    query = overpass_client._build_simple_query(
        bbox=bbox,
        days_back=7,
        amenity_types=["cafe", "restaurant"],
        shop_types=["bakery"],
    )

    assert "[out:json]" in query
    assert "timeout:60" in query
    assert "amenity" in query
    assert "cafe" in query
    assert "restaurant" in query
    assert "shop" in query
    assert "bakery" in query
    assert "newer:" in query


@pytest.mark.asyncio
async def test_overpass_client_discover_success(overpass_client, mock_osm_response_success):
    """Testa descoberta bem-sucedida de negocios."""
    with patch.object(
        overpass_client, "_make_request", new=AsyncMock(return_value=mock_osm_response_success)
    ):
        elements = await overpass_client.discover_new_businesses(
            area="lisboa",
            days_back=7,
        )

    assert len(elements) == 3
    assert elements[0].name == "Cafe A"
    assert elements[1].name == "Restaurante B"
    assert elements[2].name == "Farmacia C"


@pytest.mark.asyncio
async def test_overpass_client_discover_with_bbox(overpass_client, mock_osm_response_success):
    """Testa descoberta usando bbox customizado."""
    bbox = (38.7, -9.2, 38.8, -9.1)

    with patch.object(
        overpass_client, "_make_request", new=AsyncMock(return_value=mock_osm_response_success)
    ):
        elements = await overpass_client.discover_new_businesses(
            area=bbox,
            days_back=7,
        )

    assert len(elements) == 3


@pytest.mark.asyncio
async def test_overpass_client_timeout_error(overpass_client):
    """Testa tratamento de erro de timeout."""
    with patch.object(
        overpass_client, "_make_request", side_effect=OverpassTimeoutError("Timeout")
    ):
        with pytest.raises(OverpassTimeoutError):
            await overpass_client.discover_new_businesses(area="lisboa", days_back=7)


@pytest.mark.asyncio
async def test_overpass_client_rate_limit_error(overpass_client):
    """Testa tratamento de rate limiting."""
    with patch.object(
        overpass_client, "_make_request", side_effect=OverpassRateLimitError("Rate limit")
    ):
        with pytest.raises(OverpassRateLimitError):
            await overpass_client.discover_new_businesses(area="lisboa", days_back=7)


@pytest.mark.asyncio
async def test_overpass_client_empty_response(overpass_client):
    """Testa resposta vazia (sem elementos)."""
    with patch.object(
        overpass_client, "_make_request", new=AsyncMock(return_value={"elements": []})
    ):
        elements = await overpass_client.discover_new_businesses(area="lisboa", days_back=7)

    assert len(elements) == 0


@pytest.mark.asyncio
async def test_overpass_client_filter_elements_without_name(overpass_client):
    """Testa filtragem de elementos sem nome."""
    response = {
        "elements": [
            {
                "type": "node",
                "id": 1,
                "lat": 38.7,
                "lon": -9.1,
                "tags": {"name": "Cafe X", "amenity": "cafe"},
            },
            {
                "type": "node",
                "id": 2,
                "lat": 38.7,
                "lon": -9.1,
                "tags": {"amenity": "parking"},
            },  # Sem nome
            {
                "type": "node",
                "id": 3,
                "lat": 38.7,
                "lon": -9.1,
                "tags": {"name": "Loja Y", "shop": "bakery"},
            },
        ]
    }

    with patch.object(overpass_client, "_make_request", new=AsyncMock(return_value=response)):
        elements = await overpass_client.discover_new_businesses(area="lisboa", days_back=7)

    # Deve filtrar elemento sem nome
    assert len(elements) == 2
    assert elements[0].name == "Cafe X"
    assert elements[1].name == "Loja Y"


@pytest.mark.asyncio
async def test_overpass_client_get_element_by_id(overpass_client):
    """Testa busca de elemento por ID."""
    response = {
        "elements": [
            {
                "type": "node",
                "id": 123,
                "lat": 38.7,
                "lon": -9.1,
                "tags": {"name": "Cafe Especifico", "amenity": "cafe"},
            }
        ]
    }

    with patch.object(overpass_client, "_make_request", new=AsyncMock(return_value=response)):
        element = await overpass_client.get_element_by_id("node", 123)

    assert element is not None
    assert element.name == "Cafe Especifico"
    assert element.id == 123


@pytest.mark.asyncio
async def test_overpass_client_count_new_businesses(overpass_client, mock_osm_response_success):
    """Testa contagem de negocios por tipo."""
    with patch.object(
        overpass_client, "_make_request", new=AsyncMock(return_value=mock_osm_response_success)
    ):
        counts = await overpass_client.count_new_businesses(area="lisboa", days_back=7)

    assert counts["cafe"] == 1
    assert counts["restaurant"] == 1
    assert counts["pharmacy"] == 1


@pytest.mark.asyncio
async def test_overpass_client_health_check(overpass_client):
    """Testa health check da API."""
    with patch.object(
        overpass_client, "_make_request", new=AsyncMock(return_value={"elements": []})
    ):
        is_healthy = await overpass_client.health_check()

    assert is_healthy is True


@pytest.mark.asyncio
async def test_overpass_client_health_check_failure(overpass_client):
    """Testa health check com falha."""
    with patch.object(overpass_client, "_make_request", side_effect=OverpassError("API down")):
        is_healthy = await overpass_client.health_check()

    assert is_healthy is False


@pytest.mark.asyncio
async def test_overpass_client_geocode_location(overpass_client):
    """Testa geocodificacao de localizacao."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = [
        {
            "lat": "38.7223",
            "lon": "-9.1393",
            "display_name": "Lisboa, Portugal",
            "boundingbox": ["38.691", "38.796", "-9.230", "-9.087"],
            "type": "city",
            "osm_type": "relation",
            "osm_id": 123456,
        }
    ]

    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=mock_response)):
        result = await overpass_client.geocode_location("Lisboa")

    assert result is not None
    assert result["lat"] == 38.7223
    assert result["lon"] == -9.1393
    assert "Lisboa" in result["display_name"]
    assert result["bbox"] is not None


# =============================================================================
# Testes: OSMDiscoveryService
# =============================================================================


def test_osm_discovery_calculate_score_complete(mock_osm_element):
    """Testa calculo de score para elemento completo."""
    score = OSMDiscoveryService._calculate_osm_score(mock_osm_element)

    # Nome + coords + endereco + telefone + website + email + opening_hours + tipo cafe
    # 10 + 10 + 15 + 20 + 25 + 15 + 5 = 100
    assert score == 100


def test_osm_discovery_calculate_score_minimal(mock_osm_element_minimal):
    """Testa calculo de score para elemento minimo."""
    score = OSMDiscoveryService._calculate_osm_score(mock_osm_element_minimal)

    # Apenas nome + coords
    # 10 + 10 = 20
    assert score == 20


@pytest.mark.asyncio
async def test_osm_discovery_discover_success(osm_discovery_service, mock_osm_response_success):
    """Testa descoberta bem-sucedida."""
    with patch.object(
        osm_discovery_service.client,
        "_make_request",
        new=AsyncMock(return_value=mock_osm_response_success),
    ):
        with patch("src.services.osm_discovery.db.get_session") as mock_session:
            mock_session.return_value.__enter__.return_value = MagicMock()

            result = await osm_discovery_service.discover(
                area="lisboa",
                days_back=7,
                save_to_db=False,
            )

    assert isinstance(result, DiscoveryResult)
    assert result.total_found == 3
    assert result.new_businesses == 3
    assert result.area == "lisboa"
    assert result.days_back == 7
    assert len(result.errors) == 0


@pytest.mark.asyncio
async def test_osm_discovery_discover_with_error(osm_discovery_service):
    """Testa descoberta com erro da API."""
    with patch.object(
        osm_discovery_service.client,
        "discover_new_businesses",
        side_effect=OverpassError("API Error"),
    ):
        result = await osm_discovery_service.discover(area="lisboa", days_back=7)

    assert result.total_found == 0
    assert result.new_businesses == 0
    assert len(result.errors) == 1
    assert "API Error" in result.errors[0]


@pytest.mark.asyncio
async def test_osm_discovery_preview(osm_discovery_service, mock_osm_response_success):
    """Testa preview de negocios sem guardar."""
    with patch.object(
        osm_discovery_service.client,
        "_make_request",
        new=AsyncMock(return_value=mock_osm_response_success),
    ):
        previews = await osm_discovery_service.preview(
            area="lisboa",
            days_back=7,
            limit=2,
        )

    assert len(previews) == 2  # Limitado a 2
    assert "osm_score" in previews[0]
    assert "source" in previews[0]
    assert previews[0]["source"] == "openstreetmap"


@pytest.mark.asyncio
async def test_osm_discovery_preview_with_error(osm_discovery_service):
    """Testa preview com erro da API."""
    with patch.object(
        osm_discovery_service.client, "discover_new_businesses", side_effect=OverpassError("Error")
    ):
        previews = await osm_discovery_service.preview(area="lisboa", days_back=7)

    assert len(previews) == 0


@pytest.mark.asyncio
async def test_osm_discovery_get_element_details(osm_discovery_service):
    """Testa busca de detalhes de elemento."""
    mock_element = OSMElement(
        {
            "type": "node",
            "id": 123,
            "lat": 38.7,
            "lon": -9.1,
            "tags": {"name": "Teste", "amenity": "cafe"},
        }
    )

    with patch.object(
        osm_discovery_service.client, "get_element_by_id", new=AsyncMock(return_value=mock_element)
    ):
        details = await osm_discovery_service.get_element_details("node", 123)

    assert details is not None
    assert details["name"] == "Teste"
    assert "osm_score" in details


@pytest.mark.asyncio
async def test_osm_discovery_count_by_area(osm_discovery_service, mock_osm_response_success):
    """Testa contagem por area."""
    with patch.object(
        osm_discovery_service.client,
        "count_new_businesses",
        new=AsyncMock(return_value={"cafe": 5, "restaurant": 3}),
    ):
        results = await osm_discovery_service.count_by_area(
            areas=["lisboa", "porto"],
            days_back=7,
        )

    assert "lisboa" in results
    assert "porto" in results


@pytest.mark.asyncio
async def test_osm_discovery_health_check(osm_discovery_service):
    """Testa health check do servico."""
    with patch.object(
        osm_discovery_service.client, "health_check", new=AsyncMock(return_value=True)
    ):
        health = await osm_discovery_service.health_check()

    assert health["service"] == "osm_discovery"
    assert health["status"] == "healthy"
    assert health["overpass_api"] is True
    assert "available_areas" in health


@pytest.mark.asyncio
async def test_osm_discovery_discover_by_text_success(
    osm_discovery_service, mock_osm_response_success
):
    """Testa descoberta por texto de localizacao."""
    location_info = {
        "display_name": "Almada, Portugal",
        "bbox": (38.65, -9.18, 38.70, -9.13),
    }

    with patch.object(
        osm_discovery_service.client,
        "discover_by_location_text",
        new=AsyncMock(
            return_value=(
                [OSMElement(elem) for elem in mock_osm_response_success["elements"]],
                location_info,
            )
        ),
    ):
        result, loc_info = await osm_discovery_service.discover_by_text(
            location_query="Almada",
            days_back=7,
            save_to_db=False,
        )

    assert result.total_found == 3
    assert "Almada" in result.area
    assert loc_info is not None


@pytest.mark.asyncio
async def test_osm_discovery_discover_by_text_not_found(osm_discovery_service):
    """Testa descoberta por texto com localizacao nao encontrada."""
    with patch.object(
        osm_discovery_service.client,
        "discover_by_location_text",
        new=AsyncMock(return_value=([], None)),
    ):
        result, loc_info = await osm_discovery_service.discover_by_text(
            location_query="LocalInexistente",
            days_back=7,
            save_to_db=False,
        )

    assert result.total_found == 0
    assert "nao encontrada" in result.errors[0]
    assert loc_info is None


def test_osm_discovery_get_business_types(osm_discovery_service):
    """Testa obtencao de tipos de negocio."""
    types = osm_discovery_service.get_business_types()

    assert isinstance(types, dict)
    assert "Restauracao" in types
    assert "Saude" in types
    assert len(types) > 0
