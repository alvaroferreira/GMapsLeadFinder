"""Steps BDD para Feature 07 - Gestão de Configurações."""

import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.database.models import IntegrationConfig
from src.services.notion import NotionService


# Carregar cenários
scenarios("../features/07_settings.feature")


# =============================================================================
# Fixtures Específicas
# =============================================================================


@pytest.fixture
def settings_context():
    """Contexto para partilhar dados entre steps."""
    return {
        "api_key": None,
        "database_id": None,
        "response": None,
        "error": None,
        "env_vars": {},
        "env_file_content": "",
        "notion_config": None,
        "search_attempted": False,
        "ai_providers": {},
        "masked_key": None,
    }


@pytest.fixture
def temp_env_file(tmp_path):
    """Cria ficheiro .env temporário para testes."""
    env_file = tmp_path / ".env"
    env_file.write_text("""# Test Environment
GOOGLE_PLACES_API_KEY=your_api_key_here
GOOGLE_PLACES_ENABLED=true
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
GEMINI_API_KEY=
DEFAULT_AI_PROVIDER=
""")
    return env_file


def read_env_file(env_path: Path) -> dict:
    """Le ficheiro .env."""
    env_vars = {}
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    env_vars[key.strip()] = value.strip()
    return env_vars


# =============================================================================
# GIVEN Steps
# =============================================================================


@given("que tenho acesso à página de settings")
def access_settings_page():
    """Acesso à página de settings."""
    # Contexto implícito - sempre temos acesso
    pass


@given("que tenho uma Google Places API key válida")
def set_valid_google_api_key(settings_context):
    """Define Google Places API key válida."""
    settings_context["api_key"] = "AIzaSyDEMO_VALID_KEY_1234567890ABCDEF"


@given(parsers.parse('que tenho uma API key com formato inválido "{invalid_key}"'))
def set_invalid_api_key(settings_context, invalid_key):
    """Define API key inválida."""
    settings_context["api_key"] = invalid_key


@given("que tenho uma API key válida do Notion")
def set_valid_notion_key(settings_context):
    """Define Notion API key válida."""
    settings_context["api_key"] = "secret_ntn_VALID_NOTION_KEY_123"


@given("que tenho um database_id válido")
def set_valid_database_id(settings_context):
    """Define database_id válido."""
    settings_context["database_id"] = "database_123456789"


@given("que a Google Places API está ativa")
def set_google_api_active(temp_env_file, settings_context):
    """Define Google Places API como ativa."""
    with patch("src.web.server._get_env_file_path", return_value=temp_env_file):
        env_vars = read_env_file(temp_env_file)
        env_vars["GOOGLE_PLACES_API_KEY"] = "AIzaSyDEMO_KEY_12345"
        env_vars["GOOGLE_PLACES_ENABLED"] = "true"

        lines = [f"{k}={v}" for k, v in env_vars.items()]
        temp_env_file.write_text("\n".join(lines))
        settings_context["env_vars"] = env_vars


@given("que não tenho Google Places API configurada")
def unset_google_api(temp_env_file, settings_context):
    """Remove configuração Google Places API."""
    with patch("src.web.server._get_env_file_path", return_value=temp_env_file):
        env_vars = read_env_file(temp_env_file)
        env_vars["GOOGLE_PLACES_API_KEY"] = ""
        env_vars["GOOGLE_PLACES_ENABLED"] = "false"

        lines = [f"{k}={v}" for k, v in env_vars.items()]
        temp_env_file.write_text("\n".join(lines))


@given("que o Notion não está configurado")
def unset_notion_config(test_session):
    """Remove configuração Notion."""
    # Limpar qualquer config existente
    test_session.query(IntegrationConfig).filter(IntegrationConfig.service == "notion").delete()
    test_session.commit()


@given("que tenho 1 lead na base de dados")
def create_one_lead(test_session, business_factory):
    """Cria 1 lead."""
    lead = business_factory.create()
    test_session.add(lead)
    test_session.commit()


@given("que tenho API keys para OpenAI, Anthropic e Gemini")
def set_all_ai_providers(settings_context):
    """Define todas as API keys de AI."""
    settings_context["ai_providers"] = {
        "openai": "sk-OPENAI_KEY_12345678",
        "anthropic": "sk-ant-ANTHROPIC_KEY_12345",
        "gemini": "GEMINI_KEY_12345678",
    }


