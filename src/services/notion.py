"""Servico de integracao com Notion CRM."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx

from src.database.db import db
from src.database.models import Business, IntegrationConfig


@dataclass
class SyncResult:
    """Resultado de uma sincronizacao com Notion."""

    success: bool
    business_id: str
    notion_page_id: str | None = None
    action: str = ""  # "created" ou "updated"
    error: str | None = None


class NotionClient:
    """Cliente para a API do Notion."""

    BASE_URL = "https://api.notion.com/v1"
    NOTION_VERSION = "2022-06-28"

    def __init__(self, api_key: str):
        """
        Inicializa o cliente Notion.

        Args:
            api_key: Token de integracao do Notion
        """
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Notion-Version": self.NOTION_VERSION,
            "Content-Type": "application/json",
        }

    async def test_connection(self) -> dict[str, Any]:
        """
        Testa a conexao e retorna info do utilizador/workspace.

        Returns:
            Dict com informacoes do utilizador
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/users/me",
                headers=self.headers,
                timeout=10.0,
            )
            response.raise_for_status()
            return response.json()

    async def list_databases(self) -> list[dict[str, Any]]:
        """
        Lista todas as databases acessiveis pela integracao.

        Returns:
            Lista de databases com id e titulo
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.BASE_URL}/search",
                headers=self.headers,
                json={
                    "filter": {"property": "object", "value": "database"},
                    "page_size": 100,
                },
                timeout=10.0,
            )
            response.raise_for_status()
            data = response.json()

            databases = []
            for db_item in data.get("results", []):
                title = ""
                if db_item.get("title"):
                    title = "".join(t.get("plain_text", "") for t in db_item["title"])
                databases.append(
                    {
                        "id": db_item["id"],
                        "title": title or "Sem titulo",
                        "url": db_item.get("url", ""),
                    }
                )

            return databases

    async def get_database_schema(self, database_id: str) -> dict[str, Any]:
        """
        Retorna o schema (propriedades) de uma database.

        Args:
            database_id: ID da database

        Returns:
            Dict com propriedades da database
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/databases/{database_id}",
                headers=self.headers,
                timeout=10.0,
            )
            response.raise_for_status()
            return response.json()

    async def create_page(
        self,
        database_id: str,
        properties: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Cria uma nova pagina (lead) na database.

        Args:
            database_id: ID da database destino
            properties: Propriedades da pagina no formato Notion

        Returns:
            Dados da pagina criada
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.BASE_URL}/pages",
                headers=self.headers,
                json={
                    "parent": {"database_id": database_id},
                    "properties": properties,
                },
                timeout=15.0,
            )
            response.raise_for_status()
            return response.json()

    async def update_page(
        self,
        page_id: str,
        properties: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Atualiza uma pagina existente.

        Args:
            page_id: ID da pagina a atualizar
            properties: Propriedades a atualizar

        Returns:
            Dados da pagina atualizada
        """
        async with httpx.AsyncClient() as client:
            response = await client.patch(
                f"{self.BASE_URL}/pages/{page_id}",
                headers=self.headers,
                json={"properties": properties},
                timeout=15.0,
            )
            response.raise_for_status()
            return response.json()

    async def get_page(self, page_id: str) -> dict[str, Any]:
        """
        Obtem dados de uma pagina.

        Args:
            page_id: ID da pagina

        Returns:
            Dados da pagina
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/pages/{page_id}",
                headers=self.headers,
                timeout=10.0,
            )
            response.raise_for_status()
            return response.json()


