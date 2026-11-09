"""Monitoramento de drift de features do recomendador.

Compara a distribuição das features no treino (baseline) com a distribuição
observada em serving (predições recentes) usando o Population Stability Index
(PSI). Quando o PSI de uma feature ultrapassa o threshold de alerta, o modelo
deve ser retreinado.

Os dados são armazenados no Redis com degradação graciosa: se o Redis estiver
indisponível, o monitoramento segue sem erro, mas sem persistência.
"""

import json
import logging
import math
from typing import Any

import numpy as np

from app.cache.redis_client import get_redis, ping_redis
from app.core.constants import TURNOS

logger = logging.getLogger(__name__)

# Features do modelo que serão monitoradas para drift.
FEATURE_NAMES: list[str] = [
    "total_orders",
    "has_dietary_preferences",
    "restaurant_rating",
    "restaurant_review_count",
    "restaurant_delivery_fee",
    "restaurant_delivery_time_avg",
    "is_manha",
    "is_tarde",
    "is_noite",
    "is_madrugada",
    "manha_avg_value",
    "manha_avg_fee",
    "manha_count",
    "manha_is_top_restaurant",
    "tarde_avg_value",
    "tarde_avg_fee",
    "tarde_count",
    "tarde_is_top_restaurant",
    "noite_avg_value",
    "noite_avg_fee",
    "noite_count",
    "noite_is_top_restaurant",
    "madrugada_avg_value",
    "madrugada_avg_fee",
    "madrugada_count",
    "madrugada_is_top_restaurant",
]

# Número máximo de amostras recentes mantidas por feature para serving.
SERVING_WINDOW_SIZE = 1000

# Thresholds do PSI.
PSI_THRESHOLD_WARNING = 0.1  # Mudança moderada, requer atenção
PSI_THRESHOLD_ALERT = 0.2    # Mudança significativa, retreinar modelo

# Chaves Redis.
BASELINE_KEY = "drift:baseline:{feature}"
CURRENT_KEY = "drift:current:{feature}"
BASELINE_STATS_KEY = "drift:baseline_stats:{feature}"


def compute_psi(
    baseline: np.ndarray | list[float],
    current: np.ndarray | list[float],
    bins: int = 10,
) -> float:
    """Calcula o Population Stability Index (PSI) entre duas distribuições.

    PSI < 0.1: nenhuma mudança significativa.
    PSI 0.1 - 0.2: mudança moderada, requer atenção.
    PSI > 0.2: mudança significativa, modelo deve ser retreinado.
    """
    baseline = np.array(baseline, dtype=float)
    current = np.array(current, dtype=float)

    if len(baseline) == 0 or len(current) == 0:
        return 0.0

    # Define os bins baseados no range combinado (baseline define os breakpoints).
    breakpoints = np.linspace(
        min(baseline.min(), current.min()),
        max(baseline.max(), current.max()),
        bins + 1,
    )

    def get_distribution(data: np.ndarray) -> np.ndarray:
        counts, _ = np.histogram(data, bins=breakpoints)
        # Evita divisão por zero adicionando um pequeno epsilon.
        return (counts + 1e-6) / len(data)

    expected = get_distribution(baseline)
    actual = get_distribution(current)

    # Fórmula do PSI: sum((actual - expected) * ln(actual / expected)).
    psi_value = np.sum((actual - expected) * np.log(actual / expected))
    return float(max(0.0, psi_value))


def _classify_psi(psi: float) -> str:
    if psi >= PSI_THRESHOLD_ALERT:
        return "alert"
    if psi >= PSI_THRESHOLD_WARNING:
        return "warning"
    return "ok"


