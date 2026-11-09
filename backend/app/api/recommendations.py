from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.cache.redis_client import (
    clear_scores,
    get_scores,
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


@router.get("", response_model=list[RecommendationOut])
async def recommendations(
    user_id: UUID = Query(...),
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    turno: Turno = Query("tarde"),
    session: AsyncSession = Depends(get_db),
):
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

        if (
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