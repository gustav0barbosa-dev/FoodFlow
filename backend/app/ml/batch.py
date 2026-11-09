"""Scoring em lote dos restaurantes por usuário e turno.

O job grava no Redis o mesmo formato consumido pela API
(`reco:scores:{user_id}:{turno}`), antecipando o trabalho que hoje acontece
no cache miss. A execução é feita por `scripts/batch_score.py`, agendada por
cron/Task Scheduler ou pelo profile `batch` do Docker Compose.
"""
import logging
from collections import defaultdict
from typing import Any, Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache.redis_client import SCORE_TTL_SECONDS, set_scores
from app.core.constants import TURNOS, Turno
from app.ml.features import build_user_features, has_turno_history
from app.ml.recommender import popularity_scores, recommender
from app.models import Order, Restaurant, User

logger = logging.getLogger(__name__)

STRATEGY_MODEL = "model"
STRATEGY_POPULARITY = "popularity"


def score_user_turno(
    user: User,
    orders: list[Order],
    restaurants: list[Restaurant],
    turno: Turno,
) -> tuple[dict[str, float], str]:
    """Calcula os scores de um usuário para um turno.

    O modelo só é usado quando o usuário tem histórico no turno solicitado;
    caso contrário aplica-se o mesmo fallback por popularidade da API.
    """
    if (
        restaurants
        and user is not None
        and orders
        and recommender.model is not None
        and has_turno_history(orders, turno)
    ):
        user_features = build_user_features(orders, user)
        scores = recommender.predict_scores(user_features, restaurants, turno)
        return scores, STRATEGY_MODEL

    return popularity_scores(restaurants), STRATEGY_POPULARITY


async def load_active_restaurants(session: AsyncSession) -> list[Restaurant]:
    result = await session.execute(
        select(Restaurant).where(Restaurant.is_active.is_(True))
    )
    return list(result.scalars().all())


async def score_all_users(
    session: AsyncSession,
    turnos: Sequence[Turno] = TURNOS,
    user_id: UUID | None = None,
    dry_run: bool = False,
    ttl: int = SCORE_TTL_SECONDS,
) -> list[dict[str, Any]]:
    """Calcula e grava (salvo `dry_run`) os scores de todos os usuários.

    Retorna um resumo por (usuário, turno) com a estratégia usada e se a
    gravação no Redis funcionou.
    """
    restaurants = await load_active_restaurants(session)
    if not restaurants:
        logger.warning("Nenhum restaurante ativo; batch scoring ignorado.")
        return []

    users_statement = select(User).order_by(User.name)
    if user_id is not None:
        users_statement = users_statement.where(User.id == user_id)
    users = list((await session.execute(users_statement)).scalars().all())
    if not users:
        return []

    orders = list(
        (
            await session.execute(
                select(Order).where(Order.user_id.in_([user.id for user in users]))
            )
        )
        .scalars()
        .all()
    )
    orders_by_user: dict[UUID, list[Order]] = defaultdict(list)
    for order in orders:
        orders_by_user[order.user_id].append(order)

    results: list[dict[str, Any]] = []
    for user in users:
        user_orders = orders_by_user[user.id]
        for turno in turnos:
            scores, strategy = score_user_turno(
                user,
                user_orders,
                restaurants,
                turno,
            )
            cached = False
            if not dry_run:
                cached = await set_scores(
                    str(user.id),
                    turno,
                    scores,
                    ttl=ttl,
                )
            results.append(
                {
                    "user_id": str(user.id),
                    "user_name": user.name,
                    "turno": turno,
                    "strategy": strategy,
                    "restaurants": len(scores),
                    "cached": cached,
                }
            )

    return results
