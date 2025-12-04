"""CLI principal - Google Maps Lead Finder."""

import asyncio
import shutil
from datetime import datetime
from pathlib import Path

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from src import __version__
from src.config import settings
from src.database.db import db
from src.database.models import LEAD_STATUSES
from src.database.queries import BusinessQueries
from src.services.exporter import ExportService
from src.services.scorer import LeadScorer
from src.services.search import SearchService
from src.services.tracker import TrackerService


console = Console()


def run_async(coro):
    """Helper para executar coroutines."""
    return asyncio.get_event_loop().run_until_complete(coro)


@click.group()
@click.version_option(version=__version__, prog_name="leadfinder")
@click.pass_context
def cli(ctx):
    """Google Maps Lead Finder - Ferramenta de prospeccao B2B.

    Pesquisa negocios no Google Maps, qualifica leads automaticamente
    e exporta para varios formatos.
    """
    # Inicializar DB
    settings.ensure_directories()
    db.create_tables()

    # Verificar API key
    if not settings.has_api_key:
        if ctx.invoked_subcommand not in ["config", "list", "stats", "export"]:
            console.print(
                "[yellow]Aviso: API key nao configurada. "
                "Configure GOOGLE_PLACES_API_KEY no ficheiro .env[/yellow]"
            )


# ============ SEARCH ============


@cli.command()
@click.option("--query", "-q", required=True, help="Texto de pesquisa")
@click.option("--location", "-l", help="Localizacao (cidade ou lat,lng)")
@click.option("--radius", "-r", default=5000, type=int, help="Raio em metros (max 50000)")
@click.option("--type", "place_type", help="Tipo de negocio (ex: restaurant, dentist)")
@click.option("--min-reviews", type=int, help="Minimo de reviews")
@click.option("--max-reviews", type=int, help="Maximo de reviews")
@click.option("--min-rating", type=float, help="Rating minimo (0-5)")
@click.option("--max-rating", type=float, help="Rating maximo (0-5)")
@click.option("--has-website/--no-website", default=None, help="Filtrar por website")
@click.option("--has-phone/--no-phone", default=None, help="Filtrar por telefone")
@click.option("--max-results", default=60, type=int, help="Maximo de resultados")
def search(
    query,
    location,
    radius,
    place_type,
    min_reviews,
    max_reviews,
    min_rating,
    max_rating,
    has_website,
    has_phone,
    max_results,
):
    """Pesquisa negocios no Google Maps."""
    if not settings.has_api_key:
        console.print("[red]Erro: API key nao configurada[/red]")
        raise SystemExit(1)

    # Parse location
    loc_tuple = None
    if location:
        if (
            "," in location
            and location.replace(",", "").replace("-", "").replace(".", "").isdigit()
        ):
            parts = location.split(",")
            loc_tuple = (float(parts[0].strip()), float(parts[1].strip()))
        else:
            console.print(
                f"[yellow]Nota: Geocoding de '{location}' nao implementado. "
                "Use coordenadas (lat,lng)[/yellow]"
            )

    service = SearchService()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("Pesquisando...", total=None)

        result = run_async(
            service.search(
                query=query,
                location=loc_tuple,
                radius=radius,
                place_type=place_type,
                max_results=max_results,
                min_reviews=min_reviews,
                max_reviews=max_reviews,
                min_rating=min_rating,
                max_rating=max_rating,
                has_website=has_website,
                has_phone=has_phone,
            )
        )

    console.print("\n[green]Pesquisa concluida![/green]")
    console.print(f"  Total encontrados: {result.total_found}")
    console.print(f"  Novos negocios: [cyan]{result.new_businesses}[/cyan]")
    console.print(f"  Atualizados: {result.updated_businesses}")
    if result.filtered_out > 0:
        console.print(f"  Filtrados: {result.filtered_out}")
    console.print(f"  Chamadas API: {result.api_calls}")


# ============ LIST ============


