"""Ingestão de restaurantes do OpenStreetMap para uma região.

Uso:
    python scripts/ingest_osm.py --south -23.55 --west -46.82 \
        --north -23.51 --east -46.77

A região é validada (área máxima de 1 grau²) para proteger a Overpass API.
A operação é idempotente: reexecutar atualiza os registros existentes e
renova ``last_synced_at``.

Para regiões grandes, use ``--tile-size`` para dividir a região em tiles
menores. Com ``--resume`` e ``--checkpoint``, a ingestão pode ser retomada
após uma interrupção (tiles já concluídos são ignorados).
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


def make_tiles(south, west, north, east, step):
    tiles = []
    lat = south
    while lat < north:
        lon = west
        lat_top = min(lat + step, north)
        while lon < east:
            lon_right = min(lon + step, east)
            tiles.append((lat, lon, lat_top, lon_right))
            lon = lon_right
        lat = lat_top
    return tiles


def tile_key(tile):
    return ",".join(f"{value:.6f}" for value in tile)


async def run(args: argparse.Namespace) -> int:
    tiles = make_tiles(args.south, args.west, args.north, args.east, args.tile_size)
    checkpoint_path = Path(args.checkpoint) if args.checkpoint else None
    completed: set[str] = set()
    errors_all: list[str] = []
    totals = {
        "fetched": 0,
        "deduplicated": 0,
        "created": 0,
        "updated": 0,
        "skipped": 0,
    }

    if args.resume and checkpoint_path and checkpoint_path.exists():
        try:
            data = json.loads(checkpoint_path.read_text(encoding="utf-8"))
            completed = set(data.get("completed", []))
        except (OSError, json.JSONDecodeError):
            completed = set()

    for tile in tiles:
        key = tile_key(tile)
        if key in completed:
            continue
        try:
            async with AsyncSessionLocal() as session:
                summary = await ingest_region(
                    session,
                    south=tile[0],
                    west=tile[1],
                    north=tile[2],
                    east=tile[3],
                    category=args.category,
                )
            totals["fetched"] += summary.fetched
            totals["deduplicated"] += summary.deduplicated
            totals["created"] += summary.created
            totals["updated"] += summary.updated
            totals["skipped"] += summary.skipped
            errors_all.extend(summary.errors)
            completed.add(key)
            if checkpoint_path:
                checkpoint_path.write_text(
                    json.dumps({"completed": sorted(completed)}, indent=2),
                    encoding="utf-8",
                )
        except Exception as exc:  # noqa: BLE001
            errors_all.append(f"tile {key}: {exc}")
            if checkpoint_path:
                checkpoint_path.write_text(
                    json.dumps({"completed": sorted(completed)}, indent=2),
                    encoding="utf-8",
                )

    result = {
        "tiles_total": len(tiles),
        "tiles_completed": len(completed),
        "tiles_remaining": len(tiles) - len(completed),
        **totals,
        "error_count": len(errors_all),
        "errors": errors_all[:20],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors_all else 1


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
    parser.add_argument(
        "--tile-size",
        type=float,
        default=0.5,
        help="Tamanho do tile em graus (padrão: 0.5).",
    )
    parser.add_argument(
        "--checkpoint",
        type=str,
        default=None,
        help="Arquivo de checkpoint para retomada.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Retoma a partir do checkpoint.",
    )
    args = parser.parse_args()
    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())
PY