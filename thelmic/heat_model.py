"""Heat model — response curve and behaviour mappings.

Heat modulates expression and energy only.
It never alters terrain identity, location, or signature rhythms.
"""

from __future__ import annotations

import math

INERTIA_K: float = 0.08   # lerp coefficient per ~20 ms tick; valid range 0.05–0.20


def response_curve(raw: float) -> float:
    """Non-linear 3-zone response: stable → expressive → unstable.

    0.0–0.3  stable:     slow quadratic start, minimal effect
    0.3–0.7  expressive: high sensitivity via smoothstep
    0.7–1.0  unstable:   rapid exponential escalation
    """
    raw = max(0.0, min(1.0, raw))
    if raw < 0.3:
        t = raw / 0.3
        return 0.15 * (t * t)
    elif raw < 0.7:
        t = (raw - 0.3) / 0.4
        s = t * t * (3.0 - 2.0 * t)
        return 0.15 + 0.55 * s
    else:
        t = (raw - 0.7) / 0.3
        denom = 1.0 - math.exp(-3.5)
        return 0.70 + 0.30 * (1.0 - math.exp(-3.5 * t)) / denom


def mappings(applied: float) -> dict:
    """Return the behaviour mappings derived from applied heat.  Each ∈ [0, 1]."""
    r = response_curve(applied)
    return {
        "mutation_depth":       r,
        "timing_deviation":     r * r,
        "density_variance":     max(0.0, (r - 0.1) / 0.9),
        "pressure_curve_shape": 1.0 - math.exp(-4.0 * r),
        "silence_behaviour":    r ** 0.7,
    }
