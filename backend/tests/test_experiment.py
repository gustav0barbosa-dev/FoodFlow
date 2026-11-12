from datetime import datetime, timezone
from uuid import UUID, uuid4

from app.services.experiment import (
    EXPERIMENT_BASELINE,
    EXPERIMENT_DISTANCE,
    EXPERIMENT_GROUPS,
    EXPERIMENT_PERSONALIZED,
    MIN_IMPRESSIONS_FOR_READING,
    _wilson_interval,
    assign_experiment_group,
    resolve_experiment_group,
    summarize_experiment,
)


def test_assignment_is_stable_and_covers_three_groups() -> None:
    user_id = UUID("12345678-1234-5678-1234-567812345678")

    first = assign_experiment_group(user_id)
    assert first in EXPERIMENT_GROUPS
    assert assign_experiment_group(user_id) == first

    groups = {
        assign_experiment_group(UUID(int=index)) for index in range(1, 60)
    }
    assert groups == set(EXPERIMENT_GROUPS)


def test_assignment_depends_on_experiment_version() -> None:
    user_id = uuid4()

    assert assign_experiment_group(user_id, "v1") == assign_experiment_group(
        user_id, "v1"
    )
    # A versão entra no hash: uma nova versão é uma decisão explícita e pode
    # produzir uma nova atribuição.
    assignments = {
        assign_experiment_group(user_id, version)
        for version in ("v1", "v2", "v3", "v4", "v5", "v6")
    }
    assert len(assignments) > 1


def test_resolve_experiment_group_prefers_explicit_value() -> None:
    user_id = uuid4()

    assert resolve_experiment_group("baseline", user_id) == "baseline"
    assert resolve_experiment_group("distance", user_id) == "distance"
    assert resolve_experiment_group("invalido", user_id) == assign_experiment_group(
        user_id
    )
    assert resolve_experiment_group(None, user_id) == assign_experiment_group(user_id)


def test_summarize_without_impressions_is_collecting() -> None:
    summary = summarize_experiment([], now=datetime(2026, 11, 11, tzinfo=timezone.utc))

    assert summary["phase"] == "collecting"
    assert summary["has_data"] is False
    assert summary["total_impressions"] == 0
    assert set(summary["groups"]) == set(EXPERIMENT_GROUPS)
    assert summary["statistical_analysis"]["available"] is False


def test_summarize_marks_insufficient_data_below_threshold() -> None:
    rows = [
        (EXPERIMENT_BASELINE, "IMPRESSION", 5),
        (EXPERIMENT_BASELINE, "CLICK", 1),
    ]

    summary = summarize_experiment(rows)

    assert summary["phase"] == "insufficient_data"
    assert summary["total_impressions"] == 5
    assert summary["groups"][EXPERIMENT_BASELINE]["ctr"] == 0.2
    assert MIN_IMPRESSIONS_FOR_READING > 5


def test_ready_phase_is_descriptive_not_statistical_significance() -> None:
    rows = [
        (EXPERIMENT_BASELINE, "IMPRESSION", 100),
        (EXPERIMENT_BASELINE, "CLICK", 10),
        (EXPERIMENT_BASELINE, "PURCHASE", 5),
        (EXPERIMENT_PERSONALIZED, "IMPRESSION", 100),
        (EXPERIMENT_PERSONALIZED, "CLICK", 30),
        (EXPERIMENT_PERSONALIZED, "PURCHASE", 8),
        (EXPERIMENT_DISTANCE, "IMPRESSION", 100),
        (EXPERIMENT_DISTANCE, "CLICK", 5),
        (EXPERIMENT_DISTANCE, "PURCHASE", 2),
    ]
    user_rows = [
        (EXPERIMENT_BASELINE, 7),
        (EXPERIMENT_PERSONALIZED, 7),
        (EXPERIMENT_DISTANCE, 7),
    ]

    summary = summarize_experiment(rows, user_rows)

    assert summary["phase"] == "ready"
    assert summary["statistical_analysis"]["available"] is False
    assert summary["comparison"]["winner_declared"] is False
    assert summary["comparison"]["best_ctr"] == EXPERIMENT_PERSONALIZED
    assert summary["comparison"]["best_conversion"] == EXPERIMENT_PERSONALIZED

    personalized = summary["groups"][EXPERIMENT_PERSONALIZED]
    assert personalized["ctr"] == 0.3
    assert personalized["conversion_rate"] == 0.08
    assert personalized["detail_rate"] == 0.0
    assert personalized["favorite_rate"] == 0.0
    assert personalized["users"] == 7
    assert personalized["model_versions"] == []

    for group in EXPERIMENT_GROUPS:
        interval = summary["groups"][group]["confidence_intervals"]["ctr"]
        assert interval is not None
        assert interval["low"] <= summary["groups"][group]["ctr"] <= interval["high"]


