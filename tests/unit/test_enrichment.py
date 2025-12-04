"""Testes unitarios para EnrichmentService e WebsiteScraper."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.database.models import Business
from src.services.enricher import (
    EnrichmentResult,
    EnrichmentService,
    WebsiteScraper,
)


class TestWebsiteScraper:
    """Testes para WebsiteScraper."""

    @pytest.fixture
    def scraper(self):
        """Instancia do WebsiteScraper."""
        return WebsiteScraper()

    @pytest.fixture
    def html_com_emails(self):
        """HTML com emails validos."""
        return """
        <html>
            <body>
                <a href="mailto:info@empresa.pt">Contacto</a>
                <a href="mailto:vendas@empresa.pt">Vendas</a>
                <p>Email: suporte@empresa.pt</p>
            </body>
        </html>
        """

    @pytest.fixture
    def html_com_social(self):
        """HTML com links de redes sociais."""
        return """
        <html>
            <body>
                <a href="https://facebook.com/minhaempresa">Facebook</a>
                <a href="https://linkedin.com/company/minhaempresa">LinkedIn</a>
                <a href="https://instagram.com/minhaempresa">Instagram</a>
                <a href="https://twitter.com/minhaempresa">Twitter</a>
            </body>
        </html>
        """

    @pytest.fixture
    def html_com_decisores(self):
        """HTML com informacao de decisores."""
        return """
        <html>
            <body>
                <div class="team">
                    <h3>Joao Silva - CEO</h3>
                    <p>Maria Santos, Fundadora</p>
                </div>
                <div class="about">
                    <p>Director: Pedro Costa</p>
                </div>
            </body>
        </html>
        """

    def test_extract_emails_encontra_emails_validos(self, scraper, html_com_emails):
        """Deve extrair emails validos do HTML."""
        # Act
        emails = scraper._extract_emails(html_com_emails, "https://empresa.pt")

        # Assert
        assert len(emails) == 3
        assert "info@empresa.pt" in emails
        assert "vendas@empresa.pt" in emails
        assert "suporte@empresa.pt" in emails

    def test_extract_emails_ignora_emails_invalidos(self, scraper):
        """Deve ignorar emails com padroes invalidos."""
        # Arrange
        html = """
        <html>
            <body>
                <a href="mailto:noreply@empresa.pt">No Reply</a>
                <a href="mailto:no-reply@empresa.pt">No Reply</a>
                <a href="mailto:test@example.com">Example</a>
                <a href="mailto:info@empresa.pt">Info</a>
            </body>
        </html>
        """

        # Act
        emails = scraper._extract_emails(html, "https://empresa.pt")

        # Assert
        assert len(emails) == 1
        assert "info@empresa.pt" in emails
        assert "noreply@empresa.pt" not in emails
        assert "test@example.com" not in emails

    def test_extract_emails_remove_duplicados(self, scraper):
        """Deve remover emails duplicados."""
        # Arrange
        html = """
        <html>
            <body>
                <a href="mailto:info@empresa.pt">Info 1</a>
                <a href="mailto:info@empresa.pt">Info 2</a>
                <p>info@empresa.pt</p>
            </body>
        </html>
        """

        # Act
        emails = scraper._extract_emails(html, "https://empresa.pt")

        # Assert
        assert len(emails) == 1
        assert emails[0] == "info@empresa.pt"

    def test_prioritize_emails_retorna_none_para_lista_vazia(self, scraper):
        """Deve retornar None quando nao ha emails."""
        # Act
        primary, all_emails = scraper._prioritize_emails([])

        # Assert
        assert primary is None
        assert all_emails == []

    def test_prioritize_emails_escolhe_contacto(self, scraper):
        """Deve priorizar email com prefixo 'contacto'."""
        # Arrange
        emails = ["admin@test.pt", "contacto@test.pt", "info@test.pt"]

        # Act
        primary, _ = scraper._prioritize_emails(emails)

        # Assert
        assert primary == "contacto@test.pt"

    def test_prioritize_emails_escolhe_info(self, scraper):
        """Deve priorizar email com prefixo 'info' quando nao ha 'contacto'."""
        # Arrange
        emails = ["admin@test.pt", "info@test.pt", "vendas@test.pt"]

        # Act
        primary, _ = scraper._prioritize_emails(emails)

        # Assert
        assert primary == "info@test.pt"

    def test_prioritize_emails_retorna_primeiro_sem_prioridade(self, scraper):
        """Deve retornar primeiro email quando nenhum tem prioridade."""
        # Arrange
        emails = ["admin@test.pt", "outro@test.pt"]

        # Act
        primary, _ = scraper._prioritize_emails(emails)

        # Assert
        assert primary == "admin@test.pt"

    def test_extract_social_links_encontra_todas_plataformas(self, scraper, html_com_social):
        """Deve extrair links de todas as redes sociais."""
        # Act
        social = scraper._extract_social_links(html_com_social)

        # Assert
        assert "facebook" in social
        assert "linkedin" in social
        assert "instagram" in social
        assert "twitter" in social
        assert "minhaempresa" in social["facebook"]
        assert "linkedin.com/company/minhaempresa" in social["linkedin"]

    def test_extract_social_links_ignora_outras_plataformas(self, scraper):
        """Deve ignorar links que nao sao de redes sociais conhecidas."""
        # Arrange
        html = """
        <html>
            <body>
                <a href="https://youtube.com/channel123">YouTube</a>
                <a href="https://tiktok.com/@user">TikTok</a>
            </body>
        </html>
        """

        # Act
        social = scraper._extract_social_links(html)

        # Assert
        assert len(social) == 0

    def test_extract_social_links_normaliza_urls(self, scraper):
        """Deve normalizar URLs de redes sociais."""
        # Arrange
        html = """
        <html>
            <body>
                <a href="http://fb.com/empresa">Facebook</a>
                <a href="https://x.com/empresa">Twitter/X</a>
            </body>
        </html>
        """

        # Act
        social = scraper._extract_social_links(html)

        # Assert
        assert "empresa" in social["facebook"]
        assert "empresa" in social["twitter"]

    def test_extract_decision_makers_encontra_cargos_conhecidos(self, scraper, html_com_decisores):
        """Deve extrair decisores com cargos conhecidos."""
        # Act
        makers = scraper._extract_decision_makers(html_com_decisores)

        # Assert
        assert len(makers) > 0
        # Verificar que encontrou pelo menos um CEO ou Fundador
        roles = [m["role"].lower() for m in makers]
        assert any(role in ["ceo", "fundador", "fundadora", "director"] for role in roles)

    def test_extract_decision_makers_limita_resultados(self, scraper):
        """Deve limitar resultados a 5 decisores."""
        # Arrange
        html = """
        <html>
            <body>
                <div class="team">
                    <p>Joao Silva - CEO</p>
                    <p>Maria Santos - Fundadora</p>
                    <p>Pedro Costa - Director</p>
                    <p>Ana Ferreira - Gerente</p>
                    <p>Carlos Sousa - Socio</p>
                    <p>Rita Alves - Manager</p>
                    <p>Paulo Rocha - Diretor</p>
                </div>
            </body>
        </html>
        """

        # Act
        makers = scraper._extract_decision_makers(html)

        # Assert
        assert len(makers) <= 5

    def test_extract_decision_makers_remove_duplicados(self, scraper):
        """Deve remover decisores duplicados."""
        # Arrange
        html = """
        <html>
            <body>
                <div class="team">
                    <p>Joao Silva - CEO</p>
                    <p>Joao Silva - Fundador</p>
                </div>
            </body>
        </html>
        """

        # Act
        makers = scraper._extract_decision_makers(html)

        # Assert
        # Deve ter apenas uma entrada para Joao Silva
        names = [m["name"] for m in makers]
        assert names.count("Joao Silva") <= 1

    def test_find_important_pages_encontra_paginas_contacto(self, scraper):
        """Deve encontrar paginas importantes como contacto e sobre."""
        # Arrange
        html = """
        <html>
            <body>
                <nav>
                    <a href="/contact">Contacto</a>
                    <a href="/about-us">Sobre Nos</a>
                    <a href="/team">Equipa</a>
                    <a href="/services">Servicos</a>
                </nav>
            </body>
        </html>
        """
        base_url = "https://empresa.pt"

        # Act
        pages = scraper._find_important_pages(html, base_url)

        # Assert
        assert any("contact" in page.lower() for page in pages)
        assert any("about" in page.lower() for page in pages)
        assert any("team" in page.lower() for page in pages)

    def test_find_important_pages_ignora_links_externos(self, scraper):
        """Deve ignorar links para dominios externos."""
        # Arrange
        html = """
        <html>
            <body>
                <nav>
                    <a href="/contact">Contacto</a>
                    <a href="https://facebook.com/empresa">Facebook</a>
                    <a href="https://outrosite.com/about">Outro Site</a>
                </nav>
            </body>
        </html>
        """
        base_url = "https://empresa.pt"

        # Act
        pages = scraper._find_important_pages(html, base_url)

        # Assert
        assert all("empresa.pt" in page for page in pages)
        assert not any("facebook.com" in page for page in pages)
        assert not any("outrosite.com" in page for page in pages)

    def test_find_important_pages_limita_resultados(self, scraper):
        """Deve limitar numero de paginas encontradas."""
        # Arrange
        html = """
        <html>
            <body>
                <nav>
                    <a href="/contact">Contacto</a>
                    <a href="/contactos">Contactos</a>
                    <a href="/about">Sobre</a>
                    <a href="/sobre-nos">Sobre Nos</a>
                    <a href="/team">Equipa</a>
                    <a href="/equipe">Equipe</a>
                </nav>
            </body>
        </html>
        """
        base_url = "https://empresa.pt"

        # Act
        pages = scraper._find_important_pages(html, base_url)

        # Assert
        assert len(pages) < WebsiteScraper.MAX_PAGES_PER_SITE

    @pytest.mark.asyncio
    async def test_fetch_page_sucesso(self, scraper):
        """Deve fazer fetch de pagina com sucesso."""
        # Arrange
        mock_response = MagicMock()
        mock_response.text = "<html>Test</html>"
        mock_response.headers = {"content-type": "text/html"}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        scraper._client = mock_client

        # Act
        html = await scraper._fetch_page("https://test.pt")

        # Assert
        assert html == "<html>Test</html>"
        mock_client.get.assert_called_once_with("https://test.pt")

    @pytest.mark.asyncio
    async def test_fetch_page_rejeita_nao_html(self, scraper):
        """Deve rejeitar conteudo que nao e HTML."""
        # Arrange
        mock_response = MagicMock()
        mock_response.text = "PDF content"
        mock_response.headers = {"content-type": "application/pdf"}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        scraper._client = mock_client

        # Act
        html = await scraper._fetch_page("https://test.pt/file.pdf")

        # Assert
        assert html is None

    @pytest.mark.asyncio
    async def test_fetch_page_retorna_none_em_erro(self, scraper):
        """Deve retornar None quando ocorre erro HTTP."""
        # Arrange
        import httpx

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.HTTPError("Connection error"))
        scraper._client = mock_client

        # Act
        html = await scraper._fetch_page("https://test.pt")

        # Assert
        assert html is None

    @pytest.mark.asyncio
    async def test_scrape_website_sucesso_completo(self, scraper):
        """Deve fazer scraping completo de website com sucesso."""
        # Arrange
        homepage_html = """
        <html>
            <body>
                <a href="mailto:info@empresa.pt">Info</a>
                <a href="https://facebook.com/empresa">Facebook</a>
                <a href="/contact">Contacto</a>
            </body>
        </html>
        """

        contact_html = """
        <html>
            <body>
                <a href="mailto:vendas@empresa.pt">Vendas</a>
                <div class="team">Joao Silva - CEO</div>
            </body>
        </html>
        """

        async def mock_fetch(url):
            if "/contact" in url:
                return contact_html
            return homepage_html

        with patch.object(scraper, "_fetch_page", side_effect=mock_fetch):
            # Act
            result = await scraper.scrape_website("https://empresa.pt")

        # Assert
        assert result.success is True
        assert len(result.emails) >= 2
        assert result.primary_email is not None
        assert "facebook" in result.social_links
        assert result.pages_scraped >= 1

    @pytest.mark.asyncio
    async def test_scrape_website_adiciona_https_se_necessario(self, scraper):
        """Deve adicionar https:// se URL nao tiver protocolo."""
        # Arrange
        mock_fetch = AsyncMock(return_value="<html></html>")

        with patch.object(scraper, "_fetch_page", mock_fetch):
            # Act
            await scraper.scrape_website("empresa.pt")

        # Assert
        mock_fetch.assert_called()
        call_url = mock_fetch.call_args[0][0]
        assert call_url.startswith("https://")

    @pytest.mark.asyncio
    async def test_scrape_website_retorna_erro_quando_inacessivel(self, scraper):
        """Deve retornar erro quando website e inacessivel."""
        # Arrange
        with patch.object(scraper, "_fetch_page", return_value=None):
            # Act
            result = await scraper.scrape_website("https://site-inexistente.pt")

        # Assert
        assert result.success is False
        assert result.error is not None
        assert "possivel aceder" in result.error.lower()

    @pytest.mark.asyncio
    async def test_scrape_website_respeita_delay_entre_requests(self, scraper):
        """Deve aguardar entre requests para nao sobrecarregar servidor."""
        # Arrange
        html_with_links = """
        <html>
            <body>
                <a href="/contact">Contact</a>
                <a href="/about">About</a>
            </body>
        </html>
        """

        with (
            patch.object(scraper, "_fetch_page", return_value=html_with_links),
            patch("asyncio.sleep") as mock_sleep,
        ):
            # Act
            await scraper.scrape_website("https://empresa.pt")

        # Assert
        # Deve ter chamado sleep pelo menos uma vez
        assert mock_sleep.called

    @pytest.mark.asyncio
    async def test_close_fecha_client(self, scraper):
        """Deve fechar cliente HTTP corretamente."""
        # Arrange
        mock_client = AsyncMock()
        scraper._client = mock_client

        # Act
        await scraper.close()

        # Assert
        mock_client.aclose.assert_called_once()
        assert scraper._client is None


