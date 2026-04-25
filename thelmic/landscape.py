"""Territory definitions and axis → force mappings."""

from __future__ import annotations

from thelmic.force_engine import ForceState, _lerp

# ------------------------------------------------------------------
# Territory profiles (starting defaults, tuned by ear)
# ------------------------------------------------------------------

OAK_PROFILE = ForceState(
    anticipation=0.2,
    release_pressure=0.1,
    instability=0.05,
    density=0.6,
    control_vs_chaos=0.1,
)

CHAOS_PROFILE = ForceState(
    anticipation=0.7,
    release_pressure=0.6,
    instability=0.8,
    density=0.75,
    control_vs_chaos=0.8,
)

NOTT_PROFILE = ForceState(
    anticipation=0.1,
    release_pressure=0.0,
    instability=0.2,
    density=0.5,
    control_vs_chaos=0.3,
)

# Axis layout: 0.0 = Oak, 0.5 = Chaos, 1.0 = Nott
_OAK_CENTRE = 0.0
_CHAOS_CENTRE = 0.5
_NOTT_CENTRE = 1.0

_TERRITORY_BOUNDARIES = {
    "oak": (0.0, 0.33),
    "chaos": (0.33, 0.67),
    "nott": (0.67, 1.0),
}


def territory_at(position: float) -> str:
    for name, (lo, hi) in _TERRITORY_BOUNDARIES.items():
        if lo <= position <= hi:
            return name
    return "nott"  # clamp edge


def axis_to_force(position: float) -> ForceState:
    """Map a 0.0–1.0 axis position to a ForceState via piecewise lerp."""
    if position <= 0.5:
        # Oak → Chaos
        t = position / 0.5
        return OAK_PROFILE.lerp(CHAOS_PROFILE, t)
    else:
        # Chaos → Nott
        t = (position - 0.5) / 0.5
        return CHAOS_PROFILE.lerp(NOTT_PROFILE, t)
