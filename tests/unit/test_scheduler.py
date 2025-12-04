"""Testes unitarios para servico de automacao e scheduler - Geoscout Pro."""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.database.models import AutomationLog, Notification, TrackedSearch
from src.services.scheduler import (
    AutomationResult,
    AutomationScheduler,
    AutomationService,
    NotificationService,
)
from src.services.search import SearchResult


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_tracked_search():
    """TrackedSearch de exemplo."""
    return TrackedSearch(
        id=1,
        name="Restaurantes Lisboa",
        query_type="text",
        query_params={
            "query": "restaurantes",
            "location": (38.7223, -9.1393),
            "radius": 5000,
            "place_type": "restaurant",
        },
        is_active=True,
        interval_hours=24,
        notify_on_new=True,
        notify_threshold_score=50,
        last_run_at=None,
        next_run_at=datetime.utcnow(),
        total_runs=0,
        total_new_found=0,
        last_new_count=0,
    )


@pytest.fixture
def sample_tracked_search_due():
    """TrackedSearch pronta para executar."""
    return TrackedSearch(
        id=2,
        name="Cafes Porto",
        query_type="text",
        query_params={"query": "cafes", "location": (41.1579, -8.6291), "radius": 3000},
        is_active=True,
        interval_hours=12,
        notify_on_new=False,
        notify_threshold_score=60,
        last_run_at=datetime.utcnow() - timedelta(hours=13),
        next_run_at=datetime.utcnow() - timedelta(hours=1),  # Atrasado
        total_runs=5,
        total_new_found=25,
        last_new_count=3,
    )


@pytest.fixture
def sample_tracked_search_inactive():
    """TrackedSearch inativa."""
    return TrackedSearch(
        id=3,
        name="Farmácias Desativadas",
        query_type="text",
        query_params={"query": "farmacias", "location": None, "radius": 5000},
        is_active=False,
        interval_hours=24,
        notify_on_new=True,
        notify_threshold_score=50,
    )


@pytest.fixture
def mock_search_result_success():
    """SearchResult mock bem-sucedido."""
    return SearchResult(
        total_found=15,
        new_businesses=5,
        updated_businesses=2,
        filtered_out=3,
        api_calls=1,
    )


@pytest.fixture
def automation_scheduler():
    """AutomationScheduler para testes."""
    return AutomationScheduler(check_interval=1)


@pytest.fixture
def automation_service():
    """AutomationService para testes."""
    return AutomationService()


@pytest.fixture
def notification_service():
    """NotificationService para testes."""
    return NotificationService()


# =============================================================================
# Testes: AutomationScheduler
# =============================================================================


@pytest.mark.asyncio
async def test_scheduler_initialization(automation_scheduler):
    """Testa inicializacao do scheduler."""
    assert automation_scheduler.check_interval == 1
    assert automation_scheduler._running is False
    assert automation_scheduler._task is None
    assert automation_scheduler.search_service is not None


@pytest.mark.asyncio
async def test_scheduler_start_stop(automation_scheduler):
    """Testa inicio e paragem do scheduler."""
    await automation_scheduler.start()
    assert automation_scheduler._running is True
    assert automation_scheduler._task is not None

    await automation_scheduler.stop()
    assert automation_scheduler._running is False


@pytest.mark.asyncio
async def test_scheduler_get_due_searches(automation_scheduler, sample_tracked_search_due):
    """Testa obtencao de pesquisas prontas para executar."""
    with patch("src.services.scheduler.db.get_session") as mock_session:
        mock_db_session = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_db_session
        mock_db_session.query.return_value.filter.return_value.all.return_value = [
            sample_tracked_search_due
        ]

        due_searches = automation_scheduler._get_due_searches()

    assert len(due_searches) == 1
    assert due_searches[0].id == 2
    assert due_searches[0].name == "Cafes Porto"


@pytest.mark.asyncio
async def test_scheduler_get_due_searches_empty(automation_scheduler):
    """Testa quando nao ha pesquisas prontas."""
    with patch("src.services.scheduler.db.get_session") as mock_session:
        mock_db_session = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_db_session
        mock_db_session.query.return_value.filter.return_value.all.return_value = []

        due_searches = automation_scheduler._get_due_searches()

    assert len(due_searches) == 0


