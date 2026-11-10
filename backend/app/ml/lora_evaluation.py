"""Avaliação offline do re-ranker LoRA com split temporal.

O objetivo é responder, com números, se o adapter LoRA melhora o ranking em
relação a baselines simples. A avaliação usa **split temporal**:

- treino: pedidos anteriores ao corte;
- holdout: pedidos recentes, nunca vistos no treino.

Cada contexto é um par (usuário, turno). Os candidatos são todos os
restaurantes; os positivos são os restaurantes pedidos no holdout naquele
contexto. As features do usuário usam apenas o histórico de treino, evitando
vazamento de informação.

Métricas:
- **AUC macro**: média do ROC AUC por contexto (positivo vs. negativos).
- **NDCG@5 macro**: média do NDCG@5 por contexto, com relevância binária.

Estratégias comparadas:
- `popularity`: nota ponderada pelo volume de avaliações (cold start);
- `lightgbm`: classificador binário do recomendador;
- `lora`: adapter LoRA treinado apenas no split de treino;
- `hybrid`: média dos scores normalizados de LightGBM e LoRA.

O seed determinístico tem poucos pedidos (30). Os resultados são um
**sinal inicial**, não uma avaliação estatisticamente robusta; o módulo foi
feito para ser reutilizado com o banco real (`--source db`).
"""

import asyncio
import logging
import math
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable
from uuid import UUID

import pandas as pd
from lightgbm import LGBMClassifier
from sklearn.metrics import roc_auc_score

from app.core.constants import APP_TIMEZONE, Turno
from app.database import AsyncSessionLocal
from app.ml.features import build_candidate_features, build_user_features, order_turno
from app.ml.lora_training import _try_train_with_llm_deps, build_lora_training_frame
from app.ml.recommender import popularity_scores, normalize_scores
from app.ml.reranker import LoRAReranker
from app.ml.train import (
    NEGATIVES_PER_POSITIVE,
    RANDOM_SEED,
    build_seed_entities,
    build_training_frame,
    load_training_data,
)
from app.models import Order, Restaurant, User

logger = logging.getLogger(__name__)

DEFAULT_HOLDOUT_DAYS = 7
NDCG_K = 5
HYBRID_LORA_WEIGHT = 0.5

ScoresByRestaurant = dict[str, float]


@dataclass
class HoldoutContext:
    """Um par (usuário, turno) avaliado no holdout."""

    user: User
    turno: Turno
    positives: set[str]
    candidates: list[Restaurant]
    user_features: dict[str, Any]


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _holdout_contexts(
    users: list[User],
    holdout_orders: list[Order],
    train_orders: list[Order],
    restaurants: list[Restaurant],
    now: datetime,
) -> list[HoldoutContext]:
    """Monta contextos (usuário, turno) a partir dos pedidos de holdout."""
    user_by_id = {user.id: user for user in users}
    restaurant_ids = {restaurant.id for restaurant in restaurants}
    grouped: dict[tuple[UUID, Turno], set[str]] = {}

    for order in holdout_orders:
        if order.user_id not in user_by_id or order.restaurant_id not in restaurant_ids:
            continue
        key = (order.user_id, order_turno(order))
        grouped.setdefault(key, set()).add(str(order.restaurant_id))

    history_by_user: dict[UUID, list[Order]] = {
        user.id: [order for order in train_orders if order.user_id == user.id]
        for user in users
    }

    contexts: list[HoldoutContext] = []
    for (user_id, turno), positives in sorted(
        grouped.items(), key=lambda item: (str(item[0][0]), item[0][1])
    ):
        user = user_by_id[user_id]
        contexts.append(
            HoldoutContext(
                user=user,
                turno=turno,
                positives=positives,
                candidates=restaurants,
                # Apenas histórico de treino: nenhum pedido do holdout entra aqui.
                user_features=build_user_features(
                    history_by_user.get(user_id, []), user, now=now
                ),
            )
        )

    return contexts


def _fit_lightgbm(frame: pd.DataFrame) -> tuple[LGBMClassifier, list[str]]:
    """Treina o LightGBM no split de treino, com os mesmos hiperparâmetros do serving."""
    feature_columns = [column for column in frame.columns if column != "clicked"]
    X = frame[feature_columns].fillna(0.0).astype(float)
    y = frame["clicked"].astype(int)

    model = LGBMClassifier(
        n_estimators=200,
        max_depth=5,
        num_leaves=15,
        learning_rate=0.05,
        min_child_samples=5,
        subsample=0.9,
        colsample_bytree=0.9,
        is_unbalance=True,
        random_state=RANDOM_SEED,
        verbose=-1,
    )
    model.fit(X, y)
    return model, feature_columns


