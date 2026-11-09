"""Cliente Redis com degradação graciosa quando o serviço está indisponível."""
import json
import logging
from typing import Any

import redis.asyncio as redis
from redis.exceptions import RedisError

from app.core.config import settings

logger = logging.getLogger(__name__)

_redis: redis.Redis | None = None
SCORE_TTL_SECONDS = 86400


async def get_redis() -> redis.Redis:
    global _redis
    if _redis is None:
        _redis = redis.from_url(settings.redis_url, decode_responses=True)
    return _redis


async def close_redis() -> None:
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None


async def get_scores(user_id: str, turno: str) -> dict[str, float] | None:
    key = f"reco:scores:{user_id}:{turno}"
    try:
        client = await get_redis()
        data = await client.get(key)
        if not data:
            return None
        parsed = json.loads(data)
        if not isinstance(parsed, dict):
            return None
        return {str(restaurant_id): float(score) for restaurant_id, score in parsed.items()}
    except (RedisError, ValueError, TypeError) as exc:
        logger.warning("Falha ao ler scores do Redis (%s): %s", key, exc)
        return None


async def set_scores(
    user_id: str,
    turno: str,
    scores: dict[str, float],
    ttl: int = SCORE_TTL_SECONDS,
) -> bool:
    key = f"reco:scores:{user_id}:{turno}"
    try:
        client = await get_redis()
        await client.set(key, json.dumps(scores), ex=ttl)
        return True
    except RedisError as exc:
        logger.warning("Falha ao gravar scores no Redis (%s): %s", key, exc)
        return False


async def clear_scores() -> int:
    """Invalida scores após um novo treino (batch scoring sob demanda no MVP)."""
    deleted = 0
    try:
        client = await get_redis()
        async for key in client.scan_iter(match="reco:scores:*"):
            deleted += int(await client.delete(key))
    except RedisError as exc:
        logger.warning("Falha ao invalidar scores no Redis: %s", exc)
    return deleted


async def track_event(event_type: str, payload: dict[str, Any]) -> bool:
    try:
        client = await get_redis()
        await client.xadd("events:stream", {"type": event_type, "payload": json.dumps(payload)})
        return True
    except RedisError as exc:
        logger.warning("Falha ao publicar evento no Redis Stream: %s", exc)
        return False