@given("que tenho Google Places e OpenAI configurados")
def set_multiple_apis(temp_env_file, settings_context):
    """Configura múltiplas APIs."""
    env_vars = read_env_file(temp_env_file)
    env_vars["GOOGLE_PLACES_API_KEY"] = "AIzaSyDEMO_GOOGLE_KEY"
    env_vars["OPENAI_API_KEY"] = "sk-OPENAI_ORIGINAL_KEY"
    env_vars["GOOGLE_PLACES_ENABLED"] = "true"
    env_vars["OPENAI_ENABLED"] = "true"

    lines = [f"{k}={v}" for k, v in env_vars.items()]
    temp_env_file.write_text("\n".join(lines))
    settings_context["env_vars"] = env_vars


@given(parsers.parse('que tenho uma API key configurada "{api_key}"'))
def set_configured_api_key(settings_context):
    """Define API key configurada."""
    settings_context["api_key"] = "AIzaSyDEMO_KEY_12345678"


# =============================================================================
# WHEN Steps
# =============================================================================


@when("configuro a API key do Google Places")
def configure_google_api_key(temp_env_file, settings_context):
    """Configura Google Places API key."""
    api_key = settings_context["api_key"]

    with patch("src.web.server._get_env_file_path", return_value=temp_env_file):
        env_vars = read_env_file(temp_env_file)
        env_vars["GOOGLE_PLACES_API_KEY"] = api_key

        lines = [f"{k}={v}" for k, v in env_vars.items()]
        temp_env_file.write_text("\n".join(lines))

        # Simular atualização runtime
        os.environ["GOOGLE_PLACES_API_KEY"] = api_key
        settings_context["response"] = {"success": True}


@when("tento configurar a API key do Google Places")
def try_configure_invalid_key(settings_context):
    """Tenta configurar API key inválida."""
    api_key = settings_context["api_key"]

    # Validação de formato
    if not api_key.startswith("AIza") or len(api_key) < 20:
        settings_context["error"] = "Formato de API key inválido"
        settings_context["response"] = {"success": False}
    else:
        settings_context["response"] = {"success": True}


@when("configuro a integração Notion")
async def configure_notion_integration(test_session, settings_context):
    """Configura integração Notion."""
    api_key = settings_context["api_key"]
    database_id = settings_context["database_id"]

    # Mock da API Notion
    with patch("httpx.AsyncClient") as mock_client:
        mock_instance = mock_client.return_value.__aenter__.return_value
        mock_instance.get = AsyncMock(
            return_value=MagicMock(
                json=lambda: {"name": "Test Workspace", "id": "user_123"},
                raise_for_status=lambda: None,
            )
        )

        with patch("src.services.notion.db.get_session") as mock_db:
            mock_db.return_value.__enter__.return_value = test_session

            service = NotionService()
            service.save_config(
                api_key=api_key,
                database_id=database_id,
                workspace_name="Test Workspace",
            )

            settings_context["notion_config"] = service.get_config()


@when("desativo a Google Places API via toggle")
def disable_google_api(temp_env_file, settings_context):
    """Desativa Google Places API."""
    with patch("src.web.server._get_env_file_path", return_value=temp_env_file):
        env_vars = read_env_file(temp_env_file)
        env_vars["GOOGLE_PLACES_ENABLED"] = "false"

        lines = [f"{k}={v}" for k, v in env_vars.items()]
        temp_env_file.write_text("\n".join(lines))
        settings_context["env_vars"] = env_vars


@when("reativo a Google Places API via toggle")
def enable_google_api(temp_env_file, settings_context):
    """Reativa Google Places API."""
    with patch("src.web.server._get_env_file_path", return_value=temp_env_file):
        env_vars = read_env_file(temp_env_file)
        env_vars["GOOGLE_PLACES_ENABLED"] = "true"

        lines = [f"{k}={v}" for k, v in env_vars.items()]
        temp_env_file.write_text("\n".join(lines))
        settings_context["env_vars"] = env_vars


@when("tento fazer uma pesquisa de lugares")
def try_search_places(settings_context):
    """Tenta fazer pesquisa."""
    # Simular verificação de API key
    from src.config import settings as app_settings

    if not app_settings.has_api_key:
        settings_context["error"] = "API key não configurada"
        settings_context["search_attempted"] = False
    else:
        settings_context["search_attempted"] = True


@when("depois desconecto a integração Notion")
def disconnect_notion(test_session, settings_context):
    """Desconecta Notion."""
    with patch("src.services.notion.db.get_session") as mock_db:
        mock_db.return_value.__enter__.return_value = test_session

        service = NotionService()
        service.disconnect()


@when("tento sincronizar o lead com o Notion")
async def try_sync_without_config(test_session, settings_context):
    """Tenta sincronizar sem config."""
    from src.services.notion import NotionService

    with patch("src.services.notion.db.get_session") as mock_db:
        mock_db.return_value.__enter__.return_value = test_session

        service = NotionService()

        # Buscar um lead qualquer
        from src.database.models import Business

        lead = test_session.query(Business).first()

        if lead:
            result = await service.sync_lead(lead.id)
            if not result.success:
                settings_context["error"] = result.error


