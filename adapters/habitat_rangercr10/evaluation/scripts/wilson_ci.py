#!/usr/bin/env python3
# ################################
# VLN adapt: Wilson score interval for binomial SR (no external deps)
# ################################
"""Wilson (score) 95% CI for success rate."""

from __future__ import annotations

import math
from typing import Tuple


def wilson_ci(successes: int, n: int, z: float = 1.959963984540054) -> Tuple[float, float, float]:
    """Return (p_hat, lo, hi). Empty n → (nan, nan, nan)."""
    if n <= 0:
        return (float("nan"), float("nan"), float("nan"))
    p = successes / n
    z2 = z * z
    denom = 1.0 + z2 / n
    center = (p + z2 / (2.0 * n)) / denom
    half = (z / denom) * math.sqrt(p * (1.0 - p) / n + z2 / (4.0 * n * n))
    return (p, max(0.0, center - half), min(1.0, center + half))
