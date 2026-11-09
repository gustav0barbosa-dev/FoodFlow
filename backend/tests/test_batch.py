from datetime import datetime, timezone
from uuid import uuid4

from app.core.constants import APP_TIMEZONE
from app.ml import batch
from app.ml.batch import score_all_users, score_user_turno
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


def make_order(user_id, restaurant_id, *, hour: int = 20) -> Order:
    local = datetime.now(APP_TIMEZONE).replace(
        hour=hour,
        minute=0,
        second=0,
        microsecond=0,
    )
    return Order(
        id=uuid4(),
        user_id=user_id,
        restaurant_id=restaurant_id,
        order_value=35.0,
        delivery_fee=5.0,
        created_at=local.astimezone(timezone.utc),
    )


def make_user(index: int) -> User:
    return User(
        id=uuid4(),
        name=f"Usuário {index}",
        email=f"user{index}@test.dev",
        dietary_preferences=[],
    )


class _FakeScalars:
    def __init__(self, items):
        self._items = items

    def scalars(self):
        return self

    def all(self):
        return self._items


class _FakeSession:
    """Devolve os lotes na ordem das queries: restaurantes, usuários, pedidos."""

    def __init__(self, *batches):
        self._batches = list(batches)

    async def execute(self, _statement):
        return _FakeScalars(self._batches.pop(0))


def test_score_user_turno_falls_back_to_popularity_without_history(monkeypatch) -> None:
    monkeypatch.setattr(batch.recommender, "model", None)
    user = make_user(0)
    restaurants = [make_restaurant(0), make_restaurant(1)]
    orders = [make_order(user.id, restaurants[0].id, hour=20)]

    scores, strategy = score_user_turno(user, orders, restaurants, "tarde")

    assert strategy == batch.STRATEGY_POPULARITY
    assert set(scores) == {str(restaurant.id) for restaurant in restaurants}


def test_score_user_turno_uses_model_when_history_exists(monkeypatch) -> None:
    user = make_user(0)
    restaurants = [make_restaurant(0), make_restaurant(1)]
    orders = [make_order(user.id, restaurants[0].id, hour=20)]
    expected = {str(restaurant.id): 0.7 for restaurant in restaurants}
    calls = []

    monkeypatch.setattr(batch.recommender, "model", object())

    def fake_predict_scores(user_features, candidates, turno):
        calls.append((user_features, candidates, turno))
        return expected

    monkeypatch.setattr(batch.recommender, "predict_scores", fake_predict_scores)

    scores, strategy = score_user_turno(user, orders, restaurants, "noite")

    assert strategy == batch.STRATEGY_MODEL
    assert scores == expected
    assert calls[0][2] == "noite"


async def test_score_all_users_covers_every_turno_and_caches(monkeypatch) -> None:
    users = [make_user(0), make_user(1)]
    restaurants = [make_restaurant(0), make_restaurant(1)]
    orders = [
        make_order(users[0].id, restaurants[0].id, hour=20),
        make_order(users[1].id, restaurants[1].id, hour=20),
    ]
    writes = []

    monkeypatch.setattr(batch.recommender, "model", None)

    async def fake_set_scores(user_id, turno, scores, ttl):
        writes.append((user_id, turno, ttl))
        return True

    monkeypatch.setattr(batch, "set_scores", fake_set_scores)

    session = _FakeSession(restaurants, users, orders)
    results = await score_all_users(session, turnos=("tarde", "noite"))

    assert len(results) == 4
    assert {result["turno"] for result in results} == {"tarde", "noite"}
    assert all(result["strategy"] == batch.STRATEGY_POPULARITY for result in results)
    assert len(writes) == 4
    assert all(ttl == 86400 for _, _, ttl in writes)


async def test_score_all_users_dry_run_does_not_cache(monkeypatch) -> None:
    user = make_user(0)
    restaurants = [make_restaurant(0)]
    orders = [make_order(user.id, restaurants[0].id, hour=12)]

    async def fail_set_scores(*_args, **_kwargs):
        raise AssertionError("dry-run não deve gravar no Redis")

    monkeypatch.setattr(batch.recommender, "model", None)
    monkeypatch.setattr(batch, "set_scores", fail_set_scores)

    session = _FakeSession(restaurants, [user], orders)
    results = await score_all_users(session, turnos=("tarde",), dry_run=True)

    assert len(results) == 1
    assert results[0]["cached"] is False
