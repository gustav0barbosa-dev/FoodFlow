from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas import EventIn, RestaurantSearchParams, ReviewCreate


def test_review_create_accepts_valid_rating() -> None:
    review = ReviewCreate(
        restaurant_id=uuid4(),
        user_id=uuid4(),
        rating=5,
        comment="Excelente",
    )
    assert review.rating == 5


@pytest.mark.parametrize("rating", [0, 6, -1])
def test_review_create_rejects_invalid_rating(rating: int) -> None:
    with pytest.raises(ValidationError):
        ReviewCreate(
            restaurant_id=uuid4(),
            user_id=uuid4(),
            rating=rating,
        )


def test_event_in_rejects_unknown_type() -> None:
    with pytest.raises(ValidationError):
        EventIn(type="unknown_event")


def test_event_in_accepts_documented_type() -> None:
    event = EventIn(
        type="restaurant_opened",
        payload={"restaurant_id": "r1"},
    )
    assert event.payload["restaurant_id"] == "r1"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("lat", 91),
        ("lon", -181),
        ("radius_km", 0),
        ("limit", 101),
        ("offset", -1),
    ],
)
def test_search_params_validate_ranges(field: str, value: float) -> None:
    base = {"lat": -23.5, "lon": -46.8}
    base[field] = value
    with pytest.raises(ValidationError):
        RestaurantSearchParams(**base)
