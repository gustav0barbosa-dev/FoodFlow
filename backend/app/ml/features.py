from typing import Any
import numpy as np
import pandas as pd
from app.models import Order, Review, User, Restaurant


TURNO_MAP = {
    "manha": (6, 11),
    "tarde": (12, 17),
    "noite": (18, 23),
    "madrugada": (0, 5),
}


def turno_da_hora(hora: int) -> str:
    for turno, (ini, fim) in TURNO_MAP.items():
        if ini <= hora <= fim:
            return turno
    return "tarde"


def build_user_features(orders: list[Order], user: User) -> dict[str, Any]:
    """Gera features do usuário por turno (ticket médio, frete médio, medoides)."""
    features: dict[str, Any] = {
        "total_orders": len(orders),
        "dietary_preferences": user.dietary_preferences or [],
    }
    if not orders:
        return features

    df = pd.DataFrame(
        [
            {
                "turno": turno_da_hora(o.created_at.hour),
                "order_value": float(o.order_value),
                "delivery_fee": float(o.delivery_fee),
                "restaurant_id": str(o.restaurant_id),
            }
            for o in orders
        ]
    )

    for turno in ["manha", "tarde", "noite", "madrugada"]:
        sub = df[df["turno"] == turno]
        if len(sub) > 0:
            features[f"{turno}_avg_value"] = float(sub["order_value"].mean())
            features[f"{turno}_avg_fee"] = float(sub["delivery_fee"].mean())
            features[f"{turno}_count"] = int(len(sub))
            top_rest = sub["restaurant_id"].mode()
            features[f"{turno}_top_restaurant"] = (
                str(top_rest.iloc[0]) if len(top_rest) > 0 else None
            )
        else:
            features[f"{turno}_avg_value"] = 0.0
            features[f"{turno}_avg_fee"] = 0.0
            features[f"{turno}_count"] = 0
            features[f"{turno}_top_restaurant"] = None

    return features
