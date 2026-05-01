"""Snare voice — archetype-driven backbeat with drop-aware fills.

Pre-drop: generates varied snare fills derived from the signature rhythm seed.
These can range from tight rolls (compression, tightening toward drop) to
loose patterns with intentional dropped hits (dissolution, slackening).

Rules (musical_rules.md — Percussive Removal and Reintroduction):
- Snare thinned 2–4 bars before drop
- Snare anchors removed last (steps 4, 12 in 4/4)
- Grid reminder role filled by hat in final bars; snare may disappear entirely
- Compression mode: snare may subdivide (16th ghost rolls)
- Dissolution mode: snare pattern fragmented, some hits dropped
"""

from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from thelmic.archetypes import PATTERNS
from thelmic.bank_generator import SNARE_NOTE
from thelmic.dimensions import Dimensions, PhraseContext
from thelmic.landscape_map import SignatureRhythm
from thelmic.stream_engine import Intent, StructureFrame
from thelmic.voices import make_intent

if TYPE_CHECKING:
    from thelmic.anticipation_engine import AnticipationState


class SnareIntentStream:
    def intents_for_frame(
        self,
        frame: StructureFrame,
        context: Optional[PhraseContext] = None,
        dims: Optional[Dimensions] = None,
        sr: Optional[SignatureRhythm] = None,
        ant: Optional["AnticipationState"] = None,
    ) -> tuple[Intent, ...]:
        stability = dims.stability if dims else 0.5
        emphasis  = dims.emphasis  if dims else 0.0

        # Anticipation gate: ant may suppress snare entirely or thin to anchors
        if ant is not None and not ant.snare_allowed:
            # Snare removed in final pre-drop bars — silence
            return ()

        # drop_prep handled by anticipation state above; legacy drop_prep kept
        # only if no anticipation state supplied
        if frame.is_drop_prep and ant is None:
            if frame.step_in_bar == 12:
                return (make_intent(frame, "snare", "backbeat", 78, 0.05,
                                    "drop_prep_backbeat_reference", SNARE_NOTE, 8),)
            return ()

        pattern      = PATTERNS[context.active_archetype] if context else None
        anchor_steps = pattern.snare_steps if pattern else frozenset({4, 12})

        # Pre-drop fill mode: ant mode != groove means we're in anticipation
        if ant is not None and ant.mode != "groove":
            return self._anticipation_fill(
                frame, anchor_steps, stability, emphasis, ant, sr
            )

        intents: list[Intent] = []

        # Anchor steps — always fire (core rules: snare anchors are mandatory)
        if frame.step_in_bar in anchor_steps:
            velocity = self._velocity(stability, emphasis, ghost=False)
            intents.append(make_intent(frame, "snare", "backbeat", velocity, 0.06,
                                       "archetype_snare", SNARE_NOTE, 8))

        # Ghost note just before beat 2 — only at low stability (Chaos feel)
        elif frame.step_in_bar == 2 and stability < 0.35:
            velocity = self._velocity(stability, emphasis, ghost=True)
            intents.append(make_intent(frame, "snare", "backbeat", velocity, 0.03,
                                       "ghost_snare", SNARE_NOTE, 3))

        return tuple(intents)

    def _anticipation_fill(
        self,
        frame: StructureFrame,
        anchor_steps: frozenset,
        stability: float,
        emphasis: float,
        ant: "AnticipationState",
        sr: Optional[SignatureRhythm],
    ) -> tuple[Intent, ...]:
        """Varied pre-drop snare fill.

        Compression mode: tightening roll — snare subdivides toward drop.
        Dissolution mode: fragmented fill with deterministic dropped hits.

        Both are deterministic from (sr.base_pattern_seed + musical_step).
        """
        step     = frame.step_in_bar
        seed     = sr.base_pattern_seed if sr else 0
        mode     = ant.mode

        if "compression" in mode:
            return self._compression_fill(frame, step, anchor_steps, stability, emphasis, seed)
        else:
            return self._dissolution_fill(frame, step, anchor_steps, stability, emphasis, seed)

    def _compression_fill(
        self, frame, step, anchor_steps, stability, emphasis, seed
    ) -> tuple[Intent, ...]:
        """Tightening snare roll: progressively adds ghost hits toward drop.

        The snare roll gets denser as bars_until_drop decreases. This is the
        "snare stutter" typical of hardstyle, hard house, and hardcore builds.
        """
        musical_step = frame.musical_step

        # Anchor steps always fire in compression (they anchor the grid)
        if step in anchor_steps:
            vel = self._velocity(stability, emphasis, ghost=False)
            return (make_intent(frame, "snare", "backbeat", vel, 0.05,
                                "comp_snare_anchor", SNARE_NOTE, 8),)

        # Add ghost rolls: deterministic from seed + position
        # Density increases as musical_step approaches bank end (bar 16)
        bar_abs = musical_step // 16  # 0-15
        fill_threshold = max(9, 14 - bar_abs)  # starts sparse, tightens
        roll_hash = ((musical_step * 17 + seed * 7 + step * 3) * 2654435761) & 0xFFFF
        if roll_hash % 16 < fill_threshold:
            return ()   # not this step

        # Ghost roll hit
        vel = self._velocity(stability, emphasis, ghost=True)
        vel = max(20, int(vel * (0.6 + bar_abs * 0.025)))   # grows louder toward drop
        return (make_intent(frame, "snare", "fill", vel, 0.02,
                            "comp_snare_roll", SNARE_NOTE, 3),)

    def _dissolution_fill(
        self, frame, step, anchor_steps, stability, emphasis, seed
    ) -> tuple[Intent, ...]:
        """Fragmented snare with deterministic dropped hits.

        The pattern is algorithmically irregular — some hits missing, some
        doubled. This creates the "unsettled" feel before a Chaos drop.
        """
        musical_step = frame.musical_step

        # Anchor steps: may be thinned in dissolution (irregular gaps)
        if step in anchor_steps:
            # Drop some anchor hits deterministically (creates the "dropped hit" feel)
            drop_hash = ((musical_step * 31 + seed * 13) * 2654435761) & 0xFFFF
            bar_abs = musical_step // 16
            # More drops as bars approach the drop
            drop_threshold = max(0, 3 - bar_abs // 3)   # 3 drops early, 0 near drop
            if drop_hash % 16 < drop_threshold:
                return ()   # deliberately drop this anchor hit
            vel = self._velocity(stability, emphasis, ghost=False)
            return (make_intent(frame, "snare", "backbeat", vel, 0.05,
                                "dis_snare_anchor", SNARE_NOTE, 8),)

        # Off-beat hits: sparse and irregular — the dissolution feel
        fill_hash = ((musical_step * 7 + seed * 19 + step * 11) * 2654435761) & 0xFFFF
        if fill_hash % 24 != 0:   # ~4% chance per step
            return ()

        vel = self._velocity(stability, emphasis, ghost=True)
        return (make_intent(frame, "snare", "fill", vel, 0.02,
                            "dis_snare_ghost", SNARE_NOTE, 3),)

    def _velocity(self, stability: float, emphasis: float, ghost: bool) -> int:
        """Rules (musical_rules.md, Velocity Dynamics):
        High stability: anchor 95–112, fill 55–75.
        Low stability:  anchor 110–127, fill 40–65.
        """
        heat_proxy = 1.0 - stability
        if ghost:
            # Fill/ghost: cold=68, hot=50 (recede)
            base = int(68 - heat_proxy * 18)
        else:
            # Anchor: cold=82, hot=118 (rules: anchor 95–112 stable, 110–127 unstable)
            base = int(82 + heat_proxy * 36)
        v = int(base * (1.0 + emphasis * 0.18))
        return max(15, min(120, v))
