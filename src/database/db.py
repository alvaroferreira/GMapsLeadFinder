"""Conexao e gestao da base de dados."""

import os
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from src.config import settings
from src.database.models import Base


class Database:
    """Gestao da conexao a base de dados."""

    def __init__(self, url: str | None = None):
        """
        Inicializa a base de dados.

        Args:
            url: URL de conexao. Se None, usa DATABASE_URL env var ou settings.database_url
        """
        # Prioridade: parametro > DATABASE_URL env var > settings
        self.url = url or os.getenv("DATABASE_URL") or settings.database_url

        # Determinar se e PostgreSQL ou SQLite
        self.is_postgresql = self.url.startswith("postgresql")

        if not self.is_postgresql:
            self._ensure_directory()

        # Configurar engine com parametros apropriados
        engine_kwargs = {
            "echo": False,
            "pool_pre_ping": True,
        }

        if self.is_postgresql:
            # PostgreSQL (Neon) - connection pooling
            engine_kwargs.update(
                {
                    "pool_size": 5,
                    "max_overflow": 10,
                }
            )
        else:
            # SQLite - desativar check_same_thread
            engine_kwargs["connect_args"] = {"check_same_thread": False}

        self.engine: Engine = create_engine(self.url, **engine_kwargs)
        self._session_factory = sessionmaker(bind=self.engine)

    def _ensure_directory(self) -> None:
        """Cria directorio da base de dados se nao existir (para SQLite)."""
        if self.url.startswith("sqlite:///"):
            db_path = Path(self.url.replace("sqlite:///", ""))
            db_path.parent.mkdir(parents=True, exist_ok=True)

    def create_tables(self) -> None:
        """Cria todas as tabelas definidas nos modelos."""
        Base.metadata.create_all(self.engine)

    def drop_tables(self) -> None:
        """Remove todas as tabelas (usar com cuidado!)."""
        Base.metadata.drop_all(self.engine)

    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """
        Context manager para obter uma sessao da DB.

        Usage:
            with db.get_session() as session:
                session.query(Business).all()

        Yields:
            Session: Sessao SQLAlchemy
        """
        session = self._session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def get_new_session(self) -> Session:
        """
        Retorna uma nova sessao (o caller e responsavel por fechar).

        Returns:
            Session: Nova sessao SQLAlchemy
        """
        return self._session_factory()


def get_db(url: str | None = None) -> Database:
    """
    Factory para obter instancia da base de dados.

    Args:
        url: URL de conexao opcional

    Returns:
        Database: Instancia configurada
    """
    return Database(url)


# Instancia global
db = Database()
