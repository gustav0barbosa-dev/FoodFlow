"""Treino e avaliação offline do recomendador LightGBM.

O pipeline é deliberadamente explícito:

- **contexto** = usuário + instante (``until``) + candidatos. Cada ocasião de
  pedido (mesmo dia local + turno) vira um contexto;
- as features de um contexto usam apenas pedidos/interações **anteriores** a
  ``until`` (nenhum dado futuro entra no treino ou na avaliação);
- o split é temporal por contexto: treino -> validação -> teste;
- as métricas de ranking são calculadas **por contexto** e agregadas por
  macro-média, incluindo contextos sem item relevante (valor 0);
- LightGBM, popularidade e aleatório recebem exatamente os mesmos candidatos;
- o relatório registra hash do dataset, períodos, contagens, baselines,
  limitações e a decisão de promoção/rollback.

Nenhuma etapa pesada é executada dentro de endpoints HTTP.
"""

import asyncio
import hashlib
import json
import logging
import math
import random
import shutil
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

import joblib
import pandas as pd
from lightgbm import LGBMClassifier, early_stopping
from sklearn.metrics import roc_auc_score
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import APP_TIMEZONE, TURNOS, Turno
from app.database import AsyncSessionLocal
from app.ml.features import (
    _as_utc,
    build_candidate_features,
    build_user_features,
    order_turno,
)
from app.ml import recommender as recommender_module
from app.ml.metrics_store import save_training_report
from app.ml.recommender import recommender
from app.models import Order, Restaurant, User, UserRestaurantInteraction
from app.seed_data import SEED_NAMESPACE, SEED_ORDERS, SEED_RESTAURANTS, SEED_USERS

logger = logging.getLogger(__name__)

RANDOM_SEED = 42
RANKING_K = 5
MODEL_VERSION_PREFIX = "lgbm"
# A AUC só é reportada quando há amostras e as duas classes no conjunto.
MIN_ROC_AUC_SAMPLES = 20
MIN_ROC_AUC_POSITIVES = 5
MIN_ROC_AUC_NEGATIVES = 5
# Evidência mínima para promover um candidato sobre o modelo em produção.
MIN_PROMOTION_TEST_CONTEXTS = 2

MODEL_PARAMS: dict[str, Any] = {
    "n_estimators": 200,
    "max_depth": 5,
    "num_leaves": 15,
    "learning_rate": 0.05,
    "min_child_samples": 5,
    "subsample": 0.9,
    "colsample_bytree": 0.9,
    "is_unbalance": True,
    "random_state": RANDOM_SEED,
    "verbose": -1,
}

# Colunas de contexto usadas para agrupar/splitar, nunca como features.
METADATA_COLUMNS: set[str] = {
    "clicked",
    "_user_id",
    "_restaurant_id",
    "_turno",
    "_context_id",
    "_event_time",
}


class InsufficientTrainingDataError(RuntimeError):
    """Dataset vazio ou sem diversidade de classes para treinar."""


def feature_columns(frame: pd.DataFrame) -> list[str]:
    return [column for column in frame.columns if column not in METADATA_COLUMNS]


def _period(frame: pd.DataFrame) -> dict[str, str | None]:
    if frame.empty:
        return {"start": None, "end": None}
    times = [_as_utc(value) for value in frame["_event_time"]]
    return {"start": min(times).isoformat(), "end": max(times).isoformat()}


