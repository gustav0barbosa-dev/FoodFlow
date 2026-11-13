"""Comportamento dos agentes: utilidade latente, funil de interação e métricas.

Módulo puro (sem banco nem HTTP), por isso testável isoladamente.

Modelo, em uma frase: cada usuário tem uma utilidade latente por restaurante
(afinidade por tipo de comida + turno + qualidade - preço - distância - frete
- restrição alimentar). A utilidade vira probabilidade de clique, favorito e
compra, e só os itens *examinados* (com viés de posição) podem ser clicados.
Como a utilidade verdadeira é conhecida, dá para medir o quanto um ranking
fica perto do ranking ideal (oráculo).

ATENÇÃO: os resultados medem o recomendador contra *este simulador*, não
contra pessoas reais. Servem para validar pipeline, A/B e regressões.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Any, Sequence

from app.simulation.personas import SimUser

EARTH_RADIUS_KM = 6371.0088
EXAM_DECAY = 0.30  # exam(pos) = 1 / (1 + EXAM_DECAY * pos)
DEFAULT_TOP_K = 10


@dataclass(frozen=True)
class SimMenuItem:
    id: str
    name: str
    price: float
    dietary_tags: frozenset[str]


@dataclass(frozen=True)
class SimRestaurant:
    id: str
    name: str
    archetype: str
    lat: float
    lon: float
    delivery_fee: float
    rating: float
    review_count: int
    price_index: float  # 1.0 = preço médio do catálogo
    quality: float  # qualidade latente em [0, 1] (verdade oculta)
    dietary_tags: frozenset[str]
    menu: tuple[SimMenuItem, ...] = ()


def sigmoid(x: float) -> float:
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    e = math.exp(x)
    return e / (1.0 + e)


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def latent_quality(restaurant_id: str) -> float:
    """Qualidade verdadeira, determinística por restaurante."""
    return random.Random(f"quality:{restaurant_id}").betavariate(5, 2.5)


def unmet_dietary(user: SimUser, restaurant: SimRestaurant) -> int:
    """Quantas restrições do usuário o restaurante não atende."""
    if not user.dietary:
        return 0
    offered = set(restaurant.dietary_tags)
    for item in restaurant.menu:
        offered |= item.dietary_tags
    return sum(1 for pref in user.dietary if pref not in offered)


def latent_utility(
    user: SimUser, restaurant: SimRestaurant, turno: str, distance_km: float
) -> float:
    u = 2.5 * user.affinity.get(restaurant.archetype, 0.1)
    u += user.persona.turno_boost.get(turno, {}).get(restaurant.archetype, 0.0)
    u += user.quality_weight * (restaurant.quality - 0.5) * 3.0
    u -= user.price_sensitivity * (restaurant.price_index - 1.0) * 2.0
    u -= user.distance_sensitivity * distance_km * 0.35
    u -= user.fee_sensitivity * restaurant.delivery_fee * 0.12
    u -= 2.0 * unmet_dietary(user, restaurant)
    return u


# Calibração do funil (ajustável sem mexer no resto).
CLICK_SLOPE, CLICK_CENTER = 1.5, 1.5
BUY_SLOPE, BUY_CENTER = 1.6, 2.0


def p_click(u: float) -> float:
    return 0.02 + 0.78 * sigmoid(CLICK_SLOPE * (u - CLICK_CENTER))


def p_buy_given_click(u: float) -> float:
    return 0.03 + 0.70 * sigmoid(BUY_SLOPE * (u - BUY_CENTER))


def relevance(u: float) -> float:
    """Probabilidade de compra se o item for examinado (relevância graduada)."""
    return p_click(u) * p_buy_given_click(u)


def exam_prob(position: int) -> float:
    return 1.0 / (1.0 + EXAM_DECAY * position)


@dataclass
class Event:
    interaction_type: str
    restaurant_id: str
    position: int | None = None
    purchase_value: float | None = None
    items: list[dict[str, Any]] | None = None


@dataclass
class SessionResult:
    events: list[Event] = field(default_factory=list)
    purchased_restaurant_id: str | None = None
    order_items: list[dict[str, Any]] = field(default_factory=list)
    order_value: float = 0.0
    # Qualidade da ordenação *dentro* da lista servida (NDCG@k).
    ranking_quality_served: float | None = None
    # Fração do top-k ideal do universo elegível que apareceu na lista servida.
    candidate_recall: float | None = None
    # Compras esperadas da lista servida / compras esperadas do top-k ideal
    # considerando *todos* os candidatos elegíveis.
    selection_coverage: float | None = None
    expected_purchases: float = 0.0
    oracle_expected_purchases: float = 0.0

    @property
    def ndcg(self) -> float | None:
        """Alias histórico de ``ranking_quality_served``."""
        return self.ranking_quality_served

    @property
    def clicks(self) -> int:
        return sum(1 for e in self.events if e.interaction_type == "CLICK")

    @property
    def impressions(self) -> int:
        return sum(1 for e in self.events if e.interaction_type == "IMPRESSION")


def dcg(relevances: Sequence[float]) -> float:
    return sum(rel / math.log2(i + 2) for i, rel in enumerate(relevances))


def ranking_quality(
    served_rel: Sequence[float], all_rel: Sequence[float], k: int
) -> tuple[float | None, float, float]:
    """NDCG@k da ordenação servida e rendimento esperado vs. oráculo completo.

    O NDCG compara a lista servida com a melhor ordenação *da própria lista*:
    mede se a API ordenou bem o que mostrou. O oráculo, por outro lado, usa
    ``all_rel`` (o universo elegível completo), então ``expected / oracle``
    mede também se os bons restaurantes foram selecionados.
    """
    served = list(served_rel)[:k]
    ideal_served_dcg = dcg(sorted(served, reverse=True))
    ndcg = dcg(served) / ideal_served_dcg if ideal_served_dcg > 0 else None

    ideal_full = sorted(all_rel, reverse=True)[:k]
    expected = sum(exam_prob(i) * r for i, r in enumerate(served))
    oracle = sum(exam_prob(i) * r for i, r in enumerate(ideal_full))
    return ndcg, expected, oracle


def candidate_recall(
    served_ids: Sequence[str], ideal_ids: Sequence[str], k: int
) -> float | None:
    """Fração do top-k ideal do universo que entrou na lista servida."""
    ideal = list(ideal_ids)[:k]
    if not ideal:
        return None
    return len(set(served_ids[:k]) & set(ideal)) / len(ideal)


def pick_order_items(
    user: SimUser, restaurant: SimRestaurant, rng: random.Random
) -> list[dict[str, Any]]:
    """Escolhe 1-3 itens compatíveis com a dieta, favorecendo preços menores.

    Se nenhum item atende às restrições, devolve ``[]``: o agente não compra
    naquele restaurante. Não existe fallback para o cardápio inteiro.
    """
    menu = list(restaurant.menu)
    if user.dietary:
        menu = [
            m for m in menu if all(p in m.dietary_tags for p in user.dietary)
        ]
    if not menu:
        return []
    weights = [1.0 / (max(m.price, 1.0) ** max(user.price_sensitivity, 0.1)) for m in menu]
    count = rng.choices((1, 2, 3), weights=(0.5, 0.35, 0.15))[0]
    chosen: dict[str, SimMenuItem] = {}
    for _ in range(count):
        item = rng.choices(menu, weights=weights)[0]
        chosen[item.id] = item
    return [
        {
            "id": item.id,
            "name": item.name,
            "quantity": rng.choices((1, 2), weights=(0.8, 0.2))[0],
            "price": item.price,
        }
        for item in chosen.values()
    ]


def simulate_session(
    user: SimUser,
    ranked: Sequence[SimRestaurant],
    candidates: Sequence[SimRestaurant],
    turno: str,
    rng: random.Random,
    top_k: int = DEFAULT_TOP_K,
) -> SessionResult:
    """Simula uma sessão: o usuário vê ``ranked[:top_k]`` e age.

    ``candidates`` é o conjunto completo elegível (para o ranking ideal). No
    modo ``live`` ele deve ser calculado *antes* de chamar a API; usar a própria
    lista retornada como universo esconderia os restaurantes relevantes que
    ficaram de fora da seleção.
    """

    def utility(r: SimRestaurant) -> float:
        d = haversine_km(user.home_lat, user.home_lon, r.lat, r.lon)
        return latent_utility(user, r, turno, d)

    all_candidates = list(candidates)
    base_u = {r.id: utility(r) for r in all_candidates}
    for r in ranked:
        base_u.setdefault(r.id, utility(r))

    result = SessionResult()
    shown = list(ranked[:top_k])
    served_rel = [relevance(base_u[r.id]) for r in shown]
    all_rel = [relevance(base_u[r.id]) for r in all_candidates]
    (
        result.ranking_quality_served,
        result.expected_purchases,
        result.oracle_expected_purchases,
    ) = ranking_quality(served_rel, all_rel, top_k)
    if result.oracle_expected_purchases > 0:
        result.selection_coverage = (
            result.expected_purchases / result.oracle_expected_purchases
        )
    ideal_ids = [
        r.id
        for r in sorted(all_candidates, key=lambda r: base_u[r.id], reverse=True)[:top_k]
    ]
    result.candidate_recall = candidate_recall(
        [r.id for r in shown], ideal_ids, top_k
    )

    mood = rng.gauss(0.0, user.mood_sd)  # humor do momento, comum à sessão
    for position, r in enumerate(shown):
        result.events.append(Event("IMPRESSION", r.id, position))

    for position, r in enumerate(shown):
        u = base_u[r.id] + mood
        if rng.random() > exam_prob(position):
            continue  # não examinou este item
        if rng.random() >= p_click(u):
            if u < -0.5 and rng.random() < 0.08:
                result.events.append(Event("DISMISS", r.id, position))
            continue

        result.events.append(Event("CLICK", r.id, position))
        result.events.append(Event("VIEW_DETAILS", r.id, position))
        if rng.random() < 0.12 * sigmoid(u - 1.0) * 2:
            result.events.append(Event("FAVORITE", r.id, position))
        if rng.random() < p_buy_given_click(u):
            items = pick_order_items(user, r, rng)
            if not items:
                continue
            value = round(sum(i["price"] * i["quantity"] for i in items), 2)
            result.events.append(
                Event("PURCHASE", r.id, position, purchase_value=value, items=items)
            )
            result.purchased_restaurant_id = r.id
            result.order_items = items
            result.order_value = value
            break  # um pedido por sessão
    return result


_REVIEW_COMMENTS = {
    5: ("Excelente, chegou quentinho!", "Muito bom, vou pedir de novo.", "Superou as expectativas."),
    4: ("Bom, entrega dentro do prazo.", "Gostei, só achei a porção um pouco pequena."),
    3: ("Razoável, esperava mais.", "Ok, nada de especial."),
    2: ("Demorou e chegou morno.", "Abaixo do esperado."),
    1: ("Péssima experiência.", "Não recomendo."),
}


def sample_review(
    restaurant: SimRestaurant, rng: random.Random
) -> tuple[int, str]:
    """Nota reflete a qualidade latente do restaurante (não o gosto do usuário)."""
    raw = 1 + 4 * restaurant.quality + rng.gauss(0, 0.7)
    rating = max(1, min(5, round(raw)))
    return rating, rng.choice(_REVIEW_COMMENTS[rating])