def _lightgbm_scores(
    model: LGBMClassifier,
    feature_columns: list[str],
    context: HoldoutContext,
) -> ScoresByRestaurant:
    rows = [
        build_candidate_features(context.user_features, restaurant, context.turno)
        for restaurant in context.candidates
    ]
    frame = pd.DataFrame(rows).reindex(columns=feature_columns, fill_value=0.0)
    frame = frame.fillna(0.0).astype(float)
    probabilities = model.predict_proba(frame)[:, 1]
    return {
        str(restaurant.id): float(score)
        for restaurant, score in zip(context.candidates, probabilities, strict=True)
    }


def _hybrid_scores(
    lightgbm: ScoresByRestaurant,
    lora: ScoresByRestaurant,
    lora_weight: float = HYBRID_LORA_WEIGHT,
) -> ScoresByRestaurant:
    lightgbm_norm = normalize_scores(lightgbm)
    lora_norm = normalize_scores(lora)
    restaurant_ids = set(lightgbm_norm) | set(lora_norm)
    return {
        restaurant_id: round(
            lora_weight * lora_norm.get(restaurant_id, 0.0)
            + (1.0 - lora_weight) * lightgbm_norm.get(restaurant_id, 0.0),
            6,
        )
        for restaurant_id in restaurant_ids
    }


def _context_labels_and_scores(
    context: HoldoutContext,
    scores: ScoresByRestaurant,
) -> tuple[list[int], list[float]]:
    labels = [
        1 if str(restaurant.id) in context.positives else 0
        for restaurant in context.candidates
    ]
    values = [
        float(scores.get(str(restaurant.id), 0.0))
        for restaurant in context.candidates
    ]
    return labels, values


def ndcg_at_k(labels: list[int], scores: list[float], k: int = NDCG_K) -> float:
    """NDCG@k com relevância binária."""
    if not labels or k <= 0:
        return 0.0

    ranked = sorted(
        range(len(scores)), key=lambda index: scores[index], reverse=True
    )[:k]
    dcg = sum(
        labels[index] / math.log2(rank + 2)
        for rank, index in enumerate(ranked)
    )
    ideal = sorted(labels, reverse=True)[:k]
    idcg = sum(relevance / math.log2(rank + 2) for rank, relevance in enumerate(ideal))
    return dcg / idcg if idcg > 0 else 0.0


def _aggregate(
    contexts: list[HoldoutContext],
    score_fn: Callable[[HoldoutContext], ScoresByRestaurant],
) -> dict[str, Any]:
    aucs: list[float] = []
    ndcgs: list[float] = []

    for context in contexts:
        labels, values = _context_labels_and_scores(context, score_fn(context))
        if len(set(labels)) == 2:
            aucs.append(float(roc_auc_score(labels, values)))
        ndcgs.append(ndcg_at_k(labels, values))

    return {
        "auc": round(sum(aucs) / len(aucs), 4) if aucs else None,
        "ndcg_at_5": round(sum(ndcgs) / len(ndcgs), 4) if ndcgs else None,
        "contexts_evaluated": len(contexts),
        "auc_contexts": len(aucs),
    }


def _train_lora_on_split(
    users: list[User],
    train_orders: list[Order],
    restaurants: list[Restaurant],
    output_dir: Path,
) -> tuple[LoRAReranker | None, dict[str, Any]]:
    """Treina um adapter temporário no split de treino e o carrega para inferência."""
    samples = build_lora_training_frame(users, train_orders, restaurants)
    if not samples:
        return None, {
            "available": False,
            "reason": "Nenhuma amostra LoRA gerada no split de treino.",
            "train_samples": 0,
        }

    metrics = _try_train_with_llm_deps(samples, output_dir=output_dir)
    if metrics is None:
        return None, {
            "available": False,
            "reason": "Dependências de LLM ausentes (torch/transformers/peft).",
            "train_samples": len(samples),
        }

    reranker = LoRAReranker(model_dir=output_dir)
    if not reranker.load():
        return None, {
            "available": False,
            "reason": "Adapter treinado não pôde ser carregado.",
            "train_samples": len(samples),
        }

    return reranker, {"available": True, "train_samples": len(samples), **metrics}


