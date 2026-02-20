"""Tests for CRPS scoring functions."""

import math

import pytest

from bayesian_quiz.scoring import (
    InvalidStandardDeviationError,
    NonFiniteValueError,
    crps_normal,
    crps_to_points,
)


class TestCrpsNormal:
    def test_perfect_prediction_small_sigma(self):
        """CRPS approaches 0 when mean equals true value and sigma is tiny."""
        assert crps_normal(100.0, 0.001, 100.0) == pytest.approx(0.0, abs=1e-3)

    def test_crps_is_nonnegative(self):
        assert crps_normal(0.0, 1.0, 10.0) >= 0
        assert crps_normal(50.0, 0.1, 50.0) >= 0
        assert crps_normal(-100.0, 50.0, 200.0) >= 0

    def test_wider_sigma_increases_crps_when_centered(self):
        """When mean == true_value, wider sigma means worse (higher) CRPS."""
        narrow = crps_normal(50.0, 1.0, 50.0)
        wide = crps_normal(50.0, 10.0, 50.0)
        assert wide > narrow

    def test_overconfident_wrong_answer_is_worst(self):
        """Tight sigma far from answer produces large CRPS."""
        overconfident = crps_normal(0.0, 0.1, 100.0)
        hedged = crps_normal(0.0, 50.0, 100.0)
        assert overconfident > hedged

    def test_symmetric_around_true_value(self):
        """CRPS is symmetric: overshooting and undershooting by same amount give equal CRPS."""
        above = crps_normal(110.0, 5.0, 100.0)
        below = crps_normal(90.0, 5.0, 100.0)
        assert above == pytest.approx(below)

    def test_known_value_sigma_1_z_0(self):
        """When z=0 (mean==true_value) and sigma=1: CRPS = 1*(0 + 2*phi(0) - 1/sqrt(pi))."""
        phi_0 = 1 / math.sqrt(2 * math.pi)
        expected = 2 * phi_0 - 1 / math.sqrt(math.pi)
        assert crps_normal(5.0, 1.0, 5.0) == pytest.approx(expected)

    def test_scales_linearly_with_sigma_at_z_zero(self):
        """When mean==true_value, CRPS scales linearly with sigma."""
        crps_s1 = crps_normal(0.0, 1.0, 0.0)
        crps_s5 = crps_normal(0.0, 5.0, 0.0)
        assert crps_s5 == pytest.approx(5.0 * crps_s1)

    def test_negative_values(self):
        result = crps_normal(-10.0, 3.0, -7.0)
        assert result >= 0
        assert math.isfinite(result)

    def test_large_z(self):
        """Very wrong prediction still returns a finite result."""
        result = crps_normal(0.0, 1.0, 1000.0)
        assert math.isfinite(result)
        assert result == pytest.approx(1000.0, rel=0.01)

    def test_zero_sigma_raises(self):
        with pytest.raises(InvalidStandardDeviationError):
            crps_normal(0.0, 0.0, 0.0)

    def test_negative_sigma_raises(self):
        with pytest.raises(InvalidStandardDeviationError):
            crps_normal(0.0, -1.0, 0.0)

    def test_nan_input_raises(self):
        with pytest.raises(NonFiniteValueError):
            crps_normal(float("nan"), 1.0, 0.0)

    def test_inf_input_raises(self):
        with pytest.raises(NonFiniteValueError):
            crps_normal(0.0, 1.0, float("inf"))

    def test_inf_sigma_raises(self):
        with pytest.raises(NonFiniteValueError):
            crps_normal(0.0, float("inf"), 0.0)


class TestCrpsToPoints:
    def test_zero_crps_gives_100_points(self):
        assert crps_to_points(0.0, 10.0) == 100.0

    def test_crps_equals_scale(self):
        assert crps_to_points(10.0, 10.0) == pytest.approx(100.0 / math.e)

    def test_crps_exceeds_scale_still_positive(self):
        assert crps_to_points(20.0, 10.0) > 0.0

    def test_large_crps_approaches_zero(self):
        assert crps_to_points(100.0, 10.0) < 0.01

    def test_monotonically_decreasing(self):
        p1 = crps_to_points(1.0, 10.0)
        p2 = crps_to_points(5.0, 10.0)
        p3 = crps_to_points(10.0, 10.0)
        assert p1 > p2 > p3 > 0

    def test_result_is_float(self):
        assert isinstance(crps_to_points(3.0, 10.0), float)