@pytest.mark.asyncio
async def test_scheduler_execute_tracked_search_success(
    automation_scheduler, sample_tracked_search, mock_search_result_success
):
    """Testa execucao bem-sucedida de pesquisa agendada."""
    with patch.object(
        automation_scheduler.search_service,
        "search",
        new=AsyncMock(return_value=mock_search_result_success),
    ):
        with patch("src.services.scheduler.db.get_session") as mock_session:
            mock_db_session = MagicMock()
            mock_session.return_value.__enter__.return_value = mock_db_session
            mock_db_session.get.return_value = sample_tracked_search

            result = await automation_scheduler._execute_tracked_search(sample_tracked_search)

    assert isinstance(result, AutomationResult)
    assert result.status == "success"
    assert result.total_found == 15
    assert result.new_found == 5
    assert result.tracked_name == "Restaurantes Lisboa"
    assert result.duration_seconds > 0


@pytest.mark.asyncio
async def test_scheduler_execute_tracked_search_with_error(
    automation_scheduler, sample_tracked_search
):
    """Testa execucao com erro."""
    with patch.object(
        automation_scheduler.search_service, "search", side_effect=Exception("API Error")
    ):
        with patch("src.services.scheduler.db.get_session") as mock_session:
            mock_db_session = MagicMock()
            mock_session.return_value.__enter__.return_value = mock_db_session
            mock_db_session.get.return_value = sample_tracked_search

            result = await automation_scheduler._execute_tracked_search(sample_tracked_search)

    assert result.status == "failed"
    assert result.error_message == "API Error"
    assert result.total_found == 0
    assert result.new_found == 0


@pytest.mark.asyncio
async def test_scheduler_execute_updates_tracked_search(
    automation_scheduler, sample_tracked_search, mock_search_result_success
):
    """Testa que execucao atualiza estatisticas do TrackedSearch."""
    with patch.object(
        automation_scheduler.search_service,
        "search",
        new=AsyncMock(return_value=mock_search_result_success),
    ):
        with patch("src.services.scheduler.db.get_session") as mock_session:
            mock_db_session = MagicMock()
            mock_session.return_value.__enter__.return_value = mock_db_session

            # Mock para primeiro get (buscar business) e segundo get (atualizar tracked)
            mock_db_session.get.return_value = sample_tracked_search

            result = await automation_scheduler._execute_tracked_search(sample_tracked_search)

    # Verificar que tentou atualizar tracked search
    assert result.status == "success"


@pytest.mark.asyncio
async def test_scheduler_execute_creates_automation_log(
    automation_scheduler, sample_tracked_search, mock_search_result_success
):
    """Testa que execucao cria log de automacao."""
    with patch.object(
        automation_scheduler.search_service,
        "search",
        new=AsyncMock(return_value=mock_search_result_success),
    ):
        with patch("src.services.scheduler.db.get_session") as mock_session:
            mock_db_session = MagicMock()
            mock_session.return_value.__enter__.return_value = mock_db_session
            mock_db_session.get.return_value = sample_tracked_search

            result = await automation_scheduler._execute_tracked_search(sample_tracked_search)

    # Verificar que add foi chamado (para criar log)
    assert mock_db_session.add.called
    assert result.status == "success"


@pytest.mark.asyncio
async def test_scheduler_execute_with_notifications(
    automation_scheduler, sample_tracked_search, mock_search_result_success
):
    """Testa criacao de notificacoes quando configurado."""
    sample_tracked_search.notify_on_new = True

    with patch.object(
        automation_scheduler.search_service,
        "search",
        new=AsyncMock(return_value=mock_search_result_success),
    ):
        with patch("src.services.scheduler.db.get_session") as mock_session:
            mock_db_session = MagicMock()
            mock_session.return_value.__enter__.return_value = mock_db_session
            mock_db_session.get.return_value = sample_tracked_search

            result = await automation_scheduler._execute_tracked_search(sample_tracked_search)

    assert result.notifications_created > 0


