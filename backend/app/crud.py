from typing import Sequence, Any
from uuid import UUID
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Restaurant, Event
from app.schemas import RestaurantSearchParams


async def search_restaurants(
    session: AsyncSession,
    params: RestaurantSearchParams,
) -> Sequence[Restaurant]:
    distance_m = params.radius_km * 1000
    point = text(
        f"ST_SetSRID(ST_MakePoint({params.lon}, {params.lat}), 4326)::geography"
    )

    distance_expr = func.ST_Distance(
        Restaurant.location,
        text(f"ST_SetSRID(ST_MakePoint({params.lon}, {params.lat}), 4326)::geography"),
    ) / 1000

    stmt = (
        select(Restaurant)
        .where(
            func.ST_DWithin(Restaurant.location, point, distance_m),
            Restaurant.is_active.is_(True),
        )
        .order_by(distance_expr.asc())
        .limit(params.limit)
        .offset(params.offset)
    )

    result = await session.execute(stmt)
    restaurants = result.scalars().all()

    for r in restaurants:
        dist = await session.scalar(
            select(distance_expr).where(Restaurant.id == r.id)
        )
        r.distance_km = round(float(dist), 2) if dist is not None else None

    return restaurants


async def get_restaurant(session: AsyncSession, restaurant_id: UUID) -> Restaurant | None:
    result = await session.execute(
        select(Restaurant).where(Restaurant.id == restaurant_id)
    )
    return result.scalars().first()


async def create_event(session: AsyncSession, event_type: str, payload: dict) -> Event:
    event = Event(type=event_type, payload=payload)
    session.add(event)
    await session.commit()
    await session.refresh(event)
    return event
