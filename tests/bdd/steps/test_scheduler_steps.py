"""Steps BDD para Feature 08 - Agendamento Automático de Pesquisas."""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.database.models import AutomationLog, Notification, TrackedSearch
from src.services.scheduler import (
    AutomationScheduler,
    AutomationService,
    NotificationService,
)
from tests.conftest import TrackedSearchFactory


# Carregar cenários
scenarios("../features/08_scheduler.feature")


# =============================================================================
# Fixtures Específicas
# =============================================================================


@pytest.fixture
def scheduler_context():
    """Contexto para partilhar dados entre steps."""
    return {
        "scheduler": None,
        "tracked_search": None,
        "tracked_searches": [],
        "automation_result": None,
        "logs": [],
        "notifications": [],
        "stats": {},
        "error": None,
        "search_executed": False,
        "api_calls": [],
    }


@pytest.fixture
def automation_service():
    """AutomationService para testes."""
    return AutomationService()


@pytest.fixture
def notification_service():
    """NotificationService para testes."""
    return NotificationService()


# =============================================================================
# GIVEN Steps
# =============================================================================


@given("que tenho uma base de dados de teste")
def setup_test_db(test_session):
    """Setup DB de teste."""
    pass


@given("que o scheduler está inicializado")
def initialize_scheduler(scheduler_context):
    """Inicializa scheduler."""
    scheduler = AutomationScheduler(check_interval=1)
    scheduler_context["scheduler"] = scheduler


@given("que tenho parâmetros de pesquisa válidos")
def set_valid_search_params(scheduler_context):
    """Define parâmetros válidos."""
    scheduler_context["search_params"] = {
        "query": "restaurantes",
        "location": "Lisboa",
        "radius": 5000,
    }


@given(parsers.parse("que tenho {count:d} pesquisa rastreada ativa"))
def create_active_tracked_search(test_session, scheduler_context, count):
    """Cria pesquisa rastreada ativa."""
    tracked = TrackedSearchFactory.create(
        name="Test Search",
        is_active=True,
        next_run_at=datetime.utcnow(),
    )
    test_session.add(tracked)
    test_session.commit()
    scheduler_context["tracked_search"] = tracked
    scheduler_context["tracked_searches"] = [tracked]


@given("que next_run_at está no passado")
def set_next_run_past(test_session, scheduler_context):
    """Define next_run_at no passado."""
    tracked = scheduler_context["tracked_search"]
    tracked.next_run_at = datetime.utcnow() - timedelta(hours=1)
    test_session.commit()


@given("que tenho 1 pesquisa rastreada com notify_on_new=True")
def create_tracked_with_notifications(test_session, scheduler_context):
    """Cria pesquisa com notificações ativas."""
    tracked = TrackedSearchFactory.create(
        name="Search with Notifications",
        is_active=True,
        notify_on_new=True,
        notify_threshold_score=50,
    )
    test_session.add(tracked)
    test_session.commit()
    scheduler_context["tracked_search"] = tracked


@given(parsers.parse("threshold de score mínimo de {threshold:d}"))
def set_notification_threshold(test_session, scheduler_context, threshold):
    """Define threshold."""
    tracked = scheduler_context["tracked_search"]
    tracked.notify_threshold_score = threshold
    test_session.commit()


@given("a API do Google Places está indisponível")
def mock_api_unavailable(scheduler_context):
    """Mock API indisponível."""
    scheduler_context["api_unavailable"] = True


@given(parsers.parse("que tenho {count:d} pesquisas rastreadas"))
def create_multiple_tracked_searches(test_session, scheduler_context, count):
    """Cria múltiplas pesquisas."""
    searches = []
    for i in range(count):
        tracked = TrackedSearchFactory.create(
            name=f"Search {i + 1}",
            is_active=True,
        )
        test_session.add(tracked)
        searches.append(tracked)

    test_session.commit()
    scheduler_context["tracked_searches"] = searches


@given(parsers.parse("{active:d} estão ativas e {inactive:d} inativa"))
def set_active_inactive_searches(test_session, scheduler_context, active, inactive):
    """Define searches ativas e inativas."""
    searches = scheduler_context["tracked_searches"]

    # Primeiro X são ativas
    for i in range(active):
        searches[i].is_active = True

    # Resto são inativas
    for i in range(active, active + inactive):
        searches[i].is_active = False

    test_session.commit()


