"""Distribution sampling for the simulation engine.

Provides pure functions for sampling full-time-in-status (log-normal)
and work-time-in-status (uniform) distributions.
"""

import math
import random

# Z-scores for standard normal distribution
_Z_25 = -0.6745  # 25th percentile
_Z_99 = 2.3263  # 99th percentile

# Minimum sampled time to avoid zero-duration statuses
_MIN_FULL_TIME = 0.1  # hours


def fit_lognormal(p25: float, p50: float, p99: float) -> tuple[float, float]:
    """Fit a log-normal distribution from three percentiles.

    For a log-normal distribution X = exp(N(mu, sigma)):
      - median = exp(mu), so mu = ln(p50)
      - sigma estimated from p25 and p99 for robustness

    Args:
        p25: 25th percentile value in hours (must be > 0)
        p50: 50th percentile (median) value in hours (must be > 0)
        p99: 99th percentile value in hours (must be > 0)

    Returns:
        (mu, sigma) parameters for the log-normal distribution.
    """
    if p25 <= 0 or p50 <= 0 or p99 <= 0:
        raise ValueError(f"All percentiles must be positive: p25={p25}, p50={p50}, p99={p99}")
    if not (p25 <= p50 <= p99):
        raise ValueError(f"Percentiles must be ordered: p25={p25} <= p50={p50} <= p99={p99}")

    mu = math.log(p50)

    # Derive sigma from both tails and average for robustness
    # ln(p25) = mu + Z_25 * sigma  →  sigma = (mu - ln(p25)) / |Z_25|
    # ln(p99) = mu + Z_99 * sigma  →  sigma = (ln(p99) - mu) / Z_99
    sigma_from_p25 = (mu - math.log(p25)) / abs(_Z_25)
    sigma_from_p99 = (math.log(p99) - mu) / _Z_99

    sigma = (sigma_from_p25 + sigma_from_p99) / 2.0

    # Ensure sigma is non-negative (can happen with degenerate inputs)
    sigma = max(sigma, 0.0)

    return mu, sigma


def sample_full_time(
    p25: float, p50: float, p99: float, rng: random.Random,
) -> float:
    """Sample full-time-in-status from a log-normal distribution.

    Args:
        p25: 25th percentile in hours
        p50: 50th percentile (median) in hours
        p99: 99th percentile in hours
        rng: Random instance for reproducibility

    Returns:
        Sampled time in hours, guaranteed >= _MIN_FULL_TIME.
    """
    mu, sigma = fit_lognormal(p25, p50, p99)

    if sigma == 0.0:
        return max(math.exp(mu), _MIN_FULL_TIME)

    z = rng.gauss(0.0, 1.0)
    value = math.exp(mu + sigma * z)
    return max(value, _MIN_FULL_TIME)


def sample_work_time(
    min_hours: float, max_hours: float, rng: random.Random,
) -> float:
    """Sample work-time-in-status from a uniform distribution.

    Args:
        min_hours: Minimum work time in hours (>= 0)
        max_hours: Maximum work time in hours (>= min_hours)
        rng: Random instance for reproducibility

    Returns:
        Sampled time in hours. Returns 0.0 if both min and max are 0.
    """
    if min_hours == 0.0 and max_hours == 0.0:
        return 0.0

    if min_hours < 0 or max_hours < min_hours:
        raise ValueError(
            f"Invalid work time range: min={min_hours}, max={max_hours}"
        )

    return rng.uniform(min_hours, max_hours)


def sample_sprint_capacity(
    min_sp: int, max_sp: int, rng: random.Random,
) -> int:
    """Sample sprint capacity target from a uniform integer distribution.

    Args:
        min_sp: Minimum story points
        max_sp: Maximum story points (>= min_sp)
        rng: Random instance for reproducibility

    Returns:
        Integer capacity target in [min_sp, max_sp].
    """
    if min_sp > max_sp:
        raise ValueError(
            f"Invalid capacity range: min={min_sp}, max={max_sp}"
        )
    return rng.randint(min_sp, max_sp)
