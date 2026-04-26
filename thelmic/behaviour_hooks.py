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

def _ghost_inject_hook(transition: Transition, force: ForceState) -> float:
    """Modulate ghost injection intensity during landscape traversal.

    Toward Nott (increasing position):
        Half-sine arc over progress — builds through the journey then
        releases as the destination approaches. Scaled by instability so
        the hook only fires meaningfully when the force state supports it.

    Toward Oak (decreasing position):
        Fast quadratic decay — the return should feel clean and settling.
        Ghosts fade quickly rather than lingering.

    At rest (no active transition): returns 0.0, hook is suppressed.
    """
    progress  = transition.progress
    direction = transition.direction

    if direction == "toward_nott":
        arc = math.sin(math.pi * progress)   # 0 → peak at 0.5 → 0
        return _clamp(arc * force.instability)

    if direction == "toward_oak":
        decay = (1.0 - progress) ** 2
        return _clamp(decay * force.instability * 0.5)

    return 0.0


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