def _dataset_hash(frame: pd.DataFrame) -> str:
    """Hash canônico do dataset (contexto, candidato, rótulo e instante)."""
    rows = sorted(
        (
            str(context_id),
            str(restaurant_id),
            int(clicked),
            _as_utc(event_time).isoformat(),
        )
        for context_id, restaurant_id, clicked, event_time in zip(
            frame["_context_id"],
            frame["_restaurant_id"],
            frame["clicked"],
            frame["_event_time"],
            strict=True,
        )
    )
    payload = "\n".join("|".join(str(part) for part in row) for row in rows)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_contexts(
    users: list[User],
    orders: list[Order],
    restaurants: list[Restaurant],
    interactions: list[UserRestaurantInteraction] | None = None,
) -> list[dict[str, Any]]:
    """Reconstrói contextos reais de recomendação sem usar dados futuros.

    Uma ocasião de pedido é identificada por (usuário, data local, turno). O
    instante ``until`` é o primeiro pedido da ocasião: tudo que aconteceu
    depois (inclusive o próprio pedido avaliado) fica fora das features.
    """
    if not users or not orders or not restaurants:
        return []

    restaurant_by_id = {restaurant.id: restaurant for restaurant in restaurants}
    users_by_id = {user.id: user for user in users}
    interactions = interactions or []

    orders_by_user: dict[Any, list[Order]] = defaultdict(list)
    for order in orders:
        if order.restaurant_id in restaurant_by_id:
            orders_by_user[order.user_id].append(order)

    interactions_by_user: dict[Any, list[UserRestaurantInteraction]] = defaultdict(list)
    for interaction in interactions:
        interactions_by_user[interaction.user_id].append(interaction)

    contexts: list[dict[str, Any]] = []
    for user_id, user_orders in orders_by_user.items():
        user = users_by_id.get(user_id)
        if user is None:
            continue

        occasions: dict[tuple[Any, Turno], list[Order]] = defaultdict(list)
        for order in user_orders:
            local = _as_utc(order.created_at).astimezone(APP_TIMEZONE)
            occasions[(local.date(), order_turno(order))].append(order)

        for (local_date, turno), occasion_orders in occasions.items():
            relevant = {str(order.restaurant_id) for order in occasion_orders}
            if not relevant:
                continue

            until = min(_as_utc(order.created_at) for order in occasion_orders)
            history_orders = [
                order
                for order in user_orders
                if _as_utc(order.created_at) < until
            ]
            history_interactions = [
                interaction
                for interaction in interactions_by_user.get(user_id, [])
                if _as_utc(interaction.created_at) < until
            ]

            user_features = build_user_features(
                history_orders,
                user,
                now=until,
                interactions=history_interactions,
                restaurants=restaurant_by_id,
            )
            context_id = f"{user_id}:{local_date.isoformat()}:{turno}"
            contexts.append(
                {
                    "context_id": context_id,
                    "user_id": str(user_id),
                    "until": until,
                    "turno": turno,
                    "relevant": relevant,
                    "user_features": user_features,
                    # Todos os candidatos do catálogo, iguais para as três
                    # estratégias. A ausência de pedido é tratada como
                    # "não relevante" (negativo implícito).
                    "candidates": list(restaurants),
                }
            )

    contexts.sort(key=lambda context: (context["until"], context["context_id"]))
    return contexts


def build_training_frame(
    users: list[User],
    orders: list[Order],
    restaurants: list[Restaurant],
    negatives_per_positive: int = 0,
    seed: int = RANDOM_SEED,
    interactions: list[UserRestaurantInteraction] | None = None,
) -> pd.DataFrame:
    """Gera uma linha por (contexto, candidato) com o rótulo observado.

    ``negatives_per_positive`` e ``seed`` são mantidos por compatibilidade de
    assinatura; a avaliação usa o catálogo inteiro como candidatos para que
    todas as estratégias recebam exatamente o mesmo conjunto.
    """
    del negatives_per_positive, seed
    contexts = build_contexts(users, orders, restaurants, interactions=interactions)
    rows: list[dict[str, Any]] = []
    for context in contexts:
        for restaurant in context["candidates"]:
            row = build_candidate_features(
                context["user_features"], restaurant, context["turno"]
            )
            row.update(
                {
                    "clicked": 1
                    if str(restaurant.id) in context["relevant"]
                    else 0,
                    "_user_id": context["user_id"],
                    "_restaurant_id": str(restaurant.id),
                    "_turno": context["turno"],
                    "_context_id": context["context_id"],
                    "_event_time": context["until"],
                }
            )
            rows.append(row)
    return pd.DataFrame(rows)


def _split_stats(frame: pd.DataFrame, mask: pd.Series) -> dict[str, Any]:
    subset = frame.loc[mask]
    positives = int(subset["clicked"].sum()) if len(subset) else 0
    return {
        "samples": int(len(subset)),
        "contexts": int(subset["_context_id"].nunique()) if len(subset) else 0,
        "users": int(subset["_user_id"].nunique()) if len(subset) else 0,
        "positives": positives,
        "negatives": int(len(subset) - positives),
        "period": _period(subset),
    }


def _split_frame(frame: pd.DataFrame) -> dict[str, Any]:
    """Divide contextos em treino/validação/teste respeitando a cronologia."""
    if frame.empty:
        empty = pd.Series(False, index=frame.index)
        return {
            "strategy": "empty",
            "masks": {"train": empty, "validation": empty, "test": empty},
            "stats": {
                name: {
                    "samples": 0,
                    "contexts": 0,
                    "users": 0,
                    "positives": 0,
                    "negatives": 0,
                    "period": {"start": None, "end": None},
                }
                for name in ("train", "validation", "test")
            },
            "boundaries": {
                "train_end": None,
                "validation_end": None,
                "test_end": None,
            },
        }

    context_times = (
        frame.groupby("_context_id")["_event_time"].max().sort_values()
    )
    context_ids = list(context_times.index)
    n_contexts = len(context_ids)

    if n_contexts >= 3:
        train_end = max(1, round(n_contexts * 0.6))
        validation_end = max(train_end + 1, round(n_contexts * 0.8))
        validation_end = min(validation_end, n_contexts - 1)
        train_ids = set(context_ids[:train_end])
        validation_ids = set(context_ids[train_end:validation_end])
        test_ids = set(context_ids[validation_end:])
        strategy = "temporal"
    elif n_contexts == 2:
        # Não há contextos suficientes para três períodos: o primeiro treina,
        # o último testa e a validação fica vazia. O relatório registra isso.
        train_ids = {context_ids[0]}
        validation_ids: set[str] = set()
        test_ids = {context_ids[1]}
        strategy = "insufficient_temporal"
    else:
        train_ids = set(context_ids)
        validation_ids = set()
        test_ids = set()
        strategy = "insufficient_temporal"

    masks = {
        "train": frame["_context_id"].isin(train_ids),
        "validation": frame["_context_id"].isin(validation_ids),
        "test": frame["_context_id"].isin(test_ids),
    }
    stats = {name: _split_stats(frame, mask) for name, mask in masks.items()}
    boundaries = {
        "train_end": stats["train"]["period"]["end"],
        "validation_end": stats["validation"]["period"]["end"],
        "test_end": stats["test"]["period"]["end"],
    }
    return {"strategy": strategy, "masks": masks, "stats": stats, "boundaries": boundaries}


