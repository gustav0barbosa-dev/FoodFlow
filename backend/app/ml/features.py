"""Feature engineering compartilhado entre treino e serving."""
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import pandas as pd

from app.core.constants import APP_TIMEZONE, TURNOS, Turno
from app.models import Order, Restaurant, User, UserRestaurantInteraction

TURNO_MAP: dict[Turno, tuple[int, int]] = {
    "manha": (6, 11),
    "tarde": (12, 17),
    "noite": (18, 23),
    "madrugada": (0, 5),
}

# Pesos explícitos do perfil de preferências. A escala é intencional:
# compra confirmada é o sinal positivo mais forte; favorito sinaliza intenção;
# clique é um sinal positivo fraco; visualização é interesse fraco. Impressão
# é apenas exposição e NÃO soma afinidade (evita viés de exposição). DISMISS é
# tratado como sinal negativo separado, com cautela. Os pedidos reais também
# entram na afinidade de restaurante/categoria/cozinha (ver
# ``build_user_features``), usando o peso de compra.
INTERACTION_WEIGHTS: dict[str, float] = {
    "IMPRESSION": 0.0,
    "VIEW": 0.2,
    "VIEW_DETAILS": 0.4,
    "CLICK": 1.0,
    "FAVORITE": 2.5,
    "PURCHASE": 5.0,
    "DISMISS": 0.0,
}

# Eventos que representam engajamento (excluem a mera exposição).
ENGAGEMENT_TYPES: tuple[str, ...] = (
    "VIEW",
    "VIEW_DETAILS",
    "CLICK",
    "FAVORITE",
    "PURCHASE",
    "DISMISS",
)

INTERACTION_TYPES: tuple[str, ...] = tuple(INTERACTION_WEIGHTS)

# Peso do histórico no ranking final. O modelo continua sendo a base; a
# afinidade só reordena o que o comportamento recente indica como relevante.
AFFINITY_ALPHA = 0.3

# Atributos do restaurante lidos do estado atual da tabela. Eles são úteis,
# mas não têm snapshot histórico: se rating, contagem de avaliações, frete ou
# tempo de entrega mudaram depois do contexto avaliado, o treino pode ver
# informação que não existia em ``until``. O relatório expõe essa política e o
# treino aceita ``strict_temporal`` para excluí-los.
CURRENT_STATE_RESTAURANT_FEATURES: tuple[str, ...] = (
    "restaurant_rating",
    "restaurant_review_count",
    "restaurant_delivery_fee",
    "restaurant_delivery_time_avg",
)

STATIC_RESTAURANT_ATTRIBUTES: tuple[str, ...] = (
    "restaurant_id",
    "restaurant_categories",
    "restaurant_cuisine",
)


def feature_temporal_policy() -> dict[str, Any]:
    """Descreve quais atributos têm risco de vazamento temporal.

    O histórico do usuário é estritamente anterior a ``until``. Já os
    atributos do restaurante vêm do estado atual do objeto ``Restaurant``. Sem
    uma tabela de snapshots, não é possível afirmar que rating/frete/tempo de
    entrega eram os mesmos no passado. O modo ``strict_temporal`` remove essas
    features do modelo; o modo padrão as mantém e registra a limitação.
    """
    return {
        "user_history": "strictly_before_until",
        "static_restaurant_attributes": list(STATIC_RESTAURANT_ATTRIBUTES),
        "current_state_restaurant_features": list(
            CURRENT_STATE_RESTAURANT_FEATURES
        ),
        "risk": (
            "Atributos do restaurante são lidos do estado atual; mudanças "
            "posteriores ao contexto podem vazar informação. Não há snapshots "
            "históricos implementados."
        ),
        "mitigation": (
            "Use strict_temporal=True/--strict-temporal para excluir essas "
            "features da avaliação. A solução definitiva é persistir snapshots "
            "por versão/data do restaurante."
        ),
    }


def turno_da_hora(hora: int) -> Turno:
    for turno, (inicio, fim) in TURNO_MAP.items():
        if inicio <= hora <= fim:
            return turno
    return "tarde"


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _local_hour(value: datetime) -> int:
    return _as_utc(value).astimezone(APP_TIMEZONE).hour


def _recency_weight(created_at: datetime, now: datetime) -> float:
    """Peso exponencial: eventos recentes contam mais para o perfil."""
    age_days = max((now - _as_utc(created_at)).total_seconds() / 86400, 0.0)
    return max(0.5 ** (age_days / 30.0), 0.01)


