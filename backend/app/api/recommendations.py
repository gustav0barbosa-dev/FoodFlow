from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.cache.redis_client import (
    clear_scores,
    get_ab_test_metrics,
    get_scores,
    increment_ab_test_metrics,
    increment_metrics,
    set_scores,
)
from app.core.constants import Turno
from app.database import get_db
from app.ml.features import build_user_features, has_turno_history
from app.ml.reranker import reranker
from app.ml.recommender import popularity_scores, recommender
from app.ml.train import train
from app.schemas import RecommendationOut, RestaurantSearchParams

router = APIRouter(prefix="/recommendations", tags=["recommendations"])

# Grupos do experimento A/B de recomendações.
EXPERIMENT_PERSONALIZED = "personalized"
EXPERIMENT_DISTANCE = "distance"
EXPERIMENT_GROUPS = (EXPERIMENT_PERSONALIZED, EXPERIMENT_DISTANCE)


def _assign_experiment_group(user_id: UUID) -> str:
    """Atribui determinísticamente um usuário a um grupo do A/B test.

    Usa um hash estável do user_id para que o mesmo usuário sempre caia no
    mesmo grupo, sem precisar persistir a atribuição.
    """
    digest = hash(str(user_id)) & 0xFFFFFFFF
    return EXPERIMENT_PERSONALIZED if digest % 2 == 0 else EXPERIMENT_DISTANCE


def _get_experiment_group(
    experiment: str | None, user_id: UUID
) -> str:
    """Resolve o grupo do experimento: parâmetro explícito ou atribuição por hash."""
    if experiment and experiment in EXPERIMENT_GROUPS:
        return experiment
    return _assign_experiment_group(user_id)


@router.get("", response_model=list[RecommendationOut])
async def recommendations(
    user_id: UUID = Query(...),
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    turno: Turno = Query("tarde"),
    experiment: str | None = Query(
        None,
        description="Grupo do experimento A/B: 'personalized' ou 'distance'. "
        "Quando omitido, o usuário é atribuído determinísticamente por hash do user_id.",
    ),
    session: AsyncSession = Depends(get_db),
):
    group = _get_experiment_group(experiment, user_id)
    await increment_ab_test_metrics(group)
    params = RestaurantSearchParams(
        lat=lat,
        lon=lon,
        radius_km=10,
        limit=50,
        offset=0,
    )
    nearby = await crud.search_restaurants(session, params)
    if not nearby:
        return []

    scores = await get_scores(str(user_id), turno)

    # Variável para rastrear qual estratégia foi usada (útil para o drift log)
    strategy_used = "cache_hit"

    if scores is None:
        user = await crud.get_user(session, user_id)
        orders = await crud.get_user_orders(session, user_id) if user else []

        if group == EXPERIMENT_DISTANCE:
            # Grupo controle: ordena por distância (sem modelo de ML).
            sorted_nearby = sorted(
                nearby,
                key=lambda restaurant: (restaurant.distance_km or float("inf")),
            )
            for restaurant in sorted_nearby:
                restaurant.score = round(
                    float(restaurant.distance_km or 0.0), 4
                )
            await increment_metrics(
                "requests",
                "cache_misses",
                "distance_scores",
            )
            strategy_used = "distance"
            scores = {
                str(restaurant.id): 1.0 / (1.0 + float(restaurant.distance_km or 0))
                for restaurant in sorted_nearby
            }
        elif (
            recommender.model is not None
            and orders
            and user is not None
            and has_turno_history(orders, turno)
        ):
            user_features = build_user_features(orders, user)
            lightgbm_scores = recommender.predict_scores(user_features, nearby, turno)
            # Re-ranking com LoRA (ou fallback determinístico).
            scores = reranker.rerank(
                user_features, nearby, lightgbm_scores, turno
            )
            await increment_metrics("requests", "cache_misses", "model_scores")
            strategy_used = "lightgbm+rerank"
        else:
            # Cold start (sem histórico no turno): popularidade documentada.
            scores = popularity_scores(nearby)
            await increment_metrics("requests", "cache_misses", "popularity_scores")
            strategy_used = "popularity"

        await set_scores(str(user_id), turno, scores)
    else:
        await increment_metrics("requests", "cache_hits")

    for restaurant in nearby:
        restaurant.score = round(
            float(scores.get(str(restaurant.id), 0.0)),
            4,
        )

    sorted_recommendations = sorted(
        nearby, key=lambda restaurant: restaurant.score or 0.0, reverse=True
    )

    return sorted_recommendations


@router.post("/train")
async def train_model():
    metrics = await train()
    if metrics is None:
        raise HTTPException(
            status_code=400,
            detail="Dados insuficientes para treino (necessário ao menos 1 pedido por usuário).",
        )
    invalidated = await clear_scores()
    return {"status": "trained", **metrics, "cache_invalidated": invalidated}


@router.post("/train-lora")
async def train_lora_model():
    """Treina o adapter LoRA de re-ranking (ou gera artefato placeholder)."""
    from app.scripts.train_lora import train_lora

    metrics = await train_lora()
    if metrics is None:
        raise HTTPException(
            status_code=400,
            detail="Dados insuficientes para treino do LoRA.",
        )
    return {"status": "trained", **metrics}


@router.post("/rerank")
async def rerank_endpoint(
    user_id: UUID = Query(...),
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    turno: Turno = Query("tarde"),
    session: AsyncSession = Depends(get_db),
):
    """Re-executa o re-ranking (LoRA) sobre os scores já em cache para um usuário/turno."""
    scores = await get_scores(str(user_id), turno)
    if scores is None:
        raise HTTPException(
            status_code=404,
            detail="Nenhum score em cache para este usuário/turno. Chame /recommendations primeiro.",
        )

    user = await crud.get_user(session, user_id)
    orders = await crud.get_user_orders(session, user_id) if user else []
    user_features = build_user_features(orders, user) if user else {}

    nearby = await crud.search_restaurants(
        session,
        RestaurantSearchParams(lat=lat, lon=lon, radius_km=10, limit=50, offset=0),
    )
    if not nearby:
        return []

    adjusted = reranker.rerank(user_features, nearby, scores, turno)

    for restaurant in nearby:
        restaurant.score = round(float(adjusted.get(str(restaurant.id), 0.0)), 4)

    return sorted(
        nearby, key=lambda restaurant: restaurant.score or 0.0, reverse=True
    )