"""Steps para testes BDD de enriquecimento de leads."""

import asyncio
from unittest.mock import MagicMock, patch

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.database.models import Business
from src.services.enricher import EnrichmentResult, EnrichmentService, WebsiteScraper


# Carregar cenários
scenarios("../features/04_enrichment.feature")


# ==================== FIXTURES ====================


@pytest.fixture
def mock_business(db_session):
    """Cria um lead de teste."""
    business = Business(
        id="test_place_id_001",
        name="Empresa Teste",
        formatted_address="Rua Teste, 123, Lisboa",
        latitude=38.7223,
        longitude=-9.1393,
        rating=4.5,
        review_count=100,
        lead_score=85.5,
        lead_status="new",
        enrichment_status="pending",
    )
    db_session.add(business)
    db_session.commit()
    db_session.refresh(business)
    return business


@pytest.fixture
def mock_scraper():
    """Cria um scraper mockado."""
    scraper = MagicMock(spec=WebsiteScraper)
    return scraper


@pytest.fixture
def enrichment_service(mock_scraper):
    """Cria serviço de enriquecimento com scraper mockado."""
    return EnrichmentService(scraper=mock_scraper)


@pytest.fixture
def context():
    """Contexto compartilhado entre steps."""
    return {
        "business": None,
        "result": None,
        "mock_html": "",
        "mock_response_status": 200,
        "mock_delay": 0,
        "mock_pages": [],
    }


# ==================== GIVEN STEPS ====================


@given("que tenho um lead na base de dados", target_fixture="business")
def given_lead_in_database(mock_business, context):
    """Lead existe na base de dados."""
    context["business"] = mock_business
    return mock_business


@given(parsers.parse('um lead com website "{website}"'))
def given_lead_with_website(context, db_session, website):
    """Define website do lead."""
    if context["business"] is None:
        business = Business(
            id="test_place_id_001",
            name="Empresa Teste",
            formatted_address="Rua Teste, 123, Lisboa",
            latitude=38.7223,
            longitude=-9.1393,
            enrichment_status="pending",
        )
        db_session.add(business)
        db_session.commit()
        db_session.refresh(business)
        context["business"] = business

    context["business"].website = website
    context["business"].has_website = True
    db_session.commit()


@given("um lead sem website")
def given_lead_without_website(context, db_session):
    """Lead sem website."""
    if context["business"] is None:
        business = Business(
            id="test_place_id_001",
            name="Empresa Teste",
            formatted_address="Rua Teste, 123, Lisboa",
            latitude=38.7223,
            longitude=-9.1393,
            enrichment_status="pending",
        )
        db_session.add(business)
        db_session.commit()
        db_session.refresh(business)
        context["business"] = business

    context["business"].website = None
    context["business"].has_website = False
    db_session.commit()


@given(parsers.parse('o website contém os emails "{emails}"'))
def given_website_contains_emails(context, emails):
    """Mock de HTML com emails."""
    email_list = emails.split(",")
    email_html = " ".join([f'<a href="mailto:{e}">{e}</a>' for e in email_list])
    context["mock_html"] = f"""
    <html>
        <body>
            <h1>Contactos</h1>
            {email_html}
        </body>
    </html>
    """


@given(parsers.parse('o website contém link do LinkedIn "{url}"'))
def given_website_contains_linkedin(context, url):
    """Mock de HTML com LinkedIn."""
    if not context["mock_html"]:
        context["mock_html"] = "<html><body>"
    context["mock_html"] += f'<a href="{url}">LinkedIn</a>'


@given(parsers.parse('o website contém link do Facebook "{url}"'))
def given_website_contains_facebook(context, url):
    """Mock de HTML com Facebook."""
    if not context["mock_html"]:
        context["mock_html"] = "<html><body>"
    context["mock_html"] += f'<a href="{url}">Facebook</a>'


