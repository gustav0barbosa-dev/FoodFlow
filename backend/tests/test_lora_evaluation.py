from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.core.constants import APP_TIMEZONE
from app.ml import lora_training
from app.ml.lora_evaluation import (
    NDCG_K,
    _holdout_contexts,
    _hybrid_scores,
    ndcg_at_k,
)
from app.ml.lora_training import _generate_placeholder_artifact
from app.ml.reranker import LoRAReranker
from app.models import Order, Restaurant, User


def _make_restaurant(index: int) -> Restaurant:
    return Restaurant(
        id=uuid4(),
        name=f"Restaurante {index}",
        address=f"Rua {index}",
        categories=["Brasileira"],
        average_rating=4.0,
        review_count=50 + index,
        delivery_fee=5.0,
        delivery_time_min=20,
        delivery_time_max=30,
    )


def _make_order(user_id, restaurant_id, *, hour: int, days_ago: int) -> Order:
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
        order_value=30.0,
        delivery_fee=5.0,
        created_at=local.astimezone(timezone.utc),
    )


def test_ndcg_at_k_perfect_ranking() -> None:
    labels = [1, 0, 0, 0, 0]
    scores = [0.9, 0.8, 0.7, 0.6, 0.5]

    assert ndcg_at_k(labels, scores, k=NDCG_K) == 1.0


def test_ndcg_at_k_penalizes_positive_outside_top_k() -> None:
    labels = [0, 0, 0, 0, 0, 1]
    scores = [0.9, 0.8, 0.7, 0.6, 0.5, 0.4]

    assert ndcg_at_k(labels, scores, k=NDCG_K) == 0.0


def test_ndcg_at_k_without_positives_is_zero() -> None:
    assert ndcg_at_k([0, 0, 0], [0.9, 0.5, 0.1], k=5) == 0.0


def test_hybrid_scores_blends_both_rankings() -> None:
    lightgbm = {"a": 1.0, "b": 0.0}
    lora = {"a": 0.0, "b": 1.0}

    hybrid = _hybrid_scores(lightgbm, lora)

    assert hybrid["a"] == 0.5
    assert hybrid["b"] == 0.5


def test_holdout_contexts_use_only_training_history() -> None:
    user = User(
        id=uuid4(),
        name="Usuário Teste",
        email="eval@test.dev",
        dietary_preferences=[],
    )
    restaurants = [_make_restaurant(index) for index in range(3)]
    train_orders = [
        _make_order(user.id, restaurants[0].id, hour=12, days_ago=10),
    ]
    holdout_orders = [
        _make_order(user.id, restaurants[1].id, hour=12, days_ago=1),
    ]

    contexts = _holdout_contexts(
        [user],
        holdout_orders,
        train_orders,
        restaurants,
        datetime.now(APP_TIMEZONE),
    )

    assert len(contexts) == 1
    context = contexts[0]
    assert context.positives == {str(restaurants[1].id)}
    # Nenhum pedido do holdout entra nas features do usuário.
    assert context.user_features["total_orders"] == 1


def test_placeholder_artifact_honors_custom_output_dir(tmp_path, monkeypatch) -> None:
    default_dir = tmp_path / "default"
    custom_dir = tmp_path / "custom"
    monkeypatch.setattr(lora_training, "LORA_MODEL_DIR", default_dir)

    metadata = _generate_placeholder_artifact(output_dir=custom_dir)

    assert metadata["placeholder"] is True
    assert (custom_dir / "adapter_config.json").exists()
    assert (custom_dir / "reranker_metadata.json").exists()
    assert not default_dir.exists()


def test_reranker_honors_custom_model_dir(tmp_path) -> None:
    instance = LoRAReranker(model_dir=tmp_path)

    assert instance.model_dir == tmp_path
    assert instance.load() is False
