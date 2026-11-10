import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.core.constants import APP_TIMEZONE
from app.ml import lora_training
from app.ml.lora_training import (
    _generate_placeholder_artifact,
    build_lora_training_frame,
)
from app.models import Order, Restaurant, User


def _make_restaurant(index: int) -> Restaurant:
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
        order_value=30.0 + hour,
        delivery_fee=5.0,
        created_at=local.astimezone(timezone.utc),
    )


def _fixture():
    restaurants = [_make_restaurant(index) for index in range(5)]
    user = User(
        id=uuid4(),
        name="Usuário Teste",
        email="lora@test.dev",
        dietary_preferences=[],
    )
    orders = [
        _make_order(user.id, restaurants[0].id, hour=12, days_ago=1),
        _make_order(user.id, restaurants[1].id, hour=20, days_ago=2),
    ]
    return [user], orders, restaurants


def test_build_lora_training_frame_has_positive_and_negative_samples() -> None:
    users, orders, restaurants = _fixture()

    samples = build_lora_training_frame(users, orders, restaurants)

    assert samples
    labels = {sample["label"] for sample in samples}
    assert labels == {0.0, 1.0}
    assert all(isinstance(sample["text"], str) and sample["text"] for sample in samples)
    assert any("restaurante=" in sample["text"] for sample in samples)


def test_generate_placeholder_artifact_marks_metadata(tmp_path, monkeypatch) -> None:
    target = tmp_path / "lora_reranker"
    monkeypatch.setattr(lora_training, "LORA_MODEL_DIR", target)

    metadata = _generate_placeholder_artifact()

    assert metadata["placeholder"] is True
    assert (target / "adapter_config.json").exists()
    assert (target / "adapter_model.safetensors").exists()
    assert (target / "reranker_metadata.json").exists()

    saved = json.loads((target / "reranker_metadata.json").read_text(encoding="utf-8"))
    assert saved["placeholder"] is True
