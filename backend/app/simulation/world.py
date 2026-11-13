"""Carrega o catálogo do banco como ``SimRestaurant`` e cria usuários simulados."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from statistics import mean

from geoalchemy2 import Geometry
from sqlalchemy import cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import MenuItem, Restaurant, User
from app.simulation.behavior import (
    SimMenuItem,
    SimRestaurant,
    latent_quality,
)
from app.simulation.menu_catalog import archetype_for
from app.simulation.personas import SimUser

SIM_EMAIL_DOMAIN = "sim.foodflow.dev"


@dataclass
class World:
    restaurants: list[SimRestaurant]
    by_id: dict[str, SimRestaurant]
    skipped_without_menu: int = 0

    @property
    def center(self) -> tuple[float, float]:
        return (
            mean(r.lat for r in self.restaurants),
            mean(r.lon for r in self.restaurants),
        )


async def load_world(session: AsyncSession) -> World:
    """Restaurantes ativos que têm cardápio (sem cardápio não há pedido)."""
    point = cast(Restaurant.location, Geometry("POINT", srid=4326))
    rows = (
        await session.execute(
            select(Restaurant, func.ST_Y(point), func.ST_X(point)).where(
                Restaurant.is_active.is_(True)
            )
        )
    ).all()
    menu_rows = (
        (await session.execute(select(MenuItem).where(MenuItem.is_available.is_(True))))
        .scalars()
        .all()
    )
    menus: dict[uuid.UUID, list[SimMenuItem]] = {}
    for item in menu_rows:
        menus.setdefault(item.restaurant_id, []).append(
            SimMenuItem(
                id=str(item.id),
                name=item.name,
                price=float(item.price),
                dietary_tags=frozenset(item.dietary_tags or []),
            )
        )

    mean_price = {rid: mean(m.price for m in items) for rid, items in menus.items()}
    global_mean = mean(mean_price.values()) if mean_price else 1.0

    restaurants: list[SimRestaurant] = []
    skipped = 0
    for restaurant, lat, lon in rows:
        items = menus.get(restaurant.id)
        if not items or lat is None or lon is None:
            skipped += 1
            continue
        rid = str(restaurant.id)
        restaurants.append(
            SimRestaurant(
                id=rid,
                name=restaurant.name,
                archetype=archetype_for(
                    list(restaurant.categories or []), restaurant.cuisine, restaurant.name
                ),
                lat=float(lat),
                lon=float(lon),
                delivery_fee=float(restaurant.delivery_fee or 0),
                rating=float(restaurant.average_rating or 0),
                review_count=int(restaurant.review_count or 0),
                price_index=mean_price[restaurant.id] / global_mean,
                quality=latent_quality(rid),
                dietary_tags=frozenset(restaurant.dietary_tags or []),
                menu=tuple(items),
            )
        )
    return World(restaurants, {r.id: r for r in restaurants}, skipped)


def sim_email(run_id: str, index: int) -> str:
    return f"sim-{run_id}-{index:04d}@{SIM_EMAIL_DOMAIN}"


async def create_sim_users(
    session: AsyncSession,
    run_id: str,
    users: list[SimUser],
    created_at: dict[int, datetime] | None = None,
) -> dict[int, uuid.UUID]:
    """Cria os usuários simulados (idempotente por e-mail) e devolve index->id."""
    ids: dict[int, uuid.UUID] = {}
    for user in users:
        email = sim_email(run_id, user.index)
        existing = (
            await session.execute(select(User).where(User.email == email))
        ).scalars().first()
        if existing is not None:
            ids[user.index] = existing.id
            continue
        row = User(
            id=uuid.uuid5(uuid.NAMESPACE_URL, email),
            name=f"Sim {user.persona.label} {user.index}",
            email=email,
            dietary_preferences=list(user.dietary),
        )
        if created_at and user.index in created_at:
            row.created_at = created_at[user.index]
        session.add(row)
        ids[user.index] = row.id
    await session.commit()
    return ids
