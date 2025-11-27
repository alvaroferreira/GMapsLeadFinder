"""Servidor FastAPI para interface web."""

import asyncio
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from src.config import settings
from src.database.db import db
from src.database.models import LEAD_STATUSES, ENRICHMENT_STATUSES
from src.database.queries import BusinessQueries, SearchHistoryQueries
from src.services.enricher import EnrichmentService
from src.services.exporter import ExportService
from src.services.notion import NotionService
from src.services.scheduler import AutomationService, AutomationScheduler, NotificationService
from src.services.scorer import LeadScorer
from src.services.search import SearchService
from src.services.tracker import TrackerService

# Setup
app = FastAPI(
    title="Lead Finder",
    description="Google Maps Lead Finder - Interface Web",
    version="1.0.0",
)

# Templates
TEMPLATE_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

# Inicializar DB
settings.ensure_directories()
db.create_tables()


# ============ HEALTH CHECK ============

@app.get("/health")
async def health_check():
    """Health check endpoint para Railway/Docker."""
    return {"status": "healthy", "version": "1.0.0"}


# ============ PAGINAS ============

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Pagina inicial com dashboard."""
    with db.get_session() as session:
        stats = BusinessQueries.get_stats(session)
        recent_searches = SearchHistoryQueries.get_recent(session, limit=5)

        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "stats": stats,
                "recent_searches": recent_searches,
                "has_api_key": settings.has_api_key,
            },
        )


@app.get("/help", response_class=HTMLResponse)
async def help_page(request: Request):
    """Pagina de ajuda e tutorial."""
    return templates.TemplateResponse("help.html", {"request": request})


@app.get("/search", response_class=HTMLResponse)
async def search_page(request: Request):
    """Pagina de pesquisa."""
    return templates.TemplateResponse(
        "search.html",
        {
            "request": request,
            "has_api_key": settings.has_api_key,
        },
    )


@app.post("/search", response_class=HTMLResponse)
async def do_search(
    request: Request,
    query: str = Form(...),
    location: str = Form(""),
    radius: str = Form("5000"),
    place_type: str = Form(""),
    max_reviews: str = Form(""),
    has_website: str = Form(""),
    max_results: str = Form("60"),
):
    """Executa pesquisa."""
    if not settings.has_api_key:
        return templates.TemplateResponse(
            "partials/error.html",
            {"request": request, "message": "API key nao configurada"},
        )

    # Parse valores numericos
    radius_int = int(radius) if radius else 5000
    max_reviews_int = int(max_reviews) if max_reviews else None
    max_results_int = int(max_results) if max_results else 60

    # Parse location
    loc_tuple = None
    if location and "," in location:
        try:
            parts = location.split(",")
            loc_tuple = (float(parts[0].strip()), float(parts[1].strip()))
        except ValueError:
            pass

    # Parse has_website
    website_filter = None
    if has_website == "yes":
        website_filter = True
    elif has_website == "no":
        website_filter = False

    service = SearchService()

    try:
        result = await service.search(
            query=query,
            location=loc_tuple,
            radius=radius_int,
            place_type=place_type or None,
            max_results=max_results_int,
            max_reviews=max_reviews_int,
            has_website=website_filter,
        )

        return templates.TemplateResponse(
            "partials/search_result.html",
            {
                "request": request,
                "result": result,
                "query": query,
            },
        )
    except Exception as e:
        return templates.TemplateResponse(
            "partials/error.html",
            {"request": request, "message": str(e)},
        )


@app.get("/leads", response_class=HTMLResponse)
async def leads_page(
    request: Request,
    status: str = Query(None),
    min_score: int = Query(None),
    has_website: str = Query(None),
    this_week: str = Query(None),
    page: int = Query(1),
):
    """Pagina de listagem de leads."""
    limit = 20
    offset = (page - 1) * limit

    website_filter = None
    if has_website == "yes":
        website_filter = True
    elif has_website == "no":
        website_filter = False

    # Filtro de "descobertos esta semana"
    first_seen_since = None
    if this_week == "yes":
        first_seen_since = datetime.now() - timedelta(days=7)

    with db.get_session() as session:
        businesses_db = BusinessQueries.get_all(
            session,
            status=status or None,
            min_score=min_score,
            has_website=website_filter,
            first_seen_since=first_seen_since,
            limit=limit,
            offset=offset,
        )
        total = BusinessQueries.count(
            session,
            status=status or None,
            first_seen_since=first_seen_since,
        )

        # Converter para dicts dentro da sessao
        businesses = []
        for b in businesses_db:
            businesses.append({
                "id": b.id,
                "name": b.name,
                "formatted_address": b.formatted_address,
                "rating": b.rating,
                "review_count": b.review_count,
                "has_website": b.has_website,
                "lead_score": b.lead_score,
                "lead_status": b.lead_status,
                "google_maps_url": b.google_maps_url,
                "notion_synced_at": b.notion_synced_at,
            })

    total_pages = (total + limit - 1) // limit

    # Verificar se Notion esta configurado
    notion = NotionService()
    notion_config = notion.get_config()
    notion_active = notion_config.get("is_active", False) if notion_config else False

    return templates.TemplateResponse(
        "leads.html",
        {
            "request": request,
            "businesses": businesses,
            "statuses": LEAD_STATUSES,
            "notion_active": notion_active,
            "current_status": status,
            "current_min_score": min_score,
            "current_has_website": has_website,
            "page": page,
            "total_pages": total_pages,
            "total": total,
        },
    )


@app.get("/leads/{place_id}", response_class=HTMLResponse)
async def lead_detail(request: Request, place_id: str):
    """Detalhes de um lead."""
    with db.get_session() as session:
        business = BusinessQueries.get_by_id(session, place_id)
        if not business:
            return templates.TemplateResponse(
                "partials/error.html",
                {"request": request, "message": "Lead nao encontrado"},
            )

        scorer = LeadScorer()
        score_explanation = scorer.explain(business)

        # Check Notion integration status
        notion_active = False
        try:
            from src.database.models import IntegrationConfig
            notion_config = session.query(IntegrationConfig).filter_by(service="notion").first()
            notion_active = notion_config and notion_config.is_active
        except Exception:
            pass

        return templates.TemplateResponse(
            "lead_detail.html",
            {
                "request": request,
                "business": business,
                "score_explanation": score_explanation,
                "statuses": LEAD_STATUSES,
                "notion_active": notion_active,
            },
        )


@app.post("/leads/{place_id}/update", response_class=HTMLResponse)
async def update_lead(
    request: Request,
    place_id: str,
    status: str = Form(None),
    notes: str = Form(None),
):
    """Atualiza status/notas de um lead."""
    with db.get_session() as session:
        business = BusinessQueries.get_by_id(session, place_id)
        if not business:
            return templates.TemplateResponse(
                "partials/error.html",
                {"request": request, "message": "Lead nao encontrado"},
            )

        if status:
            business.lead_status = status
        if notes:
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
            existing = business.notes or ""
            business.notes = f"{existing}\n[{timestamp}] {notes}".strip()

    return RedirectResponse(url=f"/leads/{place_id}", status_code=303)


@app.get("/export", response_class=HTMLResponse)
async def export_page(request: Request):
    """Pagina de exportacao."""
    with db.get_session() as session:
        total = BusinessQueries.count(session)

    return templates.TemplateResponse(
        "export.html",
        {
            "request": request,
            "total": total,
            "formats": ExportService.get_supported_formats(),
            "statuses": LEAD_STATUSES,
        },
    )


@app.post("/export/download")
async def do_export(
    format: str = Form("csv"),
    status: str = Form(None),
    min_score: int = Form(None),
):
    """Executa exportacao e retorna ficheiro."""
    from fastapi.responses import FileResponse

    exporter = ExportService()

    with db.get_session() as session:
        businesses = BusinessQueries.get_all(
            session,
            status=status or None,
            min_score=min_score,
            limit=10000,
        )

    if not businesses:
        return {"error": "Nenhum lead para exportar"}

    if format == "csv":
        path = exporter.export_csv(businesses)
    elif format == "xlsx":
        path = exporter.export_excel(businesses)
    elif format == "json":
        path = exporter.export_json(businesses)
    else:
        path = exporter.export_crm(businesses, format)

    return FileResponse(
        path,
        filename=path.name,
        media_type="application/octet-stream",
    )


@app.get("/stats", response_class=HTMLResponse)
async def stats_page(request: Request):
    """Pagina de estatisticas."""
    with db.get_session() as session:
        stats = BusinessQueries.get_stats(session)
        search_stats = SearchHistoryQueries.get_stats(session)

    return templates.TemplateResponse(
        "stats.html",
        {
            "request": request,
            "stats": stats,
            "search_stats": search_stats,
        },
    )


# ============ ENRICHMENT ============

@app.get("/enrichment", response_class=HTMLResponse)
async def enrichment_page(request: Request):
    """Pagina de enriquecimento de dados."""
    enricher = EnrichmentService()
    stats = enricher.get_enrichment_stats()
    enrichable = enricher.get_enrichable_leads(limit=50)

    return templates.TemplateResponse(
        "enrichment.html",
        {
            "request": request,
            "stats": stats,
            "enrichable_leads": enrichable,
            "statuses": ENRICHMENT_STATUSES,
        },
    )


@app.post("/enrichment/enrich/{place_id}", response_class=HTMLResponse)
async def enrich_single(request: Request, place_id: str):
    """Enriquecer um lead especifico."""
    enricher = EnrichmentService()
    result = await enricher.enrich_business(place_id)

    return templates.TemplateResponse(
        "partials/enrichment_result.html",
        {
            "request": request,
            "result": result,
            "place_id": place_id,
        },
    )


@app.post("/enrichment/enrich-batch", response_class=HTMLResponse)
async def enrich_batch(
    request: Request,
    place_ids: str = Form(""),
    enrich_all: bool = Form(False),
    limit: int = Form(10),
):
    """Enriquecer multiplos leads."""
    enricher = EnrichmentService()

    if enrich_all:
        leads = enricher.get_enrichable_leads(limit=limit)
        ids_to_enrich = [lead.id for lead in leads]
    else:
        ids_to_enrich = [pid.strip() for pid in place_ids.split(",") if pid.strip()]

    if not ids_to_enrich:
        return templates.TemplateResponse(
            "partials/error.html",
            {"request": request, "message": "Nenhum lead selecionado"},
        )

    results = await enricher.enrich_batch(ids_to_enrich, concurrency=3)

    success_count = sum(1 for r in results.values() if r.success)
    failed_count = len(results) - success_count

    return templates.TemplateResponse(
        "partials/enrichment_batch_result.html",
        {
            "request": request,
            "total": len(results),
            "success_count": success_count,
            "failed_count": failed_count,
            "results": results,
        },
    )


@app.get("/api/enrichment/stats")
async def api_enrichment_stats() -> dict:
    """API: Estatisticas de enriquecimento."""
    enricher = EnrichmentService()
    return enricher.get_enrichment_stats()


# ============ AUTOMATION ============

# Instancia global do scheduler
scheduler = AutomationScheduler(check_interval=60)


@app.on_event("startup")
async def startup_event():
    """Inicia o scheduler no startup do servidor."""
    await scheduler.start()


@app.on_event("shutdown")
async def shutdown_event():
    """Para o scheduler no shutdown do servidor."""
    await scheduler.stop()


@app.get("/automation", response_class=HTMLResponse)
async def automation_page(request: Request):
    """Pagina de automacao e pesquisas agendadas."""
    automation = AutomationService()
    searches = automation.get_tracked_searches(active_only=False)
    stats = automation.get_automation_stats()
    logs = automation.get_automation_logs(limit=10)

    # Converter dicts para objetos para compatibilidade com templates
    class DictObj:
        def __init__(self, data):
            for key, value in data.items():
                setattr(self, key, value)

    searches_obj = [DictObj(s) for s in searches]
    logs_obj = [DictObj(l) for l in logs]

    return templates.TemplateResponse(
        "automation.html",
        {
            "request": request,
            "searches": searches_obj,
            "stats": stats,
            "recent_logs": logs_obj,
        },
    )


@app.post("/automation/create", response_class=HTMLResponse)
async def create_tracked_search(
    request: Request,
    name: str = Form(...),
    query: str = Form(...),
    location: str = Form(""),
    radius: int = Form(5000),
    place_type: str = Form(""),
    interval_hours: int = Form(24),
    notify_on_new: bool = Form(True),
    notify_threshold_score: int = Form(50),
):
    """Cria uma nova pesquisa agendada."""
    automation = AutomationService()
    automation.create_tracked_search(
        name=name,
        query=query,
        location=location or None,
        radius=radius,
        place_type=place_type or None,
        interval_hours=interval_hours,
        notify_on_new=notify_on_new,
        notify_threshold_score=notify_threshold_score,
    )
    return RedirectResponse(url="/automation", status_code=303)


@app.post("/automation/{tracked_id}/toggle")
async def toggle_tracked_search(tracked_id: int):
    """Alterna estado ativo/inativo de uma pesquisa."""
    automation = AutomationService()
    new_state = automation.toggle_tracked_search(tracked_id)
    return {"is_active": new_state}


@app.post("/automation/{tracked_id}/delete")
async def delete_tracked_search(tracked_id: int):
    """Apaga uma pesquisa agendada."""
    automation = AutomationService()
    automation.delete_tracked_search(tracked_id)
    return RedirectResponse(url="/automation", status_code=303)


@app.post("/automation/{tracked_id}/run-now", response_class=HTMLResponse)
async def run_tracked_search_now(request: Request, tracked_id: int):
    """Executa uma pesquisa agendada imediatamente."""
    automation = AutomationService()
    result = await automation.run_search_now(tracked_id)

    if result:
        return templates.TemplateResponse(
            "partials/automation_result.html",
            {
                "request": request,
                "result": result,
            },
        )
    return templates.TemplateResponse(
        "partials/error.html",
        {"request": request, "message": "Pesquisa nao encontrada"},
    )


@app.get("/automation/logs/{tracked_id}", response_class=HTMLResponse)
async def automation_logs_page(request: Request, tracked_id: int):
    """Pagina de logs de uma pesquisa especifica."""
    automation = AutomationService()
    logs = automation.get_automation_logs(tracked_id=tracked_id, limit=50)
    searches = automation.get_tracked_searches(active_only=False)

    # Encontrar a pesquisa especifica
    search = next((s for s in searches if s["id"] == tracked_id), None)

    if not search:
        return templates.TemplateResponse(
            "partials/error.html",
            {"request": request, "message": "Pesquisa nao encontrada"},
        )

    # Converter dict para objeto-like para compatibilidade com template
    class DictObj:
        def __init__(self, data):
            for key, value in data.items():
                setattr(self, key, value)

    logs_obj = [DictObj(l) for l in logs]

    return templates.TemplateResponse(
        "automation_logs.html",
        {
            "request": request,
            "logs": logs_obj,
            "search": DictObj(search),
        },
    )


# ============ NOTIFICATIONS ============

@app.get("/notifications", response_class=HTMLResponse)
async def notifications_page(
    request: Request,
    unread_only: bool = Query(False),
):
    """Pagina de notificacoes."""
    notification_service = NotificationService()
    notifications = notification_service.get_notifications(unread_only=unread_only, limit=50)
    unread_count = notification_service.get_unread_count()
    total_count = len(notification_service.get_notifications(limit=100))

    # Converter dicts para objetos para compatibilidade com template
    class NotificationObj:
        def __init__(self, data):
            for key, value in data.items():
                setattr(self, key, value)

    notifications_obj = [NotificationObj(n) for n in notifications]

    return templates.TemplateResponse(
        "notifications.html",
        {
            "request": request,
            "notifications": notifications_obj,
            "unread_only": unread_only,
            "stats": {
                "total": total_count,
                "unread": unread_count,
                "read": total_count - unread_count,
            },
        },
    )


@app.post("/notifications/{notification_id}/read")
async def mark_notification_read(notification_id: int):
    """Marca notificacao como lida."""
    notification_service = NotificationService()
    notification_service.mark_as_read(notification_id)
    return RedirectResponse(url="/notifications", status_code=303)


@app.post("/notifications/read-all")
async def mark_all_notifications_read():
    """Marca todas as notificacoes como lidas."""
    notification_service = NotificationService()
    notification_service.mark_all_as_read()
    return RedirectResponse(url="/notifications", status_code=303)


@app.post("/notifications/{notification_id}/delete")
async def delete_notification(notification_id: int):
    """Apaga uma notificacao."""
    notification_service = NotificationService()
    notification_service.delete_notification(notification_id)
    return RedirectResponse(url="/notifications", status_code=303)


@app.get("/api/notifications/unread")
async def api_unread_notifications() -> dict:
    """API: Contagem de notificacoes nao lidas."""
    notification_service = NotificationService()
    return {"unread_count": notification_service.get_unread_count()}


# ============ SETTINGS ============

@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    """Pagina de configuracoes."""
    notion = NotionService()
    notion_config = notion.get_config()
    sync_stats = notion.get_sync_stats()

    # Converter config para objeto para template
    class ConfigObj:
        def __init__(self, data):
            if data:
                for key, value in data.items():
                    setattr(self, key, value)
            else:
                self.is_active = False

    return templates.TemplateResponse(
        "settings.html",
        {
            "request": request,
            "notion_config": ConfigObj(notion_config) if notion_config else None,
            "sync_stats": sync_stats,
        },
    )


@app.post("/settings/notion/test")
async def test_notion_connection(api_key: str = Form(...)):
    """Testa conexao com Notion."""
    notion = NotionService()
    try:
        result = await notion.test_connection(api_key)
        workspace_name = result.get("name", "")
        return {
            "success": True,
            "workspace_name": workspace_name,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/settings/notion/databases")
async def list_notion_databases(api_key: str = Query(...)):
    """Lista databases Notion disponiveis."""
    notion = NotionService()
    try:
        databases = await notion.list_databases(api_key)
        return {"databases": databases}
    except Exception as e:
        return {"databases": [], "error": str(e)}


@app.post("/settings/notion/connect")
async def connect_notion(
    api_key: str = Form(...),
    database_id: str = Form(...),
):
    """Conecta integracao Notion."""
    notion = NotionService()
    try:
        # Obter nome do workspace
        result = await notion.test_connection(api_key)
        workspace_name = result.get("name", "")

        # Salvar config
        notion.save_config(
            api_key=api_key,
            database_id=database_id,
            workspace_name=workspace_name,
        )
        return RedirectResponse(url="/settings", status_code=303)
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post("/settings/notion/disconnect")
async def disconnect_notion():
    """Desconecta integracao Notion."""
    notion = NotionService()
    notion.disconnect()
    return RedirectResponse(url="/settings", status_code=303)


# ============ NOTION SYNC ============

@app.post("/notion/sync/{place_id}", response_class=HTMLResponse)
async def sync_lead_to_notion(request: Request, place_id: str):
    """Sincroniza um lead com o Notion."""
    notion = NotionService()
    result = await notion.sync_lead(place_id)

    return templates.TemplateResponse(
        "partials/notion_sync_result.html",
        {
            "request": request,
            "result": result,
        },
    )


@app.post("/notion/sync-batch", response_class=HTMLResponse)
async def sync_batch_to_notion(
    request: Request,
    place_ids: str = Form(""),
):
    """Sincroniza multiplos leads com o Notion."""
    notion = NotionService()

    ids_list = [pid.strip() for pid in place_ids.split(",") if pid.strip()]
    if not ids_list:
        return templates.TemplateResponse(
            "partials/error.html",
            {"request": request, "message": "Nenhum lead selecionado"},
        )

    results = await notion.sync_batch(ids_list)

    success_count = sum(1 for r in results.values() if r.success)
    created_count = sum(1 for r in results.values() if r.success and r.action == "created")
    updated_count = sum(1 for r in results.values() if r.success and r.action == "updated")
    failed_count = len(results) - success_count

    return templates.TemplateResponse(
        "partials/notion_batch_result.html",
        {
            "request": request,
            "total": len(results),
            "success_count": success_count,
            "created_count": created_count,
            "updated_count": updated_count,
            "failed_count": failed_count,
            "results": results,
        },
    )


@app.get("/api/notion/status")
async def api_notion_status():
    """API: Status da integracao Notion."""
    notion = NotionService()
    config = notion.get_config()
    stats = notion.get_sync_stats()

    return {
        "connected": config.get("is_active", False) if config else False,
        "workspace": config.get("workspace_name") if config else None,
        "stats": stats,
    }


# ============ API JSON ============

@app.get("/api/stats")
async def api_stats() -> dict[str, Any]:
    """API: Estatisticas."""
    with db.get_session() as session:
        return BusinessQueries.get_stats(session)


@app.get("/api/leads")
async def api_leads(
    status: str = None,
    min_score: int = None,
    limit: int = 100,
) -> list[dict]:
    """API: Lista de leads."""
    with db.get_session() as session:
        businesses = BusinessQueries.get_all(
            session,
            status=status,
            min_score=min_score,
            limit=limit,
        )
        return [
            {
                "id": b.id,
                "name": b.name,
                "address": b.formatted_address,
                "phone": b.phone_number,
                "website": b.website,
                "rating": b.rating,
                "review_count": b.review_count,
                "lead_score": b.lead_score,
                "lead_status": b.lead_status,
            }
            for b in businesses
        ]


def main():
    """Entry point para o servidor web."""
    # Usar PORT env var (Railway define automaticamente) ou 6789 por defeito
    port = int(os.getenv("PORT", 6789))

    print("\n" + "=" * 50)
    print("  Lead Finder - Interface Web")
    print("=" * 50)
    print(f"\n  URL: http://localhost:{port}")
    print(f"  API Key: {'Configurada' if settings.has_api_key else 'NAO CONFIGURADA'}")
    print(f"  Database: {'PostgreSQL' if os.getenv('DATABASE_URL') else 'SQLite'}")
    print("\n  Pressiona Ctrl+C para parar\n")

    # Em producao (Railway), desativar reload
    is_production = os.getenv("RAILWAY_ENVIRONMENT") is not None

    uvicorn.run(
        "src.web.server:app",
        host="0.0.0.0",
        port=port,
        reload=not is_production,
    )


if __name__ == "__main__":
    main()
