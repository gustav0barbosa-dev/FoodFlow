from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.database import get_db
from app.schemas import (
    RestaurantDetailOut,
    RestaurantOut,
    RestaurantSearchParams,
    ReviewOut,
)

router = APIRouter(prefix="/restaurants", tags=["restaurants"])


@router.get("/search", response_model=list[RestaurantOut])
async def search_restaurants(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    radius_km: float = Query(5, gt=0, le=50),
    limit: int = Query(20, gt=0, le=100),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db),
):
    params = RestaurantSearchParams(
        lat=lat,
        lon=lon,
        radius_km=radius_km,
        limit=limit,
        offset=offset,
    )
    return await crud.search_restaurants(session, params)


@router.get("/{restaurant_id}", response_model=RestaurantDetailOut)
async def get_restaurant(
    restaurant_id: UUID,
    session: AsyncSession = Depends(get_db),
):
    restaurant = await crud.get_restaurant(session, restaurant_id)
    if restaurant is None:
        raise HTTPException(status_code=404, detail="Restaurante não encontrado")

    reviews = await crud.get_restaurant_reviews(session, restaurant_id)
    payload = RestaurantOut.model_validate(restaurant).model_dump()
    payload["reviews"] = [
        ReviewOut.model_validate(review).model_copy(
            update={"user_name": user_name}
        )
        for review, user_name in reviews
    ]
    return RestaurantDetailOut(**payload)
