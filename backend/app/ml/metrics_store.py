"""Persistência do relatório de treino/avaliação do recomendador.

O relatório é gravado ao lado do artefato do modelo (``backend/models``), que
já é montado como volume no Docker Compose. A API apenas lê esse arquivo;
o treino continua sendo uma operação offline.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

REPORT_PATH = Path(__file__).resolve().parents[2] / "models" / "training_metrics.json"


def save_training_report(report: dict[str, Any]) -> Path:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = REPORT_PATH.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    os.replace(temporary, REPORT_PATH)
    logger.info("Relatório de treino salvo em %s", REPORT_PATH)
    return REPORT_PATH


def load_training_report() -> dict[str, Any] | None:
    if not REPORT_PATH.exists():
        return None
    try:
        data = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        logger.warning("Falha ao ler relatório de treino: %s", exc)
        return None
    return data if isinstance(data, dict) else None
