import math
from typing import Any

import numpy as np

# Features que vamos monitorar.
# No PR 1 logamos "list_length" e "strategy".
# Vamos monitorar o tamanho da lista e a proporção de cache hits (futuramente).
FEATURE_NAMES: list[str] = ["list_length"]


def compute_psi(baseline: np.ndarray | list[float], current: np.ndarray | list[float], bins: int = 10) -> float:
    """
    Calcula o Population Stability Index (PSI) entre duas distribuições.
    PSI < 0.1: Nenhuma mudança significativa.
    PSI 0.1 - 0.2: Mudança moderada, requer atenção.
    PSI > 0.2: Mudança significativa, modelo deve ser retreinado.
    """
    baseline = np.array(baseline, dtype=float)
    current = np.array(current, dtype=float)

    if len(baseline) == 0 or len(current) == 0:
        return 0.0

    # Define os bins baseados no baseline
    breakpoints = np.linspace(
        min(baseline.min(), current.min()),
        max(baseline.max(), current.max()),
        bins + 1
    )

    def get_distribution(data):
        counts, _ = np.histogram(data, bins=breakpoints)
        # Evita divisão por zero adicionando um pequeno epsilon
        return (counts + 1e-6) / len(data)

    expected = get_distribution(baseline)
    actual = get_distribution(current)

    # Fórmula do PSI: sum((actual - expected) * ln(actual / expected))
    psi_value = np.sum((actual - expected) * np.log(actual / expected))
    return float(max(0.0, psi_value)) # Garante que não retorne negativo por erro de float