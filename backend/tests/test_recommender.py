from uuid import uuid4

from app.ml.recommender import (
    Recommender,
    normalize_scores,
    popularity_score,
    popularity_scores,
)
from app.models import Restaurant


def make_restaurant(*, rating: float, reviews: int) -> Restaurant:
    return Restaurant(
        id=uuid4(),
        name=f"Restaurante {reviews}",
        address="Rua Teste, 1",
        categories=["Brasileira"],
        average_rating=rating,
        review_count=reviews,
        delivery_fee=5.0,
        delivery_time_min=20,
        delivery_time_max=30,
    )


def test_popularity_score_rewards_rating_and_volume() -> None:
    low = make_restaurant(rating=4.0, reviews=10)
    high = make_restaurant(rating=4.8, reviews=500)

    assert popularity_score(high) > popularity_score(low)


def test_popularity_scores_are_normalized() -> None:
    restaurants = [
        make_restaurant(rating=4.0, reviews=10),
        make_restaurant(rating=4.8, reviews=500),
    ]

    scores = popularity_scores(restaurants)

    assert set(scores) == {str(r.id) for r in restaurants}
    assert max(scores.values()) == 1.0
    assert all(0.0 <= score <= 1.0 for score in scores.values())


def test_normalize_scores_preserves_order() -> None:
    scores = {"a": 0.001, "b": 0.002, "c": 0.0005}

    normalized = normalize_scores(scores)

    assert normalized["b"] == 1.0
    assert normalized["c"] == 0.0
    assert normalized["a"] > normalized["c"]
    assert normalized["a"] < normalized["b"]


def test_normalize_scores_handles_ties() -> None:
    assert normalize_scores({"a": 0.3, "b": 0.3}) == {"a": 0.5, "b": 0.5}


def test_predict_scores_without_model_returns_neutral_scores() -> None:
    restaurants = [
        make_restaurant(rating=4.0, reviews=10),
        make_restaurant(rating=4.8, reviews=500),
    ]
    recommender = Recommender()

    scores = recommender.predict_scores({}, restaurants)

    assert scores == {str(r.id): 0.5 for r in restaurants}
