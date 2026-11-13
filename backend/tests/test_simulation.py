import random

from app.simulation.behavior import (
    SimMenuItem,
    SimRestaurant,
    candidate_recall,
    exam_prob,
    haversine_km,
    latent_quality,
    latent_utility,
    pick_order_items,
    ranking_quality,
    relevance,
    simulate_session,
)
from app.simulation.menu_catalog import ARCHETYPES, archetype_for, build_menu
from app.simulation.personas import PERSONAS, sample_user


def _restaurant(i: int, archetype: str = "pizza", tags=frozenset(), fee=0.0, dist=0.0):
    return SimRestaurant(
        id=str(i), name=f"r{i}", archetype=archetype,
        lat=-23.53 + dist / 111.0, lon=-46.79, delivery_fee=fee, rating=0.0,
        review_count=0, price_index=1.0, quality=0.6, dietary_tags=tags,
        menu=(SimMenuItem(f"m{i}", "item", 30.0, frozenset(tags)),),
    )


def _user(seed: int = 1):
    return sample_user(seed, random.Random(seed), (-23.53, -46.79))


def test_archetype_from_osm_and_portuguese_categories() -> None:
    assert archetype_for(["restaurant"], "pizza;italian") == "pizza"
    assert archetype_for(["fast_food"], "burger") == "hamburguer"
    assert archetype_for(["Japonês"], None) == "japonesa"
    assert archetype_for(["restaurant"], "barbecue") == "churrasco"  # não vira "bar"
    assert archetype_for(["bar"], None) == "bar"
    assert archetype_for(["restaurant"], None) == "brasileira"
    assert archetype_for(None, None) == "brasileira"


def test_menu_is_deterministic_and_well_formed() -> None:
    for archetype in ARCHETYPES:
        menu = build_menu("rest-1", archetype)
        assert menu == build_menu("rest-1", archetype)
        assert len(menu) >= 5
        assert len({item["name"] for item in menu}) == len(menu)
        assert all(item["price"] > 0 for item in menu)
    assert build_menu("rest-1", "pizza") != build_menu("rest-2", "pizza")


def test_personas_shares_sum_to_one() -> None:
    assert abs(sum(p.share for p in PERSONAS) - 1.0) < 1e-9


def test_utility_penalizes_distance_fee_and_unmet_diet() -> None:
    user = _user()
    base = latent_utility(user, _restaurant(1), "noite", 1.0)
    assert latent_utility(user, _restaurant(1), "noite", 8.0) < base
    assert latent_utility(user, _restaurant(1, fee=9.99), "noite", 1.0) < base
    vegan_user = _user()
    vegan_user.dietary = ("Vegano",)
    assert (
        latent_utility(vegan_user, _restaurant(1), "noite", 1.0)
        < latent_utility(vegan_user, _restaurant(2, tags=frozenset({"Vegano"})), "noite", 1.0)
    )


def test_quality_is_stable_and_bounded() -> None:
    assert latent_quality("a") == latent_quality("a")
    assert 0 <= latent_quality("a") <= 1


def test_ideal_ranking_has_ndcg_one_and_full_efficiency() -> None:
    rels = [0.5, 0.1, 0.3, 0.05]
    ndcg, expected, oracle = ranking_quality(sorted(rels, reverse=True), rels, k=4)
    assert abs(ndcg - 1.0) < 1e-9 and abs(expected - oracle) < 1e-9
    worse_ndcg, worse_expected, _ = ranking_quality(sorted(rels), rels, k=4)
    assert worse_ndcg < 1.0 and worse_expected < oracle
    assert exam_prob(0) == 1.0 and exam_prob(9) < exam_prob(1)


def test_session_invariants() -> None:
    rng = random.Random(0)
    restaurants = [_restaurant(i, archetype=a, dist=i * 0.3)
                   for i, a in enumerate(["pizza", "japonesa", "lanches", "cafe"] * 5)]
    purchases = 0
    for seed in range(200):
        user = _user(seed)
        user.dietary = ()  # invariantes do funil, não restrição alimentar
        result = simulate_session(user, restaurants, restaurants, "noite", rng, top_k=10)
        types = [e.interaction_type for e in result.events]
        assert types.count("PURCHASE") <= 1
        assert types.count("IMPRESSION") == 10
        assert types.count("VIEW_DETAILS") == types.count("CLICK")
        if result.purchased_restaurant_id:
            purchases += 1
            assert types[-1] == "PURCHASE"
            assert result.order_value == round(
                sum(i["price"] * i["quantity"] for i in result.order_items), 2
            )
        assert result.ndcg is None or 0 <= result.ndcg <= 1 + 1e-9
        assert result.expected_purchases <= result.oracle_expected_purchases + 1e-9
    assert 0 < purchases < 200


