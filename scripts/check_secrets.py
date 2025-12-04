#!/usr/bin/env python3
"""
Verifica padroes de secrets hardcoded no codigo.

Este script e usado pelo pre-commit para detetar API keys,
tokens e outras credenciais que nao devem ser commitadas.

Uso:
    python scripts/check_secrets.py file1.py file2.py ...
"""

import re
import sys
from pathlib import Path
from typing import NamedTuple


class SecretPattern(NamedTuple):
    """Padrao de secret com nome e regex."""

    name: str
    pattern: str
    description: str


# Padroes de secrets conhecidos
SECRET_PATTERNS = [
    SecretPattern(
        name="Google API Key",
        pattern=r"AIza[0-9A-Za-z\-_]{35}",
        description="Google Cloud/Maps API key",
    ),
    SecretPattern(
        name="Stripe Live Key",
        pattern=r"sk_live_[0-9a-zA-Z]{24,}",
        description="Stripe production secret key",
    ),
    SecretPattern(
        name="Stripe Test Key",
        pattern=r"sk_test_[0-9a-zA-Z]{24,}",
        description="Stripe test secret key",
    ),
    SecretPattern(
        name="GitHub Token",
        pattern=r"ghp_[0-9a-zA-Z]{36}",
        description="GitHub personal access token",
    ),
    SecretPattern(
        name="GitHub OAuth",
        pattern=r"gho_[0-9a-zA-Z]{36}",
        description="GitHub OAuth token",
    ),
    SecretPattern(
        name="Notion Secret",
        pattern=r"secret_[0-9a-zA-Z]{32,}",
        description="Notion integration secret",
    ),
    SecretPattern(
        name="AWS Access Key",
        pattern=r"AKIA[0-9A-Z]{16}",
        description="AWS access key ID",
    ),
    SecretPattern(
        name="Private Key",
        pattern=r"-----BEGIN[A-Z ]*PRIVATE KEY-----",
        description="PEM private key",
    ),
    SecretPattern(
        name="OpenAI Key",
        pattern=r"sk-[a-zA-Z0-9]{48}",
        description="OpenAI API key",
    ),
    SecretPattern(
        name="Slack Token",
        pattern=r"xox[baprs]-[0-9a-zA-Z]{10,}",
        description="Slack API token",
    ),
    SecretPattern(
        name="Discord Token",
        pattern=r"[MN][A-Za-z\d]{23,}\.[\w-]{6}\.[\w-]{27}",
        description="Discord bot token",
    ),
    SecretPattern(
        name="Neon/Postgres Connection",
        pattern=r"postgres://[^:]+:[^@]+@[^/]+\.neon\.tech",
        description="Neon database connection string with password",
    ),
]

# Linhas a ignorar (comentarios, exemplos, testes)
IGNORE_PATTERNS = [
    r"^\s*#",  # Comentarios Python
    r"^\s*//",  # Comentarios estilo C
    r"example",  # Exemplos
    r"placeholder",  # Placeholders
    r"your[_-]?api[_-]?key",  # Placeholders genericos
    r"xxx+",  # Placeholders com x
    r"FAKE",  # Valores de teste
    r"TEST",  # Valores de teste
    r"\.env\.example",  # Referencias a .env.example
]


def should_ignore_line(line: str) -> bool:
    """Verifica se a linha deve ser ignorada."""
    line_lower = line.lower()
    return any(re.search(pattern, line_lower) for pattern in IGNORE_PATTERNS)


def check_file(filepath: str) -> list[tuple[int, str, SecretPattern]]:
    """
    Verifica um ficheiro por secrets hardcoded.

    Args:
        filepath: Caminho para o ficheiro

    Returns:
        Lista de (linha, conteudo, padrao) para cada secret encontrado
    """
    findings: list[tuple[int, str, SecretPattern]] = []

    try:
        with open(filepath, encoding="utf-8", errors="ignore") as f:
            for line_num, line in enumerate(f, 1):
                # Ignorar linhas especiais
                if should_ignore_line(line):
                    continue

                # Verificar cada padrao
                for secret_pattern in SECRET_PATTERNS:
                    if re.search(secret_pattern.pattern, line):
                        findings.append((line_num, line.strip(), secret_pattern))

    except OSError as e:
        print(f"Warning: Could not read {filepath}: {e}", file=sys.stderr)

    return findings


def main() -> int:
    """
    Ponto de entrada principal.

    Returns:
        0 se nenhum secret encontrado, 1 caso contrario
    """
    if len(sys.argv) < 2:
        # Sem ficheiros para verificar
        return 0

    files = sys.argv[1:]
    total_findings: list[tuple[str, int, str, SecretPattern]] = []

    for filepath in files:
        # Ignorar ficheiros que nao sao Python
        if not filepath.endswith(".py"):
            continue

        # Ignorar testes e conftest
        path = Path(filepath)
        if "test" in path.stem.lower() or path.stem == "conftest":
            continue

        findings = check_file(filepath)
        for line_num, content, pattern in findings:
            total_findings.append((filepath, line_num, content, pattern))

    if total_findings:
        print("\n" + "=" * 60)
        print("SECRETS DETECTED - Commit Blocked!")
        print("=" * 60 + "\n")

        for filepath, line_num, content, pattern in total_findings:
            print(f"File: {filepath}:{line_num}")
            print(f"Type: {pattern.name} ({pattern.description})")
            # Mascarar parte do secret
            masked = re.sub(pattern.pattern, "[REDACTED]", content)
            print(f"Line: {masked}")
            print("-" * 40)

        print(f"\nTotal: {len(total_findings)} potential secret(s) found")
        print("\nHow to fix:")
        print("  1. Move secrets to .env file")
        print("  2. Use environment variables: os.getenv('API_KEY')")
        print("  3. If this is a false positive, add to .secrets.baseline")
        print()

        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
