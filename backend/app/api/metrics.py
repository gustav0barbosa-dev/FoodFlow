from typing import Any

from fastapi import APIRouter

from app.cache.redis_client import get_recommendation_metrics

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("/recommendations")
async def recommendation_metrics() -> dict[str, Any]:
    """Contadores de cache, modelo e popularidade desde o último restart."""
    return await get_recommendation_metrics()
