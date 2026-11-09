"""Cria tabelas, aplica ajustes incrementais e popula o seed idempotente."""
import asyncio
import sys
from pathlib import Path

# Quando executado como `python scripts/init_db.py`, o Python adiciona apenas
# `backend/scripts` ao sys.path. Incluímos `backend/` para importar o pacote app.
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import text

from app.database import AsyncSessionLocal, engine
from app.models import Base
from app.seeds import seed_database

INCREMENTAL_DDL = (
    "ALTER TABLE reviews ADD COLUMN IF NOT EXISTS idempotency_key VARCHAR(120)",
    "CREATE UNIQUE INDEX IF NOT EXISTS ix_reviews_idempotency_key "
    "ON reviews (idempotency_key)",
    "CREATE INDEX IF NOT EXISTS ix_reviews_restaurant_id ON reviews (restaurant_id)",
    "CREATE INDEX IF NOT EXISTS ix_reviews_user_id ON reviews (user_id)",
    "CREATE INDEX IF NOT EXISTS ix_orders_user_id ON orders (user_id)",
    "CREATE INDEX IF NOT EXISTS ix_orders_restaurant_id ON orders (restaurant_id)",
    "CREATE INDEX IF NOT EXISTS ix_restaurants_active ON restaurants (is_active)",
    "CREATE INDEX IF NOT EXISTS idx_events_type_created_at "
    "ON events (type, created_at)",
)


async def init() -> None:
    async with engine.begin() as connection:
        await connection.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
        await connection.run_sync(Base.metadata.create_all)
        for statement in INCREMENTAL_DDL:
            await connection.execute(text(statement))

    async with AsyncSessionLocal() as session:
        summary = await seed_database(session)

    await engine.dispose()
    print(f"✅ Banco inicializado: {summary}")


if __name__ == "__main__":
    asyncio.run(init())
