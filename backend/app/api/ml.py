"""Endpoint somente leitura das métricas de treino do modelo."""

from typing import Any

from fastapi import APIRouter

from app.ml.metrics_store import load_training_report
from app.ml.recommender import recommender

router = APIRouter(prefix="/ml", tags=["ml"])


@router.get("/metrics", response_model=dict[str, Any])
async def training_metrics() -> dict[str, Any]:
    """Retorna o último relatório de treino/avaliação persistido.

    Se ainda não houve treino, devolve ``available=False`` em vez de métricas
    artificiais. O endpoint não dispara treinamento.
    """
    report = load_training_report()
    if report is None:
        return {
            "available": False,
            "message": (
                "Nenhum relatório de treino encontrado. Execute "
                "`python -m app.ml.train --source db` (ou `--source seed`) no "
                "diretório backend."
            ),
            "model_loaded": recommender.model is not None,
        }

    return {
        "available": True,
        "model_loaded": recommender.model is not None,
        "loaded_model_version": recommender.metadata.get("model_version"),
        **report,
    }