def compute_ranking_metrics(
    contexts: Sequence[dict[str, Any]],
    k: int = RANKING_K,
    *,
    catalog_size: int | None = None,
    user_count: int | None = None,
) -> dict[str, Any]:
    """Métricas de ranking por contexto, agregadas por macro-média.

    Cada contexto é ``{"context_id", "user_id", "items": [(id, score, rel)]}``.
    Regras explícitas:

    - contextos sem candidatos são contados e excluídos das médias (não há
      ranking para avaliar);
    - contextos com candidatos e nenhum item relevante entram nas médias com
      valor 0 (não são silenciosamente ignorados);
    - Precision@K usa ``min(K, n_candidatos)`` no denominador, porque não é
      possível recuperar K itens quando o contexto tem menos de K candidatos;
    - empates de score são desempatados pelo id do restaurante, de forma
      determinística;
    - ``catalog_coverage`` e ``user_coverage`` são reportadas separadamente.
    """
    precision_values: list[float] = []
    recall_values: list[float] = []
    ndcg_values: list[float] = []
    map_values: list[float] = []
    recommended: set[str] = set()
    users_with_recommendations: set[str] = set()
    candidate_ids: set[str] = set()
    contexts_without_candidates = 0
    contexts_without_relevance = 0
    total_relevant = 0

    for context in contexts:
        items = list(context.get("items") or [])
        if not items:
            contexts_without_candidates += 1
            continue

        ordered = sorted(
            items, key=lambda item: (-float(item[1]), str(item[0]))
        )
        n_candidates = len(ordered)
        top = ordered[:k]
        gains = [float(item[2]) for item in ordered]
        # Para Precision/Recall/MAP, "relevante" significa ganho > 0. O NDCG
        # usa o ganho graduado diretamente.
        relevant = sum(1 for gain in gains if gain > 0)
        hits = sum(1 for _, _, gain in top if float(gain) > 0)
        total_relevant += relevant

        precision_values.append(hits / min(k, n_candidates))
        recall_values.append(hits / relevant if relevant else 0.0)

        dcg = sum(
            float(gain) / math.log2(rank + 2)
            for rank, (_, _, gain) in enumerate(top)
            if float(gain) > 0
        )
        ideal_gains = sorted(gains, reverse=True)[:k]
        idcg = sum(
            gain / math.log2(rank + 2)
            for rank, gain in enumerate(ideal_gains)
            if gain > 0
        )
        ndcg_values.append(dcg / idcg if idcg else 0.0)

        average_precision = 0.0
        hit_count = 0
        for rank, (_, _, gain) in enumerate(top, start=1):
            if float(gain) > 0:
                hit_count += 1
                average_precision += hit_count / rank
        map_values.append(
            average_precision / min(relevant, k) if relevant else 0.0
        )

        recommended.update(str(item[0]) for item in top)
        candidate_ids.update(str(item[0]) for item in ordered)
        users_with_recommendations.add(str(context.get("user_id", "")))
        if relevant == 0:
            contexts_without_relevance += 1

    def mean(values: list[float]) -> float:
        return round(sum(values) / len(values), 4) if values else 0.0

    resolved_catalog = catalog_size or len(candidate_ids)
    resolved_users = user_count or len(users_with_recommendations)
    catalog_coverage = (
        round(len(recommended) / resolved_catalog, 4) if resolved_catalog else 0.0
    )
    user_coverage = (
        round(len(users_with_recommendations) / resolved_users, 4)
        if resolved_users
        else 0.0
    )

    return {
        "k": k,
        "contexts": len(precision_values),
        "contexts_total": len(contexts),
        "contexts_without_candidates": contexts_without_candidates,
        "contexts_without_relevance": contexts_without_relevance,
        "total_relevant": total_relevant,
        "precision_at_k": mean(precision_values),
        "recall_at_k": mean(recall_values),
        "ndcg_at_k": mean(ndcg_values),
        "map_at_k": mean(map_values),
        "catalog_coverage": catalog_coverage,
        "user_coverage": user_coverage,
        # Compatibilidade com o contrato anterior do painel.
        "coverage": catalog_coverage,
        "distinct_recommended": len(recommended),
        "catalog_size": resolved_catalog,
        "users_with_recommendations": len(users_with_recommendations),
        "users": resolved_users,
    }


