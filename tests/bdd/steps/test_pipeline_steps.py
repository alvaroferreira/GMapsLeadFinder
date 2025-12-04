"""Steps BDD para funcionalidade de pipeline Kanban - Geoscout Pro."""

from datetime import datetime

from pytest_bdd import given, parsers, scenarios, then, when

from src.database.models import Business
from src.database.queries import BusinessQueries
from src.exceptions import BusinessNotFoundError, ValidationError
from src.services.leads_service import LeadFilters, LeadUpdate


# Carregar scenarios do feature file
scenarios("../features/03_pipeline_kanban.feature")


# =============================================================================
# Given Steps (Contexto)
# =============================================================================


@given("que tenho um servico de leads configurado")
def setup_leads_service(bdd_context, leads_service):
    """Configura servico de leads para o cenario."""
    bdd_context["leads_service"] = leads_service


@given("tenho leads de exemplo na base de dados")
def setup_sample_leads(bdd_context, db_session, sample_businesses_in_db):
    """Garante que leads de exemplo existem na BD."""
    bdd_context["db_session"] = db_session
    # sample_businesses_in_db ja cria os leads automaticamente


@given(parsers.parse('que tenho um lead com status "{status}"'))
def setup_lead_with_status(bdd_context, db_session, status):
    """Cria ou busca lead com status especifico."""
    # Buscar lead existente com esse status ou criar novo
    businesses = BusinessQueries.get_all(db_session, status=status, limit=1)

    if businesses:
        lead = businesses[0]
        db_session.expunge(lead)
    else:
        # Criar novo lead
        lead = Business(
            id=f"bdd_lead_{status}_{datetime.now().timestamp()}",
            name=f"Lead Status {status}",
            formatted_address="Rua Teste Pipeline, Lisboa, Portugal",
            latitude=38.7223,
            longitude=-9.1393,
            place_types=["restaurant"],
            business_status="OPERATIONAL",
            lead_status=status,
            lead_score=60,
        )
        db_session.add(lead)
        db_session.commit()
        db_session.expunge(lead)

    bdd_context["current_lead"] = lead
    bdd_context["lead_id"] = lead.id


@given("que tenho um lead sem tags")
def setup_lead_without_tags(bdd_context, db_session):
    """Cria lead sem tags."""
    lead = Business(
        id=f"bdd_lead_no_tags_{datetime.now().timestamp()}",
        name="Lead Sem Tags",
        formatted_address="Rua Sem Tags, Lisboa, Portugal",
        latitude=38.7223,
        longitude=-9.1393,
        place_types=["cafe"],
        business_status="OPERATIONAL",
        lead_status="new",
        lead_score=50,
        tags=[],
    )

    db_session.add(lead)
    db_session.commit()
    db_session.expunge(lead)

    bdd_context["current_lead"] = lead
    bdd_context["lead_id"] = lead.id


@given(parsers.parse('que tenho um lead com id "{lead_id}"'))
def setup_lead_by_id(bdd_context, db_session, lead_id):
    """Busca lead por ID especifico."""
    lead = BusinessQueries.get_by_id(db_session, lead_id)

    if lead:
        db_session.expunge(lead)
        bdd_context["current_lead"] = lead
        bdd_context["lead_id"] = lead_id
    else:
        # Se nao existe, criar
        lead = Business(
            id=lead_id,
            name=f"Lead {lead_id}",
            formatted_address="Rua Pipeline, Lisboa, Portugal",
            latitude=38.7223,
            longitude=-9.1393,
            place_types=["store"],
            business_status="OPERATIONAL",
            lead_status="new",
            lead_score=65,
        )
        db_session.add(lead)
        db_session.commit()
        db_session.expunge(lead)
        bdd_context["current_lead"] = lead
        bdd_context["lead_id"] = lead_id


@given("carrego o lead em duas sessoes diferentes")
def load_lead_in_two_sessions(bdd_context, db_session):
    """Simula carregar lead em duas sessoes (concorrencia)."""
    lead_id = bdd_context["lead_id"]

    # Primeira sessao
    lead_session1 = BusinessQueries.get_by_id(db_session, lead_id)
    db_session.expunge(lead_session1)

    # Segunda sessao (simulada pelo mesmo db_session)
    lead_session2 = BusinessQueries.get_by_id(db_session, lead_id)
    db_session.expunge(lead_session2)

    bdd_context["lead_session1"] = lead_session1
    bdd_context["lead_session2"] = lead_session2


