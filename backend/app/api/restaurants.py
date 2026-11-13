from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.database import get_db
from app.integrations.overpass_client import (
    OverpassError,
    OverpassRateLimitError,
    OverpassTimeoutError,
)
from app.schemas import (
    MenuItemOut,
    NearbyCategory,
    NearbyRestaurantsOut,
    RestaurantDetailOut,
    RestaurantOut,
    RestaurantSearchParams,
    ReviewOut,
)
from app.services import restaurant_service

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


@router.get("/nearby", response_model=NearbyRestaurantsOut)
async def nearby_restaurants(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    radius: int = Query(3000, ge=100, le=50000),
    category: NearbyCategory | None = Query(None),
):
    """Descobre restaurantes reais próximos via OpenStreetMap (Overpass).

    Rota separada do catálogo próprio: não consulta o PostGIS nem altera os
    restaurantes do FoodFlow. Os resultados usam o cache Redis antes de uma
    nova consulta à Overpass API.
    """
    try:
        restaurants = await restaurant_service.find_nearby_restaurants(
            lat=lat,
            lon=lon,
            radius=radius,
            category=category.value if category else None,
        )
    except OverpassRateLimitError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except OverpassTimeoutError as exc:
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except OverpassError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return NearbyRestaurantsOut(
        source="OpenStreetMap",
        count=len(restaurants),
        restaurants=restaurants,
    )


@router.get(
    "/osm/{osm_type}/{osm_id}",
    response_model=RestaurantDetailOut,
)
async def get_osm_restaurant(
    osm_type: str,
    osm_id: int,
    refresh: bool = Query(
        False,
        description="Atualiza os dados a partir do OpenStreetMap; "
        "em caso de falha mantém o registro persistido.",
    ),
    session: AsyncSession = Depends(get_db),
):
    """Detalhe de um estabelecimento descoberto no OpenStreetMap.

    O restaurante é persistido na primeira abertura, relacionado pelo par
    ``osm_type`` + ``osm_id``. Campos ausentes no OSM permanecem nulos.
    """
    if osm_type not in restaurant_service.OSM_TYPES:
        raise HTTPException(
            status_code=422,
            detail="Tipo OSM inválido. Use node, way ou relation.",
        )
    if osm_id <= 0:
        raise HTTPException(status_code=422, detail="osm_id deve ser positivo.")

    try:
        restaurant = await restaurant_service.get_osm_restaurant_detail(
            session, osm_type=osm_type, osm_id=osm_id, refresh=refresh
        )
    except restaurant_service.OsmRestaurantNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except OverpassRateLimitError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except OverpassTimeoutError as exc:
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except OverpassError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    payload = RestaurantOut.model_validate(restaurant).model_dump()
    payload["reviews"] = []
    return RestaurantDetailOut(**payload)


@router.get("/{restaurant_id}/menu", response_model=list[MenuItemOut])
async def get_restaurant_menu(
    restaurant_id: UUID,
    session: AsyncSession = Depends(get_db),
):
    """Cardápio do restaurante (lista vazia se ainda não houver itens)."""
    restaurant = await crud.get_restaurant(session, restaurant_id)
    if restaurant is None:
        raise HTTPException(status_code=404, detail="Restaurante não encontrado")
    return await crud.get_menu_items(session, restaurant_id)


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