def _popularity_by_context(
    frame: pd.DataFrame, orders: list[Order] | None
) -> dict[str, dict[str, int]]:
    """Popularidade global disponível até o instante de cada contexto."""
    if not orders:
        return {str(context_id): {} for context_id in frame["_context_id"].unique()}

    ordered_orders = sorted(orders, key=lambda order: _as_utc(order.created_at))
    context_times = (
        frame.groupby("_context_id")["_event_time"].min().sort_values()
    )
    counts: Counter[str] = Counter()
    index = 0
    result: dict[str, dict[str, int]] = {}
    for context_id, until in context_times.items():
        until_utc = _as_utc(until)
        while (
            index < len(ordered_orders)
            and _as_utc(ordered_orders[index].created_at) < until_utc
        ):
            counts[str(ordered_orders[index].restaurant_id)] += 1
            index += 1
        result[str(context_id)] = dict(counts)
    return result


def _random_score(context_id: str, restaurant_id: str) -> float:
    digest = hashlib.sha256(
        f"{RANDOM_SEED}:{context_id}:{restaurant_id}".encode("utf-8")
    ).digest()
    return int.from_bytes(digest[:4], "big") / 2**32


def _strategy_contexts(
    frame: pd.DataFrame,
    model_scores: Sequence[float],
    orders: list[Order] | None,
) -> dict[str, list[dict[str, Any]]]:
    """Monta os mesmos contextos/candidatos para as três estratégias."""
    working = frame[
        ["_context_id", "_user_id", "_restaurant_id", "clicked"]
    ].copy()
    working["_model_score"] = list(model_scores)
    popularity = _popularity_by_context(frame, orders)

    model_contexts: list[dict[str, Any]] = []
    popularity_contexts: list[dict[str, Any]] = []
    random_contexts: list[dict[str, Any]] = []

    for context_id, group in working.groupby("_context_id", sort=False):
        context_key = str(context_id)
        user_id = str(group["_user_id"].iloc[0])
        popularity_scores = popularity.get(context_key, {})
        model_items: list[tuple[str, float, int]] = []
        popularity_items: list[tuple[str, float, int]] = []
        random_items: list[tuple[str, float, int]] = []
        for restaurant_id, relevance, score in zip(
            group["_restaurant_id"],
            group["clicked"],
            group["_model_score"],
            strict=True,
        ):
            restaurant_id = str(restaurant_id)
            relevance = int(relevance)
            model_items.append((restaurant_id, float(score), relevance))
            popularity_items.append(
                (restaurant_id, float(popularity_scores.get(restaurant_id, 0)), relevance)
            )
            random_items.append(
                (restaurant_id, _random_score(context_key, restaurant_id), relevance)
            )

        base = {"context_id": context_key, "user_id": user_id}
        model_contexts.append({**base, "items": model_items})
        popularity_contexts.append({**base, "items": popularity_items})
        random_contexts.append({**base, "items": random_items})

    return {
        "model": model_contexts,
        "popularity": popularity_contexts,
        "random": random_contexts,
    }


def _ranking_metrics(
    frame: pd.DataFrame,
    scores: list[float],
    k: int = RANKING_K,
    *,
    orders: list[Order] | None = None,
    catalog_size: int | None = None,
) -> dict[str, Any]:
    """Compatibilidade: métricas de ranking de uma única estratégia."""
    contexts = _strategy_contexts(frame, scores, orders)["model"]
    return compute_ranking_metrics(
        contexts, k, catalog_size=catalog_size
    )


def _popularity_baseline(frame: pd.DataFrame) -> list[float]:
    """Mantido para compatibilidade; use ``_popularity_by_context`` no treino."""
    return (
        frame["restaurant_rating"].astype(float)
        * (1.0 + frame["restaurant_review_count"].astype(float).map(math.log1p))
    ).tolist()


def _random_baseline(frame: pd.DataFrame) -> list[float]:
    return [
        _random_score(str(context_id), str(restaurant_id))
        for context_id, restaurant_id in zip(
            frame["_context_id"], frame["_restaurant_id"], strict=True
        )
    ]


def _roc_auc(
    labels: Sequence[int], scores: Sequence[float]
) -> tuple[float | None, str | None]:
    """Calcula ROC AUC somente quando há amostras e as duas classes."""
    y = [int(value) for value in labels]
    total = len(y)
    positives = sum(y)
    negatives = total - positives
    if total < MIN_ROC_AUC_SAMPLES:
        return None, (
            f"Amostras insuficientes para ROC AUC: {total} < "
            f"{MIN_ROC_AUC_SAMPLES}."
        )
    if positives < MIN_ROC_AUC_POSITIVES:
        return None, (
            f"Positivos insuficientes para ROC AUC: {positives} < "
            f"{MIN_ROC_AUC_POSITIVES}."
        )
    if negatives < MIN_ROC_AUC_NEGATIVES:
        return None, (
            f"Negativos insuficientes para ROC AUC: {negatives} < "
            f"{MIN_ROC_AUC_NEGATIVES}."
        )
    try:
        return round(float(roc_auc_score(y, list(scores))), 4), None
    except ValueError as exc:  # pragma: no cover - proteção defensiva
        return None, f"ROC AUC indisponível: {exc}"


