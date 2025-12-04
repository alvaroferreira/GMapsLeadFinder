"""Queries reutilizaveis para a base de dados."""

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.database.models import Business, BusinessSnapshot, SearchHistory, TrackedSearch


class BusinessQueries:
    """Queries para a tabela de negocios."""

    @staticmethod
    def get_by_id(session: Session, place_id: str) -> Business | None:
        """Retorna negocio por ID."""
        return session.query(Business).filter(Business.id == place_id).first()

    @staticmethod
    def get_all(
        session: Session,
        status: str | None = None,
        min_score: int | None = None,
        max_score: int | None = None,
        place_type: str | None = None,
        has_website: bool | None = None,
        city: str | None = None,
        first_seen_since: datetime | None = None,
        first_seen_from: datetime | None = None,
        first_seen_to: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
        order_by: str = "lead_score",
        order_desc: bool = True,
    ) -> list[Business]:
        """
        Retorna lista de negocios com filtros.

        Args:
            session: Sessao SQLAlchemy
            status: Filtrar por lead_status
            min_score: Score minimo
            max_score: Score maximo
            place_type: Filtrar por tipo (parcial match em JSON)
            has_website: Filtrar por ter/nao ter website
            city: Filtrar por cidade (parcial match no endereco)
            first_seen_since: Filtrar por data de descoberta
            limit: Numero maximo de resultados
            offset: Offset para paginacao
            order_by: Campo para ordenar
            order_desc: Ordenar descendente

        Returns:
            Lista de Business
        """
        query = session.query(Business)

        if status:
            query = query.filter(Business.lead_status == status)
        if min_score is not None:
            query = query.filter(Business.lead_score >= min_score)
        if max_score is not None:
            query = query.filter(Business.lead_score <= max_score)
        if has_website is not None:
            query = query.filter(Business.has_website == has_website)
        if city:
            query = query.filter(Business.formatted_address.ilike(f"%{city}%"))
        if place_type:
            # Para SQLite com JSON, usar cast para string e LIKE
            query = query.filter(func.cast(Business.place_types, str).ilike(f"%{place_type}%"))
        if first_seen_since:
            query = query.filter(Business.first_seen_at >= first_seen_since)
        if first_seen_from:
            query = query.filter(Business.first_seen_at >= first_seen_from)
        if first_seen_to:
            query = query.filter(Business.first_seen_at <= first_seen_to)

        # Ordenacao
        order_column = getattr(Business, order_by, Business.lead_score)
        if order_desc:
            query = query.order_by(order_column.desc())
        else:
            query = query.order_by(order_column.asc())

        return query.offset(offset).limit(limit).all()

    @staticmethod
    def get_new_since(
        session: Session,
        since: datetime,
        limit: int = 100,
    ) -> list[Business]:
        """Retorna negocios descobertos desde uma data."""
        return (
            session.query(Business)
            .filter(Business.first_seen_at >= since)
            .order_by(Business.first_seen_at.desc())
            .limit(limit)
            .all()
        )

    @staticmethod
    def get_expiring_soon(
        session: Session,
        days: int = 7,
    ) -> list[Business]:
        """Retorna negocios com dados a expirar em breve."""
        threshold = datetime.utcnow() + timedelta(days=days)
        return (
            session.query(Business)
            .filter(Business.data_expires_at <= threshold)
            .filter(Business.data_expires_at >= datetime.utcnow())
            .all()
        )

    @staticmethod
    def upsert(session: Session, business: Business) -> tuple[Business, bool]:
        """
        Insere ou atualiza um negocio.

        Args:
            session: Sessao SQLAlchemy
            business: Business a inserir/atualizar

        Returns:
            Tuple de (Business, is_new)
        """
        existing = session.query(Business).filter(Business.id == business.id).first()

        if existing:
            # Update apenas campos que mudaram
            update_fields = [
                "name",
                "formatted_address",
                "latitude",
                "longitude",
                "place_types",
                "business_status",
                "phone_number",
                "international_phone",
                "website",
                "google_maps_url",
                "rating",
                "review_count",
                "price_level",
                "has_website",
                "has_photos",
                "photo_count",
                "last_search_query",
            ]
            for field in update_fields:
                new_value = getattr(business, field, None)
                if new_value is not None:
                    setattr(existing, field, new_value)

            existing.last_updated_at = datetime.utcnow()
            existing.data_expires_at = datetime.utcnow() + timedelta(days=30)
            return existing, False
        else:
            business.first_seen_at = datetime.utcnow()
            business.data_expires_at = datetime.utcnow() + timedelta(days=30)
            session.add(business)
            return business, True

    @staticmethod
    def update_status(
        session: Session,
        place_id: str,
        status: str,
        notes: str | None = None,
    ) -> Business | None:
        """Atualiza status e notas de um lead."""
        business = session.query(Business).filter(Business.id == place_id).first()
        if business:
            business.lead_status = status
            if notes:
                business.notes = notes
            business.last_updated_at = datetime.utcnow()
        return business

    @staticmethod
    def update_score(session: Session, place_id: str, score: int) -> Business | None:
        """Atualiza score de um lead."""
        business = session.query(Business).filter(Business.id == place_id).first()
        if business:
            business.lead_score = score
        return business

    @staticmethod
    def delete(session: Session, place_id: str) -> bool:
        """Remove um negocio."""
        business = session.query(Business).filter(Business.id == place_id).first()
        if business:
            session.delete(business)
            return True
        return False

    @staticmethod
    def count(
        session: Session,
        status: str | None = None,
        first_seen_since: datetime | None = None,
    ) -> int:
        """Conta total de negocios."""
        query = session.query(func.count(Business.id))
        if status:
            query = query.filter(Business.lead_status == status)
        if first_seen_since:
            query = query.filter(Business.first_seen_at >= first_seen_since)
        return query.scalar() or 0

    @staticmethod
    def get_stats(session: Session) -> dict[str, Any]:
        """Retorna estatisticas da base de dados."""
        total = session.query(func.count(Business.id)).scalar() or 0

        # Por status
        status_counts = dict(
            session.query(Business.lead_status, func.count(Business.id))
            .group_by(Business.lead_status)
            .all()
        )

        # Metricas
        avg_score = session.query(func.avg(Business.lead_score)).scalar() or 0
        avg_rating = (
            session.query(func.avg(Business.rating)).filter(Business.rating.isnot(None)).scalar()
            or 0
        )

        no_website = (
            session.query(func.count(Business.id))
            .filter(Business.has_website == False)  # noqa: E712
            .scalar()
            or 0
        )

        # Novos esta semana
        week_ago = datetime.utcnow() - timedelta(days=7)
        new_this_week = (
            session.query(func.count(Business.id))
            .filter(Business.first_seen_at >= week_ago)
            .scalar()
            or 0
        )

        return {
            "total": total,
            "by_status": status_counts,
            "avg_score": round(avg_score, 1),
            "avg_rating": round(avg_rating, 2),
            "without_website": no_website,
            "new_this_week": new_this_week,
        }

    @staticmethod
    def find_duplicates(session: Session) -> list[tuple[str, str, int]]:
        """
        Encontra possiveis duplicados por nome similar.

        Returns:
            Lista de tuplas (name, address, count)
        """
        return (
            session.query(
                Business.name,
                Business.formatted_address,
                func.count(Business.id).label("count"),
            )
            .group_by(Business.name, Business.formatted_address)
            .having(func.count(Business.id) > 1)
            .all()
        )


