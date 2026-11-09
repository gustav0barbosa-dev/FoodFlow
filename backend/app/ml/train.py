"""Treino offline do recomendador LightGBM com dados de pedidos do banco."""
import asyncio
import logging
import random
from typing import Any

import pandas as pd
from lightgbm import LGBMClassifier
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import TURNOS, Turno
from app.database import AsyncSessionLocal
from app.ml.features import (
    build_candidate_features,
    build_user_features,
    order_turno,
)
from app.ml.recommender import recommender
from app.models import Order, Restaurant, User

logger = logging.getLogger(__name__)

NEGATIVES_PER_POSITIVE = 3
RANDOM_SEED = 42


def build_training_frame(
    users: list[User],
    orders: list[Order],
    restaurants: list[Restaurant],
    negatives_per_positive: int = NEGATIVES_PER_POSITIVE,
    seed: int = RANDOM_SEED,
) -> pd.DataFrame:
    """Gera amostras (usuário, restaurante, turno) com 1 positivo : N negativos.

    Cada turno vira um contexto independente. Para evitar vazamento, as
    features de um positivo são calculadas sem os pedidos daquele restaurante
    (leave-one-restaurant-out).
    """
    if not users or not restaurants:
        return pd.DataFrame()

    restaurant_by_id = {restaurant.id: restaurant for restaurant in restaurants}
    rng = random.Random(seed)
    rows: list[dict[str, Any]] = []

    for user in users:
        user_orders = [order for order in orders if order.user_id == user.id]
        if not user_orders:
            continue

        orders_by_turno: dict[Turno, list[Order]] = {turno: [] for turno in TURNOS}
        for order in user_orders:
            orders_by_turno[order_turno(order)].append(order)

        for turno in TURNOS:
            turno_orders = orders_by_turno[turno]
            if not turno_orders:
                continue

            positive_ids = sorted(
                {
                    order.restaurant_id
                    for order in turno_orders
                    if order.restaurant_id in restaurant_by_id
                }
            )
            if not positive_ids:
                continue

            for restaurant_id in positive_ids:
                history_without_target = [
                    order
                    for order in user_orders
                    if order.restaurant_id != restaurant_id
                ]
                features = build_user_features(history_without_target, user)
                row = build_candidate_features(
                    features,
                    restaurant_by_id[restaurant_id],
                    turno,
                )
                row["clicked"] = 1
                rows.append(row)

            negative_candidates = [
                restaurant
                for restaurant in restaurants
                if restaurant.id not in set(positive_ids)
            ]
            sample_size = min(
                len(negative_candidates),
                max(1, len(positive_ids) * negatives_per_positive),
            )
            if sample_size == 0:
                continue

            features = build_user_features(user_orders, user)
            for restaurant in rng.sample(negative_candidates, sample_size):
                row = build_candidate_features(features, restaurant, turno)
                row["clicked"] = 0
                rows.append(row)

    return pd.DataFrame(rows)


def _fit_and_evaluate(frame: pd.DataFrame) -> tuple[LGBMClassifier, dict[str, Any]]:
    feature_columns = [column for column in frame.columns if column != "clicked"]
    X = frame[feature_columns].fillna(0.0).astype(float)
    y = frame["clicked"].astype(int)

    model = LGBMClassifier(
        n_estimators=200,
        max_depth=5,
        num_leaves=15,
        learning_rate=0.05,
        min_child_samples=5,
        subsample=0.9,
        colsample_bytree=0.9,
        is_unbalance=True,
        random_state=RANDOM_SEED,
        verbose=-1,
    )

    auc: float | None = None
    if len(frame) >= 40 and y.nunique() == 2:
        try:
            X_train, X_test, y_train, y_test = train_test_split(
                X,
                y,
                test_size=0.25,
                random_state=RANDOM_SEED,
                stratify=y,
            )
            model.fit(X_train, y_train)
            auc = float(roc_auc_score(y_test, model.predict_proba(X_test)[:, 1]))
        except ValueError:
            model.fit(X, y)

    if auc is None:
        model.fit(X, y)

    metrics = {
        "samples": int(len(frame)),
        "positives": int(y.sum()),
        "negatives": int((1 - y).sum()),
        "features": len(feature_columns),
        "roc_auc": round(auc, 4) if auc is not None else None,
    }
    return model, metrics


async def load_training_data(
    session: AsyncSession,
) -> tuple[list[User], list[Order], list[Restaurant]]:
    users = (await session.execute(select(User))).scalars().all()
    orders = (await session.execute(select(Order))).scalars().all()
    restaurants = (await session.execute(select(Restaurant))).scalars().all()
    return list(users), list(orders), list(restaurants)


async def train() -> dict[str, Any] | None:
    async with AsyncSessionLocal() as session:
        users, orders, restaurants = await load_training_data(session)

    frame = build_training_frame(users, orders, restaurants)
    if frame.empty or frame["clicked"].nunique() < 2:
        return None

    model, metrics = _fit_and_evaluate(frame)
    feature_columns = [column for column in frame.columns if column != "clicked"]
    recommender.save(model, feature_columns, metadata=metrics)

    # Salva a distribuição de treino (baseline) para cada feature monitorada,
    # usada futuramente pelo monitoramento de drift.
    try:
        from app.services.drift import drift_monitor  # evita import circular

        for feature in drift_monitor.feature_names:
            if feature in frame.columns:
                values = frame[feature].dropna().astype(float).tolist()
                await drift_monitor.save_baseline(feature, values)
    except Exception as exc:  # não deve falhar o treino por causa do drift
        logger.warning("Falha ao salvar baseline de drift: %s", exc)

    return metrics


if __name__ == "__main__":
    result = asyncio.run(train())
    if result is None:
        print("⚠️ Dados insuficientes para treino; modelo não salvo.")
    else:
        print(f"✅ Modelo treinado: {result}")
