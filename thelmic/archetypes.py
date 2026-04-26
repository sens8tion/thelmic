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
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import NamedTuple


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


class DrumBlend(NamedTuple):
    """Complete drum pattern blend returned by select_blend()."""
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
# Blending and selection
# ---------------------------------------------------------------------------

def _lerp_probs(
    a: tuple[float, ...], b: tuple[float, ...], t: float
) -> list[float]:
    t = max(0.0, min(1.0, t))
    return [a[i] * (1.0 - t) + b[i] * t for i in range(16)]


def select_blend(
    density: float,
    instability: float,
    landscape_position: float,
    locked_archetype: str | None = None,
) -> DrumBlend:
    """Return a DrumBlend (kick, snare, hat probs + expectations) for the given force state.

    If locked_archetype is set (a key in ARCHETYPE_BY_NAME), that archetype's arrays
    are returned directly — no territory logic, no instability blending.

    Otherwise, selection logic:
      - landscape_position determines the territory (Oak / Chaos / Nott)
      - density selects the base archetype within that territory
      - instability blends toward the territory's disruption archetype (capped 65%),
        but at pure Oak (pos=0.0) instability has zero blending power; it scales
        linearly to full influence at the Chaos boundary (pos=0.33)
    """
    # --- Archetype lock: return raw archetype, no blending ---
    if locked_archetype and locked_archetype in ARCHETYPE_BY_NAME:
        a = ARCHETYPE_BY_NAME[locked_archetype]
        return DrumBlend(
            kick_probs  = list(a.kick_probs),
            kick_exp    = list(a.expectation),
            snare_probs = list(a.snare_probs),
            snare_exp   = list(a.snare_exp),
            hat_probs   = list(a.hat_probs),
            hat_exp     = list(a.hat_exp),
        )

    # --- Primary archetype by territory and density ---

    if landscape_position > 0.67:
        # Nott: dark and sparse. Half-step regardless of density.
        nott_depth = (landscape_position - 0.67) / 0.33  # 0→1
        t = nott_depth * 0.85
        primary, secondary = TWO_STEP, HALF_STEP
        disrupt_arch = STUTTER

    elif landscape_position > 0.33:
        # Chaos: principled complexity. Blends between shuffled two-step and amen.
        chaos_depth = (landscape_position - 0.33) / 0.34  # 0→1
        t = density * chaos_depth
        primary, secondary = SHUFFLED_TWO_STEP, AMEN
        disrupt_arch = GABBER if density > 0.65 else STUTTER

    else:
        # Oak: clear, archetype-compliant. Density selects along the continuum.
        # At hard left (pos=0.0) the secondary-blend weight is 0 — pure primary
        # archetype, total compliance. Blend grows linearly toward the Chaos boundary.
        oak_blend_scale = min(1.0, landscape_position / 0.33)
        if density < 0.25:
            primary, secondary = HALF_STEP, TWO_STEP
            t = (density / 0.25) * oak_blend_scale
        elif density < 0.5:
            primary, secondary = TWO_STEP, ROLLING
            t = ((density - 0.25) / 0.25) * oak_blend_scale
        elif density < 0.72:
            primary, secondary = ROLLING, FOUR_ON_THE_FLOOR
            t = ((density - 0.5) / 0.22) * oak_blend_scale
        else:
            primary, secondary = FOUR_ON_THE_FLOOR, HAPPY_HARDCORE
            t = ((density - 0.72) / 0.28) * oak_blend_scale
        disrupt_arch = BREAKBEAT_HARDCORE

    # --- Base blend ---
    base_kick_probs  = _lerp_probs(primary.kick_probs,   secondary.kick_probs,   t)
    base_kick_exp    = _lerp_probs(primary.expectation,   secondary.expectation,   t)
    base_snare_probs = _lerp_probs(primary.snare_probs,  secondary.snare_probs,  t)
    base_snare_exp   = _lerp_probs(primary.snare_exp,    secondary.snare_exp,    t)
    base_hat_probs   = _lerp_probs(primary.hat_probs,    secondary.hat_probs,    t)
    base_hat_exp     = _lerp_probs(primary.hat_exp,      secondary.hat_exp,      t)

    # --- Instability blends toward the disruption archetype (capped 65%) ---
    # At pure Oak (pos=0.0) instability has zero blending power — total archetype
    # compliance. Influence grows linearly to full at the Chaos boundary (pos=0.33).
    oak_scale = min(1.0, landscape_position / 0.33) if landscape_position < 0.33 else 1.0
    inst_t = min(instability * 0.65, 0.65) * oak_scale

    return DrumBlend(
        kick_probs  = _lerp_probs(base_kick_probs,  disrupt_arch.kick_probs,  inst_t),
        kick_exp    = _lerp_probs(base_kick_exp,    disrupt_arch.expectation,  inst_t),
        snare_probs = _lerp_probs(base_snare_probs, disrupt_arch.snare_probs, inst_t),
        snare_exp   = _lerp_probs(base_snare_exp,   disrupt_arch.snare_exp,   inst_t),
        hat_probs   = _lerp_probs(base_hat_probs,   disrupt_arch.hat_probs,   inst_t),
        hat_exp     = _lerp_probs(base_hat_exp,     disrupt_arch.hat_exp,     inst_t),
    )


def archetype_name_at(
    density: float,
    instability: float,
    landscape_position: float,
) -> str:
    """Human-readable label for the dominant archetype at these force values."""
    if landscape_position > 0.67:
        return "half_step" if density < 0.5 else "half_step→two_step"
    elif landscape_position > 0.33:
        base = "shuffled_two_step" if density < 0.5 else "amen"
        return f"{base}+disruption" if instability > 0.5 else base
    else:
        if density < 0.25:   return "half_step"
        elif density < 0.5:  return "two_step"
        elif density < 0.72: return "rolling"
        else:                return "four_on_the_floor"