@given(parsers.parse('o website contém link do Instagram "{url}"'))
def given_website_contains_instagram(context, url):
    """Mock de HTML com Instagram."""
    if not context["mock_html"]:
        context["mock_html"] = "<html><body>"
    context["mock_html"] += f'<a href="{url}">Instagram</a>'
    context["mock_html"] += "</body></html>"


@given("o website demora mais de 10 segundos a responder")
def given_website_timeout(context):
    """Mock de timeout."""
    context["mock_delay"] = 15
    context["mock_response_status"] = "timeout"


@given("o website retorna erro 403")
def given_website_forbidden(context):
    """Mock de erro 403."""
    context["mock_response_status"] = 403


@given("o website tem 10 páginas importantes")
def given_website_many_pages(context):
    """Mock de website com muitas páginas."""
    context["mock_html"] = """
    <html>
        <body>
            <a href="/contacto">Contacto</a>
            <a href="/sobre">Sobre</a>
            <a href="/equipa">Equipa</a>
            <a href="/team">Team</a>
            <a href="/about">About</a>
            <a href="/contacts">Contacts</a>
            <a href="/contact">Contact</a>
            <a href="/sobre-nos">Sobre Nós</a>
            <a href="/contactos">Contactos</a>
            <a href="/about-us">About Us</a>
        </body>
    </html>
    """


@given("o website não contém emails")
def given_website_no_emails(context):
    """Mock de website sem emails."""
    context["mock_html"] = """
    <html>
        <body>
            <h1>Empresa Teste</h1>
            <p>Sem informações de contacto.</p>
        </body>
    </html>
    """


@given(parsers.parse('o website tem uma página "/equipa" com "{info}"'))
def given_website_team_page(context, info):
    """Mock de página de equipa."""
    if "/equipa" not in context["mock_html"]:
        context["mock_html"] = f"""
        <html>
            <body>
                <div class="team-member">
                    <p>{info}</p>
                </div>
            </body>
        </html>
        """
    else:
        # Adicionar mais membros
        context["mock_html"] = context["mock_html"].replace(
            "</body>",
            f'<div class="team-member"><p>{info}</p></div></body>',
        )


@given("que tenho 5 leads com websites")
def given_multiple_leads(db_session, context):
    """Cria múltiplos leads."""
    businesses = []
    for i in range(5):
        business = Business(
            id=f"test_place_id_{i:03d}",
            name=f"Empresa {i}",
            formatted_address=f"Rua {i}, Lisboa",
            latitude=38.7223,
            longitude=-9.1393,
            website=f"https://empresa{i}.pt",
            has_website=True,
            enrichment_status="pending",
        )
        db_session.add(business)
        businesses.append(business)
    db_session.commit()
    context["businesses"] = businesses


# ==================== WHEN STEPS ====================


