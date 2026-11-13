"""Personas: perfis latentes de preferência dos usuários simulados."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

TURNOS = ("manha", "tarde", "noite", "madrugada")


@dataclass(frozen=True)
class Persona:
    key: str
    label: str
    share: float  # participação na população
    affinity: dict[str, float]  # arquétipo -> afinidade em [0, 1]
    turno_boost: dict[str, dict[str, float]]  # turno -> arquétipo -> bônus
    price_sensitivity: float
    distance_sensitivity: float
    fee_sensitivity: float
    quality_weight: float
    dietary: tuple[str, ...] = ()
    sessions_per_day: float = 1.0
    turno_activity: dict[str, float] = field(
        default_factory=lambda: {"manha": 0.2, "tarde": 0.35, "noite": 0.4, "madrugada": 0.05}
    )


PERSONAS: tuple[Persona, ...] = (
    Persona(
        "executivo_almoco", "Executivo de almoço", 0.22,
        {"brasileira": 0.8, "saudavel": 0.6, "churrasco": 0.5, "lanches": 0.3},
        {"tarde": {"brasileira": 0.8, "saudavel": 0.4}},
        0.4, 0.8, 0.5, 0.6, (), 1.1,
        {"manha": 0.1, "tarde": 0.7, "noite": 0.18, "madrugada": 0.02},
    ),
    Persona(
        "familia_pizza", "Família de fim de noite", 0.2,
        {"pizza": 0.9, "hamburguer": 0.6, "italiana": 0.5, "arabe": 0.3},
        {"noite": {"pizza": 0.9, "hamburguer": 0.5}},
        0.5, 0.4, 0.6, 0.5, (), 0.8,
        {"manha": 0.05, "tarde": 0.15, "noite": 0.75, "madrugada": 0.05},
    ),
    Persona(
        "fit_vegetariana", "Fit / vegetariana", 0.15,
        {"saudavel": 0.95, "japonesa": 0.5, "arabe": 0.5, "cafe": 0.4},
        {"manha": {"cafe": 0.6, "saudavel": 0.4}, "tarde": {"saudavel": 0.6}},
        0.3, 0.6, 0.4, 0.9, ("Vegetariano",), 1.0,
        {"manha": 0.3, "tarde": 0.45, "noite": 0.25, "madrugada": 0.0},
    ),
    Persona(
        "noturno_lanche", "Noturno de lanche", 0.15,
        {"hamburguer": 0.8, "lanches": 0.9, "bar": 0.6, "pizza": 0.5},
        {"noite": {"lanches": 0.7, "bar": 0.7}, "madrugada": {"lanches": 1.0, "hamburguer": 0.8}},
        0.7, 0.5, 0.7, 0.3, (), 0.9,
        {"manha": 0.0, "tarde": 0.15, "noite": 0.55, "madrugada": 0.3},
    ),
    Persona(
        "exploradora", "Exploradora (gosta de variar)", 0.13,
        {a: 0.55 for a in (
            "japonesa", "arabe", "italiana", "saudavel", "doces", "cafe", "brasileira",
        )},
        {},
        0.3, 0.3, 0.3, 0.8, (), 0.7,
    ),
    Persona(
        "economico", "Econômico", 0.15,
        {"lanches": 0.7, "brasileira": 0.7, "cafe": 0.5, "pizza": 0.4},
        {},
        1.0, 0.7, 1.0, 0.3, (), 0.8,
    ),
)


@dataclass
class SimUser:
    """Usuário simulado: persona + variação individual + localização."""

    index: int
    persona: Persona
    affinity: dict[str, float]
    price_sensitivity: float
    distance_sensitivity: float
    fee_sensitivity: float
    quality_weight: float
    dietary: tuple[str, ...]
    home_lat: float
    home_lon: float
    join_day_fraction: float  # 0 = entra no início da janela, 1 = no fim
    mood_sd: float = 0.4

    @property
    def key(self) -> str:
        return f"{self.persona.key}:{self.index}"


def sample_user(
    index: int,
    rng: random.Random,
    home: tuple[float, float],
    personas: tuple[Persona, ...] = PERSONAS,
) -> SimUser:
    persona = rng.choices(personas, weights=[p.share for p in personas])[0]

    def jitter(value: float, sd: float = 0.25) -> float:
        return value * math.exp(rng.gauss(0, sd))

    affinity = {a: min(1.0, jitter(v)) for a, v in persona.affinity.items()}
    # Gosto idiossincrático: um arquétipo aleatório ganha afinidade extra.
    extra = rng.choice(("pizza", "japonesa", "hamburguer", "doces", "arabe", "italiana"))
    affinity[extra] = max(affinity.get(extra, 0.1), rng.uniform(0.4, 0.8))

    # ~15% da população tem preferência alimentar adicional.
    dietary = persona.dietary
    if not dietary and rng.random() < 0.15:
        dietary = (rng.choice(("Vegetariano", "Sem lactose", "Sem glúten")),)

    return SimUser(
        index=index,
        persona=persona,
        affinity=affinity,
        price_sensitivity=jitter(persona.price_sensitivity),
        distance_sensitivity=jitter(persona.distance_sensitivity),
        fee_sensitivity=jitter(persona.fee_sensitivity),
        quality_weight=jitter(persona.quality_weight),
        dietary=dietary,
        home_lat=home[0],
        home_lon=home[1],
        join_day_fraction=rng.random() ** 1.5 * 0.7,
    )