def _fit_and_evaluate(
    frame: pd.DataFrame,
    orders: list[Order] | None = None,
    catalog_size: int | None = None,
) -> tuple[LGBMClassifier, dict[str, Any]]:
    if frame.empty:
        raise InsufficientTrainingDataError("Dataset de treino vazio.")

    columns = feature_columns(frame)
    if not columns:
        raise InsufficientTrainingDataError("Nenhuma feature disponível.")

    X = frame[columns].fillna(0.0).astype(float)
    y = frame["clicked"].astype(int)
    split = _split_frame(frame)
    masks = split["masks"]

    X_train = X.loc[masks["train"]]
    y_train = y.loc[masks["train"]]
    X_validation = X.loc[masks["validation"]]
    y_validation = y.loc[masks["validation"]]
    X_test = X.loc[masks["test"]]
    y_test = y.loc[masks["test"]]

    if len(X_train) == 0:
        raise InsufficientTrainingDataError("Conjunto de treino vazio.")
    if y_train.nunique() < 2:
        raise InsufficientTrainingDataError(
            "O conjunto de treino não contém as duas classes."
        )

    model = LGBMClassifier(**MODEL_PARAMS)
    if len(X_validation) and y_validation.nunique() == 2:
        model.fit(
            X_train,
            y_train,
            eval_set=[(X_validation, y_validation)],
            callbacks=[early_stopping(30, verbose=False)],
        )
    else:
        model.fit(X_train, y_train)

    if masks["test"].any():
        evaluation_frame = frame.loc[masks["test"]]
        evaluation_name = "test"
    elif masks["validation"].any():
        evaluation_frame = frame.loc[masks["validation"]]
        evaluation_name = "validation"
    else:
        evaluation_frame = frame
        evaluation_name = "all"

    if len(evaluation_frame):
        model_scores = model.predict_proba(
            evaluation_frame[columns].fillna(0.0).astype(float)
        )[:, 1].tolist()
    else:
        model_scores = []

    resolved_catalog_size = catalog_size or int(frame["_restaurant_id"].nunique())
    strategies = _strategy_contexts(evaluation_frame, model_scores, orders)
    model_ranking = compute_ranking_metrics(
        strategies["model"], catalog_size=resolved_catalog_size
    )
    baselines = {
        name: compute_ranking_metrics(
            strategies[name], catalog_size=resolved_catalog_size
        )
        for name in ("popularity", "random")
    }

    test_scores = (
        model.predict_proba(X_test)[:, 1].tolist() if len(X_test) else []
    )
    validation_scores = (
        model.predict_proba(X_validation)[:, 1].tolist()
        if len(X_validation)
        else []
    )
    test_auc, test_auc_note = _roc_auc(y_test.tolist(), test_scores)
    validation_auc, _ = _roc_auc(y_validation.tolist(), validation_scores)

    metrics = {
        "samples": int(len(frame)),
        "positives": int(y.sum()),
        "negatives": int(len(frame) - y.sum()),
        "features": len(columns),
        "feature_names": columns,
        "params": MODEL_PARAMS,
        "seed": RANDOM_SEED,
        "split": {
            "strategy": split["strategy"],
            "boundaries": split["boundaries"],
            "train": split["stats"]["train"],
            "validation": split["stats"]["validation"],
            "test": split["stats"]["test"],
            "train_samples": split["stats"]["train"]["samples"],
            "validation_samples": split["stats"]["validation"]["samples"],
            "test_samples": split["stats"]["test"]["samples"],
            "contexts": {
                name: split["stats"][name]["contexts"]
                for name in ("train", "validation", "test")
            },
        },
        "evaluation_split": evaluation_name,
        "roc_auc": test_auc,
        "roc_auc_available": test_auc is not None,
        "roc_auc_note": test_auc_note,
        "validation_roc_auc": validation_auc,
        "test_roc_auc": test_auc,
        "ranking": model_ranking,
        "baselines": baselines,
        "comparison": {
            "ndcg_at_k_delta_vs_popularity": round(
                model_ranking["ndcg_at_k"]
                - baselines["popularity"]["ndcg_at_k"],
                4,
            ),
            "map_at_k_delta_vs_popularity": round(
                model_ranking["map_at_k"] - baselines["popularity"]["map_at_k"],
                4,
            ),
            "precision_at_k_delta_vs_popularity": round(
                model_ranking["precision_at_k"]
                - baselines["popularity"]["precision_at_k"],
                4,
            ),
            "ndcg_at_k_delta_vs_random": round(
                model_ranking["ndcg_at_k"] - baselines["random"]["ndcg_at_k"],
                4,
            ),
            "map_at_k_delta_vs_random": round(
                model_ranking["map_at_k"] - baselines["random"]["map_at_k"],
                4,
            ),
        },
    }
    return model, metrics