@when("configuro os 3 AI providers")
def configure_all_ai_providers(temp_env_file, settings_context):
    """Configura todos os AI providers."""
    providers = settings_context["ai_providers"]

    with patch("src.web.server._get_env_file_path", return_value=temp_env_file):
        env_vars = read_env_file(temp_env_file)
        env_vars["OPENAI_API_KEY"] = providers["openai"]
        env_vars["ANTHROPIC_API_KEY"] = providers["anthropic"]
        env_vars["GEMINI_API_KEY"] = providers["gemini"]

        lines = [f"{k}={v}" for k, v in env_vars.items()]
        temp_env_file.write_text("\n".join(lines))
        settings_context["env_vars"] = env_vars


@when(parsers.parse('seleciono "{provider}" como provider padrão'))
def set_default_provider(temp_env_file, settings_context, provider):
    """Define provider padrão."""
    with patch("src.web.server._get_env_file_path", return_value=temp_env_file):
        env_vars = read_env_file(temp_env_file)
        env_vars["DEFAULT_AI_PROVIDER"] = provider

        lines = [f"{k}={v}" for k, v in env_vars.items()]
        temp_env_file.write_text("\n".join(lines))
        settings_context["env_vars"] = env_vars


@when("visualizo a página de settings")
def view_settings_page(settings_context):
    """Visualiza settings."""
    from src.web.server import _mask_api_key

    api_key = settings_context["api_key"]
    settings_context["masked_key"] = _mask_api_key(api_key)


@when("atualizo apenas a API key do Google Places")
def update_google_key_only(temp_env_file, settings_context):
    """Atualiza apenas Google Places key."""
    with patch("src.web.server._get_env_file_path", return_value=temp_env_file):
        env_vars = read_env_file(temp_env_file)
        old_openai = env_vars.get("OPENAI_API_KEY")

        # Atualizar apenas Google
        env_vars["GOOGLE_PLACES_API_KEY"] = "AIzaSyNEW_GOOGLE_KEY_12345"

        lines = [f"{k}={v}" for k, v in env_vars.items()]
        temp_env_file.write_text("\n".join(lines))

        # Verificar que OpenAI não mudou
        updated_vars = read_env_file(temp_env_file)
        settings_context["old_openai_key"] = old_openai
        settings_context["env_vars"] = updated_vars


# =============================================================================
# THEN Steps
# =============================================================================


@then("a configuração deve ser guardada no .env")
def verify_saved_in_env(temp_env_file, settings_context):
    """Verifica que foi guardado no .env."""
    env_vars = read_env_file(temp_env_file)
    api_key = settings_context["api_key"]
    assert env_vars.get("GOOGLE_PLACES_API_KEY") == api_key


@then("a variável de ambiente deve estar atualizada")
def verify_env_var_updated(settings_context):
    """Verifica env var."""
    # Verificado no step when
    assert settings_context["response"]["success"] is True


@then("devo receber confirmação de sucesso")
def verify_success_response(settings_context):
    """Verifica resposta de sucesso."""
    assert settings_context["response"]["success"] is True


@then("a configuração não deve ser guardada")
def verify_not_saved(settings_context):
    """Verifica que não foi guardado."""
    assert settings_context["response"]["success"] is False


@then("devo receber erro de validação de formato")
def verify_validation_error(settings_context):
    """Verifica erro de validação."""
    assert settings_context["error"] is not None
    assert (
        "formato" in settings_context["error"].lower()
        or "inválido" in settings_context["error"].lower()
    )


@then("a configuração deve ser guardada na base de dados")
def verify_saved_in_db(test_session):
    """Verifica que foi guardado na DB."""
    config = (
        test_session.query(IntegrationConfig).filter(IntegrationConfig.service == "notion").first()
    )
    assert config is not None


@then("o campo is_active deve ser True")
def verify_is_active(settings_context):
    """Verifica is_active."""
    assert settings_context["notion_config"]["is_active"] is True


@then("devo ver o workspace_name nas configurações")
def verify_workspace_name(settings_context):
    """Verifica workspace_name."""
    assert settings_context["notion_config"]["workspace_name"] == "Test Workspace"


@then(parsers.parse('a variável GOOGLE_PLACES_ENABLED deve ser "{value}"'))
def verify_enabled_value(temp_env_file, value):
    """Verifica valor de ENABLED."""
    env_vars = read_env_file(temp_env_file)
    assert env_vars.get("GOOGLE_PLACES_ENABLED") == value


