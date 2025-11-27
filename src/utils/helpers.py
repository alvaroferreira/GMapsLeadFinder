"""Funcoes utilitarias."""

import re
from typing import Any


def parse_location(location_str: str) -> tuple[float, float] | None:
    """
    Tenta parsear uma string de localizacao para coordenadas.

    Args:
        location_str: String com coordenadas (ex: "38.7223,-9.1393")

    Returns:
        Tupla (latitude, longitude) ou None se nao for valida
    """
    if not location_str:
        return None

    # Tentar parsear como coordenadas
    pattern = r"^(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)$"
    match = re.match(pattern, location_str.strip())

    if match:
        lat = float(match.group(1))
        lng = float(match.group(2))

        # Validar ranges
        if -90 <= lat <= 90 and -180 <= lng <= 180:
            return (lat, lng)

    return None


def truncate_string(text: str, max_length: int, suffix: str = "...") -> str:
    """
    Trunca string para tamanho maximo.

    Args:
        text: Texto a truncar
        max_length: Tamanho maximo
        suffix: Sufixo a adicionar se truncado

    Returns:
        String truncada
    """
    if not text or len(text) <= max_length:
        return text or ""

    return text[: max_length - len(suffix)] + suffix


def format_phone(phone: str | None) -> str:
    """
    Formata numero de telefone para display.

    Args:
        phone: Numero de telefone

    Returns:
        Numero formatado ou string vazia
    """
    if not phone:
        return ""

    # Remover caracteres nao numericos exceto +
    clean = re.sub(r"[^\d+]", "", phone)
    return clean


def extract_city_from_address(address: str | None) -> str:
    """
    Extrai cidade de um endereco formatado.

    Args:
        address: Endereco completo

    Returns:
        Nome da cidade ou string vazia
    """
    if not address:
        return ""

    # Assumir formato: "Rua X, Cidade, Pais" ou similar
    parts = [p.strip() for p in address.split(",")]

    if len(parts) >= 2:
        # Cidade normalmente e o penultimo elemento
        return parts[-2]

    return ""


def safe_get(data: dict, *keys: str, default: Any = None) -> Any:
    """
    Acesso seguro a dicionarios aninhados.

    Args:
        data: Dicionario
        keys: Chaves em sequencia
        default: Valor default se nao encontrar

    Returns:
        Valor encontrado ou default
    """
    result = data
    for key in keys:
        if isinstance(result, dict):
            result = result.get(key, default)
        else:
            return default
    return result


def chunks(lst: list, n: int):
    """
    Divide lista em chunks de tamanho n.

    Args:
        lst: Lista a dividir
        n: Tamanho de cada chunk

    Yields:
        Chunks da lista
    """
    for i in range(0, len(lst), n):
        yield lst[i : i + n]
