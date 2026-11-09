from app.seed_data import (
    REVIEWERS,
    REVIEW_COMMENTS,
    SEED_ORDERS,
    SEED_RESTAURANTS,
    SEED_USERS,
)


def test_seed_has_twelve_restaurants_with_menu_items() -> None:
    assert len(SEED_RESTAURANTS) == 12
    assert len({restaurant["name"] for restaurant in SEED_RESTAURANTS}) == 12
    assert all(restaurant["menu_item"]["id"] for restaurant in SEED_RESTAURANTS)


def test_seed_orders_reference_existing_entities() -> None:
    restaurant_names = {restaurant["name"] for restaurant in SEED_RESTAURANTS}
    user_emails = {user["email"] for user in SEED_USERS}

    assert len(SEED_ORDERS) >= 24
    for email, restaurant_name, days_ago, hour, quantity in SEED_ORDERS:
        assert email in user_emails
        assert restaurant_name in restaurant_names
        assert 0 <= days_ago <= 90
        assert 0 <= hour <= 23
        assert quantity >= 1


def test_seed_reviews_cover_all_restaurants() -> None:
    restaurant_names = {restaurant["name"] for restaurant in SEED_RESTAURANTS}
    user_emails = {user["email"] for user in SEED_USERS}

    assert set(REVIEW_COMMENTS) == restaurant_names
    assert set(REVIEWERS) <= user_emails
    assert all(len(comments) >= 3 for comments in REVIEW_COMMENTS.values())