@cli.command("list")
@click.option("--status", type=click.Choice(LEAD_STATUSES), help="Filtrar por status")
@click.option("--min-score", type=int, help="Score minimo")
@click.option("--city", help="Filtrar por cidade")
@click.option("--has-website/--no-website", default=None, help="Filtrar por website")
@click.option("--limit", default=20, type=int, help="Numero de resultados")
@click.option("--offset", default=0, type=int, help="Offset para paginacao")
def list_leads(status, min_score, city, has_website, limit, offset):
    """Lista leads da base de dados."""
    with db.get_session() as session:
        businesses = BusinessQueries.get_all(
            session,
            status=status,
            min_score=min_score,
            city=city,
            has_website=has_website,
            limit=limit,
            offset=offset,
        )

        if not businesses:
            console.print("[yellow]Nenhum lead encontrado[/yellow]")
            return

        table = Table(title=f"Leads ({len(businesses)} resultados)")
        table.add_column("Nome", style="cyan", max_width=30)
        table.add_column("Score", justify="right")
        table.add_column("Rating", justify="right")
        table.add_column("Reviews", justify="right")
        table.add_column("Website", justify="center")
        table.add_column("Status")
        table.add_column("Cidade", max_width=20)

        for b in businesses:
            website_icon = "[green]Sim[/green]" if b.has_website else "[red]Nao[/red]"
            rating = f"{b.rating:.1f}" if b.rating else "-"
            city_name = b.formatted_address.split(",")[-2].strip() if b.formatted_address else "-"

            table.add_row(
                b.name[:30],
                str(b.lead_score),
                rating,
                str(b.review_count or 0),
                website_icon,
                b.lead_status,
                city_name[:20],
            )

        console.print(table)


# ============ EXPORT ============


@cli.command()
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["csv", "xlsx", "json", "hubspot", "pipedrive", "salesforce"]),
    default="csv",
    help="Formato de exportacao",
)
@click.option("--output", "-o", help="Nome do ficheiro")
@click.option("--min-score", type=int, help="Score minimo")
@click.option("--status", type=click.Choice(LEAD_STATUSES), help="Filtrar por status")
@click.option("--has-website/--no-website", default=None, help="Filtrar por website")
@click.option("--limit", default=10000, type=int, help="Maximo de leads")
def export(fmt, output, min_score, status, has_website, limit):
    """Exporta leads para ficheiro."""
    exporter = ExportService()

    with db.get_session() as session:
        businesses = BusinessQueries.get_all(
            session,
            status=status,
            min_score=min_score,
            has_website=has_website,
            limit=limit,
        )

        if not businesses:
            console.print("[yellow]Nenhum lead para exportar[/yellow]")
            return

        # Mostrar resumo
        summary = exporter.get_export_summary(businesses)
        console.print(f"\nExportando {summary['total']} leads...")

        # Exportar
        if fmt == "csv":
            path = exporter.export_csv(businesses, output)
        elif fmt == "xlsx":
            path = exporter.export_excel(businesses, output)
        elif fmt == "json":
            path = exporter.export_json(businesses, output)
        else:
            path = exporter.export_crm(businesses, fmt, output)

        console.print(f"[green]Exportado para:[/green] {path}")


# ============ STATS ============


@cli.command()
def stats():
    """Mostra estatisticas da base de dados."""
    with db.get_session() as session:
        stats = BusinessQueries.get_stats(session)

        console.print("\n[bold]Estatisticas da Base de Dados[/bold]\n")
        console.print(f"  Total de leads: [cyan]{stats['total']}[/cyan]")
        console.print(f"  Score medio: {stats['avg_score']}")
        console.print(f"  Rating medio: {stats['avg_rating']}")
        console.print(f"  Sem website: [yellow]{stats['without_website']}[/yellow]")
        console.print(f"  Novos esta semana: [green]{stats['new_this_week']}[/green]")

        if stats["by_status"]:
            console.print("\n  Por status:")
            for status, count in stats["by_status"].items():
                console.print(f"    {status}: {count}")