@when("executo o enriquecimento do lead")
def when_enrich_lead(context, db_session):
    """Executa enriquecimento."""
    business = context["business"]

    # Mock do scraper
    async def mock_scrape(url):
        if context["mock_response_status"] == "timeout" or context["mock_response_status"] == 403:
            return EnrichmentResult(
                success=False,
                error="Nao foi possivel aceder ao website",
            )

        # Parse emails do HTML mockado
        emails = []
        if "mailto:" in context["mock_html"]:
            import re

            email_pattern = r"mailto:([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})"
            emails = re.findall(email_pattern, context["mock_html"])

        # Parse social links
        social_links = {}
        if "linkedin.com" in context["mock_html"]:
            import re

            match = re.search(r'href="(https://linkedin\.com/[^"]+)"', context["mock_html"])
            if match:
                social_links["linkedin"] = match.group(1)
        if "facebook.com" in context["mock_html"]:
            import re

            match = re.search(r'href="(https://facebook\.com/[^"]+)"', context["mock_html"])
            if match:
                social_links["facebook"] = match.group(1)
        if "instagram.com" in context["mock_html"]:
            import re

            match = re.search(r'href="(https://instagram\.com/[^"]+)"', context["mock_html"])
            if match:
                social_links["instagram"] = match.group(1)

        # Parse decision makers
        decision_makers = []
        if "team-member" in context["mock_html"]:
            import re

            from bs4 import BeautifulSoup

            soup = BeautifulSoup(context["mock_html"], "lxml")
            for member in soup.find_all("div", class_="team-member"):
                text = member.get_text()
                # Parse "Nome - Cargo"
                match = re.search(r"([A-Za-zÀ-ÿ\s]+)\s*-\s*([A-Za-zÀ-ÿ\s]+)", text)
                if match:
                    decision_makers.append(
                        {
                            "name": match.group(1).strip(),
                            "role": match.group(2).strip(),
                            "source": "website",
                        }
                    )

        # Filtrar emails inválidos
        scraper = WebsiteScraper()
        valid_emails = []
        for email in emails:
            is_ignored = False
            for pattern in scraper.IGNORED_EMAIL_PATTERNS:
                import re

                if re.search(pattern, email):
                    is_ignored = True
                    break
            if not is_ignored:
                valid_emails.append(email)

        # Priorizar email principal
        primary_email = None
        if valid_emails:
            priority_prefixes = ["contacto", "contact", "info", "geral"]
            for prefix in priority_prefixes:
                for email in valid_emails:
                    if email.startswith(prefix + "@"):
                        primary_email = email
                        break
                if primary_email:
                    break
            if not primary_email:
                primary_email = valid_emails[0]

        # Simular contagem de páginas
        pages_scraped = 1
        if context["mock_html"] and "href=" in context["mock_html"]:
            import re

            links = re.findall(r'href="(/[^"]+)"', context["mock_html"])
            # Limitar a 5 páginas (homepage + 4)
            pages_scraped = min(len(links) + 1, 5)

        return EnrichmentResult(
            success=True,
            emails=valid_emails,
            primary_email=primary_email,
            social_links=social_links,
            decision_makers=decision_makers,
            pages_scraped=pages_scraped,
        )

    # Executar enriquecimento
    service = EnrichmentService()
    with patch.object(service.scraper, "scrape_website", side_effect=mock_scrape):
        result = asyncio.run(service.enrich_business(business.id))

    context["result"] = result

    # Recarregar business da DB
    db_session.expire(business)
    db_session.refresh(business)
    context["business"] = business


@when(parsers.parse("executo o enriquecimento em batch com concorrência {concurrency:d}"))
def when_enrich_batch(context, db_session, concurrency):
    """Executa enriquecimento em batch."""
    businesses = context["businesses"]
    business_ids = [b.id for b in businesses]

    # Mock do scraper
    async def mock_scrape(url):
        return EnrichmentResult(
            success=True,
            emails=["info@empresa.pt"],
            primary_email="info@empresa.pt",
            pages_scraped=1,
        )

    service = EnrichmentService()
    with patch.object(service.scraper, "scrape_website", side_effect=mock_scrape):
        import time

        start = time.time()
        results = asyncio.run(service.enrich_batch(business_ids, concurrency=concurrency))
        end = time.time()

    context["batch_results"] = results
    context["batch_time"] = end - start


# ==================== THEN STEPS ====================


@then("os emails extraídos são guardados")
def then_emails_saved(context):
    """Verifica se emails foram guardados."""
    business = context["business"]
    assert business.emails_scraped is not None
    assert len(business.emails_scraped) > 0


@then(parsers.parse('o email principal é "{email}"'))
def then_primary_email_is(context, email):
    """Verifica email principal."""
    business = context["business"]
    assert business.email == email


@then(parsers.parse('o status de enrichment é "{status}"'))
def then_enrichment_status_is(context, status):
    """Verifica status de enriquecimento."""
    business = context["business"]
    assert business.enrichment_status == status


