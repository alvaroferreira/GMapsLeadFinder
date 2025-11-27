"""Testes para API models e client."""

from unittest.mock import AsyncMock, patch

import pytest

from src.api.models import (
    Place,
    SearchResponse,
    DisplayName,
    Location,
    PlacePhoto,
)
from src.api.google_places import GooglePlacesClient, GooglePlacesAuthError


class TestPlaceModel:
    """Testes para o modelo Place."""

    def test_place_name_property(self):
        """Deve retornar nome do displayName."""
        place = Place(
            id="test123",
            displayName=DisplayName(text="Restaurante Teste", languageCode="pt"),
        )
        assert place.name == "Restaurante Teste"

    def test_place_name_unknown(self):
        """Deve retornar 'Unknown' se sem displayName."""
        place = Place(id="test123")
        assert place.name == "Unknown"

    def test_place_has_website(self):
        """Deve verificar se tem website."""
        place_with = Place(id="test1", websiteUri="https://example.com")
        place_without = Place(id="test2")

        assert place_with.has_website is True
        assert place_without.has_website is False

    def test_place_has_phone(self):
        """Deve verificar se tem telefone."""
        place_national = Place(id="test1", nationalPhoneNumber="+351912345678")
        place_international = Place(id="test2", internationalPhoneNumber="+351912345678")
        place_without = Place(id="test3")

        assert place_national.has_phone is True
        assert place_international.has_phone is True
        assert place_without.has_phone is False

    def test_place_photo_count(self):
        """Deve contar fotos."""
        place_with = Place(
            id="test1",
            photos=[
                PlacePhoto(name="photo1"),
                PlacePhoto(name="photo2"),
            ],
        )
        place_without = Place(id="test2")

        assert place_with.photo_count == 2
        assert place_without.photo_count == 0

    def test_place_price_level_int(self):
        """Deve converter price level para inteiro."""
        place = Place(id="test1", priceLevel="PRICE_LEVEL_MODERATE")
        assert place.price_level_int == 2

        place = Place(id="test2", priceLevel="PRICE_LEVEL_EXPENSIVE")
        assert place.price_level_int == 3

        place = Place(id="test3")
        assert place.price_level_int is None


class TestSearchResponse:
    """Testes para SearchResponse."""

    def test_empty_response(self):
        """Deve aceitar resposta vazia."""
        response = SearchResponse()
        assert response.places == []
        assert response.nextPageToken is None

    def test_response_with_places(self):
        """Deve parsear resposta com lugares."""
        response = SearchResponse(
            places=[
                Place(id="place1"),
                Place(id="place2"),
            ],
            nextPageToken="token123",
        )
        assert len(response.places) == 2
        assert response.nextPageToken == "token123"


class TestGooglePlacesClient:
    """Testes para GooglePlacesClient."""

    def test_client_initialization(self):
        """Deve inicializar cliente com API key."""
        client = GooglePlacesClient(api_key="test_key")
        assert client.api_key == "test_key"

    def test_headers(self):
        """Deve gerar headers corretos."""
        client = GooglePlacesClient(api_key="test_key")
        headers = client._get_headers()

        assert headers["X-Goog-Api-Key"] == "test_key"
        assert headers["Content-Type"] == "application/json"
        assert "X-Goog-FieldMask" in headers

    @pytest.mark.asyncio
    async def test_text_search_builds_payload(self):
        """Deve construir payload correto para text search."""
        client = GooglePlacesClient(api_key="test_key")

        with patch.object(client, "_make_request", new_callable=AsyncMock) as mock:
            mock.return_value = {"places": []}

            await client.text_search(
                query="restaurante Lisboa",
                location=(38.7223, -9.1393),
                radius=5000,
            )

            call_args = mock.call_args
            endpoint = call_args[0][0]
            payload = call_args[0][1]

            assert endpoint == "places:searchText"
            assert payload["textQuery"] == "restaurante Lisboa"
            assert payload["locationBias"]["circle"]["center"]["latitude"] == 38.7223
            assert payload["locationBias"]["circle"]["radius"] == 5000.0

    @pytest.mark.asyncio
    async def test_text_search_with_type(self):
        """Deve incluir tipo na pesquisa."""
        client = GooglePlacesClient(api_key="test_key")

        with patch.object(client, "_make_request", new_callable=AsyncMock) as mock:
            mock.return_value = {"places": []}

            await client.text_search(
                query="Lisboa",
                included_type="restaurant",
            )

            payload = mock.call_args[0][1]
            assert payload["includedType"] == "restaurant"

    @pytest.mark.asyncio
    async def test_nearby_search_builds_payload(self):
        """Deve construir payload correto para nearby search."""
        client = GooglePlacesClient(api_key="test_key")

        with patch.object(client, "_make_request", new_callable=AsyncMock) as mock:
            mock.return_value = {"places": []}

            await client.nearby_search(
                latitude=38.7223,
                longitude=-9.1393,
                radius=3000,
                included_types=["restaurant", "cafe"],
            )

            payload = mock.call_args[0][1]

            assert payload["locationRestriction"]["circle"]["center"]["latitude"] == 38.7223
            assert payload["locationRestriction"]["circle"]["radius"] == 3000.0
            assert payload["includedTypes"] == ["restaurant", "cafe"]

    @pytest.mark.asyncio
    async def test_search_all_pages_iterates(self):
        """Deve iterar por todas as paginas."""
        client = GooglePlacesClient(api_key="test_key")

        # Simular duas paginas de resultados
        responses = [
            {
                "places": [{"id": "place1"}, {"id": "place2"}],
                "nextPageToken": "token1",
            },
            {
                "places": [{"id": "place3"}],
            },
        ]

        with patch.object(client, "_make_request", new_callable=AsyncMock) as mock:
            mock.side_effect = responses

            places = []
            async for place in client.search_all_pages("test query", max_total_results=10):
                places.append(place)

            assert len(places) == 3
            assert places[0].id == "place1"
            assert places[2].id == "place3"

    @pytest.mark.asyncio
    async def test_search_all_pages_respects_max(self):
        """Deve respeitar limite maximo de resultados."""
        client = GooglePlacesClient(api_key="test_key")

        with patch.object(client, "_make_request", new_callable=AsyncMock) as mock:
            mock.return_value = {
                "places": [{"id": f"place{i}"} for i in range(20)],
                "nextPageToken": "token",
            }

            places = []
            async for place in client.search_all_pages("test", max_total_results=5):
                places.append(place)

            assert len(places) == 5
