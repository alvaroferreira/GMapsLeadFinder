"""Configuracoes centrais do projeto usando pydantic-settings."""

from pathlib import Path
from functools import lru_cache

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
    google_places_api_key: str = Field(
        default="",
        description="API key do Google Places"
    )

    # Database
    database_url: str = Field(
        default="sqlite:///data/leads.db",
        description="URL de conexao a base de dados"
    )

    # Defaults para pesquisa
    default_radius: int = Field(
        default=5000,
        ge=1,
        le=50000,
        description="Raio padrao em metros"
    )
    default_language: str = Field(
        default="pt",
        description="Idioma padrao dos resultados"
    )
    max_results_per_page: int = Field(
        default=20,
        ge=1,
        le=20,
        description="Resultados por pagina (max 20 da API)"
    )

    # Rate Limiting
    requests_per_second: float = Field(
        default=5.0,
        ge=0.1,
        le=10.0,
        description="Limite de requests por segundo"
    )
    max_retries: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Numero maximo de retries"
    )

    # Export
    export_dir: Path = Field(
        default=Path("./exports"),
        description="Directorio para ficheiros exportados"
    )

    # Data Retention (Google ToS)
    data_refresh_days: int = Field(
        default=30,
        ge=1,
        le=30,
        description="Dias ate refresh obrigatorio (ToS Google)"
    )

    # Logging
    log_level: str = Field(
        default="INFO",
        description="Nivel de logging"
    )

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
        return bool(self.google_places_api_key) and self.google_places_api_key != "your_api_key_here"


@lru_cache
def get_settings() -> Settings:
    """Retorna instancia cached das settings."""
    return Settings()


# Instancia global para uso direto
settings = get_settings()
