"""GABBER NATIVE KIT — Rotterdam-style hardcore from stock Ableton instruments only.

No samples, no Splice. Every voice is synthesised on Operator and bent into
shape with native audio FX (Overdrive / Saturator / EQ Eight). The signature
gabber kick IS a distorted sine, so this genre is a perfect fit for pure synthesis.

Builds into the CURRENT (blank) Live set:
  T?  ROTTERDAM SKULLKICK  Operator(sine+pitch-env) -> Overdrive -> Saturator -> EQ8
  T?  MENTASM HOOVER       Analog(saw + PWM pulse, LFO swirl, unison) -> Overdrive -> Saturator -> Chorus -> EQ8
  T?  ZAAGBASS             Operator(saw, plucky)    -> Saturator
  T?  TIN HAT              Operator(inharmonic FM tick)  -> EQ8
  T?  KLAP                 Operator(noisy FM burst+feedback) -> EQ8

Then writes a single 4-bar bare-bones gabber loop into scene slot 0:
  kick 4-on-floor (+16th roll fill on the last beat), clap on every 2 & 4,
  offbeat-8th hats, offbeat-8th saw bass, a 4-bar A-minor hoover stab riff.

190 BPM, A minor. Fire scene 1 (top row) in Live to hear it.

    python scripts/gabber_native_kit.py
"""
from __future__ import annotations
import os, sys
os.environ.setdefault("LIVE_CHANNEL_ENABLED", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from thelmic.live_channel import LiveChannel
from thelmic.bridge.helpers import (
    set_param, set_eq_band, to_clip_notes,
    EQ8_BELL, EQ8_HIGH_SHELF,
)


class Frac(float):
    """A 0..1 value meaning 'this fraction of the param's REAL range'.

    Lets amount-style params be set scale-independently: Frac(0.70) is "70% driven"
    whether the param is 0..1 (Saturator Drive) or 0..100 (Overdrive Drive). Plain
    numbers are still treated as absolute values (range-checked by set_param)."""
    __slots__ = ()

TEMPO = 190.0

OPERATOR = "query:Synths#Operator"
ANALOG = "query:Synths#Analog"          # the hoover lives here: real PWM, sub, unison
OVERDRIVE = "query:AudioFx#Overdrive"
SATURATOR = "query:AudioFx#Saturator"
CHORUS = "query:AudioFx#Chorus-Ensemble"   # Live 12; reports as class 'Chorus2'
EQ8 = "query:AudioFx#EQ%20Eight"

# MIDI pitches — bass/kick register (low) and hoover register (lead)
E1, F1, G1, A1, Bb1, C2 = 28, 29, 31, 33, 34, 36
A2 = 45                                          # octave-up kick for the jack
E3, F3, G3, A3, Bb3, C4, D4, E4, F4, G4, A4 = 52, 53, 55, 57, 58, 60, 62, 64, 65, 67, 69
PERC = 60  # nominal note for FM perc voices (pitch sets absolute FM ratio)


def op(**kw):
    """Operator param dict, set by name (all clamped to real range on apply)."""
    return kw


# ----------------------------------------------------------------------
# Instrument definitions: (name, vol, operator-params, fx-chain)
# fx entry = (uri, class_match, {param_name: value})  applied in order
# ----------------------------------------------------------------------

SKULLKICK = op(
    Algorithm=0, Volume=0.72, Tone=1.0,
    **{"Osc-A Wave": 0},                       # sine
    **{"Ae Attack": 0.0, "Ae Decay": 0.48, "Ae Sustain": 0.0, "Ae Release": 0.30},  # tonal tail = pitch reads
    **{"Pe On": 1, "Pe Attack": 0.0, "Pe Peak": 28.0,
       "Pe Decay": 0.22, "Pe Sustain": 0.0, "Pe End": 0.0, "Pe Amount": 1.0},
)

# MENTASM HOOVER on Analog (NOT Operator) — Operator (FM) can't do true PWM, and PWM
# is the defining hoover ingredient. Analog: saw (OSC1) + pulse (OSC2) with the pulse
# width swirled by an LFO, unison detune, resonant LP w/ fast filter env, gentle pitch
# bend. Volume kept low so it hits the downstream Overdrive clean. Params set by name.
HOOVER = {
    "Voices": 6, "Volume": 0.55,                                  # low out -> cool into Overdrive
    "Unison On/Off": 1, "Unison Voices": 1, "Unison Detune": 0.30,
    # OSC1 saw
    "OSC1 On/Off": 1, "OSC1 Shape": 1, "OSC1 Octave": 0, "OSC1 Detune": 0.52, "OSC1 Level": 0.80,
    "PEG1 Amount": 0.12, "PEG1 Time": 0.30,                       # gentle downward pitch bend
    # OSC2 pulse, width swirled by the LFO = PWM (the signature)
    "OSC2 On/Off": 1, "OSC2 Shape": 2, "OSC2 Octave": 0, "OSC2 Detune": 0.56, "OSC2 PW": 0.50,
    "O2 PW < LFO": 0.60, "OSC2 Level": 0.70, "PEG2 Amount": 0.12, "PEG2 Time": 0.30,
    # LFOs drive the swirl
    "LFO1 On/Off": 1, "LFO1 Shape": 0, "LFO1 Speed": 0.55,
    "LFO2 On/Off": 1, "LFO2 Shape": 0, "LFO2 Speed": 0.55,
    # resonant LP + fast filter envelope (the "wow")
    "F1 On/Off": 1, "F1 Type": 1, "F1 Freq": 0.55, "F1 Resonance": 0.40, "F1 Drive": 2, "F1 Freq < Env": 0.45,
    "FEG1 Attack": 0.0, "FEG1 Decay": 0.40, "FEG1 Sustain": 0.25, "FEG1 Rel": 0.35,
    # amp env: slight attack (not dead-vertical), holds for stabs
    "AEG1 Attack": 0.05, "AEG1 Decay": 0.40, "AEG1 Sustain": 0.85, "AEG1 Rel": 0.35, "AMP1 Level": 0.80,
}

ZAAGBASS = op(
    Algorithm=10, Volume=0.92, Tone=0.85,   # no Overdrive makeup -> Operator carries the level
    **{"Osc-A Wave": 6, "Osc-A Level": 1.0},
    **{"Osc-B On": 1, "B Coarse": 1.0, "B Fine": 6.0, "Osc-B Wave": 6, "Osc-B Level": 0.8},
    **{"Filter On": 1, "Filter Freq": 0.40, "Filter Res": 0.30},
    **{"Ae Attack": 0.0, "Ae Decay": 0.35, "Ae Sustain": 0.20, "Ae Release": 0.20},
)

TIN_HAT = op(
    Algorithm=0, Volume=0.94, Tone=1.0,         # algo 0 = B modulates A (FM = metallic); EQ-only chain so push Operator

    **{"Osc-A Wave": 0, "A Coarse": 20.0},
    **{"Osc-B On": 1, "B Coarse": 31.0, "B Fine": 500.0, "Osc-B Level": 0.80},
    **{"Ae Attack": 0.0, "Ae Decay": 0.10, "Ae Sustain": 0.0, "Ae Release": 0.08},
)

KLAP = op(
    Algorithm=0, Volume=0.92, Tone=1.0,         # EQ-only chain so push Operator
    **{"Osc-A Wave": 0, "A Coarse": 8.0, "Osc-A Feedb": 40.0},   # feedback -> noise grit
    **{"Osc-B On": 1, "B Coarse": 13.0, "B Fine": 700.0, "Osc-B Level": 1.0},
    **{"Osc-C On": 1, "C Coarse": 19.0, "C Fine": 300.0, "Osc-C Level": 0.7},
    **{"Ae Attack": 0.0, "Ae Decay": 0.22, "Ae Sustain": 0.0, "Ae Release": 0.12},
)

TRACKS = [
    # Heavy gabber kick: Overdrive bites, then Saturator driven hard (~+25 dB on its
    # dB-mapped 0..1 Drive). KEY MOVE: 'Color Amt Low' 0.39 (UI 'Amt Lo' -22%) pulls
    # the low band OUT of the waveshaper -> sub stays clean & thuddy while the tops
    # distort. Output recovers makeup.
    ("ROTTERDAM SKULLKICK", 0.84, OPERATOR, SKULLKICK,
     [(OVERDRIVE, "Overdrive", {"Drive": Frac(0.65), "Tone": Frac(0.45), "Dry/Wet": Frac(1.0)}),
      (SATURATOR, "Saturator", {"Type": 0.0, "Drive": 0.84, "Color On": 1,
                                "Color Amt Low": 0.39, "Output": Frac(0.72), "Dry/Wet": Frac(1.0)}),
      (EQ8, "Eq8", "KICK_EQ")]),
    # Analog hoover (PWM!) -> moderate Overdrive + soft Saturator -> Chorus -> taming EQ.
    ("MENTASM HOOVER", 0.82, ANALOG, HOOVER,
     [(OVERDRIVE, "Overdrive", {"Drive": Frac(0.50), "Tone": Frac(0.45), "Dry/Wet": Frac(1.0)}),
      (SATURATOR, "Saturator", {"Type": 0.0, "Drive": Frac(0.60), "Output": Frac(0.5), "Dry/Wet": Frac(0.9)}),
      (CHORUS, "Chorus", {}),     # default chorus = lush detuned width
      (EQ8, "Eq8", "HOOVER_EQ")]),
    ("ZAAGBASS", 0.82, OPERATOR, ZAAGBASS,
     [(SATURATOR, "Saturator", {"Drive": 0.35, "Dry/Wet": 1.0})]),
    ("TIN HAT", 0.72, OPERATOR, TIN_HAT,
     [(EQ8, "Eq8", "HAT_EQ")]),
    ("KLAP", 0.80, OPERATOR, KLAP,
     [(EQ8, "Eq8", "CLAP_EQ")]),
]


def _set(ch, t, dev_idx, name, val):
    """Range-aware write: Frac -> fraction of real range, else absolute (checked)."""
    if isinstance(val, Frac):
        set_param(ch, t, dev_idx, name, frac=float(val))
    else:
        set_param(ch, t, dev_idx, name, value=float(val))


def apply_instrument(ch, t, dev_idx, params):
    """Set instrument params by name (works for Operator or Analog — all by-name)."""
    for name, val in params.items():
        try:
            _set(ch, t, dev_idx, name, val)
        except Exception as e:
            print(f"    [skip] instrument '{name}': {e}")


def apply_fx_params(ch, t, dev_idx, params):
    for name, val in params.items():
        try:
            _set(ch, t, dev_idx, name, val)
        except Exception as e:
            print(f"    [skip] fx '{name}': {e}")


def apply_eq_preset(ch, t, dev_idx, preset):
    if preset == "KICK_EQ":
        set_eq_band(ch, t, dev_idx, 1, ftype=EQ8_BELL, hz=90,   gain=4.0, q_norm=0.5)
        set_eq_band(ch, t, dev_idx, 2, ftype=EQ8_BELL, hz=2500, gain=3.0, q_norm=0.4)
        set_eq_band(ch, t, dev_idx, 3, ftype=EQ8_HIGH_SHELF, hz=9000, gain=-3.0)
    elif preset == "HOOVER_EQ":
        set_eq_band(ch, t, dev_idx, 1, ftype=EQ8_BELL,       hz=150,  gain=-6.0, q_norm=0.4)   # thin lows
        set_eq_band(ch, t, dev_idx, 2, ftype=EQ8_BELL,       hz=2500, gain=3.0,  q_norm=0.45)  # bite
        set_eq_band(ch, t, dev_idx, 3, ftype=EQ8_BELL,       hz=5800, gain=-4.0, q_norm=0.55)  # kill fizz
        set_eq_band(ch, t, dev_idx, 4, ftype=EQ8_HIGH_SHELF, hz=9500, gain=-2.0)               # tame top
    elif preset == "HAT_EQ":
        set_eq_band(ch, t, dev_idx, 1, ftype=EQ8_BELL, hz=300, gain=-10.0, q_norm=0.4)
        set_eq_band(ch, t, dev_idx, 2, ftype=EQ8_HIGH_SHELF, hz=8000, gain=3.0)
    elif preset == "CLAP_EQ":
        set_eq_band(ch, t, dev_idx, 1, ftype=EQ8_BELL, hz=200, gain=-4.0, q_norm=0.4)
        set_eq_band(ch, t, dev_idx, 2, ftype=EQ8_HIGH_SHELF, hz=4000, gain=4.0)


# ----------------------------------------------------------------------
# The bare-bones loop (4 bars = 16 beats)
# ----------------------------------------------------------------------
BARS, BEATS = 4, 16


# ---- shared drum voices (identical across riff scenes) ----
def clap_notes():
    return [(PERC, float(b), 0.20, 108) for b in range(BEATS) if b % 2 == 1]  # 2 & 4


def hat_notes():
    return [(PERC, i * 0.5, 0.12, 84 if i % 2 else 70)
            for i in range(BEATS * 2) if (i * 0.5) % 1.0 == 0.5]              # offbeat 8ths


def kick_pulse(root=A1):
    return [(root, float(b), 0.24, 122) for b in range(BEATS)]               # hypnotic 4-floor pulse


# In gabber the hoover is NOT a melody — it's a power chord ("noise bomb") stabbed as a
# rhythmic riff (Wikipedia: "used like a guitar with fast synth riffs ... a heavy-metal
# power chord"). Each scene varies by RHYTHM + the occasional power-chord change, not a
# chord progression. Hoover (power chord, lead reg) and bass (root, low) hammer the SAME
# hook locked together; the kick pounds the root underneath. A stab is (time, root, dur).
def power_riff(stabs):
    hoov, bass = [], []
    for (t, r, d) in stabs:
        for p in (r + 24, r + 31, r + 36):       # root + 5th + octave, two octaves up
            hoov.append((p, t, d, 110))
        bass.append((r, t, d, 106))
    return hoov, bass


def _rave_stab():       # syncopated on/off-beat stab hook
    return [(o + off, A1, 0.20) for o in (0, 4, 8, 12) for off in (0.0, 0.75, 1.5, 2.5, 3.25)]

def _powerchord_riot():  # straight 8ths, one bar shoves to F (bVI power chord) = the hook
    return [(i * 0.5, (F1 if 8 <= i * 0.5 < 12 else A1), 0.18) for i in range(BEATS * 2)]

def _gallop():          # metal gallop X-xx per beat
    return [(b + off, A1, 0.12) for b in range(BEATS) for off in (0.0, 0.5, 0.75)]


# (scene name, stab pattern) — power_riff() turns each into locked hoover + bass.
RIFFS = [
    ("OFFBEAT RIOT",    [(i + 0.5, A1, 0.25) for i in range(BEATS)]),         # kick<->stab interlock
    ("RAVE STAB",       _rave_stab()),
    ("POWERCHORD RIOT", _powerchord_riot()),
    ("GALLOP STORM",    _gallop()),
    ("NOISE BOMB",      [(0, A1, 7.5), (8, F1, 7.5)]),                        # held power-chord screech
]


def roll_notes():
    """Canon 2: dedicated hardcore build roll — 4-on-floor -> 8ths -> 16ths ->
    32nd machine-gun roll, velocity ramping to the slam. Launch this clip to swap
    the kick into a build while the rest of the scene keeps playing."""
    out = []
    for b in range(8):                         # bars 1-2: four-on-floor
        out.append((A1, float(b), 0.22, 118))
    for i in range(8):                         # bar 3: 8ths
        out.append((A1, 8.0 + i * 0.5, 0.16, 108 + i * 2))
    for i in range(8):                         # bar 4 beats 12-13: 16ths
        out.append((A1, 12.0 + i * 0.25, 0.12, 112 + i * 2))
    for i in range(16):                        # bar 4 beats 14-15: 32nds -> slam
        out.append((A1, 14.0 + i * 0.125, 0.08, 116 + min(11, i)))
    return out


# Track-index roles within idxs[] (TRACKS creation order)
KICK_I, HOOV_I, BASS_I, HAT_I, KLAP_I = 0, 1, 2, 3, 4


def main():
    ch = LiveChannel(lower_priority=False)
    ch.start()
    try:
        print("ping:", ch.ping().result(timeout=3))
        ch.set_tempo(TEMPO).result(timeout=3)
        print(f"tempo -> {TEMPO}")

        base = ch.get_session_info().result(timeout=5)["track_count"]
        idxs = []
        for i, (name, *_rest) in enumerate(TRACKS):
            ch.create_midi_track(-1).result(timeout=10)
            t = ch.get_session_info().result(timeout=5)["track_count"] - 1
            ch.set_track_name(t, name).result(timeout=3)
            idxs.append(t)
            print(f"track {t}: {name}")

        # Build each instrument
        for ti, (name, vol, instrument, instparams, fx) in zip(idxs, TRACKS):
            print(f"\n== {name} (track {ti}) ==")
            ch.load_device(ti, instrument).result(timeout=20)
            ch.set_track_volume(ti, vol).result(timeout=3)
            apply_instrument(ch, ti, 0, instparams)
            for uri, klass, params in fx:
                ch.load_device(ti, uri).result(timeout=20)
                info = ch.get_track_info(ti).result(timeout=5)
                dev_idx = info["device_count"] - 1
                if isinstance(params, str):
                    apply_eq_preset(ch, ti, dev_idx, params)
                    print(f"   + {klass} (EQ preset {params}) @dev{dev_idx}")
                else:
                    apply_fx_params(ch, ti, dev_idx, params)
                    print(f"   + {klass} @dev{dev_idx}")

        # Write the riff set: one clever gabber riff per scene row + a roll/fill row
        print("\n== writing gabber riff scenes ==")
        kick_t, hoov_t, bass_t = idxs[KICK_I], idxs[HOOV_I], idxs[BASS_I]
        hat_t, klap_t = idxs[HAT_I], idxs[KLAP_I]
        while ch.get_scene_count().result(timeout=5)["count"] < len(RIFFS) + 1:
            ch.create_scene(-1).result(timeout=5)

        def wclip(t, slot, name, notes):
            try:
                ch.create_clip(t, slot, float(BEATS)).result(timeout=8)
            except Exception:
                pass
            ch.set_clip_name(t, slot, name).result(timeout=3)
            ch.add_notes_to_clip(t, slot, to_clip_notes(notes), replace=True).result(timeout=8)

        for r, (name, stabs) in enumerate(RIFFS):
            hoov, bass = power_riff(stabs)            # hoover + bass hammer the same hook
            wclip(kick_t, r, name, kick_pulse())      # hypnotic root pulse under every riff
            wclip(bass_t, r, name, bass)
            wclip(hoov_t, r, name, hoov)
            wclip(hat_t, r, name, hat_notes())
            wclip(klap_t, r, name, clap_notes())
            try:
                ch.set_scene_name(r, name).result(timeout=3)
            except Exception:
                pass
            print(f"   row {r}: {name}")

        # dedicated hardcore kick-roll fill on its own scene row
        roll_row = len(RIFFS)
        wclip(kick_t, roll_row, "ROTTERDAM ROLL", roll_notes())
        try:
            ch.set_scene_name(roll_row, "ROLL / FILL").result(timeout=3)
        except Exception:
            pass
        print(f"   row {roll_row}: ROLL / FILL (kick only)")

        ch.set_launch_quantization(1).result(timeout=3)   # 1-bar launch quant
        print("\nDONE. Fire scenes 1-5 for the riffs; launch the ROLL clip as a fill.")
        print("Scenes:", ", ".join(f"{r}:{name}" for r, (name, *_ ) in enumerate(RIFFS)))
    finally:
        ch.stop()


if __name__ == "__main__":
    main()
