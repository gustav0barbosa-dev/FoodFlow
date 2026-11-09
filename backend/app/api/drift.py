"""Endpoint de monitoramento de drift de features do recomendador."""

from typing import Any

from fastapi import APIRouter

from app.services.drift import drift_monitor

router = APIRouter(prefix="/drift", tags=["drift"])


@router.get("", response_model=dict[str, Any])
async def drift_report() -> dict[str, Any]:
    """Retorna o relatório de drift de todas as features monitoradas.

    Compara a distribuição de treino (baseline) com a distribuição observada
    em serving usando o Population Stability Index (PSI).

    Status por feature:
    - ok: PSI < 0.1 (sem mudança significativa)
    - warning: 0.1 <= PSI < 0.2 (mudança moderada, requer atenção)
    - alert: PSI >= 0.2 (mudança significativa, retreinar modelo)
    """
    return await drift_monitor.compute_drift_report()
