"""Cliente async para Overpass API (OpenStreetMap)."""

import asyncio
from datetime import UTC, datetime, timedelta

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)


class OverpassError(Exception):
    """Erro base para operacoes da Overpass API."""

    pass


class OverpassTimeoutError(OverpassError):
    """Erro de timeout na query."""

    pass


class OverpassRateLimitError(OverpassError):
    """Erro de rate limiting (429 ou 503)."""

    pass


class OverpassSyntaxError(OverpassError):
    """Erro de sintaxe na query Overpass."""

    pass


class OSMElement:
    """Representa um elemento OSM (node, way, relation)."""

    def __init__(self, data: dict):
        self.raw = data
        self.id = data.get("id")
        self.type = data.get("type", "node")
        self.tags = data.get("tags", {})
        self.lat = data.get("lat")
        self.lon = data.get("lon")

        # Para ways/relations, usar centro se disponivel
        if "center" in data:
            self.lat = data["center"].get("lat")
            self.lon = data["center"].get("lon")

        # Metadados OSM
        self.timestamp = data.get("timestamp")
        self.version = data.get("version")
        self.changeset = data.get("changeset")
        self.user = data.get("user")

    @property
    def name(self) -> str:
        """Nome do elemento."""
        return self.tags.get("name", "Sem nome")

    @property
    def amenity(self) -> str | None:
        """Tipo de amenity (restaurant, cafe, etc)."""
        return self.tags.get("amenity")

    @property
    def shop(self) -> str | None:
        """Tipo de shop (clothes, supermarket, etc)."""
        return self.tags.get("shop")

    @property
    def business_type(self) -> str:
        """Retorna o tipo principal do negocio."""
        return self.amenity or self.shop or self.tags.get("tourism") or "unknown"

    @property
    def phone(self) -> str | None:
        """Telefone do negocio."""
        return self.tags.get("phone") or self.tags.get("contact:phone")

    @property
    def website(self) -> str | None:
        """Website do negocio."""
        return self.tags.get("website") or self.tags.get("contact:website")

    @property
    def email(self) -> str | None:
        """Email do negocio."""
        return self.tags.get("email") or self.tags.get("contact:email")

    @property
    def address(self) -> str:
        """Endereco formatado."""
        parts = []
        if self.tags.get("addr:street"):
            street = self.tags.get("addr:street", "")
            number = self.tags.get("addr:housenumber", "")
            parts.append(f"{street} {number}".strip())
        if self.tags.get("addr:postcode"):
            parts.append(self.tags["addr:postcode"])
        if self.tags.get("addr:city"):
            parts.append(self.tags["addr:city"])
        return ", ".join(parts) if parts else ""

    @property
    def opening_hours(self) -> str | None:
        """Horario de funcionamento."""
        return self.tags.get("opening_hours")

    @property
    def has_website(self) -> bool:
        """Verifica se tem website."""
        return bool(self.website)

    @property
    def has_phone(self) -> bool:
        """Verifica se tem telefone."""
        return bool(self.phone)

    @property
    def osm_url(self) -> str:
        """URL para ver no OpenStreetMap."""
        return f"https://www.openstreetmap.org/{self.type}/{self.id}"

    def to_dict(self) -> dict:
        """Converte para dicionario."""
        return {
            "osm_id": self.id,
            "osm_type": self.type,
            "name": self.name,
            "business_type": self.business_type,
            "latitude": self.lat,
            "longitude": self.lon,
            "address": self.address,
            "phone": self.phone,
            "website": self.website,
            "email": self.email,
            "opening_hours": self.opening_hours,
            "osm_url": self.osm_url,
            "timestamp": self.timestamp,
            "tags": self.tags,
        }


