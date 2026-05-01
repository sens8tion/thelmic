"""Response voice — resolution.

Fires only from PhraseContext.response_slots (second half of bar, steps 8–15).
Requires a call to have fired earlier in the same bar — tracked per phrase.
Subordinate to hook and bass.

A response resolves the tension created by a call. Without a preceding call,
no response fires.
"""

from __future__ import annotations

from thelmic.dimensions import Dimensions, PhraseContext
from thelmic.landscape_map import SignatureRhythm
from thelmic.stream_engine import Intent, StructureFrame
from thelmic.voices import make_intent


class ResponseIntentStream:
    """Stateful: tracks whether a call fired in the current bar."""

    def __init__(self) -> None:
        self._last_call_bar: int = -1

    def reset(self) -> None:
        """Clear per-bank call state. Call at the start of each generate_bank."""
        self._last_call_bar = -1

    def record_call(self, bar_index: int) -> None:
        """Called by the orchestrator when a call fires."""
        self._last_call_bar = bar_index

    def intents_for_frame(
        self,
        frame: StructureFrame,
        context: PhraseContext,
        dims: Dimensions,
        sr: SignatureRhythm | None = None,
    ) -> tuple[Intent, ...]:
        if frame.step_in_bar not in context.response_slots:
            return ()

        # Response requires a call in the same bar
        if self._last_call_bar != frame.bar_index:
            return ()

        # Low pressure → no resolution needed
        if dims.pressure < 0.12:
            return ()

        if sr is None:
            return ()
        note     = _response_note(sr, frame.step_in_bar)
        velocity = _velocity(dims.pressure, dims.stability)
        return (make_intent(frame, "response", "response", velocity, 0.15,
                            "signature_response", note, 6),)


def _response_note(sr, step: int) -> int:
    """Response settles back toward the bass root — resolving tension."""
    # Descending from call range back toward hook range
    offset = 7 + (step % 4)
    return sr.root_note + 12 + offset


def _velocity(pressure: float, stability: float) -> int:
    """Response slightly quieter than call — it's the answer, not the question."""
    base = 52 + int(pressure * 24)
    return min(84, base)
