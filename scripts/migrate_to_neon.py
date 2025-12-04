#!/usr/bin/env python3
"""
Script de migracao de dados do SQLite para PostgreSQL (Neon).

Uso:
    1. Certifica-te que tens o DATABASE_URL do Neon configurado
    2. Executa: python scripts/migrate_to_neon.py

O script vai:
    1. Ler todos os dados do SQLite local
    2. Conectar ao Neon PostgreSQL
    3. Criar as tabelas no Neon
    4. Migrar todos os dados
"""

import os
import sys
from pathlib import Path


# Adicionar root do projeto ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.models import (
    AutomationLog,
    Base,
    Business,
    BusinessSnapshot,
    IntegrationConfig,
    Notification,
    SearchHistory,
    TrackedSearch,
)


# Connection strings
SQLITE_URL = "sqlite:///data/leads.db"
NEON_URL = os.getenv("DATABASE_URL")

if not NEON_URL:
    print("ERRO: DATABASE_URL nao definido!")
    print("Define a variavel de ambiente DATABASE_URL com a connection string do Neon")
    print("\nExemplo:")
    print("export DATABASE_URL='postgresql://user:pass@host/db?sslmode=require'")
    sys.exit(1)


def migrate_data():
    """Migra dados do SQLite para Neon PostgreSQL."""
    print("\n" + "=" * 60)
    print("  Migracao SQLite -> Neon PostgreSQL")
    print("=" * 60)

    # Conectar ao SQLite
    print("\n[1/5] Conectando ao SQLite...")
    sqlite_engine = create_engine(SQLITE_URL, connect_args={"check_same_thread": False})
    SQLiteSession = sessionmaker(bind=sqlite_engine)
    sqlite_session = SQLiteSession()

    # Conectar ao Neon
    print("[2/5] Conectando ao Neon PostgreSQL...")
    neon_engine = create_engine(
        NEON_URL,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
    )
    NeonSession = sessionmaker(bind=neon_engine)
    neon_session = NeonSession()

    # Criar tabelas no Neon
    print("[3/5] Criando tabelas no Neon...")
    Base.metadata.create_all(neon_engine)

    # Migrar dados
    print("[4/5] Migrando dados...")

    # Ordem importa por causa de foreign keys
    tables_to_migrate = [
        ("businesses", Business),
        ("search_history", SearchHistory),
        ("business_snapshots", BusinessSnapshot),
        ("tracked_searches", TrackedSearch),
        ("automation_logs", AutomationLog),
        ("notifications", Notification),
        ("integration_configs", IntegrationConfig),
    ]

    total_migrated = 0

    for table_name, model in tables_to_migrate:
        try:
            # Ler do SQLite
            records = sqlite_session.query(model).all()
            count = len(records)

            if count == 0:
                print(f"  - {table_name}: 0 registos (vazio)")
                continue

            # Inserir no Neon
            for record in records:
                # Criar novo objeto para Neon
                record_dict = {}
                for column in model.__table__.columns:
                    record_dict[column.name] = getattr(record, column.name)

                # Verificar se ja existe (por ID)
                if hasattr(model, "id"):
                    existing = (
                        neon_session.query(model).filter(model.id == record_dict.get("id")).first()
                    )
                    if existing:
                        continue

                new_record = model(**record_dict)
                neon_session.merge(new_record)

            neon_session.commit()
            print(f"  - {table_name}: {count} registos migrados")
            total_migrated += count

        except Exception as e:
            print(f"  - {table_name}: ERRO - {e}")
            neon_session.rollback()

    # Verificar migracao
    print("\n[5/5] Verificando migracao...")
    for table_name, model in tables_to_migrate:
        neon_count = neon_session.query(model).count()
        sqlite_count = sqlite_session.query(model).count()
        status = "OK" if neon_count >= sqlite_count else "ATENCAO"
        print(f"  - {table_name}: SQLite={sqlite_count}, Neon={neon_count} [{status}]")

    # Fechar sessoes
    sqlite_session.close()
    neon_session.close()

    print("\n" + "=" * 60)
    print(f"  Migracao concluida! Total: {total_migrated} registos")
    print("=" * 60)
    print("\nProximos passos:")
    print("  1. Verifica os dados no Neon console")
    print("  2. Testa a aplicacao com DATABASE_URL configurado")
    print("  3. Deploy para Railway com as env vars:\n")
    print("     DATABASE_URL=<neon_connection_string>")
    print("     GOOGLE_PLACES_API_KEY=<your_api_key>")
    print("")


if __name__ == "__main__":
    migrate_data()