class SearchHistoryQueries:
    """Queries para historico de pesquisas."""

    @staticmethod
    def add(
        session: Session,
        query_type: str,
        query_params: dict,
        results_count: int,
        new_count: int,
        api_calls: int,
    ) -> SearchHistory:
        """Regista uma pesquisa no historico."""
        history = SearchHistory(
            query_type=query_type,
            query_params=query_params,
            results_count=results_count,
            new_businesses_count=new_count,
            api_calls_made=api_calls,
        )
        session.add(history)
        return history

    @staticmethod
    def get_recent(session: Session, limit: int = 10) -> list[SearchHistory]:
        """Retorna pesquisas recentes."""
        return (
            session.query(SearchHistory)
            .order_by(SearchHistory.executed_at.desc())
            .limit(limit)
            .all()
        )

    @staticmethod
    def get_stats(session: Session) -> dict[str, Any]:
        """Estatisticas de pesquisas."""
        total = session.query(func.count(SearchHistory.id)).scalar() or 0
        total_results = session.query(func.sum(SearchHistory.results_count)).scalar() or 0
        total_new = session.query(func.sum(SearchHistory.new_businesses_count)).scalar() or 0
        total_api_calls = session.query(func.sum(SearchHistory.api_calls_made)).scalar() or 0

        return {
            "total_searches": total,
            "total_results": total_results,
            "total_new_businesses": total_new,
            "total_api_calls": total_api_calls,
        }


