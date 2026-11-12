"""Cache Redis dos resultados de restaurantes próximos (OpenStreetMap)."""

from __future__ import annotations

import json
import logging
from typing import Any

from redis.exceptions import RedisError

from app.cache.redis_client import get_redis
from app.core.config import settings

logger = logging.getLogger(__name__)

CACHE_PREFIX = "nearby:osm:v1"


def build_cache_key(
    lat: float,
    lon: float,
    radius: int,
    category: str | None = None,
) -> str:
    """Chave estável para a região consultada.

    As coordenadas são arredondadas (~111 m) para reaproveitar resultados
    quando o usuário se move pouco, sem reutilizar dados de outra região.
    """
    return (
        f"{CACHE_PREFIX}:{lat:.3f}:{lon:.3f}:"
        f"{radius}:{category or 'all'}"
    )


async def get_nearby(key: str) -> list[dict[str, Any]] | None:
    """Lê resultados do Redis; qualquer falha degrada para cache miss."""
    try:
        client = await get_redis()
        raw = await client.get(key)
    except RedisError as exc:
        logger.warning("Falha ao ler cache OSM (%s): %s", key, exc)
        return None

    if not raw:
        return None

    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError) as exc:
        logger.warning("Cache OSM inválido (%s): %s", key, exc)
        return None

    if not isinstance(parsed, list):
        return None

    return [item for item in parsed if isinstance(item, dict)]


async def set_nearby(key: str, restaurants: list[dict[str, Any]]) -> bool:
    """Grava resultados no Redis com TTL configurável."""
    ttl = max(1, int(settings.overpass_cache_ttl_seconds))

    try:
        client = await get_redis()
        await client.set(
            key,
            json.dumps(restaurants, ensure_ascii=False),
            ex=ttl,
        )
        return True
    except RedisError as exc:
        logger.warning("Falha ao gravar cache OSM (%s): %s", key, exc)
        return False