def order_turno(order: Order) -> Turno:
    """Turno local (fuso do app) em que o pedido foi feito."""
    return turno_da_hora(_local_hour(order.created_at))


def interaction_turno(interaction: UserRestaurantInteraction) -> Turno:
    return turno_da_hora(_local_hour(interaction.created_at))


def has_turno_history(orders: list[Order], turno: Turno) -> bool:
    """Indica se o usuário já pediu naquele turno.

    A API só usa o modelo quando há sinal no turno solicitado; caso contrário
    cai no fallback por popularidade (cold start contextual).
    """
    return any(order_turno(order) == turno for order in orders)


def _normalize_affinity(values: dict[str, float]) -> dict[str, float]:
    if not values:
        return {}
    highest = max(values.values())
    if highest <= 0:
        return {key: 0.0 for key in values}
    return {key: value / highest for key, value in values.items()}


def build_user_features(
    orders: list[Order],
    user: User | None,
    now: datetime | None = None,
    interactions: list[UserRestaurantInteraction] | None = None,
    restaurants: list[Restaurant] | dict[UUID, Restaurant] | None = None,
) -> dict[str, Any]:
    """Agrega comportamento do usuário por turno e por afinidade.

    Mantém as features de pedidos (ticket, frete e medoide) e adiciona o
    histórico de interações: visualizações, cliques, favoritos e compras.
    """
    current_time = now or datetime.now(timezone.utc)
    features: dict[str, Any] = {
        "total_orders": len(orders),
        "has_dietary_preferences": 1.0
        if user and user.dietary_preferences
        else 0.0,
    }

    for turno in TURNOS:
        features[f"{turno}_avg_value"] = 0.0
        features[f"{turno}_avg_fee"] = 0.0
        features[f"{turno}_count"] = 0.0
        features[f"{turno}_top_restaurant"] = None
        features[f"{turno}_interaction_count"] = 0.0
        features[f"{turno}_purchase_count"] = 0.0

    if restaurants is None:
        restaurant_lookup: dict[UUID, Restaurant] = {}
    elif isinstance(restaurants, dict):
        restaurant_lookup = restaurants
    else:
        restaurant_lookup = {restaurant.id: restaurant for restaurant in restaurants}

    interactions = interactions or []
    type_counts: dict[str, int] = defaultdict(int)
    restaurant_counts: dict[str, dict[str, int]] = defaultdict(
        lambda: {
            "total": 0,
            "view": 0,
            "purchase": 0,
            "favorite": 0,
            "impression": 0,
            "dismiss": 0,
        }
    )
    restaurant_scores: dict[str, float] = defaultdict(float)
    category_scores: dict[str, float] = defaultdict(float)
    cuisine_scores: dict[str, float] = defaultdict(float)
    purchase_values: list[float] = []

    for interaction in interactions:
        interaction_type = str(interaction.interaction_type).upper()
        type_counts[interaction_type] += 1
        recency = _recency_weight(interaction.created_at, current_time)
        weight = INTERACTION_WEIGHTS.get(interaction_type, 1.0) * recency

        restaurant_id = str(interaction.restaurant_id)
        counts = restaurant_counts[restaurant_id]
        counts["total"] += 1
        if interaction_type in {"VIEW", "VIEW_DETAILS"}:
            counts["view"] += 1
        elif interaction_type == "PURCHASE":
            counts["purchase"] += 1
        elif interaction_type == "FAVORITE":
            counts["favorite"] += 1
        elif interaction_type == "IMPRESSION":
            counts["impression"] += 1
        elif interaction_type == "DISMISS":
            counts["dismiss"] += 1

        if interaction_type == "DISMISS":
            # Sinal negativo explícito: reduz a afinidade sem zerar o
            # histórico positivo anterior do restaurante.
            restaurant_scores[restaurant_id] -= 1.0 * recency
        else:
            restaurant_scores[restaurant_id] += weight

        turno = interaction_turno(interaction)
        features[f"{turno}_interaction_count"] += 1.0
        if interaction_type == "PURCHASE":
            features[f"{turno}_purchase_count"] += 1.0
            if interaction.purchase_value is not None:
                purchase_values.append(float(interaction.purchase_value))

        restaurant = restaurant_lookup.get(interaction.restaurant_id)
        if restaurant is not None and weight > 0:
            categories = [str(category) for category in restaurant.categories or []]
            for category in categories:
                category_scores[category] += weight / max(len(categories), 1)
            if restaurant.cuisine:
                cuisine_scores[str(restaurant.cuisine)] += weight

    # Pedidos reais são o sinal de consumo mais confiável. Eles entram na
    # afinidade de restaurante, categoria e cozinha com o peso de compra e
    # decaimento temporal. Antes desta correção a afinidade de categoria
    # considerava apenas interações, ignorando o que o usuário realmente pediu.
    for order in orders:
        restaurant = restaurant_lookup.get(order.restaurant_id)
        if restaurant is None:
            continue
        recency = _recency_weight(order.created_at, current_time)
        weight = INTERACTION_WEIGHTS["PURCHASE"] * recency
        restaurant_id = str(order.restaurant_id)
        counts = restaurant_counts[restaurant_id]
        counts["total"] += 1
        counts["purchase"] += 1
        restaurant_scores[restaurant_id] += weight

        categories = [str(category) for category in restaurant.categories or []]
        for category in categories:
            category_scores[category] += weight / max(len(categories), 1)
        if restaurant.cuisine:
            cuisine_scores[str(restaurant.cuisine)] += weight

    views = type_counts.get("VIEW", 0) + type_counts.get("VIEW_DETAILS", 0)
    clicks = type_counts.get("CLICK", 0)
    favorites = type_counts.get("FAVORITE", 0)
    purchases = type_counts.get("PURCHASE", 0)
    impressions = type_counts.get("IMPRESSION", 0)
    dismissals = type_counts.get("DISMISS", 0)
    total_interactions = len(interactions)
    engagement_count = max(total_interactions - impressions, 0)

    features.update(
        {
            "interaction_count": engagement_count,
            "impression_count": impressions,
            "view_count": views,
            "click_count": clicks,
            "favorite_count": favorites,
            "purchase_count": purchases,
            "dismiss_count": dismissals,
            "purchase_ratio": (
                purchases / engagement_count if engagement_count else 0.0
            ),
            "total_spent": sum(purchase_values),
            "avg_purchase_value": (
                sum(purchase_values) / len(purchase_values)
                if purchase_values
                else 0.0
            ),
            "restaurant_affinity": _normalize_affinity(dict(restaurant_scores)),
            "category_affinity": _normalize_affinity(dict(category_scores)),
            "cuisine_affinity": _normalize_affinity(dict(cuisine_scores)),
            "restaurant_interactions": {
                restaurant_id: dict(counts)
                for restaurant_id, counts in restaurant_counts.items()
            },
            "category_interactions": dict(category_scores),
            "cuisine_interactions": dict(cuisine_scores),
        }
    )

    if not orders:
        return features

    frame = pd.DataFrame(
        [
            {
                "turno": order_turno(order),
                "order_value": float(order.order_value or 0.0),
                "delivery_fee": float(order.delivery_fee or 0.0),
                "restaurant_id": str(order.restaurant_id),
                "weight": _recency_weight(order.created_at, current_time),
            }
            for order in orders
        ]
    )

    for turno in TURNOS:
        subset = frame[frame["turno"] == turno]
        if subset.empty:
            continue

        features[f"{turno}_avg_value"] = float(subset["order_value"].mean())
        features[f"{turno}_avg_fee"] = float(subset["delivery_fee"].mean())
        features[f"{turno}_count"] = float(len(subset))

        weighted = subset.groupby("restaurant_id")["weight"].sum()
        features[f"{turno}_top_restaurant"] = str(weighted.idxmax())

    return features


