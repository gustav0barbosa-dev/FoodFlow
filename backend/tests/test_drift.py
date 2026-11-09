import numpy as np
import pytest

from app.services.drift import compute_psi


def test_psi_identical_distributions_returns_zero():
    baseline = [1.0, 2.0, 3.0, 4.0, 5.0] * 10
    current = [1.0, 2.0, 3.0, 4.0, 5.0] * 10
    assert compute_psi(baseline, current) == 0.0


def test_psi_empty_distribution_returns_zero():
    assert compute_psi([], [1.0, 2.0]) == 0.0
    assert compute_psi([1.0, 2.0], []) == 0.0


def test_psi_shifted_distribution_returns_high_value():
    # Baseline centrado em 10, atual centrado em 50 (drift severo)
    baseline = np.random.normal(loc=10, scale=2, size=1000)
    current = np.random.normal(loc=50, scale=2, size=1000)
    psi = compute_psi(baseline, current)
    assert psi > 0.2  # Acima do threshold de alerta


def test_psi_slight_change_returns_low_value():
    # Baseline e atual com médias próximas (drift leve)
    rng = np.random.RandomState(42)
    baseline = rng.normal(loc=10, scale=2, size=1000)
    current = rng.normal(loc=10.5, scale=2, size=1000)
    psi = compute_psi(baseline, current)
    assert psi < 0.2