import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import select

from app.cache.redis_client import get_redis  # <-- Ajuste se o nome for outro
from app.database import AsyncSessionLocal
from app.models import RecommendationLog
from app.services.drift import FEATURE_NAMES, compute_psi

logger = logging.getLogger(__name__)

BASELINE_FILE = Path("app/jobs/baselines/psi_baseline.json")
LATEST_FILE = Path("app/jobs/baselines/psi_latest.json")


async def run_drift_job():
    """
    Job diário que calcula o PSI das features logadas nas últimas 24h
    em comparação com o baseline salvo.
    """
    logger.info("Iniciando job de cálculo de drift...")

    # 1. Carrega o baseline (se existir)
    baseline_data = {}
    if BASELINE_FILE.exists():
        with open(BASELINE_FILE, "r", encoding="utf-8") as f:
            baseline_data = json.load(f)

    async with AsyncSessionLocal() as session:
        # 2. Pega logs das últimas 24h
        cutoff = datetime.now(timezone.utc) - timedelta(days=1)
        stmt = select(RecommendationLog).where(RecommendationLog.created_at >= cutoff)
        result = await session.execute(stmt)
        logs = result.scalars().all()

        if not logs:
            logger.warning("Nenhum log encontrado nas últimas 24h. Abortando.")
            return

        # 3. Extrai as features atuais
        current_data = {feature: [] for feature in FEATURE_NAMES}
        for log in logs:
            for feature in FEATURE_NAMES:
                if feature in log.features:
                    current_data[feature].append(log.features[feature])

        # 4. Calcula PSI por feature
        drift_report = {}
        redis_conn = await get_redis() # Obtém a conexão usando o helper do projeto

        for feature in FEATURE_NAMES:
            current_vals = current_data[feature]
            baseline_vals = baseline_data.get(feature, [])

            if not baseline_vals:
                # Se não há baseline, a primeira execução salva os dados atuais como baseline
                baseline_data[feature] = current_vals
                drift_report[feature] = 0.0
                logger.info(f"Baseline criado para a feature '{feature}'.")
            else:
                psi_score = compute_psi(baseline_vals, current_vals)
                drift_report[feature] = round(psi_score, 4)
                logger.info(f"PSI para '{feature}': {psi_score:.4f}")

                # 5. Salva no Redis (se a conexão não for None, devido à degradação graciosa)
                if redis_conn:
                    try:
                        await redis_conn.set(
                            f"drift:psi:{feature}", 
                            str(psi_score), 
                            ex=7 * 24 * 3600 # TTL de 7 dias
                        )
                        logger.info(f"PSI de '{feature}' salvo no Redis.")
                    except Exception as e:
                        logger.error(f"Falha ao salvar no Redis: {e}")
                else:
                    logger.warning("Redis indisponível. PSI não foi salvo em cache.")

    # 6. Salva o arquivo de baseline e o último relatório
    BASELINE_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    with open(BASELINE_FILE, "w", encoding="utf-8") as f:
        json.dump(baseline_data, f, indent=2)

    with open(LATEST_FILE, "w", encoding="utf-8") as f:
        json.dump(drift_report, f, indent=2)

    logger.info("Job de drift finalizado com sucesso.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    asyncio.run(run_drift_job())