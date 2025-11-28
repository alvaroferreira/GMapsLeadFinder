"""API Routers RESTful para endpoints JSON."""

from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from src.database.db import db
from src.database.queries import BusinessQueries, SearchHistoryQueries
from src.exceptions import BusinessNotFoundError, DatabaseError
from src.services.enricher import EnrichmentService
from src.services.notion import NotionService
from src.services.scheduler import NotificationService

# API Router v1
api_v1 = APIRouter(prefix="/api/v1", tags=["api"])


# ============ MODELS (DTOs) ============

class BusinessResponse(BaseModel):
    """Response model para um negocio."""
    id: str
    name: str
    formatted_address: str | None = None
    phone_number: str | None = None
    website: str | None = None
    email: str | None = None
    rating: float | None = None
    review_count: int = 0
    lead_score: int = 0
    lead_status: str = "new"
    has_website: bool = False
    google_maps_url: str | None = None


class StatsResponse(BaseModel):
    """Response model para estatisticas."""
    total: int
    by_status: dict[str, int]
    avg_score: float
    avg_rating: float
    without_website: int
    new_this_week: int


class UpdateLeadStatusRequest(BaseModel):
    """Request model para atualizar status de lead."""
    status: str = Field(..., description="Novo status do lead")


class UpdateLeadNotesRequest(BaseModel):
    """Request model para atualizar notas de lead."""
    notes: str = Field(..., description="Notas a adicionar")


class EnrichmentStatsResponse(BaseModel):
    """Response model para estatisticas de enriquecimento."""
    total: int
    pending: int
    in_progress: int
    completed: int
    failed: int
    no_website: int
    enrichable: int


class NotionStatusResponse(BaseModel):
    """Response model para status do Notion."""
    connected: bool
    workspace: str | None = None
    stats: dict[str, int]


class ErrorResponse(BaseModel):
    """Response model para erros."""
    error: str
    details: dict[str, Any] | None = None


# ============ ENDPOINTS ============

@api_v1.get(
    "/stats",
    response_model=StatsResponse,
    summary="Obter estatisticas gerais",
    description="Retorna estatisticas agregadas sobre todos os leads",
)
async def get_stats() -> StatsResponse:
    """Retorna estatisticas gerais da base de dados."""
    try:
        with db.get_session() as session:
            stats = BusinessQueries.get_stats(session)
            return StatsResponse(**stats)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao obter estatisticas: {str(e)}",
        )


@api_v1.get(
    "/leads",
    response_model=list[BusinessResponse],
    summary="Listar leads",
    description="Retorna lista de leads com filtros opcionais",
)
async def list_leads(
    status_filter: str | None = Query(None, alias="status", description="Filtrar por status"),
    min_score: int | None = Query(None, description="Score minimo"),
    has_website: bool | None = Query(None, description="Filtrar por ter website"),
    limit: int = Query(100, ge=1, le=1000, description="Limite de resultados"),
    offset: int = Query(0, ge=0, description="Offset para paginacao"),
) -> list[BusinessResponse]:
    """Lista leads com filtros opcionais."""
    try:
        with db.get_session() as session:
            businesses = BusinessQueries.get_all(
                session,
                status=status_filter,
                min_score=min_score,
                has_website=has_website,
                limit=limit,
                offset=offset,
            )

            return [
                BusinessResponse(
                    id=b.id,
                    name=b.name,
                    formatted_address=b.formatted_address,
                    phone_number=b.phone_number,
                    website=b.website,
                    email=b.email,
                    rating=b.rating,
                    review_count=b.review_count,
                    lead_score=b.lead_score,
                    lead_status=b.lead_status,
                    has_website=b.has_website,
                    google_maps_url=b.google_maps_url,
                )
                for b in businesses
            ]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao listar leads: {str(e)}",
        )


