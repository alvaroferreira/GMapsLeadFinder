"""Testes unitarios para servico de integracao Notion - Geoscout Pro."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.database.models import Business, IntegrationConfig
from src.services.notion import NotionClient, NotionService, SyncResult


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def notion_api_key():
    """API key de teste para Notion."""
    return "secret_test_notion_key_123"


@pytest.fixture
def notion_database_id():
    """Database ID de teste."""
    return "database_test_id_456"


@pytest.fixture
def notion_client(notion_api_key):
    """Cliente NotionClient para testes."""
    return NotionClient(api_key=notion_api_key)


@pytest.fixture
def notion_service():
    """Servico NotionService para testes."""
    return NotionService()


@pytest.fixture
def mock_notion_user_response():
    """Resposta mock do endpoint /users/me."""
    return {
        "object": "user",
        "id": "user_123",
        "name": "Test User",
        "type": "person",
        "person": {"email": "test@example.com"},
    }


@pytest.fixture
def mock_notion_databases_response():
    """Resposta mock do endpoint de databases."""
    return {
        "results": [
            {
                "id": "db_123",
                "title": [{"plain_text": "Leads CRM"}],
                "url": "https://notion.so/db_123",
            },
            {
                "id": "db_456",
                "title": [{"plain_text": "Clientes"}],
                "url": "https://notion.so/db_456",
            },
            {
                "id": "db_789",
                "title": [],  # Sem titulo
                "url": "https://notion.so/db_789",
            },
        ],
        "has_more": False,
    }


@pytest.fixture
def mock_notion_database_schema():
    """Schema mock de uma database Notion."""
    return {
        "id": "db_123",
        "properties": {
            "Nome": {"type": "title"},
            "Email": {"type": "email"},
            "Telefone": {"type": "phone_number"},
            "Website": {"type": "url"},
            "Score": {"type": "number"},
        },
    }


@pytest.fixture
def mock_notion_page_created():
    """Resposta mock de criacao de pagina."""
    return {
        "id": "page_123",
        "url": "https://notion.so/page_123",
        "created_time": "2025-01-15T10:00:00.000Z",
    }


@pytest.fixture
def sample_business_for_notion():
    """Business de exemplo para sync com Notion."""
    return Business(
        id="test_biz_123",
        name="Cafe Notion Test",
        formatted_address="Rua Teste 123, Lisboa, Portugal",
        latitude=38.7223,
        longitude=-9.1393,
        place_types=["cafe", "food"],
        business_status="OPERATIONAL",
        phone_number="+351 912 345 678",
        website="https://cafe-test.pt",
        rating=4.5,
        review_count=50,
        has_website=True,
        has_photos=True,
        photo_count=10,
        lead_score=75,
        lead_status="qualified",
        email="info@cafe-test.pt",
        emails_scraped=["info@cafe-test.pt", "contacto@cafe-test.pt"],
        social_linkedin="https://linkedin.com/company/cafe-test",
        social_facebook="https://facebook.com/cafetest",
        social_instagram="https://instagram.com/cafetest",
        enrichment_status="completed",
        enriched_at=datetime.utcnow(),
        tags=["premium", "lisboa"],
        notes="Lead de alta qualidade",
        first_seen_at=datetime.utcnow(),
    )


# =============================================================================
# Testes: NotionClient
# =============================================================================


@pytest.mark.asyncio
async def test_notion_client_initialization(notion_client, notion_api_key):
    """Testa inicializacao do cliente Notion."""
    assert notion_client.api_key == notion_api_key
    assert "Authorization" in notion_client.headers
    assert f"Bearer {notion_api_key}" == notion_client.headers["Authorization"]
    assert notion_client.headers["Notion-Version"] == "2022-06-28"


@pytest.mark.asyncio
async def test_notion_client_test_connection_success(notion_client, mock_notion_user_response):
    """Testa conexao bem-sucedida com Notion."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = mock_notion_user_response
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=mock_response)):
        result = await notion_client.test_connection()

    assert result["id"] == "user_123"
    assert result["name"] == "Test User"


@pytest.mark.asyncio
async def test_notion_client_test_connection_unauthorized(notion_client):
    """Testa conexao com API key invalido."""
    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_response.raise_for_status = MagicMock(
        side_effect=httpx.HTTPStatusError(
            "Unauthorized", request=MagicMock(), response=mock_response
        )
    )

    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=mock_response)):
        with pytest.raises(httpx.HTTPStatusError):
            await notion_client.test_connection()


@pytest.mark.asyncio
async def test_notion_client_list_databases(notion_client, mock_notion_databases_response):
    """Testa listagem de databases."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = mock_notion_databases_response
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=mock_response)):
        databases = await notion_client.list_databases()

    assert len(databases) == 3
    assert databases[0]["id"] == "db_123"
    assert databases[0]["title"] == "Leads CRM"
    assert databases[1]["title"] == "Clientes"
    assert databases[2]["title"] == "Sem titulo"  # Tratamento de titulo vazio


@pytest.mark.asyncio
async def test_notion_client_get_database_schema(
    notion_client, notion_database_id, mock_notion_database_schema
):
    """Testa obtencao de schema da database."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = mock_notion_database_schema
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=mock_response)):
        schema = await notion_client.get_database_schema(notion_database_id)

    assert schema["id"] == "db_123"
    assert "properties" in schema
    assert "Nome" in schema["properties"]


