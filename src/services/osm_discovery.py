"""Servico de descoberta de negocios via OpenStreetMap."""

from dataclasses import dataclass
from typing import Any

from src.api.overpass import OSMElement, OverpassClient, OverpassError
from src.config import settings
from src.database.db import db
from src.database.models import Business
from src.database.queries import BusinessQueries, SearchHistoryQueries
from src.services.scorer import LeadScorer


@dataclass
class DiscoveryResult:
    """Resultado de uma descoberta OSM."""

    total_found: int
    new_businesses: int
    updated_businesses: int
    area: str
    days_back: int
    execution_time_seconds: float
    errors: list[str]


class OSMDiscoveryService:
    """Servico para descobrir negocios novos via OpenStreetMap/Overpass API."""

    def __init__(
        self,
        client: OverpassClient | None = None,
        scorer: LeadScorer | None = None,
    ):
        """
        Inicializa o servico.

        Args:
            client: Cliente Overpass (opcional)
            scorer: Scorer de leads (opcional)
        """
        self.client = client or OverpassClient(timeout=settings.osm_timeout)
        self.scorer = scorer or LeadScorer()

    @staticmethod
    def _osm_element_to_business(element: OSMElement) -> Business:
        """
        Converte OSMElement para modelo Business.

        Args:
            element: Elemento OSM

        Returns:
            Business populado
        """
        # ID unico baseado no tipo e ID do OSM
        osm_id = f"osm_{element.type}_{element.id}"

        # Construir URL do Google Maps baseado nas coordenadas (para visualizacao)
        google_maps_url = None
        if element.lat and element.lon:
            google_maps_url = (
                f"https://www.google.com/maps/search/?api=1&query={element.lat},{element.lon}"
            )

        return Business(
            id=osm_id,
            name=element.name,
            formatted_address=element.address or "",
            latitude=element.lat,
            longitude=element.lon,
            place_types=[element.business_type],
            business_status="OPERATIONAL",  # OSM nao tem este campo
            phone_number=element.phone,
            website=element.website,
            google_maps_url=google_maps_url,
            rating=None,  # OSM nao tem ratings
            review_count=0,
            has_website=element.has_website,
            has_photos=False,  # OSM nao tem fotos estruturadas
            photo_count=0,
            last_search_query=f"osm:discovery:{element.business_type}",
            data_expires_at=None,  # OSM permite guardar indefinidamente (ODbL)
            email=element.email,
        )

    @staticmethod
    def _calculate_osm_score(element: OSMElement) -> int:
        """
        Calcula score especifico para negocio OSM.

        Como OSM nao tem ratings/reviews, o score e baseado em:
        - Completude dos dados (nome, endereco, telefone, website, email)
        - Tipo de negocio (alguns tipos sao mais valiosos para lead gen)

        Args:
            element: Elemento OSM

        Returns:
            Score de 0-100
        """
        score = 0

        # Nome presente (obrigatorio, ja filtrado)
        score += 10

        # Coordenadas presentes
        if element.lat and element.lon:
            score += 10

        # Endereco
        if element.address:
            score += 15

        # Contactos (muito importantes para lead gen)
        if element.phone:
            score += 20
        if element.website:
            score += 25
        if element.email:
            score += 15

        # Horario de funcionamento (indica negocio ativo)
        if element.opening_hours:
            score += 5

        # Bonus por tipo de negocio de alto valor
        high_value_types = [
            "restaurant",
            "cafe",
            "bar",
            "clinic",
            "dentist",
            "doctors",
            "beauty_salon",
            "hairdresser",
            "gym",
            "fitness_centre",
            "car_repair",
            "veterinary",
        ]
        if element.business_type in high_value_types:
            score += 10

        return min(score, 100)

    async def discover(
        self,
        area: str = "lisboa",
        days_back: int | None = None,
        amenity_types: list[str] | None = None,
        shop_types: list[str] | None = None,
        save_to_db: bool = True,
    ) -> DiscoveryResult:
        """
        Descobre negocios novos via OSM.

        Args:
            area: Area de pesquisa (lisboa, porto, portugal, etc)
            days_back: Dias atras para filtro newer (None = usar settings)
            amenity_types: Tipos de amenity a incluir
            shop_types: Tipos de shop a incluir
            save_to_db: Se True, guarda resultados na DB

        Returns:
            DiscoveryResult com estatisticas
        """
        import time

        start_time = time.time()
        errors: list[str] = []

        # Usar defaults se nao especificado
        if days_back is None:
            days_back = settings.osm_discovery_days

        # Executar descoberta
        try:
            elements = await self.client.discover_new_businesses(
                area=area,
                days_back=days_back,
                amenity_types=amenity_types,
                shop_types=shop_types,
            )
        except OverpassError as e:
            return DiscoveryResult(
                total_found=0,
                new_businesses=0,
                updated_businesses=0,
                area=area,
                days_back=days_back,
                execution_time_seconds=time.time() - start_time,
                errors=[str(e)],
            )

        new_count = 0
        updated_count = 0

        if save_to_db:
            with db.get_session() as session:
                for element in elements:
                    try:
                        business = self._osm_element_to_business(element)

                        # Calcular score especifico para OSM
                        business.lead_score = self._calculate_osm_score(element)

                        # Upsert
                        _, is_new = BusinessQueries.upsert(session, business)
                        if is_new:
                            new_count += 1
                        else:
                            updated_count += 1

                    except Exception as e:
                        errors.append(f"Erro ao processar {element.name}: {str(e)}")

                # Registar no historico
                SearchHistoryQueries.add(
                    session=session,
                    query_type="osm_discovery",
                    query_params={
                        "area": area,
                        "days_back": days_back,
                        "amenity_types": amenity_types,
                        "shop_types": shop_types,
                    },
                    results_count=len(elements),
                    new_count=new_count,
                    api_calls=1,
                )
        else:
            # So contar
            new_count = len(elements)

        return DiscoveryResult(
            total_found=len(elements),
            new_businesses=new_count,
            updated_businesses=updated_count,
            area=area,
            days_back=days_back,
            execution_time_seconds=time.time() - start_time,
            errors=errors,
        )

    async def discover_all_areas(
        self,
        areas: list[str] | None = None,
        days_back: int | None = None,
    ) -> dict[str, DiscoveryResult]:
        """
        Descobre negocios em multiplas areas.

        Args:
            areas: Lista de areas (None = todas as predefinidas)
            days_back: Dias atras para filtro

        Returns:
            Dict com resultados por area
        """
        if areas is None:
            areas = list(self.client.BOUNDING_BOXES.keys())

        results: dict[str, DiscoveryResult] = {}

        for area in areas:
            results[area] = await self.discover(
                area=area,
                days_back=days_back,
            )

        return results

    async def preview(
        self,
        area: str = "lisboa",
        days_back: int = 7,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """
        Preview de negocios sem guardar na DB.

        Args:
            area: Area de pesquisa
            days_back: Dias atras
            limit: Maximo de resultados

        Returns:
            Lista de dicts com preview dos negocios
        """
        try:
            elements = await self.client.discover_new_businesses(
                area=area,
                days_back=days_back,
            )
        except OverpassError:
            return []

        previews = []
        for element in elements[:limit]:
            preview = element.to_dict()
            preview["osm_score"] = self._calculate_osm_score(element)
            preview["source"] = "openstreetmap"
            previews.append(preview)

        return previews

    async def get_element_details(
        self,
        osm_type: str,
        osm_id: int,
    ) -> dict[str, Any] | None:
        """
        Busca detalhes de um elemento OSM especifico.

        Args:
            osm_type: Tipo (node, way, relation)
            osm_id: ID do elemento

        Returns:
            Dict com detalhes ou None
        """
        element = await self.client.get_element_by_id(osm_type, osm_id)
        if element:
            data = element.to_dict()
            data["osm_score"] = self._calculate_osm_score(element)
            return data
        return None

    async def count_by_area(
        self,
        areas: list[str] | None = None,
        days_back: int = 7,
    ) -> dict[str, dict[str, int]]:
        """
        Conta negocios novos por area e tipo.

        Args:
            areas: Lista de areas (None = predefinidas)
            days_back: Dias atras

        Returns:
            Dict com contagens {area: {tipo: count}}
        """
        if areas is None:
            areas = list(self.client.BOUNDING_BOXES.keys())

        results: dict[str, dict[str, int]] = {}

        for area in areas:
            try:
                counts = await self.client.count_new_businesses(
                    area=area,
                    days_back=days_back,
                )
                results[area] = counts
            except OverpassError:
                results[area] = {}

        return results

    async def health_check(self) -> dict[str, Any]:
        """
        Verifica estado do servico OSM.

        Returns:
            Dict com informacoes de saude
        """
        is_healthy = await self.client.health_check()

        return {
            "service": "osm_discovery",
            "status": "healthy" if is_healthy else "unhealthy",
            "overpass_api": is_healthy,
            "default_area": settings.osm_default_area,
            "discovery_days": settings.osm_discovery_days,
            "available_areas": list(self.client.BOUNDING_BOXES.keys()),
        }

    async def discover_by_text(
        self,
        location_query: str,
        days_back: int | None = None,
        business_type: str | None = None,
        save_to_db: bool = True,
    ) -> tuple[DiscoveryResult, dict | None]:
        """
        Descobre negocios por texto livre de localizacao.

        Args:
            location_query: Texto da localizacao (ex: "Almada", "Setubal")
            days_back: Dias atras
            business_type: Tipo de negocio especifico
            save_to_db: Se True, guarda na DB

        Returns:
            Tupla (DiscoveryResult, location_info)
        """
        import time

        start_time = time.time()
        errors: list[str] = []

        if days_back is None:
            days_back = settings.osm_discovery_days

        # Descobrir por texto
        try:
            elements, location_info = await self.client.discover_by_location_text(
                location_query=location_query,
                days_back=days_back,
                business_type=business_type,
            )
        except OverpassError as e:
            result = DiscoveryResult(
                total_found=0,
                new_businesses=0,
                updated_businesses=0,
                area=location_query,
                days_back=days_back,
                execution_time_seconds=time.time() - start_time,
                errors=[str(e)],
            )
            return result, None

        if not location_info:
            result = DiscoveryResult(
                total_found=0,
                new_businesses=0,
                updated_businesses=0,
                area=location_query,
                days_back=days_back,
                execution_time_seconds=time.time() - start_time,
                errors=["Localizacao nao encontrada"],
            )
            return result, None

        new_count = 0
        updated_count = 0

        if save_to_db and elements:
            with db.get_session() as session:
                for element in elements:
                    try:
                        business = self._osm_element_to_business(element)
                        business.lead_score = self._calculate_osm_score(element)

                        _, is_new = BusinessQueries.upsert(session, business)
                        if is_new:
                            new_count += 1
                        else:
                            updated_count += 1
                    except Exception as e:
                        errors.append(f"Erro ao processar {element.name}: {str(e)}")

                SearchHistoryQueries.add(
                    session=session,
                    query_type="osm_discovery",
                    query_params={
                        "location_query": location_query,
                        "days_back": days_back,
                        "business_type": business_type,
                    },
                    results_count=len(elements),
                    new_count=new_count,
                    api_calls=1,
                )
        else:
            new_count = len(elements)

        display_name = location_info.get("display_name", location_query)

        result = DiscoveryResult(
            total_found=len(elements),
            new_businesses=new_count,
            updated_businesses=updated_count,
            area=display_name,
            days_back=days_back,
            execution_time_seconds=time.time() - start_time,
            errors=errors,
        )

        return result, location_info

    async def preview_by_text(
        self,
        location_query: str,
        days_back: int = 7,
        business_type: str | None = None,
        limit: int = 50,
    ) -> tuple[list[dict[str, Any]], dict | None]:
        """
        Preview por texto sem guardar na DB.

        Returns:
            Tupla (lista de previews, location_info)
        """
        try:
            elements, location_info = await self.client.discover_by_location_text(
                location_query=location_query,
                days_back=days_back,
                business_type=business_type,
            )
        except OverpassError:
            return [], None

        if not location_info:
            return [], None

        previews = []
        for element in elements[:limit]:
            preview = element.to_dict()
            preview["osm_score"] = self._calculate_osm_score(element)
            preview["source"] = "openstreetmap"
            previews.append(preview)

        return previews, location_info

    def get_business_types(self) -> dict[str, list[dict]]:
        """Retorna tipos de negocio organizados."""
        return self.client.get_business_types()

    async def search_locations(self, query: str, limit: int = 5) -> list[dict]:
        """Pesquisa localizacoes para autocomplete."""
        return await self.client.search_locations(query, limit)


# Instancia global para uso direto
osm_discovery_service = OSMDiscoveryService()
