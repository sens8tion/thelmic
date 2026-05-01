"""Kick voice — archetype-driven, anchor-guaranteed.

Fires all kick anchor steps defined by the active archetype.
Anchors are ALWAYS present — sparsity must not remove them.
"""

from __future__ import annotations

from typing import Optional

from thelmic.archetypes import PATTERNS
from thelmic.bank_generator import KICK_NOTE
from thelmic.dimensions import Dimensions, PhraseContext
from thelmic.stream_engine import Intent, StructureFrame
from thelmic.voices import make_intent


class KickIntentStream:
    def intents_for_frame(
        self,
        frame: StructureFrame,
        context: Optional[PhraseContext] = None,
        dims: Optional[Dimensions] = None,
    ) -> tuple[Intent, ...]:
        if frame.is_drop:
            return (make_intent(frame, "kick", "timing_anchor", 124, 0.08,
                                "drop_anchor", KICK_NOTE, 10),)
        if frame.is_drop_prep:
            if frame.step_in_bar in (0, 8):
                return (make_intent(frame, "kick", "timing_anchor", 108, 0.07,
                                    "compressed_kick_anchor", KICK_NOTE, 10),)
            return ()

        pattern = PATTERNS[context.active_archetype] if context else None
        anchor_steps = pattern.kick_steps if pattern else frozenset({0, 8})

        emphasis = dims.emphasis if dims else 0.0
        pressure = dims.pressure if dims else 0.0

        # Anticipation kick at step 15 (pre-beat 1): hard techno / pressure technique
        # One extra event per bar — legal mutation under high pressure
        if frame.step_in_bar == 15 and pressure > 0.65:
            ant_vel = self._velocity(15, anchor_steps, dims, emphasis * 0.5)
            return (make_intent(frame, "kick", "timing_anchor", ant_vel, 0.05,
                                "anticipation_kick", KICK_NOTE, 9),)

        if frame.step_in_bar not in anchor_steps:
            return ()

        velocity = self._velocity(frame.step_in_bar, anchor_steps, dims, emphasis)
        return (make_intent(frame, "kick", "timing_anchor", velocity, 0.08,
                            "archetype_kick", KICK_NOTE, 10),)

    def _velocity(self, step: int, anchors: frozenset[int], dims, emphasis: float) -> int:
        stability = dims.stability if dims else 0.5
        heat_proxy = 1.0 - stability   # 0=cold/stable, 1=hot/unstable

        # Cold: compressed 90-100 (mechanical, uniform feel).
        # Hot: extreme contrast — beat-1 at 127, off-beats stay lower.
        #
        # Formula: each position has a cold base and a hot base.
        # Velocity interpolates linearly between them via heat_proxy.
        if step == 0:
            # Beat 1 anchor: cold=92, hot=127
            v = int(92 + heat_proxy * 35)
        elif step in {4, 8, 12}:
            # Quarter-note kicks: cold=90, hot=110
            v = int(90 + heat_proxy * 20)
        else:
            # Off-beat / syncopated: cold=88, hot=94 (modest — stays controlled)
            v = int(88 + heat_proxy * 6)

        # Emphasis post-drop: everything hits harder
        v = int(v * (1.0 + emphasis * 0.20))

        return max(60, min(127, v))
