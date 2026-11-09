from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
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
from app.ml.recommender import popularity_scores, recommender
from app.ml.train import train
from app.models import RecommendationLog
from app.schemas import RecommendationOut, RestaurantSearchParams
from app.services.drift import FEATURE_NAMES

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@router.get("", response_model=list[RecommendationOut])
async def recommendations(
    background_tasks: BackgroundTasks,
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
            scores = recommender.predict_scores(user_features, nearby, turno)
            await increment_metrics("requests", "cache_misses", "model_scores")
            strategy_used = "lightgbm"
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