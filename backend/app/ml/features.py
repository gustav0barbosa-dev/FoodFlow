"""Feature engineering compartilhado entre treino e serving."""
from datetime import datetime, timezone
from typing import Any

import pandas as pd

from app.core.constants import APP_TIMEZONE, TURNOS, Turno
from app.models import Order, Restaurant, User

TURNO_MAP: dict[Turno, tuple[int, int]] = {
    "manha": (6, 11),
    "tarde": (12, 17),
    "noite": (18, 23),
    "madrugada": (0, 5),
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
    """Peso exponencial: pedidos recentes contam mais para o medoide do turno."""
    age_days = max((now - _as_utc(created_at)).total_seconds() / 86400, 0.0)
    return max(0.5 ** (age_days / 30.0), 0.01)


def order_turno(order: Order) -> Turno:
    """Turno local (fuso do app) em que o pedido foi feito."""
    return turno_da_hora(_local_hour(order.created_at))


def has_turno_history(orders: list[Order], turno: Turno) -> bool:
    """Indica se o usuário já pediu naquele turno.

    A API só usa o modelo quando há sinal no turno solicitado; caso contrário
    cai no fallback por popularidade (cold start contextual).
    """
    return any(order_turno(order) == turno for order in orders)


def build_user_features(
    orders: list[Order],
    user: User | None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Agrega comportamento do usuário por turno (ticket, frete e medoide).

    O medoide é aproximado por moda ponderada pela recência, conforme a
    documentação (frequência + recência) sem exigir uma feature store externa.
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


def build_candidate_features(
    user_features: dict[str, Any],
    restaurant: Restaurant,
    turno: Turno = "tarde",
) -> dict[str, float]:
    """Monta a linha (usuário, restaurante, turno) usada no treino e no serving."""
    row: dict[str, float] = {
        "total_orders": float(user_features.get("total_orders", 0.0)),
        "has_dietary_preferences": float(
            user_features.get("has_dietary_preferences", 0.0)
        ),
        "restaurant_rating": float(restaurant.average_rating or 0.0),
        "restaurant_review_count": float(restaurant.review_count or 0),
        "restaurant_delivery_fee": float(restaurant.delivery_fee or 0.0),
        "restaurant_delivery_time_avg": float(
            (restaurant.delivery_time_min + restaurant.delivery_time_max) / 2
        ),
    }

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
        top_restaurant = user_features.get(f"{candidate_turno}_top_restaurant")
        row[f"{candidate_turno}_is_top_restaurant"] = (
            1.0 if top_restaurant and str(top_restaurant) == str(restaurant.id) else 0.0
        )

    return row
