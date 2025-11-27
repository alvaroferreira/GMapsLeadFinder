"""Testes para database models e queries."""

from datetime import datetime, timedelta

import pytest

from src.database.models import Business, SearchHistory, BusinessSnapshot
from src.database.queries import BusinessQueries, SearchHistoryQueries, SnapshotQueries


class TestBusinessModel:
    """Testes para o modelo Business."""

    def test_create_business(self, test_session, sample_business):
        """Deve criar um negocio na DB."""
        test_session.add(sample_business)
        test_session.commit()

        result = test_session.query(Business).filter(
            Business.id == sample_business.id
        ).first()

        assert result is not None
        assert result.name == sample_business.name
        assert result.lead_status == "new"

    def test_business_repr(self, sample_business):
        """Repr deve mostrar info util."""
        repr_str = repr(sample_business)
        assert sample_business.id in repr_str
        assert sample_business.name in repr_str


class TestBusinessQueries:
    """Testes para BusinessQueries."""

    def test_get_by_id(self, test_session, sample_business):
        """Deve encontrar negocio por ID."""
        test_session.add(sample_business)
        test_session.commit()

        result = BusinessQueries.get_by_id(test_session, sample_business.id)
        assert result is not None
        assert result.id == sample_business.id

    def test_get_by_id_not_found(self, test_session):
        """Deve retornar None se nao encontrar."""
        result = BusinessQueries.get_by_id(test_session, "nonexistent")
        assert result is None

    def test_get_all_with_status_filter(
        self, test_session, sample_business, sample_business_with_website
    ):
        """Deve filtrar por status."""
        sample_business.lead_status = "new"
        sample_business_with_website.lead_status = "contacted"

        test_session.add_all([sample_business, sample_business_with_website])
        test_session.commit()

        results = BusinessQueries.get_all(test_session, status="new")
        assert len(results) == 1
        assert results[0].id == sample_business.id

    def test_get_all_with_min_score(
        self, test_session, sample_business, sample_business_with_website
    ):
        """Deve filtrar por score minimo."""
        sample_business.lead_score = 30
        sample_business_with_website.lead_score = 70

        test_session.add_all([sample_business, sample_business_with_website])
        test_session.commit()

        results = BusinessQueries.get_all(test_session, min_score=50)
        assert len(results) == 1
        assert results[0].id == sample_business_with_website.id

    def test_get_all_with_has_website(
        self, test_session, sample_business, sample_business_with_website
    ):
        """Deve filtrar por ter website."""
        test_session.add_all([sample_business, sample_business_with_website])
        test_session.commit()

        results = BusinessQueries.get_all(test_session, has_website=True)
        assert len(results) == 1
        assert results[0].has_website is True

        results = BusinessQueries.get_all(test_session, has_website=False)
        assert len(results) == 1
        assert results[0].has_website is False

    def test_get_all_with_city_filter(self, test_session, sample_business):
        """Deve filtrar por cidade no endereco."""
        test_session.add(sample_business)
        test_session.commit()

        results = BusinessQueries.get_all(test_session, city="Lisboa")
        assert len(results) == 1

        results = BusinessQueries.get_all(test_session, city="Porto")
        assert len(results) == 0

    def test_upsert_new(self, test_session, sample_business):
        """Upsert deve inserir novo negocio."""
        business, is_new = BusinessQueries.upsert(test_session, sample_business)
        test_session.commit()

        assert is_new is True
        assert business.first_seen_at is not None
        assert business.data_expires_at is not None

    def test_upsert_existing(self, test_session, sample_business):
        """Upsert deve atualizar negocio existente."""
        test_session.add(sample_business)
        test_session.commit()

        # Criar copia com dados atualizados
        updated = Business(
            id=sample_business.id,
            name="Nome Atualizado",
            rating=4.9,
        )

        business, is_new = BusinessQueries.upsert(test_session, updated)
        test_session.commit()

        assert is_new is False
        assert business.name == "Nome Atualizado"
        assert business.rating == 4.9

    def test_get_new_since(self, test_session, sample_business):
        """Deve retornar negocios desde uma data."""
        sample_business.first_seen_at = datetime.utcnow()
        test_session.add(sample_business)
        test_session.commit()

        yesterday = datetime.utcnow() - timedelta(days=1)
        results = BusinessQueries.get_new_since(test_session, yesterday)
        assert len(results) == 1

        tomorrow = datetime.utcnow() + timedelta(days=1)
        results = BusinessQueries.get_new_since(test_session, tomorrow)
        assert len(results) == 0

    def test_update_status(self, test_session, sample_business):
        """Deve atualizar status de um lead."""
        test_session.add(sample_business)
        test_session.commit()

        result = BusinessQueries.update_status(
            test_session, sample_business.id, "contacted", "Enviado email"
        )
        test_session.commit()

        assert result.lead_status == "contacted"
        assert result.notes == "Enviado email"

    def test_get_stats(self, test_session, sample_business, sample_business_with_website):
        """Deve retornar estatisticas corretas."""
        sample_business.lead_score = 50
        sample_business.lead_status = "new"
        sample_business_with_website.lead_score = 30
        sample_business_with_website.lead_status = "contacted"

        test_session.add_all([sample_business, sample_business_with_website])
        test_session.commit()

        stats = BusinessQueries.get_stats(test_session)

        assert stats["total"] == 2
        assert stats["avg_score"] == 40.0
        assert stats["without_website"] == 1
        assert "new" in stats["by_status"]
        assert "contacted" in stats["by_status"]

    def test_count(self, test_session, sample_business, sample_business_with_website):
        """Deve contar negocios."""
        sample_business.lead_status = "new"
        sample_business_with_website.lead_status = "new"

        test_session.add_all([sample_business, sample_business_with_website])
        test_session.commit()

        assert BusinessQueries.count(test_session) == 2
        assert BusinessQueries.count(test_session, status="new") == 2
        assert BusinessQueries.count(test_session, status="contacted") == 0


