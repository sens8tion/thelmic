"""Rhythmic archetype definitions — v1.2 contract.

Patterns are taken verbatim from musical_rules.md.
Anchor steps (kick and snare x-marks) are mandatory and must always fire.
Hat is split into closed (CH) and open (OH) — separate instruments, different roles.
  CH: tight click, drives rhythm, fills the groove
  OH: accent/lift, sustains longer, never on kick beats
"""

from __future__ import annotations

from enum import Enum
from dataclasses import dataclass


class RhythmicArchetype(str, Enum):
    HALF_STEP         = "half_step"
    TWO_STEP          = "two_step"
    SHUFFLED_TWO_STEP = "shuffled_two_step"
    STUTTER           = "stutter"
    ROLLING           = "rolling"
    BREAKBEAT_HARDCORE = "breakbeat_hardcore"
    AMEN              = "amen"
    FOUR_ON_THE_FLOOR = "four_on_the_floor"
    HAPPY_HARDCORE    = "happy_hardcore"
    GABBER            = "gabber"


@dataclass(frozen=True)
class ArchetypePattern:
    """Canonical 16-step pattern for one archetype.

    Open and closed hats are separate instruments:
      closed_hat_steps: tight click, rhythmic drive — fills the groove
      open_hat_steps:   accent/lift, longer sustain — never on kick beats
    Steps must not appear in both sets.
    hat_steps = closed | open (all positions where any hat fires).
    """
    archetype:         RhythmicArchetype
    kick_steps:        frozenset[int]
    snare_steps:       frozenset[int]
    closed_hat_steps:  frozenset[int]
    open_hat_steps:    frozenset[int]
    sub_steps:         frozenset[int] = frozenset({0})

    @property
    def hat_steps(self) -> frozenset[int]:
        """All hat positions (closed ∪ open)."""
        return self.closed_hat_steps | self.open_hat_steps


# ---------------------------------------------------------------------------
# Pattern tables — open/closed hat researched per genre
# ---------------------------------------------------------------------------
# Steps 0-15 = 16th notes within one bar. CH = closed, OH = open.
# OH never lands on beat 1 or 3 kick positions.
# OH is always louder and longer than CH (except Gabber where it matches).

PATTERNS: dict[RhythmicArchetype, ArchetypePattern] = {

    RhythmicArchetype.HALF_STEP: ArchetypePattern(
        archetype         = RhythmicArchetype.HALF_STEP,
        kick_steps        = frozenset({0, 8}),
        snare_steps       = frozenset({4, 12}),
        # CH on all 8ths — drives the half-time feel
        # OH: none (industrial techno mono hat, no open accent)
        closed_hat_steps  = frozenset({0, 2, 4, 6, 8, 10, 12, 14}),
        open_hat_steps    = frozenset(),
        sub_steps         = frozenset({0}),
    ),

    RhythmicArchetype.TWO_STEP: ArchetypePattern(
        archetype         = RhythmicArchetype.TWO_STEP,
        kick_steps        = frozenset({0, 6, 12}),
        snare_steps       = frozenset({4, 12}),
        # CH on 8ths minus the OH position
        # OH on step 14 (off-beat "and" before bar 1) — garage-influenced lift
        closed_hat_steps  = frozenset({0, 2, 4, 6, 8, 10, 12}),
        open_hat_steps    = frozenset({14}),
        sub_steps         = frozenset({2, 10}),
    ),

    RhythmicArchetype.SHUFFLED_TWO_STEP: ArchetypePattern(
        archetype         = RhythmicArchetype.SHUFFLED_TWO_STEP,
        kick_steps        = frozenset({0, 5, 8}),
        snare_steps       = frozenset({4, 12}),
        # Shuffled CH pattern — the swing displacement is the character
        # OH on step 3 (the "late" 8th of a triplet-swing feel)
        closed_hat_steps  = frozenset({0, 5, 8, 10, 13}),
        open_hat_steps    = frozenset({3}),
        sub_steps         = frozenset({2, 11}),
    ),

    RhythmicArchetype.STUTTER: ArchetypePattern(
        archetype         = RhythmicArchetype.STUTTER,
        kick_steps        = frozenset({0, 3, 8, 11}),
        snare_steps       = frozenset({4, 12}),
        # CH all 16 — stutter feel comes from kick irregularity against the hat wall
        # OH: none (the relentless closed hat is the stutter character)
        closed_hat_steps  = frozenset(range(16)),
        open_hat_steps    = frozenset(),
        sub_steps         = frozenset({0, 3}),
    ),

    RhythmicArchetype.ROLLING: ArchetypePattern(
        archetype         = RhythmicArchetype.ROLLING,
        kick_steps        = frozenset({0, 4, 10, 13}),
        snare_steps       = frozenset({4, 12}),
        # CH on 8ths minus OH positions
        # OH on beat 3 "and" (step 10) and beat 1 "and" (step 2) — rolling uplift
        # Ref: rolling DnB / liquid DnB / hardstyle Brennan Heart era
        closed_hat_steps  = frozenset({0, 4, 6, 8, 12, 14}),
        open_hat_steps    = frozenset({2, 10}),
        sub_steps         = frozenset({0, 12}),
    ),

    RhythmicArchetype.BREAKBEAT_HARDCORE: ArchetypePattern(
        archetype         = RhythmicArchetype.BREAKBEAT_HARDCORE,
        kick_steps        = frozenset({0, 3, 7, 10}),
        snare_steps       = frozenset({4, 8, 12}),
        # Dense CH from breakbeat character, OH at beat 3 "and" (step 10)
        # Ref: oldskool rave (Altern-8, Prodigy), breakbeat hardcore 1992-1994
        closed_hat_steps  = frozenset({0, 2, 3, 5, 6, 8, 9, 11, 12, 13, 14}),
        open_hat_steps    = frozenset({4}),
        sub_steps         = frozenset({0, 12}),
    ),

    RhythmicArchetype.AMEN: ArchetypePattern(
        archetype         = RhythmicArchetype.AMEN,
        kick_steps        = frozenset({0, 3, 8, 10}),
        snare_steps       = frozenset({4, 7, 12}),
        # Amen-derived CH — dense, near-continuous 16ths from the break
        # OH on steps 5 and 12 — the jungle/darkcore accent points
        # Ref: darkcore, jungle-influenced hardcore, Dropzone era
        closed_hat_steps  = frozenset({0, 2, 3, 6, 8, 9, 10, 13, 14}),
        open_hat_steps    = frozenset({5, 12}),
        sub_steps         = frozenset({0, 12}),
    ),

    RhythmicArchetype.FOUR_ON_THE_FLOOR: ArchetypePattern(
        archetype         = RhythmicArchetype.FOUR_ON_THE_FLOOR,
        kick_steps        = frozenset({0, 4, 8, 12}),
        snare_steps       = frozenset({4, 12}),
        # CH on 8th-note beats (0,4,8,12 and their ands 2,10)
        # OH on off-beat 8ths between kicks — the classic house/hard dance pump
        # Ref: Hi-NRG, hard house, trance, mainstream gabber (Scooter era)
        closed_hat_steps  = frozenset({0, 2, 4, 8, 10, 12}),
        open_hat_steps    = frozenset({6, 14}),
        sub_steps         = frozenset({0, 4, 8, 12}),
    ),

    RhythmicArchetype.HAPPY_HARDCORE: ArchetypePattern(
        archetype         = RhythmicArchetype.HAPPY_HARDCORE,
        kick_steps        = frozenset({0, 4, 8, 12}),
        snare_steps       = frozenset({4, 12}),
        # CH on all 8ths — the manic driving 8th-note stream
        # OH on beat 2 "and" and beat 4 "and" — uplifting euphoric accent
        # Ref: Hixxy, Sharkey, Scott Brown — happy hardcore peaks
        closed_hat_steps  = frozenset({0, 2, 6, 8, 10, 14}),
        open_hat_steps    = frozenset({4, 12}),
        sub_steps         = frozenset({0, 4, 8, 12}),
    ),

    RhythmicArchetype.GABBER: ArchetypePattern(
        archetype         = RhythmicArchetype.GABBER,
        kick_steps        = frozenset(range(16)),
        snare_steps       = frozenset({4, 12}),
        # CH all 8ths — relentless drive against the all-16th kick wall
        # OH on beat 2 tail (step 7) and beat 4 tail (step 15) — short, equal volume
        # Ref: Rotterdam gabber, Lenny Dee, Industrial Strength
        closed_hat_steps  = frozenset({0, 2, 4, 6, 8, 10, 12, 14}),
        open_hat_steps    = frozenset({7, 15}),
        sub_steps         = frozenset(range(16)),
    ),
}


