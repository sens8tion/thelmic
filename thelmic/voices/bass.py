"""Bass voice — tonal foundation, archetype-driven rhythm.

Archetype defines WHEN bass fires (timing grid).
SignatureRhythm defines WHAT pitch to use (root, fifth, octave, colour tones).

This is the authority from musical_rules.md:
  "BassIntentStream must derive firing steps from PATTERNS[context.active_archetype].
   SignatureRhythm informs pitch; archetype defines timing."

GABBER exception: bass is entirely suppressed — sub absorbs the bass role.
"""

from __future__ import annotations

from thelmic.archetypes import PATTERNS, RhythmicArchetype
from thelmic.dimensions import Dimensions, PhraseContext
from thelmic.landscape_map import SignatureRhythm
from thelmic.stream_engine import Intent, StructureFrame
from thelmic.voices import make_intent

# MIDI interval offsets (from musical_rules.md — Oak, Nott, Chaos pitch material)
_FIFTH   = 7
_MIN3    = 3   # Nott/Chaos colour: minor third
_MIN7    = 10  # DnB/industrial colour: minor seventh
_OCTAVE  = 12

# Archetype-keyed anchor durations (seconds) from musical_rules.md.
# At 174 BPM: 1 beat = 0.345s, 1 bar = 1.379s.
_ARCHETYPE_DURATION: dict[RhythmicArchetype, float] = {
    RhythmicArchetype.HALF_STEP:          0.45,  # industrial mono-bass, long sustain
    RhythmicArchetype.TWO_STEP:           0.30,  # DnB reese character
    RhythmicArchetype.SHUFFLED_TWO_STEP:  0.25,  # breakbeat sustain
    RhythmicArchetype.STUTTER:            0.10,  # stutter stab, short punchy
    RhythmicArchetype.ROLLING:            0.22,  # rolling groove, medium
    RhythmicArchetype.BREAKBEAT_HARDCORE: 0.09,  # hardcore stab, fast decay
    RhythmicArchetype.AMEN:               0.38,  # DnB reese, sustained
    RhythmicArchetype.FOUR_ON_THE_FLOOR:  0.09,  # French house pump stab
    RhythmicArchetype.HAPPY_HARDCORE:     0.08,  # short bright stab every 8th
    RhythmicArchetype.GABBER:             0.05,  # suppressed; minimal if fired
}


class BassIntentStream:
    def intents_for_frame(
        self,
        frame: StructureFrame,
        context: PhraseContext,
        dims: Dimensions,
        sr: SignatureRhythm | None = None,
    ) -> tuple[Intent, ...]:
        if sr is None:
            return ()

        # GABBER: bass is entirely suppressed — sub absorbs the bass role.
        if context and context.active_archetype == RhythmicArchetype.GABBER:
            return ()

        # Drop phrase: assert root on beat 1, long sustain
        if context.is_drop_phrase and frame.is_phrase_start:
            dur = _duration(context, dims.stability, is_anchor=True)
            return (make_intent(
                frame, "bass", "root", _velocity(dims.stability, is_anchor=True),
                dur, "drop_anchor_bass", sr.root_note, 9,
            ),)

        # Normal phrase: firing steps from the active archetype pattern
        pattern    = PATTERNS[context.active_archetype] if context else None
        bass_steps = pattern.kick_steps if pattern else frozenset({0, 4, 8, 12})
        # Use the archetype's kick steps as the bass grid (kick and bass lock together)
        # Musical note selection is from the SignatureRhythm

        if frame.step_in_bar not in bass_steps:
            return ()

        note     = _pick_note(sr.root_note, frame.step_in_bar, sr, dims.stability)
        velocity = _velocity(dims.stability, is_anchor=(frame.step_in_bar == 0))
        dur      = _duration(context, dims.stability, is_anchor=(frame.step_in_bar == 0))
        return (make_intent(frame, "bass", "bass", velocity, dur,
                            "archetype_bass", note, 9),)


def _pick_note(root: int, step: int, sr, stability: float) -> int:
    """Pitch selection from musical_rules.md terrain tonality.

    Oak (stability ≥ 0.70): root, maj3, 5th, octave — warm, resolved.
    Nott (0.45–0.70):       root, min3, 5th, min7 — dark, minor.
    Chaos (< 0.45):         root only, or occasional tritone.
    """
    if step == 0:
        return root

    # Deterministic pitch selection from syncopation_bias + step
    pattern_hash = (step * 31 + int(sr.syncopation_bias * 100)) % 10

    if stability >= 0.70:
        # Oak: major intervals
        intervals = [0, 0, 0, _FIFTH, _FIFTH, _FIFTH, _OCTAVE, _OCTAVE, 4, 4]
    elif stability >= 0.45:
        # Nott: minor intervals
        intervals = [0, 0, 0, _FIFTH, _FIFTH, _MIN3, _MIN7, _OCTAVE, _MIN3, _FIFTH]
    else:
        # Chaos: root-heavy, rare colour
        intervals = [0, 0, 0, 0, 0, 0, _FIFTH, 0, 0, 6]  # mostly root, occasional tritone

    return root + intervals[pattern_hash]


def _duration(context, stability: float, is_anchor: bool) -> float:
    """Archetype-keyed duration scaled by stability.

    Rules (musical_rules.md, Melodic Voice Tonality):
    Short notes = stabs (percussive energy).
    Long notes = sustain (harmonic weight).
    At high stability: ×1.2–1.4 multiplier.
    At low stability: ×0.6–0.8 multiplier.
    """
    arch     = context.active_archetype if context else RhythmicArchetype.FOUR_ON_THE_FLOOR
    base_dur = _ARCHETYPE_DURATION.get(arch, 0.20)
    # Scale by stability
    scale    = 0.65 + stability * 0.70   # 0.65 (chaos) → 1.35 (oak)
    dur      = base_dur * scale
    if not is_anchor:
        dur *= 0.60   # fill notes shorter than anchor
    return max(0.04, round(dur, 3))


def _velocity(stability: float, is_anchor: bool) -> int:
    """Rules (musical_rules.md, Velocity Dynamics):
    High stability: anchor 95–112, fill 55–75.
    Low stability:  anchor 110–127, fill 40–65.
    """
    heat_proxy = 1.0 - stability   # 0=cold/stable, 1=hot/unstable
    if is_anchor:
        # Cold: 88, Hot: 112  (rules say 95–112 at high stability, 110–127 at low)
        v = int(88 + heat_proxy * 24)
    else:
        # Cold: 72, Hot: 55  (recede behind anchor at high heat)
        v = int(72 - heat_proxy * 17)
    return max(40, min(112, v))
