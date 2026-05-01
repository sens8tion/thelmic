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


def modulate_for_step(base: Dimensions, musical_step: int) -> Dimensions:
    """Return dims modulated by sub-phrase position within the bank.

    Sub-phrase layout (fixed 4+8+4 bars):
      build   steps   0–63   → sparsity suppressed; pressure builds
      hold    steps  64–191  → stable, consistent
      release steps 192–255  → sparsity rises toward drop; pressure eases

    This gives audible intra-phrase evolution without changing the archetype.
    """
    _BUILD_END  =  64   # 4 bars × 16 steps
    _HOLD_END   = 192   # 12 bars × 16 steps
    _BANK_END   = 256

    if musical_step < _BUILD_END:
        # Build: pressure climbs, stability slightly loosens, sparsity low.
        # Pressure crossing 0.15 unlocks calls; peak pressure by end of build.
        t        = musical_step / _BUILD_END
        pressure = min(1.0, base.pressure + 0.15 + t * 0.35)   # minimum 0.15
        stability = max(0.0, base.stability - t * 0.15)          # loosen slightly
        sparsity  = base.sparsity * 0.2                          # minimal thinning
        return Dimensions(stability=stability, pressure=pressure,
                          sparsity=sparsity, release=0.0, emphasis=0.0)

    if musical_step < _HOLD_END:
        # Hold: pressure settles, stability recovers, pattern tightens.
        t         = (musical_step - _BUILD_END) / (_HOLD_END - _BUILD_END)
        pressure  = max(base.pressure, base.pressure + 0.15 * (1.0 - t))
        stability = min(1.0, base.stability + 0.10)
        return Dimensions(stability=stability, pressure=pressure,
                          sparsity=base.sparsity * 0.3,
                          release=0.0, emphasis=0.0)

    # Release: pressure falls, sparsity rises (velocity-based — events stay
    # but get quieter), stability tightens for the final approach.
    t         = (musical_step - _HOLD_END) / (_BANK_END - _HOLD_END)
    sparsity  = min(0.35, base.sparsity + t * 0.40)   # capped safely below gate
    pressure  = max(0.0, base.pressure - t * 0.15)
    stability = min(1.0, base.stability + t * 0.20)
    return Dimensions(stability=stability, pressure=pressure,
                      sparsity=sparsity, release=0.0, emphasis=0.0)


def compute_at_drop(trajectory: LandscapeTrajectory, heat: float) -> Dimensions:
    """Dimensions for the drop step itself — release spikes, emphasis begins."""
    base = compute(trajectory, heat)
    return Dimensions(
        stability=base.stability,
        pressure=base.pressure,
        sparsity=0.0,       # sparsity clears at drop
        release=1.0,        # release fires
        emphasis=0.8,       # emphasis begins
    )


def compute_post_drop(
    trajectory: LandscapeTrajectory,
    heat: float,
    steps_since_drop: int,
) -> Dimensions:
    """Dimensions decaying from drop emphasis back to normal over ~16 steps."""
    base = compute(trajectory, heat)
    decay = max(0.0, 1.0 - steps_since_drop / 12.0)
    return Dimensions(
        stability=base.stability,
        pressure=base.pressure,
        sparsity=base.sparsity * (1.0 - decay * 0.8),  # gradual return
        release=0.0,
        emphasis=decay * 0.8,
    )
