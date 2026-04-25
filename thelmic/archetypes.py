"""Rhythmic archetypes — probability distributions and expectation maps for kick placement.

Each archetype encodes two things:

  kick_probs   — 16 floats (0.0–1.0): probability of a kick on each 16th-note slot per bar.
                 These are BASE probabilities, scaled by density before use.

  expectation  — 16 floats (0.0–1.0): how strongly a listener familiar with this genre
                 expects a kick on each slot. Drives role assignment:
                   - hit on high-expectation slot  → anchor / impact
                   - hit on low-expectation slot   → ghost / disruption
                   - NO hit on high-expectation slot under high anticipation
                                                   → withheld_resolution

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


@dataclass(frozen=True)
class RhythmArchetype:
    name: str
    genre: str
    description: str
    kick_probs: tuple[float, ...]   # 16 values
    expectation: tuple[float, ...]  # 16 values
    density_index: float            # 0.0=sparse → 1.0=dense; used for archetype ordering
    grid_conformity: float          # 0.0=loose → 1.0=rigid; how locked to the grid


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
) -> tuple[list[float], list[float]]:
    """Return (kick_probs, expectation) blended from archetypes for the given force state.

    Selection logic:
      - landscape_position determines the territory (Oak / Chaos / Nott)
      - density selects the base archetype within that territory
      - instability blends toward the territory's disruption archetype

    Returns lists of 16 floats ready to use in generation.
    """
    # --- Primary archetype by territory and density ---

    if landscape_position > 0.67:
        # Nott: dark and sparse. Half-step regardless of density.
        # Deep into Nott, blend from two-step toward pure half-step.
        nott_depth = (landscape_position - 0.67) / 0.33  # 0→1
        base_probs = _lerp_probs(TWO_STEP.kick_probs, HALF_STEP.kick_probs, nott_depth * 0.85)
        base_exp   = _lerp_probs(TWO_STEP.expectation, HALF_STEP.expectation, nott_depth * 0.85)
        disrupt_arch = STUTTER  # jagged dark interruptions

    elif landscape_position > 0.33:
        # Chaos: principled complexity. Blends between shuffled two-step and amen.
        chaos_depth = (landscape_position - 0.33) / 0.34  # 0→1
        base_probs = _lerp_probs(
            SHUFFLED_TWO_STEP.kick_probs, AMEN.kick_probs, density * chaos_depth
        )
        base_exp = _lerp_probs(
            SHUFFLED_TWO_STEP.expectation, AMEN.expectation, density * chaos_depth
        )
        disrupt_arch = GABBER if density > 0.65 else STUTTER

    else:
        # Oak: clear, archetype-compliant. Density selects along the continuum.
        if density < 0.25:
            primary, secondary = HALF_STEP, TWO_STEP
            t = density / 0.25
        elif density < 0.5:
            primary, secondary = TWO_STEP, ROLLING
            t = (density - 0.25) / 0.25
        elif density < 0.72:
            primary, secondary = ROLLING, FOUR_ON_THE_FLOOR
            t = (density - 0.5) / 0.22
        else:
            primary, secondary = FOUR_ON_THE_FLOOR, HAPPY_HARDCORE
            t = (density - 0.72) / 0.28
        base_probs = _lerp_probs(primary.kick_probs, secondary.kick_probs, t)
        base_exp   = _lerp_probs(primary.expectation, secondary.expectation, t)
        disrupt_arch = BREAKBEAT_HARDCORE

    # --- Instability blends toward the disruption archetype ---
    # Cap at 65% so base archetype is always audible.
    inst_t = min(instability * 0.65, 0.65)
    final_probs = _lerp_probs(base_probs, disrupt_arch.kick_probs, inst_t)
    final_exp   = _lerp_probs(base_exp,   disrupt_arch.expectation,  inst_t)

    return final_probs, final_exp


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