def _category_affinity(
    user_features: dict[str, Any], restaurant: Restaurant
) -> float:
    affinity = user_features.get("category_affinity") or {}
    if not affinity:
        return 0.0
    return max(
        (float(affinity.get(str(category), 0.0)) for category in restaurant.categories or []),
        default=0.0,
    )


def _cuisine_affinity(
    user_features: dict[str, Any], restaurant: Restaurant
) -> float:
    cuisine = getattr(restaurant, "cuisine", None)
    if not cuisine:
        return 0.0
    affinity = user_features.get("cuisine_affinity") or {}
    return float(affinity.get(str(cuisine), 0.0))


def _restaurant_counts(
    user_features: dict[str, Any], restaurant: Restaurant
) -> dict[str, int]:
    interactions = user_features.get("restaurant_interactions") or {}
    return interactions.get(
        str(restaurant.id),
        {
            "total": 0,
            "view": 0,
            "purchase": 0,
            "favorite": 0,
            "impression": 0,
            "dismiss": 0,
        },
    )


def resolve_restaurant_state(
    restaurant: Restaurant,
    snapshots: list[Any] | None = None,
    as_of: datetime | None = None,
) -> dict[str, Any]:
    """Resolve o estado mutável do restaurante em ``as_of``.

    Usa o snapshot válido (``valid_from <= as_of < valid_to``) mais recente;
    se não houver, cai no estado atual do restaurante. O resultado é um dict
    com as chaves ``average_rating``, ``review_count``, ``delivery_fee``,
    ``delivery_time_min`` e ``delivery_time_max``.
    """
    current = {
        "average_rating": getattr(restaurant, "average_rating", 0),
        "review_count": getattr(restaurant, "review_count", 0),
        "delivery_fee": getattr(restaurant, "delivery_fee", 0),
        "delivery_time_min": getattr(restaurant, "delivery_time_min", 20),
        "delivery_time_max": getattr(restaurant, "delivery_time_max", 30),
    }
    if not snapshots or as_of is None:
        return current

    restaurant_id = getattr(restaurant, "id", None)
    candidates = [
        snapshot
        for snapshot in snapshots
        if getattr(snapshot, "restaurant_id", None) == restaurant_id
        or (isinstance(snapshot, dict) and snapshot.get("restaurant_id") == restaurant_id)
    ]
    chosen = None
    for snapshot in candidates:
        valid_from = (
            snapshot.get("valid_from")
            if isinstance(snapshot, dict)
            else getattr(snapshot, "valid_from", None)
        )
        valid_to = (
            snapshot.get("valid_to")
            if isinstance(snapshot, dict)
            else getattr(snapshot, "valid_to", None)
        )
        if valid_from is None:
            continue
        valid_from_utc = _as_utc(valid_from)
        if valid_from_utc > _as_utc(as_of):
            continue
        if valid_to is not None and _as_utc(valid_to) <= _as_utc(as_of):
            continue
        if chosen is None:
            chosen = snapshot
        else:
            chosen_from = (
                chosen.get("valid_from")
                if isinstance(chosen, dict)
                else getattr(chosen, "valid_from", None)
            )
            if _as_utc(valid_from) > _as_utc(chosen_from):
                chosen = snapshot

    if chosen is None:
        return current

    def _get(key: str, default):
        if isinstance(chosen, dict):
            return chosen.get(key, default)
        return getattr(chosen, key, default)

    return {
        "average_rating": _get("average_rating", current["average_rating"]),
        "review_count": _get("review_count", current["review_count"]),
        "delivery_fee": _get("delivery_fee", current["delivery_fee"]),
        "delivery_time_min": _get("delivery_time_min", current["delivery_time_min"]),
        "delivery_time_max": _get("delivery_time_max", current["delivery_time_max"]),
    }


