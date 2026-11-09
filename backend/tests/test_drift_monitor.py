import numpy as np
import pytest

from app.services.drift import (
    PSI_THRESHOLD_ALERT,
    PSI_THRESHOLD_WARNING,
    DriftMonitor,
    compute_psi,
    drift_monitor,
)


class _FakeRedis:
    """Simula o Redis com get/set/rpush/lrange."""

    def __init__(self) -> None:
        self.store: dict[str, object] = {}

    async def get(self, key: str):
        value = self.store.get(key)
        return value if isinstance(value, str) else None

    async def set(self, key: str, value: str, ex: int | None = None) -> bool:
        self.store[key] = value
        return True

    async def rpush(self, key: str, *values: str) -> int:
        current = self.store.get(key, [])
        if not isinstance(current, list):
            current = []
        current.extend(values)
        self.store[key] = current
        return len(current)

    async def lrange(self, key: str, start: int, end: int):
        current = self.store.get(key, [])
        if not isinstance(current, list):
            return []
        if end == -1:
            return list(current[start:])
        return list(current[start : end + 1])

    async def ltrim(self, key: str, start: int, end: int) -> bool:
        current = self.store.get(key, [])
        if not isinstance(current, list):
            return True
        if end == -1:
            self.store[key] = current[start:]
        else:
            self.store[key] = current[start : end + 1]
        return True

    async def ping(self) -> bool:
        return True


@pytest.fixture
def fake_redis():
    return _FakeRedis()


@pytest.fixture
def monitor(fake_redis):
    async def _fake_get_redis():
        return fake_redis

    async def _fake_ping() -> bool:
        return True

    return DriftMonitor(
        feature_names=["feature_a", "feature_b"],
        get_redis_callable=_fake_get_redis,
        ping_callable=_fake_ping,
    )


class TestComputePsi:
    def test_identical_distributions_returns_zero(self):
        baseline = [1.0, 2.0, 3.0, 4.0, 5.0] * 10
        current = [1.0, 2.0, 3.0, 4.0, 5.0] * 10
        assert compute_psi(baseline, current) == 0.0

    def test_empty_distribution_returns_zero(self):
        assert compute_psi([], [1.0, 2.0]) == 0.0
        assert compute_psi([1.0, 2.0], []) == 0.0

    def test_shifted_distribution_returns_high_value(self):
        rng = np.random.RandomState(42)
        baseline = rng.normal(loc=10, scale=2, size=1000).tolist()
        current = rng.normal(loc=50, scale=2, size=1000).tolist()
        psi = compute_psi(baseline, current)
        assert psi > 0.2

    def test_slight_change_returns_low_value(self):
        rng = np.random.RandomState(42)
        baseline = rng.normal(loc=10, scale=2, size=1000).tolist()
        current = rng.normal(loc=10.5, scale=2, size=1000).tolist()
        psi = compute_psi(baseline, current)
        assert psi < 0.2


class TestDriftMonitorBaseline:
    async def test_save_and_get_baseline(self, monitor, fake_redis):
        values = [1.0, 2.0, 3.0, 4.0, 5.0] * 20

        assert await monitor.save_baseline("feature_a", values) is True
        payload = await monitor.get_baseline("feature_a")
        assert payload is not None
        assert payload["n"] == 100
        assert "breakpoints" in payload
        assert "counts" in payload

    async def test_save_baseline_empty_values(self, monitor, fake_redis):
        assert await monitor.save_baseline("feature_a", []) is False


class TestDriftMonitorServing:
    async def test_record_and_get_serving_values(self, monitor, fake_redis):
        await monitor.record_serving("feature_a", 1.5)
        await monitor.record_serving("feature_a", 2.5)
        values = await monitor.get_current_values("feature_a")
        assert values == [1.5, 2.5]


class TestDriftMonitorFeatureDrift:
    async def test_no_data_returns_no_data(self, monitor, fake_redis):
        result = await monitor.compute_feature_drift("feature_a")
        assert result["status"] == "no_data"
        assert result["psi"] == 0.0

    async def test_identical_distribution_returns_ok(self, monitor, fake_redis):
        values = [1.0, 2.0, 3.0, 4.0, 5.0] * 20

        await monitor.save_baseline("feature_a", values)
        for v in values:
            await monitor.record_serving("feature_a", v)
        result = await monitor.compute_feature_drift("feature_a")
        assert result["status"] == "ok"
        assert result["psi"] < 0.1

    async def test_shifted_distribution_returns_alert(self, monitor, fake_redis):
        rng = np.random.RandomState(42)
        baseline = rng.normal(loc=10, scale=2, size=1000).tolist()
        current = rng.normal(loc=50, scale=2, size=1000).tolist()

        await monitor.save_baseline("feature_a", baseline)
        for v in current:
            await monitor.record_serving("feature_a", v)
        result = await monitor.compute_feature_drift("feature_a")
        assert result["status"] == "alert"
        assert result["psi"] > 0.2

    def test_classify_psi_thresholds(self):
        from app.services.drift import _classify_psi

        assert _classify_psi(0.05) == "ok"
        assert _classify_psi(0.1) == "warning"
        assert _classify_psi(0.15) == "warning"
        assert _classify_psi(0.2) == "alert"
        assert _classify_psi(0.5) == "alert"


class TestDriftMonitorReport:
    async def test_report_structure(self, monitor, fake_redis):
        report = await monitor.compute_drift_report()

        assert report["redis_available"] is True
        assert report["overall_status"] in ("ok", "warning", "alert")
        assert "features" in report
        assert report["features_monitored"] == 2
        assert report["psi_threshold_warning"] == PSI_THRESHOLD_WARNING
        assert report["psi_threshold_alert"] == PSI_THRESHOLD_ALERT

        for feature in report["features"]:
            assert "feature" in feature
            assert "psi" in feature
            assert "status" in feature
            assert feature["status"] in ("ok", "warning", "alert", "no_data")

    async def test_report_with_alert(self, monitor, fake_redis):
        rng = np.random.RandomState(42)
        baseline = rng.normal(loc=10, scale=2, size=1000).tolist()
        current = rng.normal(loc=50, scale=2, size=1000).tolist()

        await monitor.save_baseline("feature_a", baseline)
        for v in current:
            await monitor.record_serving("feature_a", v)

        report = await monitor.compute_drift_report()
        assert report["overall_status"] == "alert"
        assert report["features_with_alert"] >= 1
        assert "feature_a" in report["alert_features"]

    def test_drift_monitor_global_instance(self):
        """Verifica que a instância global usa as funções reais do Redis."""
        assert drift_monitor._get_redis is not None
        assert drift_monitor._ping_redis is not None