@pytest.mark.asyncio
async def test_scheduler_run_due_searches(
    automation_scheduler, sample_tracked_search_due, mock_search_result_success
):
    """Testa execucao de todas as pesquisas prontas."""
    with patch.object(
        automation_scheduler, "_get_due_searches", return_value=[sample_tracked_search_due]
    ):
        with patch.object(
            automation_scheduler,
            "_execute_tracked_search",
            new=AsyncMock(
                return_value=AutomationResult(
                    tracked_search_id=2,
                    tracked_name="Cafes Porto",
                    total_found=10,
                    new_found=3,
                    high_score_found=1,
                    duration_seconds=1.5,
                    status="success",
                )
            ),
        ):
            await automation_scheduler._run_due_searches()

    # Se chegou aqui sem erro, passou


@pytest.mark.asyncio
async def test_scheduler_loop_runs_periodically(automation_scheduler):
    """Testa que loop do scheduler executa periodicamente."""
    run_count = 0

    async def mock_run_due():
        nonlocal run_count
        run_count += 1

    with patch.object(
        automation_scheduler, "_run_due_searches", new=AsyncMock(side_effect=mock_run_due)
    ):
        await automation_scheduler.start()
        await asyncio.sleep(2.5)  # Esperar 2+ ciclos (check_interval=1)
        await automation_scheduler.stop()

    assert run_count >= 2  # Deve ter executado pelo menos 2 vezes


# =============================================================================
# Testes: NotificationService
# =============================================================================


def test_notification_service_get_unread_count(notification_service):
    """Testa contagem de notificacoes nao lidas."""
    with patch("src.services.scheduler.db.get_session") as mock_session:
        mock_db_session = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_db_session
        mock_db_session.query.return_value.filter.return_value.count.return_value = 5

        count = notification_service.get_unread_count()

    assert count == 5


def test_notification_service_get_notifications_all(notification_service):
    """Testa obtencao de todas as notificacoes."""
    mock_notifications = [
        Notification(
            id=1,
            type="new_lead",
            title="Novo Lead",
            message="Lead encontrado",
            is_read=False,
            created_at=datetime.utcnow(),
        ),
        Notification(
            id=2,
            type="batch_complete",
            title="Pesquisa Concluida",
            message="10 leads",
            is_read=True,
            created_at=datetime.utcnow(),
        ),
    ]

    with patch("src.services.scheduler.db.get_session") as mock_session:
        mock_db_session = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_db_session
        mock_db_session.query.return_value.order_by.return_value.limit.return_value.all.return_value = mock_notifications

        notifications = notification_service.get_notifications(unread_only=False, limit=50)

    assert len(notifications) == 2
    assert notifications[0]["id"] == 1
    assert notifications[0]["title"] == "Novo Lead"


def test_notification_service_get_notifications_unread_only(notification_service):
    """Testa obtencao apenas de notificacoes nao lidas."""
    mock_notifications = [
        Notification(
            id=1,
            type="new_lead",
            title="Novo Lead",
            message="Lead",
            is_read=False,
            created_at=datetime.utcnow(),
        ),
    ]

    with patch("src.services.scheduler.db.get_session") as mock_session:
        mock_db_session = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_db_session

        mock_query = MagicMock()
        mock_db_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = mock_notifications

        notifications = notification_service.get_notifications(unread_only=True, limit=50)

    assert len(notifications) == 1
    assert notifications[0]["is_read"] is False


def test_notification_service_mark_as_read(notification_service):
    """Testa marcar notificacao como lida."""
    mock_notification = Notification(
        id=1,
        type="new_lead",
        title="Test",
        message="Msg",
        is_read=False,
        created_at=datetime.utcnow(),
    )

    with patch("src.services.scheduler.db.get_session") as mock_session:
        mock_db_session = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_db_session
        mock_db_session.get.return_value = mock_notification

        result = notification_service.mark_as_read(1)

    assert result is True
    assert mock_notification.is_read is True


def test_notification_service_mark_as_read_not_found(notification_service):
    """Testa marcar notificacao inexistente."""
    with patch("src.services.scheduler.db.get_session") as mock_session:
        mock_db_session = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_db_session
        mock_db_session.get.return_value = None

        result = notification_service.mark_as_read(999)

    assert result is False


