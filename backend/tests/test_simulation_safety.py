import argparse
import uuid

import pytest

from app.simulation.safety import (
    database_label,
    guard_write,
    production_reason,
    remote_host_reason,
)
from scripts.generate_synthetic_restaurants import synthetic_restaurant_id


def _args(**kwargs) -> argparse.Namespace:
    base = {"yes": False, "dry_run": False, "allow_remote_db": False}
    base.update(kwargs)
    return argparse.Namespace(**base)


def test_database_label_hides_credentials() -> None:
    label = database_label("postgresql+asyncpg://user:secret@db.example.com:5432/foodflow_sim")

    assert label == "db.example.com:5432/foodflow_sim"
    assert "secret" not in label


def test_production_is_detected_by_environment(monkeypatch) -> None:
    monkeypatch.setenv("FOODFLOW_ENV", "production")

    assert production_reason("postgresql+asyncpg://u:p@localhost:5432/foodflow") is not None


def test_production_is_detected_by_database_name(monkeypatch) -> None:
    monkeypatch.delenv("FOODFLOW_ENV", raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("ENVIRONMENT", raising=False)

    assert production_reason("postgresql+asyncpg://u:p@localhost:5432/foodflow_prod") is not None
    assert production_reason("postgresql+asyncpg://u:p@localhost:5432/foodflow_sim") is None


def test_remote_host_requires_explicit_flag() -> None:
    url = "postgresql+asyncpg://u:p@db.example.com:5432/foodflow_sim"

    assert remote_host_reason(url) is not None
    with pytest.raises(SystemExit) as exc:
        guard_write(_args(yes=True), url=url)
    assert exc.value.code == 3


def test_guard_write_blocks_without_yes(monkeypatch) -> None:
    monkeypatch.setenv("FOODFLOW_ENV", "development")

    with pytest.raises(SystemExit) as exc:
        guard_write(
            _args(yes=False),
            url="postgresql+asyncpg://u:p@localhost:5432/foodflow_sim",
        )
    assert exc.value.code == 2


def test_guard_write_allows_dry_run_without_yes(monkeypatch) -> None:
    monkeypatch.setenv("FOODFLOW_ENV", "development")

    guard_write(
        _args(dry_run=True),
        url="postgresql+asyncpg://u:p@localhost:5432/foodflow_sim",
    )


def test_guard_write_blocks_production_even_with_yes(monkeypatch) -> None:
    monkeypatch.setenv("FOODFLOW_ENV", "production")

    with pytest.raises(SystemExit) as exc:
        guard_write(
            _args(yes=True),
            url="postgresql+asyncpg://u:p@localhost:5432/foodflow",
        )
    assert exc.value.code == 3


def test_synthetic_restaurant_id_is_deterministic_and_seed_dependent() -> None:
    base = argparse.Namespace(seed=1, lat=-23.5, lon=-46.7, radius_km=6.0)

    assert synthetic_restaurant_id(base, 3) == synthetic_restaurant_id(base, 3)
    assert synthetic_restaurant_id(base, 3) != synthetic_restaurant_id(base, 4)
    assert synthetic_restaurant_id(base, 3) != synthetic_restaurant_id(
        argparse.Namespace(seed=2, lat=-23.5, lon=-46.7, radius_km=6.0), 3
    )
    assert isinstance(synthetic_restaurant_id(base, 3), uuid.UUID)