class OverpassClient:
    """Cliente async para Overpass API."""

    # Endpoints publicos (usar varios para failover)
    ENDPOINTS = [
        "https://overpass-api.de/api/interpreter",
        "https://overpass.kumi.systems/api/interpreter",
        "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    ]

    # Tipos de negocio relevantes para lead generation
    AMENITY_TYPES = [
        "restaurant",
        "cafe",
        "bar",
        "pub",
        "fast_food",
        "pharmacy",
        "clinic",
        "dentist",
        "doctors",
        "bank",
        "bureau_de_change",
        "car_repair",
        "car_wash",
        "beauty_salon",
        "hairdresser",
        "gym",
        "fitness_centre",
        "veterinary",
        "childcare",
        "kindergarten",
        "language_school",
        "driving_school",
        "cinema",
        "theatre",
    ]

    SHOP_TYPES = [
        "supermarket",
        "convenience",
        "bakery",
        "butcher",
        "clothes",
        "shoes",
        "jewelry",
        "optician",
        "electronics",
        "computer",
        "mobile_phone",
        "furniture",
        "hardware",
        "doityourself",
        "florist",
        "pet",
        "books",
        "gift",
        "beauty",
        "cosmetics",
        "car",
        "car_parts",
        "bicycle",
    ]

    # Bounding boxes pre-definidos para Portugal
    BOUNDING_BOXES = {
        "portugal": (36.838269, -9.526086, 42.280469, -6.189158),
        "lisboa": (38.691, -9.230, 38.796, -9.087),
        "porto": (41.121, -8.691, 41.185, -8.551),
        "faro": (36.980, -7.970, 37.050, -7.900),
        "braga": (41.530, -8.470, 41.580, -8.390),
        "coimbra": (40.170, -8.470, 40.240, -8.390),
    }

    def __init__(self, timeout: int = 180):
        """
        Inicializa o cliente.

        Args:
            timeout: Timeout em segundos para queries (default 180s)
        """
        self.timeout = timeout
        self._semaphore = asyncio.Semaphore(2)  # Max 2 requests simultaneos
        self._current_endpoint_idx = 0

    def _get_endpoint(self) -> str:
        """Retorna endpoint atual (com round-robin em caso de falha)."""
        return self.ENDPOINTS[self._current_endpoint_idx % len(self.ENDPOINTS)]

    def _next_endpoint(self) -> str:
        """Muda para proximo endpoint."""
        self._current_endpoint_idx += 1
        return self._get_endpoint()

    def _build_query(
        self,
        bbox: tuple[float, float, float, float] | None = None,
        area_name: str | None = None,
        days_back: int = 7,
        amenity_types: list[str] | None = None,
        shop_types: list[str] | None = None,
        include_all_types: bool = False,
    ) -> str:
        """
        Constroi query Overpass QL.

        Args:
            bbox: Bounding box (min_lat, min_lon, max_lat, max_lon)
            area_name: Nome da area (ex: "Lisboa", "Portugal")
            days_back: Dias atras para filtro `newer` (0 = todos)
            amenity_types: Lista de tipos amenity a incluir
            shop_types: Lista de tipos shop a incluir
            include_all_types: Se True, inclui todos os tipos de negocio

        Returns:
            Query Overpass QL formatada
        """
        # Definir area de busca
        if area_name:
            area_name_lower = area_name.lower()
            if area_name_lower in self.BOUNDING_BOXES:
                bbox = self.BOUNDING_BOXES[area_name_lower]
            else:
                # Usar area por nome (busca OSM)
                area_clause = f'area["name"="{area_name}"]->.searchArea;'
                area_filter = "(area.searchArea)"

        if bbox:
            area_clause = ""
            area_filter = f"({bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]})"
        elif not area_name:
            # Default: Lisboa
            bbox = self.BOUNDING_BOXES["lisboa"]
            area_clause = ""
            area_filter = f"({bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]})"

        # Filtro temporal (newer) - precisa de data ISO
        if days_back > 0:
            date_threshold = datetime.now(UTC) - timedelta(days=days_back)
            date_iso = date_threshold.strftime("%Y-%m-%dT%H:%M:%SZ")
            date_filter = f'(newer:"{date_iso}")'
        else:
            date_filter = ""

        # Tipos de negocio
        if include_all_types:
            amenity_types = self.AMENITY_TYPES
            shop_types = self.SHOP_TYPES
        else:
            amenity_types = amenity_types or ["restaurant", "cafe", "shop"]
            shop_types = shop_types or []

        # Construir queries para cada tipo
        queries = []

        for amenity in amenity_types:
            queries.append(f'node["amenity"="{amenity}"]{area_filter}{date_filter};')
            queries.append(f'way["amenity"="{amenity}"]{area_filter}{date_filter};')

        for shop in shop_types:
            queries.append(f'node["shop"="{shop}"]{area_filter}{date_filter};')
            queries.append(f'way["shop"="{shop}"]{area_filter}{date_filter};')

        # Query final
        query = f"""
[out:json][timeout:{self.timeout}];
{area_clause}
(
  {chr(10).join(queries)}
);
out body center meta;
""".strip()

        return query

    def _build_simple_query(
        self,
        bbox: tuple[float, float, float, float],
        days_back: int = 7,
        amenity_types: list[str] | None = None,
        shop_types: list[str] | None = None,
    ) -> str:
        """
        Constroi query Overpass simplificada para negocios novos.

        Args:
            bbox: Bounding box (min_lat, min_lon, max_lat, max_lon)
            days_back: Dias atras para filtro `newer`
            amenity_types: Lista de tipos amenity a incluir (None = todos)
            shop_types: Lista de tipos shop a incluir (None = todos)

        Returns:
            Query Overpass QL formatada
        """
        # Filtro temporal com data ISO
        if days_back > 0:
            date_threshold = datetime.now(UTC) - timedelta(days=days_back)
            date_iso = date_threshold.strftime("%Y-%m-%dT%H:%M:%SZ")
            date_filter = f'(newer:"{date_iso}")'
        else:
            date_filter = ""
        bbox_str = f"({bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]})"

        # Se tipos especificos foram passados, filtrar por eles
        queries = []

        if amenity_types is not None or shop_types is not None:
            # Filtrar por tipos especificos
            if amenity_types:
                for amenity in amenity_types:
                    queries.append(f'node["amenity"="{amenity}"]{bbox_str}{date_filter};')
                    queries.append(f'way["amenity"="{amenity}"]{bbox_str}{date_filter};')
            if shop_types:
                for shop in shop_types:
                    queries.append(f'node["shop"="{shop}"]{bbox_str}{date_filter};')
                    queries.append(f'way["shop"="{shop}"]{bbox_str}{date_filter};')
        else:
            # Buscar todos os tipos
            queries = [
                f'node["amenity"]{bbox_str}{date_filter};',
                f'way["amenity"]{bbox_str}{date_filter};',
                f'node["shop"]{bbox_str}{date_filter};',
                f'way["shop"]{bbox_str}{date_filter};',
            ]

        query = f"""
[out:json][timeout:{self.timeout}];
(
  {chr(10).join(queries)}
);
out body center meta;
""".strip()

        return query

    @retry(
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=4, max=30),
    )
    async def _make_request(self, query: str) -> dict:
        """
        Executa query na Overpass API.

        Args:
            query: Query Overpass QL

        Returns:
            Resposta JSON da API

        Raises:
            OverpassTimeoutError: Se timeout excedido
            OverpassRateLimitError: Se rate limit excedido
            OverpassSyntaxError: Se erro de sintaxe na query
            OverpassError: Para outros erros
        """
        async with self._semaphore:
            endpoint = self._get_endpoint()

            async with httpx.AsyncClient() as client:
                try:
                    response = await client.post(
                        endpoint,
                        data={"data": query},
                        timeout=float(self.timeout + 30),  # Extra margin
                    )
                except httpx.TimeoutException:
                    # Tentar proximo endpoint
                    self._next_endpoint()
                    raise OverpassTimeoutError(f"Query timeout em {endpoint}")

                if response.status_code == 429:
                    self._next_endpoint()
                    raise OverpassRateLimitError("Rate limit excedido - aguarde")
                elif response.status_code == 504:
                    self._next_endpoint()
                    raise OverpassTimeoutError("Gateway timeout - query muito pesada")
                elif response.status_code == 400:
                    raise OverpassSyntaxError(f"Erro de sintaxe: {response.text[:500]}")
                elif response.status_code >= 400:
                    raise OverpassError(f"Erro {response.status_code}: {response.text[:500]}")

                return response.json()

    async def discover_new_businesses(
        self,
        area: str | tuple[float, float, float, float] = "lisboa",
        days_back: int = 7,
        amenity_types: list[str] | None = None,
        shop_types: list[str] | None = None,
    ) -> list[OSMElement]:
        """
        Descobre negocios novos/modificados recentemente.

        Args:
            area: Nome da area ("lisboa", "porto", etc) ou bbox tuple
            days_back: Quantos dias atras procurar (default 7)
            amenity_types: Tipos de amenity a incluir (None = todos)
            shop_types: Tipos de shop a incluir (None = todos)

        Returns:
            Lista de OSMElement com negocios encontrados
        """
        # Determinar bbox
        if isinstance(area, str):
            bbox = self.BOUNDING_BOXES.get(area.lower())
            if not bbox:
                # Tentar busca por area name
                query = self._build_query(
                    area_name=area,
                    days_back=days_back,
                    amenity_types=amenity_types or self.AMENITY_TYPES,
                    shop_types=shop_types or self.SHOP_TYPES,
                )
            else:
                query = self._build_simple_query(
                    bbox,
                    days_back,
                    amenity_types=amenity_types,
                    shop_types=shop_types,
                )
        else:
            bbox = area
            query = self._build_simple_query(
                bbox,
                days_back,
                amenity_types=amenity_types,
                shop_types=shop_types,
            )

        # Executar query
        data = await self._make_request(query)

        # Converter elementos
        elements = []
        for elem in data.get("elements", []):
            # Filtrar apenas elementos com nome
            if elem.get("tags", {}).get("name"):
                elements.append(OSMElement(elem))

        return elements

    async def search_businesses(
        self,
        bbox: tuple[float, float, float, float],
        business_types: list[str] | None = None,
        name_contains: str | None = None,
    ) -> list[OSMElement]:
        """
        Pesquisa negocios em uma area (sem filtro temporal).

        Args:
            bbox: Bounding box (min_lat, min_lon, max_lat, max_lon)
            business_types: Tipos de negocio a incluir
            name_contains: Filtrar por nome (case insensitive)

        Returns:
            Lista de OSMElement
        """
        query = self._build_simple_query(bbox, days_back=0)
        data = await self._make_request(query)

        elements = []
        for elem in data.get("elements", []):
            osm_elem = OSMElement(elem)

            # Filtrar por nome
            if not osm_elem.name or osm_elem.name == "Sem nome":
                continue

            if name_contains and name_contains.lower() not in osm_elem.name.lower():
                continue

            # Filtrar por tipo
            if business_types:
                if osm_elem.business_type not in business_types:
                    continue

            elements.append(osm_elem)

        return elements

    async def get_element_by_id(
        self,
        osm_type: str,
        osm_id: int,
    ) -> OSMElement | None:
        """
        Busca elemento especifico por ID.

        Args:
            osm_type: Tipo do elemento ("node", "way", "relation")
            osm_id: ID do elemento

        Returns:
            OSMElement ou None se nao encontrado
        """
        query = f"""
[out:json][timeout:30];
{osm_type}({osm_id});
out body center meta;
""".strip()

        data = await self._make_request(query)
        elements = data.get("elements", [])

        if elements:
            return OSMElement(elements[0])
        return None

    async def count_new_businesses(
        self,
        area: str = "lisboa",
        days_back: int = 7,
    ) -> dict[str, int]:
        """
        Conta negocios novos por tipo.

        Args:
            area: Nome da area
            days_back: Dias atras

        Returns:
            Dict com contagens por tipo
        """
        elements = await self.discover_new_businesses(area, days_back)

        counts: dict[str, int] = {}
        for elem in elements:
            btype = elem.business_type
            counts[btype] = counts.get(btype, 0) + 1

        return counts

    async def health_check(self) -> bool:
        """
        Verifica se API esta acessivel.

        Returns:
            True se OK, False caso contrario
        """
        try:
            query = "[out:json][timeout:5];node(1);out;"
            await self._make_request(query)
            return True
        except Exception:
            return False

    async def geocode_location(self, query: str) -> dict | None:
        """
        Geocodifica uma localizacao usando Nominatim (OSM).

        Args:
            query: Nome do local (ex: "Lisboa", "Rua Augusta, Lisboa")

        Returns:
            Dict com lat, lon, display_name, bbox ou None
        """
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    "https://nominatim.openstreetmap.org/search",
                    params={
                        "q": query,
                        "format": "json",
                        "limit": 1,
                        "addressdetails": 1,
                        "countrycodes": "pt",  # Priorizar Portugal
                    },
                    headers={"User-Agent": "GeoscoutPro/1.0"},
                    timeout=10.0,
                )

                if response.status_code == 200:
                    results = response.json()
                    if results:
                        r = results[0]
                        return {
                            "lat": float(r["lat"]),
                            "lon": float(r["lon"]),
                            "display_name": r.get("display_name", query),
                            "bbox": (
                                float(r["boundingbox"][0]),  # min_lat
                                float(r["boundingbox"][2]),  # min_lon
                                float(r["boundingbox"][1]),  # max_lat
                                float(r["boundingbox"][3]),  # max_lon
                            )
                            if "boundingbox" in r
                            else None,
                            "type": r.get("type"),
                            "osm_type": r.get("osm_type"),
                            "osm_id": r.get("osm_id"),
                        }
            except Exception:
                pass

        return None

    async def search_locations(self, query: str, limit: int = 5) -> list[dict]:
        """
        Pesquisa localizacoes para autocomplete.

        Args:
            query: Texto de pesquisa
            limit: Maximo de resultados

        Returns:
            Lista de localizacoes com lat, lon, display_name
        """
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    "https://nominatim.openstreetmap.org/search",
                    params={
                        "q": query,
                        "format": "json",
                        "limit": limit,
                        "addressdetails": 1,
                        "countrycodes": "pt",
                    },
                    headers={"User-Agent": "GeoscoutPro/1.0"},
                    timeout=10.0,
                )

                if response.status_code == 200:
                    results = response.json()
                    return [
                        {
                            "lat": float(r["lat"]),
                            "lon": float(r["lon"]),
                            "display_name": r.get("display_name", ""),
                            "name": r.get("name") or r.get("display_name", "").split(",")[0],
                            "type": r.get("type"),
                            "bbox": (
                                float(r["boundingbox"][0]),
                                float(r["boundingbox"][2]),
                                float(r["boundingbox"][1]),
                                float(r["boundingbox"][3]),
                            )
                            if "boundingbox" in r
                            else None,
                        }
                        for r in results
                    ]
            except Exception:
                pass

        return []

    def get_business_types(self) -> dict[str, list[dict]]:
        """
        Retorna tipos de negocio organizados por categoria.

        Returns:
            Dict com categorias e tipos
        """
        return {
            "Restauracao": [
                {"value": "restaurant", "label": "Restaurante"},
                {"value": "cafe", "label": "Cafe"},
                {"value": "bar", "label": "Bar"},
                {"value": "pub", "label": "Pub"},
                {"value": "fast_food", "label": "Fast Food"},
            ],
            "Saude": [
                {"value": "pharmacy", "label": "Farmacia"},
                {"value": "clinic", "label": "Clinica"},
                {"value": "dentist", "label": "Dentista"},
                {"value": "doctors", "label": "Medico"},
                {"value": "veterinary", "label": "Veterinario"},
            ],
            "Beleza": [
                {"value": "beauty_salon", "label": "Salao de Beleza"},
                {"value": "hairdresser", "label": "Cabeleireiro"},
            ],
            "Fitness": [
                {"value": "gym", "label": "Ginasio"},
                {"value": "fitness_centre", "label": "Centro de Fitness"},
            ],
            "Servicos": [
                {"value": "bank", "label": "Banco"},
                {"value": "car_repair", "label": "Oficina Auto"},
                {"value": "car_wash", "label": "Lavagem Auto"},
                {"value": "driving_school", "label": "Escola de Conducao"},
                {"value": "language_school", "label": "Escola de Linguas"},
            ],
            "Lojas": [
                {"value": "supermarket", "label": "Supermercado"},
                {"value": "convenience", "label": "Loja de Conveniencia"},
                {"value": "bakery", "label": "Padaria"},
                {"value": "clothes", "label": "Roupa"},
                {"value": "electronics", "label": "Electronica"},
                {"value": "furniture", "label": "Mobiliario"},
                {"value": "florist", "label": "Florista"},
            ],
        }

    async def discover_by_location_text(
        self,
        location_query: str,
        days_back: int = 7,
        business_type: str | None = None,
        radius_km: float = 5.0,
    ) -> tuple[list["OSMElement"], dict | None]:
        """
        Descobre negocios por texto de localizacao.

        Args:
            location_query: Texto da localizacao (ex: "Almada", "Rua Augusta Lisboa")
            days_back: Dias atras
            business_type: Tipo de negocio especifico (ex: "restaurant")
            radius_km: Raio em km para criar bbox

        Returns:
            Tupla (lista de elementos, info da localizacao geocodificada)
        """
        # Primeiro verificar se e um nome predefinido
        location_lower = location_query.lower().strip()
        if location_lower in self.BOUNDING_BOXES:
            bbox = self.BOUNDING_BOXES[location_lower]
            location_info = {
                "display_name": location_query.title(),
                "bbox": bbox,
                "predefined": True,
            }
        else:
            # Geocodificar
            location_info = await self.geocode_location(location_query)
            if not location_info:
                return [], None

            # Usar bbox do resultado ou criar um baseado no raio
            if location_info.get("bbox"):
                bbox = location_info["bbox"]
            else:
                # Criar bbox aproximado baseado no raio
                lat, lon = location_info["lat"], location_info["lon"]
                # Aproximacao: 1 grau ~ 111km
                delta = radius_km / 111.0
                bbox = (lat - delta, lon - delta, lat + delta, lon + delta)
                location_info["bbox"] = bbox

        # Definir tipos a pesquisar
        amenity_types = None
        shop_types = None

        if business_type:
            if business_type in self.AMENITY_TYPES:
                amenity_types = [business_type]
                shop_types = []
            elif business_type in self.SHOP_TYPES:
                amenity_types = []
                shop_types = [business_type]
            else:
                # Tentar em ambos
                amenity_types = [business_type]
                shop_types = [business_type]

        # Executar descoberta
        elements = await self.discover_new_businesses(
            area=bbox,
            days_back=days_back,
            amenity_types=amenity_types,
            shop_types=shop_types,
        )

        return elements, location_info


# Instancia global para uso direto
overpass_client = OverpassClient()
