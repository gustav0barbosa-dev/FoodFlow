from typing import Any
import math

# Features que vamos monitorar no futuro.
# Por enquanto, vamos registrar apenas o turno e o tamanho da lista recomendada.
FEATURE_NAMES: list[str] = ["turno_encoded", "list_length"]


def compute_psi(baseline: list[float], current: list[float], bins: int = 10) -> float:
    """
    Calcula o Population Stability Index (PSI) entre duas distribuições.
    Stub inicial: retorna 0.0 se as listas forem iguais, e um valor fictício caso contrário.
    No PR 2 (feat/drift-job) implementaremos a fórmula matemática real.
    """
    if not baseline or not current:
        return 0.0
    if baseline == current:
        return 0.0
    return 0.15  # Valor fictício para simular drift moderado nos testes