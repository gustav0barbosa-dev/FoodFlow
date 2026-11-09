"""Aplica as migrações Alembic e popula o seed idempotente."""
import asyncio
import sys
from pathlib import Path

# Quando executado como `python scripts/init_db.py`, o Python adiciona apenas
# `backend/scripts` ao sys.path. Incluímos `backend/` para importar o pacote app.
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from app.core.config import settings
from app.database import AsyncSessionLocal, engine
from app.seeds import seed_database


def sync_database_url(url: str | None = None) -> str:
    """A API usa asyncpg; o Alembic executa migrações com driver síncrono."""
    return (url or settings.database_url).replace(
        "postgresql+asyncpg://",
        "postgresql+psycopg2://",
    )


def get_alembic_config() -> Config:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.attributes["configure_logger"] = False
    return config


def _database_state() -> tuple[bool, bool]:
    """Retorna (tem alembic_version, tem tabela restaurants)."""
    probe_engine = create_engine(sync_database_url(), pool_pre_ping=True)
    try:
        with probe_engine.connect() as connection:
            has_version = (
                connection.execute(
                    text("SELECT to_regclass('public.alembic_version')")
                ).scalar()
                is not None
            )
            has_schema = (
                connection.execute(
                    text("SELECT to_regclass('public.restaurants')")
                ).scalar()
                is not None
            )
    finally:
        probe_engine.dispose()
    return has_version, has_schema


def run_migrations() -> None:
    """Atualiza o schema, marcando como baseline bancos criados via create_all."""
    config = get_alembic_config()
    has_version, has_schema = _database_state()

    if has_schema and not has_version:
        command.stamp(config, "head")
        print("ℹ️ Schema existente detectado; baseline Alembic marcado (stamp head).")

    command.upgrade(config, "head")


async def _seed() -> dict[str, int]:
    async with AsyncSessionLocal() as session:
        summary = await seed_database(session)
    await engine.dispose()
    return summary


def init() -> None:
    run_migrations()
    summary = asyncio.run(_seed())
    print(f"✅ Banco inicializado: {summary}")


if __name__ == "__main__":
    init()
