from redis.exceptions import RedisError

from app.cache import redis_client


class _FakePipeline:
    def __init__(self, client: "_FakeRedis") -> None:
        self.client = client
        self.keys: list[str] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False

    def incr(self, key: str) -> None:
        self.keys.append(key)

    async def execute(self):
        for key in self.keys:
            self.client.store[key] = self.client.store.get(key, 0) + 1
        return [self.client.store[key] for key in self.keys]


class _FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, int] = {}

    def pipeline(self, transaction: bool = False) -> _FakePipeline:
        return _FakePipeline(self)

    async def mget(self, keys: list[str]):
        return [self.store.get(key) for key in keys]

    async def ping(self) -> bool:
        return True


async def test_increment_and_read_recommendation_metrics(monkeypatch) -> None:
    fake = _FakeRedis()

    async def fake_get_redis():
        return fake

    monkeypatch.setattr(redis_client, "get_redis", fake_get_redis)

    assert await redis_client.increment_metrics("requests", "cache_hits") is True
    assert await redis_client.increment_metrics("requests", "cache_misses") is True
    assert await redis_client.increment_metrics("model_scores") is True

    metrics = await redis_client.get_recommendation_metrics()

    assert metrics["redis_available"] is True
    assert metrics["requests"] == 2
    assert metrics["cache_hits"] == 1
    assert metrics["cache_misses"] == 1
    assert metrics["model_scores"] == 1
    assert metrics["popularity_scores"] == 0
    assert metrics["cache_hit_rate"] == 0.5


async def test_increment_metrics_ignores_unknown_names(monkeypatch) -> None:
    fake = _FakeRedis()

    async def fake_get_redis():
        return fake

    monkeypatch.setattr(redis_client, "get_redis", fake_get_redis)

    assert await redis_client.increment_metrics("unknown") is False
    assert await redis_client.increment_metrics("unknown", "requests") is True
    assert fake.store == {"metrics:reco:requests": 1}


async def test_metrics_degrade_gracefully_without_redis(monkeypatch) -> None:
    async def failing_get_redis():
        raise RedisError("redis down")

    monkeypatch.setattr(redis_client, "get_redis", failing_get_redis)

    metrics = await redis_client.get_recommendation_metrics()

    assert metrics["redis_available"] is False
    assert metrics["requests"] == 0
    assert metrics["cache_hit_rate"] == 0.0
    assert await redis_client.increment_metrics("requests") is False
    assert await redis_client.ping_redis() is False
