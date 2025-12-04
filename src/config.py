"""Configuracoes centrais do projeto usando pydantic-settings."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuracoes da aplicacao carregadas de variaveis de ambiente."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Google Places API
    google_places_api_key: str = Field(default="", description="API key do Google Places")
    google_places_enabled: bool = Field(
        default=True, description="Se a API Google Places esta ativa"
    )

    # Database
    database_url: str = Field(
        default="sqlite:///data/leads.db", description="URL de conexao a base de dados"
    )

    # Defaults para pesquisa
    default_radius: int = Field(default=5000, ge=1, le=50000, description="Raio padrao em metros")
    default_language: str = Field(default="pt", description="Idioma padrao dos resultados")
    max_results_per_page: int = Field(
        default=20, ge=1, le=20, description="Resultados por pagina (max 20 da API)"
    )

    # Rate Limiting
    requests_per_second: float = Field(
        default=5.0, ge=0.1, le=10.0, description="Limite de requests por segundo"
    )
    max_retries: int = Field(default=3, ge=1, le=10, description="Numero maximo de retries")

    # Export
    export_dir: Path = Field(
        default=Path("./exports"), description="Directorio para ficheiros exportados"
    )

    # Data Retention (Google ToS)
    data_refresh_days: int = Field(
        default=30, ge=1, le=30, description="Dias ate refresh obrigatorio (ToS Google)"
    )

    # Logging
    log_level: str = Field(default="INFO", description="Nivel de logging")

    # OpenStreetMap / Overpass Settings
    osm_default_area: str = Field(
        default="lisboa",
        description="Area padrao para descoberta OSM (lisboa, porto, portugal, etc)",
    )
    osm_discovery_days: int = Field(
        default=7, ge=1, le=90, description="Dias atras para filtro newer do Overpass"
    )
    osm_timeout: int = Field(
        default=180, ge=30, le=600, description="Timeout em segundos para queries Overpass"
    )

    # AI Settings
    openai_api_key: str = Field(default="", description="API key do OpenAI")
    openai_enabled: bool = Field(default=True, description="Se a API OpenAI esta ativa")
    anthropic_api_key: str = Field(default="", description="API key do Anthropic")
    anthropic_enabled: bool = Field(default=True, description="Se a API Anthropic esta ativa")
    gemini_api_key: str = Field(default="", description="API key do Google Gemini")
    gemini_enabled: bool = Field(default=True, description="Se a API Gemini esta ativa")
    default_ai_provider: str = Field(default="openai", description="Provider de AI padrao")

    def ensure_directories(self) -> None:
        """Cria directorios necessarios se nao existirem."""
        self.export_dir.mkdir(parents=True, exist_ok=True)

        # Criar directorio da DB se for SQLite
        if self.database_url.startswith("sqlite:///"):
            db_path = Path(self.database_url.replace("sqlite:///", ""))
            db_path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def has_api_key(self) -> bool:
        """Verifica se a API key esta configurada."""
        return (
            bool(self.google_places_api_key) and self.google_places_api_key != "your_api_key_here"
        )


@lru_cache
def get_settings() -> Settings:
    """Retorna instancia cached das settings."""
    return Settings()


# Instancia global para uso direto
settings = get_settings()
