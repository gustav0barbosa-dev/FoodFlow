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

RECOMMENDATION_METRIC_KEYS: dict[str, str] = {
    "requests": "metrics:reco:requests",
    "cache_hits": "metrics:reco:cache_hits",
    "cache_misses": "metrics:reco:cache_misses",
    "model_scores": "metrics:reco:model_scores",
    "popularity_scores": "metrics:reco:popularity_scores",
    "distance_scores": "metrics:reco:distance_scores",
}

# Chaves de métrica por grupo do experimento A/B.
AB_TEST_METRIC_KEYS: dict[str, str] = {
    "personalized_requests": "metrics:ab:personalized:requests",
    "distance_requests": "metrics:ab:distance:requests",
}


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


async def increment_metrics(*names: str) -> bool:
    """Incrementa contadores de recomendação em um único pipeline."""
    keys = [
        RECOMMENDATION_METRIC_KEYS[name]
        for name in names
        if name in RECOMMENDATION_METRIC_KEYS
    ]
    if not keys:
        return False

    try:
        client = await get_redis()
        async with client.pipeline(transaction=False) as pipeline:
            for key in keys:
                pipeline.incr(key)
            await pipeline.execute()
        return True
    except RedisError as exc:
        logger.warning("Falha ao incrementar métricas no Redis: %s", exc)
        return False


async def get_recommendation_metrics() -> dict[str, Any]:
    """Lê os contadores acumulados e calcula a taxa de acerto do cache."""
    metrics: dict[str, int] = {name: 0 for name in RECOMMENDATION_METRIC_KEYS}

    try:
        client = await get_redis()
        values = await client.mget(list(RECOMMENDATION_METRIC_KEYS.values()))
    except RedisError as exc:
        logger.warning("Falha ao ler métricas do Redis: %s", exc)
        return {"redis_available": False, "cache_hit_rate": 0.0, **metrics}

    for name, value in zip(RECOMMENDATION_METRIC_KEYS, values, strict=True):
        metrics[name] = int(value or 0)

    requests = metrics["requests"]
    hit_rate = round(metrics["cache_hits"] / requests, 4) if requests else 0.0
    return {"redis_available": True, "cache_hit_rate": hit_rate, **metrics}


async def increment_ab_test_metrics(group: str) -> bool:
    """Incrementa o contador de requisições de um grupo do experimento A/B."""
    key = AB_TEST_METRIC_KEYS.get(group)
    if not key:
        return False

    try:
        client = await get_redis()
        await client.incr(key)
        return True
    except RedisError as exc:
        logger.warning("Falha ao incrementar métrica do A/B test (%s): %s", group, exc)
        return False


async def get_ab_test_metrics() -> dict[str, Any]:
    """Lê os contadores acumulados de cada grupo do experimento A/B."""
    metrics: dict[str, int] = {name: 0 for name in AB_TEST_METRIC_KEYS}

    try:
        client = await get_redis()
        values = await client.mget(list(AB_TEST_METRIC_KEYS.values()))
    except RedisError as exc:
        logger.warning("Falha ao ler métricas do A/B test: %s", exc)
        return {"redis_available": False, **metrics}

    for name, value in zip(AB_TEST_METRIC_KEYS, values, strict=True):
        metrics[name] = int(value or 0)

    total = metrics["personalized_requests"] + metrics["distance_requests"]
    personalized_share = (
        round(metrics["personalized_requests"] / total, 4) if total else 0.0
    )
    distance_share = (
        round(metrics["distance_requests"] / total, 4) if total else 0.0
    )

    return {
        "redis_available": True,
        "total_requests": total,
        "personalized_requests": metrics["personalized_requests"],
        "distance_requests": metrics["distance_requests"],
        "personalized_share": personalized_share,
        "distance_share": distance_share,
    }


async def ping_redis() -> bool:
    try:
        client = await get_redis()
        return bool(await client.ping())
    except RedisError as exc:
        logger.warning("Redis indisponível: %s", exc)
        return False
