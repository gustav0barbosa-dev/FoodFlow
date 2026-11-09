"""Script para criar tabelas e popular seed no banco de dados."""
import asyncio
from sqlalchemy import text
from app.database import engine, AsyncSessionLocal
from app.models import Base
from app.seeds import seed_restaurants


async def init():
    async with engine.begin() as conn:
        # Habilita extensão PostGIS
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
        # Cria todas as tabelas
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        await seed_restaurants(session)
        print("✅ Banco inicializado com seed de restaurantes")


if __name__ == "__main__":
    asyncio.run(init())
