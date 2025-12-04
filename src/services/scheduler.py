"""Servico de agendamento e automacao de pesquisas."""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from src.database.db import db
from src.database.models import AutomationLog, Notification, TrackedSearch
from src.services.search import SearchService


@dataclass
class AutomationResult:
    """Resultado de uma execucao automatica."""

    tracked_search_id: int
    tracked_name: str
    total_found: int
    new_found: int
    high_score_found: int
    duration_seconds: float
    status: str
    error_message: str | None = None
    notifications_created: int = 0


class AutomationScheduler:
    """Scheduler de tarefas automaticas em background."""

    def __init__(self, check_interval: int = 60):
        """
        Inicializa o scheduler.

        Args:
            check_interval: Intervalo em segundos entre verificacoes
        """
        self.check_interval = check_interval
        self._running = False
        self._task: asyncio.Task | None = None
        self.search_service = SearchService()

    async def start(self):
        """Inicia o scheduler em background."""
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._scheduler_loop())
        print("[Scheduler] Iniciado")

    async def stop(self):
        """Para o scheduler graciosamente."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        print("[Scheduler] Parado")

    async def _scheduler_loop(self):
        """Loop principal do scheduler."""
        while self._running:
            try:
                await self._run_due_searches()
            except Exception as e:
                print(f"[Scheduler] Erro no loop: {e}")

            await asyncio.sleep(self.check_interval)

    async def _run_due_searches(self):
        """Executa todas as pesquisas que estao prontas."""
        due_searches = self._get_due_searches()

        for tracked in due_searches:
            try:
                result = await self._execute_tracked_search(tracked)
                print(f"[Scheduler] Executado '{tracked.name}': {result.new_found} novos")
            except Exception as e:
                print(f"[Scheduler] Erro ao executar '{tracked.name}': {e}")

    def _get_due_searches(self) -> list[TrackedSearch]:
        """Retorna pesquisas prontas para executar."""
        with db.get_session() as session:
            now = datetime.utcnow()
            searches = (
                session.query(TrackedSearch)
                .filter(
                    TrackedSearch.is_active == True,  # noqa: E712
                    (TrackedSearch.next_run_at <= now) | (TrackedSearch.next_run_at.is_(None)),
                )
                .all()
            )
            # Expunge para usar fora da sessao
            for s in searches:
                session.expunge(s)
            return searches

    async def _execute_tracked_search(self, tracked: TrackedSearch) -> AutomationResult:
        """
        Executa uma pesquisa agendada com logging e notificacoes.

        Args:
            tracked: TrackedSearch a executar

        Returns:
            AutomationResult com detalhes da execucao
        """
        start_time = datetime.utcnow()
        params = tracked.query_params or {}

        # Guardar valores antes de fechar sessao
        tracked_id = tracked.id
        tracked_name = tracked.name
        notify_on_new = tracked.notify_on_new
        notify_threshold = tracked.notify_threshold_score

        try:
            # Executar pesquisa
            result = await self.search_service.search(
                query=params.get("query", ""),
                location=params.get("location"),
                radius=params.get("radius", 5000),
                place_type=params.get("place_type"),
            )

            duration = (datetime.utcnow() - start_time).total_seconds()

            # Contar leads de alto score
            high_score_count = self._count_high_score_leads(
                result.new_businesses,
                notify_threshold,
            )

            # Criar log
            with db.get_session() as session:
                log = AutomationLog(
                    tracked_search_id=tracked_id,
                    executed_at=start_time,
                    total_found=result.total_found,
                    new_found=result.new_businesses,
                    high_score_found=high_score_count,
                    duration_seconds=duration,
                    status="success",
                )
                session.add(log)

                # Atualizar estatisticas do TrackedSearch
                ts = session.get(TrackedSearch, tracked_id)
                if ts:
                    ts.last_run_at = start_time
                    ts.next_run_at = start_time + timedelta(hours=ts.interval_hours)
                    ts.total_runs = (ts.total_runs or 0) + 1
                    ts.total_new_found = (ts.total_new_found or 0) + result.new_businesses
                    ts.last_new_count = result.new_businesses

                session.commit()

            # Criar notificacoes se configurado
            notifications_created = 0
            if notify_on_new and result.new_businesses > 0:
                notifications_created = self._create_notifications(
                    tracked_id,
                    tracked_name,
                    result.new_businesses,
                    high_score_count,
                    notify_threshold,
                )

            return AutomationResult(
                tracked_search_id=tracked_id,
                tracked_name=tracked_name,
                total_found=result.total_found,
                new_found=result.new_businesses,
                high_score_found=high_score_count,
                duration_seconds=duration,
                status="success",
                notifications_created=notifications_created,
            )

        except Exception as e:
            duration = (datetime.utcnow() - start_time).total_seconds()

            # Criar log de erro
            with db.get_session() as session:
                log = AutomationLog(
                    tracked_search_id=tracked_id,
                    executed_at=start_time,
                    duration_seconds=duration,
                    status="failed",
                    error_message=str(e),
                )
                session.add(log)

                # Atualizar next_run mesmo em caso de erro
                ts = session.get(TrackedSearch, tracked_id)
                if ts:
                    ts.last_run_at = start_time
                    ts.next_run_at = start_time + timedelta(hours=ts.interval_hours)

                session.commit()

            return AutomationResult(
                tracked_search_id=tracked_id,
                tracked_name=tracked_name,
                total_found=0,
                new_found=0,
                high_score_found=0,
                duration_seconds=duration,
                status="failed",
                error_message=str(e),
            )

    def _count_high_score_leads(self, new_count: int, threshold: int) -> int:
        """
        Conta quantos dos novos leads tem score alto.

        Nota: Simplificado - retorna estimativa baseada no threshold.
        Para contagem exata, seria necessario passar a lista de IDs.
        """
        # TODO: Implementar contagem exata se necessario
        return 0

    def _create_notifications(
        self,
        tracked_id: int,
        tracked_name: str,
        new_count: int,
        high_score_count: int,
        threshold: int,
    ) -> int:
        """
        Cria notificacoes para novos leads.

        Args:
            tracked_id: ID da pesquisa agendada
            tracked_name: Nome da pesquisa
            new_count: Total de novos leads
            high_score_count: Leads com score alto
            threshold: Score minimo para notificacao

        Returns:
            Numero de notificacoes criadas
        """
        with db.get_session() as session:
            # Notificacao de resumo
            notification = Notification(
                type="batch_complete",
                title=f"Pesquisa '{tracked_name}' concluida",
                message=f"Encontrados {new_count} novos leads.",
                tracked_search_id=tracked_id,
            )
            session.add(notification)
            session.commit()
            return 1


class NotificationService:
    """Servico para gestao de notificacoes."""

    def get_unread_count(self) -> int:
        """Retorna contagem de notificacoes nao lidas."""
        with db.get_session() as session:
            return (
                session.query(Notification)
                .filter(Notification.is_read == False)  # noqa: E712
                .count()
            )

    def get_notifications(
        self,
        unread_only: bool = False,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """
        Retorna lista de notificacoes.

        Args:
            unread_only: Apenas nao lidas
            limit: Maximo de resultados

        Returns:
            Lista de notificacoes como dicts
        """
        with db.get_session() as session:
            query = session.query(Notification)

            if unread_only:
                query = query.filter(Notification.is_read == False)  # noqa: E712

            notifications = query.order_by(Notification.created_at.desc()).limit(limit).all()

            return [
                {
                    "id": n.id,
                    "type": n.type,
                    "title": n.title,
                    "message": n.message,
                    "business_id": n.business_id,
                    "tracked_search_id": n.tracked_search_id,
                    "is_read": n.is_read,
                    "created_at": n.created_at,
                }
                for n in notifications
            ]

    def mark_as_read(self, notification_id: int) -> bool:
        """
        Marca notificacao como lida.

        Args:
            notification_id: ID da notificacao

        Returns:
            True se atualizada, False se nao encontrada
        """
        with db.get_session() as session:
            notification = session.get(Notification, notification_id)
            if notification:
                notification.is_read = True
                session.commit()
                return True
            return False

    def mark_all_as_read(self) -> int:
        """
        Marca todas as notificacoes como lidas.

        Returns:
            Numero de notificacoes atualizadas
        """
        with db.get_session() as session:
            count = (
                session.query(Notification)
                .filter(Notification.is_read == False)  # noqa: E712
                .update({"is_read": True})
            )
            session.commit()
            return count

    def delete_notification(self, notification_id: int) -> bool:
        """
        Apaga uma notificacao.

        Args:
            notification_id: ID da notificacao

        Returns:
            True se apagada, False se nao encontrada
        """
        with db.get_session() as session:
            notification = session.get(Notification, notification_id)
            if notification:
                session.delete(notification)
                session.commit()
                return True
            return False


class AutomationService:
    """Servico principal de automacao."""

    def __init__(self):
        """Inicializa o servico."""
        self.scheduler = AutomationScheduler()
        self.notification_service = NotificationService()

    def get_tracked_searches(self, active_only: bool = True) -> list[dict[str, Any]]:
        """
        Retorna pesquisas agendadas com estatisticas.

        Args:
            active_only: Apenas ativas

        Returns:
            Lista de TrackedSearch como dicts
        """
        with db.get_session() as session:
            query = session.query(TrackedSearch)
            if active_only:
                query = query.filter(TrackedSearch.is_active == True)  # noqa: E712

            searches = query.order_by(TrackedSearch.created_at.desc()).all()

            return [
                {
                    "id": s.id,
                    "name": s.name,
                    "query_params": s.query_params,
                    "is_active": s.is_active,
                    "interval_hours": s.interval_hours,
                    "last_run_at": s.last_run_at,
                    "next_run_at": s.next_run_at,
                    "notify_on_new": s.notify_on_new,
                    "notify_threshold_score": s.notify_threshold_score,
                    "total_runs": s.total_runs or 0,
                    "total_new_found": s.total_new_found or 0,
                    "last_new_count": s.last_new_count or 0,
                    "created_at": s.created_at,
                }
                for s in searches
            ]

    def get_automation_logs(
        self,
        tracked_id: int | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """
        Retorna logs de automacao.

        Args:
            tracked_id: Filtrar por pesquisa (opcional)
            limit: Maximo de resultados

        Returns:
            Lista de AutomationLog como dicts
        """
        with db.get_session() as session:
            query = session.query(AutomationLog)

            if tracked_id:
                query = query.filter(AutomationLog.tracked_search_id == tracked_id)

            logs = query.order_by(AutomationLog.executed_at.desc()).limit(limit).all()

            return [
                {
                    "id": log.id,
                    "tracked_search_id": log.tracked_search_id,
                    "executed_at": log.executed_at,
                    "total_found": log.total_found,
                    "new_found": log.new_found,
                    "high_score_found": log.high_score_found,
                    "duration_seconds": log.duration_seconds,
                    "status": log.status,
                    "error_message": log.error_message,
                }
                for log in logs
            ]

    def create_tracked_search(
        self,
        name: str,
        query: str,
        location: str | None = None,
        radius: int = 5000,
        place_type: str | None = None,
        interval_hours: int = 24,
        notify_on_new: bool = True,
        notify_threshold_score: int = 50,
    ) -> dict[str, Any]:
        """
        Cria uma nova pesquisa agendada.

        Returns:
            TrackedSearch criada como dict
        """
        # Parse location se fornecido
        loc_tuple = None
        if location:
            try:
                parts = location.split(",")
                loc_tuple = (float(parts[0].strip()), float(parts[1].strip()))
            except (ValueError, IndexError):
                pass

        with db.get_session() as session:
            tracked = TrackedSearch(
                name=name,
                query_type="text",
                query_params={
                    "query": query,
                    "location": loc_tuple,
                    "radius": radius,
                    "place_type": place_type,
                },
                interval_hours=interval_hours,
                next_run_at=datetime.utcnow(),  # Executar imediatamente
                notify_on_new=notify_on_new,
                notify_threshold_score=notify_threshold_score,
            )
            session.add(tracked)
            session.commit()

            return {
                "id": tracked.id,
                "name": tracked.name,
                "query_params": tracked.query_params,
                "interval_hours": tracked.interval_hours,
                "is_active": tracked.is_active,
            }

    def toggle_tracked_search(self, tracked_id: int) -> bool:
        """
        Alterna estado ativo/inativo de uma pesquisa.

        Returns:
            Novo estado (True=ativo, False=inativo)
        """
        with db.get_session() as session:
            tracked = session.get(TrackedSearch, tracked_id)
            if tracked:
                tracked.is_active = not tracked.is_active
                if tracked.is_active:
                    # Reativar: agendar proxima execucao
                    tracked.next_run_at = datetime.utcnow()
                session.commit()
                return tracked.is_active
            return False

    def delete_tracked_search(self, tracked_id: int) -> bool:
        """
        Apaga uma pesquisa agendada.

        Returns:
            True se apagada
        """
        with db.get_session() as session:
            tracked = session.get(TrackedSearch, tracked_id)
            if tracked:
                session.delete(tracked)
                session.commit()
                return True
            return False

    async def run_search_now(self, tracked_id: int) -> AutomationResult | None:
        """
        Executa uma pesquisa agendada imediatamente.

        Returns:
            AutomationResult ou None se nao encontrada
        """
        with db.get_session() as session:
            tracked = session.get(TrackedSearch, tracked_id)
            if not tracked:
                return None
            session.expunge(tracked)

        return await self.scheduler._execute_tracked_search(tracked)

    def get_automation_stats(self) -> dict[str, Any]:
        """
        Retorna estatisticas gerais de automacao.

        Returns:
            Dict com estatisticas
        """
        with db.get_session() as session:
            total_searches = session.query(TrackedSearch).count()
            active_searches = (
                session.query(TrackedSearch)
                .filter(TrackedSearch.is_active == True)  # noqa: E712
                .count()
            )
            total_logs = session.query(AutomationLog).count()
            total_notifications = session.query(Notification).count()
            unread_notifications = (
                session.query(Notification)
                .filter(Notification.is_read == False)  # noqa: E712
                .count()
            )

            return {
                "total_searches": total_searches,
                "active_searches": active_searches,
                "total_executions": total_logs,
                "total_notifications": total_notifications,
                "unread_notifications": unread_notifications,
            }
