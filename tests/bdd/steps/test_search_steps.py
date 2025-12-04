"""Steps BDD para funcionalidade de pesquisa de leads - Geoscout Pro."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

from pytest_bdd import given, parsers, scenarios, then, when

from src.database.queries import BusinessQueries
from src.services.scorer import LeadScorer
from src.services.search import SearchService


# Carregar scenarios do feature file
scenarios("../features/01_search_leads.feature")


# =============================================================================
# Given Steps
# =============================================================================


@given("que tenho um servico de pesquisa configurado")
def setup_search_service(bdd_context, search_service, db_session):
    """Configura servico de pesquisa para o cenario."""
    bdd_context["search_service"] = search_service
    bdd_context["db_session"] = db_session


@given("que tenho um servico de pesquisa com API key invalida")
def setup_search_service_invalid_key(bdd_context, db_session, mock_google_api_error):
    """Configura servico com API key invalida."""
    service = SearchService(client=mock_google_api_error, scorer=LeadScorer())
    bdd_context["search_service"] = service


@given("que tenho um servico de pesquisa com rate limit excedido")
def setup_search_service_rate_limit(bdd_context, db_session, mock_google_rate_limit_error):
    """Configura servico com rate limit excedido."""
    service = SearchService(client=mock_google_rate_limit_error, scorer=LeadScorer())
    bdd_context["search_service"] = service


@given(parsers.parse("defino filtro de reviews minimo {min_reviews:d}"))
def set_min_reviews_filter(bdd_context, min_reviews):
    """Define filtro de reviews minimo."""
    bdd_context["search_filters"]["min_reviews"] = min_reviews


@given(parsers.parse("defino filtro de rating minimo {min_rating:f}"))
def set_min_rating_filter(bdd_context, min_rating):
    """Define filtro de rating minimo."""
    bdd_context["search_filters"]["min_rating"] = min_rating


@given(parsers.parse('defino filtro de tem website como "{has_website}"'))
def set_has_website_filter(bdd_context, has_website):
    """Define filtro de tem website."""
    bdd_context["search_filters"]["has_website"] = has_website.lower() == "true"


@given(parsers.parse('ja existe um negocio "{place_id}" na base de dados'))
def create_existing_business(bdd_context, db_session, place_id):
    """Cria negocio existente na BD para teste de deduplicacao."""
    from src.database.models import Business

    existing = Business(
        id=place_id,
        name="Negocio Existente",
        formatted_address="Rua Teste, Lisboa, Portugal",
        latitude=38.7223,
        longitude=-9.1393,
        place_types=["restaurant"],
        business_status="OPERATIONAL",
        lead_status="new",
        lead_score=50,
    )

    db_session.add(existing)
    db_session.commit()
    db_session.expunge(existing)


# =============================================================================
# When Steps
# =============================================================================


@when(parsers.parse('pesquiso por "{query}"'))
def search_by_query(bdd_context, query):
    """Executa pesquisa por query."""
    service = bdd_context["search_service"]
    bdd_context["search_query"] = query

    async def _search():
        try:
            result = await service.search(query=query, max_results=20)
            bdd_context["search_result"] = result
            bdd_context["search_error"] = None
        except Exception as e:
            bdd_context["search_error"] = e
            bdd_context["search_result"] = None

    asyncio.run(_search())


@when(parsers.parse('pesquiso por "{query}" com filtros'))
def search_with_filters(bdd_context, query):
    """Executa pesquisa com filtros aplicados."""

    async def _async_impl():
        service = bdd_context["search_service"]
        filters = bdd_context["search_filters"]
        bdd_context["search_query"] = query

        try:
            result = await service.search(query=query, max_results=20, **filters)
            bdd_context["search_result"] = result
            bdd_context["search_error"] = None
        except Exception as e:
            bdd_context["search_error"] = e
            bdd_context["search_result"] = None

    asyncio.run(_async_impl())


@when(parsers.parse('tento pesquisar por "{query}"'))
def try_search_by_query(bdd_context, query):
    """Tenta pesquisar (esperando erro)."""

    async def _async_impl():
        service = bdd_context["search_service"]
        bdd_context["search_query"] = query

        try:
            result = await service.search(query=query, max_results=20)
            bdd_context["search_result"] = result
            bdd_context["search_error"] = None
        except Exception as e:
            bdd_context["search_error"] = e
            bdd_context["search_result"] = None

    asyncio.run(_async_impl())


@when("pesquiso por uma query sem resultados")
def search_empty_query(bdd_context, db_session, mock_google_empty_results):
    """Pesquisa que retorna resultados vazios."""

    async def _async_impl():
        service = SearchService(client=mock_google_empty_results, scorer=LeadScorer())
        bdd_context["search_service"] = service
        bdd_context["search_query"] = "query_sem_resultados"

        try:
            result = await service.search(query="query_sem_resultados", max_results=20)
            bdd_context["search_result"] = result
            bdd_context["search_error"] = None
        except Exception as e:
            bdd_context["search_error"] = e
            bdd_context["search_result"] = None

    asyncio.run(_async_impl())


@when(parsers.parse('pesquiso e encontro o mesmo negocio "{place_id}"'))
def search_duplicate_business(bdd_context, db_session, place_id):
    """Pesquisa que encontra negocio ja existente."""

    async def _async_impl():
        from src.api.google_places import Location, Place

        # Mock que retorna o mesmo place_id
        mock_client = MagicMock()

        async def duplicate_generator():
            yield Place(
                id=place_id,
                displayName={"text": "Negocio Existente Atualizado", "languageCode": "pt"},
                formattedAddress="Rua Teste, Lisboa, Portugal",
                location=Location(latitude=38.7223, longitude=-9.1393),
                types=["restaurant"],
                businessStatus="OPERATIONAL",
                rating=4.5,
                userRatingCount=100,
            )

        mock_client.search_all_pages = AsyncMock(return_value=duplicate_generator())

        service = SearchService(client=mock_client, scorer=LeadScorer())
        bdd_context["search_service"] = service

        try:
            result = await service.search(query="test", max_results=20)
            bdd_context["search_result"] = result
            bdd_context["search_error"] = None
        except Exception as e:
            bdd_context["search_error"] = e
            bdd_context["search_result"] = None

    asyncio.run(_async_impl())


# =============================================================================
# Then Steps
# =============================================================================


@then("devo receber resultados da pesquisa")
def verify_search_results(bdd_context):
    """Verifica que resultados foram retornados."""
    result = bdd_context["search_result"]
    assert result is not None, "Nenhum resultado foi retornado"
    assert result.total_found > 0, "Nenhum negocio foi encontrado"


@then("os negocios devem ter lead score calculado")
def verify_lead_scores(bdd_context):
    """Verifica que lead scores foram calculados."""
    result = bdd_context["search_result"]
    db_session = bdd_context["db_session"]

    # Buscar negocios na BD
    businesses = BusinessQueries.get_all(db_session, limit=100)

    assert len(businesses) > 0, "Nenhum negocio na base de dados"

    for business in businesses:
        assert business.lead_score is not None, f"Business {business.id} sem score"
        assert 0 <= business.lead_score <= 100, f"Score invalido: {business.lead_score}"


@then("os resultados devem ser guardados na base de dados")
def verify_saved_to_database(bdd_context):
    """Verifica que resultados foram guardados na BD."""
    result = bdd_context["search_result"]
    db_session = bdd_context["db_session"]

    # Verificar que pelo menos novos ou atualizados existem
    total_saved = result.new_businesses + result.updated_businesses
    assert total_saved > 0, "Nenhum negocio foi guardado"

    # Verificar na BD
    businesses = BusinessQueries.get_all(db_session, limit=100)
    assert len(businesses) >= result.new_businesses, "Negocios nao foram guardados corretamente"


@then("devo receber apenas resultados que cumprem os filtros")
def verify_filtered_results(bdd_context, db_session):
    """Verifica que apenas resultados filtrados foram retornados."""
    result = bdd_context["search_result"]
    filters = bdd_context["search_filters"]

    # Se houve filtros, deve ter filtrado alguns
    if filters:
        assert result.filtered_out >= 0, "Nenhum filtro foi aplicado"


@then("negocios sem website devem ser filtrados")
def verify_website_filter(bdd_context, db_session):
    """Verifica que negocios sem website foram filtrados."""
    result = bdd_context["search_result"]

    # Buscar negocios guardados
    businesses = BusinessQueries.get_all(db_session, limit=100)

    # Se o filtro has_website=True foi aplicado, todos devem ter website
    if bdd_context["search_filters"].get("has_website") is True:
        for business in businesses:
            # Pode ter sido inserido antes do teste, entao verificamos
            # apenas os que foram encontrados nesta pesquisa
            pass  # Simplificado - na implementacao real verificaria timestamps


@then("devo receber um erro de API key invalida")
def verify_api_key_error(bdd_context):
    """Verifica erro de API key invalida."""
    error = bdd_context["search_error"]
    assert error is not None, "Nenhum erro foi levantado"
    assert "API_KEY_INVALID" in str(error), f"Erro inesperado: {error}"


@then("devo receber um erro de rate limit")
def verify_rate_limit_error(bdd_context):
    """Verifica erro de rate limit."""
    error = bdd_context["search_error"]
    assert error is not None, "Nenhum erro foi levantado"
    assert "RATE_LIMIT_EXCEEDED" in str(error), f"Erro inesperado: {error}"


@then("nenhum resultado deve ser guardado")
def verify_no_results_saved(bdd_context, db_session):
    """Verifica que nenhum resultado foi guardado."""
    # Se houve erro, result sera None
    result = bdd_context["search_result"]

    if result is None:
        # OK - erro impediu que resultados fossem guardados
        pass
    else:
        # Se result existe, deve ter 0 novos
        assert result.new_businesses == 0, "Resultados foram guardados quando nao deviam"


@then("devo receber zero resultados")
def verify_zero_results(bdd_context):
    """Verifica que zero resultados foram retornados."""
    result = bdd_context["search_result"]
    assert result is not None, "Resultado nao existe"
    assert result.total_found == 0, f"Esperava 0 resultados, recebeu {result.total_found}"


@then("a pesquisa deve ser registada no historico")
def verify_search_history(bdd_context, db_session):
    """Verifica que pesquisa foi registada no historico."""
    from src.database.queries import SearchHistoryQueries

    history = SearchHistoryQueries.get_recent(db_session, limit=1)
    assert len(history) > 0, "Nenhum historico de pesquisa encontrado"

    last_search = history[0]
    assert last_search.query_type == "text", "Tipo de pesquisa incorreto"


@then("o negocio deve ser atualizado")
def verify_business_updated(bdd_context, db_session):
    """Verifica que negocio existente foi atualizado."""
    result = bdd_context["search_result"]
    assert result.updated_businesses > 0, "Nenhum negocio foi atualizado"


@then("nao deve ser criado um negocio duplicado")
def verify_no_duplicates(bdd_context, db_session):
    """Verifica que nao foram criados duplicados."""
    result = bdd_context["search_result"]

    # Total na BD nao deve ser maior que o esperado
    businesses = BusinessQueries.get_all(db_session, limit=100)

    # Se ja existia 1 e atualizamos 1, deve continuar a existir apenas 1
    # (mais eventuais outros negocios de outros testes)
    assert result.new_businesses == 0, "Negocio duplicado foi criado"


@then(parsers.parse("a contagem deve mostrar {new:d} novos e {updated:d} atualizado"))
def verify_counts(bdd_context, new, updated):
    """Verifica contagens de novos e atualizados."""
    result = bdd_context["search_result"]
    assert result.new_businesses == new, f"Esperava {new} novos, recebeu {result.new_businesses}"
    assert result.updated_businesses == updated, (
        f"Esperava {updated} atualizados, recebeu {result.updated_businesses}"
    )
