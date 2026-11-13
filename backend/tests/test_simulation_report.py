import pandas as pd

from scripts.simulate import _add_period, build_report


def _frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "mode": "live", "group": "baseline", "cohort": "known",
                "persona": "executivo_almoco", "user_index": 1,
                "purchased": True, "impressions": 10, "clicks": 2,
                "ranking_quality_served": 0.8, "candidate_recall": 0.5,
                "selection_coverage": 0.6, "expected_purchases": 0.6,
                "oracle_expected_purchases": 1.0,
                "session_time": "2026-11-01T12:00:00Z",
            },
            {
                "mode": "live", "group": "baseline", "cohort": "known",
                "persona": "executivo_almoco", "user_index": 2,
                "purchased": False, "impressions": 10, "clicks": 1,
                "ranking_quality_served": 0.6, "candidate_recall": 0.3,
                "selection_coverage": 0.4, "expected_purchases": 0.4,
                "oracle_expected_purchases": 1.0,
                "session_time": "2026-11-02T12:00:00Z",
            },
        ]
    )


def test_report_exposes_ordering_and_selection_metrics() -> None:
    report = build_report(_frame(), ["mode", "group"])

    row = report.iloc[0]
    assert row["usuarios"] == 2
    assert row["ordenacao servida (NDCG@10)"] == 0.7
    assert row["recall do top-10 ideal"] == 0.4
    assert abs(row["cobertura do oraculo"] - 0.5) < 1e-9
    assert "cobertura IC95" in report.columns


def test_report_period_grouping() -> None:
    frame = _add_period(_frame(), "day")

    assert frame["period"].tolist() == ["2026-11-01", "2026-11-02"]
    assert _add_period(_frame(), None) is not None