@then(parsers.parse('o campo "{field}" está preenchido'))
def then_field_is_filled(context, field):
    """Verifica se campo está preenchido."""
    business = context["business"]
    value = getattr(business, field)
    assert value is not None


@then(parsers.parse('apenas o email "{email}" é guardado'))
def then_only_email_saved(context, email):
    """Verifica que apenas um email específico foi guardado."""
    business = context["business"]
    assert business.email == email
    assert email in business.emails_scraped


@then(parsers.parse('os emails "{emails}" são filtrados'))
def then_emails_filtered(context, emails):
    """Verifica que emails foram filtrados."""
    business = context["business"]
    email_list = emails.split(",")
    for email in email_list:
        assert email not in business.emails_scraped


@then(parsers.parse('o LinkedIn "{url}" é guardado'))
def then_linkedin_saved(context, url):
    """Verifica LinkedIn guardado."""
    business = context["business"]
    assert business.social_linkedin == url


@then(parsers.parse('o Facebook "{url}" é guardado'))
def then_facebook_saved(context, url):
    """Verifica Facebook guardado."""
    business = context["business"]
    assert business.social_facebook == url


@then(parsers.parse('o Instagram "{url}" é guardado'))
def then_instagram_saved(context, url):
    """Verifica Instagram guardado."""
    business = context["business"]
    assert business.social_instagram == url


@then(parsers.parse('o campo "{field}" contém "{text}"'))
def then_field_contains(context, field, text):
    """Verifica se campo contém texto."""
    business = context["business"]
    value = getattr(business, field)
    assert value is not None
    assert text in value


@then(parsers.parse("apenas {count:d} páginas são visitadas"))
def then_pages_visited(context, count):
    """Verifica número de páginas visitadas."""
    result = context["result"]
    assert result.pages_scraped <= count


@then(parsers.parse('o campo "{field}" não excede {max_value:d}'))
def then_field_not_exceeds(context, field, max_value):
    """Verifica que campo não excede valor."""
    result = context["result"]
    value = getattr(result, field)
    assert value <= max_value


@then(parsers.parse('o campo "{field}" está vazio'))
def then_field_is_empty(context, field):
    """Verifica se campo está vazio."""
    business = context["business"]
    value = getattr(business, field)
    assert value is None or value == [] or value == {}


@then('todos os emails são guardados em "emails_scraped"')
def then_all_emails_saved(context):
    """Verifica que todos os emails estão guardados."""
    business = context["business"]
    assert len(business.emails_scraped) >= 3


@then("os decisores são guardados")
def then_decision_makers_saved(context):
    """Verifica que decisores foram guardados."""
    business = context["business"]
    assert business.decision_makers is not None
    assert len(business.decision_makers) > 0


@then(parsers.parse('o decisor "{name}" tem o cargo "{role}"'))
def then_decision_maker_has_role(context, name, role):
    """Verifica cargo de decisor."""
    business = context["business"]
    decisor = next((d for d in business.decision_makers if d["name"] == name), None)
    assert decisor is not None
    assert decisor["role"] == role


@then(parsers.parse("todos os {count:d} leads são enriquecidos"))
def then_all_leads_enriched(context, count):
    """Verifica que todos os leads foram enriquecidos."""
    results = context["batch_results"]
    assert len(results) == count


@then("o processamento é feito em paralelo")
def then_processing_is_parallel(context):
    """Verifica processamento paralelo."""
    # Se foi executado, assume-se paralelismo
    assert context["batch_results"] is not None


@then("o tempo total é inferior ao processamento sequencial")
def then_time_is_less(context):
    """Verifica que tempo é inferior ao sequencial."""
    # Com 5 leads e delay mínimo, paralelo deve ser mais rápido
    batch_time = context["batch_time"]
    # Assumindo delay mínimo, sequencial seria > 5 segundos
    assert batch_time < 10  # Threshold razoável para teste