class NotionService:
    """Servico de integracao com Notion CRM."""

    # Mapeamento de campos Lead -> Notion
    FIELD_MAPPING = {
        # Basicos
        "name": {"type": "title", "notion_name": "Nome"},
        "formatted_address": {"type": "rich_text", "notion_name": "Endereco"},
        "phone_number": {"type": "phone_number", "notion_name": "Telefone"},
        "website": {"type": "url", "notion_name": "Website"},
        "google_maps_url": {"type": "url", "notion_name": "Google Maps"},
        # Metricas
        "rating": {"type": "number", "notion_name": "Rating"},
        "review_count": {"type": "number", "notion_name": "Reviews"},
        "lead_score": {"type": "number", "notion_name": "Score"},
        "lead_status": {"type": "select", "notion_name": "Status"},
        # Enrichment
        "email": {"type": "email", "notion_name": "Email"},
        "emails_scraped": {"type": "rich_text", "notion_name": "Outros Emails"},
        "social_linkedin": {"type": "url", "notion_name": "LinkedIn"},
        "social_facebook": {"type": "url", "notion_name": "Facebook"},
        "social_instagram": {"type": "url", "notion_name": "Instagram"},
        "social_twitter": {"type": "url", "notion_name": "Twitter"},
        # Decision Makers
        "decision_makers": {"type": "rich_text", "notion_name": "Decisores"},
        # Metadata
        "notes": {"type": "rich_text", "notion_name": "Notas"},
        "tags": {"type": "multi_select", "notion_name": "Tags"},
        "first_seen_at": {"type": "date", "notion_name": "Descoberto Em"},
        "enriched_at": {"type": "date", "notion_name": "Enriquecido Em"},
    }

    def __init__(self):
        """Inicializa o servico."""
        self._client: NotionClient | None = None

    def _get_client(self) -> NotionClient | None:
        """Retorna cliente Notion se configurado."""
        config = self.get_config()
        if config and config.get("api_key"):
            return NotionClient(config["api_key"])
        return None

    def get_config(self) -> dict[str, Any] | None:
        """
        Retorna configuracao do Notion se existir.

        Returns:
            Dict com configuracao ou None
        """
        with db.get_session() as session:
            config = (
                session.query(IntegrationConfig)
                .filter(IntegrationConfig.service == "notion")
                .first()
            )
            if config:
                return {
                    "id": config.id,
                    "api_key": config.api_key,
                    "config": config.config or {},
                    "is_active": config.is_active,
                    "last_sync_at": config.last_sync_at,
                    "database_id": (config.config or {}).get("database_id"),
                    "workspace_name": (config.config or {}).get("workspace_name"),
                }
            return None

    def save_config(
        self,
        api_key: str,
        database_id: str | None = None,
        workspace_name: str | None = None,
    ) -> bool:
        """
        Salva ou atualiza configuracao do Notion.

        Args:
            api_key: Token de integracao
            database_id: ID da database selecionada
            workspace_name: Nome do workspace

        Returns:
            True se salvo com sucesso
        """
        with db.get_session() as session:
            config = (
                session.query(IntegrationConfig)
                .filter(IntegrationConfig.service == "notion")
                .first()
            )

            config_data = {}
            if database_id:
                config_data["database_id"] = database_id
            if workspace_name:
                config_data["workspace_name"] = workspace_name

            if config:
                config.api_key = api_key
                if config_data:
                    config.config = {**(config.config or {}), **config_data}
                config.is_active = bool(database_id)
            else:
                config = IntegrationConfig(
                    service="notion",
                    api_key=api_key,
                    config=config_data,
                    is_active=bool(database_id),
                )
                session.add(config)

            session.commit()
            return True

    def disconnect(self) -> bool:
        """
        Desconecta a integracao Notion.

        Returns:
            True se desconectado com sucesso
        """
        with db.get_session() as session:
            config = (
                session.query(IntegrationConfig)
                .filter(IntegrationConfig.service == "notion")
                .first()
            )
            if config:
                session.delete(config)
                session.commit()
            return True

    async def test_connection(self, api_key: str) -> dict[str, Any]:
        """
        Testa conexao com um API key.

        Args:
            api_key: Token a testar

        Returns:
            Info do workspace se sucesso
        """
        client = NotionClient(api_key)
        return await client.test_connection()

    async def list_databases(self, api_key: str | None = None) -> list[dict]:
        """
        Lista databases disponiveis.

        Args:
            api_key: Token (usa config se nao fornecido)

        Returns:
            Lista de databases
        """
        if api_key:
            client = NotionClient(api_key)
        else:
            client = self._get_client()
            if not client:
                return []

        return await client.list_databases()

    def _business_to_notion_properties(
        self,
        business: Business,
    ) -> dict[str, Any]:
        """
        Converte um Business para propriedades Notion.

        Args:
            business: Objeto Business

        Returns:
            Dict de propriedades no formato Notion
        """
        properties = {}

        for field, mapping in self.FIELD_MAPPING.items():
            value = getattr(business, field, None)
            notion_name = mapping["notion_name"]
            prop_type = mapping["type"]

            if value is None:
                continue

            # Converter para formato Notion
            if prop_type == "title":
                properties[notion_name] = {"title": [{"text": {"content": str(value)[:2000]}}]}

            elif prop_type == "rich_text":
                # Tratar listas (emails_scraped, decision_makers)
                if isinstance(value, list):
                    if field == "decision_makers":
                        # Formatar decisores legivelmente
                        text_parts = []
                        for dm in value[:5]:  # Max 5
                            name = dm.get("name", "")
                            role = dm.get("role", "")
                            email = dm.get("email", "")
                            parts = [name]
                            if role:
                                parts.append(f"({role})")
                            if email:
                                parts.append(f"- {email}")
                            text_parts.append(" ".join(parts))
                        text = "\n".join(text_parts)
                    else:
                        text = ", ".join(str(v) for v in value[:10])
                else:
                    text = str(value)

                properties[notion_name] = {"rich_text": [{"text": {"content": text[:2000]}}]}

            elif prop_type == "number":
                properties[notion_name] = {"number": float(value)}

            elif prop_type == "url":
                if value:
                    properties[notion_name] = {"url": str(value)[:2000]}

            elif prop_type == "email":
                if value:
                    properties[notion_name] = {"email": str(value)}

            elif prop_type == "phone_number":
                if value:
                    properties[notion_name] = {"phone_number": str(value)}

            elif prop_type == "select":
                properties[notion_name] = {"select": {"name": str(value)}}

            elif prop_type == "multi_select":
                if isinstance(value, list):
                    properties[notion_name] = {
                        "multi_select": [{"name": str(t)[:100]} for t in value[:10]]
                    }

            elif prop_type == "date":
                if isinstance(value, datetime):
                    properties[notion_name] = {"date": {"start": value.isoformat()}}

        return properties

    async def sync_lead(self, business_id: str) -> SyncResult:
        """
        Sincroniza um lead com o Notion.

        Args:
            business_id: ID do lead a sincronizar

        Returns:
            SyncResult com detalhes
        """
        config = self.get_config()
        if not config or not config.get("is_active"):
            return SyncResult(
                success=False,
                business_id=business_id,
                error="Notion nao configurado ou inativo",
            )

        database_id = config.get("database_id")
        if not database_id:
            return SyncResult(
                success=False,
                business_id=business_id,
                error="Database Notion nao selecionada",
            )

        client = NotionClient(config["api_key"])

        # Buscar business
        with db.get_session() as session:
            business = session.get(Business, business_id)
            if not business:
                return SyncResult(
                    success=False,
                    business_id=business_id,
                    error="Lead nao encontrado",
                )

            # Guardar valores antes de fechar sessao
            notion_page_id = business.notion_page_id
            properties = self._business_to_notion_properties(business)

        try:
            if notion_page_id:
                # UPDATE
                await client.update_page(notion_page_id, properties)
                action = "updated"
            else:
                # CREATE
                result = await client.create_page(database_id, properties)
                notion_page_id = result["id"]
                action = "created"

            # Atualizar business com page_id
            with db.get_session() as session:
                business = session.get(Business, business_id)
                if business:
                    business.notion_page_id = notion_page_id
                    business.notion_synced_at = datetime.utcnow()
                    session.commit()

            # Atualizar last_sync_at na config
            with db.get_session() as session:
                cfg = (
                    session.query(IntegrationConfig)
                    .filter(IntegrationConfig.service == "notion")
                    .first()
                )
                if cfg:
                    cfg.last_sync_at = datetime.utcnow()
                    session.commit()

            return SyncResult(
                success=True,
                business_id=business_id,
                notion_page_id=notion_page_id,
                action=action,
            )

        except httpx.HTTPStatusError as e:
            error_msg = f"Erro HTTP {e.response.status_code}"
            try:
                error_data = e.response.json()
                error_msg = error_data.get("message", error_msg)
            except Exception:
                pass

            return SyncResult(
                success=False,
                business_id=business_id,
                error=error_msg,
            )

        except Exception as e:
            return SyncResult(
                success=False,
                business_id=business_id,
                error=str(e),
            )

    async def sync_batch(
        self,
        business_ids: list[str],
        concurrency: int = 3,
    ) -> dict[str, SyncResult]:
        """
        Sincroniza multiplos leads com rate limiting.

        Args:
            business_ids: Lista de IDs a sincronizar
            concurrency: Numero maximo de requests simultaneos

        Returns:
            Dict de business_id -> SyncResult
        """
        import asyncio

        results = {}
        semaphore = asyncio.Semaphore(concurrency)

        async def sync_with_limit(bid: str):
            async with semaphore:
                result = await self.sync_lead(bid)
                results[bid] = result
                # Rate limiting - Notion tem limite de 3 req/s
                await asyncio.sleep(0.4)

        await asyncio.gather(*[sync_with_limit(bid) for bid in business_ids])
        return results

    def get_sync_stats(self) -> dict[str, int]:
        """
        Retorna estatisticas de sincronizacao.

        Returns:
            Dict com contagens
        """
        with db.get_session() as session:
            total = session.query(Business).count()
            synced = session.query(Business).filter(Business.notion_page_id.isnot(None)).count()
            not_synced = total - synced

            return {
                "total": total,
                "synced": synced,
                "not_synced": not_synced,
            }
