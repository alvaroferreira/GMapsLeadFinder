"""Servico de pesquisa de negocios."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from src.api.google_places import GooglePlacesClient, Place
from src.database.db import db
from src.database.models import Business
from src.database.queries import BusinessQueries, SearchHistoryQueries
from src.services.scorer import LeadScorer


@dataclass
class SearchResult:
    """Resultado de uma pesquisa."""

    total_found: int
    new_businesses: int
    updated_businesses: int
    filtered_out: int
    api_calls: int


class SearchService:
    """Servico para pesquisar e guardar negocios."""

    def __init__(
        self,
        client: GooglePlacesClient | None = None,
        scorer: LeadScorer | None = None,
    ):
        """
        Inicializa o servico.

        Args:
            client: Cliente Google Places (opcional)
            scorer: Scorer de leads (opcional)
        """
        self.client = client or GooglePlacesClient()
        self.scorer = scorer or LeadScorer()

    def _place_to_business(self, place: Place, search_query: str) -> Business:
        """
        Converte Place da API para modelo Business.

        Args:
            place: Place retornado pela API
            search_query: Query usada na pesquisa

        Returns:
            Business populado
        """
        return Business(
            id=place.id,
            name=place.name,
            formatted_address=place.formattedAddress,
            latitude=place.location.latitude if place.location else None,
            longitude=place.location.longitude if place.location else None,
            place_types=place.types or [],
            business_status=place.businessStatus,
            phone_number=place.nationalPhoneNumber,
            international_phone=place.internationalPhoneNumber,
            website=place.websiteUri,
            google_maps_url=place.googleMapsUri,
            rating=place.rating,
            review_count=place.userRatingCount or 0,
            price_level=place.price_level_int,
            has_website=place.has_website,
            has_photos=place.photo_count > 0,
            photo_count=place.photo_count,
            last_search_query=search_query,
            data_expires_at=datetime.utcnow() + timedelta(days=30),
        )

    def _apply_filters(
        self,
        place: Place,
        min_reviews: int | None = None,
        max_reviews: int | None = None,
        min_rating: float | None = None,
        max_rating: float | None = None,
        has_website: bool | None = None,
        has_phone: bool | None = None,
    ) -> bool:
        """
        Aplica filtros pos-pesquisa (que a API nao suporta).

        Returns:
            True se passa todos os filtros
        """
        review_count = place.userRatingCount or 0

        if min_reviews is not None and review_count < min_reviews:
            return False
        if max_reviews is not None and review_count > max_reviews:
            return False
        if min_rating is not None and (place.rating is None or place.rating < min_rating):
            return False
        if max_rating is not None and place.rating is not None and place.rating > max_rating:
            return False
        if has_website is not None and place.has_website != has_website:
            return False
        if has_phone is not None and place.has_phone != has_phone:
            return False

        return True

    async def search(
        self,
        query: str,
        location: tuple[float, float] | None = None,
        radius: int = 5000,
        place_type: str | None = None,
        max_results: int = 60,
        # Filtros pos-pesquisa
        min_reviews: int | None = None,
        max_reviews: int | None = None,
        min_rating: float | None = None,
        max_rating: float | None = None,
        has_website: bool | None = None,
        has_phone: bool | None = None,
    ) -> SearchResult:
        """
        Executa pesquisa e guarda resultados na DB.

        Args:
            query: Texto de pesquisa
            location: Tupla (lat, lng) opcional
            radius: Raio em metros
            place_type: Tipo de negocio
            max_results: Maximo de resultados
            min_reviews: Minimo de reviews
            max_reviews: Maximo de reviews
            min_rating: Rating minimo
            max_rating: Rating maximo
            has_website: Filtrar por ter website
            has_phone: Filtrar por ter telefone

        Returns:
            SearchResult com estatisticas
        """
        results: list[Business] = []
        new_count = 0
        updated_count = 0
        filtered_count = 0
        api_calls = 0

        # Pesquisa na API
        async for place in self.client.search_all_pages(
            query=query,
            location=location,
            radius=radius,
            included_type=place_type,
            max_total_results=max_results,
        ):
            api_calls += 1

            # Aplicar filtros
            if not self._apply_filters(
                place,
                min_reviews=min_reviews,
                max_reviews=max_reviews,
                min_rating=min_rating,
                max_rating=max_rating,
                has_website=has_website,
                has_phone=has_phone,
            ):
                filtered_count += 1
                continue

            business = self._place_to_business(place, query)
            results.append(business)

        # Guardar na DB
        with db.get_session() as session:
            for business in results:
                # Calcular lead score
                business.lead_score = self.scorer.calculate(business)

                # Upsert
                _, is_new = BusinessQueries.upsert(session, business)
                if is_new:
                    new_count += 1
                else:
                    updated_count += 1

            # Registar no historico
            SearchHistoryQueries.add(
                session=session,
                query_type="text",
                query_params={
                    "query": query,
                    "location": location,
                    "radius": radius,
                    "place_type": place_type,
                    "filters": {
                        "min_reviews": min_reviews,
                        "max_reviews": max_reviews,
                        "min_rating": min_rating,
                        "max_rating": max_rating,
                        "has_website": has_website,
                    },
                },
                results_count=len(results),
                new_count=new_count,
                api_calls=api_calls,
            )

        return SearchResult(
            total_found=len(results),
            new_businesses=new_count,
            updated_businesses=updated_count,
            filtered_out=filtered_count,
            api_calls=api_calls,
        )

    async def nearby_search(
        self,
        latitude: float,
        longitude: float,
        radius: int = 5000,
        place_types: list[str] | None = None,
        max_results: int = 20,
    ) -> SearchResult:
        """
        Pesquisa por proximidade geografica.

        Args:
            latitude: Latitude do centro
            longitude: Longitude do centro
            radius: Raio em metros
            place_types: Lista de tipos de negocio
            max_results: Maximo de resultados

        Returns:
            SearchResult com estatisticas
        """
        new_count = 0
        updated_count = 0

        response = await self.client.nearby_search(
            latitude=latitude,
            longitude=longitude,
            radius=radius,
            included_types=place_types,
            max_results=max_results,
        )

        search_query = f"nearby:{latitude},{longitude}"

        with db.get_session() as session:
            for place in response.places:
                business = self._place_to_business(place, search_query)
                business.lead_score = self.scorer.calculate(business)

                _, is_new = BusinessQueries.upsert(session, business)
                if is_new:
                    new_count += 1
                else:
                    updated_count += 1

            SearchHistoryQueries.add(
                session=session,
                query_type="nearby",
                query_params={
                    "latitude": latitude,
                    "longitude": longitude,
                    "radius": radius,
                    "place_types": place_types,
                },
                results_count=len(response.places),
                new_count=new_count,
                api_calls=1,
            )

        return SearchResult(
            total_found=len(response.places),
            new_businesses=new_count,
            updated_businesses=len(response.places) - new_count,
            filtered_out=0,
            api_calls=1,
        )

    def get_leads(
        self,
        status: str | None = None,
        min_score: int | None = None,
        has_website: bool | None = None,
        city: str | None = None,
        limit: int = 100,
    ) -> list[Business]:
        """
        Retorna leads da base de dados.

        Args:
            status: Filtrar por status
            min_score: Score minimo
            has_website: Filtrar por website
            city: Filtrar por cidade
            limit: Maximo de resultados

        Returns:
            Lista de Business
        """
        with db.get_session() as session:
            return BusinessQueries.get_all(
                session,
                status=status,
                min_score=min_score,
                has_website=has_website,
                city=city,
                limit=limit,
            )

    def get_stats(self) -> dict[str, Any]:
        """Retorna estatisticas da base de dados."""
        with db.get_session() as session:
            return BusinessQueries.get_stats(session)
