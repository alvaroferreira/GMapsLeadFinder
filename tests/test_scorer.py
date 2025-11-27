"""Testes para o sistema de lead scoring."""

import pytest

from src.services.scorer import LeadScorer, ScoringRule


class TestLeadScorer:
    """Testes para LeadScorer."""

    def test_score_no_website(self, sample_business):
        """Negocio sem website deve receber +30 pontos."""
        scorer = LeadScorer()
        sample_business.has_website = False
        score = scorer.calculate(sample_business)
        assert score >= 30

    def test_score_with_website(self, sample_business_with_website):
        """Negocio com website deve ter score mais baixo."""
        scorer = LeadScorer()
        score = scorer.calculate(sample_business_with_website)
        # Com website, muitos reviews e bom rating = score baixo
        assert score < 50

    def test_score_low_visibility(self, sample_business_low_visibility):
        """Negocio com baixa visibilidade deve ter score alto."""
        scorer = LeadScorer()
        score = scorer.calculate(sample_business_low_visibility)
        # Sem website, poucos reviews, rating baixo, poucas fotos
        assert score >= 60

    def test_score_max_100(self, sample_business_low_visibility):
        """Score nunca deve exceder 100."""
        scorer = LeadScorer()
        # Configurar para maximizar pontos
        sample_business_low_visibility.price_level = 4
        score = scorer.calculate(sample_business_low_visibility)
        assert score <= 100

    def test_score_few_reviews(self, sample_business):
        """Menos de 10 reviews deve dar +20 pontos."""
        scorer = LeadScorer()
        sample_business.review_count = 5
        score1 = scorer.calculate(sample_business)

        sample_business.review_count = 50
        score2 = scorer.calculate(sample_business)

        assert score1 > score2

    def test_score_low_rating(self, sample_business):
        """Rating abaixo de 4.0 deve dar +15 pontos."""
        scorer = LeadScorer()
        sample_business.rating = 3.5
        score1 = scorer.calculate(sample_business)

        sample_business.rating = 4.5
        score2 = scorer.calculate(sample_business)

        assert score1 > score2

    def test_explain_returns_all_rules(self, sample_business):
        """Explain deve retornar detalhes de todas as regras."""
        scorer = LeadScorer()
        explanation = scorer.explain(sample_business)

        assert len(explanation) == len(scorer.rules)
        for item in explanation:
            assert "rule" in item
            assert "matched" in item
            assert "points" in item
            assert "description" in item

    def test_add_custom_rule(self, sample_business):
        """Deve ser possivel adicionar regras customizadas."""
        scorer = LeadScorer()
        initial_rules = len(scorer.rules)

        custom_rule = ScoringRule(
            name="custom_test",
            points=10,
            condition=lambda b: "restaurant" in (b.place_types or []),
            description="Bonus para restaurantes",
        )
        scorer.add_rule(custom_rule)

        assert len(scorer.rules) == initial_rules + 1

        sample_business.place_types = ["restaurant"]
        score = scorer.calculate(sample_business)
        assert score >= 10  # Pelo menos os pontos da regra custom

    def test_remove_rule(self, sample_business):
        """Deve ser possivel remover regras."""
        scorer = LeadScorer()
        initial_rules = len(scorer.rules)

        removed = scorer.remove_rule("no_website")
        assert removed is True
        assert len(scorer.rules) == initial_rules - 1

        # Tentar remover regra que nao existe
        removed = scorer.remove_rule("nonexistent")
        assert removed is False

    def test_get_max_score(self):
        """Deve retornar pontuacao maxima possivel."""
        scorer = LeadScorer()
        max_score = scorer.get_max_score()
        assert max_score <= 100
        assert max_score == min(sum(r.points for r in scorer.rules), 100)

    def test_recalculate_all(self, test_session, sample_business):
        """Deve recalcular scores de todos os negocios."""
        scorer = LeadScorer()

        # Adicionar negocios com score errado
        sample_business.lead_score = 0
        test_session.add(sample_business)
        test_session.commit()

        processed, changed = scorer.recalculate_all(test_session)

        assert processed == 1
        assert changed == 1
        assert sample_business.lead_score > 0


class TestScoringRules:
    """Testes para regras individuais."""

    def test_operational_status_rule(self, sample_business):
        """Negocio operacional deve receber bonus."""
        scorer = LeadScorer()

        sample_business.business_status = "OPERATIONAL"
        score1 = scorer.calculate(sample_business)

        sample_business.business_status = "CLOSED_TEMPORARILY"
        score2 = scorer.calculate(sample_business)

        assert score1 > score2

    def test_has_phone_rule(self, sample_business):
        """Negocio com telefone deve receber bonus."""
        scorer = LeadScorer()

        sample_business.phone_number = "+351912345678"
        score1 = scorer.calculate(sample_business)

        sample_business.phone_number = None
        sample_business.international_phone = None
        score2 = scorer.calculate(sample_business)

        assert score1 > score2

    def test_high_price_rule(self, sample_business):
        """Negocio premium deve receber bonus."""
        scorer = LeadScorer()

        sample_business.price_level = 4
        score1 = scorer.calculate(sample_business)

        sample_business.price_level = 1
        score2 = scorer.calculate(sample_business)

        assert score1 > score2
