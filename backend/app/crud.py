from typing import Sequence
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Event, Order, Restaurant, Review, User
from app.schemas import RestaurantSearchParams


def _geography_point(lat: float, lon: float):
    """Ponto geográfico com binds nomeados (sem interpolar valores no SQL)."""
    return text(
        "ST_SetSRID(ST_MakePoint(:point_lon, :point_lat), 4326)::geography"
    ).bindparams(point_lon=lon, point_lat=lat)


def build_search_statement(params: RestaurantSearchParams):
    point = _geography_point(params.lat, params.lon)
    distance = func.ST_Distance(Restaurant.location, point) / 1000.0

    return (
        select(Restaurant, distance.label("distance_km"))
        .where(
            func.ST_DWithin(
                Restaurant.location,
                point,
                params.radius_km * 1000,
            ),
            Restaurant.is_active.is_(True),
        )
        .order_by(distance.asc(), Restaurant.average_rating.desc())
        .limit(params.limit)
        .offset(params.offset)
    )


async def search_restaurants(
    session: AsyncSession,
    params: RestaurantSearchParams,
) -> list[Restaurant]:
    """Busca geoespacial com distância calculada na mesma query (sem N+1)."""
    statement = build_search_statement(params)
    rows = (await session.execute(statement)).all()
    restaurants: list[Restaurant] = []
    for restaurant, distance_km in rows:
        restaurant.distance_km = (
            round(float(distance_km), 2) if distance_km is not None else None
        )
        restaurants.append(restaurant)
    return restaurants


async def get_restaurant(
    session: AsyncSession,
    restaurant_id: UUID,
) -> Restaurant | None:
    result = await session.execute(
        select(Restaurant).where(Restaurant.id == restaurant_id)
    )
    return result.scalars().first()


async def get_restaurant_reviews(
    session: AsyncSession,
    restaurant_id: UUID,
    limit: int = 10,
) -> Sequence[tuple[Review, str]]:
    statement = (
        select(Review, User.name)
        .join(User, User.id == Review.user_id)
        .where(Review.restaurant_id == restaurant_id)
        .order_by(Review.created_at.desc())
        .limit(limit)
    )
    return (await session.execute(statement)).all()


async def get_user(session: AsyncSession, user_id: UUID) -> User | None:
    result = await session.execute(select(User).where(User.id == user_id))
    return result.scalars().first()


async def get_user_orders(session: AsyncSession, user_id: UUID) -> list[Order]:
    result = await session.execute(
        select(Order)
        .where(Order.user_id == user_id)
        .order_by(Order.created_at.desc())
    )
    return list(result.scalars().all())


async def refresh_restaurant_rating(
    session: AsyncSession,
    restaurant: Restaurant,
) -> None:
    average, count = (
        await session.execute(
            select(func.avg(Review.rating), func.count(Review.id)).where(
                Review.restaurant_id == restaurant.id
            )
        )
    ).one()
    restaurant.average_rating = round(float(average or 0), 1)
    restaurant.review_count = int(count or 0)


async def create_review(
    session: AsyncSession,
    restaurant: Restaurant,
    user: User,
    rating: int,
    comment: str | None,
    idempotency_key: str | None,
) -> tuple[Review, bool]:
    """Cria avaliação idempotente e mantém os agregados do restaurante."""
    if idempotency_key:
        existing = (
            await session.execute(
                select(Review).where(Review.idempotency_key == idempotency_key)
            )
        ).scalars().first()
        if existing is not None:
            return existing, False

    review = Review(
        restaurant_id=restaurant.id,
        user_id=user.id,
        rating=rating,
        comment=comment,
        idempotency_key=idempotency_key,
    )
    session.add(review)
    await session.flush()
    await refresh_restaurant_rating(session, restaurant)

    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        if not idempotency_key:
            raise
        existing = (
            await session.execute(
                select(Review).where(Review.idempotency_key == idempotency_key)
            )
        ).scalars().first()
        if existing is None:
            raise
        return existing, False

    await session.refresh(review)
    return review, True


async def get_review(
    session: AsyncSession,
    review_id: UUID,
) -> Review | None:
    result = await session.execute(select(Review).where(Review.id == review_id))
    return result.scalars().first()


async def update_review(
    session: AsyncSession,
    review: Review,
    rating: int,
    comment: str | None,
) -> Review:
    """Atualiza a avaliação e recalcula os agregados do restaurante."""
    restaurant = await get_restaurant(session, review.restaurant_id)
    review.rating = rating
    review.comment = comment
    if restaurant is not None:
        await refresh_restaurant_rating(session, restaurant)

    await session.commit()
    await session.refresh(review)
    return review


async def delete_review(
    session: AsyncSession,
    review: Review,
) -> None:
    """Remove a avaliação e recalcula os agregados do restaurante."""
    restaurant = await get_restaurant(session, review.restaurant_id)
    await session.delete(review)
    await session.flush()
    if restaurant is not None:
        await refresh_restaurant_rating(session, restaurant)

    await session.commit()


async def create_event(
    session: AsyncSession,
    event_type: str,
    payload: dict,
) -> Event:
    event = Event(type=event_type, payload=payload)
    session.add(event)
    await session.commit()
    await session.refresh(event)
    return event