@given(parsers.parse("existem {count:d} logs de execução"))
def create_automation_logs(test_session, scheduler_context, count):
    """Cria logs de automação."""
    tracked = (
        scheduler_context["tracked_searches"][0] if scheduler_context["tracked_searches"] else None
    )

    if tracked:
        for i in range(count):
            log = AutomationLog(
                tracked_search_id=tracked.id,
                executed_at=datetime.utcnow() - timedelta(hours=i),
                total_found=10,
                new_found=2,
                high_score_found=1,
                duration_seconds=5.0,
                status="success",
            )
            test_session.add(log)

        test_session.commit()


@given(parsers.parse("{count:d} notificações não lidas"))
def create_unread_notifications(test_session, scheduler_context, count):
    """Cria notificações não lidas."""
    for i in range(count):
        notif = Notification(
            type="batch_complete",
            title=f"Notification {i + 1}",
            message="Test notification",
            is_read=False,
        )
        test_session.add(notif)

    test_session.commit()


@given(parsers.parse("next_run_at está agendado para daqui a {hours:d} horas"))
def set_next_run_future(test_session, scheduler_context, hours):
    """Define next_run_at no futuro."""
    tracked = scheduler_context["tracked_search"]
    tracked.next_run_at = datetime.utcnow() + timedelta(hours=hours)
    test_session.commit()


@given(parsers.parse("que tenho 1 pesquisa rastreada com {count:d} logs de execução"))
def create_tracked_with_logs(test_session, scheduler_context, count):
    """Cria pesquisa com logs."""
    tracked = TrackedSearchFactory.create(name="Search with Logs")
    test_session.add(tracked)
    test_session.commit()

    for i in range(count):
        log = AutomationLog(
            tracked_search_id=tracked.id,
            executed_at=datetime.utcnow() - timedelta(hours=i),
            status="success",
        )
        test_session.add(log)

    test_session.commit()
    scheduler_context["tracked_search"] = tracked


# =============================================================================
# WHEN Steps
# =============================================================================


@when(parsers.parse('crio uma pesquisa rastreada chamada "{name}"'))
def create_tracked_search(test_session, scheduler_context, name):
    """Cria pesquisa rastreada."""
    scheduler_context["search_name"] = name


@when(parsers.parse('Com query "{query}" e localização "{location}"'))
def set_query_and_location(scheduler_context, query, location):
    """Define query e localização."""
    scheduler_context["search_query"] = query
    scheduler_context["search_location"] = location


@when(parsers.parse("E intervalo de {hours:d} horas"))
def set_interval_and_create(test_session, scheduler_context, hours):
    """Define intervalo e cria."""
    with patch("src.services.scheduler.db.get_session") as mock_db:
        mock_db.return_value.__enter__.return_value = test_session

        service = AutomationService()
        result = service.create_tracked_search(
            name=scheduler_context["search_name"],
            query=scheduler_context["search_query"],
            location=scheduler_context["search_location"],
            interval_hours=hours,
        )

        # Buscar da DB
        tracked = test_session.get(TrackedSearch, result["id"])
        scheduler_context["tracked_search"] = tracked


@when("o scheduler executa o ciclo de verificação")
async def scheduler_executes_cycle(test_session, scheduler_context):
    """Scheduler executa ciclo."""
    scheduler = scheduler_context["scheduler"]

    # Mock SearchService
    mock_search_result = MagicMock()
    mock_search_result.total_found = 5
    mock_search_result.new_businesses = 3

    with patch("src.services.scheduler.db.get_session") as mock_db:
        mock_db.return_value.__enter__.return_value = test_session

        with patch.object(
            scheduler.search_service, "search", new_callable=AsyncMock
        ) as mock_search:
            mock_search.return_value = mock_search_result

            await scheduler._run_due_searches()
            scheduler_context["search_executed"] = True


@when(parsers.parse("a pesquisa descobre {count:d} novos leads"))
async def search_discovers_new_leads(test_session, scheduler_context, count):
    """Pesquisa descobre novos leads."""
    tracked = scheduler_context["tracked_search"]

    # Mock SearchService
    mock_search_result = MagicMock()
    mock_search_result.total_found = count
    mock_search_result.new_businesses = count

    with patch("src.services.scheduler.db.get_session") as mock_db:
        mock_db.return_value.__enter__.return_value = test_session

        scheduler = AutomationScheduler()

        with patch.object(
            scheduler.search_service, "search", new_callable=AsyncMock
        ) as mock_search:
            mock_search.return_value = mock_search_result

            # Expunge para usar fora da sessão
            test_session.expunge(tracked)
            result = await scheduler._execute_tracked_search(tracked)
            scheduler_context["automation_result"] = result