@api_v1.get(
    "/leads/{place_id}",
    response_model=BusinessResponse,
    summary="Obter detalhes de um lead",
    description="Retorna informacao detalhada sobre um lead especifico",
    responses={
        404: {"model": ErrorResponse, "description": "Lead nao encontrado"},
    },
)
async def get_lead(place_id: str) -> BusinessResponse:
    """Retorna detalhes de um lead especifico."""
    try:
        with db.get_session() as session:
            business = BusinessQueries.get_by_id(session, place_id)

            if not business:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Lead com ID {place_id} nao encontrado",
                )

            return BusinessResponse(
                id=business.id,
                name=business.name,
                formatted_address=business.formatted_address,
                phone_number=business.phone_number,
                website=business.website,
                email=business.email,
                rating=business.rating,
                review_count=business.review_count,
                lead_score=business.lead_score,
                lead_status=business.lead_status,
                has_website=business.has_website,
                google_maps_url=business.google_maps_url,
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao obter lead: {str(e)}",
        )


@api_v1.patch(
    "/leads/{place_id}/status",
    response_model=BusinessResponse,
    summary="Atualizar status de um lead",
    description="Atualiza apenas o status de um lead",
    responses={
        404: {"model": ErrorResponse, "description": "Lead nao encontrado"},
    },
)
async def update_lead_status(
    place_id: str,
    request: UpdateLeadStatusRequest,
) -> BusinessResponse:
    """Atualiza o status de um lead."""
    try:
        with db.get_session() as session:
            business = BusinessQueries.get_by_id(session, place_id)

            if not business:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Lead com ID {place_id} nao encontrado",
                )

            business.lead_status = request.status
            # Commit automatico pelo context manager

            return BusinessResponse(
                id=business.id,
                name=business.name,
                formatted_address=business.formatted_address,
                phone_number=business.phone_number,
                website=business.website,
                email=business.email,
                rating=business.rating,
                review_count=business.review_count,
                lead_score=business.lead_score,
                lead_status=business.lead_status,
                has_website=business.has_website,
                google_maps_url=business.google_maps_url,
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao atualizar status: {str(e)}",
        )


@api_v1.delete(
    "/leads/{place_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Apagar um lead",
    description="Remove permanentemente um lead da base de dados",
    responses={
        404: {"model": ErrorResponse, "description": "Lead nao encontrado"},
    },
)
async def delete_lead(place_id: str) -> None:
    """Apaga um lead da base de dados."""
    try:
        with db.get_session() as session:
            deleted = BusinessQueries.delete(session, place_id)

            if not deleted:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Lead com ID {place_id} nao encontrado",
                )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao apagar lead: {str(e)}",
        )


@api_v1.get(
    "/enrichment/stats",
    response_model=EnrichmentStatsResponse,
    summary="Estatisticas de enriquecimento",
    description="Retorna estatisticas sobre o status de enriquecimento dos leads",
)
async def get_enrichment_stats() -> EnrichmentStatsResponse:
    """Retorna estatisticas de enriquecimento."""
    try:
        enricher = EnrichmentService()
        stats = enricher.get_enrichment_stats()
        return EnrichmentStatsResponse(**stats)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao obter estatisticas de enriquecimento: {str(e)}",
        )


@api_v1.get(
    "/notifications/unread",
    summary="Contagem de notificacoes nao lidas",
    description="Retorna o numero de notificacoes nao lidas",
)
async def get_unread_notifications_count() -> dict[str, int]:
    """Retorna contagem de notificacoes nao lidas."""
    try:
        notification_service = NotificationService()
        count = notification_service.get_unread_count()
        return {"unread_count": count}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao obter contagem de notificacoes: {str(e)}",
        )


@api_v1.get(
    "/integrations/notion/status",
    response_model=NotionStatusResponse,
    summary="Status da integracao Notion",
    description="Retorna informacao sobre o estado da integracao com Notion",
)
async def get_notion_status() -> NotionStatusResponse:
    """Retorna status da integracao Notion."""
    try:
        notion = NotionService()
        config = notion.get_config()
        stats = notion.get_sync_stats()

        return NotionStatusResponse(
            connected=config.get("is_active", False) if config else False,
            workspace=config.get("workspace_name") if config else None,
            stats=stats,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao obter status do Notion: {str(e)}",
        )
