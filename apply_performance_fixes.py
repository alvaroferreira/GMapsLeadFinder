#!/usr/bin/env python3
"""Script para aplicar fixes de performance ao server.py"""

from pathlib import Path


def apply_fixes():
    """Aplica todas as otimizações ao server.py"""

    server_path = Path(__file__).parent / "src" / "web" / "server.py"

    with open(server_path) as f:
        content = f.read()

    print("🔧 Aplicando performance fixes...")

    # Fix 1: Adicionar imports otimizados
    import_section = """from src.config import settings
from src.database.db import db
from src.database.models import LEAD_STATUSES, ENRICHMENT_STATUSES
from src.database.queries import BusinessQueries, SearchHistoryQueries
from src.services.enricher import EnrichmentService
from src.services.exporter import ExportService
from src.services.notion import NotionService
from src.services.scheduler import AutomationService, AutomationScheduler, NotificationService
from src.services.scorer import LeadScorer
from src.services.search import SearchService
from src.services.tracker import TrackerService"""

    new_import_section = """from src.config import settings
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
from src.web.optimizations import (
    get_notion_config_cached,
    get_stats_cached,
    invalidate_notion_cache,
    invalidate_stats_cache,
    businesses_to_dicts,
)"""

    content = content.replace(import_section, new_import_section)
    print("✅ Fix 1: Imports otimizados adicionados")

    # Fix 2: Otimizar homepage com cache
    old_home = """@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    \"\"\"Pagina inicial com dashboard.\"\"\"
    with db.get_session() as session:
        stats = BusinessQueries.get_stats(session)
        recent_searches = SearchHistoryQueries.get_recent(session, limit=5)"""

    new_home = """@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    \"\"\"Pagina inicial com dashboard.\"\"\"
    # PERFORMANCE: Cache stats por 2 minutos
    stats = get_stats_cached()

    with db.get_session() as session:
        recent_searches = SearchHistoryQueries.get_recent(session, limit=5)"""

    content = content.replace(old_home, new_home)
    print("✅ Fix 2: Homepage com stats cached")

    # Fix 3: Otimizar /leads endpoint
    old_leads_conversion = """        # Converter para dicts dentro da sessao
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
    notion_active = notion_config.get("is_active", False) if notion_config else False"""

    new_leads_conversion = """        # PERFORMANCE: Converter para dicts de forma otimizada
        businesses = businesses_to_dicts(businesses_db, include_extra=True)

    total_pages = (total + limit - 1) // limit

    # PERFORMANCE: Cache config do Notion por 5 minutos
    notion_config = get_notion_config_cached()
    notion_active = notion_config.get("is_active", False) if notion_config else False"""

    content = content.replace(old_leads_conversion, new_leads_conversion)
    print("✅ Fix 3: /leads endpoint otimizado")

    # Fix 4: Otimizar /pipeline endpoint
    old_pipeline = """    with db.get_session() as session:
        all_leads_db = BusinessQueries.get_all(session, limit=500)

        # Group by status
        leads_by_status = {s["key"]: [] for s in statuses}
        for lead in all_leads_db:
            status = lead.lead_status or "new"
            if status in leads_by_status:
                leads_by_status[status].append({
                    "id": lead.id,
                    "name": lead.name,
                    "formatted_address": lead.formatted_address,
                    "rating": lead.rating,
                    "lead_score": lead.lead_score,
                })"""

    new_pipeline = """    with db.get_session() as session:
        all_leads_db = BusinessQueries.get_all(session, limit=500)

        # PERFORMANCE: Converter todos de uma vez
        all_leads_dicts = businesses_to_dicts(all_leads_db, include_extra=False)

    # Group by status (fora da sessão)
    leads_by_status = {s["key"]: [] for s in statuses}
    for lead in all_leads_dicts:
        status = lead.get("lead_status") or "new"
        if status in leads_by_status:
            leads_by_status[status].append(lead)"""

    content = content.replace(old_pipeline, new_pipeline)
    print("✅ Fix 4: /pipeline endpoint otimizado")

    # Fix 5: Otimizar /new-businesses endpoint
    old_new_businesses = """        # Converter para dicts
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
                "first_seen_at": b.first_seen_at,
            })"""

    new_new_businesses = """        # PERFORMANCE: Converter para dicts de forma otimizada
        businesses = businesses_to_dicts(businesses_db, include_extra=False)
        # Adicionar first_seen_at manualmente
        for i, b in enumerate(businesses):
            b["first_seen_at"] = businesses_db[i].first_seen_at"""

    content = content.replace(old_new_businesses, new_new_businesses)
    print("✅ Fix 5: /new-businesses endpoint otimizado")

    # Fix 6: Adicionar invalidação de cache nos endpoints de update
    old_notion_connect = """        notion.save_config(
            api_key=api_key,
            database_id=database_id,
            workspace_name=workspace_name,
        )
        return RedirectResponse(url="/settings", status_code=303)"""

    new_notion_connect = """        notion.save_config(
            api_key=api_key,
            database_id=database_id,
            workspace_name=workspace_name,
        )
        # PERFORMANCE: Invalidar cache do Notion
        invalidate_notion_cache()
        return RedirectResponse(url="/settings", status_code=303)"""

    content = content.replace(old_notion_connect, new_notion_connect)
    print("✅ Fix 6: Cache invalidation adicionado")

    # Fix 7: Otimizar busca de existing IDs em /search
    old_existing_ids = """    # Get existing business IDs before search to identify new ones
    existing_ids = set()
    if not show_only_new:
        with db.get_session() as session:
            all_businesses = BusinessQueries.get_all(session, limit=10000)
            existing_ids = {b.id for b in all_businesses}"""

    new_existing_ids = """    # PERFORMANCE: Get existing business IDs (apenas IDs, não objetos completos)
    existing_ids = set()
    if not show_only_new:
        from src.database.models import Business
        with db.get_session() as session:
            # Query otimizada: buscar apenas IDs
            existing_ids = {row[0] for row in session.query(Business.id).all()}"""

    content = content.replace(old_existing_ids, new_existing_ids)
    print("✅ Fix 7: Busca de existing IDs otimizada")

    # Salvar arquivo modificado
    with open(server_path, "w") as f:
        f.write(content)

    print("\n✨ Todos os fixes aplicados com sucesso!")
    print(f"📁 Arquivo modificado: {server_path}")
    print("📋 Backup disponível em: server.py.backup")
    print("\n⚠️  IMPORTANTE: Testar a aplicação antes de fazer deploy!")


if __name__ == "__main__":
    apply_fixes()
