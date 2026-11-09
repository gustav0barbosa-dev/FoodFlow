from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app import crud
from app.database import get_db
from app.main import app
from app.models import Restaurant, Review


@pytest.fixture(autouse=True)
def reset_dependency_overrides():
    yield
    app.dependency_overrides.clear()


async def _fake_db():
    yield object()


def _use_fake_db() -> None:
    app.dependency_overrides[get_db] = _fake_db


def test_health() -> None:
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "model_loaded" in body


def test_restaurant_invalid_uuid_returns_422() -> None:
    _use_fake_db()
    with TestClient(app) as client:
        response = client.get("/api/v1/restaurants/not-a-uuid")

    assert response.status_code == 422


def test_restaurant_not_found_returns_404(monkeypatch) -> None:
    _use_fake_db()

    async def fake_get_restaurant(*_args, **_kwargs):
        return None

    monkeypatch.setattr(crud, "get_restaurant", fake_get_restaurant)

    with TestClient(app) as client:
        response = client.get(f"/api/v1/restaurants/{uuid4()}")

    assert response.status_code == 404


def test_restaurant_detail_includes_reviews(monkeypatch) -> None:
    _use_fake_db()
    restaurant = Restaurant(
        id=uuid4(),
        name="Sabor da Vila",
        address="Rua Teste, 1",
        categories=["Brasileira"],
        average_rating=4.8,
        review_count=10,
        delivery_fee=5.0,
        delivery_time_min=20,
        delivery_time_max=30,
    )
    review = Review(
        id=uuid4(),
        restaurant_id=restaurant.id,
        user_id=uuid4(),
        rating=5,
        comment="Muito bom",
        created_at=datetime.now(timezone.utc),
    )

    async def fake_get_restaurant(*_args, **_kwargs):
        return restaurant

    async def fake_get_reviews(*_args, **_kwargs):
        return [(review, "Ana Souza")]

    monkeypatch.setattr(crud, "get_restaurant", fake_get_restaurant)
    monkeypatch.setattr(crud, "get_restaurant_reviews", fake_get_reviews)

    with TestClient(app) as client:
        response = client.get(f"/api/v1/restaurants/{restaurant.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Sabor da Vila"
    assert body["reviews"][0]["user_name"] == "Ana Souza"
    assert body["reviews"][0]["rating"] == 5


def test_review_invalid_rating_returns_422() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/reviews",
            json={
                "restaurant_id": str(uuid4()),
                "user_id": str(uuid4()),
                "rating": 6,
            },
        )

    assert response.status_code == 422


def test_event_unknown_type_returns_422() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/events",
            json={"type": "unknown_event", "payload": {}},
        )

    assert response.status_code == 422


def test_search_requires_coordinates() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/restaurants/search")

    assert response.status_code == 422
