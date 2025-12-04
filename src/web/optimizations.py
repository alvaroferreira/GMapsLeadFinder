"""Otimizacoes de performance para o servidor web."""

from typing import Any

from src.database.db import db
from src.database.models import IntegrationConfig
from src.database.queries import BusinessQueries
from src.utils.cache import cache


def get_notion_config_cached() -> dict[str, Any] | None:
    """
    Retorna configuracao do Notion com caching.
    Cache de 5 minutos para evitar queries repetidas.

    Returns:
        Dict com configuracao ou None
    """
    cache_key = "notion:config"
    cached_config = cache.get(cache_key)

    if cached_config is not None:
        return cached_config

    with db.get_session() as session:
        config = (
            session.query(IntegrationConfig).filter(IntegrationConfig.service == "notion").first()
        )

        if config:
            result = {
                "is_active": config.is_active,
                "database_id": (config.config or {}).get("database_id"),
                "workspace_name": (config.config or {}).get("workspace_name"),
            }
        else:
            result = None

        # Cachear por 5 minutos
        cache.set(cache_key, result, ttl=300)
        return result


def invalidate_notion_cache():
    """Invalida cache de configuracao do Notion."""
    cache.delete("notion:config")


def get_stats_cached() -> dict[str, Any]:
    """
    Retorna estatisticas com caching.
    Cache de 2 minutos para dashboard.

    Returns:
        Dict com estatisticas
    """
    cache_key = "stats:global"
    cached_stats = cache.get(cache_key)

    if cached_stats is not None:
        return cached_stats

    with db.get_session() as session:
        stats = BusinessQueries.get_stats(session)

    # Cachear por 2 minutos
    cache.set(cache_key, stats, ttl=120)
    return stats


def invalidate_stats_cache():
    """Invalida cache de estatisticas."""
    cache.delete("stats:global")


def business_to_dict(business: Any, include_extra: bool = False) -> dict[str, Any]:
    """
    Converte Business para dict de forma otimizada.

    Args:
        business: Objeto Business do SQLAlchemy
        include_extra: Se True, inclui campos adicionais (phone, website, etc)

    Returns:
        Dicionario com dados do business
    """
    base_dict = {
        "id": business.id,
        "name": business.name,
        "formatted_address": business.formatted_address,
        "rating": business.rating,
        "review_count": business.review_count,
        "has_website": business.has_website,
        "lead_score": business.lead_score,
        "lead_status": business.lead_status,
        "google_maps_url": business.google_maps_url,
        "notion_synced_at": business.notion_synced_at,
        "first_seen_at": business.first_seen_at,
    }

    if include_extra:
        base_dict.update(
            {
                "phone": business.phone_number,
                "website": business.website,
                "enrichment_status": getattr(business, "enrichment_status", "pending"),
                "latitude": business.latitude,
                "longitude": business.longitude,
                "email": business.email,
            }
        )

    return base_dict


def businesses_to_dicts(businesses: list[Any], include_extra: bool = False) -> list[dict]:
    """
    Converte lista de Business para dicts de forma otimizada.
    Usa list comprehension para melhor performance.

    Args:
        businesses: Lista de objetos Business
        include_extra: Se True, inclui campos adicionais

    Returns:
        Lista de dicionarios
    """
    return [business_to_dict(b, include_extra=include_extra) for b in businesses]
