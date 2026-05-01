"""Voice intent streams.

Each voice module exposes one class with one method:
    intents_for_frame(frame: StructureFrame) -> tuple[Intent, ...]

In Phase C the signature will expand to:
    intents_for_frame(frame, context: PhraseContext, dims: Dimensions) -> tuple[Intent, ...]
"""

from __future__ import annotations

from thelmic.stream_engine import Intent, StructureFrame


def make_intent(
    frame:      StructureFrame,
    instrument: str,
    role:       str,
    velocity:   int,
    duration:   float,
    reason:     str,
    note:       int,
    priority:   int,
) -> Intent:
    """Construct a fully-provenanced Intent from a StructureFrame."""
    return Intent(
        step=frame.global_step,
        instrument=instrument,
        role=role,
        velocity=velocity,
        duration=duration,
        phrase_index=frame.phrase_index,
        subphrase_index=frame.subphrase_index,
        priority=priority,
        source="note_generation_chain",
        reason=reason,
        intent_id=f"note_generation_chain:{frame.global_step}:{instrument}:{reason}",
        payload={
            "note":         note,
            "global_step":  frame.global_step,
            "musical_step": frame.musical_step,
            "bar_index":    frame.bar_index,
            "step_in_bar":  frame.step_in_bar,
            "phrase_index": frame.phrase_index,
            "is_drop":      frame.is_drop,
            "is_drop_prep": frame.is_drop_prep,
        },
    )