def evaluate_with_entities(
    users: list[User],
    orders: list[Order],
    restaurants: list[Restaurant],
    holdout_days: int = DEFAULT_HOLDOUT_DAYS,
    now: datetime | None = None,
    lora_output_dir: Path | str | None = None,
) -> dict[str, Any]:
    """Avalia popularidade, LightGBM, LoRA e híbrido em um split temporal."""
    if not users or not orders or not restaurants:
        raise ValueError("Dados insuficientes para avaliação.")

    reference = now or datetime.now(APP_TIMEZONE)
    cutoff = (reference - timedelta(days=holdout_days)).astimezone(timezone.utc)

    train_orders = [order for order in orders if _as_utc(order.created_at) < cutoff]
    holdout_orders = [order for order in orders if _as_utc(order.created_at) >= cutoff]

    if not train_orders or not holdout_orders:
        raise ValueError(
            f"Split inválido para holdout_days={holdout_days}: "
            f"{len(train_orders)} pedidos de treino, "
            f"{len(holdout_orders)} de holdout."
        )

    contexts = _holdout_contexts(
        users, holdout_orders, train_orders, restaurants, reference
    )
    if not contexts:
        raise ValueError("Nenhum contexto (usuário, turno) no holdout.")

    frame = build_training_frame(users, train_orders, restaurants)
    if frame.empty or frame["clicked"].nunique() < 2:
        raise ValueError("Split de treino sem positivos e negativos suficientes.")

    lightgbm_model, feature_columns = _fit_lightgbm(frame)

    results: dict[str, Any] = {
        "source": "seed",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "holdout_days": holdout_days,
        "split": {
            "train_orders": len(train_orders),
            "holdout_orders": len(holdout_orders),
            "contexts": len(contexts),
            "candidates_per_context": len(restaurants),
            "training_rows": int(len(frame)),
            "training_positives": int(frame["clicked"].sum()),
            "negatives_per_positive": NEGATIVES_PER_POSITIVE,
        },
        "metrics": {},
        "lora": {},
        "notes": (
            "Seed determinístico pequeno: resultados indicativos, não "
            "estatisticamente robustos. Use --source db para dados reais."
        ),
    }

    results["metrics"]["popularity"] = _aggregate(
        contexts, lambda context: popularity_scores(context.candidates)
    )
    results["metrics"]["lightgbm"] = _aggregate(
        contexts,
        lambda context: _lightgbm_scores(
            lightgbm_model, feature_columns, context
        ),
    )

    with tempfile.TemporaryDirectory(
        prefix="lora_eval_",
        dir=str(lora_output_dir) if lora_output_dir else None,
    ) as tmp:
        reranker, lora_info = _train_lora_on_split(
            users, train_orders, restaurants, Path(tmp)
        )
        results["lora"] = lora_info

        if reranker is not None:
            def _lora(context: HoldoutContext) -> ScoresByRestaurant:
                return reranker.rerank(
                    context.user_features,
                    context.candidates,
                    {},
                    context.turno,
                )

            lora_scores_by_context = {
                id(context): _lora(context) for context in contexts
            }
            results["metrics"]["lora"] = _aggregate(
                contexts, lambda context: lora_scores_by_context[id(context)]
            )
            results["metrics"]["hybrid"] = _aggregate(
                contexts,
                lambda context: _hybrid_scores(
                    _lightgbm_scores(lightgbm_model, feature_columns, context),
                    lora_scores_by_context[id(context)],
                ),
            )

    return results


def evaluate_from_seed(
    holdout_days: int = DEFAULT_HOLDOUT_DAYS,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Avalia o LoRA usando o seed determinístico (sem PostgreSQL/PostGIS)."""
    reference = now or datetime.now(APP_TIMEZONE)
    users, orders, restaurants = build_seed_entities(now=reference)
    result = evaluate_with_entities(
        users, orders, restaurants, holdout_days=holdout_days, now=reference
    )
    result["source"] = "seed"
    return result


async def evaluate_from_db(
    holdout_days: int = DEFAULT_HOLDOUT_DAYS,
) -> dict[str, Any]:
    """Avalia o LoRA usando os pedidos do PostgreSQL."""
    async with AsyncSessionLocal() as session:
        users, orders, restaurants = await load_training_data(session)

    result = evaluate_with_entities(
        users, orders, restaurants, holdout_days=holdout_days
    )
    result["source"] = "db"
    return result


def evaluate(
    source: str = "seed",
    holdout_days: int = DEFAULT_HOLDOUT_DAYS,
) -> dict[str, Any]:
    """Ponto de entrada único para a CLI."""
    if source == "db":
        return asyncio.run(evaluate_from_db(holdout_days=holdout_days))
    return evaluate_from_seed(holdout_days=holdout_days)
