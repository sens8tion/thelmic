"""Ghost 32nd note hits — ornamental layer.

Ghost hits land at half-step positions (between 1/16th notes) to create
the physical feel of a live drummer or tight programmed groove.

Rules (from musical_rules.md):
  - velocity < 40 always
  - no structural authority
  - must not create new anchor positions
  - gated by sparsity > 0.60 and stability
  - pattern deterministic from SignatureRhythm.base_pattern_seed

High stability  → predictable positions (consistent groove feel)
Low stability   → irregular positions (loose, almost dragging feel)
Heat            → scales density and velocity ceiling

References: DnB ghost snares, techno hi-hat ghosts, live drummer feel,
            house rim-shot ghosts on the 'e' and 'ah' of each beat.
"""

from __future__ import annotations

from typing import Optional

from thelmic.bank_generator import CLOSED_HAT_NOTE
from thelmic.dimensions import Dimensions, PhraseContext
from thelmic.landscape_map import SignatureRhythm
from thelmic.stream_engine import Intent, StructureFrame
from thelmic.voices import make_intent


class Ghost32ndStream:
    """Generates ghost hits at half-step (32nd note) positions."""

    def intents_for_frame(
        self,
        frame: StructureFrame,
        context: Optional[PhraseContext] = None,
        dims: Optional[Dimensions] = None,
        sr: Optional[SignatureRhythm] = None,
    ) -> tuple[Intent, ...]:
        if dims is None or sr is None:
            return ()

        # Gate: high sparsity or drop_prep suppress ghosts entirely
        if dims.sparsity > 0.60 or frame.is_drop_prep:
            return ()

        # Heat-based density gate: cold=rare ghosts, hot=common ghosts
        # heat_proxy 0=cold/stable → threshold 0.85 (rare), 1=hot/unstable → threshold 0.50 (common)
        heat_proxy = 1.0 - dims.stability
        ghost_prob_threshold = 0.85 - heat_proxy * 0.35   # cold=0.85, hot=0.50
        # Deterministic "random" based on seed + step to stay reproducible
        step_hash = (sr.base_pattern_seed ^ (frame.step_in_bar * 2654435761)) & 0xFFFFFFFF
        step_prob = (step_hash % 1000) / 1000.0
        if step_prob > ghost_prob_threshold:
            return ()

        # Gate: no ghosts in drop/pre-drop phrase
        if context and context.is_drop_phrase:
            return ()

        # Determine ghost positions from pattern_seed + stability
        ghost_steps = self._ghost_steps(sr.base_pattern_seed, dims.stability)

        if frame.step_in_bar not in ghost_steps:
            return ()

        velocity = self._velocity(dims, sr)
        if velocity < 1:
            return ()

        # Ghost hits use step + 0.5 for 32nd note timing
        # We encode this in the payload; _resolved_to_midi_event uses it
        return (Intent(
            step=frame.global_step,
            instrument="hat",
            role="ghost",
            velocity=velocity,
            duration=0.018,
            phrase_index=frame.phrase_index,
            subphrase_index=frame.subphrase_index,
            priority=1,
            source="note_generation_chain",
            reason="ghost_32nd",
            intent_id=f"note_generation_chain:{frame.global_step}:hat:ghost_32nd",
            payload={
                "note":          CLOSED_HAT_NOTE,
                "global_step":   frame.global_step,
                "musical_step":  frame.musical_step + 0.5,   # half-step = 32nd note
                "bar_index":     frame.bar_index,
                "step_in_bar":   frame.step_in_bar,
                "phrase_index":  frame.phrase_index,
                "is_drop":       frame.is_drop,
                "is_drop_prep":  frame.is_drop_prep,
            },
        ),)

    def _ghost_steps(self, seed: int, stability: float) -> frozenset[int]:
        """Deterministic ghost step positions within a 16-step bar.

        High stability → ghost hits on predictable off-beats (the 'e' and 'ah'
        of beats 1 and 3 = steps 1, 9 in common 4/4).
        Low stability  → more irregular positioning derived from seed.
        """
        if stability > 0.60:
            # Predictable: 'e' of beat 1 and beat 3
            return frozenset({1, 9})
        if stability > 0.35:
            # Moderate: add 'ah' of beats 2 and 4
            return frozenset({1, 5, 9, 13})
        # Low stability: seed-derived irregular placement
        rng = seed ^ 0xDEAD1234
        steps: set[int] = set()
        for _ in range(4):
            rng = (rng * 1664525 + 1013904223) & 0xFFFFFFFF
            s = rng % 16
            # Avoid anchor positions (0, 4, 8, 12) — ghosts are off-beat only
            if s % 4 != 0:
                steps.add(s)
        return frozenset(steps) if steps else frozenset({1, 9})

    def _velocity(self, dims: Dimensions, sr: SignatureRhythm) -> int:
        """Ghost velocity: always < 40, scales with stability inverse.

        Low stability (Chaos) → louder ghosts (more aggressive groove)
        High stability (Oak)  → quieter ghosts (subtle background texture)
        Heat scales the ceiling.
        """
        contrast = 1.0 - dims.stability
        base = 14 + int(contrast * 22)   # 14 (Oak) → 36 (deep Chaos)
        # Sparsity reduces ghost presence
        base = int(base * (1.0 - dims.sparsity * 0.4))
        return max(1, min(38, base))
