"""Sistema de Lead Scoring para qualificacao de negocios."""

from dataclasses import dataclass
from typing import Callable

from sqlalchemy.orm import Session

from src.database.models import Business


@dataclass
class ScoringRule:
    """Regra de pontuacao para leads."""

    name: str
    points: int
    condition: Callable[[Business], bool]
    description: str


class LeadScorer:
    """
    Sistema de pontuacao 0-100 para qualificacao de leads.

    Score mais alto = maior potencial como cliente de marketing digital.
    """

    def __init__(self) -> None:
        """Inicializa o scorer com regras padrao."""
        self.rules: list[ScoringRule] = self._default_rules()

    def _default_rules(self) -> list[ScoringRule]:
        """
        Retorna regras padrao de scoring.

        Logica: negocios que precisam mais de marketing digital
        recebem scores mais altos.
        """
        return [
            ScoringRule(
                name="no_website",
                points=30,
                condition=lambda b: not b.has_website,
                description="Negocio sem website - precisa de presenca digital",
            ),
            ScoringRule(
                name="few_reviews",
                points=20,
                condition=lambda b: (b.review_count or 0) < 10,
                description="Poucos reviews (<10) - baixa visibilidade online",
            ),
            ScoringRule(
                name="low_rating",
                points=15,
                condition=lambda b: b.rating is not None and b.rating < 4.0,
                description="Rating baixo (<4.0) - pode precisar de gestao de reputacao",
            ),
            ScoringRule(
                name="no_photos",
                points=15,
                condition=lambda b: (b.photo_count or 0) < 5,
                description="Poucas fotos (<5) - precisa de conteudo visual",
            ),
            ScoringRule(
                name="high_price",
                points=10,
                condition=lambda b: b.price_level is not None and b.price_level >= 3,
                description="Negocio premium (price 3-4) - maior budget potencial",
            ),
            ScoringRule(
                name="has_phone",
                points=5,
                condition=lambda b: bool(b.phone_number or b.international_phone),
                description="Tem telefone - contactavel diretamente",
            ),
            ScoringRule(
                name="operational",
                points=5,
                condition=lambda b: b.business_status == "OPERATIONAL",
                description="Negocio ativo e operacional",
            ),
        ]

    def calculate(self, business: Business) -> int:
        """
        Calcula score total para um negocio.

        Args:
            business: Negocio a avaliar

        Returns:
            Score de 0-100
        """
        score = 0
        for rule in self.rules:
            try:
                if rule.condition(business):
                    score += rule.points
            except Exception:
                # Se a regra falhar, ignora
                continue
        return min(score, 100)

    def explain(self, business: Business) -> list[dict]:
        """
        Retorna explicacao detalhada do score.

        Args:
            business: Negocio a analisar

        Returns:
            Lista de dicts com detalhes de cada regra
        """
        explanation = []
        total_score = 0

        for rule in self.rules:
            try:
                matched = rule.condition(business)
                points = rule.points if matched else 0
                total_score += points

                explanation.append({
                    "rule": rule.name,
                    "matched": matched,
                    "points": points,
                    "max_points": rule.points,
                    "description": rule.description,
                })
            except Exception as e:
                explanation.append({
                    "rule": rule.name,
                    "matched": False,
                    "points": 0,
                    "max_points": rule.points,
                    "description": f"Erro: {e}",
                })

        return explanation

    def add_rule(self, rule: ScoringRule) -> None:
        """
        Adiciona uma regra customizada.

        Args:
            rule: Nova regra de scoring
        """
        self.rules.append(rule)

    def remove_rule(self, name: str) -> bool:
        """
        Remove uma regra por nome.

        Args:
            name: Nome da regra a remover

        Returns:
            True se removida, False se nao encontrada
        """
        for i, rule in enumerate(self.rules):
            if rule.name == name:
                self.rules.pop(i)
                return True
        return False

    def get_max_score(self) -> int:
        """Retorna pontuacao maxima possivel."""
        return min(sum(rule.points for rule in self.rules), 100)

    def recalculate_all(self, session: Session) -> tuple[int, int]:
        """
        Recalcula scores de todos os negocios.

        Args:
            session: Sessao SQLAlchemy

        Returns:
            Tuple (total_processed, total_changed)
        """
        businesses = session.query(Business).all()
        processed = 0
        changed = 0

        for business in businesses:
            old_score = business.lead_score
            new_score = self.calculate(business)

            if new_score != old_score:
                business.lead_score = new_score
                changed += 1

            processed += 1

        return processed, changed


# Instancia global para uso direto
scorer = LeadScorer()