def test_oracle_order_beats_reverse_order() -> None:
    users = [_user(s) for s in range(150)]
    restaurants = [_restaurant(i, archetype=a, dist=i * 0.2)
                   for i, a in enumerate(["pizza", "japonesa", "lanches", "cafe", "saudavel"] * 6)]

    def total(ordering) -> float:
        rng = random.Random(5)
        wins = 0
        for user in users:
            user.dietary = ()
            ranked = sorted(
                restaurants,
                key=lambda r: ordering * latent_utility(
                    user, r, "noite", haversine_km(user.home_lat, user.home_lon, r.lat, r.lon)),
            )
            wins += simulate_session(user, ranked, restaurants, "noite", rng).purchased_restaurant_id is not None
        return wins

    assert total(-1) > total(1)  # melhor primeiro compra mais do que pior primeiro
    assert relevance(3.0) > relevance(0.0)


def test_dietary_restriction_never_falls_back_to_incompatible_menu() -> None:
    user = _user()
    user.dietary = ("Vegano",)
    restaurant = SimRestaurant(
        id="meat-only", name="Carne", archetype="churrasco",
        lat=user.home_lat, lon=user.home_lon, delivery_fee=0.0, rating=0.0,
        review_count=0, price_index=1.0, quality=0.9, dietary_tags=frozenset(),
        menu=(SimMenuItem("meat", "Picanha", 50.0, frozenset({"Sem glúten"})),),
    )

    assert pick_order_items(user, restaurant, random.Random(0)) == []
    for seed in range(100):
        result = simulate_session(
            user, [restaurant], [restaurant], "noite", random.Random(seed)
        )
        assert result.purchased_restaurant_id is None


def test_pick_order_items_uses_only_compatible_items() -> None:
    user = _user()
    user.dietary = ("Vegano",)
    restaurant = SimRestaurant(
        id="mixed", name="Misto", archetype="pizza",
        lat=user.home_lat, lon=user.home_lon, delivery_fee=0.0, rating=0.0,
        review_count=0, price_index=1.0, quality=0.7, dietary_tags=frozenset(),
        menu=(
            SimMenuItem("meat", "Calabresa", 40.0, frozenset()),
            SimMenuItem("vegan", "Pizza Vegana", 45.0, frozenset({"Vegano"})),
        ),
    )

    items = pick_order_items(user, restaurant, random.Random(3))

    assert items
    assert {item["id"] for item in items} == {"vegan"}


def test_selection_metrics_use_full_candidate_universe() -> None:
    user = _user()
    restaurants = [_restaurant(i, archetype=a, dist=i * 0.1)
                   for i, a in enumerate(["pizza", "japonesa", "lanches", "cafe"] * 5)]
    utilities = {
        r.id: latent_utility(
            user, r, "noite", haversine_km(user.home_lat, user.home_lon, r.lat, r.lon)
        )
        for r in restaurants
    }
    ideal = sorted(restaurants, key=lambda r: utilities[r.id], reverse=True)
    # Serve os 10 piores: a ordenação interna pode até ser boa, mas a seleção
    # contra o universo completo é ruim.
    served = list(reversed(ideal))[:10]

    result = simulate_session(user, served, restaurants, "noite", random.Random(1), top_k=10)

    assert result.candidate_recall == 0.0
    assert result.selection_coverage is not None
    assert result.selection_coverage < 1.0
    assert result.expected_purchases < result.oracle_expected_purchases


def test_ranking_quality_served_only_measures_ordering() -> None:
    ndcg, expected, oracle = ranking_quality([0.1, 0.5, 0.3], [0.9, 0.5, 0.3, 0.1], k=3)

    assert ndcg is not None and ndcg < 1.0  # a lista servida não está ordenada
    assert oracle > expected  # o oráculo usa o universo completo
    assert candidate_recall(["a", "b"], ["a", "c", "d"], k=3) == 1 / 3
    assert candidate_recall([], [], k=3) is None