def build_candidate_features(
    user_features: dict[str, Any],
    restaurant: Restaurant,
    turno: Turno = "tarde",
    restaurant_state: dict[str, Any] | None = None,
) -> dict[str, float]:
    """Monta a linha (usuário, restaurante, turno) usada no treino e no serving."""
    state = restaurant_state or resolve_restaurant_state(restaurant, None, None)
    row: dict[str, float] = {
        "total_orders": float(user_features.get("total_orders", 0.0)),
        "has_dietary_preferences": float(
            user_features.get("has_dietary_preferences", 0.0)
        ),
        "restaurant_rating": float(state.get("average_rating", 0.0) or 0.0),
        "restaurant_review_count": float(state.get("review_count", 0) or 0),
        "restaurant_delivery_fee": float(state.get("delivery_fee", 0.0) or 0.0),
        "restaurant_delivery_time_avg": float(
            (
                float(state.get("delivery_time_min", 0) or 0)
                + float(state.get("delivery_time_max", 0) or 0)
            )
            / 2
        ),
        "interaction_count": float(user_features.get("interaction_count", 0.0)),
        "impression_count": float(user_features.get("impression_count", 0.0)),
        "view_count": float(user_features.get("view_count", 0.0)),
        "click_count": float(user_features.get("click_count", 0.0)),
        "favorite_count": float(user_features.get("favorite_count", 0.0)),
        "purchase_count": float(user_features.get("purchase_count", 0.0)),
        "dismiss_count": float(user_features.get("dismiss_count", 0.0)),
        "purchase_ratio": float(user_features.get("purchase_ratio", 0.0)),
        "total_spent": float(user_features.get("total_spent", 0.0)),
        "avg_purchase_value": float(
            user_features.get("avg_purchase_value", 0.0)
        ),
    }

    counts = _restaurant_counts(user_features, restaurant)
    category_affinity = _category_affinity(user_features, restaurant)
    cuisine_affinity = _cuisine_affinity(user_features, restaurant)
    direct_affinity = float(
        (user_features.get("restaurant_affinity") or {}).get(
            str(restaurant.id), 0.0
        )
    )

    row.update(
        {
            "restaurant_interaction_count": float(counts.get("total", 0)),
            "restaurant_view_count": float(counts.get("view", 0)),
            "restaurant_purchase_count": float(counts.get("purchase", 0)),
            "restaurant_impression_count": float(counts.get("impression", 0)),
            "restaurant_dismiss_count": float(counts.get("dismiss", 0)),
            "restaurant_is_favorite": 1.0
            if counts.get("favorite", 0) > 0
            else 0.0,
            "restaurant_category_affinity": category_affinity,
            "restaurant_cuisine_affinity": cuisine_affinity,
            "restaurant_affinity": max(
                direct_affinity,
                0.6 * category_affinity + 0.4 * cuisine_affinity,
            ),
        }
    )

    # One-hot do turno solicitado: permite ao modelo aplicar o contexto certo
    # em vez de aprender um ranking único para todos os horários.
    for candidate_turno in TURNOS:
        row[f"is_{candidate_turno}"] = 1.0 if candidate_turno == turno else 0.0

    for candidate_turno in TURNOS:
        row[f"{candidate_turno}_avg_value"] = float(
            user_features.get(f"{candidate_turno}_avg_value", 0.0)
        )
        row[f"{candidate_turno}_avg_fee"] = float(
            user_features.get(f"{candidate_turno}_avg_fee", 0.0)
        )
        row[f"{candidate_turno}_count"] = float(
            user_features.get(f"{candidate_turno}_count", 0.0)
        )
        row[f"{candidate_turno}_interaction_count"] = float(
            user_features.get(f"{candidate_turno}_interaction_count", 0.0)
        )
        row[f"{candidate_turno}_purchase_count"] = float(
            user_features.get(f"{candidate_turno}_purchase_count", 0.0)
        )
        top_restaurant = user_features.get(f"{candidate_turno}_top_restaurant")
        row[f"{candidate_turno}_is_top_restaurant"] = (
            1.0 if top_restaurant and str(top_restaurant) == str(restaurant.id) else 0.0
        )

    return row


