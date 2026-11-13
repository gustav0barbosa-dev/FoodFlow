"""Enriquece restaurantes com cardápio sintético (sem APIs pagas).

Uso:
    python scripts/enrich_restaurants.py --dry-run
    python scripts/enrich_restaurants.py --yes
    python scripts/enrich_restaurants.py --fill-delivery --yes

Regras:
- ``--dry-run`` mostra o que mudaria e não grava;
- sem ``--yes`` o script não grava; o banco de destino é sempre exibido;
- bancos de produção são bloqueados;
- só cria cardápio para restaurantes que ainda não têm itens (idempotente);
- nunca sobrescreve dados vindos do OSM; ``--fill-delivery`` apenas troca os
  valores neutros (frete 0, prazo 20-30) por valores sintéticos determinísticos;
- itens recebem ``source='synthetic'``: não representam o cardápio real.

Para trazer mais restaurantes reais antes, use ``scripts/ingest_osm.py``.
"""

import argparse
import asyncio
import json
import random
import sys
from collections import Counter
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import select  # noqa: E402

from app.database import AsyncSessionLocal  # noqa: E402
from app.models import MenuItem, Restaurant  # noqa: E402
from app.simulation.menu_catalog import archetype_for, build_menu  # noqa: E402
from app.simulation.safety import database_label, guard_write  # noqa: E402

FEES = (0.0, 3.99, 4.99, 5.99, 7.99, 9.99)


def synthetic_delivery(restaurant_id: str) -> tuple[float, int, int]:
    rng = random.Random(f"delivery:{restaurant_id}")
    low = rng.choice((20, 25, 30, 35, 40))
    return rng.choice(FEES), low, low + rng.choice((10, 15, 20))


async def run(args: argparse.Namespace) -> int:
    guard_write(args)
    summary: Counter = Counter()
    by_archetype: Counter = Counter()
    async with AsyncSessionLocal() as session:
        restaurants = (
            (await session.execute(select(Restaurant).where(Restaurant.is_active.is_(True))))
            .scalars()
            .all()
        )
        with_menu = set(
            (await session.execute(select(MenuItem.restaurant_id).distinct())).scalars().all()
        )
        for restaurant in restaurants:
            summary["restaurants"] += 1
            if args.fill_delivery and restaurant.source in ("osm", "synthetic"):
                # Só substitui os valores neutros gravados pela ingestão.
                if (
                    float(restaurant.delivery_fee or 0) == 0.0
                    and restaurant.delivery_time_min == 20
                    and restaurant.delivery_time_max == 30
                ):
                    fee, low, high = synthetic_delivery(str(restaurant.id))
                    restaurant.delivery_fee = fee
                    restaurant.delivery_time_min = low
                    restaurant.delivery_time_max = high
                    summary["delivery_filled"] += 1

            if restaurant.id in with_menu:
                summary["already_had_menu"] += 1
                continue

            archetype = archetype_for(
                list(restaurant.categories or []), restaurant.cuisine, restaurant.name
            )
            by_archetype[archetype] += 1
            for item in build_menu(str(restaurant.id), archetype):
                session.add(MenuItem(restaurant_id=restaurant.id, source="synthetic", **item))
                summary["menu_items_created"] += 1
            summary["menus_created"] += 1

        if args.dry_run:
            await session.rollback()
        else:
            await session.commit()

    print(
        json.dumps(
            {
                "dry_run": args.dry_run,
                "database": database_label(),
                **summary,
                "archetypes": dict(by_archetype),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Cardápio sintético para restaurantes")
    parser.add_argument("--fill-delivery", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="mostra o que mudaria sem gravar")
    parser.add_argument("--allow-remote-db", action="store_true", help="permite banco de simulação em host remoto")
    parser.add_argument("--yes", action="store_true", help="autoriza a gravação")
    return asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
