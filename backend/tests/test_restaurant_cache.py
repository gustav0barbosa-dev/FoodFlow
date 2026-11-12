from redis.exceptions import RedisError

from app.cache import restaurant_cache
from app.core.config import settings


class FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}
        self.ttl: int | None = None

    async def get(self, key: str) -> str | None:
        return self.store.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> bool:
        self.store[key] = value
        self.ttl = ex
        return True


def test_cache_key_rounds_coordinates_and_includes_category() -> None:
    key1 = restaurant_cache.build_cache_key(
        -23.55051, -46.63332, 3000, "cafe"
    )
    key2 = restaurant_cache.build_cache_key(
        -23.55052, -46.63331, 3000, "cafe"
    )

    assert key1 == key2
    assert ":cafe" in key1
    assert restaurant_cache.build_cache_key(0, 0, 3000).endswith(":all")


async def test_cache_roundtrip(monkeypatch) -> None:
    fake = FakeRedis()

    async def fake_get_redis():
        return fake

    monkeypatch.setattr(restaurant_cache, "get_redis", fake_get_redis)

    key = restaurant_cache.build_cache_key(-23.55, -46.63, 3000)
    payload = [{"osm_id": 1, "name": "Café"}]

    assert await restaurant_cache.set_nearby(key, payload) is True
    assert fake.ttl == settings.overpass_cache_ttl_seconds
    assert await restaurant_cache.get_nearby(key) == payload


async def test_cache_degrades_when_redis_fails(monkeypatch) -> None:
    async def broken():
        raise RedisError("indisponível")

    monkeypatch.setattr(restaurant_cache, "get_redis", broken)

    assert await restaurant_cache.get_nearby("nearby:osm:v1:x") is None
    assert await restaurant_cache.set_nearby("nearby:osm:v1:x", []) is False


async def test_cache_ignores_invalid_payload(monkeypatch) -> None:
    fake = FakeRedis()
    fake.store["chave"] = "não é json"

    async def fake_get_redis():
        return fake

    monkeypatch.setattr(restaurant_cache, "get_redis", fake_get_redis)

    assert await restaurant_cache.get_nearby("chave") is None
