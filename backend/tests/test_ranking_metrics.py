"""Testes matemáticos das métricas de ranking.

Os casos usam resultados conhecidos para garantir que Precision, Recall,
NDCG, MAP e cobertura estão corretos — inclusive em situações extremas.
"""

import pytest

from app.ml.train import compute_ranking_metrics


def context(items, *, user_id="u1", context_id="c1"):
    return {
        "context_id": context_id,
        "user_id": user_id,
        "items": [
            (restaurant_id, score, relevance)
            for restaurant_id, score, relevance in items
        ],
    }


def test_better_ranking_has_higher_ndcg_and_map() -> None:
    ranking_a = context(
        [("a", 0.9, 1), ("b", 0.8, 1), ("c", 0.7, 0), ("d", 0.6, 0), ("e", 0.5, 0)]
    )
    ranking_b = context(
        [("a", 0.9, 0), ("b", 0.8, 0), ("c", 0.7, 1), ("d", 0.6, 1), ("e", 0.5, 0)]
    )

    metrics_a = compute_ranking_metrics([ranking_a], k=5)
    metrics_b = compute_ranking_metrics([ranking_b], k=5)

    assert metrics_a["ndcg_at_k"] > metrics_b["ndcg_at_k"]
    assert metrics_a["map_at_k"] > metrics_b["map_at_k"]
    assert metrics_a["precision_at_k"] == metrics_b["precision_at_k"] == 0.4
    assert metrics_a["recall_at_k"] == metrics_b["recall_at_k"] == 1.0


def test_all_items_relevant_is_perfect() -> None:
    metrics = compute_ranking_metrics(
        [context([("a", 1.0, 1), ("b", 0.9, 1), ("c", 0.8, 1)])], k=3
    )

    assert metrics["precision_at_k"] == 1.0
    assert metrics["recall_at_k"] == 1.0
    assert metrics["ndcg_at_k"] == 1.0
    assert metrics["map_at_k"] == 1.0


def test_context_without_relevance_is_counted_as_zero() -> None:
    metrics = compute_ranking_metrics(
        [context([("a", 1.0, 0), ("b", 0.9, 0)])], k=5
    )

    assert metrics["contexts"] == 1
    assert metrics["contexts_without_relevance"] == 1
    assert metrics["precision_at_k"] == 0.0
    assert metrics["recall_at_k"] == 0.0
    assert metrics["ndcg_at_k"] == 0.0
    assert metrics["map_at_k"] == 0.0


def test_macro_average_includes_contexts_without_relevance() -> None:
    perfect = context([("a", 1.0, 1)], context_id="perfect", user_id="u1")
    empty = context([("b", 1.0, 0)], context_id="empty", user_id="u2")

    metrics = compute_ranking_metrics([perfect, empty], k=5)

    assert metrics["contexts"] == 2
    assert metrics["ndcg_at_k"] == 0.5
    assert metrics["map_at_k"] == 0.5


def test_fewer_candidates_than_k_uses_available_denominator() -> None:
    metrics = compute_ranking_metrics(
        [context([("a", 1.0, 1), ("b", 0.5, 0)])], k=5
    )

    # Não é possível recuperar 5 itens: o denominador é min(K, n) = 2.
    assert metrics["precision_at_k"] == 0.5
    assert metrics["recall_at_k"] == 1.0
    assert metrics["ndcg_at_k"] == 1.0
    assert metrics["map_at_k"] == 1.0


def test_context_without_candidates_is_excluded_from_averages() -> None:
    metrics = compute_ranking_metrics(
        [context([]), context([("a", 1.0, 1)])], k=5
    )

    assert metrics["contexts_total"] == 2
    assert metrics["contexts"] == 1
    assert metrics["contexts_without_candidates"] == 1
    assert metrics["ndcg_at_k"] == 1.0


def test_graded_relevance_uses_gain_in_ndcg() -> None:
    strong_first = context([("a", 1.0, 3), ("b", 0.5, 2), ("c", 0.1, 0)])
    strong_last = context([("a", 1.0, 0), ("b", 0.5, 0), ("c", 0.1, 3)])

    assert compute_ranking_metrics([strong_first], k=3)["ndcg_at_k"] > (
        compute_ranking_metrics([strong_last], k=3)["ndcg_at_k"]
    )


def test_ties_are_broken_deterministically_by_restaurant_id() -> None:
    items = [("b", 0.5, 0), ("a", 0.5, 1)]
    first = compute_ranking_metrics([context(items)], k=2)
    second = compute_ranking_metrics([context(list(reversed(items)))], k=2)

    assert first == second
    # "a" vem antes de "b" no desempate, então o item relevante fica em 1º.
    assert first["ndcg_at_k"] == 1.0


def test_catalog_and_user_coverage_are_separate() -> None:
    metrics = compute_ranking_metrics(
        [
            context([("a", 1.0, 1), ("b", 0.5, 0)], user_id="u1", context_id="c1"),
            context([("b", 1.0, 1), ("c", 0.5, 0)], user_id="u2", context_id="c2"),
        ],
        k=2,
        catalog_size=10,
        user_count=4,
    )

    assert metrics["distinct_recommended"] == 3  # a, b, c
    assert metrics["catalog_coverage"] == 0.3
    assert metrics["users_with_recommendations"] == 2
    assert metrics["user_coverage"] == 0.5
    # "coverage" é mantido como alias explícito de catalog_coverage.
    assert metrics["coverage"] == metrics["catalog_coverage"]


@pytest.mark.parametrize(
    ("labels", "expected_ndcg", "expected_map"),
    [
        ([1, 0, 0], 1.0, 1.0),
        ([0, 1, 0], 1.0 / 1.584962500721156, 0.5),
        ([0, 0, 1], 1.0 / 2.0, 1.0 / 3.0),
    ],
)
def test_known_binary_rankings(labels, expected_ndcg, expected_map) -> None:
    items = [
        (f"r{index}", 1.0 - index * 0.1, label)
        for index, label in enumerate(labels)
    ]
    metrics = compute_ranking_metrics([context(items)], k=3)

    assert metrics["ndcg_at_k"] == pytest.approx(expected_ndcg, abs=1e-4)
    assert metrics["map_at_k"] == pytest.approx(expected_map, abs=1e-4)
