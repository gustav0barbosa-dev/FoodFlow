"""Modo demonstração x experimento oficial e propagação do contexto de eventos."""

from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.api import recommendations as recommendations_api
from app.schemas import InteractionIn
from app.services import interactions as interactions_module
from app.services.interactions import record_interaction


async def test_demo_mode_uses_selected_strategy() -> None:
    user_id = uuid4()

    assert (
        await recommendations_api._resolve_group(None, user_id, "demo", "distance")
        == "distance"
    )
    assert (
        await recommendations_api._resolve_group(None, user_id, "demo", "personalized")
        == "personalized"
    )
    # Estratégia inválida no modo demo cai no baseline de forma explícita.
    assert (
        await recommendations_api._resolve_group(None, user_id, "demo", "invalida")
        == "baseline"
    )


async def test_experiment_mode_ignores_manual_strategy(monkeypatch) -> None:
    user_id = uuid4()

    async def fake_assignment(_session, _user_id, _version=None):
        return SimpleNamespace(group_name="personalized")

    monkeypatch.setattr(
        recommendations_api, "get_or_create_assignment", fake_assignment
    )

    # Mesmo pedindo "distance" manualmente, o modo experimental usa a
    # atribuição persistente do usuário.
    assert (
        await recommendations_api._resolve_group(None, user_id, "experiment", "distance")
        == "personalized"
    )


def test_interaction_schema_validates_mode() -> None:
    payload = InteractionIn(
        user_id=uuid4(),
        restaurant_id=uuid4(),
        interaction_type="IMPRESSION",
        experiment_mode="demo",
        experiment_version="2026-11-v1",
        recommendation_id="rec-1",
    )
    assert payload.experiment_mode == "demo"

    with pytest.raises(ValidationError):
        InteractionIn(
            user_id=uuid4(),
            restaurant_id=uuid4(),
            interaction_type="IMPRESSION",
            experiment_mode="oficial",
        )


async def test_record_interaction_propagates_recommendation_context(
    monkeypatch,
) -> None:
    user_id = uuid4()
    restaurant_id = uuid4()
    captured: dict = {}

    async def fake_get_user(_session, _user_id):
        return SimpleNamespace(id=_user_id)

    async def fake_get_restaurant(_session, _restaurant_id):
        return SimpleNamespace(id=_restaurant_id)

    async def fake_create(_session, **kwargs):
        captured.update(kwargs)
        return SimpleNamespace(id=uuid4()), True

    async def fake_clear(_user_id):
        return True

    monkeypatch.setattr(interactions_module.crud, "get_user", fake_get_user)
    monkeypatch.setattr(interactions_module.crud, "get_restaurant", fake_get_restaurant)
    monkeypatch.setattr(interactions_module.crud, "create_interaction", fake_create)
    monkeypatch.setattr(interactions_module, "clear_user_scores", fake_clear)

    await record_interaction(
        None,
        user_id=user_id,
        restaurant_id=restaurant_id,
        interaction_type="CLICK",
        experiment_group="personalized",
        experiment_mode="experiment",
        experiment_version="2026-11-v1",
        recommendation_id="rec-123",
        recommendation_position=2,
        model_version="lgbm-test",
        event_metadata={"source": "home"},
    )

    assert captured["experiment_group"] == "personalized"
    assert captured["experiment_mode"] == "experiment"
    assert captured["experiment_version"] == "2026-11-v1"
    assert captured["recommendation_id"] == "rec-123"
    assert captured["recommendation_position"] == 2
    assert captured["model_version"] == "lgbm-test"


async def test_purchase_without_recommendation_context_is_not_attributed(
    monkeypatch,
) -> None:
    captured: dict = {}

    async def fake_get_user(_session, _user_id):
        return SimpleNamespace(id=_user_id)

    async def fake_get_restaurant(_session, _restaurant_id):
        return SimpleNamespace(id=_restaurant_id)

    async def fake_create(_session, **kwargs):
        captured.update(kwargs)
        return SimpleNamespace(id=uuid4()), True

    async def fake_clear(_user_id):
        return True

    monkeypatch.setattr(interactions_module.crud, "get_user", fake_get_user)
    monkeypatch.setattr(interactions_module.crud, "get_restaurant", fake_get_restaurant)
    monkeypatch.setattr(interactions_module.crud, "create_interaction", fake_create)
    monkeypatch.setattr(interactions_module, "clear_user_scores", fake_clear)

    await record_interaction(
        None,
        user_id=uuid4(),
        restaurant_id=uuid4(),
        interaction_type="PURCHASE",
        purchase_value=42.0,
    )

    # Sem contexto explícito de recomendação, a compra não é atribuída a uma
    # exposição inventada.
    assert captured["recommendation_id"] is None
    assert captured["experiment_group"] is None