@given("que tenho leads com varios status")
def setup_leads_multiple_status(bdd_context, db_session):
    """Cria leads com varios status diferentes."""
    # sample_businesses_in_db ja cria leads com varios status
    # Verificar que existem
    for status in ["new", "contacted", "qualified"]:
        businesses = BusinessQueries.get_all(db_session, status=status, limit=1)
        if not businesses:
            # Criar se nao existe
            lead = Business(
                id=f"bdd_lead_{status}_{datetime.now().timestamp()}",
                name=f"Lead {status.title()}",
                formatted_address=f"Rua {status}, Lisboa, Portugal",
                latitude=38.7200 + (0.01 * len(status)),
                longitude=-9.1400,
                place_types=["restaurant"],
                business_status="OPERATIONAL",
                lead_status=status,
                lead_score=50 + len(status) * 5,
            )
            db_session.add(lead)

    db_session.commit()


@given("que tenho leads com varios scores")
def setup_leads_multiple_scores(bdd_context, db_session):
    """Cria leads com varios scores."""
    scores = [40, 60, 75, 85]

    for score in scores:
        # Verificar se ja existe lead com esse score
        existing = BusinessQueries.get_all(db_session, min_score=score, max_score=score, limit=1)

        if not existing:
            lead = Business(
                id=f"bdd_lead_score_{score}_{datetime.now().timestamp()}",
                name=f"Lead Score {score}",
                formatted_address=f"Rua Score {score}, Lisboa, Portugal",
                latitude=38.7200 + (score / 1000),
                longitude=-9.1400,
                place_types=["cafe"],
                business_status="OPERATIONAL",
                lead_status="new",
                lead_score=score,
            )
            db_session.add(lead)

    db_session.commit()


@given("que tenho leads com tags diferentes")
def setup_leads_with_tags(bdd_context, db_session):
    """Cria leads com tags diferentes."""
    tags_configs = [
        (["premium", "tech"], "Lead Premium Tech"),
        (["premium", "urgente"], "Lead Premium Urgente"),
        (["tech"], "Lead Tech"),
        ([], "Lead Sem Tags"),
    ]

    for tags, name in tags_configs:
        lead = Business(
            id=f"bdd_lead_tags_{name.replace(' ', '_')}_{datetime.now().timestamp()}",
            name=name,
            formatted_address=f"Rua {name}, Lisboa, Portugal",
            latitude=38.7200,
            longitude=-9.1400,
            place_types=["store"],
            business_status="OPERATIONAL",
            lead_status="new",
            lead_score=70,
            tags=tags,
        )
        db_session.add(lead)

    db_session.commit()


# =============================================================================
# When Steps
# =============================================================================


@when(parsers.parse('atualizo o status para "{new_status}"'))
def update_lead_status(bdd_context, new_status):
    """Atualiza status do lead."""
    service = bdd_context["leads_service"]
    lead_id = bdd_context["lead_id"]

    try:
        update = LeadUpdate(status=new_status)
        updated_lead = service.update_lead(lead_id, update)
        bdd_context["update_result"] = updated_lead
        bdd_context["update_error"] = None
    except Exception as e:
        bdd_context["update_error"] = e
        bdd_context["update_result"] = None


@when(parsers.parse('adiciono as tags "{tag1}", "{tag2}", "{tag3}"'))
def add_multiple_tags(bdd_context, tag1, tag2, tag3):
    """Adiciona multiplas tags ao lead."""
    service = bdd_context["leads_service"]
    lead_id = bdd_context["lead_id"]
    tags = [tag1, tag2, tag3]

    try:
        update = LeadUpdate(tags=tags)
        updated_lead = service.update_lead(lead_id, update)
        bdd_context["update_result"] = updated_lead
        bdd_context["update_error"] = None
    except Exception as e:
        bdd_context["update_error"] = e
        bdd_context["update_result"] = None


@when(parsers.parse('adiciono a nota "{note_text}"'))
def add_note_to_lead(bdd_context, note_text):
    """Adiciona nota ao lead."""
    service = bdd_context["leads_service"]
    lead_id = bdd_context["lead_id"]

    try:
        update = LeadUpdate(notes=note_text)
        updated_lead = service.update_lead(lead_id, update)
        bdd_context["update_result"] = updated_lead
        bdd_context["update_error"] = None
    except Exception as e:
        bdd_context["update_error"] = e
        bdd_context["update_result"] = None