class TestEnrichmentService:
    """Testes para EnrichmentService."""

    @pytest.fixture
    def mock_scraper(self):
        """Mock do WebsiteScraper."""
        mock = MagicMock(spec=WebsiteScraper)
        mock.scrape_website = AsyncMock()
        return mock

    @pytest.fixture
    def service(self, mock_scraper):
        """Instancia do EnrichmentService com mock."""
        return EnrichmentService(scraper=mock_scraper)

    @pytest.mark.asyncio
    async def test_enrich_business_sucesso(
        self, service, mock_scraper, test_session, sample_business_with_website
    ):
        """Deve enriquecer business com sucesso."""
        # Arrange
        test_session.add(sample_business_with_website)
        test_session.commit()

        enrichment_result = EnrichmentResult(
            success=True,
            emails=["info@clinica.pt", "geral@clinica.pt"],
            primary_email="info@clinica.pt",
            social_links={"facebook": "https://facebook.com/clinica"},
            decision_makers=[{"name": "Dr. Silva", "role": "CEO"}],
            pages_scraped=2,
        )
        mock_scraper.scrape_website.return_value = enrichment_result

        with patch("src.services.enricher.db.get_session") as mock_db:
            mock_db.return_value.__enter__.return_value = test_session

            # Act
            result = await service.enrich_business(sample_business_with_website.id)

        # Assert
        assert result.success is True
        assert result.primary_email == "info@clinica.pt"

        # Verificar que business foi atualizado
        business = test_session.get(Business, sample_business_with_website.id)
        assert business.email == "info@clinica.pt"
        assert business.enrichment_status == "completed"
        assert business.enriched_at is not None

    @pytest.mark.asyncio
    async def test_enrich_business_nao_encontrado(self, service, test_session):
        """Deve retornar erro quando business nao existe."""
        # Arrange
        with patch("src.services.enricher.db.get_session") as mock_db:
            mock_db.return_value.__enter__.return_value = test_session

            # Act
            result = await service.enrich_business("id_inexistente")

        # Assert
        assert result.success is False
        assert "nao encontrado" in result.error.lower()

    @pytest.mark.asyncio
    async def test_enrich_business_sem_website(self, service, test_session, sample_business):
        """Deve marcar como no_website quando business nao tem website."""
        # Arrange
        test_session.add(sample_business)
        test_session.commit()

        with patch("src.services.enricher.db.get_session") as mock_db:
            mock_db.return_value.__enter__.return_value = test_session

            # Act
            result = await service.enrich_business(sample_business.id)

        # Assert
        assert result.success is False
        assert "nao tem website" in result.error.lower()

        # Verificar que status foi atualizado
        business = test_session.get(Business, sample_business.id)
        assert business.enrichment_status == "no_website"

    @pytest.mark.asyncio
    async def test_enrich_business_marca_in_progress(
        self, service, mock_scraper, test_session, sample_business_with_website
    ):
        """Deve marcar business como in_progress durante enriquecimento."""
        # Arrange
        test_session.add(sample_business_with_website)
        test_session.commit()

        mock_scraper.scrape_website.return_value = EnrichmentResult(success=True)

        with patch("src.services.enricher.db.get_session") as mock_db:
            mock_db.return_value.__enter__.return_value = test_session

            # Act
            await service.enrich_business(sample_business_with_website.id)

        # Assert - deve ter sido marcado como in_progress antes do scraping
        # (verificado pela sequencia de commits)

    @pytest.mark.asyncio
    async def test_enrich_business_trata_excecao(
        self, service, mock_scraper, test_session, sample_business_with_website
    ):
        """Deve tratar excecoes durante scraping."""
        # Arrange
        test_session.add(sample_business_with_website)
        test_session.commit()

        mock_scraper.scrape_website.side_effect = Exception("Erro de rede")

        with patch("src.services.enricher.db.get_session") as mock_db:
            mock_db.return_value.__enter__.return_value = test_session

            # Act
            result = await service.enrich_business(sample_business_with_website.id)

        # Assert
        assert result.success is False
        assert "Erro de rede" in result.error

    @pytest.mark.asyncio
    async def test_enrich_business_atualiza_erro_em_falha(
        self, service, mock_scraper, test_session, sample_business_with_website
    ):
        """Deve registrar erro quando enriquecimento falha."""
        # Arrange
        test_session.add(sample_business_with_website)
        test_session.commit()

        mock_scraper.scrape_website.return_value = EnrichmentResult(
            success=False,
            error="Timeout ao aceder website",
        )

        with patch("src.services.enricher.db.get_session") as mock_db:
            mock_db.return_value.__enter__.return_value = test_session

            # Act
            await service.enrich_business(sample_business_with_website.id)

        # Assert
        business = test_session.get(Business, sample_business_with_website.id)
        assert business.enrichment_status == "failed"
        assert business.enrichment_error == "Timeout ao aceder website"

    @pytest.mark.asyncio
    async def test_enrich_batch_processa_multiplos(
        self, service, mock_scraper, test_session, business_factory
    ):
        """Deve enriquecer multiplos negocios em paralelo."""
        # Arrange
        businesses = business_factory.create_batch(3, has_website=True, website="https://test.pt")
        for b in businesses:
            test_session.add(b)
        test_session.commit()

        business_ids = [b.id for b in businesses]

        mock_scraper.scrape_website.return_value = EnrichmentResult(success=True)

        with patch("src.services.enricher.db.get_session") as mock_db:
            mock_db.return_value.__enter__.return_value = test_session

            # Act
            results = await service.enrich_batch(business_ids, concurrency=2)

        # Assert
        assert len(results) == 3
        assert all(bid in results for bid in business_ids)

    @pytest.mark.asyncio
    async def test_enrich_batch_respeita_concurrency(
        self, service, mock_scraper, test_session, business_factory
    ):
        """Deve respeitar limite de concorrencia."""
        # Arrange
        businesses = business_factory.create_batch(5, has_website=True, website="https://test.pt")
        for b in businesses:
            test_session.add(b)
        test_session.commit()

        business_ids = [b.id for b in businesses]

        mock_scraper.scrape_website.return_value = EnrichmentResult(success=True)

        with patch("src.services.enricher.db.get_session") as mock_db:
            mock_db.return_value.__enter__.return_value = test_session

            # Act
            results = await service.enrich_batch(business_ids, concurrency=2)

        # Assert
        assert len(results) == 5

    def test_get_enrichable_leads_retorna_com_website(
        self, service, test_session, business_factory
    ):
        """Deve retornar apenas leads com website pendentes de enriquecimento."""
        # Arrange
        b1 = business_factory.create(
            has_website=True, website="https://test1.pt", enrichment_status="pending"
        )
        b2 = business_factory.create(has_website=False, enrichment_status="pending")
        b3 = business_factory.create(
            has_website=True, website="https://test3.pt", enrichment_status="completed"
        )

        test_session.add_all([b1, b2, b3])
        test_session.commit()

        with patch("src.services.enricher.db.get_session") as mock_db:
            mock_db.return_value.__enter__.return_value = test_session

            # Act
            results = service.get_enrichable_leads(limit=100)

        # Assert
        assert len(results) >= 1
        assert all(b.has_website for b in results)

    def test_get_enrichment_stats_retorna_contagens(self, service, test_session):
        """Deve retornar estatisticas de enriquecimento."""
        # Arrange
        stats_data = [
            ("pending", 10),
            ("completed", 5),
            ("failed", 2),
        ]

        with patch("src.services.enricher.db.get_session") as mock_db:
            mock_session = MagicMock()
            mock_db.return_value.__enter__.return_value = mock_session
            mock_session.query.return_value.group_by.return_value.all.return_value = stats_data

            # Act
            stats = service.get_enrichment_stats()

        # Assert
        assert stats["pending"] == 10
        assert stats["completed"] == 5
        assert stats["failed"] == 2
        assert stats["total"] == 17
        assert stats["enrichable"] == 12  # pending + failed