def test_statistical_analysis_uses_bonferroni_for_all_comparisons() -> None:
    rows = [
        (EXPERIMENT_BASELINE, "IMPRESSION", 200),
        (EXPERIMENT_BASELINE, "CLICK", 20),
        (EXPERIMENT_BASELINE, "PURCHASE", 10),
        (EXPERIMENT_PERSONALIZED, "IMPRESSION", 200),
        (EXPERIMENT_PERSONALIZED, "CLICK", 60),
        (EXPERIMENT_PERSONALIZED, "PURCHASE", 20),
        (EXPERIMENT_DISTANCE, "IMPRESSION", 200),
        (EXPERIMENT_DISTANCE, "CLICK", 20),
        (EXPERIMENT_DISTANCE, "PURCHASE", 10),
    ]
    user_rows = [
        (EXPERIMENT_BASELINE, 25),
        (EXPERIMENT_PERSONALIZED, 25),
        (EXPERIMENT_DISTANCE, 25),
    ]

    summary = summarize_experiment(rows, user_rows)

    assert summary["phase"] == "statistical_analysis"
    analysis = summary["statistical_analysis"]
    assert analysis["available"] is True
    assert analysis["alpha"] == 0.05
    # 2 métricas x 2 grupos comparados contra o baseline = 4 comparações.
    assert analysis["corrected_alpha"] == 0.0125
    assert len(analysis["comparisons"]) == 4
    assert "Bonferroni" in analysis["method"]
    assert summary["comparison"]["winner_declared"] is True


def test_summarize_counts_untagged_events_separately() -> None:
    rows = [(None, "IMPRESSION", 4), (EXPERIMENT_BASELINE, "IMPRESSION", 1)]

    summary = summarize_experiment(rows)

    assert summary["untagged_events"] == 4
    assert summary["groups"][EXPERIMENT_BASELINE]["impressions"] == 1


def test_summarize_does_not_inflate_detail_rate_with_legacy_view() -> None:
    rows = [
        (EXPERIMENT_BASELINE, "IMPRESSION", 10),
        (EXPERIMENT_BASELINE, "VIEW", 4),
        (EXPERIMENT_BASELINE, "VIEW_DETAILS", 2),
    ]

    summary = summarize_experiment(rows)

    baseline = summary["groups"][EXPERIMENT_BASELINE]
    assert baseline["views"] == 4
    assert baseline["view_details"] == 2
    assert baseline["detail_rate"] == 0.2


def test_rates_use_impressions_as_denominator() -> None:
    rows = [
        (EXPERIMENT_BASELINE, "IMPRESSION", 50),
        (EXPERIMENT_BASELINE, "CLICK", 10),
        (EXPERIMENT_BASELINE, "VIEW_DETAILS", 5),
        (EXPERIMENT_BASELINE, "FAVORITE", 4),
        (EXPERIMENT_BASELINE, "PURCHASE", 2),
    ]

    baseline = summarize_experiment(rows)["groups"][EXPERIMENT_BASELINE]

    assert baseline["ctr"] == 0.2
    assert baseline["detail_rate"] == 0.1
    assert baseline["favorite_rate"] == 0.08
    assert baseline["conversion_rate"] == 0.04
    # Detalhe por clique é uma métrica separada e não substitui detail_rate.
    assert baseline["detail_per_click"] == 0.5


def test_unique_users_is_distinct_and_not_sum_of_groups() -> None:
    rows = [
        (EXPERIMENT_BASELINE, "IMPRESSION", 100),
        (EXPERIMENT_PERSONALIZED, "IMPRESSION", 100),
    ]
    user_rows = [(EXPERIMENT_BASELINE, 7), (EXPERIMENT_PERSONALIZED, 6)]

    summary = summarize_experiment(rows, user_rows, unique_users=10)

    assert summary["unique_users"] == 10
    assert summary["exposed_users"] == 13


def test_demo_events_are_reported_but_never_in_official_denominator() -> None:
    rows = [(EXPERIMENT_BASELINE, "IMPRESSION", 100)]

    summary = summarize_experiment(rows, demo_events=50)

    assert summary["total_impressions"] == 100
    assert summary["demo_events"] == 50
    assert summary["groups"][EXPERIMENT_BASELINE]["impressions"] == 100


def test_contamination_is_reported() -> None:
    summary = summarize_experiment(
        [(EXPERIMENT_BASELINE, "IMPRESSION", 100)],
        contaminated_users=2,
    )

    assert summary["contaminated_users"] == 2
    assert summary["contamination_detected"] is True


def test_wilson_interval_contains_observed_rate_and_is_bounded() -> None:
    interval = _wilson_interval(30, 100)

    assert interval is not None
    assert interval["low"] <= 0.3 <= interval["high"]
    assert 0.0 <= interval["low"] <= interval["high"] <= 1.0
    assert _wilson_interval(0, 0) is None