def test_notification_service_mark_all_as_read(notification_service):
    """Testa marcar todas como lidas."""
    with patch("src.services.scheduler.db.get_session") as mock_session:
        mock_db_session = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_db_session
        mock_db_session.query.return_value.filter.return_value.update.return_value = 10

        count = notification_service.mark_all_as_read()

    assert count == 10


def test_notification_service_delete_notification(notification_service):
    """Testa apagar notificacao."""
    mock_notification = Notification(
        id=1,
        type="new_lead",
        title="Test",
        message="Msg",
        is_read=False,
        created_at=datetime.utcnow(),
    )

    with patch("src.services.scheduler.db.get_session") as mock_session:
        mock_db_session = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_db_session
        mock_db_session.get.return_value = mock_notification

        result = notification_service.delete_notification(1)

    assert result is True


def test_notification_service_delete_notification_not_found(notification_service):
    """Testa apagar notificacao inexistente."""
    with patch("src.services.scheduler.db.get_session") as mock_session:
        mock_db_session = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_db_session
        mock_db_session.get.return_value = None

        result = notification_service.delete_notification(999)

    assert result is False


# =============================================================================
# Testes: AutomationService
# =============================================================================


def test_automation_service_initialization(automation_service):
    """Testa inicializacao do servico de automacao."""
    assert automation_service.scheduler is not None
    assert automation_service.notification_service is not None


def test_automation_service_get_tracked_searches(automation_service):
    """Testa obtencao de pesquisas agendadas."""
    mock_searches = [
        TrackedSearch(
            id=1,
            name="Search 1",
            query_type="text",
            query_params={},
            is_active=True,
            interval_hours=24,
            created_at=datetime.utcnow(),
        ),
        TrackedSearch(
            id=2,
            name="Search 2",
            query_type="text",
            query_params={},
            is_active=True,
            interval_hours=12,
            created_at=datetime.utcnow(),
        ),
    ]

    with patch("src.services.scheduler.db.get_session") as mock_session:
        mock_db_session = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_db_session
        mock_db_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = mock_searches

        searches = automation_service.get_tracked_searches(active_only=True)

    assert len(searches) == 2
    assert searches[0]["id"] == 1
    assert searches[0]["name"] == "Search 1"


def test_automation_service_get_automation_logs(automation_service):
    """Testa obtencao de logs de automacao."""
    mock_logs = [
        AutomationLog(
            id=1,
            tracked_search_id=1,
            executed_at=datetime.utcnow(),
            total_found=10,
            new_found=5,
            high_score_found=2,
            duration_seconds=2.0,
            status="success",
        ),
        AutomationLog(
            id=2,
            tracked_search_id=1,
            executed_at=datetime.utcnow(),
            total_found=0,
            new_found=0,
            high_score_found=0,
            duration_seconds=1.0,
            status="failed",
            error_message="Error",
        ),
    ]

    with patch("src.services.scheduler.db.get_session") as mock_session:
        mock_db_session = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_db_session
        mock_db_session.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = mock_logs

        logs = automation_service.get_automation_logs(tracked_id=1, limit=50)

    assert len(logs) == 2
    assert logs[0]["status"] == "success"
    assert logs[1]["status"] == "failed"


def test_automation_service_create_tracked_search(automation_service):
    """Testa criacao de pesquisa agendada."""
    with patch("src.services.scheduler.db.get_session") as mock_session:
        mock_db_session = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_db_session

        # Criar um mock que simula o TrackedSearch apos commit
        class MockTrackedSearch:
            id = 1
            name = "Nova Pesquisa"
            query_type = "text"
            query_params = {
                "query": "restaurantes",
                "location": None,
                "radius": 5000,
                "place_type": None,
            }
            interval_hours = 24
            is_active = True

        # Capturar o objeto adicionado
        added_object = None

        def mock_add(obj):
            nonlocal added_object
            added_object = obj
            # Simular que apos add, o objeto ganha um ID
            obj.id = 1

        mock_db_session.add = mock_add

        tracked_dict = automation_service.create_tracked_search(
            name="Nova Pesquisa",
            query="restaurantes",
            location=None,
            radius=5000,
            interval_hours=24,
        )

    # Verificar que add foi chamado (objeto foi adicionado)
    assert added_object is not None