def _model_version(
    source: str, frame: pd.DataFrame, columns: list[str], dataset_hash: str
) -> str:
    fingerprint = hashlib.sha256(
        "|".join(columns).encode("utf-8")
        + f"|{dataset_hash}|{len(frame)}|{source}".encode("utf-8")
    ).hexdigest()[:8]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{MODEL_VERSION_PREFIX}-{stamp}-{fingerprint}"


def _quality_assessment(
    metrics: dict[str, Any], split_strategy: str
) -> dict[str, Any]:
    train = metrics["split"]["train"]
    test = metrics["split"]["test"]
    checks = {
        "dataset_not_empty": metrics["samples"] > 0,
        "features_present": metrics["features"] > 0,
        "train_has_two_classes": train["positives"] > 0 and train["negatives"] > 0,
        "temporal_split": split_strategy == "temporal",
        "test_has_contexts": test["contexts"] >= 1,
        "test_has_positive_and_negative": test["positives"] > 0
        and test["negatives"] > 0,
    }
    promotion_checks = {
        "test_has_enough_contexts": test["contexts"] >= MIN_PROMOTION_TEST_CONTEXTS,
        "evaluation_is_test": metrics["evaluation_split"] == "test",
    }
    limitations: list[str] = []
    if split_strategy != "temporal":
        limitations.append(
            "O split não pôde ser estritamente temporal; há risco de "
            "vazamento e o resultado não deve ser usado como evidência."
        )
    if test["contexts"] < 5:
        limitations.append(
            f"Conjunto de teste com apenas {test['contexts']} contexto(s); "
            "as métricas têm alta variância e não são significância estatística."
        )
    if metrics["samples"] < 200:
        limitations.append(
            f"Dataset pequeno ({metrics['samples']} amostras); não é evidência "
            "de desempenho em produção."
        )
    limitations.append(
        "Negativos implícitos: restaurantes não pedidos no contexto são "
        "tratados como não relevantes; ausência de pedido não é rejeição."
    )
    limitations.append(
        "As métricas de ranking são macro-médias por contexto; contextos sem "
        "item relevante entram como 0."
    )
    if not metrics["roc_auc_available"]:
        limitations.append(
            "ROC AUC não reportada: " + str(metrics["roc_auc_note"])
        )
    return {
        "ok": all(checks.values()),
        "promotion_ready": all(checks.values())
        and all(promotion_checks.values()),
        "checks": checks,
        "promotion_checks": promotion_checks,
        "limitations": limitations,
    }


def _model_path() -> Path:
    """Caminho efetivo do artefato de produção (respeita monkeypatch em testes)."""
    return Path(recommender_module.MODEL_PATH)


def _previous_model() -> dict[str, Any] | None:
    model_path = _model_path()
    if not model_path.exists():
        return None
    try:
        bundle = joblib.load(model_path)
    except Exception as exc:  # artefato inválido não impede novo treino
        logger.warning("Modelo anterior ilegível (%s): %s", model_path, exc)
        return {"version": None, "path": str(model_path)}
    if isinstance(bundle, dict):
        metadata = bundle.get("metadata") or {}
        return {
            "version": metadata.get("model_version"),
            "path": str(model_path),
        }
    return {"version": None, "path": str(model_path)}


def _promotion_decision(
    metrics: dict[str, Any],
    quality: dict[str, Any],
    previous: dict[str, Any] | None,
) -> dict[str, Any]:
    model_ranking = metrics["ranking"]
    baselines = metrics["baselines"]
    best_ndcg = max(
        baselines["popularity"]["ndcg_at_k"], baselines["random"]["ndcg_at_k"]
    )
    best_map = max(
        baselines["popularity"]["map_at_k"], baselines["random"]["map_at_k"]
    )
    model_ndcg = model_ranking["ndcg_at_k"]
    model_map = model_ranking["map_at_k"]

    if not quality["ok"]:
        return {
            "decision": "rejected_quality",
            "promoted": False,
            "reason": "O dataset/split não passou nas validações mínimas de qualidade.",
        }
    if not quality["promotion_ready"]:
        return {
            "decision": "insufficient_evidence",
            "promoted": False,
            "reason": (
                "Não há contextos de teste suficientes para comparar o "
                "candidato com o modelo em produção."
            ),
        }
    if previous is None:
        return {
            "decision": "bootstrap",
            "promoted": True,
            "reason": "Não havia modelo em produção; o candidato foi promovido.",
        }

    improved = model_ndcg > best_ndcg + 1e-9 or model_map > best_map + 1e-9
    degraded = (
        model_ndcg + 0.01 < best_ndcg or model_map + 0.01 < best_map
    )
    if improved and not degraded:
        return {
            "decision": "promoted",
            "promoted": True,
            "reason": (
                "O candidato superou o melhor baseline em NDCG@K ou MAP@K "
                "sem degradação relevante na outra métrica."
            ),
        }
    return {
        "decision": "kept_previous",
        "promoted": False,
        "reason": (
            "O candidato não superou o melhor baseline de forma consistente; "
            "o modelo anterior foi preservado para rollback."
        ),
    }


