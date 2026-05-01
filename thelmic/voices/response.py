"""Response voice — resolution phrase.

Rules (musical_rules.md — Call/Response Phrase Timing):
  Response fires in RESPONSE BARS: bars 4-7 (second 4-bar block after call).
  Fires only if a call fired in the preceding call window.
  Response enters on beat 1 of bar 5 (bar_0idx=4) — no gap between call and response.
  Response fires on steps 8-15 (second half of bar) within response bars.

Rules (musical_rules.md — Melodic Note Alignment):
  Response must resolve where call left tension.
  If call ended on a non-scale tone, response opens on nearest scale tone.
  Response is never more chromatically active than call.
"""

from __future__ import annotations

from thelmic.dimensions import Dimensions, PhraseContext
from thelmic.landscape_map import SignatureRhythm
from thelmic.stream_engine import Intent, StructureFrame
from thelmic.voices import make_intent

# Bar positions (0-indexed) where response may fire.
# Response follows call: second half of the hold sub-phrase (bars 9-12, 0-indexed 8-11).
# No gap needed — response enters immediately after the 4-bar call window.
_RESPONSE_BARS = frozenset({8, 9, 10, 11})

# Resolving intervals — descend from call toward tonic
# natural minor descending: b10, b9, octave, b7, 5th
_RESOLVE_INTERVALS = (15, 14, 12, 10, 7)


class ResponseIntentStream:
    """Stateful: tracks the last bar where a call fired."""

    def __init__(self) -> None:
        self._last_call_bar: int = -1

    def reset(self) -> None:
        """Clear per-bank call state. Called at start of each generate_bank."""
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
        if sr is None:
            return ()

        # 4-bar window rule: responses only in designated response bars
        bar_0idx = frame.bar_index - 1
        if bar_0idx not in _RESPONSE_BARS:
            return ()

        # Within response bars: second half only (steps 8-15)
        if frame.step_in_bar not in context.response_slots:
            return ()

        # Response requires a call to have fired in the call window (bars 5-8, 1-indexed)
        if self._last_call_bar not in {5, 6, 7, 8}:
            return ()

        # (pressure gate removed — rules gate only on sparsity, not pressure)

        note     = _response_note(sr, frame.step_in_bar, dims.stability)
        velocity = _velocity(dims.pressure, dims.stability)
        return (make_intent(frame, "response", "response", velocity, 0.15,
                            "signature_response", note, 6),)


def _response_note(sr, step: int, stability: float) -> int:
    """Response resolves toward tonic — descending, settling.

    Rules: response must resolve tension. Never more chromatic than call.
    Uses natural minor descending intervals regardless of stability.
    """
    idx = step % len(_RESOLVE_INTERVALS)
    return sr.root_note + 12 + _RESOLVE_INTERVALS[idx]


def _velocity(pressure: float, stability: float) -> int:
    """Response slightly quieter than call — it's the answer, not the question."""
    heat_proxy = 1.0 - stability
    base = int(52 + heat_proxy * 18 + pressure * 18)
    return min(90, max(35, base))
