"""Servico de gestao de leads."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from src.database.db import db
from src.database.models import Business
from src.database.queries import BusinessQueries
from src.exceptions import BusinessNotFoundError, DatabaseError, ValidationError
from src.services.scorer import LeadScorer


@dataclass
class LeadUpdate:
    """Dados para atualizacao de um lead."""

    status: str | None = None
    notes: str | None = None
    tags: list[str] | None = None


@dataclass
class LeadFilters:
    """Filtros para pesquisa de leads."""

    status: str | None = None
    min_score: int | None = None
    max_score: int | None = None
    has_website: bool | None = None
    city: str | None = None
    first_seen_since: datetime | None = None
    first_seen_from: datetime | None = None
    first_seen_to: datetime | None = None
    limit: int = 100
    offset: int = 0


class LeadsService:
    """Servico para gestao de leads (camada de business logic)."""

    def __init__(self, scorer: LeadScorer | None = None):
        """
        Inicializa o servico.

        Args:
            scorer: LeadScorer opcional
        """
        self.scorer = scorer or LeadScorer()

    def get_lead(self, place_id: str) -> Business:
        """
        Retorna um lead por ID.

        Args:
            place_id: ID do lead

        Returns:
            Business encontrado

        Raises:
            BusinessNotFoundError: Se lead nao existir
            DatabaseError: Se houver erro de BD
        """
        try:
            with db.get_session() as session:
                business = BusinessQueries.get_by_id(session, place_id)

                if not business:
                    raise BusinessNotFoundError(
                        f"Lead com ID {place_id} nao encontrado",
                        details={"place_id": place_id},
                    )

                # Expunge para usar fora da sessao
                session.expunge(business)
                return business

        except BusinessNotFoundError:
            raise
        except Exception as e:
            raise DatabaseError(
                "Erro ao buscar lead",
                details={"place_id": place_id, "error": str(e)},
            )

    def list_leads(self, filters: LeadFilters) -> list[Business]:
        """
        Lista leads com filtros.

        Args:
            filters: Filtros de pesquisa

        Returns:
            Lista de Business

        Raises:
            DatabaseError: Se houver erro de BD
        """
        try:
            with db.get_session() as session:
                businesses = BusinessQueries.get_all(
                    session,
                    status=filters.status,
                    min_score=filters.min_score,
                    max_score=filters.max_score,
                    has_website=filters.has_website,
                    city=filters.city,
                    first_seen_since=filters.first_seen_since,
                    first_seen_from=filters.first_seen_from,
                    first_seen_to=filters.first_seen_to,
                    limit=filters.limit,
                    offset=filters.offset,
                )

                # Expunge para usar fora da sessao
                for b in businesses:
                    session.expunge(b)

                return businesses

        except Exception as e:
            raise DatabaseError(
                "Erro ao listar leads",
                details={"filters": str(filters), "error": str(e)},
            )

    def update_lead(self, place_id: str, update: LeadUpdate) -> Business:
        """
        Atualiza um lead.

        Args:
            place_id: ID do lead
            update: Dados para atualizar

        Returns:
            Business atualizado

        Raises:
            BusinessNotFoundError: Se lead nao existir
            ValidationError: Se dados invalidos
            DatabaseError: Se houver erro de BD
        """
        # Validar status se fornecido
        if update.status:
            from src.database.models import LEAD_STATUSES

            if update.status not in LEAD_STATUSES:
                raise ValidationError(
                    f"Status invalido: {update.status}",
                    details={
                        "status": update.status,
                        "valid_statuses": LEAD_STATUSES,
                    },
                )

        try:
            with db.get_session() as session:
                business = BusinessQueries.get_by_id(session, place_id)

                if not business:
                    raise BusinessNotFoundError(
                        f"Lead com ID {place_id} nao encontrado",
                        details={"place_id": place_id},
                    )

                # Aplicar updates
                if update.status:
                    business.lead_status = update.status

                if update.notes:
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
                    existing = business.notes or ""
                    business.notes = f"{existing}\n[{timestamp}] {update.notes}".strip()

                if update.tags is not None:
                    business.tags = update.tags

                business.last_updated_at = datetime.utcnow()

                # Commit automatico pelo context manager
                session.flush()  # Garantir que mudancas sao aplicadas
                session.expunge(business)

                return business

        except (BusinessNotFoundError, ValidationError):
            raise
        except Exception as e:
            raise DatabaseError(
                "Erro ao atualizar lead",
                details={
                    "place_id": place_id,
                    "update": str(update),
                    "error": str(e),
                },
            )

    def delete_lead(self, place_id: str) -> bool:
        """
        Apaga um lead.

        Args:
            place_id: ID do lead

        Returns:
            True se apagado com sucesso

        Raises:
            BusinessNotFoundError: Se lead nao existir
            DatabaseError: Se houver erro de BD
        """
        try:
            with db.get_session() as session:
                deleted = BusinessQueries.delete(session, place_id)

                if not deleted:
                    raise BusinessNotFoundError(
                        f"Lead com ID {place_id} nao encontrado",
                        details={"place_id": place_id},
                    )

                return True

        except BusinessNotFoundError:
            raise
        except Exception as e:
            raise DatabaseError(
                "Erro ao apagar lead",
                details={"place_id": place_id, "error": str(e)},
            )

    def recalculate_score(self, place_id: str) -> int:
        """
        Recalcula o lead score de um negocio.

        Args:
            place_id: ID do lead

        Returns:
            Novo score

        Raises:
            BusinessNotFoundError: Se lead nao existir
            DatabaseError: Se houver erro de BD
        """
        try:
            with db.get_session() as session:
                business = BusinessQueries.get_by_id(session, place_id)

                if not business:
                    raise BusinessNotFoundError(
                        f"Lead com ID {place_id} nao encontrado",
                        details={"place_id": place_id},
                    )

                # Recalcular score
                new_score = self.scorer.calculate(business)
                business.lead_score = new_score
                business.last_updated_at = datetime.utcnow()

                return new_score

        except BusinessNotFoundError:
            raise
        except Exception as e:
            raise DatabaseError(
                "Erro ao recalcular score",
                details={"place_id": place_id, "error": str(e)},
            )

    def get_stats(self) -> dict[str, Any]:
        """
        Retorna estatisticas agregadas sobre leads.

        Returns:
            Dicionario com estatisticas

        Raises:
            DatabaseError: Se houver erro de BD
        """
        try:
            with db.get_session() as session:
                return BusinessQueries.get_stats(session)

        except Exception as e:
            raise DatabaseError(
                "Erro ao obter estatisticas",
                details={"error": str(e)},
            )

    def count_leads(self, filters: LeadFilters | None = None) -> int:
        """
        Conta total de leads com filtros opcionais.

        Args:
            filters: Filtros opcionais

        Returns:
            Total de leads

        Raises:
            DatabaseError: Se houver erro de BD
        """
        try:
            with db.get_session() as session:
                if filters:
                    return BusinessQueries.count(
                        session,
                        status=filters.status,
                        first_seen_since=filters.first_seen_since,
                    )
                return BusinessQueries.count(session)

        except Exception as e:
            raise DatabaseError(
                "Erro ao contar leads",
                details={"error": str(e)},
            )
