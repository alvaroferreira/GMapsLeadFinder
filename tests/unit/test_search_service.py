"""Testes unitarios para SearchService."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api.models import DisplayName, Location, Place, SearchResponse
from src.services.scorer import LeadScorer
from src.services.search import SearchResult, SearchService


class TestSearchService:
    """Testes para SearchService."""

    @pytest.fixture
    def mock_google_client(self):
        """Mock do GooglePlacesClient."""
        mock = MagicMock()
        mock.search_all_pages = AsyncMock()
        mock.nearby_search = AsyncMock()
        return mock

    @pytest.fixture
    def mock_scorer(self):
        """Mock do LeadScorer."""
        mock = MagicMock(spec=LeadScorer)
        mock.calculate = MagicMock(return_value=75)
        return mock

    @pytest.fixture
    def search_service(self, mock_google_client, mock_scorer):
        """Instancia do SearchService com mocks."""
        return SearchService(client=mock_google_client, scorer=mock_scorer)

    @pytest.fixture
    def sample_place(self):
        """Place de exemplo da API."""
        return Place(
            id="ChIJ1234567890",
            displayName=DisplayName(text="Restaurante Teste", languageCode="pt"),
            formattedAddress="Rua Teste 123, Lisboa, Portugal",
            location=Location(latitude=38.7223, longitude=-9.1393),
            types=["restaurant", "food"],
            businessStatus="OPERATIONAL",
            nationalPhoneNumber="+351 912 345 678",
            websiteUri="https://restaurante-teste.pt",
            googleMapsUri="https://maps.google.com/?cid=123",
            rating=4.5,
            userRatingCount=100,
            priceLevel="PRICE_LEVEL_MODERATE",
        )

    @pytest.fixture
    def sample_place_no_website(self):
        """Place sem website."""
        return Place(
            id="ChIJ0987654321",
            displayName=DisplayName(text="Cafe Sem Web", languageCode="pt"),
            formattedAddress="Av. Teste 456, Porto, Portugal",
            location=Location(latitude=41.1579, longitude=-8.6291),
            types=["cafe"],
            businessStatus="OPERATIONAL",
            nationalPhoneNumber="+351 912 345 679",
            rating=3.5,
            userRatingCount=10,
        )

    def test_place_to_business_converte_corretamente(self, search_service, sample_place):
        """Deve converter Place para Business com todos os campos."""
        # Arrange
        query = "restaurantes lisboa"

        # Act
        business = search_service._place_to_business(sample_place, query)

        # Assert
        assert business.id == "ChIJ1234567890"
        assert business.name == "Restaurante Teste"
        assert business.formatted_address == "Rua Teste 123, Lisboa, Portugal"
        assert business.latitude == 38.7223
        assert business.longitude == -9.1393
        assert business.place_types == ["restaurant", "food"]
        assert business.business_status == "OPERATIONAL"
        assert business.phone_number == "+351 912 345 678"
        assert business.website == "https://restaurante-teste.pt"
        assert business.google_maps_url == "https://maps.google.com/?cid=123"
        assert business.rating == 4.5
        assert business.review_count == 100
        assert business.price_level == 2
        assert business.has_website is True
        assert business.last_search_query == query

    def test_place_to_business_sem_location(self, search_service):
        """Deve lidar com Place sem coordenadas."""
        # Arrange
        place = Place(
            id="test123",
            displayName=DisplayName(text="Negocio Teste"),
            rating=4.0,
        )

        # Act
        business = search_service._place_to_business(place, "query")

        # Assert
        assert business.latitude is None
        assert business.longitude is None

    def test_place_to_business_define_data_expiracao(self, search_service, sample_place):
        """Deve definir data de expiracao para 30 dias."""
        # Arrange
        before = datetime.utcnow() + timedelta(days=30)

        # Act
        business = search_service._place_to_business(sample_place, "query")

        # Assert
        after = datetime.utcnow() + timedelta(days=30)
        assert before <= business.data_expires_at <= after

    def test_apply_filters_passa_quando_dentro_limites(self, search_service, sample_place):
        """Deve passar filtros quando valores estao dentro dos limites."""
        # Act
        result = search_service._apply_filters(
            sample_place,
            min_reviews=50,
            max_reviews=200,
            min_rating=4.0,
            max_rating=5.0,
            has_website=True,
            has_phone=True,
        )

        # Assert
        assert result is True

    def test_apply_filters_rejeita_reviews_baixos(self, search_service, sample_place):
        """Deve rejeitar quando reviews abaixo do minimo."""
        # Act
        result = search_service._apply_filters(sample_place, min_reviews=150)

        # Assert
        assert result is False

    def test_apply_filters_rejeita_reviews_altos(self, search_service, sample_place):
        """Deve rejeitar quando reviews acima do maximo."""
        # Act
        result = search_service._apply_filters(sample_place, max_reviews=50)

        # Assert
        assert result is False

    def test_apply_filters_rejeita_rating_baixo(self, search_service, sample_place):
        """Deve rejeitar quando rating abaixo do minimo."""
        # Act
        result = search_service._apply_filters(sample_place, min_rating=4.8)

        # Assert
        assert result is False

    def test_apply_filters_rejeita_rating_alto(self, search_service, sample_place):
        """Deve rejeitar quando rating acima do maximo."""
        # Act
        result = search_service._apply_filters(sample_place, max_rating=4.0)

        # Assert
        assert result is False

    def test_apply_filters_rejeita_sem_website(self, search_service, sample_place_no_website):
        """Deve rejeitar quando exige website mas nao tem."""
        # Act
        result = search_service._apply_filters(sample_place_no_website, has_website=True)

        # Assert
        assert result is False

    def test_apply_filters_rejeita_sem_telefone(self, search_service):
        """Deve rejeitar quando exige telefone mas nao tem."""
        # Arrange
        place = Place(
            id="test",
            displayName=DisplayName(text="Test"),
            rating=4.0,
        )

        # Act
        result = search_service._apply_filters(place, has_phone=True)

        # Assert
        assert result is False

    def test_apply_filters_com_place_sem_rating(self, search_service):
        """Deve rejeitar place sem rating quando min_rating definido."""
        # Arrange
        place = Place(
            id="test",
            displayName=DisplayName(text="Test"),
            userRatingCount=50,
        )

        # Act
        result = search_service._apply_filters(place, min_rating=4.0)

        # Assert
        assert result is False

    def test_apply_filters_ignora_none_values(self, search_service, sample_place):
        """Deve ignorar filtros com valor None."""
        # Act
        result = search_service._apply_filters(
            sample_place,
            min_reviews=None,
            max_reviews=None,
            min_rating=None,
        )

        # Assert
        assert result is True

    @pytest.mark.asyncio
    async def test_search_sucesso_sem_filtros(self, search_service, sample_place, test_session):
        """Deve executar pesquisa com sucesso sem filtros."""

        # Arrange
        async def mock_search_generator(**kwargs):
            yield sample_place

        search_service.client.search_all_pages = mock_search_generator

        with (
            patch("src.services.search.db.get_session") as mock_db,
            patch("src.services.search.BusinessQueries.upsert") as mock_upsert,
        ):
            mock_db.return_value.__enter__.return_value = test_session
            mock_upsert.return_value = (sample_place, True)

            # Act
            result = await search_service.search(
                query="restaurantes lisboa",
                location=(38.7223, -9.1393),
                radius=5000,
            )

        # Assert
        assert isinstance(result, SearchResult)
        assert result.total_found == 1
        assert result.new_businesses == 1
        assert result.filtered_out == 0
        assert result.api_calls == 1

    @pytest.mark.asyncio
    async def test_search_aplica_filtros_corretamente(
        self, search_service, sample_place, sample_place_no_website, test_session
    ):
        """Deve aplicar filtros e rejeitar negocios que nao passam."""

        # Arrange
        async def mock_search_generator(**kwargs):
            yield sample_place
            yield sample_place_no_website

        search_service.client.search_all_pages = mock_search_generator

        with (
            patch("src.services.search.db.get_session") as mock_db,
            patch("src.services.search.BusinessQueries.upsert") as mock_upsert,
        ):
            mock_db.return_value.__enter__.return_value = test_session
            mock_upsert.return_value = (sample_place, True)

            # Act
            result = await search_service.search(
                query="restaurantes",
                has_website=True,
                min_rating=4.0,
            )

        # Assert
        assert result.total_found == 1  # Apenas sample_place passou
        assert result.filtered_out == 1  # sample_place_no_website rejeitado

    @pytest.mark.asyncio
    async def test_search_calcula_lead_score(
        self, search_service, sample_place, test_session, mock_scorer
    ):
        """Deve calcular lead score para cada business."""

        # Arrange
        async def mock_search_generator(**kwargs):
            yield sample_place

        search_service.client.search_all_pages = mock_search_generator

        with (
            patch("src.services.search.db.get_session") as mock_db,
            patch("src.services.search.BusinessQueries.upsert") as mock_upsert,
        ):
            mock_db.return_value.__enter__.return_value = test_session
            mock_upsert.return_value = (sample_place, True)

            # Act
            await search_service.search(query="test")

        # Assert
        mock_scorer.calculate.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_registra_historico(self, search_service, sample_place, test_session):
        """Deve registrar pesquisa no historico."""

        # Arrange
        async def mock_search_generator(**kwargs):
            yield sample_place

        search_service.client.search_all_pages = mock_search_generator

        with (
            patch("src.services.search.db.get_session") as mock_db,
            patch("src.services.search.SearchHistoryQueries.add") as mock_history,
            patch("src.services.search.BusinessQueries.upsert") as mock_upsert,
        ):
            mock_db.return_value.__enter__.return_value = test_session
            mock_upsert.return_value = (sample_place, True)

            # Act
            await search_service.search(
                query="restaurantes",
                location=(38.7, -9.1),
                radius=5000,
                place_type="restaurant",
                min_reviews=10,
            )

        # Assert
        mock_history.assert_called_once()
        call_args = mock_history.call_args
        assert call_args[1]["query_type"] == "text"
        assert call_args[1]["query_params"]["query"] == "restaurantes"
        assert call_args[1]["results_count"] == 1

    @pytest.mark.asyncio
    async def test_nearby_search_sucesso(self, search_service, test_session):
        """Deve executar nearby search com sucesso."""
        # Arrange
        place1 = Place(
            id="place1",
            displayName=DisplayName(text="Negocio 1"),
            rating=4.0,
            userRatingCount=50,
        )
        place2 = Place(
            id="place2",
            displayName=DisplayName(text="Negocio 2"),
            rating=4.5,
            userRatingCount=100,
        )

        response = SearchResponse(places=[place1, place2])
        search_service.client.nearby_search = AsyncMock(return_value=response)

        with patch("src.services.search.db.get_session") as mock_db:
            mock_db.return_value.__enter__.return_value = test_session

            # Act
            result = await search_service.nearby_search(
                latitude=38.7223,
                longitude=-9.1393,
                radius=5000,
                place_types=["restaurant"],
                max_results=20,
            )

        # Assert
        assert result.total_found == 2
        assert result.new_businesses == 2
        assert result.api_calls == 1

    @pytest.mark.asyncio
    async def test_nearby_search_gera_query_correto(self, search_service, test_session):
        """Deve gerar search_query no formato correto para nearby."""
        # Arrange
        place = Place(
            id="test",
            displayName=DisplayName(text="Test"),
            rating=4.0,
        )
        response = SearchResponse(places=[place])
        search_service.client.nearby_search = AsyncMock(return_value=response)

        with (
            patch("src.services.search.db.get_session") as mock_db,
            patch("src.services.search.BusinessQueries.upsert") as mock_upsert,
        ):
            mock_db.return_value.__enter__.return_value = test_session
            mock_upsert.return_value = (place, True)

            # Act
            await search_service.nearby_search(
                latitude=38.7223,
                longitude=-9.1393,
            )

        # Assert
        # Verificar que business foi criado com query correto
        assert mock_upsert.called
        business_arg = mock_upsert.call_args[0][1]
        assert business_arg.last_search_query == "nearby:38.7223,-9.1393"

    def test_get_leads_sem_filtros(self, search_service, test_session, business_factory):
        """Deve retornar todos os leads sem filtros."""
        # Arrange
        businesses = business_factory.create_batch(5)
        for b in businesses:
            test_session.add(b)
        test_session.commit()

        with patch("src.services.search.db.get_session") as mock_db:
            mock_db.return_value.__enter__.return_value = test_session

            # Act
            results = search_service.get_leads()

        # Assert
        assert len(results) == 5

    def test_get_leads_com_filtro_status(self, search_service, test_session, business_factory):
        """Deve filtrar leads por status."""
        # Arrange
        qualified = business_factory.create(lead_status="qualified")
        new = business_factory.create(lead_status="new")
        test_session.add_all([qualified, new])
        test_session.commit()

        with patch("src.services.search.db.get_session") as mock_db:
            mock_db.return_value.__enter__.return_value = test_session

            # Mock BusinessQueries.get_all
            with patch("src.services.search.BusinessQueries.get_all") as mock_get:
                mock_get.return_value = [qualified]

                # Act
                results = search_service.get_leads(status="qualified")

        # Assert
        mock_get.assert_called_once()
        assert mock_get.call_args[1]["status"] == "qualified"

    def test_get_leads_com_limite(self, search_service, test_session):
        """Deve respeitar limite de resultados."""
        # Arrange
        with (
            patch("src.services.search.db.get_session") as mock_db,
            patch("src.services.search.BusinessQueries.get_all") as mock_get,
        ):
            mock_db.return_value.__enter__.return_value = test_session
            mock_get.return_value = []

            # Act
            search_service.get_leads(limit=50)

        # Assert
        mock_get.assert_called_once()
        assert mock_get.call_args[1]["limit"] == 50

    def test_get_stats_retorna_estatisticas(self, search_service, test_session):
        """Deve retornar estatisticas da base de dados."""
        # Arrange
        stats_mock = {
            "total": 100,
            "new": 50,
            "qualified": 30,
            "contacted": 20,
        }

        with (
            patch("src.services.search.db.get_session") as mock_db,
            patch("src.services.search.BusinessQueries.get_stats") as mock_stats,
        ):
            mock_db.return_value.__enter__.return_value = test_session
            mock_stats.return_value = stats_mock

            # Act
            result = search_service.get_stats()

        # Assert
        assert result == stats_mock
        mock_stats.assert_called_once_with(test_session)
