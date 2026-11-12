from typing import Sequence
from uuid import UUID

from geoalchemy2 import Geometry
from sqlalchemy import cast, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Event,
    Order,
    Restaurant,
    Review,
    User,
    UserRestaurantInteraction,
)
from app.schemas import RestaurantSearchParams


def _coordinate_columns():
    """Extrai latitude/longitude do ponto PostGIS ``location``.

    O catálogo próprio guarda apenas a geografia; os campos ``latitude`` e
    ``longitude`` existem para registros do OSM. Calculamos as coordenadas na
    própria query para que ambos os formatos exponham o mesmo contrato.
    """
    point = cast(Restaurant.location, Geometry("POINT", srid=4326))
    return (
        func.ST_Y(point).label("location_latitude"),
        func.ST_X(point).label("location_longitude"),
    )


def _apply_coordinates(
    restaurant: Restaurant,
    latitude: float | None,
    longitude: float | None,
) -> None:
    if restaurant.latitude is None and latitude is not None:
        restaurant.latitude = float(latitude)
    if restaurant.longitude is None and longitude is not None:
        restaurant.longitude = float(longitude)



def _geography_point(lat: float, lon: float):
    """Ponto geográfico com binds nomeados (sem interpolar valores no SQL)."""
    return text(
        "ST_SetSRID(ST_MakePoint(:point_lon, :point_lat), 4326)::geography"
    ).bindparams(point_lon=lon, point_lat=lat)


def build_search_statement(params: RestaurantSearchParams):
    point = _geography_point(params.lat, params.lon)
    distance = func.ST_Distance(Restaurant.location, point) / 1000.0

    return (
        select(Restaurant, distance.label("distance_km"), *_coordinate_columns())
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
    for restaurant, distance_km, latitude, longitude in rows:
        restaurant.distance_km = (
            round(float(distance_km), 2) if distance_km is not None else None
        )
        _apply_coordinates(restaurant, latitude, longitude)
        restaurants.append(restaurant)
    return restaurants


async def get_restaurant(
    session: AsyncSession,
    restaurant_id: UUID,
) -> Restaurant | None:
    row = (
        await session.execute(
            select(Restaurant, *_coordinate_columns()).where(
                Restaurant.id == restaurant_id
            )
        )
    ).first()
    if row is None:
        return None
    restaurant = row[0]
    _apply_coordinates(restaurant, row[1], row[2])
    return restaurant


async def get_restaurant_by_osm(
    session: AsyncSession,
    osm_type: str,
    osm_id: int,
) -> Restaurant | None:
    row = (
        await session.execute(
            select(Restaurant, *_coordinate_columns()).where(
                Restaurant.osm_type == osm_type,
                Restaurant.osm_id == osm_id,
            )
        )
    ).first()
    if row is None:
        return None
    restaurant = row[0]
    _apply_coordinates(restaurant, row[1], row[2])
    return restaurant


async def get_restaurants_by_ids(
    session: AsyncSession,
    restaurant_ids: set[UUID] | list[UUID],
) -> list[Restaurant]:
    if not restaurant_ids:
        return []
    rows = (
        await session.execute(
            select(Restaurant, *_coordinate_columns()).where(
                Restaurant.id.in_(restaurant_ids)
            )
        )
    ).all()
    restaurants: list[Restaurant] = []
    for restaurant, latitude, longitude in rows:
        _apply_coordinates(restaurant, latitude, longitude)
        restaurants.append(restaurant)
    return restaurants


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


async def get_user_interactions(
    session: AsyncSession,
    user_id: UUID,
    limit: int | None = None,
) -> list[UserRestaurantInteraction]:
    statement = (
        select(UserRestaurantInteraction)
        .where(UserRestaurantInteraction.user_id == user_id)
        .order_by(UserRestaurantInteraction.created_at.desc())
    )
    if limit is not None:
        statement = statement.limit(limit)
    result = await session.execute(statement)
    return list(result.scalars().all())


async def create_interaction(
    session: AsyncSession,
    user: User,
    restaurant: Restaurant,
    interaction_type: str,
    purchase_value: float | None,
    idempotency_key: str | None,
    experiment_group: str | None = None,
    experiment_mode: str = "experiment",
    experiment_version: str | None = None,
    recommendation_id: str | None = None,
    recommendation_position: int | None = None,
    model_version: str | None = None,
    event_metadata: dict | None = None,
) -> tuple[UserRestaurantInteraction, bool]:
    """Registra uma interação, com idempotência opcional para compras."""
    if idempotency_key:
        existing = (
            await session.execute(
                select(UserRestaurantInteraction).where(
                    UserRestaurantInteraction.idempotency_key == idempotency_key
                )
            )
        ).scalars().first()
        if existing is not None:
            return existing, False

    interaction = UserRestaurantInteraction(
        user_id=user.id,
        restaurant_id=restaurant.id,
        interaction_type=interaction_type,
        purchase_value=purchase_value,
        idempotency_key=idempotency_key,
        experiment_group=experiment_group,
        experiment_mode=experiment_mode,
        experiment_version=experiment_version,
        recommendation_id=recommendation_id,
        recommendation_position=recommendation_position,
        model_version=model_version,
        event_metadata=event_metadata or {},
    )
    session.add(interaction)

    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        if not idempotency_key:
            raise
        existing = (
            await session.execute(
                select(UserRestaurantInteraction).where(
                    UserRestaurantInteraction.idempotency_key == idempotency_key
                )
            )
        ).scalars().first()
        if existing is None:
            raise
        return existing, False

    await session.refresh(interaction)
    return interaction, True


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
