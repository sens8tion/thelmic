"""Dimension engine — compute v1.2 Dimensions from location, movement, and heat.

final_dimensions = f(location, movement, heat)

v1.2 dimensions: stability, pressure, sparsity, release, emphasis.
density is NOT a dimension — it belongs to the archetype pattern.

Heat modifies how base values express themselves.
Heat must NEVER change the archetype selection (identity is location-only).
"""

from __future__ import annotations

import math

from thelmic.dimensions import Dimensions
from thelmic.heat_model import response_curve
from thelmic.landscape_trajectory import LandscapeTrajectory


def positional_sparsity(stability_bias: float) -> float:
    """Sparsity floor set by the landscape position's inherent stability.

    This is the hard floor: instruments withheld by positional sparsity
    do not return until you move to a more stable position.

    stability_bias ≥ 0.70  → 0.0  (full instrumentation)
    stability_bias 0.45–0.70 → 0.0–0.25
    stability_bias 0.25–0.45 → 0.25–0.55
    stability_bias < 0.25   → 0.55–0.80 (deep Chaos floor)
    """
    if stability_bias >= 0.70:
        return 0.0
    if stability_bias >= 0.45:
        t = (0.70 - stability_bias) / 0.25   # 0→1 as stability drops from 0.70 to 0.45
        return t * 0.25
    if stability_bias >= 0.25:
        t = (0.45 - stability_bias) / 0.20
        return 0.25 + t * 0.30
    # Deep Chaos
    t = (0.25 - stability_bias) / 0.25
    return 0.55 + t * 0.25


def compute(trajectory: LandscapeTrajectory, heat: float) -> Dimensions:
    """Derive the full v1.2 Dimensions set from current state."""
    heat = max(0.0, min(1.0, heat))
    h    = response_curve(heat)

    feature = trajectory.active_feature()
    sr      = feature.signature_rhythm

    base_stability = sr.stability_bias
    pressure_base  = trajectory.pressure_base()

    # Stability: hot loosens, cold tightens
    stability = max(0.0, base_stability - h * 0.55)

    # Pressure: amplified by heat (reflects movement urgency, not position)
    pressure = min(1.0, pressure_base * (1.0 + h * 0.8))

    # Sparsity: positional only — which instruments are present is determined by
    # WHERE you are (terrain stability), not HOW FAST you moved there.
    # Movement adds energy, not absence of instruments.
    sparsity = positional_sparsity(base_stability)

    return Dimensions(
        stability=stability,
        pressure=pressure,
        sparsity=sparsity,
        release=0.0,
        emphasis=0.0,
    )


# modulate_for_step, compute_at_drop, compute_post_drop removed — dead code.
# Pression arc logic lives in pression_engine.py.
# Drop/emphasis burst is handled by phrase_arc.py (compute_arc).
