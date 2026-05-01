"""Sub bass voice — archetype-driven with rhythmic texture.

Rules (musical_rules.md — Melodic Voice Tonality, per genre research):
  Sub steps that coincide with a kick step = PRIMARY:
    loud (~100–110 velocity), long sustain (~0.3–0.5 bar)
  Sub steps that don't coincide with kick = SECONDARY:
    quieter (~65–80 velocity), short (~0.08–0.15 bar)

This creates subliminal rhythmic texture: the long primary note carries the
weight while short secondary notes provide the groove impulse beneath the mix.

Genre references:
  Hardstyle: beat-1 sub sustains long, offbeats short
  Industrial techno: semi-independent sub with gap-fill counter-rhythm
  Hard house: pumping short notes aligned with sidechain envelope
  DnB: long anchor on half-bar downbeat, short fills elsewhere

Sparsity gate: fires at sparsity < 0.65 (present most of the time).
Velocity scales with sparsity duck factor so sub recedes gracefully in Chaos.
"""

from __future__ import annotations

from thelmic.archetypes import PATTERNS
from thelmic.dimensions import Dimensions, PhraseContext
from thelmic.landscape_map import SignatureRhythm
from thelmic.stream_engine import Intent, StructureFrame
from thelmic.voices import make_intent

_DEFAULT_SUB_NOTE = 24   # C1 — fallback when no root_note available

# Duration table: archetype → (primary_dur, secondary_dur) in seconds.
# primary = step coincides with kick, secondary = independent sub step.
# At 174 BPM: 1 beat = 0.345s, 1 bar = 1.379s.
_ARCHETYPE_DUR: dict = {}   # filled below after imports work

# Base durations by genre character:
#   Long sustain: HALF_STEP (industrial mono), AMEN/TWO_STEP (DnB)
#   Short stab:   GABBER, HAPPY_HARDCORE, BREAKBEAT_HARDCORE (hardcore)
#   Mixed:        FOUR_ON_THE_FLOOR (hard house pump), STUTTER/ROLLING
_PRIMARY_DUR_DEFAULT   = 0.38   # ~1.1 beats — primary kick-locked sub hit
_SECONDARY_DUR_DEFAULT = 0.10   # ~0.3 beats — off-kick sub impulse


def _archetype_durations(archetype) -> tuple[float, float]:
    """(primary_dur, secondary_dur) for this archetype."""
    from thelmic.archetypes import RhythmicArchetype as RA
    table = {
        RA.HALF_STEP:          (0.50, 0.12),   # industrial: long on beat 1
        RA.TWO_STEP:           (0.38, 0.10),   # DnB: medium primary, short fill
        RA.SHUFFLED_TWO_STEP:  (0.30, 0.09),
        RA.STUTTER:            (0.20, 0.07),   # stutter: punchy throughout
        RA.ROLLING:            (0.28, 0.08),   # rolling groove
        RA.BREAKBEAT_HARDCORE: (0.14, 0.06),   # hardcore: short stabs
        RA.AMEN:               (0.42, 0.10),   # DnB: long anchor, short fills
        RA.FOUR_ON_THE_FLOOR:  (0.12, 0.08),   # hard house pump: short sidechain notes
        RA.HAPPY_HARDCORE:     (0.10, 0.06),   # very short, rapid
        RA.GABBER:             (0.07, 0.05),   # minimal — kick absorbs sub
    }
    return table.get(archetype, (_PRIMARY_DUR_DEFAULT, _SECONDARY_DUR_DEFAULT))


class SubIntentStream:
    """Sub bass — archetype-driven, primary/secondary hit differentiation."""

    def intents_for_frame(
        self,
        frame: StructureFrame,
        context: PhraseContext,
        dims: Dimensions,
        sr: SignatureRhythm | None = None,
    ) -> tuple[Intent, ...]:
        # Sparsity gate: present most of the time, absent only at deep Chaos
        if dims.sparsity >= 0.65:
            return ()

        pattern   = PATTERNS[context.active_archetype] if context else None
        sub_steps = pattern.sub_steps  if pattern else frozenset({0})

        if frame.step_in_bar not in sub_steps:
            return ()

        # Resolve sub note: one octave below bass root
        if sr is not None:
            sub_note = max(0, min(127, sr.root_note - 12))
        else:
            sub_note = _DEFAULT_SUB_NOTE

        # Bar position determines hit weight — NOT kick coincidence.
        # Sub has its own genre-specific rhythm (from sub_steps); its accents
        # are driven by where the hit falls in the bar, not whether kick is there.
        #
        # primary   = step 0 (bar downbeat) — loudest, long sustain
        # semi      = quarter-note downbeats (4, 8, 12) — medium
        # secondary = all other sub hits — quieter, shorter (genre texture)
        step = frame.step_in_bar
        if step == 0:
            weight = "primary"
        elif step in {4, 8, 12}:
            weight = "semi"
        else:
            weight = "secondary"

        velocity = self._velocity(weight, dims)
        duration = self._duration(weight, context, dims.stability)

        return (make_intent(frame, "sub", f"sub_{weight}", velocity, duration,
                            "archetype_sub", sub_note, 8),)

    def _velocity(self, weight: str, dims: Dimensions) -> int:
        """Bar-position-weighted velocity.

        primary   (step 0): loud downbeat sub — the physical floor hit
        semi      (steps 4/8/12): medium quarter-note accent
        secondary (all others): textural, felt-not-heard sub impulse

        Rules (musical_rules.md, Velocity Dynamics):
        High stability: compressed dynamics. Low stability: extreme contrast.
        """
        stability  = dims.stability
        heat_proxy = 1.0 - stability
        emphasis   = dims.emphasis if dims else 0.0

        if weight == "primary":
            v = int(90 + heat_proxy * 22)    # 90 (cold) → 112 (hot)
        elif weight == "semi":
            v = int(75 + heat_proxy * 18)    # 75 → 93
        else:
            v = int(58 + heat_proxy * 14)    # 58 → 72 — textural, subliminal

        v = int(v * (1.0 + emphasis * 0.20))
        return max(40, min(112, v))

    def _duration(self, weight: str, context, stability: float) -> float:
        """Bar-position-weighted duration.
        primary = long sustain, semi = medium, secondary = short impulse.
        Scales by stability: stable = longer, Chaos = tighter.
        """
        arch = context.active_archetype if context else None
        if arch is None:
            base = {
                "primary": _PRIMARY_DUR_DEFAULT,
                "semi":    _PRIMARY_DUR_DEFAULT * 0.65,
                "secondary": _SECONDARY_DUR_DEFAULT,
            }[weight]
            return max(0.04, base)

        primary_dur, secondary_dur = _archetype_durations(arch)
        semi_dur = (primary_dur + secondary_dur) * 0.5

        base = {"primary": primary_dur, "semi": semi_dur, "secondary": secondary_dur}[weight]

        # Stability scale: Oak (high) sustains longer, Chaos (low) stays tight
        scale = 0.70 + stability * 0.60
        return max(0.04, round(base * scale, 3))
