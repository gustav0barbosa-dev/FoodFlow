"""Registro de interações e perfil de preferências do usuário."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.cache.redis_client import clear_user_scores
from app.ml.features import INTERACTION_WEIGHTS, _recency_weight
from app.models import Restaurant, UserRestaurantInteraction

logger = logging.getLogger(__name__)


class InteractionUserNotFoundError(LookupError):
    pass


class InteractionRestaurantNotFoundError(LookupError):
    pass


class InvalidInteractionTypeError(ValueError):
    pass


class InvalidExperimentGroupError(ValueError):
    pass


async def record_interaction(
    session: AsyncSession,
    *,
    user_id: UUID,
    restaurant_id: UUID,
    interaction_type: str,
    purchase_value: float | None = None,
    idempotency_key: str | None = None,
    experiment_group: str | None = None,
    experiment_mode: str = "experiment",
    experiment_version: str | None = None,
    recommendation_id: str | None = None,
    recommendation_position: int | None = None,
    model_version: str | None = None,
    event_metadata: dict | None = None,
) -> tuple[UserRestaurantInteraction, bool]:
    """Registra o comportamento do usuário e invalida os scores em cache.

    Retorna ``(interação, criada)``. Com ``idempotency_key`` repetida, devolve
    a interação existente sem duplicar compras/impressões.
    """
    normalized_type = str(interaction_type).upper()
    if normalized_type not in INTERACTION_WEIGHTS:
        raise InvalidInteractionTypeError(
            f"Tipo de interação não suportado: {interaction_type}"
        )

    if experiment_group is not None:
        from app.services.experiment import EXPERIMENT_GROUPS

        if experiment_group not in EXPERIMENT_GROUPS:
            raise InvalidExperimentGroupError(
                f"Grupo de experimento inválido: {experiment_group}"
            )

    if experiment_mode not in {"experiment", "demo"}:
        raise InvalidExperimentGroupError(
            f"Modo de experimento inválido: {experiment_mode}"
        )

    user = await crud.get_user(session, user_id)
    if user is None:
        raise InteractionUserNotFoundError("Usuário não encontrado.")

    restaurant = await crud.get_restaurant(session, restaurant_id)
    if restaurant is None:
        raise InteractionRestaurantNotFoundError("Restaurante não encontrado.")

    if normalized_type != "PURCHASE":
        purchase_value = None

    interaction, created = await crud.create_interaction(
        session,
        user=user,
        restaurant=restaurant,
        interaction_type=normalized_type,
        purchase_value=purchase_value,
        idempotency_key=idempotency_key,
        experiment_group=experiment_group,
        experiment_mode=experiment_mode,
        experiment_version=experiment_version,
        recommendation_id=recommendation_id,
        recommendation_position=recommendation_position,
        model_version=model_version,
        event_metadata=event_metadata,
    )

    if created:
        # O cache guarda os scores base; a afinidade é recalculada a cada
        # requisição, mas invalidar garante que novas features de treino
        # também sejam refletidas após um retreino.
        await clear_user_scores(str(user_id))

    return interaction, created


def summarize_preferences(
    user_id: UUID,
    interactions: list[UserRestaurantInteraction],
    restaurants: list[Restaurant],
    now: datetime | None = None,
) -> dict:
    """Deriva o perfil de preferências a partir das interações.

    O perfil não é persistido: é uma leitura determinística do histórico, o
    que evita estados divergentes entre interações e preferências.
    """
    current_time = now or datetime.now(timezone.utc)
    restaurant_lookup = {restaurant.id: restaurant for restaurant in restaurants}

    counts = {
        "IMPRESSION": 0,
        "VIEW": 0,
        "VIEW_DETAILS": 0,
        "CLICK": 0,
        "FAVORITE": 0,
        "PURCHASE": 0,
        "DISMISS": 0,
    }
    category_scores: dict[str, float] = {}
    cuisine_scores: dict[str, float] = {}
    restaurant_scores: dict[UUID, float] = {}
    restaurant_purchases: dict[UUID, int] = {}
    purchase_values: list[float] = []

    for interaction in interactions:
        interaction_type = str(interaction.interaction_type).upper()
        if interaction_type not in counts:
            continue
        counts[interaction_type] += 1

        weight = INTERACTION_WEIGHTS[interaction_type] * _recency_weight(
            interaction.created_at, current_time
        )
        restaurant_scores[interaction.restaurant_id] = (
            restaurant_scores.get(interaction.restaurant_id, 0.0) + weight
        )

        if interaction_type == "PURCHASE":
            restaurant_purchases[interaction.restaurant_id] = (
                restaurant_purchases.get(interaction.restaurant_id, 0) + 1
            )
            if interaction.purchase_value is not None:
                purchase_values.append(float(interaction.purchase_value))

        restaurant = restaurant_lookup.get(interaction.restaurant_id)
        if restaurant is None:
            continue

        categories = [str(category) for category in restaurant.categories or []]
        for category in categories:
            category_scores[category] = (
                category_scores.get(category, 0.0)
                + weight / max(len(categories), 1)
            )
        if restaurant.cuisine:
            cuisine_scores[str(restaurant.cuisine)] = (
                cuisine_scores.get(str(restaurant.cuisine), 0.0) + weight
            )

    def top_items(scores: dict[str, float]) -> list[dict]:
        if not scores:
            return []
        highest = max(scores.values())
        ordered = sorted(scores.items(), key=lambda item: item[1], reverse=True)[:5]
        return [
            {
                "name": name,
                "score": round(value / highest, 4) if highest > 0 else 0.0,
            }
            for name, value in ordered
        ]

    top_restaurants = []
    for restaurant_id, score in sorted(
        restaurant_scores.items(), key=lambda item: item[1], reverse=True
    )[:5]:
        restaurant = restaurant_lookup.get(restaurant_id)
        if restaurant is None:
            continue
        top_restaurants.append(
            {
                "restaurant_id": restaurant_id,
                "name": restaurant.name,
                "score": round(score, 4),
                "purchases": restaurant_purchases.get(restaurant_id, 0),
            }
        )

    purchases = counts["PURCHASE"]
    return {
        "user_id": user_id,
        "total_interactions": len(interactions),
        "views": counts["VIEW"] + counts["VIEW_DETAILS"],
        "clicks": counts["CLICK"],
        "favorites": counts["FAVORITE"],
        "purchases": purchases,
        "impressions": counts["IMPRESSION"],
        "dismissals": counts["DISMISS"],
        "total_spent": round(sum(purchase_values), 2),
        "average_purchase_value": (
            round(sum(purchase_values) / len(purchase_values), 2)
            if purchase_values
            else 0.0
        ),
        "top_categories": top_items(category_scores),
        "top_cuisines": top_items(cuisine_scores),
        "top_restaurants": top_restaurants,
    }


async def get_user_preference_profile(
    session: AsyncSession,
    user_id: UUID,
) -> dict | None:
    user = await crud.get_user(session, user_id)
    if user is None:
        return None

    interactions = await crud.get_user_interactions(session, user_id)
    restaurants = await crud.get_restaurants_by_ids(
        session, {interaction.restaurant_id for interaction in interactions}
    )
    return summarize_preferences(user_id, interactions, restaurants)