@pytest.mark.asyncio
async def test_notion_client_create_page(
    notion_client, notion_database_id, mock_notion_page_created
):
    """Testa criacao de pagina (lead)."""
    properties = {
        "Nome": {"title": [{"text": {"content": "Teste Lead"}}]},
        "Email": {"email": "test@example.com"},
    }

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = mock_notion_page_created
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=mock_response)):
        result = await notion_client.create_page(notion_database_id, properties)

    assert result["id"] == "page_123"
    assert "url" in result


@pytest.mark.asyncio
async def test_notion_client_update_page(notion_client, mock_notion_page_created):
    """Testa atualizacao de pagina existente."""
    page_id = "page_123"
    properties = {
        "Score": {"number": 85},
    }

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = mock_notion_page_created
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.patch", new=AsyncMock(return_value=mock_response)):
        result = await notion_client.update_page(page_id, properties)

    assert result["id"] == "page_123"


@pytest.mark.asyncio
async def test_notion_client_get_page(notion_client, mock_notion_page_created):
    """Testa obtencao de dados de uma pagina."""
    page_id = "page_123"

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = mock_notion_page_created
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=mock_response)):
        result = await notion_client.get_page(page_id)

    assert result["id"] == "page_123"


@pytest.mark.asyncio
async def test_notion_client_rate_limiting(notion_client):
    """Testa tratamento de rate limiting (429)."""
    mock_response = MagicMock()
    mock_response.status_code = 429
    mock_response.raise_for_status = MagicMock(
        side_effect=httpx.HTTPStatusError(
            "Rate limited", request=MagicMock(), response=mock_response
        )
    )

    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=mock_response)):
        with pytest.raises(httpx.HTTPStatusError):
            await notion_client.test_connection()


# =============================================================================
# Testes: NotionService
# =============================================================================


def test_notion_service_initialization(notion_service):
    """Testa inicializacao do servico."""
    assert notion_service._client is None


def test_notion_service_save_config(notion_service, notion_api_key, notion_database_id):
    """Testa salvamento de configuracao."""
    with patch("src.services.notion.db.get_session") as mock_session:
        mock_db_session = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_db_session
        mock_db_session.query.return_value.filter.return_value.first.return_value = None

        success = notion_service.save_config(
            api_key=notion_api_key,
            database_id=notion_database_id,
            workspace_name="Test Workspace",
        )

    assert success is True


def test_notion_service_get_config(notion_service):
    """Testa obtencao de configuracao."""
    mock_config = IntegrationConfig(
        id=1,
        service="notion",
        api_key="test_key",
        config={"database_id": "db_123", "workspace_name": "Test"},
        is_active=True,
        last_sync_at=datetime.utcnow(),
    )

    with patch("src.services.notion.db.get_session") as mock_session:
        mock_db_session = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_db_session
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_config

        config = notion_service.get_config()

    assert config is not None
    assert config["api_key"] == "test_key"
    assert config["database_id"] == "db_123"


def test_notion_service_disconnect(notion_service):
    """Testa desconexao da integracao."""
    mock_config = IntegrationConfig(service="notion", api_key="key")

    with patch("src.services.notion.db.get_session") as mock_session:
        mock_db_session = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_db_session
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_config

        success = notion_service.disconnect()

    assert success is True


@pytest.mark.asyncio
async def test_notion_service_test_connection(
    notion_service, notion_api_key, mock_notion_user_response
):
    """Testa conexao via servico."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = mock_notion_user_response
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=mock_response)):
        result = await notion_service.test_connection(notion_api_key)

    assert result["id"] == "user_123"


@pytest.mark.asyncio
async def test_notion_service_list_databases(
    notion_service, notion_api_key, mock_notion_databases_response
):
    """Testa listagem de databases via servico."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = mock_notion_databases_response
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=mock_response)):
        databases = await notion_service.list_databases(api_key=notion_api_key)

    assert len(databases) == 3


def test_notion_service_business_to_properties(notion_service, sample_business_for_notion):
    """Testa conversao de Business para propriedades Notion."""
    properties = notion_service._business_to_notion_properties(sample_business_for_notion)

    # Verificar campos basicos
    assert "Nome" in properties
    assert properties["Nome"]["title"][0]["text"]["content"] == "Cafe Notion Test"

    # Verificar email
    assert "Email" in properties
    assert properties["Email"]["email"] == "info@cafe-test.pt"

    # Verificar telefone
    assert "Telefone" in properties
    assert properties["Telefone"]["phone_number"] == "+351 912 345 678"

    # Verificar website
    assert "Website" in properties
    assert properties["Website"]["url"] == "https://cafe-test.pt"

    # Verificar score
    assert "Score" in properties
    assert properties["Score"]["number"] == 75.0

    # Verificar tags
    assert "Tags" in properties
    assert len(properties["Tags"]["multi_select"]) == 2