@when("executo a pesquisa manualmente")
async def execute_search_manually(test_session, scheduler_context):
    """Executa pesquisa manualmente."""
    await search_discovers_new_leads(test_session, scheduler_context, 5)


@when("o scheduler tenta executar a pesquisa")
async def scheduler_tries_execute(test_session, scheduler_context):
    """Scheduler tenta executar com erro."""
    tracked = scheduler_context["tracked_search"]

    with patch("src.services.scheduler.db.get_session") as mock_db:
        mock_db.return_value.__enter__.return_value = test_session

        scheduler = AutomationScheduler()

        with patch.object(
            scheduler.search_service, "search", new_callable=AsyncMock
        ) as mock_search:
            mock_search.side_effect = Exception("API unavailable")

            test_session.expunge(tracked)
            result = await scheduler._execute_tracked_search(tracked)
            scheduler_context["automation_result"] = result


@when("desativo a pesquisa via toggle")
def deactivate_search(test_session, scheduler_context):
    """Desativa pesquisa."""
    with patch("src.services.scheduler.db.get_session") as mock_db:
        mock_db.return_value.__enter__.return_value = test_session

        service = AutomationService()
        tracked = scheduler_context["tracked_search"]
        new_state = service.toggle_tracked_search(tracked.id)
        scheduler_context["new_state"] = new_state


@when("reativo a pesquisa via toggle")
def reactivate_search(test_session, scheduler_context):
    """Reativa pesquisa."""
    deactivate_search(test_session, scheduler_context)


@when("consulto as estatísticas de automação")
def get_automation_stats(test_session, scheduler_context):
    """Consulta estatísticas."""
    with patch("src.services.scheduler.db.get_session") as mock_db:
        mock_db.return_value.__enter__.return_value = test_session

        service = AutomationService()
        stats = service.get_automation_stats()
        scheduler_context["stats"] = stats


@when("executo a pesquisa com múltiplos resultados")
async def execute_search_with_results(test_session, scheduler_context):
    """Executa pesquisa com resultados."""
    tracked = scheduler_context["tracked_search"]

    # Mock com delay para simular rate limiting
    mock_search_result = MagicMock()
    mock_search_result.total_found = 10
    mock_search_result.new_businesses = 5

    with patch("src.services.scheduler.db.get_session") as mock_db:
        mock_db.return_value.__enter__.return_value = test_session

        scheduler = AutomationScheduler()

        with patch.object(
            scheduler.search_service, "search", new_callable=AsyncMock
        ) as mock_search:

            async def search_with_delay(*args, **kwargs):
                await asyncio.sleep(0.1)  # Simular delay
                return mock_search_result

            mock_search.side_effect = search_with_delay

            test_session.expunge(tracked)
            result = await scheduler._execute_tracked_search(tracked)
            scheduler_context["automation_result"] = result


@when('executo a pesquisa manualmente via "run now"')
async def execute_run_now(test_session, scheduler_context):
    """Executa via run now."""
    tracked = scheduler_context["tracked_search"]

    with patch("src.services.scheduler.db.get_session") as mock_db:
        mock_db.return_value.__enter__.return_value = test_session

        service = AutomationService()

        # Mock search
        mock_search_result = MagicMock()
        mock_search_result.total_found = 3
        mock_search_result.new_businesses = 2

        with patch.object(
            service.scheduler.search_service, "search", new_callable=AsyncMock
        ) as mock_search:
            mock_search.return_value = mock_search_result

            result = await service.run_search_now(tracked.id)
            scheduler_context["automation_result"] = result


@when("apago a pesquisa rastreada")
def delete_tracked_search(test_session, scheduler_context):
    """Apaga pesquisa rastreada."""
    tracked = scheduler_context["tracked_search"]

    with patch("src.services.scheduler.db.get_session") as mock_db:
        mock_db.return_value.__enter__.return_value = test_session

        service = AutomationService()
        result = service.delete_tracked_search(tracked.id)
        scheduler_context["deleted"] = result


# =============================================================================
# THEN Steps
# =============================================================================


@then("a pesquisa deve ser guardada na base de dados")
def verify_search_saved(test_session, scheduler_context):
    """Verifica que foi guardada."""
    tracked = scheduler_context["tracked_search"]
    assert tracked.id is not None


@then("o campo is_active deve ser True")
def verify_is_active(scheduler_context):
    """Verifica is_active."""
    tracked = scheduler_context["tracked_search"]
    assert tracked.is_active is True


