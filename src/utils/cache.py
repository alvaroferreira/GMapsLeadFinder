"""Cache simples em memoria para otimizacao de performance."""

import time
from collections.abc import Callable
from functools import wraps
from typing import Any


class SimpleCache:
    """Cache simples baseado em dicionario com TTL."""

    def __init__(self):
        """Inicializa o cache."""
        self._cache: dict[str, tuple[Any, float]] = {}
        self._default_ttl = 300  # 5 minutos

    def get(self, key: str) -> Any | None:
        """
        Obtem valor do cache se nao expirado.

        Args:
            key: Chave do cache

        Returns:
            Valor ou None se expirado/inexistente
        """
        if key not in self._cache:
            return None

        value, expiry = self._cache[key]
        if time.time() > expiry:
            del self._cache[key]
            return None

        return value

    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """
        Define valor no cache.

        Args:
            key: Chave do cache
            value: Valor a guardar
            ttl: Tempo de vida em segundos (usa default se None)
        """
        ttl = ttl or self._default_ttl
        expiry = time.time() + ttl
        self._cache[key] = (value, expiry)

    def delete(self, key: str) -> None:
        """Remove chave do cache."""
        if key in self._cache:
            del self._cache[key]

    def clear(self) -> None:
        """Limpa todo o cache."""
        self._cache.clear()

    def invalidate_pattern(self, pattern: str) -> None:
        """
        Invalida todas as chaves que contem o padrao.

        Args:
            pattern: String a procurar nas chaves
        """
        keys_to_delete = [k for k in self._cache.keys() if pattern in k]
        for key in keys_to_delete:
            del self._cache[key]


# Instancia global
cache = SimpleCache()


def cached(ttl: int = 300, key_prefix: str = ""):
    """
    Decorator para cachear resultados de funcoes.

    Args:
        ttl: Tempo de vida em segundos
        key_prefix: Prefixo para a chave do cache

    Usage:
        @cached(ttl=60, key_prefix="stats")
        def get_stats():
            return expensive_operation()
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Gerar chave baseada em funcao e argumentos
            cache_key = f"{key_prefix}:{func.__name__}"
            if args:
                cache_key += f":{str(args)}"
            if kwargs:
                cache_key += f":{str(sorted(kwargs.items()))}"

            # Tentar obter do cache
            result = cache.get(cache_key)
            if result is not None:
                return result

            # Executar funcao e guardar no cache
            result = func(*args, **kwargs)
            cache.set(cache_key, result, ttl=ttl)
            return result

        # Adicionar metodo para invalidar cache
        wrapper.invalidate_cache = lambda: cache.invalidate_pattern(f"{key_prefix}:{func.__name__}")

        return wrapper

    return decorator
