from typing import Sequence
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import Restaurant
from app.schemas import RestaurantOut, RestaurantSearchParams
from app import crud

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
        lat=lat, lon=lon, radius_km=radius_km, limit=limit, offset=offset
    )
    restaurants = await crud.search_restaurants(session, params)
    return restaurants


@router.get("/{restaurant_id}", response_model=RestaurantOut)
async def get_restaurant(
    restaurant_id: str,
    session: AsyncSession = Depends(get_db),
):
    try:
        uid = UUID(restaurant_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="ID inválido")

    restaurant = await crud.get_restaurant(session, uid)
    if not restaurant:
        raise HTTPException(status_code=404, detail="Restaurante não encontrado")
    return restaurant
