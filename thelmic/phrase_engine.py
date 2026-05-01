"""Phrase engine — structural authority.

Produces PhraseContext from StructureFrame + Dimensions + archetype selection.

Archetype commitment rule:
  pending_archetype tracks current position (immediate, updates every bank)
  active_archetype  commits only at drop (boundary-committed)
  At is_drop_phrase=True: active = pending for the new phrase
"""

from __future__ import annotations

from thelmic.archetypes import RhythmicArchetype, select_archetype
from thelmic.dimensions import Dimensions, PhraseContext
from thelmic.landscape_map import SignatureRhythm
from thelmic.stream_engine import StructureFrame

# Call/response windows (bar-relative steps)
_CALL_STEPS     = (2, 6)
_RESPONSE_STEPS = (10, 14)


def pending_archetype_for(sr: SignatureRhythm) -> RhythmicArchetype:
    """Select the pending archetype from a SignatureRhythm.

    This is what would commit at the next drop if position stays here.
    """
    return select_archetype(sr.density_bias, sr.syncopation_bias, sr.stability_bias)


def context_for_phrase(
    phrase_start_frame:   StructureFrame,
    dims:                 Dimensions,
    pending_sr:           SignatureRhythm,
    previous_active:      RhythmicArchetype | None,
    is_drop_phrase:       bool,
) -> PhraseContext:
    """Produce PhraseContext for the phrase starting at phrase_start_frame.

    pending_sr:       SignatureRhythm for the current landscape position
    previous_active:  archetype active in the prior phrase (None = first phrase)
    is_drop_phrase:   whether this phrase commits a structural change
    """
    pending = pending_archetype_for(pending_sr)

    # Active archetype: only changes at a drop; otherwise carries forward
    if is_drop_phrase or previous_active is None:
        active = pending
    else:
        active = previous_active

    if is_drop_phrase:
        phrase_state = "DROP"
    elif dims.pressure > 0.6:
        phrase_state = "CALL_UNRESOLVED"
    else:
        phrase_state = "GROOVE"

    structural_change = is_drop_phrase and (previous_active != active)

    return PhraseContext(
        phrase_state=phrase_state,
        call_slots=_CALL_STEPS,
        response_slots=_RESPONSE_STEPS,
        is_drop_phrase=is_drop_phrase,
        phrase_index=phrase_start_frame.phrase_index,
        active_archetype=active,
        pending_archetype=pending,
        timing_anchor_lane="kick",
        structural_change_committed=structural_change,
        drop_prep_active=phrase_start_frame.is_drop_prep,
    )
