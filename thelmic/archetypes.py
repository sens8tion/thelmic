"""Rhythmic archetypes — probability distributions and expectation maps for kick, snare, hat.

Each archetype encodes six 16-float arrays:

  kick_probs / expectation  — kick drum probability and listener expectation per slot
  snare_probs / snare_exp   — snare drum probability and expectation
  hat_probs / hat_exp       — hi-hat probability and expectation
                              (note selection: slot%4==2 → open hat; else closed hat)

BASE probabilities are scaled by density and force before use.

Slot index reference (0-indexed, 4/4 at 16th-note resolution):
  0  = beat 1 (downbeat)        8  = beat 3
  1  = beat 1 + 16th ("1-e")    9  = "3-e"
  2  = beat 1.5 ("1-and")       10 = beat 3.5 ("3-and")
  3  = beat 1 + 3×16th ("1-ah") 11 = "3-ah"
  4  = beat 2                   12 = beat 4
  5  = "2-e"                    13 = "4-e"
  6  = beat 2.5 ("2-and")       14 = beat 4.5 ("4-and")
  7  = "2-ah"                   15 = "4-ah"

Beats 2 and 4 (slots 4 and 12) are snare territory in all DnB archetypes.
Kick archetypes deliberately avoid or approach these slots as part of their identity.

Architecture
------------
Archetype selection and deformation are intentionally separate:

  1. select_archetype(density, selected_name) → RhythmArchetype
       Pure selection. Density-driven (or explicit). Territory-agnostic.

  2. to_blend(archetype) → DrumBlend
       Identity conversion — archetype arrays become mutable lists ready for deformation.

  3. deformations.apply_deformations(blend, anchors, force, landscape_position) → DrumBlend
       Pressure algorithms applied on top of the blend. Each deformation is a separate
       pure function that must not suppress any slot in anchors.kick/snare/hat.

Landscape position (Oak → Chaos → Nott) is a deformation parameter, not an archetype
selector. The archetype is stable; territory determines how it is pressured.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import NamedTuple

# Slots at or above this expectation value are structural anchors.
# Deformations must not suppress these — the listener's anchor is the source of felt tension.
ANCHOR_EXPECTATION_THRESHOLD = 0.7


@dataclass(frozen=True)
class RhythmArchetype:
    name: str
    genre: str
    description: str
    kick_probs: tuple[float, ...]    # 16 values — kick placement probability
    expectation: tuple[float, ...]   # 16 values — kick listener expectation
    snare_probs: tuple[float, ...]   # 16 values — snare placement probability
    snare_exp: tuple[float, ...]     # 16 values — snare listener expectation
    hat_probs: tuple[float, ...]     # 16 values — hat placement probability
    hat_exp: tuple[float, ...]       # 16 values — hat listener expectation
    density_index: float             # 0.0=sparse → 1.0=dense; used for archetype ordering
    grid_conformity: float           # 0.0=loose → 1.0=rigid

    @property
    def kick_anchors(self) -> frozenset[int]:
        """Slots that are structural kick anchors. Deformations must not suppress these."""
        return frozenset(i for i, e in enumerate(self.expectation) if e >= ANCHOR_EXPECTATION_THRESHOLD)

    @property
    def snare_anchors(self) -> frozenset[int]:
        """Slots that are structural snare anchors."""
        return frozenset(i for i, e in enumerate(self.snare_exp) if e >= ANCHOR_EXPECTATION_THRESHOLD)

    @property
    def hat_anchors(self) -> frozenset[int]:
        """Slots that are structural hat anchors."""
        return frozenset(i for i, e in enumerate(self.hat_exp) if e >= ANCHOR_EXPECTATION_THRESHOLD)


@dataclass(frozen=True)
class Anchors:
    """Structural anchor slots for all three layers. Passed to every deformation."""
    kick:  frozenset[int]
    snare: frozenset[int]
    hat:   frozenset[int]


class DrumBlend(NamedTuple):
    """Resolved drum probability arrays, ready for the bank generator.

    Produced by converting a RhythmArchetype via to_blend(), then optionally
    transformed by one or more deformation functions. Anchor slots must survive
    all deformations at full (≥ archetype) probability.
    """
    kick_probs:  list[float]   # 16 values
    kick_exp:    list[float]
    snare_probs: list[float]
    snare_exp:   list[float]
    hat_probs:   list[float]
    hat_exp:     list[float]


# ---------------------------------------------------------------------------
# Archetype definitions
# ---------------------------------------------------------------------------

# Two-step — the DnB signature. Kick on beat 1 and the "2-and" (slot 6), avoiding
# beats 2 and 4 (snare territory). The skip between 1 and the syncopated hit is the
# defining feel of drum & bass.
TWO_STEP = RhythmArchetype(
    name="two_step",
    genre="dnb",
    description="DnB signature. Kick on 1 and 2-and. Avoids beats 2 and 4.",
    kick_probs=(
        0.95, 0.0,  0.05, 0.0,   # beat 1: strong; 16ths: rare
        0.0,  0.0,  0.85, 0.1,   # beat 2: none; 2-and: strong
        0.15, 0.0,  0.2,  0.05,  # beat 3: occasional; 3-and: low fill
        0.0,  0.0,  0.1,  0.05,  # beat 4: none; 4-and: rare tail
    ),
    expectation=(
        1.0,  0.0,  0.0,  0.0,
        0.0,  0.0,  0.9,  0.0,
        0.1,  0.0,  0.1,  0.0,
        0.0,  0.0,  0.0,  0.0,
    ),
    snare_probs=(
        0.0,  0.0,  0.25, 0.05,  # ghost before beat 2
        0.95, 0.0,  0.1,  0.2,   # beat 2 backbone + ghost after
        0.0,  0.0,  0.25, 0.05,  # ghost before beat 4
        0.95, 0.0,  0.1,  0.2,   # beat 4 backbone + ghost after
    ),
    snare_exp=(
        0.0,  0.0,  0.15, 0.0,
        1.0,  0.0,  0.0,  0.1,
        0.0,  0.0,  0.15, 0.0,
        1.0,  0.0,  0.0,  0.1,
    ),
    hat_probs=(
        0.75, 0.2,  0.85, 0.1,   # 8ths strong, light 16th fill
        0.65, 0.15, 0.9,  0.1,   # 2-and very active (open hat feel)
        0.75, 0.2,  0.85, 0.1,
        0.65, 0.15, 0.9,  0.1,
    ),
    hat_exp=(
        0.6,  0.1,  0.8,  0.0,
        0.5,  0.1,  0.9,  0.0,
        0.6,  0.1,  0.8,  0.0,
        0.5,  0.1,  0.9,  0.0,
    ),
    density_index=0.35,
    grid_conformity=0.75,
)

# Rolling — kick every 3 sixteenth notes (slots 0, 3, 6, 9, 12), giving a
# continuously forward-pushing momentum. Common in liquid and tech-step DnB.
ROLLING = RhythmArchetype(
    name="rolling",
    genre="dnb",
    description="Kick every 3 sixteenths. Forward-rolling momentum. Liquid/tech-step.",
    kick_probs=(
        0.9,  0.0,  0.0,  0.85,  # beat 1: strong; 3rd slot: strong
        0.0,  0.0,  0.85, 0.0,   # 6th slot: strong
        0.0,  0.85, 0.0,  0.0,   # 9th slot: strong
        0.85, 0.0,  0.0,  0.4,   # 12th slot: strong; 15th: occasional tail
    ),
    expectation=(
        1.0,  0.0,  0.0,  0.8,
        0.0,  0.0,  0.8,  0.0,
        0.0,  0.8,  0.0,  0.0,
        0.8,  0.0,  0.0,  0.3,
    ),
    snare_probs=(
        0.0,  0.0,  0.3,  0.1,
        0.95, 0.0,  0.15, 0.25,
        0.0,  0.0,  0.3,  0.1,
        0.95, 0.0,  0.15, 0.25,
    ),
    snare_exp=(
        0.0,  0.0,  0.2,  0.0,
        1.0,  0.0,  0.0,  0.15,
        0.0,  0.0,  0.2,  0.0,
        1.0,  0.0,  0.0,  0.15,
    ),
    hat_probs=(
        0.8,  0.3,  0.9,  0.2,   # busy 16th feel to match rolling kick
        0.7,  0.25, 0.9,  0.2,
        0.8,  0.3,  0.9,  0.2,
        0.7,  0.25, 0.9,  0.2,
    ),
    hat_exp=(
        0.7,  0.2,  0.8,  0.1,
        0.6,  0.15, 0.9,  0.1,
        0.7,  0.2,  0.8,  0.1,
        0.6,  0.15, 0.9,  0.1,
    ),
    density_index=0.6,
    grid_conformity=0.7,
)

# Half-step — neurofunk and dark DnB. Kick only on beat 1 (sometimes a soft beat 3).
# The sparseness is intentional; the space carries as much weight as the hit.
HALF_STEP = RhythmArchetype(
    name="half_step",
    genre="dnb_neuro",
    description="Neurofunk. Kick on beat 1 only. Space is the content.",
    kick_probs=(
        0.95, 0.0,  0.0,  0.0,
        0.0,  0.0,  0.0,  0.0,
        0.25, 0.0,  0.0,  0.0,
        0.0,  0.0,  0.0,  0.0,
    ),
    expectation=(
        1.0,  0.0,  0.0,  0.0,
        0.0,  0.0,  0.0,  0.0,
        0.3,  0.0,  0.0,  0.0,
        0.0,  0.0,  0.0,  0.0,
    ),
    snare_probs=(
        0.0,  0.0,  0.05, 0.0,   # very minimal ghosts
        0.95, 0.0,  0.0,  0.05,  # tight beat 2
        0.0,  0.0,  0.05, 0.0,
        0.95, 0.0,  0.0,  0.05,  # tight beat 4
    ),
    snare_exp=(
        0.0,  0.0,  0.0,  0.0,
        1.0,  0.0,  0.0,  0.0,
        0.0,  0.0,  0.0,  0.0,
        1.0,  0.0,  0.0,  0.0,
    ),
    hat_probs=(
        0.3,  0.0,  0.55, 0.0,   # sparse — just upbeats
        0.3,  0.0,  0.55, 0.0,
        0.3,  0.0,  0.55, 0.0,
        0.3,  0.0,  0.55, 0.0,
    ),
    hat_exp=(
        0.2,  0.0,  0.5,  0.0,
        0.2,  0.0,  0.5,  0.0,
        0.2,  0.0,  0.5,  0.0,
        0.2,  0.0,  0.5,  0.0,
    ),
    density_index=0.1,
    grid_conformity=0.9,
)

# Shuffled two-step — jungle and early DnB. Two-step skeleton with triplet-feel
# displacement and additional 16th-note complexity. The swing is felt, not strictly
# quantised; represented here as added probability on "ah" positions (slots 3, 7, 11).
SHUFFLED_TWO_STEP = RhythmArchetype(
    name="shuffled_two_step",
    genre="jungle",
    description="Jungle roots. Two-step with swing displacement and 16th-note fills.",
    kick_probs=(
        0.9,  0.0,  0.1,  0.3,   # beat 1 + swing fill
        0.0,  0.0,  0.7,  0.2,   # 2-and + swing fill
        0.3,  0.1,  0.2,  0.1,   # beat 3 region: scattered
        0.05, 0.0,  0.15, 0.1,   # beat 4 region: sparse tail
    ),
    expectation=(
        1.0,  0.0,  0.0,  0.2,
        0.0,  0.0,  0.8,  0.1,
        0.3,  0.0,  0.1,  0.0,
        0.0,  0.0,  0.1,  0.0,
    ),
    snare_probs=(
        0.0,  0.0,  0.2,  0.3,   # jungle swing ghost before beat 2
        0.9,  0.05, 0.15, 0.35,  # beat 2 + ghost after
        0.0,  0.0,  0.2,  0.3,   # jungle swing ghost before beat 4
        0.9,  0.05, 0.15, 0.35,  # beat 4 + ghost after
    ),
    snare_exp=(
        0.0,  0.0,  0.1,  0.2,
        1.0,  0.0,  0.0,  0.2,
        0.0,  0.0,  0.1,  0.2,
        1.0,  0.0,  0.0,  0.2,
    ),
    hat_probs=(
        0.6,  0.3,  0.75, 0.35,  # swing: energy on "ah" positions
        0.5,  0.25, 0.8,  0.35,
        0.6,  0.3,  0.75, 0.35,
        0.5,  0.25, 0.8,  0.35,
    ),
    hat_exp=(
        0.5,  0.2,  0.7,  0.2,
        0.4,  0.15, 0.8,  0.2,
        0.5,  0.2,  0.7,  0.2,
        0.4,  0.15, 0.8,  0.2,
    ),
    density_index=0.45,
    grid_conformity=0.5,
)

# Amen — based on the Amen break (The Winstons, 1969). Complex multi-hit pattern
# that anchors drum & bass and jungle. Kick appears across beats 1, 2, and 3 with
# fill complexity. The listener expects density and syncopation; silence is the surprise.
AMEN = RhythmArchetype(
    name="amen",
    genre="jungle_dnb",
    description="Amen break-derived. Multi-hit, complex. Beat 1, beat 2, beat 3 all active.",
    kick_probs=(
        0.9,  0.0,  0.5,  0.15,  # beat 1 + fast fill
        0.65, 0.0,  0.3,  0.1,   # beat 2 present (break-derived)
        0.85, 0.0,  0.45, 0.2,   # beat 3 strong + fill
        0.15, 0.05, 0.1,  0.15,  # beat 4: sparse but complex
    ),
    expectation=(
        1.0,  0.0,  0.4,  0.0,
        0.6,  0.0,  0.2,  0.0,
        0.9,  0.0,  0.4,  0.0,
        0.1,  0.0,  0.0,  0.0,
    ),
    snare_probs=(
        0.25, 0.0,  0.35, 0.1,   # break-derived ghost on beat 1
        0.9,  0.05, 0.25, 0.3,   # beat 2 backbone + fills
        0.25, 0.0,  0.35, 0.15,  # break-derived ghost on beat 3
        0.9,  0.1,  0.25, 0.3,   # beat 4 backbone + complex
    ),
    snare_exp=(
        0.15, 0.0,  0.2,  0.0,
        0.9,  0.0,  0.1,  0.2,
        0.2,  0.0,  0.2,  0.0,
        0.9,  0.0,  0.1,  0.2,
    ),
    hat_probs=(
        0.7,  0.4,  0.8,  0.45,  # near 16th feel — very complex
        0.6,  0.35, 0.85, 0.4,
        0.7,  0.4,  0.8,  0.45,
        0.6,  0.35, 0.85, 0.35,
    ),
    hat_exp=(
        0.6,  0.3,  0.7,  0.25,
        0.5,  0.2,  0.8,  0.25,
        0.6,  0.3,  0.7,  0.25,
        0.5,  0.2,  0.8,  0.25,
    ),
    density_index=0.7,
    grid_conformity=0.4,
)

# Stutter — doubled or tripled kicks on the downbeats. A tension device: groups of
# rapid hits create urgency. Common as a build or breakdown marker across DnB, hardcore,
# and industrial techno.
STUTTER = RhythmArchetype(
    name="stutter",
    genre="dnb_hardcore",
    description="Doubled/tripled downbeat kicks. Urgency/tension device.",
    kick_probs=(
        0.95, 0.8,  0.0,  0.0,   # beat 1: double hit
        0.1,  0.0,  0.1,  0.0,
        0.85, 0.7,  0.0,  0.0,   # beat 3: double hit
        0.1,  0.0,  0.1,  0.0,
    ),
    expectation=(
        1.0,  0.7,  0.0,  0.0,
        0.0,  0.0,  0.0,  0.0,
        0.8,  0.6,  0.0,  0.0,
        0.0,  0.0,  0.0,  0.0,
    ),
    snare_probs=(
        0.0,  0.0,  0.15, 0.0,
        0.95, 0.5,  0.0,  0.1,   # stutter on the snare too
        0.0,  0.0,  0.15, 0.0,
        0.95, 0.5,  0.0,  0.1,
    ),
    snare_exp=(
        0.0,  0.0,  0.0,  0.0,
        1.0,  0.4,  0.0,  0.0,
        0.0,  0.0,  0.0,  0.0,
        1.0,  0.4,  0.0,  0.0,
    ),
    hat_probs=(
        0.8,  0.1,  0.5,  0.1,   # heavy on downbeats, sparse elsewhere
        0.8,  0.1,  0.5,  0.1,
        0.8,  0.1,  0.5,  0.1,
        0.8,  0.1,  0.5,  0.1,
    ),
    hat_exp=(
        0.7,  0.0,  0.3,  0.0,
        0.7,  0.0,  0.3,  0.0,
        0.7,  0.0,  0.3,  0.0,
        0.7,  0.0,  0.3,  0.0,
    ),
    density_index=0.5,
    grid_conformity=0.85,
)

# Four-on-the-floor — kick on every quarter note. The foundation of house and techno,
# carried into hardcore and some DnB drops. Maximum grid conformity; any deviation is
# immediately legible as a break from the archetype.
FOUR_ON_THE_FLOOR = RhythmArchetype(
    name="four_on_the_floor",
    genre="house_hardcore_techno",
    description="Kick on every beat. Maximum grid conformity. Drop archetype.",
    kick_probs=(
        0.95, 0.0,  0.0,  0.0,
        0.95, 0.0,  0.0,  0.0,
        0.95, 0.0,  0.0,  0.0,
        0.95, 0.0,  0.0,  0.0,
    ),
    expectation=(
        1.0,  0.0,  0.0,  0.0,
        1.0,  0.0,  0.0,  0.0,
        1.0,  0.0,  0.0,  0.0,
        1.0,  0.0,  0.0,  0.0,
    ),
    snare_probs=(
        0.0,  0.0,  0.15, 0.05,
        0.95, 0.0,  0.1,  0.1,
        0.0,  0.0,  0.15, 0.05,
        0.95, 0.0,  0.1,  0.1,
    ),
    snare_exp=(
        0.0,  0.0,  0.1,  0.0,
        1.0,  0.0,  0.0,  0.05,
        0.0,  0.0,  0.1,  0.0,
        1.0,  0.0,  0.0,  0.05,
    ),
    hat_probs=(
        0.85, 0.1,  0.85, 0.1,   # straight 8ths, very regular
        0.85, 0.1,  0.85, 0.1,
        0.85, 0.1,  0.85, 0.1,
        0.85, 0.1,  0.85, 0.1,
    ),
    hat_exp=(
        0.8,  0.0,  0.8,  0.0,
        0.8,  0.0,  0.8,  0.0,
        0.8,  0.0,  0.8,  0.0,
        0.8,  0.0,  0.8,  0.0,
    ),
    density_index=0.75,
    grid_conformity=1.0,
)

# Breakbeat hardcore — early UK rave (1990–92). Break-derived at 160–170 BPM.
# More complex than four-on-the-floor, less tight than two-step. The 2-and (slot 6)
# and 4-and (slot 14) carry significant weight.
BREAKBEAT_HARDCORE = RhythmArchetype(
    name="breakbeat_hardcore",
    genre="hardcore_rave",
    description="Early UK rave. Break-derived complexity at hardcore BPMs.",
    kick_probs=(
        0.9,  0.0,  0.25, 0.1,
        0.2,  0.0,  0.6,  0.0,
        0.8,  0.0,  0.3,  0.1,
        0.2,  0.0,  0.5,  0.0,
    ),
    expectation=(
        1.0,  0.0,  0.1,  0.0,
        0.2,  0.0,  0.6,  0.0,
        0.9,  0.0,  0.2,  0.0,
        0.2,  0.0,  0.4,  0.0,
    ),
    snare_probs=(
        0.15, 0.0,  0.25, 0.1,
        0.95, 0.0,  0.2,  0.25,
        0.2,  0.0,  0.3,  0.1,
        0.95, 0.0,  0.2,  0.25,
    ),
    snare_exp=(
        0.1,  0.0,  0.15, 0.0,
        1.0,  0.0,  0.1,  0.15,
        0.15, 0.0,  0.2,  0.0,
        1.0,  0.0,  0.1,  0.15,
    ),
    hat_probs=(
        0.75, 0.25, 0.8,  0.2,
        0.65, 0.2,  0.85, 0.25,
        0.75, 0.25, 0.8,  0.2,
        0.65, 0.2,  0.85, 0.25,
    ),
    hat_exp=(
        0.6,  0.15, 0.7,  0.1,
        0.5,  0.1,  0.8,  0.15,
        0.6,  0.15, 0.7,  0.1,
        0.5,  0.1,  0.8,  0.15,
    ),
    density_index=0.55,
    grid_conformity=0.55,
)

# Happy hardcore / bouncer — four-on-the-floor foundation with strong offbeat activity
# on the 8th-note upbeats (slots 2, 6, 10, 14). Creates the characteristic "bouncing"
# energy. ~165–180 BPM. Sometimes called "bouncy techno" in the rave scene.
HAPPY_HARDCORE = RhythmArchetype(
    name="happy_hardcore",
    genre="hardcore_happy",
    description="Four-on-the-floor + strong 8th upbeats. The bounce.",
    kick_probs=(
        0.95, 0.0,  0.35, 0.0,
        0.95, 0.0,  0.5,  0.0,
        0.95, 0.0,  0.35, 0.0,
        0.95, 0.0,  0.5,  0.0,
    ),
    expectation=(
        1.0,  0.0,  0.3,  0.0,
        1.0,  0.0,  0.4,  0.0,
        1.0,  0.0,  0.3,  0.0,
        1.0,  0.0,  0.4,  0.0,
    ),
    snare_probs=(
        0.0,  0.0,  0.3,  0.1,
        0.95, 0.0,  0.25, 0.2,
        0.0,  0.0,  0.3,  0.1,
        0.95, 0.0,  0.35, 0.2,
    ),
    snare_exp=(
        0.0,  0.0,  0.2,  0.0,
        1.0,  0.0,  0.15, 0.1,
        0.0,  0.0,  0.2,  0.0,
        1.0,  0.0,  0.2,  0.1,
    ),
    hat_probs=(
        0.9,  0.5,  0.9,  0.45,  # very busy bouncy 16ths
        0.85, 0.45, 0.95, 0.5,
        0.9,  0.5,  0.9,  0.45,
        0.85, 0.45, 0.95, 0.5,
    ),
    hat_exp=(
        0.8,  0.35, 0.8,  0.3,
        0.75, 0.3,  0.9,  0.35,
        0.8,  0.35, 0.8,  0.3,
        0.75, 0.3,  0.9,  0.35,
    ),
    density_index=0.85,
    grid_conformity=0.9,
)

# Gabber — extreme density, near-continuous kick. Every or near-every 16th note.
# Industrial, Rotterdam, early 200 BPM hardcore. At DnB tempos this becomes almost
# a textural element rather than a rhythmic one.
GABBER = RhythmArchetype(
    name="gabber",
    genre="hardcore_industrial",
    description="Near-continuous kick. Every 16th note or close to it. Textural.",
    kick_probs=(
        1.0,  0.35, 0.35, 0.35,
        1.0,  0.35, 0.35, 0.35,
        1.0,  0.35, 0.35, 0.35,
        1.0,  0.35, 0.35, 0.35,
    ),
    expectation=(
        1.0,  0.2,  0.2,  0.2,
        1.0,  0.2,  0.2,  0.2,
        1.0,  0.2,  0.2,  0.2,
        1.0,  0.2,  0.2,  0.2,
    ),
    snare_probs=(
        0.0,  0.0,  0.1,  0.0,
        0.7,  0.0,  0.05, 0.05,  # backbone weakened; kick dominates
        0.0,  0.0,  0.1,  0.0,
        0.7,  0.0,  0.05, 0.05,
    ),
    snare_exp=(
        0.0,  0.0,  0.0,  0.0,
        0.8,  0.0,  0.0,  0.0,
        0.0,  0.0,  0.0,  0.0,
        0.8,  0.0,  0.0,  0.0,
    ),
    hat_probs=(
        0.4,  0.15, 0.4,  0.1,   # sparse — kick fills the texture
        0.4,  0.1,  0.4,  0.1,
        0.4,  0.15, 0.4,  0.1,
        0.4,  0.1,  0.4,  0.1,
    ),
    hat_exp=(
        0.3,  0.0,  0.3,  0.0,
        0.3,  0.0,  0.3,  0.0,
        0.3,  0.0,  0.3,  0.0,
        0.3,  0.0,  0.3,  0.0,
    ),
    density_index=1.0,
    grid_conformity=0.95,
)

# All archetypes ordered by density_index (used for density-based selection)
ALL_ARCHETYPES: list[RhythmArchetype] = sorted(
    [
        HALF_STEP, TWO_STEP, SHUFFLED_TWO_STEP, STUTTER, ROLLING,
        BREAKBEAT_HARDCORE, FOUR_ON_THE_FLOOR, HAPPY_HARDCORE, GABBER, AMEN,
    ],
    key=lambda a: a.density_index,
)

# Lookup by name — used for archetype lock
ARCHETYPE_BY_NAME: dict[str, RhythmArchetype] = {a.name: a for a in ALL_ARCHETYPES}


# ---------------------------------------------------------------------------
# Selection and conversion
# ---------------------------------------------------------------------------

def select_archetype(
    density: float,
    selected_name: str | None = None,
) -> RhythmArchetype:
    """Select the base archetype.

    If selected_name is provided and valid, it is returned directly.
    Otherwise the archetype whose density_index is closest to density is chosen.
    Territory (landscape_position) plays no role here — it is a deformation parameter.
    """
    if selected_name and selected_name in ARCHETYPE_BY_NAME:
        return ARCHETYPE_BY_NAME[selected_name]
    return min(ALL_ARCHETYPES, key=lambda a: abs(a.density_index - density))


def to_blend(archetype: RhythmArchetype) -> DrumBlend:
    """Convert an archetype to a DrumBlend with no deformation applied (identity pass)."""
    return DrumBlend(
        kick_probs  = list(archetype.kick_probs),
        kick_exp    = list(archetype.expectation),
        snare_probs = list(archetype.snare_probs),
        snare_exp   = list(archetype.snare_exp),
        hat_probs   = list(archetype.hat_probs),
        hat_exp     = list(archetype.hat_exp),
    )


def archetype_name_at(density: float, **_kwargs) -> str:
    """Human-readable name of the archetype that would be selected at this density."""
    return select_archetype(density).name
