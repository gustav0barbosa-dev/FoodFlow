from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.core.constants import APP_TIMEZONE
from app.ml.features import (
    build_candidate_features,
    build_user_features,
    has_turno_history,
    turno_da_hora,
)
from app.models import Order, Restaurant, User


def make_order(
    restaurant_id,
    *,
    hour: int,
    days_ago: int,
    value: float,
    fee: float,
) -> Order:
    local = (datetime.now(APP_TIMEZONE) - timedelta(days=days_ago)).replace(
        hour=hour,
        minute=0,
        second=0,
        microsecond=0,
    )
    return Order(
        id=uuid4(),
        user_id=uuid4(),
        restaurant_id=restaurant_id,
        order_value=value,
        delivery_fee=fee,
        created_at=local.astimezone(timezone.utc),
    )


def make_restaurant(*, rating: float = 4.5, reviews: int = 100) -> Restaurant:
    restaurant = Restaurant(
        id=uuid4(),
        name="Teste",
        address="Rua Teste, 1",
        categories=["Brasileira"],
        average_rating=rating,
        review_count=reviews,
        delivery_fee=5.0,
        delivery_time_min=20,
        delivery_time_max=30,
    )
    return restaurant


def test_turno_da_hora_boundaries() -> None:
    assert turno_da_hora(0) == "madrugada"
    assert turno_da_hora(5) == "madrugada"
    assert turno_da_hora(6) == "manha"
    assert turno_da_hora(11) == "manha"
    assert turno_da_hora(12) == "tarde"
    assert turno_da_hora(17) == "tarde"
    assert turno_da_hora(18) == "noite"
    assert turno_da_hora(23) == "noite"


def test_build_user_features_aggregates_by_turno() -> None:
    user = User(
        id=uuid4(),
        name="Ana",
        email="ana@test.dev",
        dietary_preferences=["Vegetariano"],
    )
    morning = make_order(uuid4(), hour=9, days_ago=1, value=20.0, fee=5.0)
    morning_2 = make_order(uuid4(), hour=10, days_ago=2, value=30.0, fee=7.0)
    night = make_order(uuid4(), hour=20, days_ago=3, value=50.0, fee=0.0)

    features = build_user_features([morning, morning_2, night], user)

    assert features["total_orders"] == 3
    assert features["manha_count"] == 2
    assert features["manha_avg_value"] == 25.0
    assert features["manha_avg_fee"] == 6.0
    assert features["noite_count"] == 1
    assert features["noite_avg_value"] == 50.0
    assert features["tarde_count"] == 0
    assert features["has_dietary_preferences"] == 1.0


def test_top_restaurant_uses_recency_weight() -> None:
    recent_id = uuid4()
    old_id = uuid4()
    orders = [
        make_order(recent_id, hour=13, days_ago=1, value=30.0, fee=0.0),
        make_order(old_id, hour=13, days_ago=60, value=30.0, fee=0.0),
        make_order(old_id, hour=13, days_ago=70, value=30.0, fee=0.0),
    ]

    features = build_user_features(orders, user=None)

    assert features["tarde_top_restaurant"] == str(recent_id)
    assert features["total_orders"] == 3


def test_build_candidate_features_marks_top_restaurant() -> None:
    restaurant = make_restaurant(rating=4.8, reviews=250)
    user_features = {
        "total_orders": 5,
        "has_dietary_preferences": 0.0,
        "tarde_top_restaurant": str(restaurant.id),
        "tarde_avg_value": 40.0,
        "tarde_avg_fee": 5.0,
        "tarde_count": 3.0,
    }

    row = build_candidate_features(user_features, restaurant, "tarde")

    assert row["restaurant_rating"] == 4.8
    assert row["restaurant_review_count"] == 250.0
    assert row["restaurant_delivery_time_avg"] == 25.0
    assert row["tarde_is_top_restaurant"] == 1.0
    assert row["manha_is_top_restaurant"] == 0.0
    assert row["tarde_avg_value"] == 40.0
    assert row["is_tarde"] == 1.0
    assert row["is_manha"] == 0.0
    assert row["is_noite"] == 0.0
    assert row["is_madrugada"] == 0.0


def test_has_turno_history_uses_local_timezone() -> None:
    morning = make_order(uuid4(), hour=9, days_ago=1, value=20.0, fee=5.0)
    night = make_order(uuid4(), hour=20, days_ago=1, value=30.0, fee=5.0)
    orders = [morning, night]

    assert has_turno_history(orders, "manha") is True
    assert has_turno_history(orders, "noite") is True
    assert has_turno_history(orders, "tarde") is False
    assert has_turno_history([], "tarde") is False
