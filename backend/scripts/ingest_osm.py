"""Ingestão de restaurantes do OpenStreetMap para uma região.

Uso:
    python scripts/ingest_osm.py --south -23.55 --west -46.82 \
        --north -23.51 --east -46.77

A região é validada (área máxima de 1 grau²) para proteger a Overpass API.
A operação é idempotente: reexecutar atualiza os registros existentes e
renova ``last_synced_at``.
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.database import AsyncSessionLocal  # noqa: E402
from app.services.osm_ingestion import ingest_region  # noqa: E402


async def run(args: argparse.Namespace) -> int:
    async with AsyncSessionLocal() as session:
        summary = await ingest_region(
            session,
            south=args.south,
            west=args.west,
            north=args.north,
            east=args.east,
            category=args.category,
        )
    print(json.dumps(summary.as_dict(), ensure_ascii=False, indent=2))
    return 0 if not summary.errors else 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Ingestão de restaurantes do OpenStreetMap por região"
    )
    parser.add_argument("--south", type=float, required=True)
    parser.add_argument("--west", type=float, required=True)
    parser.add_argument("--north", type=float, required=True)
    parser.add_argument("--east", type=float, required=True)
    parser.add_argument(
        "--category",
        choices=("restaurant", "fast_food", "cafe", "bar"),
        default=None,
        help="Restringe a uma categoria (padrão: todas).",
    )
    args = parser.parse_args()
    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())
