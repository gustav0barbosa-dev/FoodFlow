"""Batch scoring diário: calcula scores por usuário/turno e grava no Redis.

Uso:
    python scripts/batch_score.py
    python scripts/batch_score.py --turno tarde --turno noite
    python scripts/batch_score.py --user-id <uuid> --dry-run

Agende com cron (Linux), Task Scheduler (Windows) ou pelo profile `batch`
do Docker Compose. O script carrega o modelo do disco; se ele não existir,
grava o fallback por popularidade.
"""
import argparse
import asyncio
import sys
from pathlib import Path
from uuid import UUID

# Quando executado como `python scripts/batch_score.py`, o Python adiciona
# apenas `backend/scripts` ao sys.path. Incluímos `backend/` para importar app.
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.cache.redis_client import SCORE_TTL_SECONDS, close_redis
from app.core.constants import TURNOS, Turno
from app.database import AsyncSessionLocal, engine
from app.ml.batch import score_all_users
from app.ml.recommender import recommender


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Calcula e grava scores de recomendação no Redis.",
    )
    parser.add_argument(
        "--turno",
        action="append",
        choices=TURNOS,
        dest="turnos",
        help="Turno a processar (pode repetir). Padrão: todos.",
    )
    parser.add_argument(
        "--user-id",
        type=UUID,
        help="Processa apenas um usuário.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Calcula sem gravar no Redis.",
    )
    parser.add_argument(
        "--ttl",
        type=int,
        default=SCORE_TTL_SECONDS,
        help=f"TTL dos scores em segundos (padrão: {SCORE_TTL_SECONDS}).",
    )
    args = parser.parse_args(argv)
    if args.ttl <= 0:
        parser.error("--ttl deve ser maior que zero")
    return args


async def run(args: argparse.Namespace) -> int:
    turnos: tuple[Turno, ...] = tuple(args.turnos) if args.turnos else TURNOS
    model_loaded = recommender.load()
    if model_loaded:
        print("Modelo carregado; scores usarão o LightGBM quando houver histórico.")
    else:
        print("Modelo não encontrado; todos os scores usarão popularidade.")

    try:
        async with AsyncSessionLocal() as session:
            results = await score_all_users(
                session,
                turnos=turnos,
                user_id=args.user_id,
                dry_run=args.dry_run,
                ttl=args.ttl,
            )
    finally:
        await close_redis()
        await engine.dispose()

    if not results:
        print("Nenhum score gerado (banco vazio ou usuário inexistente).")
        return 1 if args.user_id is not None else 0

    for result in results:
        cache_status = "dry-run" if args.dry_run else ("ok" if result["cached"] else "falhou")
        print(
            f"[{result['strategy']}] {result['user_name']} ({result['user_id']}) "
            f"turno={result['turno']} restaurantes={result['restaurants']} "
            f"cache={cache_status}"
        )

    model_count = sum(result["strategy"] == "model" for result in results)
    popularity_count = len(results) - model_count
    cached_count = sum(result["cached"] for result in results)
    print(
        f"Resumo: {len(results)} combinações "
        f"({model_count} modelo, {popularity_count} popularidade); "
        f"{cached_count} gravadas no Redis."
    )
    return 0


def main() -> None:
    args = parse_args()
    raise SystemExit(asyncio.run(run(args)))


if __name__ == "__main__":
    main()
