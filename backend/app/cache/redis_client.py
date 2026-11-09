import json
from typing import Any
import redis.asyncio as redis
from app.core.config import settings

_redis: redis.Redis | None = None


async def get_redis() -> redis.Redis:
    global _redis
    if _redis is None:
        _redis = redis.from_url(settings.redis_url, decode_responses=True)
    return _redis


async def get_scores(user_id: str, turno: str) -> dict[str, float] | None:
    r = await get_redis()
    key = f"reco:scores:{user_id}:{turno}"
    data = await r.get(key)
    if data:
        return json.loads(data)
    return None


async def set_scores(user_id: str, turno: str, scores: dict[str, float], ttl: int = 86400):
    r = await get_redis()
    key = f"reco:scores:{user_id}:{turno}"
    await r.set(key, json.dumps(scores), ex=ttl)


async def track_event(event_type: str, payload: dict[str, Any]):
    r = await get_redis()
    await r.xadd("events:stream", {"type": event_type, "payload": json.dumps(payload)})