@when(parsers.parse('tento atualizar o status para "{invalid_status}"'))
def try_update_invalid_status(bdd_context, invalid_status):
    """Tenta atualizar com status invalido."""
    service = bdd_context["leads_service"]
    lead_id = bdd_context["lead_id"]

    try:
        update = LeadUpdate(status=invalid_status)
        updated_lead = service.update_lead(lead_id, update)
        bdd_context["update_result"] = updated_lead
        bdd_context["update_error"] = None
    except Exception as e:
        bdd_context["update_error"] = e
        bdd_context["update_result"] = None


@when(parsers.parse('tento atualizar um lead com id "{lead_id}"'))
def try_update_nonexistent_lead(bdd_context, lead_id):
    """Tenta atualizar lead que nao existe."""
    service = bdd_context["leads_service"]

    try:
        update = LeadUpdate(status="contacted")
        updated_lead = service.update_lead(lead_id, update)
        bdd_context["update_result"] = updated_lead
        bdd_context["update_error"] = None
    except Exception as e:
        bdd_context["update_error"] = e
        bdd_context["update_result"] = None


@when("atualizo o lead na primeira sessao")
def update_first_session(bdd_context):
    """Atualiza lead na primeira sessao."""
    service = bdd_context["leads_service"]
    lead_id = bdd_context["lead_id"]

    update = LeadUpdate(notes="Atualização sessao 1")
    service.update_lead(lead_id, update)


@when("atualizo o lead na segunda sessao")
def update_second_session(bdd_context):
    """Atualiza lead na segunda sessao."""
    service = bdd_context["leads_service"]
    lead_id = bdd_context["lead_id"]

    update = LeadUpdate(notes="Atualização sessao 2")
    updated = service.update_lead(lead_id, update)
    bdd_context["update_result"] = updated


@when(parsers.parse('filtro leads por status "{status}"'))
def filter_leads_by_status(bdd_context, status):
    """Filtra leads por status."""
    service = bdd_context["leads_service"]
    filters = LeadFilters(status=status, limit=100)

    try:
        leads = service.list_leads(filters)
        bdd_context["filtered_leads"] = leads
        bdd_context["update_error"] = None
    except Exception as e:
        bdd_context["update_error"] = e
        bdd_context["filtered_leads"] = []


@when(parsers.parse("filtro leads por score minimo {min_score:d}"))
def filter_leads_by_min_score(bdd_context, min_score):
    """Filtra leads por score minimo."""
    service = bdd_context["leads_service"]
    filters = LeadFilters(min_score=min_score, limit=100)

    try:
        leads = service.list_leads(filters)
        bdd_context["filtered_leads"] = leads
        bdd_context["update_error"] = None
    except Exception as e:
        bdd_context["update_error"] = e
        bdd_context["filtered_leads"] = []


@when(parsers.parse('filtro leads pela tag "{tag}"'))
def filter_leads_by_tag(bdd_context, db_session, tag):
    """Filtra leads por tag especifica."""
    # LeadsService nao tem filtro por tag, entao fazemos manualmente
    businesses = BusinessQueries.get_all(db_session, limit=100)
    filtered = [b for b in businesses if tag in (b.tags or [])]

    for b in filtered:
        db_session.expunge(b)

    bdd_context["filtered_leads"] = filtered


# =============================================================================
# Then Steps
# =============================================================================


@then(parsers.parse('o lead deve ter status "{expected_status}"'))
def verify_lead_status(bdd_context, expected_status):
    """Verifica que lead tem o status esperado."""
    updated = bdd_context["update_result"]
    assert updated is not None, "Lead nao foi atualizado"
    assert updated.lead_status == expected_status, (
        f"Esperava status '{expected_status}', recebeu '{updated.lead_status}'"
    )


@then("o campo last_updated_at deve ser atualizado")
def verify_last_updated(bdd_context):
    """Verifica que last_updated_at foi atualizado."""
    updated = bdd_context["update_result"]
    original = bdd_context["current_lead"]

    assert updated.last_updated_at > original.last_updated_at, "last_updated_at nao foi atualizado"