# ============ UPDATE ============


@cli.command()
@click.argument("place_id")
@click.option("--status", type=click.Choice(LEAD_STATUSES), help="Novo status")
@click.option("--notes", help="Adicionar notas")
def update(place_id, status, notes):
    """Atualiza status ou notas de um lead."""
    if not status and not notes:
        console.print("[yellow]Especifique --status ou --notes[/yellow]")
        return

    with db.get_session() as session:
        business = BusinessQueries.get_by_id(session, place_id)

        if not business:
            console.print(f"[red]Lead '{place_id}' nao encontrado[/red]")
            return

        if status:
            business.lead_status = status
        if notes:
            existing = business.notes or ""
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
            business.notes = f"{existing}\n[{timestamp}] {notes}".strip()

        console.print(f"[green]Lead '{business.name}' atualizado[/green]")


# ============ NEW ============


@cli.command("new")
@click.option("--since", help="Data inicial (YYYY-MM-DD)")
@click.option("--days", default=7, type=int, help="Ultimos N dias")
@click.option("--limit", default=50, type=int, help="Maximo de resultados")
def show_new(since, days, limit):
    """Mostra negocios descobertos recentemente."""
    tracker = TrackerService()

    since_date = None
    if since:
        since_date = datetime.strptime(since, "%Y-%m-%d")

    businesses = tracker.get_new_businesses(since=since_date, days=days, limit=limit)

    if not businesses:
        console.print(f"[yellow]Nenhum negocio novo nos ultimos {days} dias[/yellow]")
        return

    console.print(f"\n[bold]Novos negocios ({len(businesses)})[/bold]\n")

    for b in businesses:
        score_color = "green" if b.lead_score >= 50 else "yellow" if b.lead_score >= 30 else "white"
        console.print(
            f"  [cyan]{b.name}[/cyan] - Score: [{score_color}]{b.lead_score}[/{score_color}]"
        )
        if b.formatted_address:
            console.print(f"    {b.formatted_address}")
        console.print(f"    Descoberto: {b.first_seen_at.strftime('%Y-%m-%d %H:%M')}")
        if b.website:
            console.print(f"    Website: {b.website}")
        console.print()


# ============ SCORE ============


@cli.command()
@click.option("--recalculate", is_flag=True, help="Recalcular todos os scores")
@click.option("--explain", "explain_id", help="Explicar score de um lead (place_id)")
def score(recalculate, explain_id):
    """Gere lead scoring."""
    scorer = LeadScorer()

    if explain_id:
        with db.get_session() as session:
            business = BusinessQueries.get_by_id(session, explain_id)
            if not business:
                console.print(f"[red]Lead '{explain_id}' nao encontrado[/red]")
                return

            explanation = scorer.explain(business)
            total = sum(e["points"] for e in explanation)

            console.print(f"\n[bold]Score de '{business.name}'[/bold]")
            console.print(f"Total: [cyan]{total}[/cyan] / {scorer.get_max_score()}\n")

            table = Table()
            table.add_column("Regra")
            table.add_column("Pontos", justify="right")
            table.add_column("Descricao")

            for e in explanation:
                if e["matched"]:
                    table.add_row(
                        f"[green]{e['rule']}[/green]",
                        f"[green]+{e['points']}[/green]",
                        e["description"],
                    )
                else:
                    table.add_row(
                        f"[dim]{e['rule']}[/dim]",
                        "[dim]0[/dim]",
                        f"[dim]{e['description']}[/dim]",
                    )

            console.print(table)
        return

    if recalculate:
        with db.get_session() as session:
            processed, changed = scorer.recalculate_all(session)
            console.print(f"[green]Recalculados {processed} leads, {changed} alterados[/green]")


# ============ TRACK ============


