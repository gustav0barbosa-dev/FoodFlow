from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.core.constants import APP_TIMEZONE
from app.ml import recommender as recommender_module
from app.ml.features import build_user_features
from app.ml.recommender import Recommender
from app.ml.train import (
    _fit_and_evaluate,
    build_seed_entities,
    build_training_frame,
    train_from_seed,
)
from app.models import Order, Restaurant, User


def make_restaurant(index: int) -> Restaurant:
    return Restaurant(
        id=uuid4(),
        name=f"Restaurante {index}",
        address=f"Rua {index}",
        categories=["Brasileira"],
        average_rating=4.0 + (index % 5) / 10,
        review_count=50 + index * 20,
        delivery_fee=float(index % 3),
        delivery_time_min=20,
        delivery_time_max=30 + index,
    )


def make_order(user_id, restaurant_id, *, hour: int, days_ago: int) -> Order:
    local = (datetime.now(APP_TIMEZONE) - timedelta(days=days_ago)).replace(
        hour=hour,
        minute=0,
        second=0,
        microsecond=0,
    )
    return Order(
        id=uuid4(),
        user_id=user_id,
        restaurant_id=restaurant_id,
        order_value=30.0 + hour,
        delivery_fee=5.0,
        created_at=local.astimezone(timezone.utc),
    )


def build_fixture():
    restaurants = [make_restaurant(index) for index in range(6)]
    users = [
        User(
            id=uuid4(),
            name=f"Usuário {index}",
            email=f"user{index}@test.dev",
            dietary_preferences=[],
        )
        for index in range(3)
    ]
    orders = []
    for user_index, user in enumerate(users):
        for offset in range(2):
            orders.append(
                make_order(
                    user.id,
                    restaurants[(user_index + offset) % len(restaurants)].id,
                    hour=12 + offset * 6,
                    days_ago=user_index + offset + 1,
                )
            )
    return users, orders, restaurants


def test_build_training_frame_has_positives_and_negatives() -> None:
    users, orders, restaurants = build_fixture()

    frame = build_training_frame(users, orders, restaurants, seed=7)

    assert not frame.empty
    assert set(frame["clicked"].unique()) == {0, 1}
    assert int(frame["clicked"].sum()) == 6
    assert len(frame) > int(frame["clicked"].sum())
    assert "restaurant_rating" in frame.columns
    assert "tarde_avg_value" in frame.columns
    # Cada turno presente no histórico vira um contexto de treino próprio.
    assert int(frame[frame["clicked"] == 1]["is_tarde"].sum()) == 3
    assert int(frame[frame["clicked"] == 1]["is_noite"].sum()) == 3
    assert int(frame[frame["clicked"] == 1]["is_manha"].sum()) == 0


def test_fit_and_evaluate_returns_metrics() -> None:
    users, orders, restaurants = build_fixture()
    frame = build_training_frame(users, orders, restaurants, seed=7)

    model, metrics = _fit_and_evaluate(frame)

    assert metrics["samples"] == len(frame)
    assert metrics["features"] > 0
    assert model is not None


def test_recommender_roundtrip_and_prediction(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(recommender_module, "MODEL_PATH", tmp_path / "model.joblib")
    users, orders, restaurants = build_fixture()
    frame = build_training_frame(users, orders, restaurants, seed=7)
    model, _ = _fit_and_evaluate(frame)
    feature_columns = [column for column in frame.columns if column != "clicked"]

    recommender = Recommender()
    recommender.save(model, feature_columns)
    loaded = Recommender()

    assert loaded.load() is True
    assert loaded.model is not None

    user_features = build_user_features(orders[:2], users[0])
    scores = loaded.predict_scores(user_features, restaurants, "tarde")

    assert set(scores) == {str(restaurant.id) for restaurant in restaurants}
    assert all(0.0 <= score <= 1.0 for score in scores.values())


def test_build_seed_entities_is_deterministic() -> None:
    users, orders, restaurants = build_seed_entities()
    users_again, orders_again, _ = build_seed_entities()

    assert users and orders and restaurants
    assert [user.id for user in users] == [user.id for user in users_again]
    assert [order.id for order in orders] == [order.id for order in orders_again]
    assert {order.user_id for order in orders} <= {user.id for user in users}


def test_train_from_seed_saves_loadable_model(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(recommender_module, "MODEL_PATH", tmp_path / "model.joblib")

    metrics = train_from_seed()

    assert metrics is not None
    assert metrics["samples"] > 0

    loaded = Recommender()
    assert loaded.load() is True
    assert loaded.metadata["source"] == "seed"
