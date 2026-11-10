import hashlib
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from app import crud
from app import main as main_module
from app.api import metrics as metrics_api
from app.api import recommendations as recommendations_api
from app.database import get_db
from app.main import app
from app.models import Restaurant, Review, User


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


def test_user_profile_returns_data(monkeypatch) -> None:
    _use_fake_db()
    user = User(
        id=uuid4(),
        name="Ana Souza",
        email="ana@test.dev",
        dietary_preferences=["Vegetariano"],
        created_at=datetime.now(timezone.utc),
    )

    async def fake_get_user(*_args, **_kwargs):
        return user

    monkeypatch.setattr(crud, "get_user", fake_get_user)

    with TestClient(app) as client:
        response = client.get(f"/api/v1/users/{user.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(user.id)
    assert body["name"] == "Ana Souza"
    assert body["dietary_preferences"] == ["Vegetariano"]


def test_user_profile_not_found_returns_404(monkeypatch) -> None:
    _use_fake_db()

    async def fake_get_user(*_args, **_kwargs):
        return None

    monkeypatch.setattr(crud, "get_user", fake_get_user)

    with TestClient(app) as client:
        response = client.get(f"/api/v1/users/{uuid4()}")

    assert response.status_code == 404


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


def _review_fixture() -> tuple[Review, User]:
    user = User(
        id=uuid4(),
        name="Ana Souza",
        email=f"{uuid4()}@test.dev",
        dietary_preferences=[],
    )
    review = Review(
        id=uuid4(),
        restaurant_id=uuid4(),
        user_id=user.id,
        rating=3,
        comment="Regular",
        created_at=datetime.now(timezone.utc),
    )
    return review, user


def test_update_review_returns_updated_payload(monkeypatch) -> None:
    _use_fake_db()
    review, user = _review_fixture()

    async def fake_get_review(*_args, **_kwargs):
        return review

    async def fake_get_user(*_args, **_kwargs):
        return user

    async def fake_update_review(session, review, rating, comment):
        review.rating = rating
        review.comment = comment
        return review

    monkeypatch.setattr(crud, "get_review", fake_get_review)
    monkeypatch.setattr(crud, "get_user", fake_get_user)
    monkeypatch.setattr(crud, "update_review", fake_update_review)

    with TestClient(app) as client:
        response = client.put(
            f"/api/v1/reviews/{review.id}",
            json={
                "user_id": str(user.id),
                "rating": 5,
                "comment": "Agora ficou excelente",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["rating"] == 5
    assert body["comment"] == "Agora ficou excelente"
    assert body["user_name"] == "Ana Souza"


def test_update_review_from_other_user_returns_403(monkeypatch) -> None:
    _use_fake_db()
    review, _user = _review_fixture()

    async def fake_get_review(*_args, **_kwargs):
        return review

    monkeypatch.setattr(crud, "get_review", fake_get_review)

    with TestClient(app) as client:
        response = client.put(
            f"/api/v1/reviews/{review.id}",
            json={
                "user_id": str(uuid4()),
                "rating": 5,
                "comment": "Tentativa indevida",
            },
        )

    assert response.status_code == 403


def test_delete_review_removes_own_review(monkeypatch) -> None:
    _use_fake_db()
    review, user = _review_fixture()
    deleted: list[str] = []

    async def fake_get_review(*_args, **_kwargs):
        return review

    async def fake_delete_review(_session, current):
        deleted.append(str(current.id))

    monkeypatch.setattr(crud, "get_review", fake_get_review)
    monkeypatch.setattr(crud, "delete_review", fake_delete_review)

    with TestClient(app) as client:
        response = client.delete(
            f"/api/v1/reviews/{review.id}",
            params={"user_id": str(user.id)},
        )

    assert response.status_code == 204
    assert deleted == [str(review.id)]


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


def test_recommendations_without_turno_history_uses_popularity(monkeypatch) -> None:
    _use_fake_db()
    restaurant = Restaurant(
        id=uuid4(),
        name="Sabor da Vila",
        address="Rua Teste, 1",
        categories=["Brasileira"],
        average_rating=4.8,
        review_count=120,
        delivery_fee=5.0,
        delivery_time_min=20,
        delivery_time_max=30,
    )
    user = User(
        id=uuid4(),
        name="Ana Souza",
        email="ana@test.dev",
        dietary_preferences=[],
    )
    writes: list[str] = []

    async def fake_search(*_args, **_kwargs):
        return [restaurant]

    async def fake_get_user(*_args, **_kwargs):
        return user

    async def fake_get_orders(*_args, **_kwargs):
        return []

    async def fake_get_scores(*_args, **_kwargs):
        return None

    async def fake_set_scores(user_id, turno, scores):
        writes.append(turno)
        return True

    monkeypatch.setattr(crud, "search_restaurants", fake_search)
    monkeypatch.setattr(crud, "get_user", fake_get_user)
    monkeypatch.setattr(crud, "get_user_orders", fake_get_orders)
    monkeypatch.setattr(recommendations_api, "get_scores", fake_get_scores)
    monkeypatch.setattr(recommendations_api, "set_scores", fake_set_scores)

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/recommendations",
            params={
                "user_id": str(user.id),
                "lat": -23.5325,
                "lon": -46.7939,
                "turno": "noite",
            },
        )

    assert response.status_code == 200
    assert writes == ["noite"]
    assert response.json()[0]["score"] == 1.0


def test_experiment_assignment_is_stable_across_processes() -> None:
    user_id = UUID("12345678-1234-5678-1234-567812345678")
    expected_digest = int.from_bytes(
        hashlib.sha256(str(user_id).encode("utf-8")).digest()[:8], "big"
    )
    expected = (
        recommendations_api.EXPERIMENT_PERSONALIZED
        if expected_digest % 2 == 0
        else recommendations_api.EXPERIMENT_DISTANCE
    )

    assert recommendations_api._assign_experiment_group(user_id) == expected
    # Repetir a chamada não pode mudar o grupo.
    assert recommendations_api._assign_experiment_group(user_id) == expected


def test_train_lora_endpoint_is_offline_only() -> None:
    with TestClient(app) as client:
        response = client.post("/api/v1/recommendations/train-lora")

    assert response.status_code == 202
    assert response.json()["status"] == "accepted"
    assert "scripts/train_lora.py" in response.json()["detail"]


def test_request_id_and_process_time_headers() -> None:
    with TestClient(app) as client:
        response = client.get(
            "/health",
            headers={"X-Request-ID": "abc-123"},
        )

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "abc-123"
    assert response.headers["X-Process-Time"].endswith("ms")


class _ReadySession:
    async def execute(self, _statement):
        return None


class _BrokenSession:
    async def execute(self, _statement):
        raise SQLAlchemyError("database down")


def test_ready_reports_dependencies(monkeypatch) -> None:
    async def fake_ready_db():
        yield _ReadySession()

    async def fake_ping() -> bool:
        return True

    app.dependency_overrides[get_db] = fake_ready_db
    monkeypatch.setattr(main_module, "ping_redis", fake_ping)

    with TestClient(app) as client:
        response = client.get("/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["database"] is True
    assert body["redis"] is True


def test_ready_returns_503_when_database_is_down(monkeypatch) -> None:
    async def fake_broken_db():
        yield _BrokenSession()

    async def fake_ping() -> bool:
        return False

    app.dependency_overrides[get_db] = fake_broken_db
    monkeypatch.setattr(main_module, "ping_redis", fake_ping)

    with TestClient(app) as client:
        response = client.get("/ready")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert body["database"] is False
    assert body["redis"] is False


def test_recommendation_metrics_endpoint(monkeypatch) -> None:
    async def fake_metrics():
        return {
            "redis_available": True,
            "cache_hit_rate": 0.5,
            "requests": 2,
            "cache_hits": 1,
            "cache_misses": 1,
            "model_scores": 1,
            "popularity_scores": 0,
        }

    monkeypatch.setattr(metrics_api, "get_recommendation_metrics", fake_metrics)

    with TestClient(app) as client:
        response = client.get("/api/v1/metrics/recommendations")

    assert response.status_code == 200
    assert response.json()["cache_hit_rate"] == 0.5
    assert response.json()["redis_available"] is True


def test_ab_test_endpoint(monkeypatch) -> None:
    from app.api import experiment as experiment_api

    async def fake_ab_metrics():
        return {
            "redis_available": True,
            "total_requests": 100,
            "personalized_requests": 52,
            "distance_requests": 48,
            "personalized_share": 0.52,
            "distance_share": 0.48,
        }

    monkeypatch.setattr(
        experiment_api, "get_ab_test_metrics", fake_ab_metrics
    )

    with TestClient(app) as client:
        response = client.get("/api/v1/experiment/ab-test")

    assert response.status_code == 200
    body = response.json()
    assert body["redis_available"] is True
    assert body["total_requests"] == 100
    assert body["personalized_requests"] == 52
    assert body["distance_requests"] == 48
    assert body["personalized_share"] == 0.52
    assert body["distance_share"] == 0.48


def test_drift_endpoint(monkeypatch) -> None:
    async def fake_report():
        return {
            "redis_available": True,
            "overall_status": "ok",
            "psi_threshold_warning": 0.1,
            "psi_threshold_alert": 0.2,
            "features_monitored": 2,
            "features_with_alert": 0,
            "features_with_warning": 0,
            "alert_features": [],
            "warning_features": [],
            "features": [
                {
                    "feature": "restaurant_rating",
                    "psi": 0.02,
                    "status": "ok",
                    "baseline_n": 100,
                    "current_n": 100,
                }
            ],
        }

    from app.api import drift as drift_api

    monkeypatch.setattr(drift_api.drift_monitor, "compute_drift_report", fake_report)

    with TestClient(app) as client:
        response = client.get("/api/v1/drift")

    assert response.status_code == 200
    body = response.json()
    assert body["overall_status"] == "ok"
    assert body["features_monitored"] == 2
    assert body["features"][0]["feature"] == "restaurant_rating"
