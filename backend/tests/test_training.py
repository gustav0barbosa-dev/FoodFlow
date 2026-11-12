from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pandas as pd
import pytest

from app.core.constants import APP_TIMEZONE
from app.ml import recommender as recommender_module
from app.ml import train as train_module
from app.ml.features import (
    CURRENT_STATE_RESTAURANT_FEATURES,
    build_user_features,
)
from app.ml.recommender import Recommender
from app.ml.train import (
    InsufficientTrainingDataError,
    UNOBSERVED_NEGATIVE_WEIGHT,
    _calibration_curve,
    _dataset_hash,
    _fit_and_evaluate,
    _predictive_metrics,
    _promotion_decision,
    _ranking_sensitivity,
    _roc_auc,
    _split_frame,
    build_contexts,
    build_seed_entities,
    build_training_frame,
    compute_ranking_metrics,
    feature_columns,
    rolling_window_evaluation,
    train_from_seed,
)
from app.models import Order, Restaurant, User, UserRestaurantInteraction


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
    assert set(frame["purchased"].unique()) == {0, 1}
    assert int(frame["purchased"].sum()) == 6
    assert len(frame) > int(frame["purchased"].sum())
    assert "restaurant_rating" in frame.columns
    assert "tarde_avg_value" in frame.columns
    # Cada ocasião de pedido vira um contexto de treino próprio.
    assert int(frame[frame["purchased"] == 1]["is_tarde"].sum()) == 3
    assert int(frame[frame["purchased"] == 1]["is_noite"].sum()) == 3
    assert int(frame[frame["purchased"] == 1]["is_manha"].sum()) == 0


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
    frame["purchased"] = 1

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
    assert report["schema_version"] == 3
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


def make_interaction(user_id, restaurant_id, *, days_ago: int, hour: int = 9):
    local = (datetime.now(APP_TIMEZONE) - timedelta(days=days_ago)).replace(
        hour=hour, minute=0, second=0, microsecond=0
    )
    return UserRestaurantInteraction(
        user_id=user_id,
        restaurant_id=restaurant_id,
        interaction_type="IMPRESSION",
        created_at=local.astimezone(timezone.utc),
    )


def test_unobserved_negatives_receive_lower_weight() -> None:
    users, orders, restaurants = build_fixture()
    frame = build_training_frame(users, orders, restaurants)

    negatives = frame[frame["purchased"] == 0]
    assert not negatives.empty
    assert (negatives["_observed"] == False).all()  # noqa: E712
    assert (negatives["_sample_weight"] == UNOBSERVED_NEGATIVE_WEIGHT).all()
    positives = frame[frame["purchased"] == 1]
    assert (positives["_sample_weight"] == 1.0).all()


def test_observed_negatives_receive_full_weight() -> None:
    users, orders, restaurants = build_fixture()
    user = users[0]
    # Interação bem antes do primeiro pedido do usuário.
    interactions = [
        make_interaction(user.id, restaurants[5].id, days_ago=20),
    ]

    frame = build_training_frame(
        users, orders, restaurants, interactions=interactions
    )
    observed = frame[
        (frame["_user_id"] == str(user.id)) & (frame["_observed"])
    ]

    assert not observed.empty
    assert (observed["_sample_weight"] == 1.0).all()


def test_predictive_metrics_include_calibration() -> None:
    labels = [0, 1] * 15
    scores = [0.1, 0.9] * 15

    metrics = _predictive_metrics(labels, scores)

    assert metrics["roc_auc"] == 1.0
    assert metrics["pr_auc"] == 1.0
    assert metrics["brier_score"] == pytest.approx(0.01, abs=1e-6)
    assert metrics["log_loss"] is not None and metrics["log_loss"] < 0.2


def test_predictive_metrics_keep_calibration_without_two_classes() -> None:
    metrics = _predictive_metrics([1] * 30, [0.5] * 30)

    # ROC/PR AUC exigem as duas classes; Brier, Log Loss e calibração não.
    assert metrics["roc_auc"] is None
    assert metrics["pr_auc"] is None
    assert metrics["brier_score"] == pytest.approx(0.25, abs=1e-6)
    assert metrics["log_loss"] == pytest.approx(0.6931, abs=1e-3)
    assert metrics["calibration"] is not None
    assert metrics["calibration"]["samples"] == 30


def test_calibration_curve_reports_ece_and_bins() -> None:
    labels = [0, 1] * 15
    scores = [0.1, 0.9] * 15

    calibration = _calibration_curve(labels, scores)

    assert calibration is not None
    assert calibration["samples"] == 30
    # Previsões bem separadas -> erro pequeno em cada bin.
    assert calibration["expected_calibration_error"] <= 0.1
    assert len(calibration["bins"]) >= 2
    for entry in calibration["bins"]:
        assert 0.0 <= entry["observed_rate"] <= 1.0


def test_ranking_sensitivity_separates_observed_and_unobserved() -> None:
    frame = pd.DataFrame(
        {
            "_context_id": ["c1"] * 4,
            "_user_id": ["u1"] * 4,
            "_restaurant_id": ["r1", "r2", "r3", "r4"],
            "purchased": [1, 0, 0, 0],
            "_observed": [True, True, False, False],
        }
    )
    scores = [0.9, 0.5, 0.4, 0.1]

    sensitivity = _ranking_sensitivity(
        frame,
        scores,
        orders=None,
        catalog_size=4,
        item_attributes=None,
    )

    assert sensitivity["primary"] == "all_candidates"
    observed = sensitivity["pools"]["negativos_observados"]
    unobserved = sensitivity["pools"]["negativos_nao_observados"]
    assert observed["available"] is True
    assert observed["positives"] == 1
    assert observed["negatives"] == 1
    assert unobserved["available"] is True
    assert unobserved["negatives"] == 2
    assert "model" in observed["metrics"]


