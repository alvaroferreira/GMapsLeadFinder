"""Servico de tracking de novos negocios e mudancas."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from src.database.db import db
from src.database.models import Business, BusinessSnapshot, TrackedSearch
from src.database.queries import (
    BusinessQueries,
    SnapshotQueries,
    TrackedSearchQueries,
)
from src.services.search import SearchService


@dataclass
class TrackingResult:
    """Resultado de uma execucao de tracking."""

    tracked_name: str
    new_businesses: int
    total_found: int
    executed_at: datetime


class TrackerService:
    """Servico para tracking de novos negocios e mudancas."""

    def __init__(self, search_service: SearchService | None = None):
        """
        Inicializa o servico.

        Args:
            search_service: Servico de pesquisa (opcional)
        """
        self.search_service = search_service or SearchService()

    def get_new_businesses(
        self,
        since: datetime | None = None,
        days: int = 7,
        limit: int = 100,
    ) -> list[Business]:
        """
        Retorna negocios descobertos desde uma data.

        Args:
            since: Data inicial (se None, usa days)
            days: Ultimos N dias (default 7)
            limit: Maximo de resultados

        Returns:
            Lista de Business ordenada por first_seen_at desc
        """
        if since is None:
            since = datetime.utcnow() - timedelta(days=days)

        with db.get_session() as session:
            return BusinessQueries.get_new_since(session, since, limit)

    def get_expiring_businesses(self, days: int = 7) -> list[Business]:
        """
        Retorna negocios com dados a expirar em breve.

        Args:
            days: Dias ate expiracao

        Returns:
            Lista de Business com data_expires_at proxima
        """
        with db.get_session() as session:
            return BusinessQueries.get_expiring_soon(session, days)

    def create_snapshot(self, business_id: str) -> BusinessSnapshot | None:
        """
        Cria snapshot do estado atual de um negocio.

        Args:
            business_id: ID do negocio

        Returns:
            Snapshot criado ou None se negocio nao existe
        """
        with db.get_session() as session:
            business = BusinessQueries.get_by_id(session, business_id)
            if not business:
                return None

            snapshot_data = {
                "name": business.name,
                "address": business.formatted_address,
                "rating": business.rating,
                "review_count": business.review_count,
                "website": business.website,
                "phone": business.phone_number,
                "lead_score": business.lead_score,
                "lead_status": business.lead_status,
            }

            return SnapshotQueries.create(
                session=session,
                business_id=business_id,
                snapshot_data=snapshot_data,
                rating=business.rating,
                review_count=business.review_count,
            )

    def get_business_history(
        self,
        business_id: str,
        limit: int = 10,
    ) -> list[BusinessSnapshot]:
        """
        Retorna historico de snapshots de um negocio.

        Args:
            business_id: ID do negocio
            limit: Maximo de snapshots

        Returns:
            Lista de snapshots ordenada por data desc
        """
        with db.get_session() as session:
            return SnapshotQueries.get_by_business(session, business_id, limit)

    def create_tracked_search(
        self,
        name: str,
        query: str,
        location: tuple[float, float] | None = None,
        radius: int = 5000,
        place_type: str | None = None,
        interval_hours: int = 24,
    ) -> TrackedSearch:
        """
        Cria uma pesquisa para execucao automatica.

        Args:
            name: Nome identificador
            query: Query de pesquisa
            location: Coordenadas opcionais
            radius: Raio em metros
            place_type: Tipo de negocio
            interval_hours: Intervalo entre execucoes

        Returns:
            TrackedSearch criada
        """
        with db.get_session() as session:
            return TrackedSearchQueries.create(
                session=session,
                name=name,
                query_type="text",
                query_params={
                    "query": query,
                    "location": location,
                    "radius": radius,
                    "place_type": place_type,
                },
                interval_hours=interval_hours,
            )

    def get_tracked_searches(self, active_only: bool = True) -> list[TrackedSearch]:
        """
        Retorna pesquisas agendadas.

        Args:
            active_only: Apenas ativas

        Returns:
            Lista de TrackedSearch
        """
        with db.get_session() as session:
            if active_only:
                return TrackedSearchQueries.get_active(session)
            return session.query(TrackedSearch).all()

    def get_due_searches(self) -> list[TrackedSearch]:
        """
        Retorna pesquisas prontas para executar.

        Returns:
            Lista de TrackedSearch com next_run_at <= now
        """
        with db.get_session() as session:
            return TrackedSearchQueries.get_due(session)

    async def run_tracked_search(self, tracked_id: int) -> TrackingResult | None:
        """
        Executa uma pesquisa agendada.

        Args:
            tracked_id: ID da pesquisa agendada

        Returns:
            TrackingResult ou None se nao encontrada
        """
        with db.get_session() as session:
            tracked = session.query(TrackedSearch).filter(
                TrackedSearch.id == tracked_id
            ).first()

            if not tracked or not tracked.is_active:
                return None

            params = tracked.query_params or {}

        # Executar pesquisa
        result = await self.search_service.search(
            query=params.get("query", ""),
            location=params.get("location"),
            radius=params.get("radius", 5000),
            place_type=params.get("place_type"),
        )

        # Marcar como executada
        with db.get_session() as session:
            TrackedSearchQueries.mark_executed(session, tracked_id)

        return TrackingResult(
            tracked_name=tracked.name,
            new_businesses=result.new_businesses,
            total_found=result.total_found,
            executed_at=datetime.utcnow(),
        )

    async def run_all_due_searches(self) -> list[TrackingResult]:
        """
        Executa todas as pesquisas agendadas prontas.

        Returns:
            Lista de TrackingResult
        """
        results = []
        due_searches = self.get_due_searches()

        for tracked in due_searches:
            result = await self.run_tracked_search(tracked.id)
            if result:
                results.append(result)

        return results

    def deactivate_tracked_search(self, tracked_id: int) -> bool:
        """
        Desativa uma pesquisa agendada.

        Args:
            tracked_id: ID da pesquisa

        Returns:
            True se desativada, False se nao encontrada
        """
        with db.get_session() as session:
            return TrackedSearchQueries.deactivate(session, tracked_id)

    def compare_snapshots(
        self,
        business_id: str,
    ) -> dict | None:
        """
        Compara ultimo snapshot com estado atual.

        Args:
            business_id: ID do negocio

        Returns:
            Dict com diferencas ou None
        """
        with db.get_session() as session:
            business = BusinessQueries.get_by_id(session, business_id)
            if not business:
                return None

            snapshots = SnapshotQueries.get_by_business(session, business_id, 1)
            if not snapshots:
                return None

            last_snapshot = snapshots[0]
            snapshot_data = last_snapshot.snapshot_data or {}

            changes = {}

            # Comparar campos
            if snapshot_data.get("rating") != business.rating:
                changes["rating"] = {
                    "old": snapshot_data.get("rating"),
                    "new": business.rating,
                }

            if snapshot_data.get("review_count") != business.review_count:
                changes["review_count"] = {
                    "old": snapshot_data.get("review_count"),
                    "new": business.review_count,
                }

            if snapshot_data.get("lead_score") != business.lead_score:
                changes["lead_score"] = {
                    "old": snapshot_data.get("lead_score"),
                    "new": business.lead_score,
                }

            return {
                "business_id": business_id,
                "business_name": business.name,
                "snapshot_date": last_snapshot.captured_at,
                "has_changes": bool(changes),
                "changes": changes,
            }