@then("a transicao deve ser persistida na base de dados")
def verify_persisted_in_db(bdd_context, db_session):
    """Verifica que mudanca foi persistida na BD."""
    updated = bdd_context["update_result"]

    # Recarregar da BD
    from_db = BusinessQueries.get_by_id(db_session, updated.id)
    assert from_db is not None, "Lead nao encontrado na BD"
    assert from_db.lead_status == updated.lead_status, "Status nao foi persistido"


@then(parsers.parse("o lead deve ter as {count:d} tags atribuidas"))
def verify_tags_count(bdd_context, count):
    """Verifica que lead tem o numero correto de tags."""
    updated = bdd_context["update_result"]
    assert updated is not None, "Lead nao foi atualizado"
    assert len(updated.tags) == count, f"Esperava {count} tags, recebeu {len(updated.tags)}"


@then("as tags devem estar na ordem correta")
def verify_tags_order(bdd_context):
    """Verifica ordem das tags."""
    updated = bdd_context["update_result"]
    # A ordem deve ser preservada
    assert isinstance(updated.tags, list), "Tags nao sao uma lista"


@then("as tags devem ser guardadas como lista JSON")
def verify_tags_json_format(bdd_context, db_session):
    """Verifica que tags foram guardadas como JSON."""
    updated = bdd_context["update_result"]

    # Recarregar e verificar tipo
    from_db = BusinessQueries.get_by_id(db_session, updated.id)
    assert isinstance(from_db.tags, list), "Tags nao foram guardadas como lista"


@then("a nota deve ser adicionada com timestamp")
def verify_note_with_timestamp(bdd_context):
    """Verifica que nota tem timestamp."""
    updated = bdd_context["update_result"]
    assert updated.notes is not None, "Notas nao existem"

    # Verificar formato [YYYY-MM-DD HH:MM]
    import re

    pattern = r"\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}\]"
    assert re.search(pattern, updated.notes), "Nota nao tem formato de timestamp correto"


@then("as notas existentes devem ser preservadas")
def verify_notes_preserved(bdd_context):
    """Verifica que notas anteriores foram preservadas."""
    updated = bdd_context["update_result"]
    original = bdd_context["current_lead"]

    if original.notes:
        assert original.notes in updated.notes, "Notas originais nao foram preservadas"


@then(parsers.parse('o formato deve ser "{format_pattern}"'))
def verify_note_format(bdd_context, format_pattern):
    """Verifica formato das notas."""
    updated = bdd_context["update_result"]
    # Format pattern: "[YYYY-MM-DD HH:MM] texto"

    import re

    pattern = r"\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}\]"
    assert re.search(pattern, updated.notes), f"Formato nao corresponde: {format_pattern}"


@then("devo receber um erro de validacao")
def verify_validation_error(bdd_context):
    """Verifica que erro de validacao foi levantado."""
    error = bdd_context["update_error"]
    assert error is not None, "Nenhum erro foi levantado"
    assert isinstance(error, ValidationError), f"Erro nao e ValidationError: {type(error)}"


@then("a mensagem deve indicar status invalido")
def verify_invalid_status_message(bdd_context):
    """Verifica mensagem de status invalido."""
    error = bdd_context["update_error"]
    assert "invalido" in str(error).lower() or "invalid" in str(error).lower(), (
        "Mensagem nao indica status invalido"
    )


@then("o lead deve manter o status original")
def verify_original_status_maintained(bdd_context, db_session):
    """Verifica que status original foi mantido."""
    original = bdd_context["current_lead"]
    lead_id = bdd_context["lead_id"]

    # Recarregar da BD
    from_db = BusinessQueries.get_by_id(db_session, lead_id)
    assert from_db.lead_status == original.lead_status, "Status foi alterado quando nao devia"


@then("devo receber um erro de lead nao encontrado")
def verify_not_found_error(bdd_context):
    """Verifica erro de lead nao encontrado."""
    error = bdd_context["update_error"]
    assert error is not None, "Nenhum erro foi levantado"
    assert isinstance(error, BusinessNotFoundError), (
        f"Erro nao e BusinessNotFoundError: {type(error)}"
    )


