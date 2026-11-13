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
- o alvo é **compra observada** (``purchased``), não clique. O nome antigo
  ``clicked`` foi substituído para não sugerir um objetivo que o rótulo não
  representa;
- negativos **observados** (o usuário teve contato com o restaurante antes do
  contexto) recebem peso maior que negativos **não observados**; ausência de
  pedido não é tratada como rejeição com o mesmo peso;
- o relatório registra hash do dataset, períodos, contagens, baselines,
  intervalos por usuário, métricas preditivas, comparação com o modelo em
  produção, limitações e a decisão de promoção/rollback.

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
from statistics import NormalDist, mean, pstdev
from typing import Any, Iterable, Sequence

import joblib
import pandas as pd
from lightgbm import LGBMClassifier, early_stopping
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    log_loss,
    roc_auc_score,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import APP_TIMEZONE, TURNOS, Turno
from app.database import AsyncSessionLocal
from app.ml.features import (
    CURRENT_STATE_RESTAURANT_FEATURES,
    _as_utc,
    build_candidate_features,
    build_user_features,
    feature_temporal_policy,
    order_turno,
    resolve_restaurant_state,
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
# Margem mínima de melhoria e tolerância de degradação ao comparar modelos.
MIN_PROMOTION_IMPROVEMENT = 0.01
MAX_PROMOTION_DEGRADATION = 0.01
# Peso de um negativo sem exposição observada. Ausência de pedido não é
# rejeição: o usuário pode nunca ter visto o restaurante.
UNOBSERVED_NEGATIVE_WEIGHT = 0.1
# Reamostragens do bootstrap por usuário (métricas offline).
BOOTSTRAP_RESAMPLES = 1000

# Semântica explícita do alvo: o rótulo positivo é uma compra observada.
TARGET_COLUMN = "purchased"
LABEL_SEMANTICS = (
    "O alvo positivo é uma compra/pedido observado no contexto "
    "(relevância binária). O modelo NÃO é um estimador de clique; para "
    "interesse/clique seria necessário um alvo e uma janela de atribuição "
    "próprios."
)
NEGATIVE_POLICY = (
    "Negativos observados (restaurante com interação registrada antes do "
    "contexto) recebem peso 1.0; negativos não observados recebem peso "
    f"{UNOBSERVED_NEGATIVE_WEIGHT}. O peso só é usado no treino; as métricas "
    "de ranking continuam usando o rótulo binário e o catálogo inteiro."
)

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
    "purchased",
    "_observed",
    "_sample_weight",
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
    """Hash canônico do dataset (contexto, candidato, rótulo, exposição e instante)."""
    rows = sorted(
        (
            str(context_id),
            str(restaurant_id),
            int(purchased),
            int(observed),
            _as_utc(event_time).isoformat(),
        )
        for context_id, restaurant_id, purchased, observed, event_time in zip(
            frame["_context_id"],
            frame["_restaurant_id"],
            frame["purchased"],
            frame["_observed"],
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
    snapshots: list[Any] | None = None,
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
                    # Restaurantes com algum contato registrado antes do
                    # contexto. Serve para distinguir negativo observado de
                    # negativo sem exposição (ver NEGATIVE_POLICY).
                    "observed": {
                        str(interaction.restaurant_id)
                        for interaction in history_interactions
                    },
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
    snapshots: list[Any] | None = None,
) -> pd.DataFrame:
    """Gera uma linha por (contexto, candidato) com o rótulo observado.

    O alvo ``purchased`` é 1 quando houve pedido naquele contexto. Negativos
    recebem ``_sample_weight`` diferente conforme tenham ou não exposição
    observada: ausência de compra não é rejeição.

    ``negatives_per_positive`` e ``seed`` são mantidos por compatibilidade de
    assinatura; a avaliação usa o catálogo inteiro como candidatos para que
    todas as estratégias recebam exatamente o mesmo conjunto.
    """
    del negatives_per_positive, seed
    contexts = build_contexts(
        users, orders, restaurants, interactions=interactions, snapshots=snapshots
    )
    rows: list[dict[str, Any]] = []
    for context in contexts:
        for restaurant in context["candidates"]:
            restaurant_id = str(restaurant.id)
            purchased = 1 if restaurant_id in context["relevant"] else 0
            observed = restaurant_id in context.get("observed", set())
            state = resolve_restaurant_state(
                restaurant, snapshots, context["until"]
            )
            row = build_candidate_features(
                context["user_features"],
                restaurant,
                context["turno"],
                restaurant_state=state,
            )
            row.update(
                {
                    "purchased": purchased,
                    "_observed": bool(observed),
                    "_sample_weight": 1.0
                    if purchased or observed
                    else UNOBSERVED_NEGATIVE_WEIGHT,
                    "_user_id": context["user_id"],
                    "_restaurant_id": restaurant_id,
                    "_turno": context["turno"],
                    "_context_id": context["context_id"],
                    "_event_time": context["until"],
                }
            )
            rows.append(row)
    return pd.DataFrame(rows)


def _split_stats(frame: pd.DataFrame, mask: pd.Series) -> dict[str, Any]:
    subset = frame.loc[mask]
    positives = int(subset["purchased"].sum()) if len(subset) else 0
    negative_mask = subset["purchased"] == 0
    observed_negatives = (
        int((negative_mask & subset["_observed"]).sum()) if len(subset) else 0
    )
    unobserved_negatives = (
        int((negative_mask & ~subset["_observed"]).sum()) if len(subset) else 0
    )
    return {
        "samples": int(len(subset)),
        "contexts": int(subset["_context_id"].nunique()) if len(subset) else 0,
        "users": int(subset["_user_id"].nunique()) if len(subset) else 0,
        "positives": positives,
        "negatives": int(len(subset) - positives),
        "observed_negatives": observed_negatives,
        "unobserved_negatives": unobserved_negatives,
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
                    "observed_negatives": 0,
                    "unobserved_negatives": 0,
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


def _percentile(values: Sequence[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[int(position)]
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def _bootstrap_by_user(
    per_context: Sequence[dict[str, Any]],
    metric_key: str,
    resamples: int,
    seed: int,
) -> dict[str, float] | None:
    """IC 95% por reamostragem de **usuários** com reposição.

    Reamostrar linhas individuais quebraria a dependência entre contextos do
    mesmo usuário; por isso o usuário inteiro é a unidade de reamostragem.
    """
    by_user: dict[str, list[float]] = defaultdict(list)
    for item in per_context:
        by_user[str(item["user_id"])].append(float(item[metric_key]))
    users = sorted(by_user)
    if len(users) < 2 or resamples <= 0:
        return None

    rng = random.Random(f"{seed}:{metric_key}")
    means: list[float] = []
    for _ in range(resamples):
        sampled = [rng.choice(users) for _ in users]
        values = [value for user in sampled for value in by_user[user]]
        if values:
            means.append(sum(values) / len(values))
    if not means:
        return None
    return {
        "low": round(_percentile(means, 0.025), 4),
        "high": round(_percentile(means, 0.975), 4),
        "resamples": resamples,
        "unit": "user",
    }


def _jaccard_distance(left: set[str], right: set[str]) -> float:
    if not left and not right:
        return 0.0
    union = left | right
    if not union:
        return 0.0
    return 1.0 - len(left & right) / len(union)


def compute_ranking_metrics(
    contexts: Sequence[dict[str, Any]],
    k: int = RANKING_K,
    *,
    catalog_size: int | None = None,
    user_count: int | None = None,
    item_attributes: dict[str, set[str]] | None = None,
    popularity_counts: dict[str, int] | None = None,
    popularity_total: int | None = None,
    bootstrap_resamples: int = BOOTSTRAP_RESAMPLES,
    bootstrap_seed: int = RANDOM_SEED,
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
    - ``catalog_coverage`` e ``user_coverage`` são reportadas separadamente;
    - ``ild_at_k`` (diversidade intra-lista) só é calculada quando
      ``item_attributes`` é fornecido; usa distância de Jaccard entre
      categorias/cozinhas dos itens do Top K;
    - ``novelty_at_k`` usa ``-log2(pop(r) / N)`` com piso de 1 para evitar
      ``log(0)``; é ``None`` sem contagens de popularidade;
    - os intervalos de confiança são bootstrap por **usuário**, não por linha.
    """
    precision_values: list[float] = []
    recall_values: list[float] = []
    ndcg_values: list[float] = []
    map_values: list[float] = []
    ild_values: list[float] = []
    novelty_values: list[float] = []
    per_context: list[dict[str, Any]] = []
    recommended: set[str] = set()
    users_with_recommendations: set[str] = set()
    candidate_ids: set[str] = set()
    contexts_without_candidates = 0
    contexts_without_relevance = 0
    total_relevant = 0

    resolved_popularity_total = popularity_total
    if resolved_popularity_total is None and popularity_counts:
        resolved_popularity_total = sum(popularity_counts.values())

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

        precision = hits / min(k, n_candidates)
        recall = hits / relevant if relevant else 0.0
        precision_values.append(precision)
        recall_values.append(recall)

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
        ndcg = dcg / idcg if idcg else 0.0
        ndcg_values.append(ndcg)

        average_precision = 0.0
        hit_count = 0
        for rank, (_, _, gain) in enumerate(top, start=1):
            if float(gain) > 0:
                hit_count += 1
                average_precision += hit_count / rank
        average_precision = (
            average_precision / min(relevant, k) if relevant else 0.0
        )
        map_values.append(average_precision)

        per_context.append(
            {
                "context_id": str(context.get("context_id", "")),
                "user_id": str(context.get("user_id", "")),
                "precision_at_k": precision,
                "recall_at_k": recall,
                "ndcg_at_k": ndcg,
                "map_at_k": average_precision,
            }
        )

        if item_attributes is not None and len(top) >= 2:
            top_ids = [str(item[0]) for item in top]
            pairs = 0
            distance_sum = 0.0
            for index, left_id in enumerate(top_ids):
                left = item_attributes.get(left_id, set())
                for right_id in top_ids[index + 1 :]:
                    right = item_attributes.get(right_id, set())
                    distance_sum += _jaccard_distance(left, right)
                    pairs += 1
            if pairs:
                ild_values.append(distance_sum / pairs)

        context_popularity = context.get("popularity", popularity_counts)
        context_total = context.get("popularity_total", resolved_popularity_total)
        if context_popularity is not None and context_total:
            total = max(int(context_total), 1)
            novelty = [
                -math.log2(
                    max(int(context_popularity.get(str(item[0]), 0)), 1) / total
                )
                for item in top
            ]
            if novelty:
                novelty_values.append(sum(novelty) / len(novelty))

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

    confidence_intervals = {
        metric: _bootstrap_by_user(
            per_context, metric, bootstrap_resamples, bootstrap_seed
        )
        for metric in (
            "precision_at_k",
            "recall_at_k",
            "ndcg_at_k",
            "map_at_k",
        )
    }

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
        "ild_at_k": mean(ild_values) if ild_values else None,
        "novelty_at_k": mean(novelty_values) if novelty_values else None,
        "catalog_coverage": catalog_coverage,
        "user_coverage": user_coverage,
        # Compatibilidade com o contrato anterior do painel.
        "coverage": catalog_coverage,
        "distinct_recommended": len(recommended),
        "catalog_size": resolved_catalog,
        "users_with_recommendations": len(users_with_recommendations),
        "users": resolved_users,
        "confidence_intervals": confidence_intervals,
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
    *,
    candidate_pool: str = "all",
) -> dict[str, list[dict[str, Any]]]:
    """Monta os mesmos contextos/candidatos para as três estratégias.

    ``candidate_pool`` permite análises de sensibilidade:

    - ``all``: catálogo inteiro (avaliação principal);
    - ``observed``: positivos + negativos com exposição observada;
    - ``unobserved``: positivos + negativos sem exposição observada.
    """
    working = frame[
        ["_context_id", "_user_id", "_restaurant_id", "purchased", "_observed"]
    ].copy()
    working["_model_score"] = list(model_scores)
    popularity = _popularity_by_context(frame, orders)

    model_contexts: list[dict[str, Any]] = []
    popularity_contexts: list[dict[str, Any]] = []
    random_contexts: list[dict[str, Any]] = []

    for context_id, group in working.groupby("_context_id", sort=False):
        if candidate_pool == "observed":
            group = group[(group["purchased"] == 1) | group["_observed"]]
        elif candidate_pool == "unobserved":
            group = group[(group["purchased"] == 1) | ~group["_observed"]]
        context_key = str(context_id)
        user_id = str(group["_user_id"].iloc[0])
        popularity_scores = popularity.get(context_key, {})
        model_items: list[tuple[str, float, int]] = []
        popularity_items: list[tuple[str, float, int]] = []
        random_items: list[tuple[str, float, int]] = []
        for restaurant_id, relevance, score in zip(
            group["_restaurant_id"],
            group["purchased"],
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

        base = {
            "context_id": context_key,
            "user_id": user_id,
            "popularity": popularity_scores,
            "popularity_total": sum(popularity_scores.values()),
        }
        model_contexts.append({**base, "items": model_items})
        popularity_contexts.append({**base, "items": popularity_items})
        random_contexts.append({**base, "items": random_items})

    return {
        "model": model_contexts,
        "popularity": popularity_contexts,
        "random": random_contexts,
    }


def _ranking_sensitivity(
    evaluation_frame: pd.DataFrame,
    model_scores: Sequence[float],
    orders: list[Order] | None,
    *,
    catalog_size: int,
    item_attributes: dict[str, set[str]] | None,
) -> dict[str, Any]:
    """Sensibilidade das métricas aos negativos observados/não observados.

    A avaliação principal continua usando o catálogo inteiro. Esta análise
    responde a uma pergunta diferente: o resultado muda se restringirmos os
    candidatos a negativos com exposição observada ou a negativos sem
    exposição? Cada pool mantém os positivos e apenas o subconjunto de
    negativos indicado.
    """
    pools: dict[str, Any] = {}
    for pool, label in (
        ("observed", "negativos_observados"),
        ("unobserved", "negativos_nao_observados"),
    ):
        negative_mask = evaluation_frame["purchased"] == 0
        selected = (
            evaluation_frame["_observed"]
            if pool == "observed"
            else ~evaluation_frame["_observed"]
        )
        negative_count = int((negative_mask & selected).sum())
        positive_count = int((evaluation_frame["purchased"] == 1).sum())
        entry: dict[str, Any] = {
            "available": negative_count > 0,
            "positives": positive_count,
            "negatives": negative_count,
            "reason": None,
            "metrics": {},
        }
        if negative_count == 0:
            entry["reason"] = (
                "Não há negativos deste tipo no conjunto de avaliação; "
                "qualquer métrica seria trivial (apenas positivos)."
            )
            pools[label] = entry
            continue
        contexts = _strategy_contexts(
            evaluation_frame,
            model_scores,
            orders,
            candidate_pool=pool,
        )
        entry["metrics"] = {
            name: compute_ranking_metrics(
                contexts[name],
                catalog_size=catalog_size,
                item_attributes=item_attributes,
            )
            for name in ("model", "popularity", "random")
        }
        pools[label] = entry
    return {
        "primary": "all_candidates",
        "pools": pools,
        "note": (
            "Análise de sensibilidade, não substitui a avaliação principal do "
            "catálogo inteiro. Restringir candidatos muda o objetivo da "
            "métrica; compare os pools apenas como diagnóstico."
        ),
    }


def _ranking_metrics(
    frame: pd.DataFrame,
    scores: list[float],
    k: int = RANKING_K,
    *,
    orders: list[Order] | None = None,
    catalog_size: int | None = None,
    item_attributes: dict[str, set[str]] | None = None,
) -> dict[str, Any]:
    """Compatibilidade: métricas de ranking de uma única estratégia."""
    contexts = _strategy_contexts(frame, scores, orders)["model"]
    return compute_ranking_metrics(
        contexts, k, catalog_size=catalog_size, item_attributes=item_attributes
    )


def _item_attributes(restaurants: Sequence[Restaurant]) -> dict[str, set[str]]:
    """Atributos usados na diversidade intra-lista (categorias + cozinha)."""
    attributes: dict[str, set[str]] = {}
    for restaurant in restaurants:
        values = {
            str(value).strip().lower()
            for value in (restaurant.categories or [])
            if str(value).strip()
        }
        if restaurant.cuisine:
            values.add(str(restaurant.cuisine).strip().lower())
        attributes[str(restaurant.id)] = values
    return attributes


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


def _calibration_curve(
    labels: Sequence[int],
    scores: Sequence[float],
    *,
    bins: int = 10,
) -> dict[str, Any] | None:
    """Curva de calibração por bins e Expected Calibration Error (ECE).

    Cada bin compara a probabilidade média prevista com a taxa observada de
    positivos. O ECE é a média ponderada pelo número de amostras. Não substitui
    Brier/Log Loss: é um diagnóstico visual/numérico da calibração.
    """
    pairs = [
        (float(score), int(label))
        for label, score in zip(labels, scores, strict=True)
    ]
    if not pairs or bins <= 0:
        return None
    total = len(pairs)
    entries: list[dict[str, Any]] = []
    weighted_error = 0.0
    max_error = 0.0
    for index in range(bins):
        low = index / bins
        high = (index + 1) / bins
        members = [
            (score, label)
            for score, label in pairs
            if (low <= score < high) or (index == bins - 1 and score == 1.0)
        ]
        if not members:
            continue
        mean_predicted = sum(score for score, _ in members) / len(members)
        observed = sum(label for _, label in members) / len(members)
        error = abs(mean_predicted - observed)
        weighted_error += error * len(members) / total
        max_error = max(max_error, error)
        entries.append(
            {
                "bin_low": round(low, 4),
                "bin_high": round(high, 4),
                "count": len(members),
                "mean_predicted": round(mean_predicted, 4),
                "observed_rate": round(observed, 4),
            }
        )
    return {
        "bins": entries,
        "expected_calibration_error": round(weighted_error, 4),
        "max_calibration_error": round(max_error, 4),
        "samples": total,
    }


def _predictive_metrics(
    labels: Sequence[int], scores: Sequence[float]
) -> dict[str, Any]:
    """ROC AUC, PR AUC, Brier, Log Loss e calibração, com disponibilidade própria.

    ROC AUC e PR AUC exigem as duas classes. Brier, Log Loss e a curva de
    calibração podem ser calculados mesmo quando há uma única classe, desde que
    existam probabilidades e rótulos válidos. Condicionar todas as métricas à
    ROC AUC esconderia informação de calibração em amostras pequenas.
    """
    y = [int(value) for value in labels]
    probabilities = [float(value) for value in scores]
    roc_auc, note = _roc_auc(y, probabilities)
    positives = sum(y)
    negatives = len(y) - positives
    result: dict[str, Any] = {
        "roc_auc": roc_auc,
        "roc_auc_available": roc_auc is not None,
        "roc_auc_note": note,
        "pr_auc": None,
        "pr_auc_note": None,
        "brier_score": None,
        "log_loss": None,
        "calibration": None,
        "predictive_notes": {},
    }
    if not y or len(y) != len(probabilities):
        result["predictive_notes"]["all"] = (
            "Rótulos/probabilidades ausentes ou com tamanhos diferentes."
        )
        return result

    if positives > 0 and negatives > 0:
        try:
            result["pr_auc"] = round(
                float(average_precision_score(y, probabilities)), 4
            )
        except ValueError as exc:  # pragma: no cover - proteção defensiva
            result["pr_auc_note"] = f"PR AUC indisponível: {exc}"
    else:
        result["pr_auc_note"] = (
            "PR AUC exige pelo menos um positivo e um negativo."
        )

    try:
        result["brier_score"] = round(
            float(brier_score_loss(y, probabilities)), 4
        )
    except ValueError as exc:  # pragma: no cover - proteção defensiva
        result["predictive_notes"]["brier_score"] = (
            f"Brier indisponível: {exc}"
        )

    try:
        clipped = [min(max(value, 1e-6), 1 - 1e-6) for value in probabilities]
        result["log_loss"] = round(
            float(log_loss(y, clipped, labels=[0, 1])), 4
        )
    except ValueError as exc:  # pragma: no cover - proteção defensiva
        result["predictive_notes"]["log_loss"] = f"Log Loss indisponível: {exc}"

    result["calibration"] = _calibration_curve(y, probabilities)
    return result


def _evaluation_selection(
    frame: pd.DataFrame,
) -> tuple[dict[str, Any], pd.Series, str]:
    """Split temporal e máscara usada para avaliar o modelo.

    Teste é preferido; sem teste, validação; sem ambos, o dataset inteiro (com
    a limitação registrada no relatório).
    """
    split = _split_frame(frame)
    masks = split["masks"]
    if masks["test"].any():
        return split, masks["test"], "test"
    if masks["validation"].any():
        return split, masks["validation"], "validation"
    return split, pd.Series(True, index=frame.index), "all"


def _fit_and_evaluate(
    frame: pd.DataFrame,
    orders: list[Order] | None = None,
    catalog_size: int | None = None,
    restaurants: Sequence[Restaurant] | None = None,
    *,
    strict_temporal: bool = False,
) -> tuple[LGBMClassifier, dict[str, Any]]:
    if frame.empty:
        raise InsufficientTrainingDataError("Dataset de treino vazio.")

    all_columns = feature_columns(frame)
    columns = (
        [
            name
            for name in all_columns
            if name not in CURRENT_STATE_RESTAURANT_FEATURES
        ]
        if strict_temporal
        else all_columns
    )
    if not columns:
        raise InsufficientTrainingDataError("Nenhuma feature disponível.")

    X = frame[columns].fillna(0.0).astype(float)
    y = frame["purchased"].astype(int)
    split, evaluation_mask, evaluation_name = _evaluation_selection(frame)
    masks = split["masks"]

    X_train = X.loc[masks["train"]]
    y_train = y.loc[masks["train"]]
    train_weights = frame.loc[masks["train"], "_sample_weight"].astype(float)
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
            sample_weight=train_weights,
            eval_set=[(X_validation, y_validation)],
            callbacks=[early_stopping(30, verbose=False)],
        )
    else:
        model.fit(X_train, y_train, sample_weight=train_weights)

    evaluation_frame = frame.loc[evaluation_mask]
    if len(evaluation_frame):
        model_scores = model.predict_proba(
            evaluation_frame[columns].fillna(0.0).astype(float)
        )[:, 1].tolist()
    else:
        model_scores = []

    resolved_catalog_size = catalog_size or int(frame["_restaurant_id"].nunique())
    strategies = _strategy_contexts(evaluation_frame, model_scores, orders)
    attributes = _item_attributes(restaurants) if restaurants else None
    model_ranking = compute_ranking_metrics(
        strategies["model"],
        catalog_size=resolved_catalog_size,
        item_attributes=attributes,
    )
    baselines = {
        name: compute_ranking_metrics(
            strategies[name],
            catalog_size=resolved_catalog_size,
            item_attributes=attributes,
        )
        for name in ("popularity", "random")
    }
    sensitivity = _ranking_sensitivity(
        evaluation_frame,
        model_scores,
        orders,
        catalog_size=resolved_catalog_size,
        item_attributes=attributes,
    )

    test_scores = (
        model.predict_proba(X_test)[:, 1].tolist() if len(X_test) else []
    )
    validation_scores = (
        model.predict_proba(X_validation)[:, 1].tolist()
        if len(X_validation)
        else []
    )
    test_predictive = _predictive_metrics(y_test.tolist(), test_scores)
    validation_predictive = _predictive_metrics(
        y_validation.tolist(), validation_scores
    )

    # Calibração: ajusta Platt Scaling e Isotonic Regression na validação e
    # escolhe o método com menor Brier Score. Se não houver validação suficiente,
    # mantém "none" (probabilidades brutas).
    calibrator = None
    calibration_method = "none"
    try:
        import numpy as np
        from sklearn.isotonic import IsotonicRegression
        from sklearn.linear_model import LogisticRegression
        from sklearn.metrics import brier_score_loss

        y_val_arr = np.asarray(y_validation.tolist(), dtype=int)
        scores_val_arr = np.asarray(validation_scores, dtype=float)
        if (
            len(y_val_arr) >= 10
            and len(np.unique(y_val_arr)) == 2
            and len(scores_val_arr) == len(y_val_arr)
        ):
            # Platt
            platt = LogisticRegression()
            platt.fit(scores_val_arr.reshape(-1, 1), y_val_arr)
            platt_scores = platt.predict_proba(scores_val_arr.reshape(-1, 1))[:, 1]
            platt_brier = brier_score_loss(y_val_arr, platt_scores)

            # Isotonic
            iso = IsotonicRegression(out_of_bounds="clip")
            iso.fit(scores_val_arr, y_val_arr)
            iso_scores = iso.predict(scores_val_arr)
            iso_brier = brier_score_loss(y_val_arr, iso_scores)

            if iso_brier < platt_brier:
                calibrator = iso
                calibration_method = "isotonic"
            else:
                calibrator = platt
                calibration_method = "platt"
    except Exception as exc:  # noqa: BLE001
        logger.warning("Falha ao ajustar calibração: %s", exc)
        calibrator = None
        calibration_method = "none"

    # Métricas calibradas no teste (diagnóstico antes/depois).
    calibrated_test_scores: list[float] = []
    if calibrator is not None and len(test_scores):
        try:
            import numpy as np

            arr = np.asarray(test_scores, dtype=float)
            if calibration_method == "platt":
                calibrated_test_scores = calibrator.predict_proba(
                    arr.reshape(-1, 1)
                )[:, 1].tolist()
            else:
                calibrated_test_scores = calibrator.predict(arr).tolist()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Falha ao calibrar scores de teste: %s", exc)
            calibrated_test_scores = []

    metrics = {
        "samples": int(len(frame)),
        "positives": int(y.sum()),
        "negatives": int(len(frame) - y.sum()),
        "observed_negatives": int(
            ((frame["purchased"] == 0) & frame["_observed"]).sum()
        ),
        "unobserved_negatives": int(
            ((frame["purchased"] == 0) & ~frame["_observed"]).sum()
        ),
        "features": len(columns),
        "feature_names": columns,
        "temporal_mode": "strict" if strict_temporal else "current_state_attributes",
        "feature_temporal_policy": feature_temporal_policy(),
        "params": MODEL_PARAMS,
        "seed": RANDOM_SEED,
        "label_semantics": LABEL_SEMANTICS,
        "negative_policy": NEGATIVE_POLICY,
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
        "roc_auc": test_predictive["roc_auc"],
        "roc_auc_available": test_predictive["roc_auc_available"],
        "roc_auc_note": test_predictive["roc_auc_note"],
        "pr_auc": test_predictive["pr_auc"],
        "pr_auc_note": test_predictive["pr_auc_note"],
        "brier_score": test_predictive["brier_score"],
        "log_loss": test_predictive["log_loss"],
        "calibration": test_predictive["calibration"],
        "calibration_method": calibration_method,
        "calibrated_predictive": (
            _predictive_metrics(y_test.tolist(), calibrated_test_scores)
            if calibrated_test_scores
            else None
        ),
        "predictive_notes": test_predictive["predictive_notes"],
        "validation_roc_auc": validation_predictive["roc_auc"],
        "test_roc_auc": test_predictive["roc_auc"],
        "ranking": model_ranking,
        "ranking_sensitivity": sensitivity,
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
    return model, metrics, calibrator, calibration_method


def rolling_window_evaluation(
    frame: pd.DataFrame,
    orders: list[Order] | None = None,
    restaurants: Sequence[Restaurant] | None = None,
    *,
    windows: int = 3,
    catalog_size: int | None = None,
    strict_temporal: bool = False,
) -> dict[str, Any]:
    """Avaliação walk-forward com janelas expansíveis.

    Cada fold treina em contextos antigos, valida no bloco imediatamente
    anterior ao teste e testa no bloco seguinte. O objetivo é medir estabilidade
    temporal, não escolher hiperparâmetros no teste. Com menos contextos do que
    o necessário, retorna ``available=False`` com motivo explícito.
    """
    if windows < 2:
        return {
            "available": False,
            "windows": windows,
            "folds": [],
            "reason": "São necessárias pelo menos 2 janelas para avaliar estabilidade.",
        }
    context_times = (
        frame.groupby("_context_id")["_event_time"].min().sort_values()
    )
    context_ids = list(context_times.index)
    total_contexts = len(context_ids)
    minimum_contexts = (windows + 1) * 2
    if total_contexts < minimum_contexts:
        return {
            "available": False,
            "windows": windows,
            "folds": [],
            "reason": (
                f"Contextos insuficientes para {windows} janelas: "
                f"{total_contexts} < {minimum_contexts}."
            ),
        }

    all_columns = feature_columns(frame)
    columns = (
        [
            name
            for name in all_columns
            if name not in CURRENT_STATE_RESTAURANT_FEATURES
        ]
        if strict_temporal
        else all_columns
    )
    if not columns:
        return {
            "available": False,
            "windows": windows,
            "folds": [],
            "reason": "Nenhuma feature disponível após o filtro temporal.",
        }

    test_size = max(1, total_contexts // (windows + 1))
    attributes = _item_attributes(restaurants) if restaurants else None
    resolved_catalog = catalog_size or int(frame["_restaurant_id"].nunique())
    folds: list[dict[str, Any]] = []

    for fold_index in range(windows):
        test_end = total_contexts - test_size * (windows - fold_index - 1)
        test_start = test_end - test_size
        train_end = test_start
        validation_size = max(1, test_size // 2)
        train_stop = max(2, train_end - validation_size)
        if train_stop >= train_end or test_start < train_stop:
            continue
        train_ids = context_ids[:train_stop]
        validation_ids = context_ids[train_stop:train_end]
        test_ids = context_ids[test_start:test_end]

        train_mask = frame["_context_id"].isin(train_ids)
        validation_mask = frame["_context_id"].isin(validation_ids)
        test_mask = frame["_context_id"].isin(test_ids)
        train_frame = frame.loc[train_mask]
        validation_frame = frame.loc[validation_mask]
        test_frame = frame.loc[test_mask]
        if train_frame.empty or test_frame.empty:
            continue
        y_train = train_frame["purchased"].astype(int)
        y_validation = validation_frame["purchased"].astype(int)
        if y_train.nunique() < 2:
            folds.append(
                {
                    "fold": fold_index + 1,
                    "available": False,
                    "reason": "Treino do fold sem as duas classes.",
                    "train_contexts": len(train_ids),
                    "validation_contexts": len(validation_ids),
                    "test_contexts": len(test_ids),
                }
            )
            continue

        model = LGBMClassifier(**MODEL_PARAMS)
        if len(validation_frame) and y_validation.nunique() == 2:
            model.fit(
                train_frame[columns].fillna(0.0).astype(float),
                y_train,
                sample_weight=train_frame["_sample_weight"].astype(float),
                eval_set=[
                    (
                        validation_frame[columns].fillna(0.0).astype(float),
                        y_validation,
                    )
                ],
                callbacks=[early_stopping(30, verbose=False)],
            )
        else:
            model.fit(
                train_frame[columns].fillna(0.0).astype(float),
                y_train,
                sample_weight=train_frame["_sample_weight"].astype(float),
            )

        test_scores = model.predict_proba(
            test_frame[columns].fillna(0.0).astype(float)
        )[:, 1].tolist()
        strategies = _strategy_contexts(test_frame, test_scores, orders)
        ranking = {
            name: compute_ranking_metrics(
                strategies[name],
                catalog_size=resolved_catalog,
                item_attributes=attributes,
            )
            for name in ("model", "popularity", "random")
        }
        predictive = _predictive_metrics(
            test_frame["purchased"].astype(int).tolist(), test_scores
        )
        folds.append(
            {
                "fold": fold_index + 1,
                "available": True,
                "train_contexts": len(train_ids),
                "validation_contexts": len(validation_ids),
                "test_contexts": len(test_ids),
                "test_period": _period(test_frame),
                "ranking": ranking["model"],
                "baselines": {
                    "popularity": ranking["popularity"],
                    "random": ranking["random"],
                },
                "predictive": predictive,
            }
        )

    available_folds = [fold for fold in folds if fold.get("available")]
    summary: dict[str, Any] = {}
    if available_folds:
        for strategy, key in (
            ("lightgbm", "ranking"),
            ("popularity", "baselines"),
            ("random", "baselines"),
        ):
            values: dict[str, list[float]] = {}
            for fold in available_folds:
                ranking = (
                    fold["ranking"]
                    if strategy == "lightgbm"
                    else fold["baselines"][strategy]
                )
                for metric in (
                    "precision_at_k",
                    "recall_at_k",
                    "ndcg_at_k",
                    "map_at_k",
                ):
                    values.setdefault(metric, []).append(float(ranking[metric]))
            summary[strategy] = {
                metric: {
                    "mean": round(mean(series), 4),
                    "std": round(pstdev(series), 4),
                    "min": round(min(series), 4),
                    "max": round(max(series), 4),
                }
                for metric, series in values.items()
            }
        predictive_values: dict[str, list[float]] = {}
        for fold in available_folds:
            predictive = fold["predictive"]
            for metric in ("roc_auc", "pr_auc", "brier_score", "log_loss"):
                value = predictive.get(metric)
                if value is not None:
                    predictive_values.setdefault(metric, []).append(float(value))
        summary["predictive"] = {
            metric: {
                "mean": round(mean(series), 4),
                "std": round(pstdev(series), 4),
            }
            for metric, series in predictive_values.items()
        }

    return {
        "available": bool(available_folds),
        "windows": windows,
        "folds": folds,
        "summary": summary,
        "reason": None
        if available_folds
        else "Nenhum fold pôde ser treinado/avaliado com os dados disponíveis.",
        "note": (
            "Janelas expansíveis: treino em contextos antigos, validação no "
            "bloco anterior ao teste e teste no bloco seguinte. A média entre "
            "janelas não substitui a pior janela; resultados instáveis não "
            "autorizam promoção."
        ),
    }


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
        "tratados como não relevantes; ausência de pedido não é rejeição. "
        f"No treino, negativos não observados recebem peso "
        f"{UNOBSERVED_NEGATIVE_WEIGHT}."
    )
    limitations.append(LABEL_SEMANTICS)
    limitations.append(
        "As métricas de ranking são macro-médias por contexto; contextos sem "
        "item relevante entram como 0."
    )
    if metrics.get("temporal_mode") != "strict":
        limitations.append(
            "Atributos do restaurante (rating, nº de avaliações, frete e tempo "
            "de entrega) vêm do estado atual, não de um snapshot histórico; "
            "pode haver vazamento temporal. Use --strict-temporal para excluí-los."
        )
    limitations.append(
        "A análise de sensibilidade observado/não observado é diagnóstica; a "
        "avaliação principal continua usando o catálogo inteiro."
    )
    if not metrics["roc_auc_available"]:
        limitations.append(
            "ROC AUC não reportada: " + str(metrics["roc_auc_note"])
        )
    production = metrics.get("production") or {}
    if not production.get("available"):
        limitations.append(
            "Modelo em produção não comparável no mesmo teste: "
            + str(production.get("reason") or "motivo não informado")
            + ". Sem essa comparação, a promoção fica bloqueada."
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


def _evaluate_previous_model(
    previous: dict[str, Any] | None,
    frame: pd.DataFrame,
    orders: list[Order] | None = None,
    catalog_size: int | None = None,
    restaurants: Sequence[Restaurant] | None = None,
) -> dict[str, Any]:
    """Avalia o modelo em produção nos **mesmos** contextos/candidatos do teste.

    Sem essa comparação, o candidato poderia ser promovido por superar a
    popularidade mesmo sendo pior que o modelo que já está servindo.
    """
    result: dict[str, Any] = {
        "available": False,
        "reason": None,
        "model_version": previous.get("version") if previous else None,
        "evaluation_split": None,
        "ranking": None,
    }
    if previous is None:
        result["reason"] = "Não havia modelo em produção para comparar."
        return result

    path = Path(str(previous.get("path")))
    try:
        bundle = joblib.load(path)
    except Exception as exc:  # artefato ilegível não impede o treino
        result["reason"] = f"Modelo em produção ilegível: {exc}"
        return result
    if not isinstance(bundle, dict):
        result["reason"] = "Formato do modelo em produção não reconhecido."
        return result

    model = bundle.get("model")
    previous_features = list(bundle.get("feature_names") or [])
    if model is None or not previous_features:
        result["reason"] = "Modelo em produção sem modelo/features utilizáveis."
        return result

    missing = [name for name in previous_features if name not in frame.columns]
    if missing:
        result["reason"] = (
            "Features do modelo em produção ausentes no dataset atual: "
            + ", ".join(missing[:5])
        )
        return result

    _, mask, evaluation_name = _evaluation_selection(frame)
    evaluation_frame = frame.loc[mask]
    if evaluation_frame.empty:
        result["reason"] = "Sem contextos de avaliação para comparar."
        return result

    try:
        scores = model.predict_proba(
            evaluation_frame[previous_features].fillna(0.0).astype(float)
        )[:, 1].tolist()
    except Exception as exc:  # pragma: no cover - proteção defensiva
        result["reason"] = f"Falha ao pontuar o modelo em produção: {exc}"
        return result

    contexts = _strategy_contexts(evaluation_frame, scores, orders)["model"]
    result.update(
        {
            "available": True,
            "evaluation_split": evaluation_name,
            "ranking": compute_ranking_metrics(
                contexts,
                catalog_size=catalog_size
                or int(frame["_restaurant_id"].nunique()),
                item_attributes=_item_attributes(restaurants)
                if restaurants
                else None,
            ),
        }
    )
    return result


def _promotion_decision(
    metrics: dict[str, Any],
    quality: dict[str, Any],
    previous: dict[str, Any] | None,
) -> dict[str, Any]:
    model_ranking = metrics["ranking"]
    baselines = metrics["baselines"]
    production = metrics.get("production") or {}
    production_ranking = (
        production.get("ranking") if production.get("available") else None
    )

    best_ndcg = max(
        baselines["popularity"]["ndcg_at_k"], baselines["random"]["ndcg_at_k"]
    )
    best_map = max(
        baselines["popularity"]["map_at_k"], baselines["random"]["map_at_k"]
    )
    if production_ranking:
        best_ndcg = max(best_ndcg, production_ranking["ndcg_at_k"])
        best_map = max(best_map, production_ranking["map_at_k"])
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
    if production_ranking is None:
        return {
            "decision": "insufficient_evidence",
            "promoted": False,
            "reason": (
                "O modelo em produção não pôde ser avaliado nos mesmos "
                "contextos/candidatos: "
                + str(production.get("reason") or "motivo desconhecido")
            ),
        }

    improved = (
        model_ndcg >= best_ndcg + MIN_PROMOTION_IMPROVEMENT
        or model_map >= best_map + MIN_PROMOTION_IMPROVEMENT
    )
    degraded = (
        model_ndcg < best_ndcg - MAX_PROMOTION_DEGRADATION
        or model_map < best_map - MAX_PROMOTION_DEGRADATION
    )
    if improved and not degraded:
        return {
            "decision": "promoted",
            "promoted": True,
            "reason": (
                "O candidato superou o melhor baseline e o modelo em produção "
                f"em NDCG@K ou MAP@K (margem mínima "
                f"{MIN_PROMOTION_IMPROVEMENT}) sem degradação relevante."
            ),
        }
    return {
        "decision": "kept_previous",
        "promoted": False,
        "reason": (
            "O candidato não superou o melhor baseline/modelo em produção de "
            "forma consistente; o modelo anterior foi preservado para rollback."
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
        for label, count in frame["purchased"].value_counts().sort_index().items()
    }
    return {
        "schema_version": 3,
        "model_version": model_version,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "model": "LightGBM",
        "target": TARGET_COLUMN,
        "label_semantics": metrics["label_semantics"],
        "negative_policy": metrics["negative_policy"],
        "dataset": {
            "hash": dataset_hash,
            "samples": metrics["samples"],
            "users": int(frame["_user_id"].nunique()),
            "contexts": int(frame["_context_id"].nunique()),
            "restaurants": int(frame["_restaurant_id"].nunique()),
            "positives": metrics["positives"],
            "negatives": metrics["negatives"],
            "observed_negatives": metrics["observed_negatives"],
            "unobserved_negatives": metrics["unobserved_negatives"],
            "relevance_distribution": relevance_distribution,
            "period": _period(frame),
            "feature_count": metrics["features"],
        },
        "features": metrics["feature_names"],
        "temporal_mode": metrics.get("temporal_mode"),
        "feature_temporal_policy": metrics.get("feature_temporal_policy"),
        "params": metrics["params"],
        "seed": metrics["seed"],
        "split": metrics["split"],
        "metrics": {
            "roc_auc": metrics["roc_auc"],
            "roc_auc_available": metrics["roc_auc_available"],
            "roc_auc_note": metrics["roc_auc_note"],
            "pr_auc": metrics["pr_auc"],
            "pr_auc_note": metrics.get("pr_auc_note"),
            "brier_score": metrics["brier_score"],
            "log_loss": metrics["log_loss"],
            "calibration": metrics.get("calibration"),
            "calibration_method": metrics.get("calibration_method"),
            "calibrated_predictive": metrics.get("calibrated_predictive"),
            "predictive_notes": metrics.get("predictive_notes") or {},
            "validation_roc_auc": metrics["validation_roc_auc"],
            "test_roc_auc": metrics["test_roc_auc"],
            "evaluation_split": metrics["evaluation_split"],
            "ranking": metrics["ranking"],
            "ranking_sensitivity": metrics.get("ranking_sensitivity"),
        },
        "baselines": metrics["baselines"],
        "production": metrics.get("production"),
        "rolling_window": metrics.get("rolling_window"),
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
    calibrator: Any = None,
    calibration_method: str = "none",
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
            "calibrator": calibrator,
            "calibration_method": calibration_method,
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
    snapshots: list[Any] | None = None,
    strict_temporal: bool = False,
    rolling_window: bool = False,
) -> dict[str, Any] | None:
    frame = build_training_frame(
        users, orders, restaurants, interactions=interactions, snapshots=snapshots
    )
    if frame.empty:
        logger.warning("Dataset vazio; modelo não será treinado.")
        return None

    dataset_hash = _dataset_hash(frame)
    columns = feature_columns(frame)
    try:
        model, metrics, calibrator, calibration_method = _fit_and_evaluate(
            frame,
            orders=orders,
            catalog_size=len(restaurants),
            restaurants=restaurants,
            strict_temporal=strict_temporal,
        )
    except InsufficientTrainingDataError as exc:
        logger.warning("Treino recusado: %s", exc)
        return None

    previous = _previous_model()
    production = _evaluate_previous_model(
        previous,
        frame,
        orders=orders,
        catalog_size=len(restaurants),
        restaurants=restaurants,
    )
    metrics["production"] = production
    if rolling_window:
        metrics["rolling_window"] = rolling_window_evaluation(
            frame,
            orders=orders,
            restaurants=restaurants,
            catalog_size=len(restaurants),
            strict_temporal=strict_temporal,
        )
    else:
        metrics["rolling_window"] = {
            "available": False,
            "reason": "Não solicitada nesta execução (use --rolling-window).",
        }
    if production.get("available") and production.get("ranking"):
        production_ranking = production["ranking"]
        metrics["comparison"].update(
            {
                "ndcg_at_k_delta_vs_production": round(
                    metrics["ranking"]["ndcg_at_k"]
                    - production_ranking["ndcg_at_k"],
                    4,
                ),
                "map_at_k_delta_vs_production": round(
                    metrics["ranking"]["map_at_k"]
                    - production_ranking["map_at_k"],
                    4,
                ),
                "precision_at_k_delta_vs_production": round(
                    metrics["ranking"]["precision_at_k"]
                    - production_ranking["precision_at_k"],
                    4,
                ),
            }
        )

    version = _model_version(source, frame, columns, dataset_hash)
    metadata = {
        **metrics,
        "source": source,
        "model_version": version,
        "dataset_hash": dataset_hash,
    }
    candidate_path = _save_candidate(
        model, columns, metadata, version, calibrator, calibration_method
    )
    quality = _quality_assessment(metrics, metrics["split"]["strategy"])
    if source == "seed" and previous is not None:
        # Seed é dado sintético/demonstrativo. Ele pode inicializar um modelo
        # quando não há artefato, mas nunca deve substituir um modelo treinado
        # com dados reais do banco.
        promotion: dict[str, Any] = {
            "decision": "kept_previous",
            "promoted": False,
            "reason": (
                "Treino com dados de seed é apenas avaliação: o modelo em "
                "produção não é substituído por um modelo treinado em dados "
                "sintéticos. Use --source db para uma decisão de promoção."
            ),
        }
    else:
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
        recommender.save(
            model,
            columns,
            metadata=metadata,
            calibrator=calibrator,
            calibration_method=calibration_method,
        )
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
    list[Any],
]:
    from app.models import RestaurantSnapshot

    users = (await session.execute(select(User))).scalars().all()
    orders = (await session.execute(select(Order))).scalars().all()
    restaurants = (await session.execute(select(Restaurant))).scalars().all()
    interactions = (
        (await session.execute(select(UserRestaurantInteraction))).scalars().all()
    )
    snapshots = (
        (await session.execute(select(RestaurantSnapshot))).scalars().all()
    )
    return (
        list(users),
        list(orders),
        list(restaurants),
        list(interactions),
        list(snapshots),
    )


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


def train_from_seed(
    *, strict_temporal: bool = False, rolling_window: bool = False
) -> dict[str, Any] | None:
    """Treina o LightGBM usando o seed determinístico, sem acessar o banco."""
    users, orders, restaurants = build_seed_entities()
    return _train_and_save(
        source="seed",
        users=users,
        orders=orders,
        restaurants=restaurants,
        strict_temporal=strict_temporal,
        rolling_window=rolling_window,
    )


async def train(
    *, strict_temporal: bool = False, rolling_window: bool = False
) -> dict[str, Any] | None:
    async with AsyncSessionLocal() as session:
        users, orders, restaurants, interactions, snapshots = await load_training_data(
            session
        )

    result = _train_and_save(
        source="database",
        users=users,
        orders=orders,
        restaurants=restaurants,
        interactions=interactions,
        snapshots=snapshots,
        strict_temporal=strict_temporal,
        rolling_window=rolling_window,
    )
    if result is None:
        return None

    # Salva a distribuição de treino (baseline) para cada feature monitorada,
    # usada futuramente pelo monitoramento de drift.
    try:
        from app.services.drift import drift_monitor  # evita import circular

        frame = build_training_frame(
            users, orders, restaurants, interactions=interactions, snapshots=snapshots
        )
        for feature in drift_monitor.feature_names:
            if feature in frame.columns:
                values = frame[feature].dropna().astype(float).tolist()
                await drift_monitor.save_baseline(feature, values)
    except Exception as exc:  # não deve falhar o treino por causa do drift
        logger.warning("Falha ao salvar baseline de drift: %s", exc)

    # Encerra o cliente Redis antes do fechamento do event loop (evita o aviso
    # "Event loop is closed" em redis.asyncio.connection.AbstractConnection).
    try:
        from app.cache.redis_client import close_redis

        await close_redis()
    except Exception as exc:  # noqa: BLE001
        logger.debug("Falha ao encerrar Redis após o treino: %s", exc)

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
    parser.add_argument(
        "--strict-temporal",
        action="store_true",
        help=(
            "Exclui atributos atuais do restaurante (rating, avaliações, frete, "
            "tempo de entrega) para reduzir risco de vazamento temporal."
        ),
    )
    parser.add_argument(
        "--rolling-window",
        action="store_true",
        help="Adiciona avaliação walk-forward com múltiplas janelas temporais.",
    )
    args = parser.parse_args()

    if args.source == "seed":
        result = train_from_seed(
            strict_temporal=args.strict_temporal,
            rolling_window=args.rolling_window,
        )
    else:
        result = asyncio.run(
            train(
                strict_temporal=args.strict_temporal,
                rolling_window=args.rolling_window,
            )
        )

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
