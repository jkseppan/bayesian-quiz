"""CRPS scoring for normal distribution predictions."""

import math


class InvalidStandardDeviationError(ValueError):
    """Raised when sigma is not positive."""


class NonFiniteValueError(ValueError):
    """Raised when an input value is not finite."""


def _validate_finite(*values: float) -> None:
    for v in values:
        if not math.isfinite(v):
            raise NonFiniteValueError(f"Non-finite value: {v}")


def crps_normal(mean: float, stdev: float, true_value: float) -> float:
    """Closed-form CRPS for a normal distribution N(mean, stdev) at true_value.

    CRPS = σ * (z * (2Φ(z) - 1) + 2φ(z) - 1/√π)
    where z = (y - μ) / σ, Φ is standard normal CDF, φ is standard normal PDF.
    """
    _validate_finite(mean, stdev, true_value)
    if stdev <= 0:
        raise InvalidStandardDeviationError(f"stdev must be positive, got {stdev}")

    z = (true_value - mean) / stdev
    phi_z = math.exp(-z * z / 2) / math.sqrt(2 * math.pi)
    big_phi_z = 0.5 * (1 + math.erf(z / math.sqrt(2)))

    return stdev * (z * (2 * big_phi_z - 1) + 2 * phi_z - 1 / math.sqrt(math.pi))


def crps_to_points(crps: float, scale: float) -> float:
    """Convert CRPS (lower-is-better) to points (higher-is-better) on a 0-100 scale."""
    return 100.0 * math.exp(-crps / scale)