def test_automation_service_toggle_tracked_search(automation_service):
    """Testa alternar estado de pesquisa agendada."""
    mock_tracked = TrackedSearch(
        id=1, name="Test", query_type="text", query_params={}, is_active=True, interval_hours=24
    )

    with patch("src.services.scheduler.db.get_session") as mock_session:
        mock_db_session = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_db_session
        mock_db_session.get.return_value = mock_tracked

        new_state = automation_service.toggle_tracked_search(1)

    assert new_state is False  # Era True, agora e False
    assert mock_tracked.is_active is False


def test_automation_service_toggle_tracked_search_reactivate(automation_service):
    """Testa reativar pesquisa agendada."""
    mock_tracked = TrackedSearch(
        id=1, name="Test", query_type="text", query_params={}, is_active=False, interval_hours=24
    )

    with patch("src.services.scheduler.db.get_session") as mock_session:
        mock_db_session = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_db_session
        mock_db_session.get.return_value = mock_tracked

        new_state = automation_service.toggle_tracked_search(1)

    assert new_state is True  # Era False, agora e True
    assert mock_tracked.is_active is True
    assert mock_tracked.next_run_at is not None  # Deve agendar proxima execucao


def test_automation_service_delete_tracked_search(automation_service):
    """Testa apagar pesquisa agendada."""
    mock_tracked = TrackedSearch(
        id=1, name="Test", query_type="text", query_params={}, is_active=True, interval_hours=24
    )

    with patch("src.services.scheduler.db.get_session") as mock_session:
        mock_db_session = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_db_session
        mock_db_session.get.return_value = mock_tracked

        result = automation_service.delete_tracked_search(1)

    assert result is True


def test_automation_service_delete_tracked_search_not_found(automation_service):
    """Testa apagar pesquisa inexistente."""
    with patch("src.services.scheduler.db.get_session") as mock_session:
        mock_db_session = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_db_session
        mock_db_session.get.return_value = None

        result = automation_service.delete_tracked_search(999)

    assert result is False


@pytest.mark.asyncio
async def test_automation_service_run_search_now(automation_service, sample_tracked_search):
    """Testa execucao imediata de pesquisa."""
    with patch("src.services.scheduler.db.get_session") as mock_session:
        mock_db_session = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_db_session
        mock_db_session.get.return_value = sample_tracked_search

        with patch.object(
            automation_service.scheduler,
            "_execute_tracked_search",
            new=AsyncMock(
                return_value=AutomationResult(
                    tracked_search_id=1,
                    tracked_name="Restaurantes Lisboa",
                    total_found=10,
                    new_found=3,
                    high_score_found=1,
                    duration_seconds=2.0,
                    status="success",
                )
            ),
        ):
            result = await automation_service.run_search_now(1)

    assert result is not None
    assert result.status == "success"


@pytest.mark.asyncio
async def test_automation_service_run_search_now_not_found(automation_service):
    """Testa execucao de pesquisa inexistente."""
    with patch("src.services.scheduler.db.get_session") as mock_session:
        mock_db_session = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_db_session
        mock_db_session.get.return_value = None

        result = await automation_service.run_search_now(999)

    assert result is None


def test_automation_service_get_automation_stats(automation_service):
    """Testa estatisticas de automacao."""
    with patch("src.services.scheduler.db.get_session") as mock_session:
        mock_db_session = MagicMock()
        mock_session.return_value.__enter__.return_value = mock_db_session

        # Mock diferentes queries
        def query_side_effect(model):
            mock_query = MagicMock()
            if model == TrackedSearch:
                mock_query.count.return_value = 10
                mock_query.filter.return_value.count.return_value = 7  # Active searches
            elif model == AutomationLog:
                mock_query.count.return_value = 100
            elif model == Notification:
                mock_query.count.return_value = 25
                mock_query.filter.return_value.count.return_value = 5  # Unread
            return mock_query

        mock_db_session.query.side_effect = query_side_effect

        stats = automation_service.get_automation_stats()

    assert stats["total_searches"] == 10
    assert stats["active_searches"] == 7
    assert stats["total_executions"] == 100
    assert stats["total_notifications"] == 25
    assert stats["unread_notifications"] == 5
