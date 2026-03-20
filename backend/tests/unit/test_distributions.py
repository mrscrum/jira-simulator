"""Tests for the distribution sampling module."""

import math
import random

import pytest

from app.engine.distributions import (
    fit_lognormal,
    sample_full_time,
    sample_sprint_capacity,
    sample_work_time,
)


class TestFitLognormal:
    def test_symmetric_input(self):
        """When p25 and p99 are symmetric around p50 in log-space."""
        mu, sigma = fit_lognormal(p25=2.0, p50=4.0, p99=32.0)
        assert mu == pytest.approx(math.log(4.0))
        assert sigma > 0

    def test_mu_equals_log_median(self):
        mu, sigma = fit_lognormal(p25=1.0, p50=2.0, p99=10.0)
        assert mu == pytest.approx(math.log(2.0))

    def test_tight_distribution(self):
        """Nearly identical percentiles → sigma near 0."""
        mu, sigma = fit_lognormal(p25=5.0, p50=5.0, p99=5.0)
        assert mu == pytest.approx(math.log(5.0))
        assert sigma == pytest.approx(0.0, abs=1e-10)

    def test_ordered_percentiles_required(self):
        with pytest.raises(ValueError, match="ordered"):
            fit_lognormal(p25=10.0, p50=5.0, p99=20.0)

    def test_positive_values_required(self):
        with pytest.raises(ValueError, match="positive"):
            fit_lognormal(p25=0.0, p50=1.0, p99=5.0)

    def test_sigma_non_negative(self):
        _, sigma = fit_lognormal(p25=1.0, p50=2.0, p99=100.0)
        assert sigma >= 0


class TestSampleFullTime:
    def test_returns_positive(self):
        rng = random.Random(42)
        for _ in range(100):
            val = sample_full_time(1.0, 2.0, 8.0, rng)
            assert val >= 0.1

    def test_reproducibility(self):
        val1 = sample_full_time(1.0, 2.0, 8.0, random.Random(123))
        val2 = sample_full_time(1.0, 2.0, 8.0, random.Random(123))
        assert val1 == val2

    def test_median_approximation(self):
        """Over many samples, median should approximate p50."""
        rng = random.Random(42)
        samples = [sample_full_time(2.0, 4.0, 16.0, rng) for _ in range(5000)]
        median = sorted(samples)[len(samples) // 2]
        assert 3.0 < median < 5.5

    def test_tight_distribution_returns_median(self):
        rng = random.Random(42)
        val = sample_full_time(5.0, 5.0, 5.0, rng)
        assert val == pytest.approx(5.0)


class TestSampleWorkTime:
    def test_within_range(self):
        rng = random.Random(42)
        for _ in range(100):
            val = sample_work_time(2.0, 8.0, rng)
            assert 2.0 <= val <= 8.0

    def test_zero_range(self):
        rng = random.Random(42)
        assert sample_work_time(0.0, 0.0, rng) == 0.0

    def test_exact_range(self):
        """When min == max, always returns that value."""
        rng = random.Random(42)
        assert sample_work_time(3.0, 3.0, rng) == 3.0

    def test_invalid_range(self):
        rng = random.Random(42)
        with pytest.raises(ValueError, match="Invalid"):
            sample_work_time(5.0, 2.0, rng)

    def test_negative_min(self):
        rng = random.Random(42)
        with pytest.raises(ValueError, match="Invalid"):
            sample_work_time(-1.0, 5.0, rng)

    def test_reproducibility(self):
        val1 = sample_work_time(1.0, 10.0, random.Random(99))
        val2 = sample_work_time(1.0, 10.0, random.Random(99))
        assert val1 == val2


class TestSampleSprintCapacity:
    def test_within_range(self):
        rng = random.Random(42)
        for _ in range(100):
            val = sample_sprint_capacity(20, 40, rng)
            assert 20 <= val <= 40

    def test_returns_int(self):
        rng = random.Random(42)
        val = sample_sprint_capacity(10, 50, rng)
        assert isinstance(val, int)

    def test_exact_range(self):
        rng = random.Random(42)
        assert sample_sprint_capacity(30, 30, rng) == 30

    def test_invalid_range(self):
        rng = random.Random(42)
        with pytest.raises(ValueError, match="Invalid"):
            sample_sprint_capacity(50, 20, rng)

    def test_reproducibility(self):
        val1 = sample_sprint_capacity(10, 100, random.Random(77))
        val2 = sample_sprint_capacity(10, 100, random.Random(77))
        assert val1 == val2