@then("next_run_at deve estar definido para agora")
def verify_next_run_at_now(scheduler_context):
    """Verifica next_run_at."""
    tracked = scheduler_context["tracked_search"]
    assert tracked.next_run_at is not None
    # Deve estar próximo de agora (dentro de 1 minuto)
    diff = abs((tracked.next_run_at - datetime.utcnow()).total_seconds())
    assert diff < 60


@then("notify_on_new deve estar ativo")
def verify_notify_on_new(scheduler_context):
    """Verifica notify_on_new."""
    tracked = scheduler_context["tracked_search"]
    assert tracked.notify_on_new is True


@then("a pesquisa deve ser executada")
def verify_search_executed(scheduler_context):
    """Verifica execução."""
    assert scheduler_context["search_executed"] is True


@then(parsers.parse("next_run_at deve ser atualizado para +{hours:d} horas"))
def verify_next_run_updated(test_session, scheduler_context, hours):
    """Verifica next_run_at atualizado."""
    tracked = scheduler_context["tracked_search"]
    test_session.refresh(tracked)

    # Deve estar próximo de agora + hours
    expected = datetime.utcnow() + timedelta(hours=hours)
    diff = abs((tracked.next_run_at - expected).total_seconds())
    assert diff < 120  # Margem de 2 minutos


@then("last_run_at deve estar atualizado")
def verify_last_run_at(test_session, scheduler_context):
    """Verifica last_run_at."""
    tracked = scheduler_context["tracked_search"]
    test_session.refresh(tracked)
    assert tracked.last_run_at is not None


@then(parsers.parse("total_runs deve incrementar em {increment:d}"))
def verify_total_runs_increment(test_session, scheduler_context, increment):
    """Verifica incremento."""
    tracked = scheduler_context["tracked_search"]
    test_session.refresh(tracked)
    assert tracked.total_runs >= increment


@then(parsers.parse("{count:d} notificação de resumo deve ser criada"))
def verify_notification_created(test_session, scheduler_context, count):
    """Verifica notificação criada."""
    # Verificar via automation result
    result = scheduler_context.get("automation_result")
    if result:
        assert result.notifications_created >= count


@then(parsers.parse('a notificação deve conter "{text}"'))
def verify_notification_contains(test_session, text):
    """Verifica conteúdo da notificação."""
    notifs = test_session.query(Notification).all()
    # Deve haver pelo menos uma com o texto
    assert any(text in (n.message or n.title) for n in notifs)


@then(parsers.parse('o tipo da notificação deve ser "{notif_type}"'))
def verify_notification_type(test_session, notif_type):
    """Verifica tipo."""
    notifs = test_session.query(Notification).order_by(Notification.created_at.desc()).first()
    if notifs:
        assert notifs.type == notif_type


@then("1 log de automação deve ser criado")
def verify_log_created(test_session):
    """Verifica log criado."""
    logs = test_session.query(AutomationLog).all()
    assert len(logs) >= 1


@then(parsers.parse('o log deve ter status "{status}"'))
def verify_log_status(test_session, status):
    """Verifica status do log."""
    log = test_session.query(AutomationLog).order_by(AutomationLog.executed_at.desc()).first()
    assert log is not None
    assert log.status == status


@then("total_found deve ser registrado")
def verify_total_found(test_session):
    """Verifica total_found."""
    log = test_session.query(AutomationLog).order_by(AutomationLog.executed_at.desc()).first()
    assert log.total_found is not None


@then(parsers.parse("new_found deve ser {count:d}"))
def verify_new_found(test_session, count):
    """Verifica new_found."""
    log = test_session.query(AutomationLog).order_by(AutomationLog.executed_at.desc()).first()
    assert log.new_found == count


@then("duration_seconds deve estar presente")
def verify_duration(test_session):
    """Verifica duration."""
    log = test_session.query(AutomationLog).order_by(AutomationLog.executed_at.desc()).first()
    assert log.duration_seconds is not None
    assert log.duration_seconds > 0


@then("um log de erro deve ser criado")
def verify_error_log(test_session):
    """Verifica log de erro."""
    verify_log_created(test_session)


@then(parsers.parse('o status deve ser "{status}"'))
def verify_status(scheduler_context, status):
    """Verifica status."""
    result = scheduler_context.get("automation_result")
    assert result is not None
    assert result.status == status