@cli.command()
@click.option("--add", "add_name", help="Criar nova pesquisa agendada")
@click.option("--query", "-q", help="Query para nova pesquisa")
@click.option("--interval", default=24, type=int, help="Intervalo em horas")
@click.option("--list", "show_list", is_flag=True, help="Listar pesquisas agendadas")
@click.option("--run", "run_id", type=int, help="Executar pesquisa agendada")
@click.option("--disable", type=int, help="Desativar pesquisa agendada")
def track(add_name, query, interval, show_list, run_id, disable):
    """Gere pesquisas agendadas para tracking."""
    tracker = TrackerService()

    if show_list:
        tracked = tracker.get_tracked_searches(active_only=False)
        if not tracked:
            console.print("[yellow]Nenhuma pesquisa agendada[/yellow]")
            return

        table = Table(title="Pesquisas Agendadas")
        table.add_column("ID")
        table.add_column("Nome")
        table.add_column("Query")
        table.add_column("Intervalo")
        table.add_column("Ultima Execucao")
        table.add_column("Ativa")

        for t in tracked:
            params = t.query_params or {}
            status = "[green]Sim[/green]" if t.is_active else "[red]Nao[/red]"
            last_run = t.last_run_at.strftime("%Y-%m-%d %H:%M") if t.last_run_at else "-"

            table.add_row(
                str(t.id),
                t.name,
                params.get("query", "-")[:30],
                f"{t.interval_hours}h",
                last_run,
                status,
            )

        console.print(table)
        return

    if add_name:
        if not query:
            console.print("[red]Especifique --query para a pesquisa[/red]")
            return

        tracked = tracker.create_tracked_search(
            name=add_name,
            query=query,
            interval_hours=interval,
        )
        console.print(f"[green]Pesquisa '{add_name}' criada (ID: {tracked.id})[/green]")
        return

    if run_id:
        with Progress(
            SpinnerColumn(), TextColumn("[progress.description]{task.description}")
        ) as progress:
            progress.add_task("Executando pesquisa...", total=None)
            result = run_async(tracker.run_tracked_search(run_id))

        if result:
            console.print(f"[green]Pesquisa '{result.tracked_name}' executada[/green]")
            console.print(f"  Novos negocios: {result.new_businesses}")
            console.print(f"  Total encontrados: {result.total_found}")
        else:
            console.print("[red]Pesquisa nao encontrada ou inativa[/red]")
        return

    if disable:
        if tracker.deactivate_tracked_search(disable):
            console.print(f"[green]Pesquisa {disable} desativada[/green]")
        else:
            console.print("[red]Pesquisa nao encontrada[/red]")
        return

    # Default: mostrar ajuda
    console.print("Use --list, --add, --run ou --disable")


# ============ BACKUP ============


@cli.command()
@click.option("--output", "-o", help="Nome do ficheiro de backup")
def backup(output):
    """Cria backup da base de dados."""
    if not settings.database_url.startswith("sqlite"):
        console.print("[red]Backup so suportado para SQLite[/red]")
        return

    db_path = Path(settings.database_url.replace("sqlite:///", ""))
    if not db_path.exists():
        console.print("[yellow]Base de dados nao existe[/yellow]")
        return

    if not output:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output = f"backup_{timestamp}.db"

    backup_path = settings.export_dir / output
    shutil.copy2(db_path, backup_path)

    console.print(f"[green]Backup criado:[/green] {backup_path}")


# ============ CONFIG ============


@cli.command()
def config():
    """Mostra configuracao atual."""
    console.print("\n[bold]Configuracao Atual[/bold]\n")
    console.print(
        f"  API Key: {'[green]Configurada[/green]' if settings.has_api_key else '[red]Nao configurada[/red]'}"
    )
    console.print(f"  Database: {settings.database_url}")
    console.print(f"  Export Dir: {settings.export_dir}")
    console.print(f"  Raio padrao: {settings.default_radius}m")
    console.print(f"  Idioma: {settings.default_language}")
    console.print(f"  Rate limit: {settings.requests_per_second} req/s")
    console.print(f"  Refresh dados: {settings.data_refresh_days} dias")


if __name__ == "__main__":
    cli()
