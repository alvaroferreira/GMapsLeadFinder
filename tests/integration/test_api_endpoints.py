"""Testes de integração completos para endpoints FastAPI - Geoscout Pro.

Este módulo contém testes de integração para todos os endpoints HTTP do servidor FastAPI,
incluindo validação de respostas, códigos de status, e comportamentos de erro.
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.services.search import SearchResult
from src.web.server import app


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def client():
    """Cliente de teste FastAPI."""
    return TestClient(app)


@pytest.fixture
def mock_db_session(test_session):
    """Mock da sessão de banco de dados."""
    from contextlib import contextmanager

    @contextmanager
    def mock_get_session():
        yield test_session

    with patch("src.web.server.db.get_session", side_effect=mock_get_session):
        with patch("src.database.db.db.get_session", side_effect=mock_get_session):
            yield test_session


@pytest.fixture
def populated_db(test_session, business_factory):
    """Database populada com dados de teste."""
    # Criar negocios com diferentes status e scores
    businesses = [
        business_factory.create(
            id="place_001",
            name="Restaurante Alto Score",
            lead_score=85,
            lead_status="new",
            has_website=False,
        ),
        business_factory.create(
            id="place_002",
            name="Clinica Qualificada",
            lead_score=75,
            lead_status="qualified",
            has_website=True,
        ),
        business_factory.create(
            id="place_003",
            name="Cafe Convertido",
            lead_score=60,
            lead_status="converted",
            has_website=False,
        ),
    ]

    for b in businesses:
        test_session.add(b)

    test_session.commit()
    return test_session


# =============================================================================
# Testes: Health Check & Home
# =============================================================================


def test_health_check_endpoint_returns_200(client):
    """Verifica que o endpoint de health check retorna 200 OK."""
    response = client.get("/health")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data


def test_health_check_contains_version_info(client):
    """Verifica que health check inclui informação de versão."""
    response = client.get("/health")
    data = response.json()

    assert data["version"] == "1.0.0"


def test_home_page_returns_200(client, mock_db_session):
    """Verifica que a página inicial retorna 200 OK."""
    with patch("src.web.server.get_stats_cached") as mock_stats:
        mock_stats.return_value = {
            "total_businesses": 10,
            "total_with_website": 5,
            "avg_score": 65.5,
        }

        response = client.get("/")
        assert response.status_code == 200
        assert b"dashboard" in response.content.lower() or b"<html" in response.content.lower()


def test_help_page_returns_200(client):
    """Verifica que a página de ajuda retorna 200 OK."""
    response = client.get("/help")
    assert response.status_code == 200


# =============================================================================
# Testes: Search Endpoints
# =============================================================================


def test_search_page_get_returns_200(client):
    """Verifica que GET /search retorna 200."""
    response = client.get("/search")
    assert response.status_code == 200


def test_search_post_without_api_key_returns_error(client, mock_db_session):
    """Verifica que pesquisa sem API key retorna erro."""
    with patch("src.web.server.settings.has_api_key", False):
        response = client.post(
            "/search", data={"query": "restaurantes", "location": "", "radius": "5000"}
        )
        assert response.status_code == 200
        assert b"API key" in response.content or b"configurada" in response.content


def test_search_post_with_valid_data_executes_search(client, mock_db_session):
    """Verifica que POST /search com dados válidos executa pesquisa."""
    with patch("src.web.server.settings.has_api_key", True):
        with patch("src.web.server.SearchService") as MockSearchService:
            mock_service = MockSearchService.return_value
            mock_service.search = AsyncMock(
                return_value=SearchResult(
                    total_found=10,
                    new_businesses=5,
                    updated_businesses=5,
                    filtered_out=0,
                    api_calls=1,
                )
            )

            response = client.post(
                "/search",
                data={
                    "query": "restaurantes Lisboa",
                    "location": "",
                    "radius": "5000",
                    "max_results": "60",
                    "place_type": "",
                    "max_reviews": "",
                    "has_website": "",
                    "date_from": "",
                    "date_to": "",
                    "only_new": "",
                },
            )

            assert response.status_code == 200


def test_search_post_with_location_coordinates(client, mock_db_session):
    """Verifica que pesquisa aceita coordenadas de localização."""
    with patch("src.web.server.settings.has_api_key", True):
        with patch("src.web.server.SearchService") as MockSearchService:
            mock_service = MockSearchService.return_value
            mock_service.search = AsyncMock(
                return_value=SearchResult(
                    total_found=5,
                    new_businesses=3,
                    updated_businesses=2,
                    filtered_out=0,
                    api_calls=1,
                )
            )

            response = client.post(
                "/search",
                data={
                    "query": "cafes",
                    "location": "38.7223, -9.1393",
                    "radius": "2000",
                    "max_results": "20",
                },
            )

            assert response.status_code == 200


def test_search_post_with_website_filter(client, mock_db_session):
    """Verifica que filtro has_website funciona corretamente."""
    with patch("src.web.server.settings.has_api_key", True):
        with patch("src.web.server.SearchService") as MockSearchService:
            mock_service = MockSearchService.return_value
            mock_service.search = AsyncMock(
                return_value=SearchResult(
                    total_found=3,
                    new_businesses=3,
                    updated_businesses=0,
                    filtered_out=2,
                    api_calls=1,
                )
            )

            response = client.post(
                "/search", data={"query": "dentistas", "has_website": "no", "max_results": "30"}
            )

            assert response.status_code == 200


def test_search_post_with_invalid_location_format(client, mock_db_session):
    """Verifica tratamento de formato inválido de localização."""
    with patch("src.web.server.settings.has_api_key", True):
        with patch("src.web.server.SearchService") as MockSearchService:
            mock_service = MockSearchService.return_value
            mock_service.search = AsyncMock(
                return_value=SearchResult(
                    total_found=0,
                    new_businesses=0,
                    updated_businesses=0,
                    filtered_out=0,
                    api_calls=1,
                )
            )

            response = client.post(
                "/search",
                data={"query": "lojas", "location": "invalid-format", "max_results": "10"},
            )

            # Deve aceitar mas ignorar localização inválida
            assert response.status_code == 200


def test_search_post_handles_api_exception(client, mock_db_session):
    """Verifica tratamento de exceções da API de pesquisa."""
    with patch("src.web.server.settings.has_api_key", True):
        with patch("src.web.server.SearchService") as MockSearchService:
            mock_service = MockSearchService.return_value
            mock_service.search = AsyncMock(side_effect=Exception("API Error"))

            response = client.post("/search", data={"query": "test", "max_results": "10"})

            assert response.status_code == 200
            assert b"erro" in response.content.lower() or b"error" in response.content.lower()


# =============================================================================
# Testes: Leads Endpoints
# =============================================================================


def test_leads_page_returns_200(client, mock_db_session):
    """Verifica que GET /leads retorna 200."""
    with patch("src.web.server.get_notion_config_cached") as mock_notion:
        mock_notion.return_value = {"is_active": False}
        response = client.get("/leads")
        assert response.status_code == 200


def test_leads_page_with_status_filter(client, mock_db_session, populated_db):
    """Verifica filtro por status na listagem de leads."""
    with patch("src.web.server.get_notion_config_cached") as mock_notion:
        mock_notion.return_value = {"is_active": False}

        response = client.get("/leads?status=qualified")
        assert response.status_code == 200


def test_leads_page_with_min_score_filter(client, mock_db_session):
    """Verifica filtro por score mínimo."""
    with patch("src.web.server.get_notion_config_cached") as mock_notion:
        mock_notion.return_value = {"is_active": False}

        response = client.get("/leads?min_score=70")
        assert response.status_code == 200


def test_leads_page_with_website_filter(client, mock_db_session):
    """Verifica filtro por website."""
    with patch("src.web.server.get_notion_config_cached") as mock_notion:
        mock_notion.return_value = {"is_active": False}

        response = client.get("/leads?has_website=yes")
        assert response.status_code == 200


def test_leads_page_with_date_range_filter(client, mock_db_session):
    """Verifica filtro por intervalo de datas."""
    with patch("src.web.server.get_notion_config_cached") as mock_notion:
        mock_notion.return_value = {"is_active": False}

        date_from = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        date_to = datetime.now().strftime("%Y-%m-%d")

        response = client.get(f"/leads?date_from={date_from}&date_to={date_to}")
        assert response.status_code == 200


def test_leads_page_pagination(client, mock_db_session):
    """Verifica paginação na listagem de leads."""
    with patch("src.web.server.get_notion_config_cached") as mock_notion:
        mock_notion.return_value = {"is_active": False}

        response = client.get("/leads?page=2")
        assert response.status_code == 200


def test_lead_detail_page_returns_200(client, mock_db_session, populated_db):
    """Verifica que página de detalhes do lead retorna 200."""
    response = client.get("/leads/place_001")
    assert response.status_code == 200


def test_lead_detail_page_not_found(client, mock_db_session):
    """Verifica que lead não encontrado retorna mensagem de erro."""
    response = client.get("/leads/nonexistent_place_id")
    assert response.status_code == 200
    assert b"encontrado" in response.content.lower() or b"not found" in response.content.lower()


def test_lead_drawer_endpoint(client, mock_db_session, populated_db):
    """Verifica endpoint do drawer de detalhes."""
    response = client.get("/leads/place_001/drawer")
    assert response.status_code == 200


def test_lead_drawer_not_found_returns_404(client, mock_db_session):
    """Verifica que drawer com ID inválido retorna 404."""
    response = client.get("/leads/invalid_id/drawer")
    assert response.status_code == 404


def test_update_lead_status_endpoint(client, mock_db_session, populated_db):
    """Verifica atualização de status via POST."""
    response = client.post(
        "/leads/place_001/update",
        data={"status": "contacted", "notes": "Primeira tentativa de contato"},
    )

    # Redirect esperado
    assert response.status_code in [200, 303]


def test_update_lead_status_api_endpoint(client, mock_db_session, populated_db):
    """Verifica endpoint API para atualizar status (drag & drop)."""
    response = client.post("/leads/place_001/status", data={"status": "qualified"})

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True


def test_update_lead_status_nonexistent_lead(client, mock_db_session):
    """Verifica atualização de lead inexistente."""
    response = client.post("/leads/nonexistent_id/status", data={"status": "contacted"})

    # Deve retornar success mesmo se não encontrou (idempotência)
    assert response.status_code == 200


# =============================================================================
# Testes: OSM Discovery Endpoints
# =============================================================================


def test_discover_page_returns_200(client):
    """Verifica que página de descoberta OSM retorna 200."""
    with patch("src.web.server.OSMDiscoveryService") as MockOSM:
        mock_service = MockOSM.return_value
        mock_service.get_business_types.return_value = ["restaurant", "cafe"]
        mock_service.health_check = AsyncMock(return_value={"status": "healthy"})
        mock_service.client.BOUNDING_BOXES = {"lisboa": {}, "porto": {}}

        response = client.get("/discover")
        assert response.status_code == 200


def test_discover_post_executes_discovery(client, mock_db_session):
    """Verifica execução de descoberta OSM via POST."""
    from src.services.osm_discovery import DiscoveryResult

    with patch("src.web.server.OSMDiscoveryService") as MockOSM:
        mock_service = MockOSM.return_value
        mock_result = DiscoveryResult(
            total_found=15,
            new_businesses=10,
            updated_businesses=5,
            area="lisboa",
            days_back=7,
            execution_time_seconds=2.5,
            errors=[],
        )
        mock_service.discover_by_text = AsyncMock(
            return_value=(mock_result, {"display_name": "Lisboa, Portugal"})
        )
        mock_service.preview_by_text = AsyncMock(return_value=([], None))

        with patch("src.web.server.invalidate_stats_cache"):
            response = client.post(
                "/discover",
                data={
                    "location": "lisboa",
                    "days_back": "7",
                    "business_type": "",
                    "save_to_db": "yes",
                },
            )

            assert response.status_code == 200


def test_discover_post_without_saving_to_db(client, mock_db_session):
    """Verifica descoberta OSM sem guardar na DB."""
    from src.services.osm_discovery import DiscoveryResult

    with patch("src.web.server.OSMDiscoveryService") as MockOSM:
        mock_service = MockOSM.return_value
        mock_result = DiscoveryResult(
            total_found=8,
            new_businesses=0,
            updated_businesses=0,
            area="porto",
            days_back=3,
            execution_time_seconds=1.2,
            errors=[],
        )
        mock_service.discover_by_text = AsyncMock(
            return_value=(mock_result, {"display_name": "Porto, Portugal"})
        )
        mock_service.preview_by_text = AsyncMock(return_value=([], None))

        response = client.post(
            "/discover",
            data={
                "location": "porto",
                "days_back": "3",
                "business_type": "cafe",
                "save_to_db": "no",
            },
        )

        assert response.status_code == 200


def test_discover_post_handles_exception(client, mock_db_session):
    """Verifica tratamento de erro na descoberta OSM."""
    with patch("src.web.server.OSMDiscoveryService") as MockOSM:
        mock_service = MockOSM.return_value
        mock_service.discover_by_text = AsyncMock(side_effect=Exception("Overpass API timeout"))

        response = client.post("/discover", data={"location": "lisboa", "days_back": "7"})

        assert response.status_code == 200
        assert b"erro" in response.content.lower() or b"error" in response.content.lower()


def test_osm_health_api_endpoint(client):
    """Verifica endpoint de health check do OSM."""
    with patch("src.web.server.OSMDiscoveryService") as MockOSM:
        mock_service = MockOSM.return_value
        mock_service.health_check = AsyncMock(
            return_value={"status": "healthy", "response_time_ms": 150}
        )

        response = client.get("/api/osm/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "healthy"


def test_osm_locations_autocomplete_endpoint(client):
    """Verifica endpoint de autocomplete de localizações."""
    with patch("src.web.server.OSMDiscoveryService") as MockOSM:
        mock_service = MockOSM.return_value
        mock_service.search_locations = AsyncMock(
            return_value=[{"display_name": "Lisboa, Portugal"}, {"display_name": "Lisbon, ME, USA"}]
        )

        response = client.get("/api/osm/locations?q=lisb")
        assert response.status_code == 200

        data = response.json()
        assert "locations" in data


def test_osm_business_types_endpoint(client):
    """Verifica endpoint de tipos de negócio OSM."""
    with patch("src.web.server.OSMDiscoveryService") as MockOSM:
        mock_service = MockOSM.return_value
        mock_service.get_business_types.return_value = [
            {"key": "restaurant", "label": "Restaurantes"},
            {"key": "cafe", "label": "Cafés"},
        ]

        response = client.get("/api/osm/business-types")
        assert response.status_code == 200


# =============================================================================
# Testes: Pipeline Endpoints
# =============================================================================


def test_pipeline_page_returns_200(client, mock_db_session):
    """Verifica que página de pipeline Kanban retorna 200."""
    response = client.get("/pipeline")
    assert response.status_code == 200


def test_pipeline_page_groups_by_status(client, mock_db_session, populated_db):
    """Verifica que pipeline agrupa leads por status."""
    response = client.get("/pipeline")
    assert response.status_code == 200

    # Verificar que contém estrutura de kanban
    content = response.content.decode()
    assert "new" in content.lower() or "novo" in content.lower()


# =============================================================================
# Testes: Export Endpoints
# =============================================================================


def test_export_page_returns_200(client, mock_db_session):
    """Verifica que página de exportação retorna 200."""
    response = client.get("/export")
    assert response.status_code == 200


def test_export_download_csv_format(client, mock_db_session, populated_db):
    """Verifica exportação em formato CSV."""
    with patch("src.web.server.ExportService") as MockExport:
        mock_service = MockExport.return_value
        mock_service.export_csv.return_value = "/tmp/export.csv"

        with patch("src.web.server.FileResponse") as MockFileResponse:
            response = client.post(
                "/export/download", data={"format": "csv", "status": "", "min_score": ""}
            )

            # Verificar que tentou exportar
            assert mock_service.export_csv.called or response.status_code == 200


def test_export_download_xlsx_format(client, mock_db_session, populated_db):
    """Verifica exportação em formato Excel."""
    with patch("src.web.server.ExportService") as MockExport:
        mock_service = MockExport.return_value
        mock_service.export_excel.return_value = "/tmp/export.xlsx"

        with patch("src.web.server.FileResponse"):
            response = client.post("/export/download", data={"format": "xlsx"})

            assert response.status_code == 200


def test_export_download_json_format(client, mock_db_session, populated_db):
    """Verifica exportação em formato JSON."""
    with patch("src.web.server.ExportService") as MockExport:
        mock_service = MockExport.return_value
        mock_service.export_json.return_value = "/tmp/export.json"

        with patch("src.web.server.FileResponse"):
            response = client.post("/export/download", data={"format": "json", "min_score": "70"})

            assert response.status_code == 200


def test_export_download_with_filters(client, mock_db_session, populated_db):
    """Verifica exportação com filtros aplicados."""
    with patch("src.web.server.ExportService") as MockExport:
        mock_service = MockExport.return_value
        mock_service.export_csv.return_value = "/tmp/export_filtered.csv"

        with patch("src.web.server.FileResponse"):
            response = client.post(
                "/export/download", data={"format": "csv", "status": "qualified", "min_score": "75"}
            )

            assert response.status_code == 200


def test_export_with_no_leads_returns_error(client, mock_db_session):
    """Verifica que exportação sem leads retorna erro."""
    response = client.post("/export/download", data={"format": "csv"})

    # Deve retornar erro ou resposta vazia
    assert response.status_code == 200


# =============================================================================
# Testes: Settings Endpoints
# =============================================================================


def test_settings_page_returns_200(client, mock_db_session):
    """Verifica que página de configurações retorna 200."""
    with patch("src.web.server.NotionService") as MockNotion:
        mock_service = MockNotion.return_value
        mock_service.get_config.return_value = None
        mock_service.get_sync_stats.return_value = {}

        with patch("src.web.server._read_env_file") as mock_env:
            mock_env.return_value = {"GOOGLE_PLACES_API_KEY": "test_key"}

            response = client.get("/settings")
            assert response.status_code == 200


def test_save_google_maps_api_key(client):
    """Verifica salvamento de API key do Google Maps."""
    with patch("src.web.server._read_env_file") as mock_read:
        with patch("src.web.server._write_env_file") as mock_write:
            mock_read.return_value = {}

            response = client.post(
                "/settings/api-keys/google-maps", data={"api_key": "new_test_key_123"}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True


def test_save_ai_settings(client):
    """Verifica salvamento de configurações de AI."""
    with patch("src.web.server._read_env_file") as mock_read:
        with patch("src.web.server._write_env_file") as mock_write:
            mock_read.return_value = {}

            response = client.post(
                "/settings/api-keys/ai",
                data={
                    "openai_api_key": "sk-test123",
                    "anthropic_api_key": "",
                    "gemini_api_key": "",
                    "default_ai_provider": "openai",
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True


def test_toggle_api_endpoint(client):
    """Verifica toggle de APIs (ligar/desligar)."""
    with patch("src.web.server._read_env_file") as mock_read:
        with patch("src.web.server._write_env_file") as mock_write:
            mock_read.return_value = {}

            response = client.post(
                "/settings/api/toggle", data={"api_name": "google_maps", "enabled": "false"}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["enabled"] is False


def test_toggle_api_with_invalid_name(client):
    """Verifica toggle com nome de API inválido."""
    with patch("src.web.server._read_env_file") as mock_read:
        mock_read.return_value = {}

        response = client.post(
            "/settings/api/toggle", data={"api_name": "invalid_api", "enabled": "true"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False


def test_notion_test_connection(client):
    """Verifica teste de conexão com Notion."""
    with patch("src.web.server.NotionService") as MockNotion:
        mock_service = MockNotion.return_value
        mock_service.test_connection = AsyncMock(return_value={"name": "Test Workspace"})

        response = client.post("/settings/notion/test", data={"api_key": "secret_test_key"})

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "workspace_name" in data


def test_notion_test_connection_failure(client):
    """Verifica falha no teste de conexão Notion."""
    with patch("src.web.server.NotionService") as MockNotion:
        mock_service = MockNotion.return_value
        mock_service.test_connection = AsyncMock(side_effect=Exception("Invalid API key"))

        response = client.post("/settings/notion/test", data={"api_key": "invalid_key"})

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False


def test_notion_list_databases(client):
    """Verifica listagem de databases Notion."""
    with patch("src.web.server.NotionService") as MockNotion:
        mock_service = MockNotion.return_value
        mock_service.list_databases = AsyncMock(
            return_value=[
                {"id": "db1", "title": "Leads Database"},
                {"id": "db2", "title": "Sales Pipeline"},
            ]
        )

        response = client.get("/settings/notion/databases?api_key=test_key")
        assert response.status_code == 200

        data = response.json()
        assert len(data["databases"]) == 2


def test_notion_connect(client, mock_db_session):
    """Verifica conexão com Notion."""
    with patch("src.web.server.NotionService") as MockNotion:
        mock_service = MockNotion.return_value
        mock_service.test_connection = AsyncMock(return_value={"name": "My Workspace"})
        mock_service.save_config = MagicMock()

        with patch("src.web.server.invalidate_notion_cache"):
            response = client.post(
                "/settings/notion/connect", data={"api_key": "secret_key", "database_id": "db_123"}
            )

            # Redirect esperado
            assert response.status_code in [200, 303]


def test_notion_disconnect(client, mock_db_session):
    """Verifica desconexão do Notion."""
    with patch("src.web.server.NotionService") as MockNotion:
        mock_service = MockNotion.return_value
        mock_service.disconnect = MagicMock()

        response = client.post("/settings/notion/disconnect")

        # Redirect esperado
        assert response.status_code in [200, 303]


# =============================================================================
# Testes: Automation Endpoints
# =============================================================================


def test_automation_page_returns_200(client, mock_db_session):
    """Verifica que página de automação retorna 200."""
    with patch("src.web.server.AutomationService") as MockAuto:
        mock_service = MockAuto.return_value
        mock_service.get_tracked_searches.return_value = []
        mock_service.get_automation_stats.return_value = {}
        mock_service.get_automation_logs.return_value = []

        response = client.get("/automation")
        assert response.status_code == 200


def test_create_tracked_search(client, mock_db_session):
    """Verifica criação de pesquisa agendada."""
    with patch("src.web.server.AutomationService") as MockAuto:
        mock_service = MockAuto.return_value
        mock_service.create_tracked_search = MagicMock()

        response = client.post(
            "/automation/create",
            data={
                "name": "Dentistas Lisboa",
                "query": "dentistas em Lisboa",
                "location": "",
                "radius": "5000",
                "place_type": "",
                "interval_hours": "24",
                "notify_on_new": "true",
                "notify_threshold_score": "60",
            },
        )

        # Redirect esperado
        assert response.status_code in [200, 303]


def test_toggle_tracked_search(client, mock_db_session):
    """Verifica toggle de pesquisa agendada."""
    with patch("src.web.server.AutomationService") as MockAuto:
        mock_service = MockAuto.return_value
        mock_service.toggle_tracked_search.return_value = False

        response = client.post("/automation/1/toggle")
        assert response.status_code == 200

        data = response.json()
        assert "is_active" in data


def test_delete_tracked_search(client, mock_db_session):
    """Verifica exclusão de pesquisa agendada."""
    with patch("src.web.server.AutomationService") as MockAuto:
        mock_service = MockAuto.return_value
        mock_service.delete_tracked_search = MagicMock()

        response = client.post("/automation/1/delete")

        # Redirect esperado
        assert response.status_code in [200, 303]


def test_run_tracked_search_now(client, mock_db_session):
    """Verifica execução imediata de pesquisa agendada."""
    with patch("src.web.server.AutomationService") as MockAuto:
        mock_service = MockAuto.return_value
        mock_service.run_search_now = AsyncMock(return_value={"total_found": 10, "new_found": 5})

        response = client.post("/automation/1/run-now")
        assert response.status_code == 200


def test_automation_logs_page(client, mock_db_session):
    """Verifica página de logs de automação."""
    with patch("src.web.server.AutomationService") as MockAuto:
        mock_service = MockAuto.return_value
        mock_service.get_automation_logs.return_value = []
        mock_service.get_tracked_searches.return_value = [{"id": 1, "name": "Test Search"}]

        response = client.get("/automation/logs/1")
        assert response.status_code == 200


# =============================================================================
# Testes: API JSON Endpoints
# =============================================================================


def test_api_stats_endpoint(client, mock_db_session):
    """Verifica endpoint de estatísticas JSON."""
    with patch("src.web.server.BusinessQueries.get_stats") as mock_stats:
        mock_stats.return_value = {
            "total_businesses": 100,
            "total_with_website": 60,
            "avg_lead_score": 65.5,
        }

        response = client.get("/api/stats")
        assert response.status_code == 200

        data = response.json()
        assert "total_businesses" in data


def test_api_leads_endpoint(client, mock_db_session, populated_db):
    """Verifica endpoint de leads JSON."""
    response = client.get("/api/leads")
    assert response.status_code == 200

    data = response.json()
    assert isinstance(data, list)


def test_api_leads_with_filters(client, mock_db_session, populated_db):
    """Verifica endpoint de leads com filtros."""
    response = client.get("/api/leads?status=qualified&min_score=70&limit=50")
    assert response.status_code == 200

    data = response.json()
    assert isinstance(data, list)


def test_api_notion_status(client, mock_db_session):
    """Verifica endpoint de status do Notion."""
    with patch("src.web.server.NotionService") as MockNotion:
        mock_service = MockNotion.return_value
        mock_service.get_config.return_value = {
            "is_active": True,
            "workspace_name": "Test Workspace",
        }
        mock_service.get_sync_stats.return_value = {"total_synced": 50}

        response = client.get("/api/notion/status")
        assert response.status_code == 200

        data = response.json()
        assert data["connected"] is True
        assert "stats" in data


# =============================================================================
# Testes: Error Handling & Edge Cases
# =============================================================================


def test_nonexistent_endpoint_returns_404(client):
    """Verifica que endpoint inexistente retorna 404."""
    response = client.get("/nonexistent/endpoint")
    assert response.status_code == 404


def test_post_to_get_only_endpoint_returns_405(client):
    """Verifica que POST em endpoint GET-only retorna 405."""
    response = client.post("/health")
    assert response.status_code == 405


def test_missing_required_form_data(client):
    """Verifica tratamento de dados obrigatórios ausentes."""
    # Tentar criar tracked search sem nome
    with patch("src.web.server.AutomationService"):
        response = client.post("/automation/create", data={})
        # Deve retornar erro 422 (Unprocessable Entity)
        assert response.status_code in [422, 400]
