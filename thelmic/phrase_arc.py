"""Phrase arc — automatic musical arc per phrase.

Two independent arcs that run from the phrase clock, not from user input:

Arc 1 — Post-drop release (intra-phrase)
  Bars 1–2 of every new phrase: full energy burst (emphasis spike)
  Decays to zero over first 32 steps after drop boundary

Arc 2 — Pre-drop anticipation (cross-phrase)
  Driven by phrases_until_drop via anticipation_engine
  Sparsity rises, instrumentation withholds, toward minimum of 1 tick/bar

Neither arc is overrideable by user position or heat changes.
Heat scales the depth/intensity of both arcs, not their shape.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


# Emphasis decays over this many steps after the drop boundary
_EMPHASIS_DECAY_STEPS = 32


@dataclass(frozen=True)
class ArcDimensions:
    """Dimension offsets applied on top of base Dimensions per frame."""
    emphasis:        float   # [0, 1] — post-drop energy burst; 0 normally
    sparsity_offset: float   # [0, 1] — pre-drop withholding addition; 0 normally


def compute_arc(
    musical_step:        int,
    is_drop_phrase:      bool,
    phrases_until_drop:  int,
    heat:                float,
) -> ArcDimensions:
    """Compute the arc dimensions for a single step.

    musical_step:        0–255 within the current bank
    is_drop_phrase:      True = this bank is a drop phrase
    phrases_until_drop:  how many phrases until the next planned drop
    heat:                [0, 1] — scales depth of both arcs
    """
    heat = max(0.0, min(1.0, heat))

    # ── Arc 1: post-drop release burst ───────────────────────────────────
    if is_drop_phrase and musical_step < _EMPHASIS_DECAY_STEPS:
        t        = musical_step / _EMPHASIS_DECAY_STEPS
        # Smooth cubic decay: fast at start, trails off
        emphasis = (1.0 - t) ** 2 * (1.0 + heat * 0.5)
    else:
        emphasis = 0.0

    # ── Arc 2: pre-drop anticipation ──────────────────────────────────────
    # sparsity_offset builds over the phrase before a drop.
    # Heat scales how deep the withholding goes.
    sparsity_offset = _anticipation_sparsity(
        musical_step, phrases_until_drop, heat
    )

    return ArcDimensions(
        emphasis=min(1.0, emphasis),
        sparsity_offset=sparsity_offset,
    )


def _anticipation_sparsity(
    musical_step: int, phrases_until_drop: int, heat: float,
) -> float:
    """Sparsity offset driven by drop proximity.

    phrases_until_drop >= 2 : no withholding
    phrases_until_drop == 1 : light withholding begins in second half of phrase
    phrases_until_drop == 0 : deep withholding from bar 5 onward,
                               maximum by final bars
    """
    if phrases_until_drop >= 2:
        return 0.0

    # Scale depth with heat: cold = gentle, hot = aggressive
    depth = 0.25 + heat * 0.55   # 0.25–0.80

    if phrases_until_drop == 1:
        # Light withholding only in the second half of the phrase (step 128+)
        if musical_step < 128:
            return 0.0
        t = (musical_step - 128) / 128   # 0→1 over second half
        return depth * 0.4 * t           # max ~32% of depth

    # phrases_until_drop == 0 — this is the final phrase before the drop
    # Withholding starts at bar 5 (step 64) and intensifies
    if musical_step < 64:
        return 0.0
    t = (musical_step - 64) / (256 - 64)   # 0→1 from bar 5 to end
    return min(depth, depth * t * 1.2)     # climbs to full depth by final bar
