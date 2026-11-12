from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.core.constants import APP_TIMEZONE
from app.ml import recommender as recommender_module
from app.ml import train as train_module
from app.ml.features import build_user_features
from app.ml.recommender import Recommender
from app.ml.train import (
    InsufficientTrainingDataError,
    _dataset_hash,
    _fit_and_evaluate,
    _roc_auc,
    _split_frame,
    build_contexts,
    build_seed_entities,
    build_training_frame,
    feature_columns,
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
    # Cada ocasião de pedido vira um contexto de treino próprio.
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
    assert metrics["ranking"]["contexts"] > 0


def test_recommender_roundtrip_and_prediction(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(recommender_module, "MODEL_PATH", tmp_path / "model.joblib")
    users, orders, restaurants = build_fixture()
    frame = build_training_frame(users, orders, restaurants, seed=7)
    model, _ = _fit_and_evaluate(frame)
    columns = feature_columns(frame)

    recommender = Recommender()
    recommender.save(model, columns)
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
    # O relatório real do repositório não pode ser sobrescrito por um teste.
    monkeypatch.setattr(
        train_module,
        "save_training_report",
        lambda report: tmp_path / "training_metrics.json",
    )

    metrics = train_from_seed()

    assert metrics is not None
    assert metrics["samples"] > 0

    loaded = Recommender()
    assert loaded.load() is True
    assert loaded.metadata["source"] == "seed"


def test_contexts_use_only_history_before_the_context_instant() -> None:
    users, orders, restaurants = build_fixture()
    contexts = build_contexts(users, orders, restaurants)

    # Cada usuário tem dois pedidos em dias diferentes. No contexto mais
    # antigo, o histórico é vazio; no mais recente, há exatamente um pedido.
    by_user = {}
    for context in contexts:
        by_user.setdefault(context["user_id"], []).append(context)

    for user_contexts in by_user.values():
        ordered = sorted(user_contexts, key=lambda item: item["until"])
        assert ordered[0]["user_features"]["total_orders"] == 0
        assert ordered[1]["user_features"]["total_orders"] == 1


def test_temporal_split_is_chronological_and_does_not_share_contexts() -> None:
    users, orders, restaurants = build_fixture()
    frame = build_training_frame(users, orders, restaurants)
    split = _split_frame(frame)

    assert split["strategy"] == "temporal"
    train = split["stats"]["train"]
    validation = split["stats"]["validation"]
    test = split["stats"]["test"]

    assert train["period"]["end"] <= validation["period"]["start"]
    assert validation["period"]["end"] <= test["period"]["start"]

    masks = split["masks"]
    train_ids = set(frame.loc[masks["train"], "_context_id"])
    validation_ids = set(frame.loc[masks["validation"], "_context_id"])
    test_ids = set(frame.loc[masks["test"], "_context_id"])
    assert not (train_ids & validation_ids)
    assert not (train_ids & test_ids)
    assert not (validation_ids & test_ids)


def test_dataset_hash_and_metrics_are_reproducible() -> None:
    users, orders, restaurants = build_fixture()
    first = build_training_frame(users, orders, restaurants)
    second = build_training_frame(users, orders, restaurants)

    assert _dataset_hash(first) == _dataset_hash(second)
    assert list(first.columns) == list(second.columns)

    _, first_metrics = _fit_and_evaluate(
        first, orders=orders, catalog_size=len(restaurants)
    )
    _, second_metrics = _fit_and_evaluate(
        second, orders=orders, catalog_size=len(restaurants)
    )

    assert first_metrics["ranking"] == second_metrics["ranking"]
    assert first_metrics["roc_auc"] == second_metrics["roc_auc"]


def test_training_rejects_dataset_without_both_classes() -> None:
    users, orders, restaurants = build_fixture()
    frame = build_training_frame(users, orders, restaurants)
    frame["clicked"] = 1

    try:
        _fit_and_evaluate(frame, orders=orders)
    except InsufficientTrainingDataError as exc:
        assert "duas classes" in str(exc)
    else:  # pragma: no cover - o teste deve falhar se não levantar
        raise AssertionError("Treino deveria recusar dataset de uma classe")


def test_all_strategies_receive_the_same_candidates() -> None:
    users, orders, restaurants = build_fixture()
    frame = build_training_frame(users, orders, restaurants)
    _, metrics = _fit_and_evaluate(
        frame, orders=orders, catalog_size=len(restaurants)
    )

    model = metrics["ranking"]
    popularity = metrics["baselines"]["popularity"]
    random_baseline = metrics["baselines"]["random"]

    assert model["contexts_total"] == popularity["contexts_total"]
    assert model["contexts_total"] == random_baseline["contexts_total"]
    assert model["contexts"] == popularity["contexts"]
    assert model["contexts"] == random_baseline["contexts"]
    assert model["catalog_size"] == popularity["catalog_size"]
    assert model["catalog_size"] == random_baseline["catalog_size"]


def test_roc_auc_is_none_when_there_is_only_one_class() -> None:
    value, reason = _roc_auc([1] * 30, [0.5] * 30)

    assert value is None
    assert "Negativos insuficientes" in str(reason)


def test_roc_auc_is_reported_with_enough_samples_and_classes() -> None:
    labels = [0, 1] * 15
    scores = [0.1, 0.9] * 15

    value, reason = _roc_auc(labels, scores)

    assert value == 1.0
    assert reason is None


def test_small_dataset_does_not_crash_and_is_not_promoted(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(recommender_module, "MODEL_PATH", tmp_path / "model.joblib")
    reports = []
    monkeypatch.setattr(
        train_module, "save_training_report", lambda report: reports.append(report)
    )

    restaurants = [make_restaurant(index) for index in range(3)]
    user = User(
        id=uuid4(),
        name="Único",
        email="unico@test.dev",
        dietary_preferences=[],
    )
    order = make_order(user.id, restaurants[0].id, hour=12, days_ago=1)

    result = train_module._train_and_save(
        source="test",
        users=[user],
        orders=[order],
        restaurants=restaurants,
    )

    assert result is not None
    assert result["split"]["strategy"] == "insufficient_temporal"
    assert result["promotion"]["promoted"] is False
    assert reports and reports[-1]["quality"]["ok"] is False


def test_train_from_seed_writes_reproducible_report(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(recommender_module, "MODEL_PATH", tmp_path / "model.joblib")
    reports = []
    monkeypatch.setattr(
        train_module, "save_training_report", lambda report: reports.append(report)
    )

    result = train_from_seed()

    assert result is not None
    report = reports[-1]
    assert report["schema_version"] == 2
    assert report["dataset"]["hash"] == result["dataset_hash"]
    assert report["dataset"]["contexts"] == 30
    assert report["dataset"]["positives"] == 30
    assert report["dataset"]["negatives"] > 0
    assert report["split"]["strategy"] == "temporal"
    assert report["quality"]["checks"]["temporal_split"] is True
    assert report["quality"]["limitations"]
    assert report["promotion"]["decision"] in {
        "bootstrap",
        "promoted",
        "kept_previous",
        "rejected_quality",
        "insufficient_evidence",
    }
