"""Simulador de usuários para testar o recomendador (dados SINTÉTICOS).

Subcomandos:
    backfill  gera histórico retroativo direto no banco (política de log:
              distância/popularidade/aleatória) para ter dados de treino.
    live      agentes chamam a API de verdade (/recommendations e
              /interactions), exercitando A/B e o modelo em produção.
    report    compara os grupos A/B contra o ranking ideal (oráculo).
    cleanup   remove usuários simulados e tudo que eles geraram.

Exemplo de fluxo:
    python scripts/enrich_restaurants.py
    python scripts/simulate.py backfill --users 300 --days 21 --yes
    python -m app.ml.train --source db
    python scripts/simulate.py live --run-id <id> --rounds 5 --yes
    python scripts/simulate.py report --run-id <id>

IMPORTANTE: rode em um banco separado (DATABASE_URL=.../foodflow_sim). Os
resultados medem o modelo contra as regras deste simulador, não contra
pessoas reais.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import random
import sys
import uuid
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import delete, func, inspect, select  # noqa: E402

from app import crud  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.core.constants import APP_TIMEZONE  # noqa: E402
from app.database import AsyncSessionLocal  # noqa: E402
from app.models import (  # noqa: E402
    ExperimentAssignment,
    Order,
    RecommendationLog,
    Restaurant,
    Review,
    User,
    UserRestaurantInteraction,
)
from app.simulation.behavior import (  # noqa: E402
    DEFAULT_TOP_K,
    SessionResult,
    SimRestaurant,
    haversine_km,
    sample_review,
    simulate_session,
)
from app.simulation.personas import TURNOS, SimUser, sample_user  # noqa: E402
from app.simulation.safety import (  # noqa: E402
    database_label as db_label,
    guard_write,
)
from app.simulation.world import (  # noqa: E402
    SIM_EMAIL_DOMAIN,
    World,
    create_sim_users,
    load_world,
)

RUNS_DIR = BACKEND_ROOT / "sim_runs"
TURNO_HOURS = {"manha": (6, 11), "tarde": (12, 17), "noite": (18, 23), "madrugada": (0, 5)}
NEARBY_LIMIT, NEARBY_RADIUS_KM = 50, 10.0  # espelha GET /recommendations
POLICIES = (("distance", 0.4), ("popularity", 0.3), ("random", 0.3))
POLICY_GROUP = {"distance": "distance", "popularity": "baseline", "random": None}
REVIEW_PROB = 0.3


# ----------------------------------------------------------------- helpers --
def poisson(rng: random.Random, lam: float) -> int:
    limit, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= rng.random()
        if p <= limit:
            return k
        k += 1


def local_to_utc(day, hour: int, minute: int, second: int = 0) -> datetime:
    local = datetime(day.year, day.month, day.day, hour, minute, second, tzinfo=APP_TIMEZONE)
    return local.astimezone(timezone.utc)


def run_dir(run_id: str) -> Path:
    path = RUNS_DIR / run_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def build_users(
    count: int,
    seed: int,
    world: World,
    *,
    user_seed: int | None = None,
    index_offset: int = 0,
) -> list[SimUser]:
    """Determinístico: mesma semente + mesma contagem = mesmos usuários.

    ``index_offset`` permite criar uma coorte de usuários inéditos sob o mesmo
    ``run_id`` (e-mails e IDs distintos) sem colidir com os usuários do
    backfill. ``user_seed`` separa a amostragem de personas do seed usado no
    comportamento.
    """
    rng = random.Random(f"{user_seed if user_seed is not None else seed}:users")
    users = []
    for position in range(count):
        index = index_offset + position
        anchor = rng.choice(world.restaurants)
        home = (anchor.lat + rng.gauss(0, 0.006), anchor.lon + rng.gauss(0, 0.006))
        users.append(sample_user(index, rng, home))
    return users


async def run_has_backfill(session, run_id: str) -> int:
    """Quantos pedidos/interações de backfill já existem para o run."""
    orders = await session.scalar(
        select(func.count())
        .select_from(Order)
        .where(
            Order.simulation_run_id == run_id,
            Order.simulation_mode == "backfill",
        )
    )
    if orders:
        return int(orders)
    interactions = await session.scalar(
        select(func.count())
        .select_from(UserRestaurantInteraction)
        .where(
            UserRestaurantInteraction.event_metadata["sim_run"].astext == run_id,
            UserRestaurantInteraction.event_metadata["sim_mode"].astext
            == "backfill",
        )
    )
    return int(interactions or 0)


def nearby_candidates(user: SimUser, world: World) -> list[SimRestaurant]:
    scored = [
        (haversine_km(user.home_lat, user.home_lon, r.lat, r.lon), r) for r in world.restaurants
    ]
    scored = [(d, r) for d, r in scored if d <= NEARBY_RADIUS_KM]
    scored.sort(key=lambda item: item[0])
    return [r for _, r in scored[:NEARBY_LIMIT]]


def apply_policy(
    policy: str, user: SimUser, candidates: list[SimRestaurant], rng: random.Random
) -> list[SimRestaurant]:
    if policy == "distance":
        return list(candidates)  # já ordenado por distância
    ranked = list(candidates)
    rng.shuffle(ranked)
    if policy == "popularity":
        ranked.sort(key=lambda r: (-r.rating, -r.review_count))
    return ranked


def write_session(path: Path, record: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def session_record(**kw: Any) -> dict[str, Any]:
    result: SessionResult = kw.pop("result")
    return {
        **kw,
        "impressions": result.impressions,
        "clicks": result.clicks,
        "purchased": result.purchased_restaurant_id is not None,
        "purchase_value": result.order_value,
        "ndcg": result.ranking_quality_served,
        "ranking_quality_served": result.ranking_quality_served,
        "candidate_recall": result.candidate_recall,
        "selection_coverage": result.selection_coverage,
        "expected_purchases": result.expected_purchases,
        "oracle_expected_purchases": result.oracle_expected_purchases,
    }


# ---------------------------------------------------------------- backfill --
async def cmd_backfill(args: argparse.Namespace) -> int:
    guard_write(args)
    run_id = args.run_id or datetime.now().strftime("%Y%m%d%H%M%S")
    rng = random.Random(f"{args.seed}:backfill")

    async with AsyncSessionLocal() as session:
        world = await load_world(session)
        existing = await run_has_backfill(session, run_id)
    if len(world.restaurants) < 10:
        print(
            f"Apenas {len(world.restaurants)} restaurantes com cardápio. "
            "Rode scripts/enrich_restaurants.py (e scripts/ingest_osm.py) antes."
        )
        return 1
    if existing and not args.dry_run:
        print(
            f"O run '{run_id}' já possui {existing} eventos de backfill no banco.\n"
            "Repetir o comando duplicaria o histórico. Use outro --run-id ou "
            "limpe antes com: python scripts/simulate.py cleanup --run-id "
            f"{run_id} --yes"
        )
        return 2

    users = build_users(args.users, args.seed, world)
    now_local = datetime.now(APP_TIMEZONE)
    start_day = (now_local - timedelta(days=args.days)).date()
    joined = {u.index: int(u.join_day_fraction * args.days) for u in users}
    created = {u.index: local_to_utc(start_day + timedelta(days=joined[u.index]), 8, 0) for u in users}

    if args.dry_run:
        print(
            json.dumps(
                {
                    "dry_run": True,
                    "run_id": run_id,
                    "database": db_label(),
                    "users": args.users,
                    "days": args.days,
                    "sessions_estimadas": int(
                        args.users * args.days * 1.2 * args.sessions_scale
                    ),
                    "seed": args.seed,
                },
                indent=2,
            )
        )
        return 0

    out = run_dir(run_id)
    (out / "config.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "mode": "backfill",
                "seed": args.seed,
                "users": args.users,
                "days": args.days,
                "database": db_label(),
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
            indent=2,
        )
    )
    sessions_path = out / "sessions.jsonl"
    counters: Counter = Counter()
    reviewed: set[uuid.UUID] = set()
    pending = 0

    async with AsyncSessionLocal() as session:
        ids = await create_sim_users(session, run_id, users, created)
        cand_cache = {u.index: nearby_candidates(u, world) for u in users}

        for day in range(args.days):
            date = start_day + timedelta(days=day)
            for user in users:
                if day < joined[user.index] or not cand_cache[user.index]:
                    continue
                weights = [user.persona.turno_activity[t] for t in TURNOS]
                session_ordinal = 0
                for _ in range(poisson(rng, user.persona.sessions_per_day * args.sessions_scale)):
                    session_ordinal += 1
                    turno = rng.choices(TURNOS, weights=weights)[0]
                    low, high = TURNO_HOURS[turno]
                    when = local_to_utc(date, rng.randint(low, high), rng.randint(0, 59), rng.randint(0, 59))
                    if when > datetime.now(timezone.utc):
                        continue

                    policy = args.policy if args.policy != "mixed" else rng.choices(
                        [p for p, _ in POLICIES], weights=[w for _, w in POLICIES]
                    )[0]
                    candidates = cand_cache[user.index]
                    ranked = apply_policy(policy, user, candidates, rng)
                    result = simulate_session(user, ranked, candidates, turno, rng)
                    group = POLICY_GROUP[policy]
                    # Determinístico por sessão: auditoria e reprodução sem
                    # depender de UUIDs aleatórios.
                    rec_id = str(
                        uuid.uuid5(
                            uuid.NAMESPACE_URL,
                            f"{run_id}:{user.index}:{date.isoformat()}:"
                            f"{turno}:{session_ordinal}",
                        )
                    )
                    user_id = ids[user.index]

                    for offset, ev in enumerate(result.events):
                        session.add(
                            UserRestaurantInteraction(
                                user_id=user_id,
                                restaurant_id=uuid.UUID(ev.restaurant_id),
                                interaction_type=ev.interaction_type,
                                experiment_group=group,
                                experiment_mode="demo",
                                experiment_version=settings.experiment_version,
                                recommendation_id=rec_id,
                                recommendation_position=ev.position,
                                model_version=f"sim-{policy}",
                                event_metadata={
                                    "sim_run": run_id,
                                    "sim_mode": "backfill",
                                },
                                purchase_value=ev.purchase_value,
                                idempotency_key=(
                                    f"{run_id}:{rec_id}:{ev.restaurant_id}:"
                                    f"{ev.interaction_type}"
                                ),
                                created_at=when + timedelta(seconds=offset),
                            )
                        )
                        pending += 1
                    if result.purchased_restaurant_id:
                        rid = uuid.UUID(result.purchased_restaurant_id)
                        restaurant = world.by_id[result.purchased_restaurant_id]
                        session.add(
                            Order(
                                id=uuid.uuid5(
                                    uuid.NAMESPACE_URL, f"{run_id}:{rec_id}:order"
                                ),
                                user_id=user_id, restaurant_id=rid, items=result.order_items,
                                order_value=result.order_value,
                                delivery_fee=restaurant.delivery_fee, status="Entregue",
                                simulation_run_id=run_id,
                                simulation_mode="backfill",
                                created_at=when + timedelta(seconds=len(result.events)),
                            )
                        )
                        counters["orders"] += 1
                        if rng.random() < REVIEW_PROB:
                            rating, comment = sample_review(restaurant, rng)
                            session.add(
                                Review(
                                    id=uuid.uuid5(
                                        uuid.NAMESPACE_URL,
                                        f"{run_id}:{rec_id}:review",
                                    ),
                                    restaurant_id=rid, user_id=user_id, rating=rating,
                                    comment=comment,
                                    idempotency_key=f"{run_id}:{rec_id}:review",
                                    simulation_run_id=run_id,
                                    simulation_mode="backfill",
                                    created_at=when + timedelta(minutes=45),
                                )
                            )
                            reviewed.add(rid)
                            counters["reviews"] += 1
                    counters["sessions"] += 1
                    counters["interactions"] += len(result.events)
                    write_session(
                        sessions_path,
                        session_record(
                            run_id=run_id, mode="backfill", cohort="training",
                            user_index=user.index, user_id=str(user_id),
                            persona=user.persona.key,
                            session_time=when.isoformat(), turno=turno, policy=policy,
                            group=group, recommendation_id=rec_id,
                            n_candidates=len(candidates),
                            n_served=min(len(ranked), DEFAULT_TOP_K),
                            result=result,
                        ),
                    )
                    if pending >= 2000:
                        await session.commit()
                        pending = 0
        await session.commit()
        await refresh_ratings(session, reviewed)

    print(json.dumps({"run_id": run_id, "database": db_label(), **counters}, indent=2))
    print(f"Log de sessões (verdade do simulador): {sessions_path}")
    return 0


async def refresh_ratings(session, restaurant_ids: set[uuid.UUID]) -> None:
    for rid in restaurant_ids:
        restaurant = await session.get(Restaurant, rid)
        if restaurant is not None:
            await crud.refresh_restaurant_rating(session, restaurant)
    await session.commit()


# -------------------------------------------------------------------- live --
async def cmd_live(args: argparse.Namespace) -> int:
    import httpx

    guard_write(args)
    run_id = args.run_id or datetime.now().strftime("%Y%m%d%H%M%S")
    out = RUNS_DIR / run_id
    cfg_path = out / "config.json"
    live_cfg_path = out / "live_config.json"
    previous_live = (
        json.loads(live_cfg_path.read_text()) if live_cfg_path.exists() else None
    )
    if previous_live is not None:
        # Continuar o run mantém a mesma coorte e a mesma amostra de usuários.
        seed = previous_live.get("seed", args.seed)
        n_users = previous_live.get("users", args.users)
    elif cfg_path.exists():
        cfg = json.loads(cfg_path.read_text())
        seed, n_users = cfg["seed"], cfg["users"]
    else:
        seed, n_users = args.seed, args.users

    requested_unseen = bool(getattr(args, "unseen_users", False))
    if previous_live is not None:
        previous_unseen = bool(
            previous_live.get(
                "unseen", previous_live.get("cohort") == "unseen"
            )
        )
        if requested_unseen != previous_unseen:
            print(
                f"O run '{run_id}' já tem sessões live da coorte "
                f"'{previous_live.get('cohort')}'. Use outro --run-id para "
                "trocar entre usuários conhecidos e inéditos; não misture as "
                "duas coortes no mesmo run."
            )
            return 2
        unseen = previous_unseen
        user_seed = previous_live.get("user_seed")
        if user_seed is None:
            user_seed = seed + 1_000_003 if unseen else seed
    else:
        unseen = requested_unseen
        user_seed = (
            args.user_seed
            if getattr(args, "user_seed", None) is not None
            else (seed + 1_000_003 if unseen else seed)
        )
    index_offset = 10_000 if unseen else 0
    cohort = "unseen" if unseen else "known"

    async with AsyncSessionLocal() as session:
        world = await load_world(session)
    if len(world.restaurants) < 10:
        print("Poucos restaurantes com cardápio; rode scripts/enrich_restaurants.py.")
        return 1
    users = build_users(
        n_users,
        seed,
        world,
        user_seed=user_seed,
        index_offset=index_offset,
    )
    sessions_path = out / "live_sessions.jsonl"
    if sessions_path.exists() and not args.append:
        print(
            f"Já existem sessões live em {sessions_path}.\n"
            "Use --append para continuar o mesmo run ou escolha outro --run-id."
        )
        return 2

    if args.dry_run:
        print(
            json.dumps(
                {
                    "dry_run": True,
                    "run_id": run_id,
                    "database": db_label(),
                    "api_url": args.api_url,
                    "users": n_users,
                    "cohort": cohort,
                    "user_seed": user_seed,
                    "rounds": args.rounds,
                },
                indent=2,
            )
        )
        return 0

    out = run_dir(run_id)
    (out / "live_config.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "mode": "live",
                "cohort": cohort,
                "unseen": unseen,
                "user_seed": user_seed,
                "seed": seed,
                "users": n_users,
                "api_url": args.api_url,
                "database": db_label(),
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
            indent=2,
        )
    )
    async with AsyncSessionLocal() as session:
        ids = await create_sim_users(session, run_id, users)

    sem = asyncio.Semaphore(args.concurrency)
    counters: Counter = Counter()
    reviewed: set[uuid.UUID] = set()
    base_rng = random.Random(f"{seed}:live:{datetime.now().timestamp()}")

    def current_turno() -> str:
        hour = datetime.now(APP_TIMEZONE).hour
        return next(t for t, (lo, hi) in TURNO_HOURS.items() if lo <= hour <= hi)

    async with httpx.AsyncClient(base_url=args.api_url, timeout=30) as client:
        try:
            (await client.get("/health")).raise_for_status()
        except Exception as exc:  # noqa: BLE001
            print(f"API indisponível em {args.api_url}: {exc}")
            return 1

        async def one(user: SimUser, round_i: int, rng: random.Random) -> None:
            async with sem:
                turno = current_turno() if args.turno == "auto" else (
                    rng.choices(TURNOS, weights=[user.persona.turno_activity[t] for t in TURNOS])[0]
                    if args.turno == "random" else args.turno
                )
                user_id = ids[user.index]
                # Universo elegível calculado *antes* da API. É contra ele que
                # medimos recall/cobertura, não contra a lista já devolvida.
                candidates = nearby_candidates(user, world)
                if not candidates:
                    counters["empty_candidates"] += 1
                    return
                try:
                    resp = await client.get("/api/v1/recommendations", params={
                        "user_id": str(user_id), "lat": user.home_lat, "lon": user.home_lon,
                        "turno": turno, "mode": "experiment"})
                    resp.raise_for_status()
                except Exception:  # noqa: BLE001
                    counters["recommendation_errors"] += 1
                    return
                h = resp.headers
                group = h.get("X-Experiment-Group")
                rec_id = h.get("X-Recommendation-Id")
                context = {
                    "experiment_group": group, "experiment_mode": "experiment",
                    "experiment_version": h.get("X-Experiment-Version"),
                    "recommendation_id": rec_id, "model_version": h.get("X-Model-Version"),
                }
                recs = [x["id"] for x in resp.json() if x["id"] in world.by_id]
                ranked = [world.by_id[i] for i in recs]
                if not ranked:
                    counters["empty_recommendations"] += 1
                    return
                result = simulate_session(user, ranked, candidates, turno, rng)
                position = {rid: i for i, rid in enumerate(recs)}
                session_key = rec_id or f"{run_id}:{user.index}:{round_i}:{uuid.uuid4()}"

                async def post(ev) -> None:
                    payload = {
                        "user_id": str(user_id), "restaurant_id": ev.restaurant_id,
                        "interaction_type": ev.interaction_type,
                        "recommendation_position": position.get(ev.restaurant_id),
                        "metadata": {
                            "sim_run": run_id,
                            "sim_mode": "live",
                            "cohort": cohort,
                        },
                        **context,
                    }
                    if ev.interaction_type == "PURCHASE":
                        payload["purchase_value"] = ev.purchase_value
                    payload["idempotency_key"] = (
                        f"{session_key}:{ev.restaurant_id}:{ev.interaction_type}"
                    )
                    try:
                        (await client.post("/api/v1/interactions", json=payload)).raise_for_status()
                    except Exception:  # noqa: BLE001
                        counters["interaction_errors"] += 1

                await asyncio.gather(*(post(ev) for ev in result.events))
                if result.purchased_restaurant_id:
                    rid = uuid.UUID(result.purchased_restaurant_id)
                    restaurant = world.by_id[result.purchased_restaurant_id]
                    async with AsyncSessionLocal() as db:
                        db.add(Order(
                            id=uuid.uuid5(
                                uuid.NAMESPACE_URL, f"{session_key}:order"
                            ),
                            user_id=user_id, restaurant_id=rid, items=result.order_items,
                            order_value=result.order_value, delivery_fee=restaurant.delivery_fee,
                            status="Entregue", simulation_run_id=run_id,
                            simulation_mode="live"))
                        if rng.random() < REVIEW_PROB:
                            rating, comment = sample_review(restaurant, rng)
                            db.add(Review(
                                id=uuid.uuid5(
                                    uuid.NAMESPACE_URL, f"{session_key}:review"
                                ),
                                restaurant_id=rid, user_id=user_id, rating=rating,
                                comment=comment,
                                idempotency_key=f"{session_key}:review",
                                simulation_run_id=run_id,
                                simulation_mode="live"))
                            reviewed.add(rid)
                        await db.commit()
                    counters["orders"] += 1
                counters["sessions"] += 1
                write_session(sessions_path, session_record(
                    run_id=run_id, mode="live", cohort=cohort, unseen=unseen,
                    user_index=user.index, user_id=str(user_id),
                    persona=user.persona.key, session_time=datetime.now(timezone.utc).isoformat(),
                    turno=turno, policy=None, group=group, recommendation_id=rec_id,
                    model_version=h.get("X-Model-Version"), strategy=h.get("X-Recommendation-Strategy"),
                    n_candidates=len(candidates),
                    n_served=min(len(ranked), DEFAULT_TOP_K),
                    result=result))

        for round_i in range(args.rounds):
            rng = random.Random(base_rng.random())
            active = [u for u in users if rng.random() < args.active_fraction]
            await asyncio.gather(*(one(u, round_i, random.Random(rng.random())) for u in active))
            print(f"rodada {round_i + 1}/{args.rounds}: {dict(counters)}")

    async with AsyncSessionLocal() as session:
        await refresh_ratings(session, reviewed)
    print(json.dumps({"run_id": run_id, "cohort": cohort, **counters}, indent=2))
    return 0


# ------------------------------------------------------------------ report --
def bootstrap_ratio(num, den, users, n=1000, seed=7):
    """IC 95% de sum(num)/sum(den), reamostrando usuários (não sessões)."""
    import numpy as np

    num_arr = np.asarray(num, dtype=float)
    den_arr = np.asarray(den, dtype=float)
    user_arr = np.asarray(users)
    valid = ~np.isnan(num_arr) & ~np.isnan(den_arr)
    num_arr, den_arr, user_arr = num_arr[valid], den_arr[valid], user_arr[valid]
    if len(num_arr) == 0:
        return float("nan"), float("nan"), float("nan")

    rng = np.random.default_rng(seed)
    uniq = np.unique(user_arr)
    idx = {u: i for i, u in enumerate(uniq)}
    n_arr = np.zeros(len(uniq)); d_arr = np.zeros(len(uniq))
    for u, a, b in zip(user_arr, num_arr, den_arr):
        n_arr[idx[u]] += a; d_arr[idx[u]] += b
    if d_arr.sum() == 0:
        return float("nan"), float("nan"), float("nan")
    point = n_arr.sum() / d_arr.sum()
    picks = rng.integers(0, len(uniq), size=(n, len(uniq)))
    ratios = n_arr[picks].sum(axis=1) / np.maximum(d_arr[picks].sum(axis=1), 1e-12)
    return point, float(np.percentile(ratios, 2.5)), float(np.percentile(ratios, 97.5))


def bootstrap_mean(values, users, n=1000, seed=7):
    """IC 95% da média, reamostrando usuários (não sessões)."""
    import numpy as np

    arr = np.asarray(values, dtype=float)
    user_arr = np.asarray(users)
    mask = ~np.isnan(arr)
    arr = arr[mask]
    user_arr = user_arr[mask]
    if len(arr) == 0:
        return float("nan"), float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    uniq = np.unique(user_arr)
    idx = {u: i for i, u in enumerate(uniq)}
    sums = np.zeros(len(uniq))
    counts = np.zeros(len(uniq))
    for u, value in zip(user_arr, arr):
        sums[idx[u]] += value
        counts[idx[u]] += 1
    point = float(arr.mean())
    picks = rng.integers(0, len(uniq), size=(n, len(uniq)))
    means = sums[picks].sum(axis=1) / np.maximum(counts[picks].sum(axis=1), 1)
    return point, float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def build_report(frame, by: list[str]):
    import pandas as pd

    rows = []
    for key, g in frame.groupby(by, dropna=False):
        key = key if isinstance(key, tuple) else (key,)
        pr, pr_lo, pr_hi = bootstrap_ratio(g["purchased"].astype(float), [1.0] * len(g), g["user_index"])
        ef, ef_lo, ef_hi = bootstrap_ratio(g["expected_purchases"], g["oracle_expected_purchases"], g["user_index"])
        rq, rq_lo, rq_hi = bootstrap_mean(g["ranking_quality_served"], g["user_index"])
        cr, cr_lo, cr_hi = bootstrap_mean(g["candidate_recall"], g["user_index"])
        rows.append({
            **dict(zip(by, ["(sem grupo)" if (isinstance(k, float) and math.isnan(k)) or k is None else k for k in key])),
            "usuarios": g["user_index"].nunique(), "sessoes": len(g),
            "impressoes": int(g["impressions"].sum()), "cliques": int(g["clicks"].sum()),
            "compras": int(g["purchased"].sum()),
            "CTR": g["clicks"].sum() / max(g["impressions"].sum(), 1),
            "compra/sessao": pr, "compra/sessao IC95": f"[{pr_lo:.3f}, {pr_hi:.3f}]",
            "ordenacao servida (NDCG@10)": rq,
            "ordenacao IC95": f"[{rq_lo:.3f}, {rq_hi:.3f}]",
            "recall do top-10 ideal": cr,
            "recall IC95": f"[{cr_lo:.3f}, {cr_hi:.3f}]",
            "cobertura do oraculo": ef,
            "cobertura IC95": f"[{ef_lo:.3f}, {ef_hi:.3f}]",
        })
    return pd.DataFrame(rows)


def _add_period(frame, period: str | None):
    if not period:
        return frame
    import pandas as pd

    frame = frame.copy()
    frame["session_time"] = pd.to_datetime(
        frame["session_time"], utc=True, errors="coerce"
    )
    if period == "day":
        frame["period"] = frame["session_time"].dt.strftime("%Y-%m-%d")
    elif period == "week":
        frame["period"] = (
            frame["session_time"].dt.to_period("W").astype(str)
        )
    else:
        frame["period"] = frame["session_time"].dt.strftime("%Y-%m")
    return frame


def cmd_report(args: argparse.Namespace) -> int:
    import warnings

    warnings.simplefilter("ignore")
    import pandas as pd

    run_path = RUNS_DIR / args.run_id
    paths = [
        path
        for path in (run_path / "sessions.jsonl", run_path / "live_sessions.jsonl")
        if path.exists()
    ]
    if not paths:
        print(f"Sem log de sessões em {run_path}")
        return 1
    frames = [pd.read_json(path, lines=True) for path in paths]
    frame = pd.concat(frames, ignore_index=True, sort=False)
    if "ranking_quality_served" not in frame and "ndcg" in frame:
        frame["ranking_quality_served"] = frame["ndcg"]
    for column in (
        "ranking_quality_served",
        "candidate_recall",
        "selection_coverage",
        "expected_purchases",
        "oracle_expected_purchases",
        "persona",
        "group",
        "cohort",
    ):
        if column not in frame:
            frame[column] = None
    frame = _add_period(frame, args.by_period)

    if args.require_unseen:
        live = frame[frame["mode"] == "live"]
        unseen = live[live["cohort"] == "unseen"]
        if unseen.empty:
            print(
                "Nenhuma sessão live com usuários inéditos. Rode o modo live com "
                "--unseen-users e reporte novamente com --require-unseen."
            )
            return 2

    by = ["mode", "group"]
    if args.by_cohort:
        by.append("cohort")
    if args.by_persona:
        by.append("persona")
    if args.by_period:
        by.append("period")
    report = build_report(frame, by)
    try:
        text = report.to_markdown(index=False, floatfmt=".3f")
    except ImportError:  # tabulate é opcional
        text = report.round(3).to_string(index=False)
    header = (
        f"# Relatório da simulação {args.run_id}\n\n"
        "> Dados **sintéticos**: as métricas medem o recomendador contra as regras "
        "do simulador, não o desempenho com pessoas reais.\n"
        "> `ordenacao servida` (NDCG@10) mede apenas a ordem da lista retornada. "
        "`recall do top-10 ideal` e `cobertura do oraculo` medem a seleção contra "
        "**todos** os candidatos elegíveis; cobertura = compras esperadas da lista "
        "servida ÷ compras esperadas do top-10 ideal (1.0 = perfeito).\n"
        "> ICs por bootstrap de usuários (não de sessões).\n\n"
    )
    (run_path / "report.md").write_text(header + text + "\n", encoding="utf-8")
    report.to_csv(run_path / "report.csv", index=False)
    print(header + text)
    return 0


# ----------------------------------------------------------------- cleanup --
async def _count_or_delete(session, model, condition, dry_run: bool) -> int:
    count = await session.scalar(
        select(func.count()).select_from(model).where(condition)
    )
    if dry_run:
        return int(count or 0)
    result = await session.execute(delete(model).where(condition))
    return int(result.rowcount or 0)


async def cmd_cleanup(args: argparse.Namespace) -> int:
    guard_write(args)
    run_id = args.run_id
    pattern = (
        f"sim-{run_id}-%@{SIM_EMAIL_DOMAIN}"
        if run_id
        else f"sim-%@{SIM_EMAIL_DOMAIN}"
    )
    counts: dict[str, int] = {}
    touched: set[uuid.UUID] = set()
    async with AsyncSessionLocal() as session:
        user_ids = (
            await session.execute(select(User.id).where(User.email.like(pattern)))
        ).scalars().all()

        interaction_filter = UserRestaurantInteraction.user_id.in_(user_ids)
        order_filter = Order.user_id.in_(user_ids)
        review_filter = Review.user_id.in_(user_ids)
        assignment_filter = ExperimentAssignment.user_id.in_(user_ids)
        log_filter = RecommendationLog.user_id.in_(user_ids)
        if run_id:
            interaction_filter = interaction_filter | (
                UserRestaurantInteraction.event_metadata["sim_run"].astext == run_id
            )
            order_filter = order_filter | (Order.simulation_run_id == run_id)
            review_filter = review_filter | (Review.simulation_run_id == run_id)
        else:
            order_filter = order_filter | Order.simulation_run_id.is_not(None)
            review_filter = review_filter | Review.simulation_run_id.is_not(None)

        if not user_ids and not run_id:
            print("Nenhum usuário simulado encontrado.")
            return 0

        touched = set(
            (
                await session.execute(
                    select(Review.restaurant_id).where(review_filter)
                )
            ).scalars().all()
        )
        touched |= set(
            (
                await session.execute(
                    select(Order.restaurant_id).where(order_filter)
                )
            ).scalars().all()
        )

        counts["user_restaurant_interactions"] = await _count_or_delete(
            session, UserRestaurantInteraction, interaction_filter, args.dry_run
        )
        counts["reviews"] = await _count_or_delete(
            session, Review, review_filter, args.dry_run
        )
        counts["orders"] = await _count_or_delete(
            session, Order, order_filter, args.dry_run
        )
        counts["experiment_assignments"] = await _count_or_delete(
            session, ExperimentAssignment, assignment_filter, args.dry_run
        )

        # A tabela pode não existir em ambientes antigos sem a migração 0006.
        has_logs = await session.run_sync(
            lambda sync: inspect(sync.connection()).has_table(
                RecommendationLog.__tablename__
            )
        )
        if has_logs:
            counts["recommendation_logs"] = await _count_or_delete(
                session, RecommendationLog, log_filter, args.dry_run
            )

        if run_id and args.include_restaurants:
            restaurant_ids = (
                await session.execute(
                    select(Restaurant.id).where(
                        Restaurant.simulation_run_id == run_id,
                        Restaurant.source == "synthetic",
                    )
                )
            ).scalars().all()
            if args.dry_run:
                # As referências ainda não foram removidas; informa apenas os
                # candidatos que seriam avaliados.
                counts["synthetic_restaurants"] = len(restaurant_ids)
                counts["synthetic_restaurants_skipped"] = 0
            else:
                safe: list[uuid.UUID] = []
                for rid in restaurant_ids:
                    remaining = 0
                    for model in (Order, Review, UserRestaurantInteraction):
                        remaining += int(
                            await session.scalar(
                                select(func.count())
                                .select_from(model)
                                .where(model.restaurant_id == rid)
                            )
                            or 0
                        )
                    if remaining == 0:
                        safe.append(rid)
                counts["synthetic_restaurants"] = len(safe)
                counts["synthetic_restaurants_skipped"] = len(restaurant_ids) - len(safe)
                if safe:
                    await session.execute(
                        delete(Restaurant).where(Restaurant.id.in_(safe))
                    )

        counts["users"] = await _count_or_delete(
            session, User, User.id.in_(user_ids), args.dry_run
        )

        if args.dry_run:
            await session.rollback()
        else:
            await session.commit()
            await refresh_ratings(session, touched)

    audit = {
        "run_id": run_id,
        "database": db_label(),
        "dry_run": args.dry_run,
        "include_restaurants": args.include_restaurants,
        "counts": counts,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    audit_dir = (RUNS_DIR / run_id) if run_id else RUNS_DIR
    audit_dir.mkdir(parents=True, exist_ok=True)
    audit_path = audit_dir / (
        f"cleanup-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    )
    audit_path.write_text(json.dumps(audit, indent=2), encoding="utf-8")
    print(json.dumps({**audit, "audit_log": str(audit_path)}, indent=2))
    return 0


# -------------------------------------------------------------------- main --
def main() -> int:
    parser = argparse.ArgumentParser(description="Simulador de usuários do FoodFlow")
    sub = parser.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("backfill", help="histórico retroativo direto no banco")
    b.add_argument("--users", type=int, default=200)
    b.add_argument("--days", type=int, default=21)
    b.add_argument("--seed", type=int, default=42)
    b.add_argument("--run-id")
    b.add_argument("--policy", choices=("mixed", "distance", "popularity", "random"), default="mixed")
    b.add_argument("--sessions-scale", type=float, default=1.0)
    b.add_argument("--dry-run", action="store_true", help="mostra o plano sem gravar")
    b.add_argument("--allow-remote-db", action="store_true", help="permite banco de simulação em host remoto")
    b.add_argument("--yes", action="store_true")

    l = sub.add_parser("live", help="agentes usando a API real")
    l.add_argument("--api-url", default="http://localhost:8000")
    l.add_argument("--run-id")
    l.add_argument("--users", type=int, default=100, help="só se o run-id for novo")
    l.add_argument("--seed", type=int, default=42)
    l.add_argument("--user-seed", type=int, help="semente separada para amostrar usuários")
    l.add_argument("--unseen-users", action="store_true", help="cria uma coorte de usuários inéditos (não vistos no backfill)")
    l.add_argument("--rounds", type=int, default=3)
    l.add_argument("--active-fraction", type=float, default=0.6)
    l.add_argument("--concurrency", type=int, default=10)
    l.add_argument("--turno", choices=("auto", "random") + TURNOS, default="auto")
    l.add_argument("--append", action="store_true", help="continua um run live já iniciado")
    l.add_argument("--dry-run", action="store_true", help="mostra o plano sem chamar a API")
    l.add_argument("--allow-remote-db", action="store_true", help="permite banco de simulação em host remoto")
    l.add_argument("--yes", action="store_true")

    r = sub.add_parser("report", help="métricas por grupo contra o oráculo")
    r.add_argument("--run-id", required=True)
    r.add_argument("--by-persona", action="store_true")
    r.add_argument("--by-cohort", action="store_true", help="separa usuários conhecidos e inéditos")
    r.add_argument("--by-period", choices=("day", "week", "month"), help="compara períodos")
    r.add_argument("--require-unseen", action="store_true", help="falha se não houver sessões com usuários inéditos")

    c = sub.add_parser("cleanup", help="remove usuários simulados")
    c.add_argument("--run-id", help="omita para remover TODOS os simulados")
    c.add_argument("--include-restaurants", action="store_true", help="remove restaurantes sintéticos do run")
    c.add_argument("--dry-run", action="store_true", help="conta o que seria removido")
    c.add_argument("--allow-remote-db", action="store_true", help="permite banco de simulação em host remoto")
    c.add_argument("--yes", action="store_true")

    args = parser.parse_args()
    if args.cmd == "report":
        return cmd_report(args)
    handler = {"backfill": cmd_backfill, "live": cmd_live, "cleanup": cmd_cleanup}[args.cmd]
    return asyncio.run(handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