def _build_report(
    *,
    source: str,
    model_version: str,
    metrics: dict[str, Any],
    dataset_hash: str,
    frame: pd.DataFrame,
    quality: dict[str, Any],
    promotion: dict[str, Any],
) -> dict[str, Any]:
    relevance_distribution = {
        str(label): int(count)
        for label, count in frame["clicked"].value_counts().sort_index().items()
    }
    return {
        "schema_version": 2,
        "model_version": model_version,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "model": "LightGBM",
        "dataset": {
            "hash": dataset_hash,
            "samples": metrics["samples"],
            "users": int(frame["_user_id"].nunique()),
            "contexts": int(frame["_context_id"].nunique()),
            "restaurants": int(frame["_restaurant_id"].nunique()),
            "positives": metrics["positives"],
            "negatives": metrics["negatives"],
            "relevance_distribution": relevance_distribution,
            "period": _period(frame),
            "feature_count": metrics["features"],
        },
        "features": metrics["feature_names"],
        "params": metrics["params"],
        "seed": metrics["seed"],
        "split": metrics["split"],
        "metrics": {
            "roc_auc": metrics["roc_auc"],
            "roc_auc_available": metrics["roc_auc_available"],
            "roc_auc_note": metrics["roc_auc_note"],
            "validation_roc_auc": metrics["validation_roc_auc"],
            "test_roc_auc": metrics["test_roc_auc"],
            "evaluation_split": metrics["evaluation_split"],
            "ranking": metrics["ranking"],
        },
        "baselines": metrics["baselines"],
        "comparison": metrics["comparison"],
        "quality": quality,
        "promotion": promotion,
        "phase": "ready" if quality["ok"] else "experimental",
    }


def _save_candidate(
    model: LGBMClassifier,
    columns: list[str],
    metadata: dict[str, Any],
    model_version: str,
) -> Path:
    candidates_dir = _model_path().parent / "candidates"
    candidates_dir.mkdir(parents=True, exist_ok=True)
    path = candidates_dir / f"{model_version}.joblib"
    joblib.dump(
        {
            "model": model,
            "feature_names": columns,
            "metadata": {
                "trained_at": datetime.now(timezone.utc).isoformat(),
                **metadata,
            },
        },
        path,
    )
    return path


def _archive_previous(previous: dict[str, Any] | None) -> Path | None:
    model_path = _model_path()
    if previous is None or not model_path.exists():
        return None
    archive_dir = model_path.parent / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    version = previous.get("version") or "previous"
    path = archive_dir / f"{version}.joblib"
    shutil.copy2(model_path, path)
    return path


def _train_and_save(
    *,
    source: str,
    users: list[User],
    orders: list[Order],
    restaurants: list[Restaurant],
    interactions: list[UserRestaurantInteraction] | None = None,
) -> dict[str, Any] | None:
    frame = build_training_frame(
        users, orders, restaurants, interactions=interactions
    )
    if frame.empty:
        logger.warning("Dataset vazio; modelo não será treinado.")
        return None

    dataset_hash = _dataset_hash(frame)
    columns = feature_columns(frame)
    try:
        model, metrics = _fit_and_evaluate(
            frame, orders=orders, catalog_size=len(restaurants)
        )
    except InsufficientTrainingDataError as exc:
        logger.warning("Treino recusado: %s", exc)
        return None

    version = _model_version(source, frame, columns, dataset_hash)
    metadata = {
        **metrics,
        "source": source,
        "model_version": version,
        "dataset_hash": dataset_hash,
    }
    candidate_path = _save_candidate(model, columns, metadata, version)
    quality = _quality_assessment(metrics, metrics["split"]["strategy"])
    previous = _previous_model()
    promotion = _promotion_decision(metrics, quality, previous)
    promotion.update(
        {
            "candidate_path": str(candidate_path),
            "previous_model_version": previous.get("version")
            if previous
            else None,
        }
    )

    if promotion["promoted"]:
        archived = _archive_previous(previous)
        if archived is not None:
            promotion["archived_previous_path"] = str(archived)
        recommender.save(model, columns, metadata=metadata)
        logger.info("Modelo %s promovido para produção.", version)
    else:
        logger.info(
            "Modelo %s não promovido (%s); produção preservada.",
            version,
            promotion["decision"],
        )

    report = _build_report(
        source=source,
        model_version=version,
        metrics=metrics,
        dataset_hash=dataset_hash,
        frame=frame,
        quality=quality,
        promotion=promotion,
    )
    save_training_report(report)
    return {
        **metrics,
        "model_version": version,
        "dataset_hash": dataset_hash,
        "quality": quality,
        "promotion": promotion,
    }


