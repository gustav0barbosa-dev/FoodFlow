from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import Restaurant, Order, User
from app.ml.recommender import recommender
from app.cache.redis_client import get_scores, set_scores
from app.crud import search_restaurants
from app.schemas import RestaurantSearchParams
from uuid import UUID

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@router.get("")
async def recommendations(
    user_id: str = Query(...),
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    turno: str = Query("tarde"),
    session: AsyncSession = Depends(get_db),
):
    try:
        uid = UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="user_id inválido")

    # 1. Tenta scores do Redis (cache)
    scores = await get_scores(str(uid), turno)

    # 2. Busca restaurantes próximos (raio 10km como base)
    params = RestaurantSearchParams(lat=lat, lon=lon, radius_km=10, limit=50, offset=0)
    nearby = await search_restaurants(session, params)

    if not nearby:
        return []

    restaurant_ids = [str(r.id) for r in nearby]

    # 3. Se não há scores em cache, usa fallback por popularidade ou modelo
    if scores is None:
        if recommender.model is not None:
            result = await session.execute(select(User).where(User.id == uid))
            user = result.scalars().first()
            orders = (
                await session.execute(select(Order).where(Order.user_id == uid))
            ).scalars().all()
            from app.ml.features import build_user_features

            user_features = build_user_features(orders, user) if user else {}
            scores = recommender.predict_scores(user_features, restaurant_ids)
            await set_scores(str(uid), turno, scores)
        else:
            # Fallback: ordenar por avaliação (popularidade)
            ranked = sorted(
                nearby, key=lambda r: (r.average_rating, r.review_count), reverse=True
            )
            scores = {str(r.id): float(r.average_rating) / 5.0 for r in ranked}
    else:
        # Se há cache mas o modelo foi carregado, recalcula para consistência
        if recommender.model is not None:
            from app.ml.features import build_user_features

            result = await session.execute(select(User).where(User.id == uid))
            user = result.scalars().first()
            orders = (
                await session.execute(select(Order).where(Order.user_id == uid))
            ).scalars().all()
            user_features = build_user_features(orders, user) if user else {}
            scores = recommender.predict_scores(user_features, restaurant_ids)
            await set_scores(str(uid), turno, scores)

    # 4. Reordena os restaurantes próximos pelos scores
    score_map = {str(r.id): scores.get(str(r.id), 0.0) for r in nearby}
    ranked = sorted(nearby, key=lambda r: score_map.get(str(r.id), 0.0), reverse=True)

    return ranked


@router.post("/train")
async def train_model():
    from app.ml.train import train

    await train()
    return {"status": "training_done"}
