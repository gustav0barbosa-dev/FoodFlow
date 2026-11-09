"""Detecção de drift do recomendador.

Executa o relatório de drift (PSI) para todas as features monitoradas e imprime
o resultado. Pode ser agendado via cron/Task Scheduler para rodar periodicamente.

Uso:
    python scripts/drift_detect.py
    # ou com o módulo do projeto:
    python -m scripts.drift_detect
"""

import asyncio
import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.drift import drift_monitor  # noqa: E402


async def main() -> int:
    report = await drift_monitor.compute_drift_report()

    print(json.dumps(report, indent=2, ensure_ascii=False))

    if report["overall_status"] == "alert":
        print(
            "\n⚠️  Drift detectado em pelo menos uma feature (PSI >= "
            f"{report['psi_threshold_alert']}). Considere retreinar o modelo."
        )
        return 1
    if report["overall_status"] == "warning":
        print(
            "\n⚠️  Drift moderado detectado (PSI >= "
            f"{report['psi_threshold_warning']}). Monitore as features: "
            f"{', '.join(report['warning_features'])}."
        )
    print("\n✅ Sem drift significativo detectado.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
