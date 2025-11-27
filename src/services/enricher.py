"""Servico de enriquecimento de dados de leads."""

import asyncio
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from src.database.db import db
from src.database.models import Business


@dataclass
class EnrichmentResult:
    """Resultado do enriquecimento de um lead."""

    success: bool
    emails: list[str] = field(default_factory=list)
    primary_email: str | None = None
    social_links: dict[str, str] = field(default_factory=dict)
    decision_makers: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None
    pages_scraped: int = 0


class WebsiteScraper:
    """Scraper async para extrair dados de websites."""

    USER_AGENT = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    REQUEST_TIMEOUT = 10.0
    DELAY_BETWEEN_REQUESTS = 1.0
    MAX_PAGES_PER_SITE = 5

    # Padroes de emails a ignorar
    IGNORED_EMAIL_PATTERNS = [
        r"^noreply@",
        r"^no-reply@",
        r"^donotreply@",
        r"^mailer-daemon@",
        r"^postmaster@",
        r"@example\.com$",
        r"@sentry\.",
        r"@wixpress\.com$",
    ]

    # Padroes de redes sociais
    SOCIAL_PATTERNS = {
        "linkedin": [
            r"linkedin\.com/company/([^/?\s]+)",
            r"linkedin\.com/in/([^/?\s]+)",
        ],
        "facebook": [
            r"facebook\.com/([^/?\s]+)",
            r"fb\.com/([^/?\s]+)",
        ],
        "instagram": [
            r"instagram\.com/([^/?\s]+)",
        ],
        "twitter": [
            r"twitter\.com/([^/?\s]+)",
            r"x\.com/([^/?\s]+)",
        ],
    }

    # Paginas importantes para procurar
    IMPORTANT_PATHS = [
        "/contact",
        "/contacto",
        "/contactos",
        "/contacts",
        "/about",
        "/sobre",
        "/about-us",
        "/sobre-nos",
        "/team",
        "/equipa",
        "/equipe",
    ]

    def __init__(self):
        """Inicializa o scraper."""
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Retorna cliente HTTP reutilizavel."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                headers={"User-Agent": self.USER_AGENT},
                timeout=self.REQUEST_TIMEOUT,
                follow_redirects=True,
            )
        return self._client

    async def close(self):
        """Fecha o cliente HTTP."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _fetch_page(self, url: str) -> str | None:
        """
        Faz fetch de uma pagina.

        Args:
            url: URL a buscar

        Returns:
            HTML da pagina ou None se falhar
        """
        try:
            client = await self._get_client()
            response = await client.get(url)
            response.raise_for_status()

            content_type = response.headers.get("content-type", "")
            if "text/html" not in content_type.lower():
                return None

            return response.text
        except (httpx.HTTPError, httpx.TimeoutException):
            return None

    def _extract_emails(self, html: str, base_url: str) -> list[str]:
        """
        Extrai emails do HTML.

        Args:
            html: Conteudo HTML
            base_url: URL base para contexto

        Returns:
            Lista de emails encontrados
        """
        # Regex para emails
        email_pattern = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
        all_emails = re.findall(email_pattern, html)

        # Filtrar emails invalidos
        valid_emails = []
        for email in all_emails:
            email = email.lower()

            # Ignorar padroes comuns de emails nao uteis
            is_ignored = False
            for pattern in self.IGNORED_EMAIL_PATTERNS:
                if re.search(pattern, email):
                    is_ignored = True
                    break

            if not is_ignored and email not in valid_emails:
                valid_emails.append(email)

        return valid_emails

    def _prioritize_emails(self, emails: list[str]) -> tuple[str | None, list[str]]:
        """
        Prioriza emails para encontrar o principal.

        Args:
            emails: Lista de emails

        Returns:
            Tupla (email principal, todos os emails)
        """
        if not emails:
            return None, []

        # Prioridades de prefixos (do mais para menos importante)
        priority_prefixes = [
            "contact",
            "contacto",
            "info",
            "geral",
            "hello",
            "ola",
            "comercial",
            "vendas",
            "sales",
        ]

        for prefix in priority_prefixes:
            for email in emails:
                if email.startswith(prefix + "@"):
                    return email, emails

        # Se nenhum prioritario, retorna o primeiro
        return emails[0], emails

    def _extract_social_links(self, html: str) -> dict[str, str]:
        """
        Extrai links de redes sociais do HTML.

        Args:
            html: Conteudo HTML

        Returns:
            Dicionario {plataforma: url}
        """
        social_links = {}

        for platform, patterns in self.SOCIAL_PATTERNS.items():
            for pattern in patterns:
                matches = re.findall(pattern, html, re.IGNORECASE)
                if matches:
                    handle = matches[0]
                    if platform == "linkedin":
                        if "company" in pattern:
                            social_links[platform] = f"https://linkedin.com/company/{handle}"
                        else:
                            social_links[platform] = f"https://linkedin.com/in/{handle}"
                    elif platform == "facebook":
                        social_links[platform] = f"https://facebook.com/{handle}"
                    elif platform == "instagram":
                        social_links[platform] = f"https://instagram.com/{handle}"
                    elif platform == "twitter":
                        social_links[platform] = f"https://twitter.com/{handle}"
                    break

        return social_links

    def _extract_decision_makers(self, html: str) -> list[dict[str, Any]]:
        """
        Extrai informacao sobre decisores do HTML.

        Args:
            html: Conteudo HTML

        Returns:
            Lista de decisores encontrados
        """
        decision_makers = []
        soup = BeautifulSoup(html, "lxml")

        # Procurar padroes comuns de equipa/sobre
        role_keywords = [
            "ceo", "founder", "fundador", "owner", "proprietario",
            "director", "diretor", "manager", "gerente",
            "socio", "partner", "presidente",
        ]

        # Procurar em elementos estruturados
        for element in soup.find_all(["div", "section", "article"], class_=re.compile(r"team|equip|about|member", re.I)):
            text = element.get_text(separator=" ", strip=True)

            # Procurar nomes com cargos
            for keyword in role_keywords:
                if keyword.lower() in text.lower():
                    # Tentar extrair nome (simplificado)
                    # Procurar padroes como "Nome - Cargo" ou "Nome, Cargo"
                    name_patterns = [
                        rf"([A-Z][a-z]+ [A-Z][a-z]+)\s*[-,]\s*{keyword}",
                        rf"{keyword}\s*[-:]\s*([A-Z][a-z]+ [A-Z][a-z]+)",
                    ]

                    for pattern in name_patterns:
                        matches = re.findall(pattern, text, re.IGNORECASE)
                        for name in matches:
                            if name and len(name) > 3:
                                decision_makers.append({
                                    "name": name.strip(),
                                    "role": keyword.title(),
                                    "source": "website",
                                })

        # Remover duplicados
        seen = set()
        unique_makers = []
        for dm in decision_makers:
            key = dm["name"].lower()
            if key not in seen:
                seen.add(key)
                unique_makers.append(dm)

        return unique_makers[:5]  # Limitar a 5

    def _find_important_pages(self, html: str, base_url: str) -> list[str]:
        """
        Encontra paginas importantes para scraping.

        Args:
            html: HTML da homepage
            base_url: URL base

        Returns:
            Lista de URLs de paginas importantes
        """
        soup = BeautifulSoup(html, "lxml")
        found_urls = []

        parsed_base = urlparse(base_url)
        base_domain = parsed_base.netloc

        for link in soup.find_all("a", href=True):
            href = link["href"]

            # Converter para URL absoluto
            full_url = urljoin(base_url, href)
            parsed = urlparse(full_url)

            # Verificar se e do mesmo dominio
            if parsed.netloc != base_domain:
                continue

            # Verificar se e uma pagina importante
            path = parsed.path.lower().rstrip("/")
            for important_path in self.IMPORTANT_PATHS:
                if path.endswith(important_path):
                    if full_url not in found_urls:
                        found_urls.append(full_url)
                    break

        return found_urls[: self.MAX_PAGES_PER_SITE - 1]  # Reservar 1 para homepage

    async def scrape_website(self, url: str) -> EnrichmentResult:
        """
        Faz scraping completo de um website.

        Args:
            url: URL do website

        Returns:
            EnrichmentResult com dados extraidos
        """
        all_emails: list[str] = []
        all_social: dict[str, str] = {}
        all_makers: list[dict] = []
        pages_scraped = 0

        # Normalizar URL
        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        # Scrape homepage
        homepage_html = await self._fetch_page(url)
        if not homepage_html:
            return EnrichmentResult(
                success=False,
                error="Nao foi possivel aceder ao website",
            )

        pages_scraped += 1

        # Extrair da homepage
        all_emails.extend(self._extract_emails(homepage_html, url))
        all_social.update(self._extract_social_links(homepage_html))
        all_makers.extend(self._extract_decision_makers(homepage_html))

        # Encontrar e scrape paginas importantes
        important_pages = self._find_important_pages(homepage_html, url)

        for page_url in important_pages:
            await asyncio.sleep(self.DELAY_BETWEEN_REQUESTS)

            page_html = await self._fetch_page(page_url)
            if page_html:
                pages_scraped += 1
                all_emails.extend(self._extract_emails(page_html, page_url))

                # Atualizar social (novos sobrescrevem)
                social = self._extract_social_links(page_html)
                all_social.update(social)

                # Adicionar decision makers
                makers = self._extract_decision_makers(page_html)
                all_makers.extend(makers)

        # Remover duplicados de emails
        unique_emails = list(dict.fromkeys(all_emails))

        # Priorizar email principal
        primary_email, emails = self._prioritize_emails(unique_emails)

        # Remover duplicados de decision makers
        seen_names = set()
        unique_makers = []
        for dm in all_makers:
            name_key = dm["name"].lower()
            if name_key not in seen_names:
                seen_names.add(name_key)
                unique_makers.append(dm)

        return EnrichmentResult(
            success=True,
            emails=emails,
            primary_email=primary_email,
            social_links=all_social,
            decision_makers=unique_makers[:5],
            pages_scraped=pages_scraped,
        )


class EnrichmentService:
    """Servico para enriquecer dados de leads."""

    def __init__(self, scraper: WebsiteScraper | None = None):
        """
        Inicializa o servico.

        Args:
            scraper: WebsiteScraper opcional
        """
        self.scraper = scraper or WebsiteScraper()

    async def enrich_business(self, business_id: str) -> EnrichmentResult:
        """
        Enriquece um negocio especifico.

        Args:
            business_id: ID do negocio

        Returns:
            EnrichmentResult com dados
        """
        with db.get_session() as session:
            business = session.get(Business, business_id)

            if not business:
                return EnrichmentResult(
                    success=False,
                    error="Negocio nao encontrado",
                )

            if not business.website:
                # Marcar como sem website
                business.enrichment_status = "no_website"
                business.enriched_at = datetime.utcnow()
                session.commit()
                return EnrichmentResult(
                    success=False,
                    error="Negocio nao tem website",
                )

            # Marcar como em progresso
            business.enrichment_status = "in_progress"
            website_url = business.website  # Guardar antes de fechar sessao
            session.commit()

        # Fazer scraping (fora da sessao para nao bloquear)
        try:
            result = await self.scraper.scrape_website(website_url)
        except Exception as e:
            result = EnrichmentResult(
                success=False,
                error=str(e),
            )

        # Atualizar negocio com resultados
        with db.get_session() as session:
            business = session.get(Business, business_id)
            if not business:
                return result

            if result.success:
                business.email = result.primary_email
                business.emails_scraped = result.emails
                business.social_linkedin = result.social_links.get("linkedin")
                business.social_facebook = result.social_links.get("facebook")
                business.social_instagram = result.social_links.get("instagram")
                business.social_twitter = result.social_links.get("twitter")
                business.decision_makers = result.decision_makers
                business.enrichment_status = "completed"
                business.enrichment_error = None
            else:
                business.enrichment_status = "failed"
                business.enrichment_error = result.error

            business.enriched_at = datetime.utcnow()
            session.commit()

        return result

    async def enrich_batch(
        self,
        business_ids: list[str],
        concurrency: int = 3,
    ) -> dict[str, EnrichmentResult]:
        """
        Enriquece multiplos negocios em paralelo.

        Args:
            business_ids: Lista de IDs
            concurrency: Numero de tarefas simultaneas

        Returns:
            Dicionario {business_id: EnrichmentResult}
        """
        results: dict[str, EnrichmentResult] = {}
        semaphore = asyncio.Semaphore(concurrency)

        async def enrich_with_semaphore(bid: str) -> tuple[str, EnrichmentResult]:
            async with semaphore:
                result = await self.enrich_business(bid)
                return bid, result

        tasks = [enrich_with_semaphore(bid) for bid in business_ids]
        completed = await asyncio.gather(*tasks, return_exceptions=True)

        for item in completed:
            if isinstance(item, Exception):
                continue
            bid, result = item
            results[bid] = result

        return results

    def get_enrichable_leads(self, limit: int = 100) -> list[Business]:
        """
        Retorna leads que podem ser enriquecidos.

        Args:
            limit: Maximo de resultados

        Returns:
            Lista de Business com website e nao enriquecidos
        """
        with db.get_session() as session:
            businesses = (
                session.query(Business)
                .filter(
                    Business.has_website == True,  # noqa: E712
                    Business.enrichment_status.in_(["pending", "failed"]),
                    Business.website.isnot(None),
                )
                .order_by(Business.lead_score.desc())
                .limit(limit)
                .all()
            )
            # Expunge para usar fora da sessao
            for b in businesses:
                session.expunge(b)
            return businesses

    def get_enrichment_stats(self) -> dict[str, int]:
        """
        Retorna estatisticas de enriquecimento.

        Returns:
            Dicionario com contagens por status
        """
        with db.get_session() as session:
            from sqlalchemy import func

            stats = (
                session.query(
                    Business.enrichment_status,
                    func.count(Business.id),
                )
                .group_by(Business.enrichment_status)
                .all()
            )

            result = {
                "pending": 0,
                "in_progress": 0,
                "completed": 0,
                "failed": 0,
                "no_website": 0,
                "skipped": 0,
            }

            for status, count in stats:
                if status in result:
                    result[status] = count

            result["total"] = sum(result.values())
            result["enrichable"] = result["pending"] + result["failed"]

            return result
