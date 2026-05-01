"""Three drone voices — sustained tonal background for Ableton processing.

Rules (musical_rules.md — Drone Voices):
  drone_spacey:  high register, full phrase sustain, stable terrain only
  drone_rumble:  sub-bass, half phrase sustain, always present
  drone_tension: mid register, 3-beat sustain per bar, builds with heat

All drones are MIDI signals for Ableton to shape with reverb, filter, pitch.
They fire deterministically from (seed, position, phrase_index).
All are silent in the final 4 bars before a drop (space for the drop itself).
"""

from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from thelmic.bank_generator import BARS_PER_PHRASE, PHRASES_PER_BANK
from thelmic.dimensions import Dimensions, PhraseContext
from thelmic.landscape_map import SignatureRhythm
from thelmic.stream_engine import Intent, StructureFrame
from thelmic.voices import make_intent

if TYPE_CHECKING:
    from thelmic.anticipation_engine import AnticipationState

# Bars per bank  (16 bars total: 4 phrases × 4 bars)
_BARS_PER_BANK = BARS_PER_PHRASE * PHRASES_PER_BANK   # = 16

# Silence window: bars 13–16 (0-indexed 12–15) — final 4 bars before drop
_SILENCE_BARS = frozenset(range(12, 16))


class DroneSpaceyStream:
    """Spacey atmospheric drone — high register, phrase-long sustain.

    Rules: fires at phrase start only; sparsity < 0.40; note = root+24 or root+19.
    """

    def intents_for_frame(
        self,
        frame: StructureFrame,
        context: Optional[PhraseContext] = None,
        dims: Optional[Dimensions] = None,
        sr: Optional[SignatureRhythm] = None,
        ant: Optional["AnticipationState"] = None,
    ) -> tuple[Intent, ...]:
        if sr is None or dims is None:
            return ()
        if dims.sparsity >= 0.40:
            return ()

        bar_0idx = frame.bar_index - 1
        # Silence in final bars before drop
        if ant and ant.mode != "groove" and bar_0idx in _SILENCE_BARS:
            return ()

        # Only fires on the first step of the entire phrase (step 0, bar 0)
        if bar_0idx != 0 or frame.step_in_bar != 0:
            return ()

        # Pitch: alternates between root+24 and root+19 per phrase_index
        # Deterministic: even phrases = octave+1, odd = fifth+octave
        phrase_idx = context.phrase_index if context else 0
        interval   = 24 if phrase_idx % 2 == 0 else 19
        note       = max(0, min(127, sr.root_note + interval))

        # Velocity: stable=65 (distant), unstable=45 (ghostly); + development
        stability = dims.stability
        development = frame.musical_step / 255.0   # 0→1 over bank
        base_vel = int(45 + stability * 20 + development * 12)
        vel      = max(30, min(80, int(base_vel * (1.0 + dims.emphasis * 0.15))))

        # Duration: full 16-bar phrase in seconds at ~174 BPM ≈ 22s
        # We set a long sustain; the deferred note-off system handles it correctly.
        duration = (_BARS_PER_BANK * 4 * 60.0 / 174.0) * 0.95   # just under full phrase

        return (make_intent(frame, "drone_spacey", "atmospheric", vel, duration,
                            "spacey_drone", note, 5),)


class DroneRumbleStream:
    """Low rumble drone — sub-bass register, half-phrase sustain.

    Rules: fires on bars 0 and 8; always present; note = root-12 or root.
    """

    def intents_for_frame(
        self,
        frame: StructureFrame,
        context: Optional[PhraseContext] = None,
        dims: Optional[Dimensions] = None,
        sr: Optional[SignatureRhythm] = None,
        ant: Optional["AnticipationState"] = None,
    ) -> tuple[Intent, ...]:
        if sr is None or dims is None:
            return ()

        bar_0idx = frame.bar_index - 1
        # Silence in final bars before drop
        if ant and ant.mode != "groove" and bar_0idx in _SILENCE_BARS:
            return ()

        # Fires at bar 0 and bar 8 (half-phrase boundaries), step 0 only
        if bar_0idx not in {0, 8} or frame.step_in_bar != 0:
            return ()

        # Pitch: bar 0 = root-12 (below bass), bar 8 = root (unison with bass)
        if bar_0idx == 0:
            note = max(0, min(127, sr.root_note - 12))
        else:
            note = max(0, min(127, sr.root_note))

        # Velocity: scales with heat proxy; cold=50 (distant rumble), hot=75 (powerful)
        heat_proxy = 1.0 - dims.stability
        development = frame.musical_step / 255.0
        vel = int(50 + heat_proxy * 25 + development * 8)
        vel = max(35, min(85, int(vel * (1.0 + dims.emphasis * 0.12))))

        # Duration: 8 bars (half phrase) in seconds
        duration = (8 * 4 * 60.0 / 174.0) * 0.95

        return (make_intent(frame, "drone_rumble", "rumble", vel, duration,
                            "rumble_drone", note, 5),)


class DroneTensionStream:
    """Tension chord drone — mid register, 3-beat sustain per bar.

    Rules: fires on bar downbeat (step 0) each bar; note = root+12; builds with heat.
    """

    def intents_for_frame(
        self,
        frame: StructureFrame,
        context: Optional[PhraseContext] = None,
        dims: Optional[Dimensions] = None,
        sr: Optional[SignatureRhythm] = None,
        ant: Optional["AnticipationState"] = None,
    ) -> tuple[Intent, ...]:
        if sr is None or dims is None:
            return ()

        # Gate: needs structure to drive a chord
        if dims.sparsity >= 0.50 or dims.stability < 0.20:
            return ()

        bar_0idx = frame.bar_index - 1
        # Silence in final bars before drop (space for the release burst)
        if ant and ant.mode != "groove" and bar_0idx in _SILENCE_BARS:
            return ()

        # Only on bar downbeats (step 0)
        if frame.step_in_bar != 0:
            return ()

        note = max(0, min(127, sr.root_note + 12))

        # Velocity: ramps up across phrase; scales with heat
        heat_proxy  = 1.0 - dims.stability
        development = bar_0idx / 15.0   # 0→1 over 16 bars
        vel = int(55 + heat_proxy * 22 + development * 18)
        vel = max(40, min(95, int(vel * (1.0 + dims.emphasis * 0.20))))

        # Duration: 3 beats (0.9s at 174 BPM) — decays before next bar
        duration = 3 * 60.0 / 174.0

        return (make_intent(frame, "drone_tension", "chord", vel, duration,
                            "tension_drone", note, 5),)