def test_notion_service_business_to_properties_minimal(notion_service):
    """Testa conversao com dados minimos."""
    business = Business(
        id="min_123",
        name="Minimal Business",
        formatted_address="Rua X",
        latitude=38.7,
        longitude=-9.1,
        place_types=["restaurant"],
        business_status="OPERATIONAL",
        has_website=False,
        lead_score=30,
        lead_status="new",
    )

    properties = notion_service._business_to_notion_properties(business)

    assert "Nome" in properties
    assert "Email" not in properties  # Sem email
    assert "Telefone" not in properties  # Sem telefone
    assert "Website" not in properties  # Sem website


@pytest.mark.asyncio
async def test_notion_service_sync_lead_create(
    notion_service, sample_business_for_notion, notion_database_id, mock_notion_page_created
):
    """Testa sincronizacao (criar novo lead)."""
    # Mock config
    mock_config = {
        "api_key": "test_key",
        "database_id": notion_database_id,
        "is_active": True,
    }

    # Mock business sem notion_page_id (sera criado)
    sample_business_for_notion.notion_page_id = None

    with patch.object(notion_service, "get_config", return_value=mock_config):
        with patch("src.services.notion.db.get_session") as mock_session:
            mock_db_session = MagicMock()
            mock_session.return_value.__enter__.return_value = mock_db_session
            mock_db_session.get.return_value = sample_business_for_notion

            # Mock Notion API
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_notion_page_created
            mock_response.raise_for_status = MagicMock()

            with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=mock_response)):
                result = await notion_service.sync_lead("test_biz_123")

    assert result.success is True
    assert result.action == "created"
    assert result.notion_page_id == "page_123"


@pytest.mark.asyncio
async def test_notion_service_sync_lead_update(
    notion_service, sample_business_for_notion, notion_database_id, mock_notion_page_created
):
    """Testa sincronizacao (atualizar lead existente)."""
    mock_config = {
        "api_key": "test_key",
        "database_id": notion_database_id,
        "is_active": True,
    }

    # Business ja tem notion_page_id (sera atualizado)
    sample_business_for_notion.notion_page_id = "page_existing_123"

    with patch.object(notion_service, "get_config", return_value=mock_config):
        with patch("src.services.notion.db.get_session") as mock_session:
            mock_db_session = MagicMock()
            mock_session.return_value.__enter__.return_value = mock_db_session
            mock_db_session.get.return_value = sample_business_for_notion

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_notion_page_created
            mock_response.raise_for_status = MagicMock()

            with patch("httpx.AsyncClient.patch", new=AsyncMock(return_value=mock_response)):
                result = await notion_service.sync_lead("test_biz_123")

    assert result.success is True
    assert result.action == "updated"


@pytest.mark.asyncio
async def test_notion_service_sync_lead_not_configured(notion_service):
    """Testa sync sem configuracao ativa."""
    with patch.object(notion_service, "get_config", return_value=None):
        result = await notion_service.sync_lead("test_biz_123")

    assert result.success is False
    assert "nao configurado" in result.error


@pytest.mark.asyncio
async def test_notion_service_sync_lead_business_not_found(notion_service):
    """Testa sync com business nao encontrado."""
    mock_config = {
        "api_key": "test_key",
        "database_id": "db_123",
        "is_active": True,
    }

    with patch.object(notion_service, "get_config", return_value=mock_config):
        with patch("src.services.notion.db.get_session") as mock_session:
            mock_db_session = MagicMock()
            mock_session.return_value.__enter__.return_value = mock_db_session
            mock_db_session.get.return_value = None  # Business nao encontrado

            result = await notion_service.sync_lead("nonexistent_id")

    assert result.success is False
    assert "nao encontrado" in result.error


@pytest.mark.asyncio
async def test_notion_service_sync_batch(notion_service):
    """Testa sincronizacao em lote."""
    business_ids = ["biz_1", "biz_2", "biz_3"]

    with patch.object(
        notion_service,
        "sync_lead",
        new=AsyncMock(
            return_value=SyncResult(
                success=True,
                business_id="biz_1",
                notion_page_id="page_1",
                action="created",
            )
        ),
    ):
        results = await notion_service.sync_batch(business_ids, concurrency=2)

    assert len(results) == 3
    assert "biz_1" in results
    assert "biz_2" in results
    assert "biz_3" in results


def test_notion_service_get_sync_stats(notion_service):
    """Testa estatisticas de sincronizacao."""
    with patch("src.services.notion.db.get_session") as mock_session:
        mock_db_session = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_db_session

        # Mock queries
        mock_db_session.query.return_value.count.return_value = 100  # Total
        mock_db_session.query.return_value.filter.return_value.count.return_value = 60  # Synced

        stats = notion_service.get_sync_stats()

    assert stats["total"] == 100
    assert stats["synced"] == 60
    assert stats["not_synced"] == 40
