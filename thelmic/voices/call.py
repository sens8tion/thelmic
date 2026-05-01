"""Call voice — tension.

Fires only from PhraseContext.call_slots (first half of bar, steps 0–7).
Character is shaped by Dimensions.pressure and Dimensions.stability:
  - high pressure + low stability → more calls, louder, overlapping
  - high pressure + high stability → clear, separated calls (Oak character)
  - low pressure → minimal calls
"""

from __future__ import annotations

from thelmic.dimensions import Dimensions, PhraseContext
from thelmic.landscape_map import SignatureRhythm
from thelmic.stream_engine import Intent, StructureFrame
from thelmic.voices import make_intent


class CallIntentStream:
    def intents_for_frame(
        self,
        frame: StructureFrame,
        context: PhraseContext,
        dims: Dimensions,
        sr: SignatureRhythm | None = None,
    ) -> tuple[Intent, ...]:
        # Calls only in GROOVE and CALL_UNRESOLVED states
        if context.phrase_state not in ("GROOVE", "CALL_UNRESOLVED"):
            return ()

        if frame.step_in_bar not in context.call_slots:
            return ()

        # Pressure gates calls: below threshold, calls are withheld
        if dims.pressure < 0.15:
            return ()

        if sr is None:
            return ()
        note     = _call_note(sr, frame.step_in_bar)
        velocity = _velocity(dims.pressure, dims.stability)
        return (make_intent(frame, "call", "call", velocity, 0.12,
                            "signature_call", note, 6),)


def _call_note(sr, step: int) -> int:
    """Call note derived from SignatureRhythm: above hook range."""
    # Calls sit a minor 7th to an octave above the hook
    offset = 10 + (step % 4)
    return sr.root_note + 12 + offset


def _velocity(pressure: float, stability: float) -> int:
    """Higher pressure → louder call; lower stability → more variation."""
    base = 58 + int(pressure * 28)
    return min(92, base)