def select_archetype(density_bias: float, syncopation_bias: float,
                     stability_bias: float = 0.5) -> RhythmicArchetype:
    """Deterministically select an archetype from SignatureRhythm biases.

    stability_bias constrains which archetypes are available at each terrain:
      High stability (Oak/Nott ≥ 0.40): steady groove archetypes
        — FOUR_ON_THE_FLOOR, ROLLING, HALF_STEP, TWO_STEP
      Medium stability (0.18–0.40): transitional archetypes
        — TWO_STEP, SHUFFLED_TWO_STEP, ROLLING, STUTTER, AMEN
      Low stability (Chaos < 0.18): high-energy archetypes
        — HAPPY_HARDCORE, GABBER, STUTTER, BREAKBEAT_HARDCORE, AMEN

    Within each band, density and syncopation biases select the specific archetype.
    """
    d = density_bias
    s = syncopation_bias
    st = stability_bias

    if st >= 0.40:
        # Stable terrain: steady groove archetypes
        if d < 0.45:
            return RhythmicArchetype.HALF_STEP if s < 0.45 else RhythmicArchetype.TWO_STEP
        if d < 0.65:
            return RhythmicArchetype.FOUR_ON_THE_FLOOR if s < 0.50 else RhythmicArchetype.TWO_STEP
        return RhythmicArchetype.ROLLING if s < 0.50 else RhythmicArchetype.FOUR_ON_THE_FLOOR

    if st >= 0.18:
        # Medium stability: transitional archetypes
        if d < 0.45:
            return RhythmicArchetype.TWO_STEP if s < 0.50 else RhythmicArchetype.SHUFFLED_TWO_STEP
        if d < 0.65:
            return RhythmicArchetype.ROLLING if s < 0.50 else RhythmicArchetype.STUTTER
        return RhythmicArchetype.AMEN if s < 0.50 else RhythmicArchetype.BREAKBEAT_HARDCORE

    # Low stability (Chaos): high-energy archetypes
    if d < 0.45:
        return RhythmicArchetype.SHUFFLED_TWO_STEP if s < 0.50 else RhythmicArchetype.STUTTER
    if d < 0.65:
        return RhythmicArchetype.STUTTER if s < 0.50 else RhythmicArchetype.BREAKBEAT_HARDCORE
    if d < 0.80:
        return RhythmicArchetype.BREAKBEAT_HARDCORE if s > 0.50 else RhythmicArchetype.AMEN
    return RhythmicArchetype.HAPPY_HARDCORE if s < 0.50 else RhythmicArchetype.GABBER
