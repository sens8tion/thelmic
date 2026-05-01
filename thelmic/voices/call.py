"""Call voice — tension phrase.

Rules (musical_rules.md — Call/Response Phrase Timing):
  Call fires only in CALL BARS: bars 0-1 (phrase opening) and bars 4 and 12
  (sub-phrase boundaries). Within those bars, fires on steps 0-7 (first half).
  Call must start at sub-phrase boundaries — not scattered through the phrase.

Rules (musical_rules.md — Melodic Note Alignment):
  Default: natural minor palette above root.
  At low stability (Chaos), tension notes (b2, tritone) permitted if approached
  by step and resolved within 2 bars.
"""

from __future__ import annotations

from thelmic.dimensions import Dimensions, PhraseContext
from thelmic.landscape_map import SignatureRhythm
from thelmic.stream_engine import Intent, StructureFrame
from thelmic.voices import make_intent

# Bar positions (0-indexed) where call may fire.
# Call lives in the HOLD sub-phrase (bars 5-12, 0-indexed 4-11), first half of it.
# Hook occupies the phrase opening (bars 0-1) and sub-phrase boundaries (bars 4, 12).
# Call and hook are mutually exclusive — call takes the interior of hold.
_CALL_BARS = frozenset({4, 5, 6, 7})   # first 4 bars of the hold sub-phrase

# Natural minor intervals above root+12 (call sits above hook range)
_MINOR_INTERVALS = (10, 12, 14, 15, 17)   # b7, octave, b9, b10, b11

# Tension intervals for Chaos positions (stability < 0.35)
_TENSION_INTERVALS = (10, 11, 12, 15, 16)  # b7, maj7(tension), oct, b10, b2+oct


class CallIntentStream:
    def intents_for_frame(
        self,
        frame: StructureFrame,
        context: PhraseContext,
        dims: Dimensions,
        sr: SignatureRhythm | None = None,
    ) -> tuple[Intent, ...]:
        if sr is None:
            return ()

        # 4-bar window rule: calls only in designated call bars
        bar_0idx = frame.bar_index - 1   # 0-indexed
        if bar_0idx not in _CALL_BARS:
            return ()

        # Within call bars: first half only (steps 0-7)
        if frame.step_in_bar not in context.call_slots:
            return ()

        # Phrase state gate
        if context.phrase_state not in ("GROOVE", "CALL_UNRESOLVED"):
            return ()

        note     = _call_note(sr, frame.step_in_bar, dims.stability)
        velocity = _velocity(dims.pressure, dims.stability)
        return (make_intent(frame, "call", "call", velocity, 0.12,
                            "signature_call", note, 6),)


def _call_note(sr, step: int, stability: float) -> int:
    """Note selection from musical_rules.md — Melodic Note Alignment.

    Oak/stable: natural minor intervals (consonant, resolved feel).
    Chaos/unstable: tension intervals (b2, tritone) for dissonant energy.
    """
    tension_allowed = stability < 0.35
    intervals = _TENSION_INTERVALS if tension_allowed else _MINOR_INTERVALS
    idx = step % len(intervals)
    return sr.root_note + 12 + intervals[idx]


def _velocity(pressure: float, stability: float) -> int:
    """Rules (musical_rules.md, Velocity Dynamics):
    High stability: melodic peak 95-112, fill 55-75.
    Low stability:  melodic peak 110-127, fill 40-65.
    """
    heat_proxy = 1.0 - stability
    base = int(58 + heat_proxy * 24 + pressure * 20)
    return min(105, max(40, base))