class SnapshotQueries:
    """Queries para snapshots de negocios."""

    @staticmethod
    def create(
        session: Session,
        business_id: str,
        snapshot_data: dict,
        rating: float | None = None,
        review_count: int | None = None,
    ) -> BusinessSnapshot:
        """Cria um snapshot de um negocio."""
        snapshot = BusinessSnapshot(
            business_id=business_id,
            snapshot_data=snapshot_data,
            rating_at_time=rating,
            review_count_at_time=review_count,
        )
        session.add(snapshot)
        return snapshot

    @staticmethod
    def get_by_business(
        session: Session,
        business_id: str,
        limit: int = 10,
    ) -> list[BusinessSnapshot]:
        """Retorna snapshots de um negocio."""
        return (
            session.query(BusinessSnapshot)
            .filter(BusinessSnapshot.business_id == business_id)
            .order_by(BusinessSnapshot.captured_at.desc())
            .limit(limit)
            .all()
        )


class TrackedSearchQueries:
    """Queries para pesquisas agendadas."""

    @staticmethod
    def create(
        session: Session,
        name: str,
        query_type: str,
        query_params: dict,
        interval_hours: int = 24,
    ) -> TrackedSearch:
        """Cria uma pesquisa para tracking."""
        tracked = TrackedSearch(
            name=name,
            query_type=query_type,
            query_params=query_params,
            interval_hours=interval_hours,
            is_active=True,
            next_run_at=datetime.utcnow(),
        )
        session.add(tracked)
        return tracked

    @staticmethod
    def get_active(session: Session) -> list[TrackedSearch]:
        """Retorna pesquisas ativas."""
        return (
            session.query(TrackedSearch)
            .filter(TrackedSearch.is_active == True)  # noqa: E712
            .all()
        )

    @staticmethod
    def get_due(session: Session) -> list[TrackedSearch]:
        """Retorna pesquisas prontas para executar."""
        now = datetime.utcnow()
        return (
            session.query(TrackedSearch)
            .filter(TrackedSearch.is_active == True)  # noqa: E712
            .filter(TrackedSearch.next_run_at <= now)
            .all()
        )

    @staticmethod
    def mark_executed(session: Session, tracked_id: int) -> TrackedSearch | None:
        """Marca pesquisa como executada e agenda proxima."""
        tracked = session.query(TrackedSearch).filter(TrackedSearch.id == tracked_id).first()
        if tracked:
            tracked.last_run_at = datetime.utcnow()
            tracked.next_run_at = datetime.utcnow() + timedelta(hours=tracked.interval_hours)
        return tracked

    @staticmethod
    def deactivate(session: Session, tracked_id: int) -> bool:
        """Desativa uma pesquisa agendada."""
        tracked = session.query(TrackedSearch).filter(TrackedSearch.id == tracked_id).first()
        if tracked:
            tracked.is_active = False
            return True
        return False