class TestSearchHistoryQueries:
    """Testes para SearchHistoryQueries."""

    def test_add_history(self, test_session):
        """Deve registar pesquisa no historico."""
        history = SearchHistoryQueries.add(
            test_session,
            query_type="text",
            query_params={"query": "restaurante Lisboa"},
            results_count=10,
            new_count=5,
            api_calls=2,
        )
        test_session.commit()

        assert history.id is not None
        assert history.results_count == 10
        assert history.new_businesses_count == 5

    def test_get_recent(self, test_session):
        """Deve retornar pesquisas recentes."""
        for i in range(5):
            SearchHistoryQueries.add(
                test_session,
                query_type="text",
                query_params={"query": f"test {i}"},
                results_count=i,
                new_count=0,
                api_calls=1,
            )
        test_session.commit()

        results = SearchHistoryQueries.get_recent(test_session, limit=3)
        assert len(results) == 3


class TestSnapshotQueries:
    """Testes para SnapshotQueries."""

    def test_create_snapshot(self, test_session, sample_business):
        """Deve criar snapshot de um negocio."""
        test_session.add(sample_business)
        test_session.commit()

        snapshot = SnapshotQueries.create(
            test_session,
            business_id=sample_business.id,
            snapshot_data={"name": sample_business.name, "rating": sample_business.rating},
            rating=sample_business.rating,
            review_count=sample_business.review_count,
        )
        test_session.commit()

        assert snapshot.id is not None
        assert snapshot.business_id == sample_business.id
        assert snapshot.rating_at_time == sample_business.rating

    def test_get_by_business(self, test_session, sample_business):
        """Deve retornar snapshots de um negocio."""
        test_session.add(sample_business)
        test_session.commit()

        # Criar varios snapshots
        for i in range(3):
            SnapshotQueries.create(
                test_session,
                business_id=sample_business.id,
                snapshot_data={"iteration": i},
                rating=4.0 + i * 0.1,
            )
        test_session.commit()

        results = SnapshotQueries.get_by_business(
            test_session, sample_business.id, limit=2
        )
        assert len(results) == 2