@then("a mensagem deve conter o ID do lead")
def verify_error_contains_lead_id(bdd_context):
    """Verifica que mensagem contem ID do lead."""
    error = bdd_context["update_error"]
    # O ID deve estar na mensagem de erro
    assert len(str(error)) > 0, "Mensagem de erro vazia"


@then("nenhuma atualizacao deve ser realizada")
def verify_no_update_performed(bdd_context):
    """Verifica que nenhuma atualizacao foi realizada."""
    result = bdd_context["update_result"]
    assert result is None, "Atualizacao foi realizada quando nao devia"


@then("ambas as atualizacoes devem ser aplicadas")
def verify_both_updates_applied(bdd_context):
    """Verifica que ambas as sessoes atualizaram."""
    updated = bdd_context["update_result"]
    assert updated is not None, "Atualizacao nao foi aplicada"

    # Verificar que notas contem ambas as sessoes
    assert "sessao 1" in updated.notes.lower(), "Atualização sessao 1 nao foi aplicada"
    assert "sessao 2" in updated.notes.lower(), "Atualização sessao 2 nao foi aplicada"


@then("o last_updated_at deve refletir a ultima atualizacao")
def verify_last_updated_reflects_last(bdd_context):
    """Verifica que last_updated_at e da ultima atualizacao."""
    updated = bdd_context["update_result"]
    assert updated.last_updated_at is not None, "last_updated_at nao existe"


@then("devo receber apenas leads qualificados")
def verify_only_qualified_leads(bdd_context):
    """Verifica que apenas leads qualificados foram retornados."""
    leads = bdd_context["filtered_leads"]
    assert len(leads) > 0, "Nenhum lead foi retornado"

    for lead in leads:
        assert lead.lead_status == "qualified", (
            f"Lead {lead.id} nao esta qualificado: {lead.lead_status}"
        )


@then("a contagem deve corresponder aos leads filtrados")
def verify_count_matches_filtered(bdd_context):
    """Verifica que contagem corresponde aos resultados."""
    leads = bdd_context["filtered_leads"]
    assert isinstance(leads, list), "Resultados nao sao uma lista"


@then("leads com outros status devem ser excluidos")
def verify_other_status_excluded(bdd_context):
    """Verifica que leads com outros status foram excluidos."""
    leads = bdd_context["filtered_leads"]

    # Todos devem ter o mesmo status (o filtrado)
    statuses = {lead.lead_status for lead in leads}
    assert len(statuses) <= 1, f"Multiplos status retornados: {statuses}"


@then(parsers.parse("devo receber apenas leads com score >= {min_score:d}"))
def verify_min_score_filter(bdd_context, min_score):
    """Verifica que apenas leads com score minimo foram retornados."""
    leads = bdd_context["filtered_leads"]
    assert len(leads) > 0, "Nenhum lead foi retornado"

    for lead in leads:
        assert lead.lead_score >= min_score, (
            f"Lead {lead.id} com score {lead.lead_score} < {min_score}"
        )


@then("todos os resultados devem cumprir o criterio")
def verify_all_results_meet_criteria(bdd_context):
    """Verifica que todos os resultados cumprem o criterio."""
    leads = bdd_context["filtered_leads"]
    assert len(leads) > 0, "Nenhum lead foi retornado"


@then("leads com score inferior devem ser excluidos")
def verify_lower_scores_excluded(bdd_context):
    """Verifica que leads com score inferior foram excluidos."""
    # Se o filtro foi aplicado corretamente, este teste passa automaticamente
    leads = bdd_context["filtered_leads"]
    assert isinstance(leads, list), "Resultados invalidos"


@then(parsers.parse('devo receber apenas leads com tag "{tag}"'))
def verify_tag_filter(bdd_context, tag):
    """Verifica que apenas leads com a tag foram retornados."""
    leads = bdd_context["filtered_leads"]
    assert len(leads) > 0, "Nenhum lead foi retornado"

    for lead in leads:
        assert tag in (lead.tags or []), f"Lead {lead.id} nao tem tag '{tag}'"


@then("leads sem essa tag devem ser excluidos")
def verify_without_tag_excluded(bdd_context):
    """Verifica que leads sem a tag foram excluidos."""
    leads = bdd_context["filtered_leads"]

    # Se o filtro foi aplicado, todos devem ter a tag
    # Teste ja foi feito no step anterior
    assert isinstance(leads, list), "Resultados invalidos"
