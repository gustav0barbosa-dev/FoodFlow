"""Constantes compartilhadas entre API, features e coleta de eventos."""
from datetime import timedelta, timezone
from typing import Literal

# Brasil não observa horário de verão desde 2019; offset fixo evita depender de tzdata.
APP_TIMEZONE = timezone(timedelta(hours=-3))

Turno = Literal["manha", "tarde", "noite", "madrugada"]

TURNOS: tuple[Turno, ...] = ("manha", "tarde", "noite", "madrugada")

EventType = Literal[
    "restaurant_card_clicked",
    "restaurant_opened",
    "add_to_cart",
    "order_completed",
    "preferences_updated",
    "search_performed",
    "favorite_toggled",
    "order_status_updated",
    "review_submitted",
]

EVENT_TYPES: tuple[EventType, ...] = (
    "restaurant_card_clicked",
    "restaurant_opened",
    "add_to_cart",
    "order_completed",
    "preferences_updated",
    "search_performed",
    "favorite_toggled",
    "order_status_updated",
    "review_submitted",
)
