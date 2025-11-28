"""Cliente async para Google Places API (New)."""

import asyncio
from typing import AsyncGenerator

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.api.models import Place, SearchResponse
from src.config import settings


class GooglePlacesError(Exception):
    """Erro base para operacoes da Google Places API."""
    pass


class GooglePlacesAuthError(GooglePlacesError):
    """Erro de autenticacao (API key invalida)."""
    pass


class GooglePlacesRateLimitError(GooglePlacesError):
    """Erro de rate limiting."""
    pass


class GooglePlacesClient:
    """Cliente async para Google Places API (New)."""

    BASE_URL = "https://places.googleapis.com/v1"

    # Field mask otimizado para lead generation
    FIELD_MASK = ",".join([
        "places.id",
        "places.displayName",
        "places.formattedAddress",
        "places.location",
        "places.types",
        "places.businessStatus",
        "places.nationalPhoneNumber",
        "places.internationalPhoneNumber",
        "places.websiteUri",
        "places.googleMapsUri",
        "places.rating",
        "places.userRatingCount",
        "places.priceLevel",
        "places.photos",
        "nextPageToken",
    ])

    def __init__(self, api_key: str | None = None):
        """
        Inicializa o cliente.

        Args:
            api_key: Google Places API key. Se None, usa settings.
        """
        self.api_key = api_key or settings.google_places_api_key
        self._semaphore = asyncio.Semaphore(int(settings.requests_per_second))

    def _get_headers(self) -> dict[str, str]:
        """Retorna headers para requests."""
        return {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": self.FIELD_MASK,
        }

    @retry(
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
        stop=stop_after_attempt(settings.max_retries),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def _make_request(self, endpoint: str, payload: dict) -> dict:
        """
        Faz request a API com rate limiting e retry.

        Args:
            endpoint: Endpoint da API (ex: "places:searchText")
            payload: Dados do request

        Returns:
            dict: Resposta JSON da API

        Raises:
            GooglePlacesAuthError: Se API key invalida
            GooglePlacesRateLimitError: Se rate limit excedido
            GooglePlacesError: Para outros erros
        """
        async with self._semaphore:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.BASE_URL}/{endpoint}",
                    headers=self._get_headers(),
                    json=payload,
                    timeout=30.0,
                )

                if response.status_code == 401:
                    raise GooglePlacesAuthError("API key invalida ou nao autorizada")
                elif response.status_code == 429:
                    raise GooglePlacesRateLimitError("Rate limit excedido")
                elif response.status_code >= 400:
                    raise GooglePlacesError(
                        f"Erro na API: {response.status_code} - {response.text}"
                    )

                return response.json()

    async def text_search(
        self,
        query: str,
        location: tuple[float, float] | None = None,
        radius: int = 5000,
        included_type: str | None = None,
        min_rating: float | None = None,
        open_now: bool | None = None,
        page_token: str | None = None,
    ) -> SearchResponse:
        """
        Pesquisa por texto livre.

        Args:
            query: Texto de pesquisa (ex: "restaurante Lisboa")
            location: Tupla (latitude, longitude) para bias
            radius: Raio em metros (max 50000)
            included_type: Tipo de negocio (ex: "restaurant")
            min_rating: Rating minimo (0-5)
            open_now: Filtrar apenas abertos
            page_token: Token para proxima pagina

        Returns:
            SearchResponse: Resultados da pesquisa
        """
        payload: dict = {
            "textQuery": query,
            "languageCode": settings.default_language,
            "pageSize": settings.max_results_per_page,
        }

        if location:
            payload["locationBias"] = {
                "circle": {
                    "center": {"latitude": location[0], "longitude": location[1]},
                    "radius": float(radius),
                }
            }

        if included_type:
            payload["includedType"] = included_type
        if min_rating is not None:
            payload["minRating"] = min_rating
        if open_now is not None:
            payload["openNow"] = open_now
        if page_token:
            payload["pageToken"] = page_token

        data = await self._make_request("places:searchText", payload)
        return SearchResponse(**data)

    async def nearby_search(
        self,
        latitude: float,
        longitude: float,
        radius: int = 5000,
        included_types: list[str] | None = None,
        excluded_types: list[str] | None = None,
        max_results: int = 20,
    ) -> SearchResponse:
        """
        Pesquisa por proximidade geografica.

        Args:
            latitude: Latitude do centro
            longitude: Longitude do centro
            radius: Raio em metros (max 50000)
            included_types: Lista de tipos a incluir
            excluded_types: Lista de tipos a excluir
            max_results: Maximo de resultados (max 20)

        Returns:
            SearchResponse: Resultados da pesquisa
        """
        payload: dict = {
            "locationRestriction": {
                "circle": {
                    "center": {"latitude": latitude, "longitude": longitude},
                    "radius": float(radius),
                }
            },
            "languageCode": settings.default_language,
            "maxResultCount": min(max_results, 20),
            "rankPreference": "POPULARITY",
        }

        if included_types:
            payload["includedTypes"] = included_types
        if excluded_types:
            payload["excludedTypes"] = excluded_types

        data = await self._make_request("places:searchNearby", payload)
        return SearchResponse(**data)

    async def search_all_pages(
        self,
        query: str,
        location: tuple[float, float] | None = None,
        radius: int = 5000,
        included_type: str | None = None,
        max_total_results: int = 60,
    ) -> AsyncGenerator[Place, None]:
        """
        Itera por todas as paginas de resultados.

        Args:
            query: Texto de pesquisa
            location: Tupla (latitude, longitude) opcional
            radius: Raio em metros
            included_type: Tipo de negocio opcional
            max_total_results: Maximo total de resultados

        Yields:
            Place: Cada lugar encontrado
        """
        page_token: str | None = None
        total_returned = 0

        while total_returned < max_total_results:
            response = await self.text_search(
                query=query,
                location=location,
                radius=radius,
                included_type=included_type,
                page_token=page_token,
            )

            for place in response.places:
                yield place
                total_returned += 1
                if total_returned >= max_total_results:
                    return

            if not response.nextPageToken:
                break

            page_token = response.nextPageToken
            # Pequeno delay entre paginas para evitar rate limiting
            await asyncio.sleep(0.2)

    async def validate_api_key(self) -> bool:
        """
        Valida se a API key esta funcional.

        Returns:
            bool: True se valida, False caso contrario
        """
        try:
            # text_search nao tem parametro max_total_results
            # esse parametro e do search_all_pages
            response = await self.text_search("test")
            return True
        except GooglePlacesAuthError:
            return False
        except Exception:
            return False
