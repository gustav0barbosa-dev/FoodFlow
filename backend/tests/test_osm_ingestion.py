from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.services import osm_ingestion


class FakeSession:
    def __init__(self) -> None:
        self.added: list = []
        self.commits = 0
        self.rollbacks = 0

    def add(self, instance) -> None:
        self.added.append(instance)

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


class FakeOverpass:
    def __init__(self, elements):
        self.elements = elements
        self.calls: list[tuple] = []

    async def search_bbox(self, south, west, north, east, category=None):
        self.calls.append((south, west, north, east, category))
        return self.elements


def element(osm_id: int, *, amenity: str = "restaurant", name: str = "Teste"):
    return {
        "type": "node",
        "id": osm_id,
        "lat": -23.55,
        "lon": -46.63,
        "tags": {"amenity": amenity, "name": name, "diet:vegan": "yes"},
    }


async def test_ingest_region_deduplicates_and_persists(monkeypatch) -> None:
    session = FakeSession()
    client = FakeOverpass(
        [element(1), element(1), element(2, amenity="cafe"), element(3, amenity="school")]
    )

    async def fake_get_by_osm(_session, osm_type, osm_id):
        return None

    monkeypatch.setattr(
        osm_ingestion.crud, "get_restaurant_by_osm", fake_get_by_osm
    )

    summary = await osm_ingestion.ingest_region(
        session,
        south=-23.6,
        west=-46.7,
        north=-23.5,
        east=-46.6,
        client=client,
    )

    assert client.calls == [(-23.6, -46.7, -23.5, -46.6, None)]
    assert summary.fetched == 4
    assert summary.deduplicated == 3
    assert summary.created == 2
    assert summary.skipped == 1
    assert summary.errors == []
    assert len(session.added) == 2
    assert all(item.last_synced_at is not None for item in session.added)
    assert session.added[0].dietary_tags == ["Vegano"]


async def test_ingest_region_updates_existing(monkeypatch) -> None:
    session = FakeSession()
    client = FakeOverpass([element(1)])
    existing = SimpleNamespace(osm_type="node", osm_id=1, name="Antigo")

    async def fake_get_by_osm(_session, osm_type, osm_id):
        return existing

    monkeypatch.setattr(
        osm_ingestion.crud, "get_restaurant_by_osm", fake_get_by_osm
    )

    summary = await osm_ingestion.ingest_region(
        session,
        south=-23.6,
        west=-46.7,
        north=-23.5,
        east=-46.6,
        client=client,
    )

    assert summary.created == 0
    assert summary.updated == 1
    assert existing.name == "Teste"
    assert existing.last_synced_at is not None
    assert session.added == []


async def test_ingest_region_continues_after_row_error(monkeypatch) -> None:
    session = FakeSession()
    client = FakeOverpass([element(1), element(2)])

    async def fake_get_by_osm(_session, osm_type, osm_id):
        return None

    monkeypatch.setattr(
        osm_ingestion.crud, "get_restaurant_by_osm", fake_get_by_osm
    )

    original_commit = session.commit
    calls = {"count": 0}

    async def flaky_commit():
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("falha simulada")
        await original_commit()

    session.commit = flaky_commit  # type: ignore[method-assign]

    summary = await osm_ingestion.ingest_region(
        session,
        south=-23.6,
        west=-46.7,
        north=-23.5,
        east=-46.6,
        client=client,
    )

    assert len(summary.errors) == 1
    assert summary.created == 1
    assert session.rollbacks == 1
