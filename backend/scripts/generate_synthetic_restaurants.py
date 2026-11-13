"""Gera restaurantes sintéticos em torno de um ponto (plano B ao OSM).

Útil quando a Overpass limita o uso ou para testar em escala. Os registros
recebem ``source='synthetic'`` e cardápio gerado por ``enrich_restaurants.py``.

Idempotência: cada restaurante recebe um UUID determinístico derivado de
(seed, centro, raio, índice). Repetir o comando com os mesmos parâmetros não
duplica o catálogo. Todos os registros guardam ``simulation_run_id`` para
auditoria e limpeza.

Uso:
    python scripts/generate_synthetic_restaurants.py --count 150 \
        --lat -23.5325 --lon -46.7939 --radius-km 6 --dry-run
    python scripts/generate_synthetic_restaurants.py --count 150 \
        --lat -23.5325 --lon -46.7939 --radius-km 6 --yes
    python scripts/enrich_restaurants.py --fill-delivery --yes
"""

import argparse
import asyncio
import json
import math
import random
import sys
import uuid
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from geoalchemy2 import WKTElement  # noqa: E402

from app.database import AsyncSessionLocal  # noqa: E402
from app.models import Restaurant  # noqa: E402
from app.simulation.safety import database_label, guard_write  # noqa: E402

# (rótulo, nome-base, amenity, cuisine, peso)
KINDS = [
    ("Pizzaria", "Pizzaria", "restaurant", "pizza", 1.2),
    ("Hamburgueria", "Burger", "fast_food", "burger", 1.2),
    ("Japonês", "Sushi", "restaurant", "japanese", 0.8),
    ("Saudável", "Verde", "restaurant", "vegetarian", 0.7),
    ("Brasileira", "Cantina", "restaurant", "brazilian", 1.6),
    ("Lanchonete", "Lanches", "fast_food", "sandwich", 1.4),
    ("Café", "Café", "cafe", "coffee_shop", 0.9),
    ("Árabe", "Esfiharia", "restaurant", "arab", 0.6),
    ("Bar", "Boteco", "bar", None, 0.8),
    ("Italiana", "Trattoria", "restaurant", "italian", 0.7),
    ("Churrascaria", "Churrasco", "restaurant", "steak_house", 0.6),
    ("Sorveteria", "Gelato", "cafe", "ice_cream", 0.5),
]
SURNAMES = ["do Zé", "da Vila", "Central", "Nova", "Express", "do Bairro", "Premium", "da Praça",
            "Sabor Real", "Bom Gosto", "do Chef", "Tradição", "Delícia", "Urbana", "Familiar"]


def default_run_id(args: argparse.Namespace) -> str:
    return (
        f"synth-{args.seed}-{args.lat:.5f}-{args.lon:.5f}-"
        f"{args.radius_km:g}"
    )


def synthetic_restaurant_id(args: argparse.Namespace, index: int) -> uuid.UUID:
    """UUID determinístico: mesmos parâmetros -> mesmo restaurante."""
    key = (
        f"foodflow:synthetic:{args.seed}:{args.lat:.6f}:{args.lon:.6f}:"
        f"{args.radius_km:g}:{index}"
    )
    return uuid.uuid5(uuid.NAMESPACE_URL, key)


async def run(args: argparse.Namespace) -> int:
    guard_write(args)
    run_id = args.run_id or default_run_id(args)
    rng = random.Random(args.seed)
    created = 0
    skipped = 0
    async with AsyncSessionLocal() as session:
        for i in range(args.count):
            label, base, amenity, cuisine, _ = rng.choices(KINDS, weights=[k[4] for k in KINDS])[0]
            radius = args.radius_km * math.sqrt(rng.random())
            angle = rng.uniform(0, 2 * math.pi)
            lat = args.lat + (radius * math.cos(angle)) / 111.0
            lon = args.lon + (radius * math.sin(angle)) / (111.0 * math.cos(math.radians(args.lat)))
            name = f"{base} {rng.choice(SURNAMES)} {i + 1}"
            restaurant_id = synthetic_restaurant_id(args, i)

            if await session.get(Restaurant, restaurant_id) is not None:
                skipped += 1
                continue

            session.add(Restaurant(
                id=restaurant_id,
                name=name, address=f"Endereço sintético {i + 1}",
                description=f"Restaurante sintético do run {run_id}",
                location=WKTElement(f"POINT({lon} {lat})", srid=4326),
                categories=[amenity], cuisine=cuisine, source="synthetic",
                latitude=lat, longitude=lon, is_active=True,
                average_rating=0.0, review_count=0, delivery_fee=0.0,
                delivery_time_min=20, delivery_time_max=30,
                simulation_run_id=run_id,
            ))
            created += 1
        if args.dry_run:
            await session.rollback()
        else:
            await session.commit()
    print(json.dumps({
        "dry_run": args.dry_run,
        "database": database_label(),
        "run_id": run_id,
        "created": created,
        "skipped_existing": skipped,
    }, indent=2))
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Restaurantes sintéticos")
    p.add_argument("--count", type=int, default=100)
    p.add_argument("--lat", type=float, default=-23.5325)
    p.add_argument("--lon", type=float, default=-46.7939)
    p.add_argument("--radius-km", type=float, default=6.0)
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--run-id", help="identificador do run (default determinístico)")
    p.add_argument("--dry-run", action="store_true", help="mostra o que mudaria sem gravar")
    p.add_argument("--allow-remote-db", action="store_true", help="permite banco de simulação em host remoto")
    p.add_argument("--yes", action="store_true", help="autoriza a gravação")
    return asyncio.run(run(p.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