def affinity_scores(
    user_features: dict[str, Any],
    restaurants: list[Restaurant],
) -> dict[str, float]:
    """Afinidade [0, 1] de cada candidato com o histórico do usuário."""
    raw: dict[str, float] = {}
    for restaurant in restaurants:
        counts = _restaurant_counts(user_features, restaurant)
        direct = float(
            (user_features.get("restaurant_affinity") or {}).get(
                str(restaurant.id), 0.0
            )
        )
        affinity = max(
            direct,
            0.6 * _category_affinity(user_features, restaurant)
            + 0.4 * _cuisine_affinity(user_features, restaurant),
        )
        # Um restaurante apenas visualizado ainda recebe um sinal mínimo,
        # menor que o de favorito/compra.
        if affinity == 0.0 and counts.get("total", 0) > 0:
            affinity = min(0.2, 0.05 * counts["total"])
        raw[str(restaurant.id)] = affinity
    return _normalize_affinity(raw)


def blend_with_affinity(
    base_scores: dict[str, float],
    affinity: dict[str, float],
    alpha: float = AFFINITY_ALPHA,
) -> dict[str, float]:
    """Combina o score base com a afinidade do histórico recente.

    A compra pode fazer um restaurante subir no ranking imediatamente, sem
    esperar o próximo treino periódico do LightGBM.
    """
    keys = set(base_scores) | set(affinity)
    if not keys:
        return {}

    combined = {
        key: (1.0 - alpha) * float(base_scores.get(key, 0.0))
        + alpha * float(affinity.get(key, 0.0))
        for key in keys
    }

    lowest = min(combined.values())
    highest = max(combined.values())
    if highest - lowest < 1e-9:
        return {key: 0.5 for key in combined}
    return {
        key: round((value - lowest) / (highest - lowest), 6)
        for key, value in combined.items()
    }
