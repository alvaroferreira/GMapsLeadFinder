"""
Migrations para database schema.

Este ficheiro documenta as mudancas no schema da base de dados
e fornece scripts para aplicar/reverter migrations.
"""

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.database.db import db


class Migration:
    """Base class para migrations."""

    version: str
    description: str

    def up(self, session: Session) -> None:
        """Aplica a migration."""
        raise NotImplementedError

    def down(self, session: Session) -> None:
        """Reverte a migration."""
        raise NotImplementedError


class Migration001_AddConstraintsAndIndexes(Migration):
    """
    Migration 001: Adicionar constraints e indices.

    Mudancas:
    - Adicionar NOT NULL em campos criticos (lead_status, enrichment_status, timestamps)
    - Adicionar indices compostos para queries comuns
    - Melhorar performance de queries de filtro
    """

    version = "001"
    description = "Adicionar constraints NOT NULL e indices compostos"

    def up(self, session: Session) -> None:
        """Aplica constraints e indices."""
        # Para PostgreSQL
        if db.is_postgresql:
            # Adicionar constraints NOT NULL (se ainda nao existem)
            session.execute(
                text("""
                ALTER TABLE businesses
                ALTER COLUMN lead_status SET NOT NULL,
                ALTER COLUMN enrichment_status SET NOT NULL,
                ALTER COLUMN first_seen_at SET NOT NULL,
                ALTER COLUMN last_updated_at SET NOT NULL;
            """)
            )

            # Adicionar indices compostos (IF NOT EXISTS e PostgreSQL 9.5+)
            session.execute(
                text("""
                CREATE INDEX IF NOT EXISTS idx_enrichment
                ON businesses (enrichment_status, has_website);
            """)
            )

            session.execute(
                text("""
                CREATE INDEX IF NOT EXISTS idx_score_status
                ON businesses (lead_score, lead_status);
            """)
            )

            session.execute(
                text("""
                CREATE INDEX IF NOT EXISTS idx_website_score
                ON businesses (has_website, lead_score);
            """)
            )

        # Para SQLite (nao suporta ALTER COLUMN, apenas CREATE INDEX)
        else:
            session.execute(
                text("""
                CREATE INDEX IF NOT EXISTS idx_enrichment
                ON businesses (enrichment_status, has_website);
            """)
            )

            session.execute(
                text("""
                CREATE INDEX IF NOT EXISTS idx_score_status
                ON businesses (lead_score, lead_status);
            """)
            )

            session.execute(
                text("""
                CREATE INDEX IF NOT EXISTS idx_website_score
                ON businesses (has_website, lead_score);
            """)
            )

        session.commit()

    def down(self, session: Session) -> None:
        """Remove constraints e indices."""
        # Remover indices
        session.execute(text("DROP INDEX IF EXISTS idx_enrichment;"))
        session.execute(text("DROP INDEX IF EXISTS idx_score_status;"))
        session.execute(text("DROP INDEX IF EXISTS idx_website_score;"))

        # Para PostgreSQL, remover constraints
        if db.is_postgresql:
            session.execute(
                text("""
                ALTER TABLE businesses
                ALTER COLUMN lead_status DROP NOT NULL,
                ALTER COLUMN enrichment_status DROP NOT NULL,
                ALTER COLUMN first_seen_at DROP NOT NULL,
                ALTER COLUMN last_updated_at DROP NOT NULL;
            """)
            )

        session.commit()


def run_migrations() -> None:
    """
    Executa todas as migrations pendentes.

    Esta funcao deve ser chamada no startup da aplicacao
    para garantir que o schema esta atualizado.
    """
    migrations = [
        Migration001_AddConstraintsAndIndexes(),
    ]

    with db.get_session() as session:
        for migration in migrations:
            try:
                print(f"[Migration] Aplicando {migration.version}: {migration.description}")
                migration.up(session)
                print(f"[Migration] {migration.version} aplicada com sucesso")
            except Exception as e:
                print(f"[Migration] Erro ao aplicar {migration.version}: {e}")
                # Se erro, tentar continuar (os indices podem ja existir)
                continue


if __name__ == "__main__":
    print("Executando migrations...")
    run_migrations()
    print("Migrations concluidas")