async def load_training_data(
    session: AsyncSession,
) -> tuple[
    list[User],
    list[Order],
    list[Restaurant],
    list[UserRestaurantInteraction],
]:
    users = (await session.execute(select(User))).scalars().all()
    orders = (await session.execute(select(Order))).scalars().all()
    restaurants = (await session.execute(select(Restaurant))).scalars().all()
    interactions = (
        (await session.execute(select(UserRestaurantInteraction))).scalars().all()
    )
    return list(users), list(orders), list(restaurants), list(interactions)


def _stable_id(value: str) -> uuid.UUID:
    return uuid.uuid5(SEED_NAMESPACE, value)


def build_seed_entities(
    now: datetime | None = None,
) -> tuple[list[User], list[Order], list[Restaurant]]:
    """Monta entidades em memória a partir do seed determinístico."""
    users = [
        User(
            id=_stable_id(f"user:{data['email']}"),
            name=data["name"],
            email=data["email"],
            dietary_preferences=list(data["dietary_preferences"]),
        )
        for data in SEED_USERS
    ]
    restaurants = [
        Restaurant(
            id=_stable_id(f"restaurant:{data['name']}"),
            name=data["name"],
            description=f"Melhor {data['category'].lower()} de Osasco",
            phone="+55 11 99999-0000",
            address=data["address"],
            categories=[data["category"]],
            average_rating=data["rating"],
            review_count=data["review_count"],
            delivery_fee=data["delivery_fee"],
            delivery_time_min=data["delivery_time_min"],
            delivery_time_max=data["delivery_time_max"],
            image_url=data["image_url"],
            dietary_tags=list(data.get("dietary_tags", [])),
        )
        for data in SEED_RESTAURANTS
    ]

    users_by_email = {user.email: user for user in users}
    restaurants_by_name = {restaurant.name: restaurant for restaurant in restaurants}
    menu_by_name = {
        item["name"]: item["menu_item"] for item in SEED_RESTAURANTS
    }

    from datetime import timedelta

    local_now = now or datetime.now(APP_TIMEZONE)
    orders: list[Order] = []
    for index, (email, restaurant_name, days_ago, hour, quantity) in enumerate(
        SEED_ORDERS
    ):
        user = users_by_email.get(email)
        restaurant = restaurants_by_name.get(restaurant_name)
        menu_item = menu_by_name.get(restaurant_name)
        if user is None or restaurant is None or menu_item is None:
            continue

        created_at = (local_now - timedelta(days=days_ago)).replace(
            hour=hour,
            minute=0,
            second=0,
            microsecond=0,
        )
        orders.append(
            Order(
                id=_stable_id(f"order:{index}"),
                user_id=user.id,
                restaurant_id=restaurant.id,
                items=[
                    {
                        "id": menu_item["id"],
                        "name": menu_item["name"],
                        "quantity": quantity,
                        "price": menu_item["price"],
                    }
                ],
                order_value=round(menu_item["price"] * quantity, 2),
                delivery_fee=float(restaurant.delivery_fee),
                status="Entregue",
                created_at=created_at.astimezone(timezone.utc),
            )
        )

    return users, orders, restaurants


def train_from_seed() -> dict[str, Any] | None:
    """Treina o LightGBM usando o seed determinístico, sem acessar o banco."""
    users, orders, restaurants = build_seed_entities()
    return _train_and_save(
        source="seed",
        users=users,
        orders=orders,
        restaurants=restaurants,
    )


async def train() -> dict[str, Any] | None:
    async with AsyncSessionLocal() as session:
        users, orders, restaurants, interactions = await load_training_data(session)

    result = _train_and_save(
        source="database",
        users=users,
        orders=orders,
        restaurants=restaurants,
        interactions=interactions,
    )
    if result is None:
        return None

    # Salva a distribuição de treino (baseline) para cada feature monitorada,
    # usada futuramente pelo monitoramento de drift.
    try:
        from app.services.drift import drift_monitor  # evita import circular

        frame = build_training_frame(
            users, orders, restaurants, interactions=interactions
        )
        for feature in drift_monitor.feature_names:
            if feature in frame.columns:
                values = frame[feature].dropna().astype(float).tolist()
                await drift_monitor.save_baseline(feature, values)
    except Exception as exc:  # não deve falhar o treino por causa do drift
        logger.warning("Falha ao salvar baseline de drift: %s", exc)

    return result


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Treino offline do recomendador LightGBM"
    )
    parser.add_argument(
        "--source",
        choices=("db", "seed"),
        default="db",
        help="'db' usa os pedidos do PostgreSQL; 'seed' usa o seed determinístico.",
    )
    args = parser.parse_args()

    if args.source == "seed":
        result = train_from_seed()
    else:
        result = asyncio.run(train())

    if result is None:
        print("Dados insuficientes para treino; modelo nao salvo.")
        return 1

    print(
        f"Modelo treinado ({args.source}): "
        f"{json.dumps(result, default=str, indent=2)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
