"""Modelos Pydantic para requests e responses da Google Places API (New)."""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ============ Enums ============

class PriceLevel(str, Enum):
    """Niveis de preco do Google Places."""
    FREE = "PRICE_LEVEL_FREE"
    INEXPENSIVE = "PRICE_LEVEL_INEXPENSIVE"
    MODERATE = "PRICE_LEVEL_MODERATE"
    EXPENSIVE = "PRICE_LEVEL_EXPENSIVE"
    VERY_EXPENSIVE = "PRICE_LEVEL_VERY_EXPENSIVE"


class BusinessStatus(str, Enum):
    """Status operacional do negocio."""
    OPERATIONAL = "OPERATIONAL"
    CLOSED_TEMPORARILY = "CLOSED_TEMPORARILY"
    CLOSED_PERMANENTLY = "CLOSED_PERMANENTLY"


class RankPreference(str, Enum):
    """Preferencia de ordenacao."""
    POPULARITY = "POPULARITY"
    DISTANCE = "DISTANCE"


# ============ Location Models ============

class Location(BaseModel):
    """Coordenadas geograficas."""
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)


class Circle(BaseModel):
    """Circulo para definir area de pesquisa."""
    center: Location
    radius: float = Field(..., ge=0, le=50000, description="Raio em metros")


class LocationRestriction(BaseModel):
    """Restricao de localizacao para Nearby Search."""
    circle: Circle


class LocationBias(BaseModel):
    """Bias de localizacao para Text Search."""
    circle: Circle


# ============ Place Components ============

class DisplayName(BaseModel):
    """Nome do local com idioma."""
    text: str
    languageCode: Optional[str] = None


class PlacePhoto(BaseModel):
    """Foto do local."""
    name: str
    widthPx: Optional[int] = None
    heightPx: Optional[int] = None


class OpeningHours(BaseModel):
    """Horario de funcionamento."""
    openNow: Optional[bool] = None


# ============ Place Model ============

class Place(BaseModel):
    """Modelo completo de um local retornado pela API."""
    id: str
    displayName: Optional[DisplayName] = None
    formattedAddress: Optional[str] = None
    location: Optional[Location] = None
    types: Optional[list[str]] = None
    businessStatus: Optional[str] = None
    nationalPhoneNumber: Optional[str] = None
    internationalPhoneNumber: Optional[str] = None
    websiteUri: Optional[str] = None
    googleMapsUri: Optional[str] = None
    rating: Optional[float] = Field(None, ge=0, le=5)
    userRatingCount: Optional[int] = Field(None, ge=0)
    priceLevel: Optional[str] = None
    photos: Optional[list[PlacePhoto]] = None
    currentOpeningHours: Optional[OpeningHours] = None

    @property
    def name(self) -> str:
        """Retorna o nome do local."""
        if self.displayName and self.displayName.text:
            return self.displayName.text
        return "Unknown"

    @property
    def has_website(self) -> bool:
        """Verifica se tem website."""
        return bool(self.websiteUri)

    @property
    def has_phone(self) -> bool:
        """Verifica se tem telefone."""
        return bool(self.nationalPhoneNumber or self.internationalPhoneNumber)

    @property
    def photo_count(self) -> int:
        """Retorna numero de fotos."""
        return len(self.photos) if self.photos else 0

    @property
    def price_level_int(self) -> Optional[int]:
        """Converte price level para inteiro (0-4)."""
        if not self.priceLevel:
            return None
        mapping = {
            "PRICE_LEVEL_FREE": 0,
            "PRICE_LEVEL_INEXPENSIVE": 1,
            "PRICE_LEVEL_MODERATE": 2,
            "PRICE_LEVEL_EXPENSIVE": 3,
            "PRICE_LEVEL_VERY_EXPENSIVE": 4,
        }
        return mapping.get(self.priceLevel)


# ============ Search Response ============

class SearchResponse(BaseModel):
    """Resposta da API de pesquisa."""
    places: list[Place] = Field(default_factory=list)
    nextPageToken: Optional[str] = None


# ============ Request Models ============

class TextSearchRequest(BaseModel):
    """Request para Text Search."""
    textQuery: str
    includedType: Optional[str] = None
    languageCode: str = "pt"
    locationBias: Optional[dict] = None
    pageSize: int = Field(default=20, ge=1, le=20)
    pageToken: Optional[str] = None
    minRating: Optional[float] = Field(None, ge=0, le=5)
    openNow: Optional[bool] = None
    priceLevels: Optional[list[str]] = None


class NearbySearchRequest(BaseModel):
    """Request para Nearby Search."""
    locationRestriction: LocationRestriction
    includedTypes: Optional[list[str]] = None
    excludedTypes: Optional[list[str]] = None
    languageCode: str = "pt"
    maxResultCount: int = Field(default=20, ge=1, le=20)
    rankPreference: str = RankPreference.POPULARITY.value
