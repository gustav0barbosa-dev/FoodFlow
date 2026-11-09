"""Endpoints de métricas do recomendador e do sistema."""

from fastapi import APIRouter, Response

from app.cache.redis_client import get_recommendation_metrics, get_redis

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("/recommendations")
async def recommendation_metrics():
    """Contadores de cache, modelo e popularidade do recomendador."""
    from app.api import metrics as metrics_api

    return await metrics_api.get_recommendation_metrics()


@router.get("")
async def metrics_endpoint():
    """
    Endpoint consumido pelo Prometheus para monitorar o sistema.
    """
    lines = [
        "# HELP recommender_drift_psi Population Stability Index das features do recomendador",
        "# TYPE recommender_drift_psi gauge",
    ]

    redis_conn = await get_redis()
    if redis_conn:
        keys = await redis_conn.keys("drift:psi:*")
        for key in keys:
            feature_name = key.decode("utf-8").replace("drift:psi:", "")
            value = await redis_conn.get(key)
            if value:
                lines.append(
                    f'recommender_drift_psi{{feature="{feature_name}"}} {value.decode("utf-8")}'
                )

    metrics = await get_recommendation_metrics()
    if metrics:
        lines.extend(
            [
                "# HELP recommender_requests_total Total de requisições ao recomendador",
                "# TYPE recommender_requests_total counter",
                f'recommender_requests_total {metrics.get("requests", 0)}',
                "# HELP recommender_cache_hits_total Total de cache hits",
                "# TYPE recommender_cache_hits_total counter",
                f'recommender_cache_hits_total {metrics.get("cache_hits", 0)}',
            ]
        )

    from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

    output = "\n".join(lines) + "\n" + generate_latest().decode("utf-8")
    return Response(content=output, media_type=CONTENT_TYPE_LATEST)
