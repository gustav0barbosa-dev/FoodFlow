from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.models import Restaurant, User, UserRestaurantInteraction
from app.services import interactions as interaction_service


def make_restaurant(name: str, categories: list[str]) -> Restaurant:
    return Restaurant(
        id=uuid4(),
        name=name,
        address="Rua Teste, 1",
        categories=categories,
        average_rating=4.5,
        review_count=10,
        delivery_fee=5.0,
        delivery_time_min=20,
        delivery_time_max=30,
    )


def make_interaction(
    user_id,
    restaurant_id,
    interaction_type: str,
    *,
    purchase_value: float | None = None,
    days_ago: int = 0,
) -> UserRestaurantInteraction:
    return UserRestaurantInteraction(
        id=uuid4(),
        user_id=user_id,
        restaurant_id=restaurant_id,
        interaction_type=interaction_type,
        purchase_value=purchase_value,
        created_at=datetime.now(timezone.utc) - timedelta(days=days_ago),
    )


def test_summarize_preferences_prioritizes_purchases() -> None:
    user_id = uuid4()
    burger = make_restaurant("Burger", ["Fast food"])
    salad = make_restaurant("Salada", ["Saudável"])
    interactions = [
        make_interaction(user_id, burger.id, "PURCHASE", purchase_value=50.0),
        make_interaction(user_id, salad.id, "VIEW"),
    ]

    profile = interaction_service.summarize_preferences(
        user_id, interactions, [burger, salad]
    )

    assert profile["total_interactions"] == 2
    assert profile["purchases"] == 1
    assert profile["views"] == 1
    assert profile["total_spent"] == 50.0
    assert profile["top_categories"][0]["name"] == "Fast food"
    assert profile["top_restaurants"][0]["restaurant_id"] == burger.id
    assert profile["top_restaurants"][0]["purchases"] == 1


def test_summarize_preferences_handles_empty_history() -> None:
    user_id = uuid4()
    profile = interaction_service.summarize_preferences(user_id, [], [])

    assert profile["total_interactions"] == 0
    assert profile["purchases"] == 0
    assert profile["average_purchase_value"] == 0.0
    assert profile["top_categories"] == []
    assert profile["top_restaurants"] == []


async def test_record_interaction_invalidates_cached_scores(monkeypatch) -> None:
    user = User(
        id=uuid4(), name="Ana", email="ana@test.dev", dietary_preferences=[]
    )
    restaurant = make_restaurant("Burger", ["Fast food"])
    created_calls: list[dict] = []
    invalidated: list[str] = []

    async def fake_get_user(*_args, **_kwargs):
        return user

    async def fake_get_restaurant(*_args, **_kwargs):
        return restaurant

    async def fake_create(*_args, **kwargs):
        created_calls.append(kwargs)
        return (
            make_interaction(
                user.id, restaurant.id, kwargs["interaction_type"]
            ),
            True,
        )

    async def fake_clear(user_id: str):
        invalidated.append(user_id)
        return 1

    monkeypatch.setattr(interaction_service.crud, "get_user", fake_get_user)
    monkeypatch.setattr(
        interaction_service.crud, "get_restaurant", fake_get_restaurant
    )
    monkeypatch.setattr(
        interaction_service.crud, "create_interaction", fake_create
    )
    monkeypatch.setattr(interaction_service, "clear_user_scores", fake_clear)

    _, created = await interaction_service.record_interaction(
        object(),
        user_id=user.id,
        restaurant_id=restaurant.id,
        interaction_type="view",
    )

    assert created is True
    assert created_calls[0]["interaction_type"] == "VIEW"
    assert invalidated == [str(user.id)]


async def test_record_interaction_rejects_unknown_type() -> None:
    with pytest.raises(interaction_service.InvalidInteractionTypeError):
        await interaction_service.record_interaction(
            object(),
            user_id=uuid4(),
            restaurant_id=uuid4(),
            interaction_type="SHARE",
        )


async def test_record_interaction_ignores_purchase_value_for_views(
    monkeypatch,
) -> None:
    user = User(
        id=uuid4(), name="Ana", email="ana@test.dev", dietary_preferences=[]
    )
    restaurant = make_restaurant("Burger", ["Fast food"])
    created_calls: list[dict] = []

    async def fake_get_user(*_args, **_kwargs):
        return user

    async def fake_get_restaurant(*_args, **_kwargs):
        return restaurant

    async def fake_create(*_args, **kwargs):
        created_calls.append(kwargs)
        return (
            make_interaction(
                user.id, restaurant.id, kwargs["interaction_type"]
            ),
            True,
        )

    async def fake_clear(_user_id: str):
        return 0

    monkeypatch.setattr(interaction_service.crud, "get_user", fake_get_user)
    monkeypatch.setattr(
        interaction_service.crud, "get_restaurant", fake_get_restaurant
    )
    monkeypatch.setattr(
        interaction_service.crud, "create_interaction", fake_create
    )
    monkeypatch.setattr(interaction_service, "clear_user_scores", fake_clear)

    await interaction_service.record_interaction(
        object(),
        user_id=user.id,
        restaurant_id=restaurant.id,
        interaction_type="VIEW",
        purchase_value=99.0,
    )

    assert created_calls[0]["purchase_value"] is None
