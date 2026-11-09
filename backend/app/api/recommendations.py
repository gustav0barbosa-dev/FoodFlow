from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.cache.redis_client import clear_scores, get_scores, set_scores
from app.core.constants import Turno
from app.database import get_db
from app.ml.features import build_user_features
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
    if scores is None:
        user = await crud.get_user(session, user_id)
        orders = await crud.get_user_orders(session, user_id) if user else []

        if recommender.model is not None and orders and user is not None:
            user_features = build_user_features(orders, user)
            scores = recommender.predict_scores(user_features, nearby)
        else:
            # Cold start: popularidade como fallback documentado.
            scores = popularity_scores(nearby)

        await set_scores(str(user_id), turno, scores)

    for restaurant in nearby:
        restaurant.score = round(
            float(scores.get(str(restaurant.id), 0.0)),
            4,
        )

    return sorted(nearby, key=lambda restaurant: restaurant.score or 0.0, reverse=True)


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
