"""Pression engine — per-step and per-bar CC value computation.

Pression lanes are the semantic CC output of Thelmic's musical dimensions.
They tell the DAW what the music is about to do (pressure, sparsity, etc.)
at per-step resolution so external instruments can respond in real time.

Rules: musical_rules.md — Pression Lane Dynamics.

This module is the single authority for pression value computation.
server.py calls it; it does not import from server.py.
"""

from __future__ import annotations

import math
from typing import Optional


def compute_bar(bar: int, n_bars: int, phrases_until_drop: int,
                dims, heat: float, is_post_drop: bool = False) -> dict:
    """Compute pression values for one bar within a phrase (0-127 range).

    Rules (musical_rules.md — Pression Lane Dynamics):
    - PRESSURE builds toward 127 at drop; resets to 20 then rebuilds post-drop
    - SPARSITY climbs as instrumentation thins; snaps to 0 at drop
    - STABILITY collapses pre-drop, snaps to 120 at drop, settles to groove
    - RELEASE stays dry during build, bursts at drop, decays post-drop
    - EMPHASIS closes pre-drop (filter down), opens at drop, decays
    """
    t = bar / max(n_bars - 1, 1)   # 0→1 over the phrase

    if is_post_drop:
        return {
            "pressure":  int(20 + t * 50),
            "sparsity":  int(t * 60),
            "stability": int(120 - t * 30),
            "release":   int(127 - t * 92),
            "emphasis":  int(127 - t * 57),
        }

    if phrases_until_drop == 0:
        return {
            "pressure":  min(127, int(60 + t * 67)),
            "sparsity":  min(127, int(70 + t * 57)),
            "stability": max(0,   int(100 - t * 100)),
            "release":   0 if bar >= 14 else 35,
            "emphasis":  max(0,   int(80 - t * 80)),
        }
    elif phrases_until_drop == 1:
        return {
            "pressure":  int(50 + t * 30),
            "sparsity":  int(60 + t * 20),
            "stability": int(100 - t * 20),
            "release":   35,
            "emphasis":  int(70 - t * 20),
        }
    else:
        # Groove: steady values from current terrain dimensions
        return {
            "pressure":  int(dims.pressure  * 70 + 30),
            "sparsity":  int(dims.sparsity  * 70 + 30),
            "stability": int(dims.stability * 40 + 70),
            "release":   35,
            "emphasis":  int(60 + heat * 20),
        }


def compute_step(step_in_bar: int, bar_pression: dict,
                 kick_steps: frozenset, snare_steps: frozenset) -> dict[str, float]:
    """Per-step (0-15) pression expression within a bar.

    Envelope shapes driven by distance to last kick/snare, metrical hierarchy,
    and archetype event grid. Decay rates tuned for 174 BPM hard dance.

    Returns values [0, 1] (caller multiplies by 127 for MIDI).
    """
    s         = step_in_bar
    hit_steps = kick_steps | snare_steps

    # Steps since last hit (backward distance, wrapping)
    last_hit = min(((s - h) % 16) for h in hit_steps) if hit_steps else 16

    # Metrical hierarchy weight
    if s in {0, 8}:
        metro = 1.00      # beats 1 and 3
    elif s in {4, 12}:
        metro = 0.75      # beats 2 and 4
    elif s % 2 == 0:
        metro = 0.50      # even 8th notes
    else:
        metro = 0.25      # off-beat 16ths

    bp = bar_pression

    # PRESSURE — peaks on kick, decays with half-life ~2.5 steps
    kick_on  = 1.0 if s in kick_steps else 0.0
    decay_p  = math.exp(-last_hit / 2.5)
    base_p   = 64 + 32 * metro
    pressure = base_p * decay_p + kick_on * 30
    pressure = max(40, min(127, int(pressure + bp.get("pressure", 64) * 0.3)))

    # STABILITY — high on beats, dips on off-beats
    stability = 100 * metro + 20 * math.exp(-last_hit / 3.0)
    stability = max(30, min(120, int(stability * (bp.get("stability", 90) / 90))))

    # SPARSITY — inversely dense around kick/snare; opens on off-beats
    density_pull = math.exp(-last_hit / 2.0)
    sparsity     = 90 - 60 * density_pull
    sparsity     = max(20, min(100, int(sparsity * (bp.get("sparsity", 70) / 70))))

    # RELEASE — blooms 1-2 steps AFTER a hit (reverb tail); dry on the hit
    if s in hit_steps:
        release = 20
    else:
        tail_offset = max(0, last_hit - 1)
        release     = 20 + 80 * math.exp(-tail_offset / 4.0)
    release = max(15, min(110, int(release * (bp.get("release", 35) / 35 + 0.1))))

    # EMPHASIS — metrical energy + kick punch; dip before beat 3 for tension
    pre_beat3_dip = -20 if s == 7 else 0
    emphasis      = 50 + 55 * metro * math.exp(-last_hit / 3.5) + pre_beat3_dip
    emphasis      = max(30, min(127, int(emphasis * (bp.get("emphasis", 70) / 70))))

    return {
        "stability": stability / 127,
        "pressure":  pressure  / 127,
        "sparsity":  sparsity  / 127,
        "release":   release   / 127,
        "emphasis":  emphasis  / 127,
    }
