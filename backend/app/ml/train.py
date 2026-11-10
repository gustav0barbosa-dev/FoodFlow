"""Treino offline do recomendador LightGBM com dados de pedidos do banco."""
import asyncio
import logging
import random
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import pandas as pd
from lightgbm import LGBMClassifier
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import APP_TIMEZONE, TURNOS, Turno
from app.database import AsyncSessionLocal
from app.ml.features import (
    build_candidate_features,
    build_user_features,
    order_turno,
)
from app.ml.recommender import recommender
from app.models import Order, Restaurant, User
from app.seed_data import SEED_NAMESPACE, SEED_ORDERS, SEED_RESTAURANTS, SEED_USERS

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


def _stable_id(value: str) -> uuid.UUID:
    return uuid.uuid5(SEED_NAMESPACE, value)


def build_seed_entities(
    now: datetime | None = None,
) -> tuple[list[User], list[Order], list[Restaurant]]:
    """Monta entidades em memória a partir do seed determinístico.

    Permite treinar o modelo em ambientes sem PostgreSQL/PostGIS (por
    exemplo, CI ou desenvolvimento local), usando exatamente os mesmos
    dados que o `seed_database` gravaria no banco.
    """
    users = [
        User(
            id=_stable_id(f"user:{data['email']}"),
            name=data["name"],
            email=data["email"],
            dietary_preferences=list(data["dietary_preferences"]),
        )
        for data in SEED_USERS
    ]
    restaurants = [
        Restaurant(
            id=_stable_id(f"restaurant:{data['name']}"),
            name=data["name"],
            description=f"Melhor {data['category'].lower()} de Osasco",
            phone="+55 11 99999-0000",
            address=data["address"],
            categories=[data["category"]],
            average_rating=data["rating"],
            review_count=data["review_count"],
            delivery_fee=data["delivery_fee"],
            delivery_time_min=data["delivery_time_min"],
            delivery_time_max=data["delivery_time_max"],
            image_url=data["image_url"],
        )
        for data in SEED_RESTAURANTS
    ]

    users_by_email = {user.email: user for user in users}
    restaurants_by_name = {restaurant.name: restaurant for restaurant in restaurants}
    menu_by_name = {
        item["name"]: item["menu_item"] for item in SEED_RESTAURANTS
    }

    local_now = now or datetime.now(APP_TIMEZONE)
    orders: list[Order] = []
    for index, (email, restaurant_name, days_ago, hour, quantity) in enumerate(
        SEED_ORDERS
    ):
        user = users_by_email.get(email)
        restaurant = restaurants_by_name.get(restaurant_name)
        menu_item = menu_by_name.get(restaurant_name)
        if user is None or restaurant is None or menu_item is None:
            continue

        created_at = (local_now - timedelta(days=days_ago)).replace(
            hour=hour,
            minute=0,
            second=0,
            microsecond=0,
        )
        orders.append(
            Order(
                id=_stable_id(f"order:{index}"),
                user_id=user.id,
                restaurant_id=restaurant.id,
                items=[
                    {
                        "id": menu_item["id"],
                        "name": menu_item["name"],
                        "quantity": quantity,
                        "price": menu_item["price"],
                    }
                ],
                order_value=round(menu_item["price"] * quantity, 2),
                delivery_fee=float(restaurant.delivery_fee),
                status="Entregue",
                created_at=created_at.astimezone(timezone.utc),
            )
        )

    return users, orders, restaurants


def train_from_seed() -> dict[str, Any] | None:
    """Treina o LightGBM usando o seed determinístico, sem acessar o banco."""
    users, orders, restaurants = build_seed_entities()
    frame = build_training_frame(users, orders, restaurants)
    if frame.empty or frame["clicked"].nunique() < 2:
        return None

    model, metrics = _fit_and_evaluate(frame)
    feature_columns = [column for column in frame.columns if column != "clicked"]
    recommender.save(
        model,
        feature_columns,
        metadata={**metrics, "source": "seed"},
    )
    return metrics


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


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Treino offline do recomendador LightGBM")
    parser.add_argument(
        "--source",
        choices=("db", "seed"),
        default="db",
        help="'db' usa os pedidos do PostgreSQL; 'seed' usa o seed determinístico.",
    )
    args = parser.parse_args()

    if args.source == "seed":
        result = train_from_seed()
    else:
        result = asyncio.run(train())

    if result is None:
        print("Dados insuficientes para treino; modelo nao salvo.")
        return 1

    print(f"Modelo treinado ({args.source}): {result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