class DriftMonitor:
    """Monitora drift de features entre treino (baseline) e serving."""

    def __init__(
        self,
        feature_names: list[str] | None = None,
        psi_threshold_warning: float = PSI_THRESHOLD_WARNING,
        psi_threshold_alert: float = PSI_THRESHOLD_ALERT,
        serving_window_size: int = SERVING_WINDOW_SIZE,
        get_redis_callable=None,
        ping_callable=None,
    ) -> None:
        self.feature_names = feature_names or list(FEATURE_NAMES)
        self.psi_threshold_warning = psi_threshold_warning
        self.psi_threshold_alert = psi_threshold_alert
        self.serving_window_size = serving_window_size
        self._get_redis = get_redis_callable or get_redis
        self._ping_redis = ping_callable or ping_redis

    # ------------------------------------------------------------------
    # Baseline (distribuição de treino)
    # ------------------------------------------------------------------

    async def save_baseline(self, feature_name: str, values: list[float]) -> bool:
        """Salva o histograma de referência (baseline) de uma feature."""
        if not values:
            return False

        arr = np.array(values, dtype=float)
        breakpoints = np.linspace(arr.min(), arr.max(), 11)
        counts, _ = np.histogram(arr, bins=breakpoints)

        payload = {
            "breakpoints": breakpoints.tolist(),
            "counts": counts.tolist(),
            "n": len(values),
            "min": float(arr.min()),
            "max": float(arr.max()),
        }

        try:
            client = await self._get_redis()
            await client.set(
                BASELINE_KEY.format(feature=feature_name),
                json.dumps(payload),
            )
            await client.set(
                BASELINE_STATS_KEY.format(feature=feature_name),
                json.dumps({"min": float(arr.min()), "max": float(arr.max()), "n": len(values)}),
            )
            logger.info("Baseline de drift salvo para '%s' (n=%d).", feature_name, len(values))
            return True
        except Exception as exc:  # Redis fora: monitoramento degrada graciosamente.
            logger.warning("Falha ao salvar baseline de drift para '%s': %s", feature_name, exc)
            return False

    async def get_baseline(self, feature_name: str) -> dict[str, Any] | None:
        try:
            client = await self._get_redis()
            raw = await client.get(BASELINE_KEY.format(feature=feature_name))
            if not raw:
                return None
            return json.loads(raw)
        except Exception as exc:
            logger.warning("Falha ao ler baseline de drift para '%s': %s", feature_name, exc)
            return None

    # ------------------------------------------------------------------
    # Serving (distribuição atual em predições)
    # ------------------------------------------------------------------

    async def record_serving(self, feature_name: str, value: float) -> bool:
        """Acumula um valor observado em serving para uma feature."""
        try:
            client = await self._get_redis()
            key = CURRENT_KEY.format(feature=feature_name)
            await client.rpush(key, json.dumps({"value": float(value)}))
            await client.ltrim(key, -self.serving_window_size, -1)
            return True
        except Exception as exc:
            logger.warning("Falha ao registrar serving de drift para '%s': %s", feature_name, exc)
            return False

    async def get_current_values(self, feature_name: str) -> list[float]:
        try:
            client = await self._get_redis()
            key = CURRENT_KEY.format(feature=feature_name)
            raw = await client.lrange(key, 0, -1)
            if not raw:
                return []
            values = []
            for item in raw:
                try:
                    values.append(float(json.loads(item)["value"]))
                except (ValueError, KeyError, TypeError):
                    continue
            return values
        except Exception as exc:
            logger.warning("Falha ao ler valores atuais de drift para '%s': %s", feature_name, exc)
            return []

    # ------------------------------------------------------------------
    # Relatório de drift
    # ------------------------------------------------------------------

    async def compute_feature_drift(
        self,
        feature_name: str,
        bins: int = 10,
    ) -> dict[str, Any]:
        """Calcula o PSI e o status de uma feature."""
        baseline_payload = await self.get_baseline(feature_name)
        current_values = await self.get_current_values(feature_name)

        if baseline_payload is None or not current_values:
            return {
                "feature": feature_name,
                "psi": 0.0,
                "status": "no_data",
                "baseline_n": None,
                "current_n": len(current_values),
                "threshold_warning": self.psi_threshold_warning,
                "threshold_alert": self.psi_threshold_alert,
            }

        breakpoints = baseline_payload["breakpoints"]
        baseline_counts = np.array(baseline_payload["counts"], dtype=float)
        baseline_n = baseline_payload["n"]

        # Distribuição do baseline (já normalizada).
        expected = (baseline_counts + 1e-6) / baseline_n

        # Distribuição atual usando os mesmos breakpoints do baseline.
        current_arr = np.array(current_values, dtype=float)
        current_counts, _ = np.histogram(current_arr, bins=breakpoints)
        actual = (current_counts + 1e-6) / len(current_arr)

        psi_value = float(np.sum((actual - expected) * np.log(actual / expected)))
        psi_value = max(0.0, psi_value)

        return {
            "feature": feature_name,
            "psi": round(psi_value, 6),
            "status": _classify_psi(psi_value),
            "baseline_n": baseline_n,
            "current_n": len(current_values),
            "threshold_warning": self.psi_threshold_warning,
            "threshold_alert": self.psi_threshold_alert,
        }

    async def compute_drift_report(self) -> dict[str, Any]:
        """Calcula o relatório de drift para todas as features monitoradas."""
        results: list[dict[str, Any]] = []
        overall_status = "ok"
        alert_features: list[str] = []
        warning_features: list[str] = []

        redis_available = await self._ping_redis()

        for feature_name in self.feature_names:
            feature_result = await self.compute_feature_drift(feature_name)
            results.append(feature_result)

            status = feature_result["status"]
            if status == "alert":
                alert_features.append(feature_name)
                overall_status = "alert"
            elif status == "warning" and overall_status != "alert":
                warning_features.append(feature_name)
                overall_status = "warning"

        return {
            "redis_available": redis_available,
            "overall_status": overall_status,
            "psi_threshold_warning": self.psi_threshold_warning,
            "psi_threshold_alert": self.psi_threshold_alert,
            "features_monitored": len(self.feature_names),
            "features_with_alert": len(alert_features),
            "features_with_warning": len(warning_features),
            "alert_features": alert_features,
            "warning_features": warning_features,
            "features": results,
        }


drift_monitor = DriftMonitor()
