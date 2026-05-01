"""Central musical interfaces: Dimensions and PhraseContext — v1.2 contract.

Dimensions = f(location, movement, heat)
PhraseContext = f(StructureFrame stream, Dimensions, archetype)

These are defined once here and consumed by all voices.

Dimension model (v1.2)
----------------------
  stability  — from landscape position; governs deformation allowed
  pressure   — from movement + trajectory; drives anticipation mechanisms
  sparsity   — derived from pressure; governs controlled event removal
  release    — at-drop signal; normally ~0, spikes at drop boundary
  emphasis   — post-drop signal; normally ~0, brief burst after drop

density is NOT an independent dimension per v1.2 rules. It is a property
of the active archetype's pattern (anchor density), varied by sparsity.
"""

from __future__ import annotations

from dataclasses import dataclass
from thelmic.archetypes import RhythmicArchetype


@dataclass(frozen=True)
class Dimensions:
    """v1.2 musical dimensions — all derived from landscape + movement + heat."""
    stability: float   # [0, 1] — position-derived; high = stable, low = unstable
    pressure:  float   # [0, 1] — movement-derived; drives anticipation mechanisms
    sparsity:  float   # [0, 1] — derived from pressure; gates non-anchor events
    release:   float   # [0, 1] — at-drop: sparsity clears, archetype restores
    emphasis:  float   # [0, 1] — post-drop: velocity reinforcement, brief


@dataclass(frozen=True)
class PhraseContext:
    """Structural phrase authority — what the phrase is doing.

    active_archetype:   the pattern currently playing (changes only at drop)
    pending_archetype:  the pattern queued for the next drop (tracks position live)

    Musical material (which notes) comes from active_archetype.
    Energy (how loud, how thin) comes from Dimensions.
    """
    phrase_state:              str               # GROOVE | CALL_UNRESOLVED | RESPONSE_RESOLVED | DROP
    call_slots:                tuple[int, ...]
    response_slots:            tuple[int, ...]
    is_drop_phrase:            bool
    phrase_index:              int
    active_archetype:          RhythmicArchetype
    pending_archetype:         RhythmicArchetype  # queued; commits at next drop
    timing_anchor_lane:        str               # e.g. "kick"
    structural_change_committed: bool
    drop_prep_active:          bool
