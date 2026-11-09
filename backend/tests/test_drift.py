import pytest
from app.services.drift import compute_psi


def test_psi_identical_distributions_returns_zero():
    baseline = [1.0, 2.0, 3.0]
    current = [1.0, 2.0, 3.0]
    assert compute_psi(baseline, current) == 0.0


def test_psi_empty_distribution_returns_zero():
    assert compute_psi([], [1.0, 2.0]) == 0.0
    assert compute_psi([1.0, 2.0], []) == 0.0


def test_psi_different_distributions_returns_positive():
    baseline = [1.0, 2.0, 3.0]
    current = [1.0, 2.0, 3.0, 4.0]  # Mudou o tamanho
    assert compute_psi(baseline, current) > 0.0