"""Endpoint de resultados do experimento A/B de recomendações."""

from typing import Any

from fastapi import APIRouter

from app.cache.redis_client import get_ab_test_metrics

router = APIRouter(prefix="/experiment", tags=["experiment"])


@router.get("/ab-test", response_model=dict[str, Any])
async def ab_test_results() -> dict[str, Any]:
    """Retorna os resultados acumulados do experimento A/B de recomendações.

    Compara o grupo "personalized" (LightGBM + LoRA) com o grupo "distance"
    (ordenação por distância), mostrando quantas requisições cada grupo recebeu
    e a proporção de tráfego alocado a cada um.
    """
    return await get_ab_test_metrics()
