"""Servico para gestao de configuracoes."""

import os
from pathlib import Path

from src.exceptions import ConfigurationError


class ConfigService:
    """Servico para ler e escrever configuracoes (.env)."""

    def __init__(self, env_path: Path | None = None):
        """
        Inicializa o servico.

        Args:
            env_path: Caminho para o ficheiro .env (opcional)
        """
        if env_path is None:
            # Determinar caminho do .env (raiz do projeto)
            current_file = Path(__file__)
            project_root = current_file.parent.parent.parent
            env_path = project_root / ".env"

        self.env_path = env_path

    def read_env_vars(self) -> dict[str, str]:
        """
        Le o ficheiro .env e retorna um dicionario.

        Returns:
            Dicionario com variaveis de ambiente

        Raises:
            ConfigurationError: Se houver erro ao ler o ficheiro
        """
        env_vars = {}

        if not self.env_path.exists():
            return env_vars

        try:
            with open(self.env_path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        env_vars[key.strip()] = value.strip()
        except Exception as e:
            raise ConfigurationError(
                "Erro ao ler ficheiro .env",
                details={"path": str(self.env_path), "error": str(e)},
            )

        return env_vars

    def write_env_vars(self, env_vars: dict[str, str]) -> None:
        """
        Escreve o ficheiro .env mantendo comentarios e ordem.

        Args:
            env_vars: Dicionario com variaveis a escrever

        Raises:
            ConfigurationError: Se houver erro ao escrever o ficheiro
        """
        lines = []

        try:
            # Ler ficheiro existente para manter comentarios
            if self.env_path.exists():
                with open(self.env_path) as f:
                    env_vars_to_write = env_vars.copy()

                    for line in f:
                        stripped = line.strip()

                        # Manter comentarios e linhas vazias
                        if stripped.startswith("#") or not stripped:
                            lines.append(line.rstrip())
                        elif "=" in stripped:
                            key = stripped.split("=", 1)[0].strip()
                            if key in env_vars_to_write:
                                # Atualizar com novo valor
                                lines.append(f"{key}={env_vars_to_write[key]}")
                                del env_vars_to_write[key]
                            else:
                                # Manter linha existente
                                lines.append(line.rstrip())

                    # Adicionar novas variaveis
                    for key, value in env_vars_to_write.items():
                        lines.append(f"{key}={value}")
            else:
                # Criar novo ficheiro
                for key, value in env_vars.items():
                    lines.append(f"{key}={value}")

            # Escrever ficheiro
            with open(self.env_path, "w") as f:
                f.write("\n".join(lines) + "\n")

        except Exception as e:
            raise ConfigurationError(
                "Erro ao escrever ficheiro .env",
                details={"path": str(self.env_path), "error": str(e)},
            )

    def update_api_key(self, key_name: str, api_key: str) -> None:
        """
        Atualiza uma API key no .env e no ambiente runtime.

        Args:
            key_name: Nome da variavel (ex: GOOGLE_PLACES_API_KEY)
            api_key: Valor da API key

        Raises:
            ConfigurationError: Se houver erro ao atualizar
        """
        env_vars = self.read_env_vars()
        env_vars[key_name] = api_key
        self.write_env_vars(env_vars)

        # Atualizar variavel de ambiente em runtime
        os.environ[key_name] = api_key

    def get_api_key(self, key_name: str) -> str | None:
        """
        Retorna uma API key do .env.

        Args:
            key_name: Nome da variavel

        Returns:
            Valor da API key ou None
        """
        env_vars = self.read_env_vars()
        return env_vars.get(key_name)

    def mask_api_key(self, key: str) -> str:
        """
        Mascara uma API key mostrando apenas os primeiros 8 caracteres.

        Args:
            key: API key a mascarar

        Returns:
            API key mascarada
        """
        if not key or len(key) < 8:
            return ""
        return key[:8] + "••••••••••••"

    def validate_required_keys(self, required_keys: list[str]) -> dict[str, bool]:
        """
        Valida se as API keys necessarias estao configuradas.

        Args:
            required_keys: Lista de nomes de variaveis necessarias

        Returns:
            Dicionario {key_name: is_configured}
        """
        env_vars = self.read_env_vars()
        result = {}

        for key in required_keys:
            value = env_vars.get(key, "")
            # Considera configurada se existe e nao e valor placeholder
            is_configured = bool(value) and value != "your_api_key_here"
            result[key] = is_configured

        return result