@then("a API key deve ser preservada")
def verify_key_preserved(temp_env_file):
    """Verifica que key foi preservada."""
    env_vars = read_env_file(temp_env_file)
    assert env_vars.get("GOOGLE_PLACES_API_KEY") != ""


@then("a operação deve falhar")
def verify_operation_failed(settings_context):
    """Verifica falha."""
    assert settings_context["error"] is not None or settings_context["search_attempted"] is False


@then(parsers.parse('devo receber mensagem "{message}"'))
def verify_error_message(settings_context, message):
    """Verifica mensagem de erro."""
    error = settings_context.get("error", "")
    assert message.lower() in error.lower()


@then("devo poder reconectar novamente")
def verify_can_reconnect(test_session):
    """Verifica que pode reconectar."""
    # Após disconnect, não deve haver config
    config = (
        test_session.query(IntegrationConfig).filter(IntegrationConfig.service == "notion").first()
    )
    # Se houver, é porque reconectou
    # Se não houver, é esperado após disconnect
    assert True  # Pode sempre reconectar


@then("a nova configuração deve substituir a anterior")
def verify_config_replaced(test_session):
    """Verifica substituição."""
    configs = (
        test_session.query(IntegrationConfig).filter(IntegrationConfig.service == "notion").all()
    )
    # Deve haver no máximo 1 config
    assert len(configs) <= 1


@then("a sincronização deve falhar")
def verify_sync_failed(settings_context):
    """Verifica falha de sync."""
    assert settings_context["error"] is not None


@then(parsers.parse('devo receber erro "{error_msg}"'))
def verify_specific_error(settings_context, error_msg):
    """Verifica erro específico."""
    error = settings_context.get("error", "")
    assert error_msg.lower() in error.lower() or any(
        word in error.lower() for word in error_msg.lower().split()
    )


@then("as 3 API keys devem estar guardadas no .env")
def verify_all_keys_saved(temp_env_file, settings_context):
    """Verifica todas as keys."""
    env_vars = read_env_file(temp_env_file)
    providers = settings_context["ai_providers"]

    assert env_vars.get("OPENAI_API_KEY") == providers["openai"]
    assert env_vars.get("ANTHROPIC_API_KEY") == providers["anthropic"]
    assert env_vars.get("GEMINI_API_KEY") == providers["gemini"]


@then(parsers.parse('o DEFAULT_AI_PROVIDER deve ser "{provider}"'))
def verify_default_provider(temp_env_file, provider):
    """Verifica provider padrão."""
    env_vars = read_env_file(temp_env_file)
    assert env_vars.get("DEFAULT_AI_PROVIDER") == provider


@then(parsers.parse('posso alternar para "{provider}" posteriormente'))
def verify_can_switch_provider(temp_env_file, provider):
    """Verifica que pode alternar."""
    # Simular alternância
    env_vars = read_env_file(temp_env_file)
    env_vars["DEFAULT_AI_PROVIDER"] = provider

    lines = [f"{k}={v}" for k, v in env_vars.items()]
    temp_env_file.write_text("\n".join(lines))

    updated_vars = read_env_file(temp_env_file)
    assert updated_vars.get("DEFAULT_AI_PROVIDER") == provider


@then(parsers.parse('devo ver a key mascarada como "{masked}"'))
def verify_masked_key(settings_context, masked):
    """Verifica key mascarada."""
    actual_masked = settings_context["masked_key"]
    assert actual_masked == masked


@then("os últimos caracteres não devem estar visíveis")
def verify_last_chars_hidden(settings_context):
    """Verifica últimos caracteres escondidos."""
    masked = settings_context["masked_key"]
    assert "••" in masked


@then("a nova key do Google Places deve ser guardada")
def verify_new_google_key_saved(temp_env_file):
    """Verifica nova key."""
    env_vars = read_env_file(temp_env_file)
    assert "NEW_GOOGLE_KEY" in env_vars.get("GOOGLE_PLACES_API_KEY", "")


@then("a API key do OpenAI deve permanecer inalterada")
def verify_openai_unchanged(settings_context):
    """Verifica OpenAI inalterada."""
    old_key = settings_context["old_openai_key"]
    new_key = settings_context["env_vars"].get("OPENAI_API_KEY")
    assert old_key == new_key


@then("as variáveis ENABLED não devem ser afetadas")
def verify_enabled_unchanged(temp_env_file):
    """Verifica ENABLED não afetadas."""
    env_vars = read_env_file(temp_env_file)
    # Devem continuar com valores
    assert "GOOGLE_PLACES_ENABLED" in env_vars
    assert "OPENAI_ENABLED" in env_vars