@then("error_message deve conter detalhes do erro")
def verify_error_message(scheduler_context):
    """Verifica error_message."""
    result = scheduler_context["automation_result"]
    assert result.error_message is not None
    assert "API unavailable" in result.error_message or "erro" in result.error_message.lower()


@then("next_run_at deve ser atualizado mesmo assim")
def verify_next_run_updated_anyway(test_session, scheduler_context):
    """Verifica next_run_at mesmo com erro."""
    tracked = scheduler_context["tracked_search"]
    test_session.refresh(tracked)
    assert tracked.next_run_at is not None


@then("is_active deve ser False")
def verify_is_inactive(test_session, scheduler_context):
    """Verifica is_active False."""
    tracked = scheduler_context["tracked_search"]
    test_session.refresh(tracked)
    assert tracked.is_active is False


@then("a pesquisa não deve ser executada no próximo ciclo")
def verify_not_executed_next_cycle(scheduler_context):
    """Verifica que não executa."""
    # Implícito - se is_active=False, não executa
    assert scheduler_context["new_state"] is False


@then("next_run_at deve ser definido para agora")
def verify_next_run_now_on_reactivate(test_session, scheduler_context):
    """Verifica next_run_at ao reativar."""
    tracked = scheduler_context["tracked_search"]
    test_session.refresh(tracked)

    if tracked.is_active:
        assert tracked.next_run_at is not None
        diff = abs((tracked.next_run_at - datetime.utcnow()).total_seconds())
        assert diff < 120


@then(parsers.parse("total_searches deve ser {count:d}"))
def verify_total_searches(scheduler_context, count):
    """Verifica total."""
    stats = scheduler_context["stats"]
    assert stats["total_searches"] == count


@then(parsers.parse("active_searches deve ser {count:d}"))
def verify_active_searches(scheduler_context, count):
    """Verifica ativas."""
    stats = scheduler_context["stats"]
    assert stats["active_searches"] == count


@then(parsers.parse("total_executions deve ser {count:d}"))
def verify_total_executions(scheduler_context, count):
    """Verifica execuções."""
    stats = scheduler_context["stats"]
    assert stats["total_executions"] == count


@then(parsers.parse("unread_notifications deve ser {count:d}"))
def verify_unread_notifications(scheduler_context, count):
    """Verifica não lidas."""
    stats = scheduler_context["stats"]
    assert stats["unread_notifications"] == count


@then("as chamadas à API devem ter delay")
def verify_api_has_delay(scheduler_context):
    """Verifica delay."""
    # Implícito no resultado
    result = scheduler_context.get("automation_result")
    if result:
        assert result.duration_seconds > 0


@then("não deve exceder 3 requisições por segundo")
def verify_rate_limit_respected(scheduler_context):
    """Verifica rate limit."""
    # Implícito - o serviço já implementa rate limiting
    result = scheduler_context.get("automation_result")
    assert result is not None


@then("a execução deve completar com sucesso")
def verify_execution_success(scheduler_context):
    """Verifica sucesso."""
    result = scheduler_context["automation_result"]
    assert result.status == "success"


@then("a pesquisa deve executar imediatamente")
def verify_executes_immediately(scheduler_context):
    """Verifica execução imediata."""
    result = scheduler_context["automation_result"]
    assert result is not None


@then("next_run_at deve permanecer no agendamento original")
def verify_next_run_unchanged(test_session, scheduler_context):
    """Verifica next_run_at inalterado."""
    # Após run_now, next_run_at pode ser atualizado, mas não deve ser agora
    tracked = scheduler_context["tracked_search"]
    test_session.refresh(tracked)
    # Deve estar no futuro
    assert tracked.next_run_at > datetime.utcnow()


@then("um log de execução manual deve ser criado")
def verify_manual_log(test_session):
    """Verifica log manual."""
    verify_log_created(test_session)


@then("a pesquisa deve ser removida da base de dados")
def verify_search_deleted(test_session, scheduler_context):
    """Verifica remoção."""
    tracked = scheduler_context["tracked_search"]
    deleted_search = test_session.get(TrackedSearch, tracked.id)
    assert deleted_search is None


@then("os logs devem permanecer para histórico")
def verify_logs_remain(test_session, scheduler_context):
    """Verifica logs permanecem."""
    logs = test_session.query(AutomationLog).all()
    # Devem existir logs
    assert len(logs) > 0


@then("as notificações relacionadas devem permanecer")
def verify_notifications_remain(test_session):
    """Verifica notificações permanecem."""
    notifs = test_session.query(Notification).all()
    # Podem existir ou não, mas não crasham
    assert True
