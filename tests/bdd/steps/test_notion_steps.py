"""Steps BDD para Feature 06 - Sincronização com Notion."""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.database.models import IntegrationConfig
from src.services.notion import NotionClient, NotionService
from tests.conftest import BusinessFactory


# Carregar cenários
scenarios("../features/06_notion_sync.feature")


# =============================================================================
# Fixtures Específicas
# =============================================================================


@pytest.fixture
def notion_service():
    """NotionService para testes."""
    return NotionService()


@pytest.fixture
def valid_notion_api_key():
    """API key válida de teste."""
    return "secret_ntn_VALID_KEY_123456789"


@pytest.fixture
def invalid_notion_api_key():
    """API key inválida de teste."""
    return "secret_ntn_INVALID_KEY"


@pytest.fixture
def mock_notion_databases():
    """Mock de databases Notion."""
    return [
        {
            "id": "database_123",
            "title": "CRM Leads",
            "url": "https://notion.so/database_123",
        },
        {
            "id": "database_456",
            "title": "Contactos",
            "url": "https://notion.so/database_456",
        },
    ]


@pytest.fixture
def notion_context():
    """Contexto para partilhar dados entre steps."""
    return {
        "api_key": None,
        "database_id": "database_123",
        "workspace_name": None,
        "connection_result": None,
        "databases": None,
        "sync_results": [],
        "leads": [],
        "error": None,
        "notion_pages_created": [],
        "sync_delays": [],
    }


# =============================================================================
# GIVEN Steps
# =============================================================================


@given("que tenho uma base de dados de teste")
def setup_test_database(test_session):
    """Inicializa base de dados de teste."""
    # A fixture test_session já cria as tabelas
    pass


@given("que tenho 3 leads na base de dados", target_fixture="leads_in_db")
def create_three_leads(test_session):
    """Cria 3 leads na base de dados."""
    leads = BusinessFactory.create_batch(3)
    for lead in leads:
        test_session.add(lead)
    test_session.commit()
    return leads


@given("que tenho uma API key válida do Notion")
def set_valid_api_key(notion_context, valid_notion_api_key):
    """Define API key válida."""
    notion_context["api_key"] = valid_notion_api_key


@given("que tenho uma API key inválida do Notion")
def set_invalid_api_key(notion_context, invalid_notion_api_key):
    """Define API key inválida."""
    notion_context["api_key"] = invalid_notion_api_key


@given("que o Notion tem 2 databases disponíveis")
def setup_mock_databases(notion_context, mock_notion_databases):
    """Prepara mock de databases."""
    # O mock será configurado no when step
    pass


@given("que o Notion está configurado com database válida")
def configure_notion_valid(test_session, notion_context, valid_notion_api_key):
    """Configura Notion com database válida."""
    config = IntegrationConfig(
        service="notion",
        api_key=valid_notion_api_key,
        config={
            "database_id": notion_context["database_id"],
            "workspace_name": "Test Workspace",
        },
        is_active=True,
    )
    test_session.add(config)
    test_session.commit()
    notion_context["api_key"] = valid_notion_api_key


@given("que o Notion está configurado com database inválida")
def configure_notion_invalid(test_session, notion_context, valid_notion_api_key):
    """Configura Notion com database inválida."""
    config = IntegrationConfig(
        service="notion",
        api_key=valid_notion_api_key,
        config={
            "database_id": "invalid_database_id",
            "workspace_name": "Test Workspace",
        },
        is_active=True,
    )
    test_session.add(config)
    test_session.commit()


@given(parsers.parse("que tenho {count:d} leads não sincronizados"))
def create_unsynced_leads(test_session, notion_context, count):
    """Cria leads não sincronizados."""
    leads = BusinessFactory.create_batch(count)
    for lead in leads:
        lead.notion_page_id = None
        lead.notion_synced_at = None
        test_session.add(lead)
    test_session.commit()
    notion_context["leads"] = leads


@given(parsers.parse("que tenho {count:d} lead não sincronizado"))
def create_one_unsynced_lead(test_session, notion_context, count):
    """Cria 1 lead não sincronizado."""
    create_unsynced_leads(test_session, notion_context, count)


