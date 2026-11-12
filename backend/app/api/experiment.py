"""Endpoint de resultados do experimento A/B de recomendações."""

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache.redis_client import get_ab_test_metrics
from app.database import get_db
from app.services.experiment import get_experiment_metrics

router = APIRouter(prefix="/experiment", tags=["experiment"])


@router.get("/ab-test", response_model=dict[str, Any])
async def ab_test_results(
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Retorna as métricas do experimento A/B calculadas a partir do banco.

    Compara baseline, personalizado (LightGBM + afinidade) e distância. Os
    contadores do Redis são incluídos apenas como diagnóstico de requisições;
    a fonte das taxas é ``user_restaurant_interactions``.
    """
    metrics = await get_experiment_metrics(session)
    metrics["request_counters"] = await get_ab_test_metrics()
    return metrics
