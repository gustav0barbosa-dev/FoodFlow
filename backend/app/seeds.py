"""Seed idempotente do catálogo, usuários, pedidos e avaliações."""
import uuid
from datetime import datetime, timedelta, timezone

from geoalchemy2 import WKTElement
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import refresh_restaurant_rating
from app.models import Order, Restaurant, Review, User
from app.seed_data import (
    REVIEWERS,
    REVIEW_COMMENTS,
    SAO_PAULO,
    SEED_NAMESPACE,
    SEED_ORDERS,
    SEED_RESTAURANTS,
    SEED_USERS,
)


def stable_id(value: str) -> uuid.UUID:
    return uuid.uuid5(SEED_NAMESPACE, value)


async def seed_restaurants(session: AsyncSession) -> dict[str, Restaurant]:
    restaurants: dict[str, Restaurant] = {}
    for data in SEED_RESTAURANTS:
        existing = (
            await session.execute(
                select(Restaurant).where(Restaurant.name == data["name"])
            )
        ).scalars().first()
        if existing is not None:
            restaurants[data["name"]] = existing
            continue

        restaurant = Restaurant(
            id=stable_id(f"restaurant:{data['name']}"),
            name=data["name"],
            description=f"Melhor {data['category'].lower()} de Osasco",
            phone="+55 11 99999-0000",
            address=data["address"],
            location=WKTElement(
                f"POINT({data['lon']} {data['lat']})",
                srid=4326,
            ),
            categories=[data["category"]],
            delivery_fee=data["delivery_fee"],
            delivery_time_min=data["delivery_time_min"],
            delivery_time_max=data["delivery_time_max"],
            average_rating=data["rating"],
            review_count=data["review_count"],
            image_url=data["image_url"],
        )
        session.add(restaurant)
        await session.flush()
        restaurants[data["name"]] = restaurant

    await session.commit()
    return restaurants


async def seed_users(session: AsyncSession) -> dict[str, User]:
    users: dict[str, User] = {}
    for data in SEED_USERS:
        existing = (
            await session.execute(select(User).where(User.email == data["email"]))
        ).scalars().first()
        if existing is not None:
            users[data["email"]] = existing
            continue

        user = User(
            id=stable_id(f"user:{data['email']}"),
            name=data["name"],
            email=data["email"],
            dietary_preferences=data["dietary_preferences"],
        )
        session.add(user)
        users[data["email"]] = user

    await session.commit()
    return users


async def seed_orders(
    session: AsyncSession,
    users: dict[str, User],
    restaurants: dict[str, Restaurant],
) -> int:
    created = 0
    local_now = datetime.now(SAO_PAULO)
    menu_by_name = {
        item["name"]: item["menu_item"] for item in SEED_RESTAURANTS
    }

    for index, (email, restaurant_name, days_ago, hour, quantity) in enumerate(
        SEED_ORDERS
    ):
        order_id = stable_id(f"order:{index}")
        if await session.get(Order, order_id) is not None:
            continue

        user = users.get(email)
        restaurant = restaurants.get(restaurant_name)
        menu_item = menu_by_name.get(restaurant_name)
        if user is None or restaurant is None or menu_item is None:
            continue
        created_at = (local_now - timedelta(days=days_ago)).replace(
            hour=hour,
            minute=0,
            second=0,
            microsecond=0,
        )

        session.add(
            Order(
                id=order_id,
                user_id=user.id,
                restaurant_id=restaurant.id,
                items=[
                    {
                        "id": menu_item["id"],
                        "name": menu_item["name"],
                        "quantity": quantity,
                        "price": menu_item["price"],
                    }
                ],
                order_value=round(menu_item["price"] * quantity, 2),
                delivery_fee=float(restaurant.delivery_fee),
                status="Entregue",
                created_at=created_at.astimezone(timezone.utc),
            )
        )
        created += 1

    await session.commit()
    return created


async def seed_reviews(
    session: AsyncSession,
    users: dict[str, User],
    restaurants: dict[str, Restaurant],
) -> int:
    created = 0

    for restaurant_index, (restaurant_name, comments) in enumerate(
        REVIEW_COMMENTS.items()
    ):
        restaurant = restaurants.get(restaurant_name)
        if restaurant is None:
            continue

        for review_index, comment in enumerate(comments[:3]):
            review_id = stable_id(
                f"review:{restaurant_name}:{review_index}"
            )
            if await session.get(Review, review_id) is not None:
                continue

            email = REVIEWERS[
                (restaurant_index + review_index) % len(REVIEWERS)
            ]
            user = users.get(email)
            if user is None:
                continue

            session.add(
                Review(
                    id=review_id,
                    restaurant_id=restaurant.id,
                    user_id=user.id,
                    rating=(5, 4, 5)[(restaurant_index + review_index) % 3],
                    comment=comment,
                )
            )
            created += 1

    await session.commit()
    return created


async def refresh_all_ratings(
    session: AsyncSession,
    restaurants: dict[str, Restaurant],
) -> None:
    for restaurant in restaurants.values():
        await refresh_restaurant_rating(session, restaurant)
    await session.commit()


async def seed_database(session: AsyncSession) -> dict[str, int]:
    restaurants = await seed_restaurants(session)
    users = await seed_users(session)
    orders = await seed_orders(session, users, restaurants)
    reviews = await seed_reviews(session, users, restaurants)
    await refresh_all_ratings(session, restaurants)

    return {
        "restaurants": len(restaurants),
        "users": len(users),
        "orders_created": orders,
        "reviews_created": reviews,
    }
