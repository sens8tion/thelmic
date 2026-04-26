"""Behaviour hooks — automatic deformation modulation from transition state.

Maps an active Transition into curve_overrides for apply_deformations().
Each hook is a pure function of (Transition, ForceState) → float in [0, 1].

Merge rule (per amendment 2)
-----------------------------
    result = dict(hook_overrides)
    result.update(manual_overrides)

Hooks are the floor. Manual pressure curves override specific keys only.
A manual curve on cc.filter_cutoff does not suppress ghost_inject hooks.

Key format
----------
Uses the same flat key format as the existing curve_overrides system:
    "ghost_inject"   — deformation target
Future CC targets will use the same string format as CurveEngine:
    "cc:<ch>:<num>"

Adding a new hook
-----------------
1. Write a hook function: (Transition, ForceState) -> float
2. Register it in _HOOKS with its target key
"""

from __future__ import annotations

import math
from typing import Optional

from thelmic.force_engine import ForceState, _clamp
from thelmic.transition_engine import Transition


# ---------------------------------------------------------------------------
# Hook: ghost_inject
# ---------------------------------------------------------------------------

# Velocity threshold above which urgency scaling kicks in.
# velocity is normalised distance-per-bar (clamped 0–1), so 0.15 means
# "travelling more than 15% of the axis per bar" — a moderately fast move.
_VELOCITY_URGENCY_THRESHOLD: float = 0.15

# How much velocity can amplify the hook output (additive, then clamped).
_VELOCITY_URGENCY_SCALE: float = 0.3


def _ghost_inject_hook(transition: Transition, force: ForceState) -> float:
    """Modulate ghost injection intensity during landscape traversal.

    Toward Nott (increasing position):
        Continuous build — p² shape, so tension grows late and hard.
        Ghosts accumulate as the destination approaches rather than
        peaking mid-journey and backing off before impact.

    Toward Oak (decreasing position):
        Quadratic decay — the return settles quickly. Ghosts clear fast
        so the landing feels clean rather than lingering.

    Velocity amplification:
        Fast gestures (velocity > threshold) add urgency on top of the
        base shape. Slow, deliberate moves stay restrained; panic moves
        spike immediately.

    Scaling:
        All shapes are multiplied by force.instability so the hook only
        fires meaningfully when the current force state supports it.
        At low instability (Oak) ghosts stay subdued regardless of direction.
    """
    progress  = transition.progress
    direction = transition.direction
    velocity  = transition.velocity

    if direction == "toward_nott":
        # Late continuous build: low early, rising hard toward arrival
        base = progress ** 2
        base = _clamp(base * force.instability)

    elif direction == "toward_oak":
        # Fast decay: high at start, clears quickly
        base = _clamp((1.0 - progress) ** 2 * force.instability * 0.5)

    else:
        return 0.0

    # Velocity urgency — fast gestures spike the hook regardless of progress
    if velocity > _VELOCITY_URGENCY_THRESHOLD:
        urgency = (velocity - _VELOCITY_URGENCY_THRESHOLD) * _VELOCITY_URGENCY_SCALE
        base = _clamp(base + urgency)

    return base


# ---------------------------------------------------------------------------
# Hook registry
# ---------------------------------------------------------------------------
# Each entry: (target_key, hook_function)
# hook_function: (Transition, ForceState) -> float

_HOOKS: list[tuple[str, object]] = [
    ("ghost_inject", _ghost_inject_hook),
]


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def compute_behaviour_overrides(
    transition: Optional[Transition],
    force: ForceState,
    manual_overrides: dict[str, float],
) -> dict[str, float]:
    """Return merged curve_overrides for apply_deformations().

    Per the architecture amendment:
        result = dict(hook_overrides)   ← hooks first
        result.update(manual_overrides) ← manual wins per key only

    Manual curves on one key do not suppress hooks on other keys.

    Args:
        transition:       Active Transition, or None if no journey in progress.
        force:            Current ForceState — hooks use instability, density, etc.
        manual_overrides: From CurveEngine.projected_overrides() — may be empty.

    Returns:
        dict[str, float] ready to pass as curve_overrides= to
        BankGenerator.generate() / apply_deformations().
    """
    # Start with hook values (only if a transition is active)
    result: dict[str, float] = {}
    if transition is not None and transition.active:
        for key, hook_fn in _HOOKS:
            value = hook_fn(transition, force)
            if value > 0.0:
                result[key] = value

    # Manual overrides win for their specific keys, leave others untouched
    result.update(manual_overrides)
    return result