@given("que tenho 1 lead já sincronizado com notion_page_id")
def create_synced_lead(test_session, notion_context):
    """Cria 1 lead já sincronizado."""
    lead = BusinessFactory.create(
        notion_page_id="page_existing_123",
        notion_synced_at=datetime.utcnow(),
    )
    test_session.add(lead)
    test_session.commit()
    notion_context["leads"] = [lead]


@given('que altero o status do lead para "qualified"')
def update_lead_status(test_session, notion_context):
    """Atualiza status do lead."""
    lead = notion_context["leads"][0]
    lead.lead_status = "qualified"
    test_session.commit()


@given(parsers.parse("que tenho {count:d} leads não sincronizados"))
def create_multiple_unsynced_leads(test_session, notion_context, count):
    """Cria múltiplos leads não sincronizados."""
    create_unsynced_leads(test_session, notion_context, count)


# =============================================================================
# WHEN Steps
# =============================================================================


@when("testo a conexão com o Notion")
async def test_notion_connection(notion_context):
    """Testa conexão com Notion."""
    api_key = notion_context["api_key"]

    # Mock da resposta HTTP
    if "INVALID" in api_key:
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.json.return_value = {"message": "Unauthorized"}

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = mock_client.return_value.__aenter__.return_value
            mock_instance.get = AsyncMock(
                side_effect=httpx.HTTPStatusError(
                    message="Unauthorized",
                    request=MagicMock(),
                    response=mock_response,
                )
            )

            client = NotionClient(api_key)
            try:
                result = await client.test_connection()
                notion_context["connection_result"] = result
            except httpx.HTTPStatusError as e:
                notion_context["error"] = e
    else:
        mock_user_data = {
            "object": "user",
            "id": "user_123",
            "name": "Test User",
            "type": "person",
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = mock_client.return_value.__aenter__.return_value
            mock_instance.get = AsyncMock(
                return_value=MagicMock(
                    json=lambda: mock_user_data,
                    raise_for_status=lambda: None,
                )
            )

            client = NotionClient(api_key)
            result = await client.test_connection()
            notion_context["connection_result"] = result
            notion_context["workspace_name"] = result.get("name")


@when("listo as databases disponíveis")
async def list_notion_databases(notion_context, mock_notion_databases):
    """Lista databases Notion."""
    api_key = notion_context["api_key"]

    mock_search_response = {
        "object": "list",
        "results": [
            {
                "id": "database_123",
                "object": "database",
                "title": [{"type": "text", "plain_text": "CRM Leads"}],
                "url": "https://notion.so/database_123",
            },
            {
                "id": "database_456",
                "object": "database",
                "title": [{"type": "text", "plain_text": "Contactos"}],
                "url": "https://notion.so/database_456",
            },
        ],
    }

    with patch("httpx.AsyncClient") as mock_client:
        mock_instance = mock_client.return_value.__aenter__.return_value
        mock_instance.post = AsyncMock(
            return_value=MagicMock(
                json=lambda: mock_search_response,
                raise_for_status=lambda: None,
            )
        )

        client = NotionClient(api_key)
        databases = await client.list_databases()
        notion_context["databases"] = databases


@when(parsers.parse("sincronizo os {count:d} leads com o Notion"))
async def sync_multiple_leads(test_session, notion_context, count):
    """Sincroniza múltiplos leads."""
    leads = notion_context["leads"]

    # Mock da API Notion para criar pages
    with patch("httpx.AsyncClient") as mock_client:
        mock_instance = mock_client.return_value.__aenter__.return_value

        def create_page_mock(*args, **kwargs):
            page_id = f"page_{len(notion_context['notion_pages_created']) + 1}"
            notion_context["notion_pages_created"].append(page_id)
            return MagicMock(
                json=lambda: {"id": page_id, "object": "page"},
                raise_for_status=lambda: None,
            )

        mock_instance.post = AsyncMock(side_effect=create_page_mock)

        # Simular NotionService com DB mockada
        with patch("src.services.notion.db.get_session") as mock_db:
            mock_db.return_value.__enter__.return_value = test_session

            service = NotionService()

            for lead in leads[:count]:
                result = await service.sync_lead(lead.id)
                notion_context["sync_results"].append(result)


@when("sincronizo o lead com o Notion")
async def sync_single_lead(test_session, notion_context):
    """Sincroniza um lead."""
    await sync_multiple_leads(test_session, notion_context, 1)


@when("sincronizo o lead com o Notion pela primeira vez")
async def sync_lead_first_time(test_session, notion_context):
    """Primeira sincronização."""
    await sync_single_lead(test_session, notion_context)


@when("sincronizo o mesmo lead com o Notion novamente")
async def sync_lead_second_time(test_session, notion_context):
    """Segunda sincronização (deve fazer update)."""
    lead = notion_context["leads"][0]

    # Mock da API Notion para UPDATE
    with patch("httpx.AsyncClient") as mock_client:
        mock_instance = mock_client.return_value.__aenter__.return_value
        mock_instance.patch = AsyncMock(
            return_value=MagicMock(
                json=lambda: {"id": lead.notion_page_id, "object": "page"},
                raise_for_status=lambda: None,
            )
        )

        with patch("src.services.notion.db.get_session") as mock_db:
            mock_db.return_value.__enter__.return_value = test_session

            service = NotionService()
            result = await service.sync_lead(lead.id)
            notion_context["sync_results"].append(result)


@when(parsers.parse("sincronizo os {count:d} leads em batch com concurrency {concurrency:d}"))
async def sync_batch_with_concurrency(test_session, notion_context, count, concurrency):
    """Sincroniza batch com concurrency."""
    leads = notion_context["leads"]
    lead_ids = [lead.id for lead in leads[:count]]

    start_times = []

    # Mock da API Notion
    with patch("httpx.AsyncClient") as mock_client:
        mock_instance = mock_client.return_value.__aenter__.return_value

        async def create_page_with_delay(*args, **kwargs):
            import time

            current_time = time.time()
            start_times.append(current_time)

            # Simular rate limiting
            await asyncio.sleep(0.4)

            page_id = f"page_{len(notion_context['notion_pages_created']) + 1}"
            notion_context["notion_pages_created"].append(page_id)
            return MagicMock(
                json=lambda: {"id": page_id, "object": "page"},
                raise_for_status=lambda: None,
            )

        mock_instance.post = AsyncMock(side_effect=create_page_with_delay)

        with patch("src.services.notion.db.get_session") as mock_db:
            mock_db.return_value.__enter__.return_value = test_session

            service = NotionService()
            results = await service.sync_batch(lead_ids, concurrency=concurrency)
            notion_context["sync_results"] = list(results.values())

            # Calcular delays entre requisições
            if len(start_times) > 1:
                for i in range(1, len(start_times)):
                    delay = start_times[i] - start_times[i - 1]
                    notion_context["sync_delays"].append(delay)


@when("tento sincronizar o lead com o Notion")
async def try_sync_lead_without_config(test_session, notion_context):
    """Tenta sincronizar sem configuração."""
    lead = notion_context["leads"][0] if notion_context["leads"] else None

    if lead:
        with patch("src.services.notion.db.get_session") as mock_db:
            mock_db.return_value.__enter__.return_value = test_session

            service = NotionService()
            result = await service.sync_lead(lead.id)
            notion_context["sync_results"].append(result)


# =============================================================================
# THEN Steps
# =============================================================================


@then("a conexão deve ser bem-sucedida")
def verify_connection_success(notion_context):
    """Verifica sucesso da conexão."""
    assert notion_context["connection_result"] is not None
    assert "id" in notion_context["connection_result"]


@then("devo receber informação do workspace")
def verify_workspace_info(notion_context):
    """Verifica informação do workspace."""
    assert notion_context["workspace_name"] is not None


@then("a conexão deve falhar")
def verify_connection_failure(notion_context):
    """Verifica falha da conexão."""
    assert notion_context["error"] is not None


@then("devo receber erro de autenticação")
def verify_auth_error(notion_context):
    """Verifica erro de autenticação."""
    error = notion_context["error"]
    assert isinstance(error, httpx.HTTPStatusError)
    assert error.response.status_code == 401


@then(parsers.parse("devo receber {count:d} databases"))
def verify_database_count(notion_context, count):
    """Verifica número de databases."""
    assert len(notion_context["databases"]) == count


@then("cada database deve ter id e título")
def verify_database_structure(notion_context):
    """Verifica estrutura das databases."""
    for db in notion_context["databases"]:
        assert "id" in db
        assert "title" in db
        assert db["title"] != ""


@then(parsers.parse("{count:d} pages devem ser criadas no Notion"))
def verify_pages_created(notion_context, count):
    """Verifica criação de pages."""
    assert len(notion_context["notion_pages_created"]) == count


@then("os leads devem ter notion_page_id preenchido")
def verify_notion_page_ids(test_session, notion_context):
    """Verifica notion_page_id preenchido."""
    for lead in notion_context["leads"]:
        test_session.refresh(lead)
        assert lead.notion_page_id is not None


@then("o campo notion_synced_at deve estar atualizado")
def verify_synced_at(test_session, notion_context):
    """Verifica notion_synced_at."""
    for lead in notion_context["leads"]:
        test_session.refresh(lead)
        assert lead.notion_synced_at is not None


@then("a page existente deve ser atualizada")
def verify_page_updated(notion_context):
    """Verifica que page foi atualizada."""
    results = notion_context["sync_results"]
    assert any(r.action == "updated" for r in results if r.success)


@then("nenhuma page nova deve ser criada")
def verify_no_new_pages(notion_context):
    """Verifica que não foram criadas pages novas."""
    results = notion_context["sync_results"]
    update_count = sum(1 for r in results if r.success and r.action == "updated")
    create_count = sum(1 for r in results if r.success and r.action == "created")

    # A última sincronização deve ser update
    if results:
        last_result = results[-1]
        assert last_result.action == "updated"


@then("a sincronização deve falhar")
def verify_sync_failure(notion_context):
    """Verifica falha na sincronização."""
    results = notion_context["sync_results"]
    assert len(results) > 0
    assert not results[-1].success


@then("o lead não deve ter notion_page_id")
def verify_no_notion_page_id(test_session, notion_context):
    """Verifica ausência de notion_page_id."""
    if notion_context["leads"]:
        lead = notion_context["leads"][0]
        test_session.refresh(lead)
        assert lead.notion_page_id is None


@then("devo receber mensagem de erro específica")
def verify_error_message(notion_context):
    """Verifica mensagem de erro."""
    results = notion_context["sync_results"]
    assert len(results) > 0
    assert results[-1].error is not None


@then(parsers.parse("apenas {count:d} page deve existir no Notion"))
def verify_single_page(notion_context, count):
    """Verifica que existe apenas 1 page."""
    # Contar creates vs updates
    results = notion_context["sync_results"]
    created = sum(1 for r in results if r.success and r.action == "created")
    assert created == count


@then("a segunda sincronização deve ser update")
def verify_second_is_update(notion_context):
    """Verifica que segunda sync é update."""
    results = notion_context["sync_results"]
    assert len(results) >= 2
    assert results[1].action == "updated"


@then("as requisições devem respeitar o rate limit")
def verify_rate_limit(notion_context):
    """Verifica rate limiting."""
    delays = notion_context["sync_delays"]
    # Verificar que há delays entre requisições
    assert len(delays) > 0


@then("deve haver delay entre cada requisição")
def verify_delays_exist(notion_context):
    """Verifica delays."""
    delays = notion_context["sync_delays"]
    for delay in delays:
        # Rate limit do Notion: 3 req/s = 0.33s entre cada
        # Com sleep(0.4), deve ser >= 0.3s
        assert delay >= 0.3


@then(parsers.parse("todas as {count:d} pages devem ser criadas com sucesso"))
def verify_all_pages_created(notion_context, count):
    """Verifica criação de todas as pages."""
    results = notion_context["sync_results"]
    successful = sum(1 for r in results if r.success)
    assert successful == count


@then('devo receber erro "Notion não configurado ou inativo"')
def verify_not_configured_error(notion_context):
    """Verifica erro de configuração."""
    results = notion_context["sync_results"]
    assert len(results) > 0
    assert results[-1].error is not None
    assert "não configurado" in results[-1].error.lower() or "inativo" in results[-1].error.lower()


@then("o campo notion_synced_at deve ser atualizado")
def verify_synced_at_updated(test_session, notion_context):
    """Verifica atualização de notion_synced_at."""
    verify_synced_at(test_session, notion_context)
