"""Custom exceptions para o Geoscout Pro."""

from typing import Any


class GeoscoutBaseException(Exception):
    """Excecao base para todas as excecoes customizadas."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        """
        Inicializa a excecao.

        Args:
            message: Mensagem de erro
            details: Detalhes adicionais (opcional)
        """
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class DatabaseError(GeoscoutBaseException):
    """Erro relacionado com operacoes de base de dados."""
    pass


class BusinessNotFoundError(GeoscoutBaseException):
    """Negocio nao encontrado na base de dados."""
    pass


class SearchError(GeoscoutBaseException):
    """Erro durante pesquisa na API do Google Places."""
    pass


class EnrichmentError(GeoscoutBaseException):
    """Erro durante enriquecimento de dados."""
    pass


class ValidationError(GeoscoutBaseException):
    """Erro de validacao de dados."""
    pass


class ConfigurationError(GeoscoutBaseException):
    """Erro de configuracao (API keys, etc)."""
    pass


class IntegrationError(GeoscoutBaseException):
    """Erro com integracoes externas (Notion, etc)."""
    pass