def test_ranking_sensitivity_marks_pool_unavailable_without_negatives() -> None:
    frame = pd.DataFrame(
        {
            "_context_id": ["c1"] * 2,
            "_user_id": ["u1"] * 2,
            "_restaurant_id": ["r1", "r2"],
            "purchased": [1, 0],
            "_observed": [True, False],
        }
    )

    sensitivity = _ranking_sensitivity(
        frame,
        [0.9, 0.1],
        orders=None,
        catalog_size=2,
        item_attributes=None,
    )

    observed = sensitivity["pools"]["negativos_observados"]
    assert observed["available"] is False
    assert "trivial" in observed["reason"].lower()


def test_rolling_window_evaluation_reports_unavailable_with_few_contexts() -> None:
    users, orders, restaurants = build_fixture()
    frame = build_training_frame(users, orders, restaurants, seed=7)

    result = rolling_window_evaluation(frame, orders=orders, restaurants=restaurants)

    # O fixture tem poucos contextos; a análise deve recusar sem inventar folds.
    assert result["available"] is False
    assert "insuficientes" in result["reason"].lower() or "nenhum" in result[
        "reason"
    ].lower()


def test_strict_temporal_excludes_current_state_features() -> None:
    users, orders, restaurants = build_fixture()
    frame = build_training_frame(users, orders, restaurants, seed=7)

    _, metrics = _fit_and_evaluate(frame, strict_temporal=True)

    assert metrics["temporal_mode"] == "strict"
    for feature in CURRENT_STATE_RESTAURANT_FEATURES:
        assert feature not in metrics["feature_names"]


def test_ranking_bootstrap_interval_is_reproducible_by_user() -> None:
    items_a = [("a", 1.0, 1), ("b", 0.9, 0), ("c", 0.8, 0)]
    items_b = [("d", 1.0, 1), ("e", 0.9, 0), ("f", 0.8, 0)]
    contexts = [
        {"context_id": "1", "user_id": "u1", "items": items_a},
        {"context_id": "2", "user_id": "u2", "items": items_b},
    ]

    first = compute_ranking_metrics(contexts, k=2, bootstrap_resamples=200)
    second = compute_ranking_metrics(contexts, k=2, bootstrap_resamples=200)

    assert first["confidence_intervals"] == second["confidence_intervals"]
    interval = first["confidence_intervals"]["ndcg_at_k"]
    assert interval is not None
    assert interval["unit"] == "user"
    assert interval["low"] <= interval["high"]


def test_ild_and_novelty_are_computed_from_attributes_and_popularity() -> None:
    contexts = [
        {
            "context_id": "1",
            "user_id": "u1",
            "items": [("a", 1.0, 1), ("b", 0.9, 0)],
            "popularity": {"a": 10, "b": 1},
            "popularity_total": 20,
        }
    ]
    attributes = {"a": {"italiana"}, "b": {"japonesa"}}

    metrics = compute_ranking_metrics(
        contexts, k=2, item_attributes=attributes
    )

    # Duas categorias diferentes: Jaccard 0 => distância 1.
    assert metrics["ild_at_k"] == 1.0
    assert metrics["novelty_at_k"] is not None
    assert metrics["novelty_at_k"] > 0


def test_promotion_requires_beating_the_production_model() -> None:
    def metrics_for(ndcg: float, production: dict) -> dict:
        ranking = {"ndcg_at_k": ndcg, "map_at_k": ndcg, "precision_at_k": ndcg}
        return {
            "ranking": ranking,
            "baselines": {
                "popularity": {"ndcg_at_k": 0.4, "map_at_k": 0.4},
                "random": {"ndcg_at_k": 0.1, "map_at_k": 0.1},
            },
            "production": production,
        }

    quality = {
        "ok": True,
        "promotion_ready": True,
        "checks": {},
        "promotion_checks": {},
    }
    previous = {"version": "prod-1", "path": "unused"}
    better_production = {
        "available": True,
        "ranking": {"ndcg_at_k": 0.6, "map_at_k": 0.6},
    }
    worse_production = {
        "available": True,
        "ranking": {"ndcg_at_k": 0.3, "map_at_k": 0.3},
    }

    kept = _promotion_decision(
        metrics_for(0.5, better_production), quality, previous
    )
    promoted = _promotion_decision(
        metrics_for(0.5, worse_production), quality, previous
    )
    unavailable = _promotion_decision(
        metrics_for(0.5, {"available": False, "reason": "sem features"}),
        quality,
        previous,
    )

    assert kept["decision"] == "kept_previous"
    assert promoted["decision"] == "promoted"
    assert unavailable["decision"] == "insufficient_evidence"


def test_seed_training_never_replaces_existing_production_model(
    tmp_path, monkeypatch
) -> None:
    model_path = tmp_path / "model.joblib"
    monkeypatch.setattr(recommender_module, "MODEL_PATH", model_path)
    monkeypatch.setattr(train_module, "save_training_report", lambda report: None)
    sentinel = b"production-sentinel"
    model_path.write_bytes(sentinel)

    result = train_from_seed()

    assert result is not None
    assert result["promotion"]["promoted"] is False
    assert result["promotion"]["decision"] == "kept_previous"
    assert "seed" in result["promotion"]["reason"].lower()
    assert model_path.read_bytes() == sentinel
