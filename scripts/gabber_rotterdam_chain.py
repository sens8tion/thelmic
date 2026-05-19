"""ROTTERDAM_CHAIN — gabber-esque 8-scene hardcore session at 190 BPM in Am.

Hand-composed MIDI through LiveChannel. No thelmic generators — explicit
note dicts per scene per lane.

Lane plan (7 lanes):
  T0  KICK_ROTTERDAM   Drum Rack  — distorted 909 gabber kick (pad 36)
  T1  PERC_INDUSTRIAL  Drum Rack  — hats 42/46, clap 39, metal 47
  T2  SUB_PUNCH        MIDI synth — Operator sub sine, kick-tied short stabs
  T3  HOOVER_LEAD      MIDI synth — Operator detuned saw, dark Am melodic
  T4  STAB_HARDCORE    MIDI synth — supersaw chord stabs (Am / F / G / E)
  T5  SIREN_FX         MIDI synth — air-raid pitch sweep via LFO
  T6  VOX_SHOUT        MIDI synth — short blip stand-in for "HARDCORE!"

Scene plan (each = 8 bars × 4 beats = 32 beats, 190 BPM ≈ 10.1 s/scene):
  S0 BLACKOUT          sirens + atmos only, no kick
  S1 KICK_ENTRY        pure 4OTF kick + sub punch
  S2 IRON_MARCH        + hats + clap + first siren wail
  S3 HOOVER_DROP       hoover lead enters dark Am riff
  S4 ANNIHILATION      full stack — stabs + vox shouts + double-kicks
  S5 BREAKDOWN_BLOOD   kicks out, hoover screams long held notes
  S6 REBUILD_HAMMER    kicks return per-bar -> per-beat -> 8ths
  S7 NUCLEAR           double-kicks + triplet rolls + chord stabs + vox carpet

Instruments are NOT loaded by this script — the user must:
  - Drop Selectah Kit (or any bare DrumGroupDevice .adg) on T0 and T1, then
    hot-swap pads with the desired gabber kick + industrial perc samples.
  - Drop Operator (or any synth) on T2-T6 with appropriate patches.

The script creates lanes, scenes, baked tempo, and writes all MIDI clips.
"""
from __future__ import annotations
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from thelmic.live_channel import LiveChannel

# --- constants ----------------------------------------------------------
BPM        = 190.0
SCENE_LEN  = 32.0    # 8 bars × 4 beats
N_BASE_SCENES = 8    # the clean arc — core 7 lanes only
N_SCENES      = 16   # base + depraved (S8-S15 mirror S0-S7 with depraved lanes)

CORE_LANES = {"KICK_ROTTERDAM", "PERC_INDUSTRIAL", "SUB_PUNCH", "HOOVER_LEAD",
              "STAB_HARDCORE", "SIREN_FX", "VOX_SHOUT"}
DEPRAVED_LANES = {"KICK_VEIN", "ACID_TONGUE", "DRONE_CRYPT", "REVERSE_VOID",
                  "CHOIR_NECRO", "SCREAM_BLEACH", "STAB_BWAAH", "NOISE_OSSUARY"}

LANE_NAMES = [
    "KICK_ROTTERDAM",
    "PERC_INDUSTRIAL",
    "SUB_PUNCH",
    "HOOVER_LEAD",
    "STAB_HARDCORE",
    "SIREN_FX",
    "VOX_SHOUT",
    # depraved layer — added 2026-05-19, follows the A-phrygian theory
    "KICK_VEIN",        # pitched 2nd-kick that root-follows the progression
    "ACID_TONGUE",      # TB-303 squelch in A phrygian
    "DRONE_CRYPT",      # sustained dread pad
    "REVERSE_VOID",     # reverse-suck swells before drops
    "CHOIR_NECRO",      # demonic chant cluster
    "SCREAM_BLEACH",    # distorted vocal screams doubling hoover peaks
    "STAB_BWAAH",       # terror-orchestral hits
    "NOISE_OSSUARY",    # white noise crescendo in builds
]
LANE_COLORS = [3, 13, 1, 14, 5, 7, 10,
               # depraved: dark reds + purples + black-ish
               2, 11, 19, 17, 16, 4, 12, 18]

BASE_SCENE_NAMES = [
    "BLACKOUT",
    "KICK_ENTRY",
    "IRON_MARCH",
    "HOOVER_DROP",
    "ANNIHILATION",
    "BREAKDOWN_BLOOD",
    "REBUILD_HAMMER",
    "NUCLEAR",
]
# Depraved scene names — each pushes the equivalent base scene one notch
# darker. Same arc shape, more menace per name.
DEPRAVED_SCENE_NAMES = [
    "BLACKOUT_BLEEDING",
    "KICK_ENTRY_RABID",
    "IRON_MARCH_BLISTERED",
    "HOOVER_DROP_DEFILED",
    "ANNIHILATION_UNSEALED",
    "BREAKDOWN_RANCID",
    "REBUILD_DEMONIC",
    "NUCLEAR_TERMINAL",
]
SCENE_NAMES = BASE_SCENE_NAMES + DEPRAVED_SCENE_NAMES

# Scene colors: dark/blue intro -> orange -> red peak -> black breakdown ->
# orange rebuild -> magenta nuclear. Depraved variants use darker / more
# saturated palette indices. Live's palette indices are 0-69.
BASE_SCENE_COLORS = [
    20,  # BLACKOUT          — dark navy
    14,  # KICK_ENTRY        — desaturated red
     6,  # IRON_MARCH        — orange
     3,  # HOOVER_DROP       — bright red
     1,  # ANNIHILATION      — neon red
    20,  # BREAKDOWN_BLOOD   — dark navy (return-to-void)
     6,  # REBUILD_HAMMER    — orange
     2,  # NUCLEAR           — hot magenta
]
# Depraved scene colors — darker / more saturated variants
DEPRAVED_SCENE_COLORS = [
    19,  # BLACKOUT_BLEEDING     — black-purple
    16,  # KICK_ENTRY_RABID      — deep crimson
    17,  # IRON_MARCH_BLISTERED  — burnt orange
     2,  # HOOVER_DROP_DEFILED   — hot magenta
     4,  # ANNIHILATION_UNSEALED — blood red
    19,  # BREAKDOWN_RANCID      — black-purple
     4,  # REBUILD_DEMONIC       — blood red
    18,  # NUCLEAR_TERMINAL      — black-magenta
]
SCENE_COLORS = BASE_SCENE_COLORS + DEPRAVED_SCENE_COLORS

# Drum pads (Selectah Kit GM mapping)
KICK   = 36
SNARE  = 38   # snare drum — stacked with clap on 2/4 for the classic gabber thump
CLAP   = 39
METAL  = 47
HATC   = 42
HATO   = 46

# Am pitches — root octave centred at A2=45.
# G#3 (56), Bb2 (46), Bb3 (58), Bb4 (70) added for the phrygian / harmonic-minor
# pincer notes (per The Mover + Angerfist extraction analysis — both tracks
# weight G# leading-tone and Bb flat-2 heavily around the A root).
A1, E2, A2, Bb2, B2, C3, D3, E3, F3, G3, Gs3, A3, Bb3, B3, C4, D4, E4, F4, G4, Bb4 = (
    33, 40, 45, 46, 47, 48, 50, 52, 53, 55, 56, 57, 58, 59, 60, 62, 64, 65, 67, 70
)
# Gabber sub root — A0 area for tectonic weight (kick-tied)
A0_SUB = 21

# 8-bar root progression: 2-bar holds per chord. This is the SAME progression
# the kick-bass-sub-stab-hoover all hew to — gabber locks every voice to the
# same harmonic skeleton, that's where the relentless power comes from.
# Am - Am - F - F - G - G - Em - Em
ROOT_PROG = [A0_SUB, A0_SUB, A0_SUB - 4, A0_SUB - 4,
             A0_SUB - 2, A0_SUB - 2, A0_SUB + 7 - 12, A0_SUB + 7 - 12]
# Stab chord voicings indexed by bar — power-chord-style for that supersaw width
AM_CHORD = [A2, E3, A3]   # root + 5th + octave
F_CHORD  = [F3 - 12, C3, F3]
G_CHORD  = [G3 - 12, D3, G3]
EM_CHORD = [E3 - 12, B2, E3]
CHORD_PROG = [AM_CHORD, AM_CHORD, F_CHORD, F_CHORD,
              G_CHORD,  G_CHORD,  EM_CHORD, EM_CHORD]

# === HOOVER ANTHEM RIFF ==================================================
# 4-bar rave riff in Am, classic call-answer-push-resolve shape.
# Repeated 2× per scene (8 bars total). Inspired by Rotterdam Termination
# Source / Charly-era gabber leads — simple, chantable, dotted-quarter +
# eighth motif that lands hard on the 1.
#
# Bar 1: A3 dotted-quarter, A3 eighth, E4 half          (CALL low->peak)
# Bar 2: A3 quarter, B3 eighth, A3 eighth, G3 half      (ANSWER)
# Bar 3: A3 dotted-quarter, A3 eighth, F4 half          (PUSH higher)
# Bar 4: G3 eighth, F3 eighth, E3 eighth, D3 eighth, A2 half  (DESCENT)
HOOVER_4BAR = [
    # bar 1 — CALL   (G#3 leading-tone pickup pulls into E4 peak)
    (0.0,  A3,  1.5,  108),
    (1.5,  Gs3, 0.5,   95),   # harmonic-minor pull
    (2.0,  E4,  2.0,  115),
    # bar 2 — ANSWER (Bb3 phrygian shadow before A3 + G3 resolution)
    (4.0,  A3,  1.0,  100),
    (5.0,  Bb3, 0.5,   95),   # phrygian flat-2
    (5.5,  A3,  0.5,   95),
    (6.0,  G3,  2.0,  108),
    # bar 3 — PUSH   (G#3 pickup again, this time pulling up to F4 peak)
    (8.0,  A3,  1.5,  110),
    (9.5,  Gs3, 0.5,   95),
    (10.0, F4,  2.0,  118),
    # bar 4 — DESCENT (Bb2 phrygian crash before the A2 root rest)
    (12.0, G3,  0.5,  100),
    (12.5, F3,  0.5,  100),
    (13.0, E3,  0.5,  100),
    (13.5, Bb2, 0.5,  102),   # phrygian descent step
    (14.0, A2,  2.0,  105),
]


# --- KICK_ROTTERDAM ------------------------------------------------------
def kick_pattern(s: int) -> list[dict]:
    """Distorted 4OTF gabber kick — kick IS the bass.

    Velocity is high across the board; gabber kicks are uniform-loud, the
    variation comes from the distorted sample's interaction at peak, not from
    velocity dynamics.
    """
    notes: list[dict] = []
    if s == 0:    # BLACKOUT — silent
        return []
    if s == 1:    # KICK_ENTRY — pure 4OTF, no embellishment
        for beat in range(32):
            notes.append({"pitch": KICK, "start_time": float(beat),
                          "duration": 0.4, "velocity": 115})
    elif s == 2:  # IRON_MARCH — 4OTF + ghost on &-of-2
        for beat in range(32):
            notes.append({"pitch": KICK, "start_time": float(beat),
                          "duration": 0.4, "velocity": 116})
        for bar in range(8):
            notes.append({"pitch": KICK, "start_time": float(bar*4 + 1.5),
                          "duration": 0.25, "velocity": 92})
    elif s == 3:  # HOOVER_DROP — 4OTF + double-up on &-of-4 (Rotterdam stomp)
        for beat in range(32):
            notes.append({"pitch": KICK, "start_time": float(beat),
                          "duration": 0.4, "velocity": 118})
        for bar in range(8):
            notes.append({"pitch": KICK, "start_time": float(bar*4 + 3.5),
                          "duration": 0.25, "velocity": 105})
    elif s == 4:  # ANNIHILATION — double-kicks: every beat + every &
        for half in range(64):
            t = half * 0.5
            v = 120 if half % 2 == 0 else 100
            notes.append({"pitch": KICK, "start_time": t, "duration": 0.35, "velocity": v})
    elif s == 5:  # BREAKDOWN_BLOOD — kicks GONE except a single bar-7 roll preview
        for i in range(8):  # 8th-note kick roll on the final bar (bar 7)
            notes.append({"pitch": KICK, "start_time": 28.0 + i * 0.5,
                          "duration": 0.3, "velocity": 80 + i * 5})
    elif s == 6:  # REBUILD_HAMMER — per-bar -> per-beat -> 8ths acceleration
        # bars 0-1: 1 hit per bar
        for bar in range(2):
            notes.append({"pitch": KICK, "start_time": float(bar*4),
                          "duration": 0.4, "velocity": 110})
        # bars 2-3: 2 hits per bar (1, 3)
        for bar in range(2, 4):
            for off in (0.0, 2.0):
                notes.append({"pitch": KICK, "start_time": float(bar*4 + off),
                              "duration": 0.4, "velocity": 112})
        # bars 4-5: 4OTF
        for beat in range(16, 24):
            notes.append({"pitch": KICK, "start_time": float(beat),
                          "duration": 0.4, "velocity": 115})
        # bars 6-7: 8ths
        for half in range(16):
            notes.append({"pitch": KICK, "start_time": 24.0 + half * 0.5,
                          "duration": 0.3, "velocity": 118})
    elif s == 7:  # NUCLEAR — 4OTF + ALL the &-doubles + 16th triplet roll fills
        for beat in range(32):
            notes.append({"pitch": KICK, "start_time": float(beat),
                          "duration": 0.35, "velocity": 122})
            # & double on every beat
            notes.append({"pitch": KICK, "start_time": float(beat) + 0.5,
                          "duration": 0.3, "velocity": 102})
        # 16th-triplet roll on the last beat of bars 3 and 7
        for bar in (3, 7):
            for i in range(6):  # 6 hits across one beat = 16th-triplets
                notes.append({"pitch": KICK, "start_time": float(bar*4 + 3) + i * (1.0/6.0),
                              "duration": 0.12, "velocity": 110})
    return notes


# --- PERC_INDUSTRIAL -----------------------------------------------------
def _snare_clap_stack(bar: int) -> list[dict]:
    """The signature gabber backbeat: snare + reverbed clap stacked on 2 + 4.
    Single voice would be too thin; stacking thickens the impact, which is
    what wet-reverb claps in Rotterdam tracks deliver."""
    out = []
    for off in (1.0, 3.0):
        t = float(bar*4 + off)
        out.append({"pitch": SNARE, "start_time": t, "duration": 0.3, "velocity": 95})
        out.append({"pitch": CLAP,  "start_time": t, "duration": 0.3, "velocity": 110})
    return out


def perc_pattern(s: int) -> list[dict]:
    """Snare+clap stack on 2/4, open hats between kicks for drive, metal hits
    on key accents. The OH offbeat is the relentless drive — it's there in
    nearly every scene with kicks."""
    notes: list[dict] = []
    if s in (0, 1):  # silent in BLACKOUT + KICK_ENTRY (austere intro)
        return []
    if s == 5:       # BREAKDOWN — kick out, perc reduced to industrial pulse
        for bar in range(8):
            notes.append({"pitch": METAL, "start_time": float(bar*4),
                          "duration": 0.5, "velocity": 95})
        # Sparse claps to mark the bar — feels like the room is half-empty
        for bar in range(0, 8, 2):
            notes.append({"pitch": CLAP, "start_time": float(bar*4 + 2),
                          "duration": 0.4, "velocity": 85})
        return notes
    # Snare+clap stack on 2/4 — the signature gabber backbeat
    for bar in range(8):
        notes.extend(_snare_clap_stack(bar))
    if s == 2:    # IRON_MARCH — 8th closed hats + offbeat OH (drive starts here)
        for i in range(64):
            notes.append({"pitch": HATC, "start_time": i * 0.5,
                          "duration": 0.18, "velocity": 75 if i % 2 == 0 else 58})
        for bar in range(8):
            notes.append({"pitch": HATO, "start_time": float(bar*4 + 1.5),
                          "duration": 0.4, "velocity": 88})
            notes.append({"pitch": HATO, "start_time": float(bar*4 + 3.5),
                          "duration": 0.4, "velocity": 88})
    elif s == 3:  # HOOVER_DROP — 8th hats + offbeat OH everywhere
        for i in range(64):
            notes.append({"pitch": HATC, "start_time": i * 0.5,
                          "duration": 0.18, "velocity": 78 if i % 2 == 0 else 60})
        for bar in range(8):
            for off in (0.5, 1.5, 2.5, 3.5):
                notes.append({"pitch": HATO, "start_time": float(bar*4 + off),
                              "duration": 0.4, "velocity": 92})
    elif s == 4:  # ANNIHILATION — 16th hats + dense OH + metal accents on bar 1+3
        for i in range(128):
            notes.append({"pitch": HATC, "start_time": i * 0.25,
                          "duration": 0.1, "velocity": 80 if i % 4 == 0 else 60})
        for bar in range(8):
            for off in (0.5, 1.5, 2.5, 3.5):
                notes.append({"pitch": HATO, "start_time": float(bar*4 + off),
                              "duration": 0.3, "velocity": 95})
            notes.append({"pitch": METAL, "start_time": float(bar*4),
                          "duration": 0.3, "velocity": 105})
            notes.append({"pitch": METAL, "start_time": float(bar*4 + 2),
                          "duration": 0.3, "velocity": 100})
    elif s == 6:  # REBUILD — hats accelerate alongside the kick
        for i in range(16):    # bars 0-1: 8ths
            notes.append({"pitch": HATC, "start_time": i * 0.5,
                          "duration": 0.15, "velocity": 65})
        for i in range(32):    # bars 2-3: 16ths
            notes.append({"pitch": HATC, "start_time": 8.0 + i * 0.25,
                          "duration": 0.12, "velocity": 70})
        for i in range(48):    # bars 4-5: 16th triplets
            notes.append({"pitch": HATC, "start_time": 16.0 + i * (1.0/3.0),
                          "duration": 0.1, "velocity": 75})
        for i in range(64):    # bars 6-7: 32nds — climax carpet
            notes.append({"pitch": HATC, "start_time": 24.0 + i * 0.125,
                          "duration": 0.08, "velocity": 80 if i % 4 == 0 else 65})
        # Snare roll across the final bar — drum-fill announcement
        for i in range(16):
            notes.append({"pitch": SNARE, "start_time": 28.0 + i * 0.25,
                          "duration": 0.1, "velocity": 60 + i * 4})
    elif s == 7:  # NUCLEAR — 16th carpet + dense OH + metal on every bar
        for i in range(128):
            notes.append({"pitch": HATC, "start_time": i * 0.25,
                          "duration": 0.1, "velocity": 85 if i % 4 == 0 else 65})
        for bar in range(8):
            for off in (0.5, 1.5, 2.5, 3.5):
                notes.append({"pitch": HATO, "start_time": float(bar*4 + off),
                              "duration": 0.3, "velocity": 100})
            notes.append({"pitch": METAL, "start_time": float(bar*4),
                          "duration": 0.5, "velocity": 110})
    return notes


# --- SUB_PUNCH -----------------------------------------------------------
def sub_pattern(s: int) -> list[dict]:
    """Sub-bass kick-tied stabs. In gabber the kick AND sub move as one
    voice — the sub's root follows the 8-bar progression in 2-bar holds
    (Am Am F F G G Em Em), kick-tied so every kick hit is doubled by the
    same-pitched sub punch. Drops out during no-kick scenes."""
    notes: list[dict] = []
    if s in (0, 5):  # silent — let the void / hoover scream do the work
        return []
    if s == 1:       # KICK_ENTRY — every kick gets a sub punch on root (Am)
        for beat in range(32):
            notes.append({"pitch": A0_SUB, "start_time": float(beat),
                          "duration": 0.25, "velocity": 102})
    elif s == 2:     # IRON_MARCH — same austerity, still root
        for beat in range(32):
            notes.append({"pitch": A0_SUB, "start_time": float(beat),
                          "duration": 0.25, "velocity": 104})
    elif s == 3:     # HOOVER_DROP — root follows progression per bar
        for bar in range(8):
            root = ROOT_PROG[bar]
            for beat in range(4):
                notes.append({"pitch": root, "start_time": float(bar*4 + beat),
                              "duration": 0.25, "velocity": 104})
    elif s == 4:     # ANNIHILATION — root follows progression + & doubles
        for bar in range(8):
            root = ROOT_PROG[bar]
            for half in range(8):
                t = bar*4 + half*0.5
                v = 108 if half % 2 == 0 else 90
                notes.append({"pitch": root, "start_time": float(t),
                              "duration": 0.2, "velocity": v})
    elif s == 6:     # REBUILD — accelerate alongside kick, root stays Am
        for bar in range(2):    # bars 0-1: per-bar
            notes.append({"pitch": A0_SUB, "start_time": float(bar*4),
                          "duration": 0.3, "velocity": 95})
        for bar in range(2, 4): # bars 2-3: 2 per bar
            for off in (0.0, 2.0):
                notes.append({"pitch": A0_SUB, "start_time": float(bar*4 + off),
                              "duration": 0.3, "velocity": 100})
        for beat in range(16, 24):  # bars 4-5: per-beat
            notes.append({"pitch": A0_SUB, "start_time": float(beat),
                          "duration": 0.25, "velocity": 105})
        for half in range(16):  # bars 6-7: 8ths
            notes.append({"pitch": A0_SUB, "start_time": 24.0 + half * 0.5,
                          "duration": 0.2, "velocity": 110})
    elif s == 7:     # NUCLEAR — root follows progression + every & punch
        for bar in range(8):
            root = ROOT_PROG[bar]
            for half in range(8):
                t = bar*4 + half*0.5
                v = 116 if half % 2 == 0 else 96
                notes.append({"pitch": root, "start_time": float(t),
                              "duration": 0.2, "velocity": v})
    return notes


# --- HOOVER_LEAD ---------------------------------------------------------
def _emit_riff(notes: list[dict], base: float, oct_shift: int = 0,
               vel_offset: int = 0) -> None:
    """Emit one 4-bar pass of the HOOVER_4BAR anthem starting at `base` beats,
    with optional octave shift and velocity offset."""
    for (t, p, d, v) in HOOVER_4BAR:
        notes.append({
            "pitch":      p + oct_shift,
            "start_time": base + t,
            "duration":   d,
            "velocity":   max(1, min(127, v + vel_offset)),
        })


def hoover_pattern(s: int) -> list[dict]:
    """Anthemic 4-bar rave riff repeated 2× per scene. Gabber leads are
    simple, chantable, and locked to the harmonic skeleton — that's where
    the singalong-stomp energy comes from."""
    notes: list[dict] = []
    if s in (0, 1, 2, 6):
        return []
    if s == 3:    # HOOVER_DROP — single-voice riff ×2 (4 bars × 2 = 8 bars)
        _emit_riff(notes, 0.0)
        _emit_riff(notes, 16.0)
    elif s == 4:  # ANNIHILATION — riff ×2, octave-stacked (lead + above)
        for base in (0.0, 16.0):
            _emit_riff(notes, base)
            _emit_riff(notes, base, oct_shift=+12, vel_offset=-18)
    elif s == 5:  # BREAKDOWN_BLOOD — long held screams descend the riff peaks
        # Pull out the peak notes (E4 / G3 / F4 / A2) and hold them long
        screams = [E4, G3, F4, A3]
        for i, p in enumerate(screams):
            notes.append({"pitch": p, "start_time": float(i * 8),
                          "duration": 7.5, "velocity": 110})
            # minor-2nd ghost a half-bar later for that dystopian wobble
            notes.append({"pitch": p + 1, "start_time": float(i * 8) + 2.0,
                          "duration": 5.0, "velocity": 80})
    elif s == 7:  # NUCLEAR — riff ×2 octave-stacked + tail wail on E4
        for base in (0.0, 16.0):
            _emit_riff(notes, base, vel_offset=+5)
            _emit_riff(notes, base, oct_shift=+12, vel_offset=-15)
        # Final-bar wail — held E4 over the whole bar
        notes.append({"pitch": E4, "start_time": 28.0, "duration": 4.0, "velocity": 118})
    return notes


# --- STAB_HARDCORE -------------------------------------------------------
def stab_pattern(s: int) -> list[dict]:
    """Supersaw stab DOUBLES THE HOOVER LEAD (octave above + chord skeleton
    under it). That's the classic gabber lead-stack — the same riff played
    on a different timbre creates the wall-of-sound peak. Plus power-chord
    pads on bar 1 + 3 of each bar to fill harmonic body.

    Also fires a single phrygian Bb-major crash at the start of S5
    BREAKDOWN_BLOOD — the dystopian "darkness drops" moment. Bb-D-F sits
    a half-step above A and lands HARD on the void."""
    notes: list[dict] = []
    if s == 5:
        # Single Bb-major triad on beat 1 — Bb3 / D4 / F4, long held into the void
        for p in (Bb3, D4, F4):
            notes.append({"pitch": p, "start_time": 0.0,
                          "duration": 6.0, "velocity": 112})
        # Echo an octave up for the screech ceiling
        for p in (Bb4, D4 + 12, F4 + 12):
            notes.append({"pitch": p, "start_time": 0.0,
                          "duration": 4.0, "velocity": 92})
        return notes
    if s not in (4, 7):
        return []
    # Power-chord pads on 1 + 3 of each bar (root + 5th + octave)
    for bar, chord in enumerate(CHORD_PROG):
        for off in (0.0, 2.0):
            for p in chord:
                notes.append({"pitch": p, "start_time": float(bar*4 + off),
                              "duration": 1.5, "velocity": 100})
    # Double the hoover riff an octave UP — the supersaw lead-stack
    for base in (0.0, 16.0):
        _emit_riff(notes, base, oct_shift=+12, vel_offset=-10)
    if s == 7:  # NUCLEAR — additional rhythmic stabs on every beat last 2 bars
        for beat in range(24, 32):
            chord = CHORD_PROG[beat // 4]
            for p in chord:
                notes.append({"pitch": p, "start_time": float(beat),
                              "duration": 0.4, "velocity": 110})
    return notes


# --- SIREN_FX ------------------------------------------------------------
def siren_pattern(s: int) -> list[dict]:
    """Air-raid siren. Long held notes that the SIREN_FX synth's LFO sweeps
    pitch around. Pitch picked is roughly Am-related (A3 / E3) to keep it
    diegetic to the key.

    Sirens carry the tension across the no-kick scenes (0 + 5) and accent
    transitions in heavier scenes."""
    notes: list[dict] = []
    if s == 0:    # BLACKOUT — full-scene siren, 2 swells
        notes.append({"pitch": A3, "start_time": 0.0,  "duration": 16.0, "velocity": 90})
        notes.append({"pitch": A3, "start_time": 16.0, "duration": 16.0, "velocity": 105})
    elif s == 1:  # KICK_ENTRY — silent, let the kick alone
        return []
    elif s == 2:  # IRON_MARCH — one swell on bars 5-8
        notes.append({"pitch": A3, "start_time": 16.0, "duration": 16.0, "velocity": 95})
    elif s == 3:  # HOOVER_DROP — punctuation hits every 2 bars
        for bar in range(0, 8, 2):
            notes.append({"pitch": E3, "start_time": float(bar*4),
                          "duration": 8.0, "velocity": 80})
    elif s == 4:  # ANNIHILATION — long siren through whole scene, two voices
        notes.append({"pitch": A3, "start_time": 0.0,  "duration": 32.0, "velocity": 90})
        notes.append({"pitch": E3, "start_time": 8.0,  "duration": 24.0, "velocity": 75})
    elif s == 5:  # BREAKDOWN_BLOOD — sirens are foreground, 4 swells building
        for i in range(4):
            notes.append({"pitch": A3, "start_time": float(i * 8),
                          "duration": 8.0, "velocity": 90 + i * 8})
    elif s == 6:  # REBUILD — single swell crescendoing
        notes.append({"pitch": A3, "start_time": 0.0, "duration": 32.0, "velocity": 100})
        # extra octave-down voice for weight on bars 4-7
        notes.append({"pitch": A2, "start_time": 16.0, "duration": 16.0, "velocity": 95})
    elif s == 7:  # NUCLEAR — siren carpet, three voices
        notes.append({"pitch": A3, "start_time": 0.0,  "duration": 32.0, "velocity": 100})
        notes.append({"pitch": E3, "start_time": 0.0,  "duration": 32.0, "velocity": 85})
        notes.append({"pitch": E4, "start_time": 16.0, "duration": 16.0, "velocity": 95})
    return notes


# --- VOX_SHOUT -----------------------------------------------------------
def vox_pattern(s: int) -> list[dict]:
    """Short percussive shouts. Single-note (C4) stabs on the back-beat in
    heavy scenes. User can replace synth with a chopped vocal sample later;
    the rhythmic placement is what matters."""
    notes: list[dict] = []
    if s == 4:    # ANNIHILATION — shout on every bar's beat 4 + bar 8 cluster
        for bar in range(8):
            notes.append({"pitch": C4, "start_time": float(bar*4 + 3),
                          "duration": 0.3, "velocity": 110})
        # cluster on bar 8 beat 4: 4 hits 16th apart
        for i in range(4):
            notes.append({"pitch": C4, "start_time": 31.0 + i * 0.25,
                          "duration": 0.15, "velocity": 105})
    elif s == 7:  # NUCLEAR — shout on every 1 + 3 + clustered ramp at end
        for bar in range(8):
            notes.append({"pitch": C4, "start_time": float(bar*4),
                          "duration": 0.25, "velocity": 112})
            notes.append({"pitch": C4, "start_time": float(bar*4 + 2),
                          "duration": 0.25, "velocity": 108})
        # final-bar carpet: 8 shouts on 8ths
        for i in range(8):
            notes.append({"pitch": C4, "start_time": 28.0 + i * 0.5,
                          "duration": 0.2, "velocity": 100 + i * 3})
    return notes


# =========================================================================
# DEPRAVED LAYER  — 8 lanes added 2026-05-19 after Convert-to-MIDI analysis
# =========================================================================

# --- KICK_VEIN -----------------------------------------------------------
# Pitched second kick that root-follows the progression Am-Am-F-F-G-G-Em-Em.
# In real Rotterdam productions the bass kick CHANGES PITCH to track the
# bassline — making the kick itself the lead bass melody. Drum-rack pads
# can't easily do per-hit pitch, so this is a separate MIDI synth lane
# playing kick-shaped percussive notes at the chord roots, kick-tied to
# the main kick rhythm.
def kick_vein_pattern(s: int) -> list[dict]:
    notes: list[dict] = []
    if s not in (1, 3, 4, 7):
        return []
    # Root pitch per bar — one octave above the sub root for kick-bass register
    BAR_ROOTS = [r + 12 for r in ROOT_PROG]  # A1-A1-F1-F1-G1-G1-E1-E1 area
    if s == 1:    # KICK_ENTRY — austere, root only, every kick
        for beat in range(32):
            notes.append({"pitch": A0_SUB + 12, "start_time": float(beat),
                          "duration": 0.3, "velocity": 110})
    elif s == 3:  # HOOVER_DROP — follows progression, every kick
        for bar in range(8):
            root = BAR_ROOTS[bar]
            for beat in range(4):
                notes.append({"pitch": root, "start_time": float(bar*4 + beat),
                              "duration": 0.3, "velocity": 112})
    elif s == 4:  # ANNIHILATION — progression + & doubles
        for bar in range(8):
            root = BAR_ROOTS[bar]
            for half in range(8):
                t = bar*4 + half*0.5
                notes.append({"pitch": root, "start_time": float(t),
                              "duration": 0.25, "velocity": 116 if half % 2 == 0 else 95})
    elif s == 7:  # NUCLEAR — progression + every 8th + triplet roll on bar ends
        for bar in range(8):
            root = BAR_ROOTS[bar]
            for half in range(8):
                t = bar*4 + half*0.5
                notes.append({"pitch": root, "start_time": float(t),
                              "duration": 0.25, "velocity": 120 if half % 2 == 0 else 100})
            # Triplet roll on bar 3 + 7 last beat
            if bar in (3, 7):
                for i in range(6):
                    notes.append({"pitch": root, "start_time": float(bar*4 + 3) + i * (1.0/6.0),
                                  "duration": 0.12, "velocity": 108})
    return notes


# --- ACID_TONGUE ---------------------------------------------------------
# TB-303-style 16th-note squelch in A phrygian. The 2-bar pattern emphasizes
# A root, slides up to Bb (phrygian flat-2) and G# (harmonic-minor leading
# tone), descends through F and back. Plays in peak scenes only.
ACID_2BAR = [
    # (beat_offset_within_2bar, pitch, duration, velocity)
    # bar 1 — pulsing root + b2 punctuation
    (0.0,   A1,  0.25, 105),
    (0.25,  A1,  0.25,  90),
    (0.5,   Bb2, 0.25, 100),
    (0.75,  A1,  0.25,  90),
    (1.0,   A2,  0.25, 110),  # accent — octave up
    (1.25,  A1,  0.25,  85),
    (1.5,   Bb2, 0.25,  95),
    (1.75,  G3-12, 0.25, 80),  # G2 — minor 7
    (2.0,   A1,  0.25, 100),
    (2.25,  A1,  0.25,  80),
    (2.5,   Bb2, 0.25,  95),
    (2.75,  A1,  0.25,  80),
    (3.0,   E3-12, 0.25, 100),  # E2 — perfect 5th
    (3.25,  A1,  0.25,  80),
    (3.5,   Bb2, 0.25,  90),
    (3.75,  A1,  0.25,  80),
    # bar 2 — descent + G# leading-tone tension
    (4.0,   A2,  0.25, 110),  # accent — octave
    (4.25,  G3-12, 0.25, 90),  # G2
    (4.5,   F3-12, 0.25, 95),  # F2 — phrygian b6
    (4.75,  E3-12, 0.25, 90),  # E2
    (5.0,   A1,  0.25, 100),
    (5.25,  A1,  0.25,  80),
    (5.5,   Gs3-12,0.25, 105), # G#2 — leading tone tension
    (5.75,  A1,  0.25,  90),
    (6.0,   Bb2, 0.25, 100),
    (6.25,  A1,  0.25,  85),
    (6.5,   A2,  0.25, 105),
    (6.75,  Bb2, 0.25,  95),
    (7.0,   A1,  0.25, 100),
    (7.25,  Gs3-12,0.25, 90),
    (7.5,   A1,  0.25,  90),
    (7.75,  A1,  0.25,  85),
]


def acid_tongue_pattern(s: int) -> list[dict]:
    if s not in (4, 7):
        return []
    notes: list[dict] = []
    # 4 reps of the 2-bar phrase = 8 bars
    for rep in range(4):
        base = rep * 8.0
        for (t, p, d, v) in ACID_2BAR:
            notes.append({"pitch": p, "start_time": base + t,
                          "duration": d, "velocity": v})
    return notes


# --- DRONE_CRYPT ---------------------------------------------------------
# Sustained dystopian pad bed: A1 + Bb1 phrygian stack (the half-step
# clash is the dread). Plays in the dark/quiet scenes — never alongside
# the peak chaos. Long held notes — 16+ beats each.
def drone_crypt_pattern(s: int) -> list[dict]:
    notes: list[dict] = []
    if s == 0:    # BLACKOUT — full-scene drone, A1 + Bb1 + A2 stack
        for p in (A1, A1 + 1, A2):  # A1, Bb1, A2 — phrygian half-step stack
            notes.append({"pitch": p, "start_time": 0.0,
                          "duration": 32.0, "velocity": 80 if p != A2 else 70})
    elif s == 5:  # BREAKDOWN_BLOOD — A1 + Bb2 throughout, F2 enters bar 5
        notes.append({"pitch": A1,  "start_time": 0.0,  "duration": 32.0, "velocity": 90})
        notes.append({"pitch": Bb2, "start_time": 0.0,  "duration": 32.0, "velocity": 80})
        notes.append({"pitch": F3,  "start_time": 16.0, "duration": 16.0, "velocity": 95})  # F3 — phrygian b6 push
    elif s == 6:  # REBUILD_HAMMER — sustained but builds intensity via overlapping notes
        # bars 0-3: just A1
        notes.append({"pitch": A1, "start_time": 0.0, "duration": 16.0, "velocity": 75})
        # bars 4-5: + Bb2
        notes.append({"pitch": Bb2, "start_time": 16.0, "duration": 8.0, "velocity": 85})
        # bars 6-7: + A2 (climbing the stack as the kicks accelerate)
        notes.append({"pitch": A2, "start_time": 24.0, "duration": 8.0, "velocity": 95})
    return notes


# --- REVERSE_VOID --------------------------------------------------------
# Reverse-suck swells before drops. Single long-decay notes played at the
# tail of build scenes — they should be heard as a "swooping inhalation"
# right before the kick hits the next scene. (Live can't natively reverse
# MIDI; this lane's Operator gets a reversed envelope shape so the note
# crescendos INTO its release rather than starting loud.)
def reverse_void_pattern(s: int) -> list[dict]:
    notes: list[dict] = []
    if s == 2:    # IRON_MARCH — swell across bars 7-8 leading into S3 HOOVER_DROP
        notes.append({"pitch": A3, "start_time": 24.0, "duration": 8.0, "velocity": 100})
        notes.append({"pitch": E4, "start_time": 28.0, "duration": 4.0, "velocity": 110})
    elif s == 6:  # REBUILD_HAMMER — swell across last 4 bars into NUCLEAR
        notes.append({"pitch": A3, "start_time": 16.0, "duration": 16.0, "velocity": 90})
        notes.append({"pitch": E4, "start_time": 24.0, "duration": 8.0, "velocity": 110})
        notes.append({"pitch": A4 if False else 69, "start_time": 28.0, "duration": 4.0, "velocity": 120})
    return notes


# --- CHOIR_NECRO ---------------------------------------------------------
# Demonic chant cluster — A minor with the phrygian Bb on top. Sustained
# 4-bar chord blocks. Plays at peaks for "ancient evil descending" vibe.
def choir_necro_pattern(s: int) -> list[dict]:
    """Demonic chant cluster. Transposed up one octave from the theory's
    base range — voice/choir presets (Dark Whispers etc.) sound in the
    C4-C6 register, sub-C4 territory is dead-zone for most choir patches.
    Cluster A3-C4-E4-Bb4 still preserves the A-root + phrygian-Bb-on-top
    dissonance the depravity needs."""
    notes: list[dict] = []
    # Cluster — transposed up an octave: A3, C4, E4, Bb4 (phrygian flat-2 top)
    CLUSTER = (A3, C4, E4, Bb4)  # MIDI 57, 60, 64, 70
    if s == 4:    # ANNIHILATION — 2× 4-bar holds, full cluster
        for base in (0.0, 16.0):
            for p in CLUSTER:
                notes.append({"pitch": p, "start_time": base,
                              "duration": 14.0, "velocity": 95})
    elif s == 5:  # BREAKDOWN_BLOOD — choir descends A→G→F→E across the void
        # 4 × 2-bar phrases — root descent, also transposed up
        descent_roots = [A3 + 12, G3 + 12, F3 + 12, E3 + 12]  # A4, G4, F4, E4
        for i, root in enumerate(descent_roots):
            base = i * 8.0
            # Triad: root + minor 3rd + 5th + b2 above (phrygian color)
            for offset in (0, 3, 7, 13):
                notes.append({"pitch": root + offset, "start_time": base,
                              "duration": 7.0, "velocity": 92})
    elif s == 7:  # NUCLEAR — full cluster throughout + Bb major reinforcement
        for base in (0.0, 16.0):
            for p in CLUSTER:
                notes.append({"pitch": p, "start_time": base,
                              "duration": 14.0, "velocity": 100})
        # Extra Bb-major triad layer at bar 5-6 — phrygian crash echo (octave up)
        for p in (Bb4, D4 + 12, F4 + 12):  # Bb4, D5, F5
            notes.append({"pitch": p, "start_time": 16.0,
                          "duration": 8.0, "velocity": 88})
    return notes


# --- SCREAM_BLEACH -------------------------------------------------------
# Distorted vocal screams doubling the hoover peaks an octave above.
# Plays the PEAK NOTES of the hoover riff only — sparse, punctuation-style.
# These are the chopped vocal-stand-in stabs (replace synth with actual
# vocal sample later).
def scream_bleach_pattern(s: int) -> list[dict]:
    notes: list[dict] = []
    if s not in (4, 7):
        return []
    # Peak notes from HOOVER_4BAR + 12 (octave up, "in the rafters")
    # bar 1 peak: E4 at t=2.0 -> E5 at t=2.0
    # bar 3 peak: F4 at t=10.0 -> F5 at t=10.0
    # Plus bar 4 final A2 -> A4 echo
    for rep_base in (0.0, 16.0):
        notes.append({"pitch": E4 + 12, "start_time": rep_base + 2.0,
                      "duration": 2.0, "velocity": 115})
        notes.append({"pitch": F4 + 12, "start_time": rep_base + 10.0,
                      "duration": 2.0, "velocity": 118})
        # Bar 4 echo — A4 short stab
        notes.append({"pitch": A3 + 12, "start_time": rep_base + 14.0,
                      "duration": 1.5, "velocity": 105})
    if s == 7:  # NUCLEAR — additional final-bar screams ramping up
        for i, p in enumerate([A3 + 12, Bb3 + 12, E4 + 12, F4 + 12]):
            notes.append({"pitch": p, "start_time": 28.0 + i * 1.0,
                          "duration": 0.8, "velocity": 110 + i * 4})
    return notes


# --- STAB_BWAAH ----------------------------------------------------------
# Terror-orchestral stab hits — the classic gabber "BWAAH" punctuation
# (think horror-film brass cluster). Single chord hits on key bars of
# drop scenes. Dissonant cluster: root + minor 2nd + minor 3rd + tritone.
def stab_bwaah_pattern(s: int) -> list[dict]:
    notes: list[dict] = []
    # Dissonant cluster around A: A2, Bb2, C3, Eb3 (root, b2, m3, tritone)
    CLUSTER = (A2, Bb2, C3, 51)  # 51 = Eb3
    if s == 3:    # HOOVER_DROP — hit on bar 1 + bar 5 (the "scene-defining" moments)
        for base in (0.0, 16.0):
            for p in CLUSTER:
                notes.append({"pitch": p, "start_time": base,
                              "duration": 1.5, "velocity": 115})
    elif s == 4:  # ANNIHILATION — hits on bar 1, 3, 5, 7 (every 2 bars)
        for bar in (0, 2, 4, 6):
            for p in CLUSTER:
                notes.append({"pitch": p, "start_time": float(bar*4),
                              "duration": 1.2, "velocity": 118})
    elif s == 7:  # NUCLEAR — hits on every bar 1 + 3 + final climax
        for bar in range(8):
            t = bar * 4
            for p in CLUSTER:
                notes.append({"pitch": p, "start_time": float(t),
                              "duration": 1.2, "velocity": 120 if bar % 2 == 0 else 105})
        # Final-bar BWAAH ramp: 4 hits 16th apart on last beat
        for i in range(4):
            for p in CLUSTER:
                notes.append({"pitch": p, "start_time": 31.0 + i * 0.25,
                              "duration": 0.2, "velocity": 110 + i * 4})
    return notes


# --- NOISE_OSSUARY -------------------------------------------------------
# White noise crescendo across build scenes. Single sustained note that
# swells via the Operator patch's filter sweep (loaded later). Plays
# only in build scenes — IRON_MARCH crescendo into HOOVER_DROP, and
# REBUILD_HAMMER crescendo into NUCLEAR.
def noise_ossuary_pattern(s: int) -> list[dict]:
    notes: list[dict] = []
    # Pitch is arbitrary for noise — pick C3 as a stable trigger note
    if s == 2:    # IRON_MARCH — single 32-beat swell
        notes.append({"pitch": C3, "start_time": 0.0,
                      "duration": 32.0, "velocity": 70})
        # Add a final-bar punch — louder
        notes.append({"pitch": C3, "start_time": 28.0,
                      "duration": 4.0, "velocity": 120})
    elif s == 6:  # REBUILD_HAMMER — staged swell that ramps to peak
        notes.append({"pitch": C3, "start_time": 0.0,
                      "duration": 16.0, "velocity": 75})
        notes.append({"pitch": C3, "start_time": 16.0,
                      "duration": 8.0, "velocity": 95})
        notes.append({"pitch": C3, "start_time": 24.0,
                      "duration": 8.0, "velocity": 120})
    return notes


# --- main ---------------------------------------------------------------
def _scan_all_track_names(ch: LiveChannel) -> dict[str, int]:
    """Single-pass: read every track's name in parallel, return name->idx map.
    Avoids the O(L*T) trap of looking up each lane by name with a full
    track scan each time."""
    info = ch.get_session_info().result(timeout=5)
    tc = info.get("track_count") or info.get("num_tracks") or 0
    futs = [ch.get_track_info(i) for i in range(tc)]
    out: dict[str, int] = {}
    for i, f in enumerate(futs):
        try:
            ti = f.result(timeout=5)
            nm = ti.get("name", "")
            if nm:
                out[nm] = i
        except Exception:
            pass
    return out


def find_track_by_name(ch: LiveChannel, name: str) -> int | None:
    """Kept for back-compat with one-off scripts. Inside this script the
    batched _scan_all_track_names is used instead."""
    return _scan_all_track_names(ch).get(name)


def apply_safe_gain_staging(ch: LiveChannel, name_to_idx: dict[str, int]) -> None:
    """Walk every track in our lane set, find any Saturator / Drum Buss,
    and set its drive/output/threshold to safe defaults. Idempotent —
    re-runs converge on the same values. Without this, repeated runs of
    the gain-stacking script (or stray UI nudges) eventually push the
    chain into clipping again."""
    rpcs = 0
    for name, t in name_to_idx.items():
        try:
            ti = ch.get_track_info(t).result(timeout=3)
        except Exception:
            continue
        for di, d in enumerate(ti.get("devices") or []):
            dn = d.get("name") or ""
            if dn == "Saturator":
                for pname, pval in SAFE_SATURATOR.items():
                    try:
                        ch.set_device_param(t, di, pname, pval).result(timeout=5)
                        rpcs += 1
                    except Exception:
                        pass
            elif dn == "Drum Buss":
                for pname, pval in SAFE_DRUM_BUSS.items():
                    try:
                        ch.set_device_param(t, di, pname, pval).result(timeout=5)
                        rpcs += 1
                    except Exception:
                        pass
    print(f"  applied safe gain staging via {rpcs} param RPCs")


def ensure_lanes(ch: LiveChannel) -> list[int]:
    """Create any missing lanes (by name). Returns ordered list of indices.
    Single-pass scan + only create what's missing."""
    name_map = _scan_all_track_names(ch)
    indices: list[int] = []
    for name, color in zip(LANE_NAMES, LANE_COLORS):
        t = name_map.get(name)
        if t is None:
            # Create at end; re-scan to find the new track's index
            ch.create_midi_track(-1).result(timeout=10)
            name_map = _scan_all_track_names(ch)
            # New track will have a default name like "N-MIDI" — pick the
            # highest-index MIDI track that isn't already mapped to a lane
            mapped = set(name_map.values()) & set(indices)
            info = ch.get_session_info().result(timeout=5)
            new_idx = (info.get("track_count") or 0) - 1
            t = new_idx
            ch.set_track_name(t, name).result(timeout=5)
            ch.set_track_color(t, color).result(timeout=5)
            name_map[name] = t  # update local cache
            print(f"  created T{t} '{name}' (color {color})")
        else:
            print(f"  reused T{t} '{name}'")
        indices.append(t)
    return indices


def ensure_scenes(ch: LiveChannel, n: int) -> None:
    # Use dedicated RPC — get_session_info doesn't surface scene_count.
    try:
        resp = ch._enqueue("get_scene_count", {}).result(timeout=5)
        have = int(resp.get("count", 0))
    except Exception:
        have = 0
    print(f"  current scenes: {have}, target: {n}")
    while have < n:
        ch.create_scene(-1).result(timeout=5)
        have += 1
        print(f"  created scene {have - 1}")


PATTERN_FNS = {
    "KICK_ROTTERDAM":  kick_pattern,
    "PERC_INDUSTRIAL": perc_pattern,
    "SUB_PUNCH":       sub_pattern,
    "HOOVER_LEAD":     hoover_pattern,
    "STAB_HARDCORE":   stab_pattern,
    "SIREN_FX":        siren_pattern,
    "VOX_SHOUT":       vox_pattern,
    # depraved layer
    "KICK_VEIN":       kick_vein_pattern,
    "ACID_TONGUE":     acid_tongue_pattern,
    "DRONE_CRYPT":     drone_crypt_pattern,
    "REVERSE_VOID":    reverse_void_pattern,
    "CHOIR_NECRO":     choir_necro_pattern,
    "SCREAM_BLEACH":   scream_bleach_pattern,
    "STAB_BWAAH":      stab_bwaah_pattern,
    "NOISE_OSSUARY":   noise_ossuary_pattern,
}

# Suggested per-track volumes. Gabber mixing keeps the kick highest, but
# every stage's INPUT must stay below clip (see [[feedback-audio-gain-staging]]).
# Factory presets are mastered hot already — track fader sits well below
# unity so the Saturator/Drum Buss after them doesn't push into clipping.
# 0.85 ≈ 0 dB; these all sit at -2 to -8 dB.
TRACK_VOLUMES = {
    "KICK_ROTTERDAM":  0.88,
    "PERC_INDUSTRIAL": 0.72,
    "SUB_PUNCH":       0.85,   # bass needs presence — keep this hot
    "HOOVER_LEAD":     0.72,
    "STAB_HARDCORE":   0.70,
    "SIREN_FX":        0.65,
    "VOX_SHOUT":       0.72,
    # depraved layer
    "KICK_VEIN":       0.85,
    "ACID_TONGUE":     0.75,
    "DRONE_CRYPT":     0.70,
    "REVERSE_VOID":    0.75,
    "CHOIR_NECRO":     0.75,
    "SCREAM_BLEACH":   0.75,
    "STAB_BWAAH":      0.78,
    "NOISE_OSSUARY":   0.68,
}

# Safe defaults for distortion stages — calibrated for gabber crunch
# without losing bass body. Earlier (Output 0.70, Threshold 0.05) was
# too conservative — gutted the low end. Drive 0.60 still pushes the
# saturator into character, Output 0.85 keeps body, Threshold back to
# default 0.0 lets the bass fundamentals through clean.
SAFE_SATURATOR = {"Drive": 0.60, "Output": 0.85, "Threshold": 0.0}
SAFE_DRUM_BUSS = {"Drive": 0.18, "Output": 0.85}


# Factory preset paths per depraved lane — these REPLACE the default
# Operator-sine setup (which is dead quiet at low transposes). Existing
# FX chains (Saturator / Drum Buss / Auto Filter / Reverb) are preserved.
DEPRAVED_PRESETS = {
    "KICK_VEIN":     ("sounds/Bass",       "808 Pure.adg"),
    "ACID_TONGUE":   ("sounds/Bass",       "Acid Bass.adv"),
    "DRONE_CRYPT":   ("sounds/Pad",        "Atmos Pad.adv"),
    "REVERSE_VOID":  ("sounds/Effects",    "Air Raid Riser.adg"),
    "CHOIR_NECRO":   ("sounds/Voices",     "Dark Whispers.adg"),
    "SCREAM_BLEACH": ("sounds/Synth Lead", "Anger Management.adv"),
    "STAB_BWAAH":    ("sounds/Brass",      "Abrasive Brass.adg"),
    "NOISE_OSSUARY": ("sounds/Effects",    "Broadcast Noise.adg"),
}


def main():
    import argparse, time
    ap = argparse.ArgumentParser(
        description="ROTTERDAM_CHAIN build script. Re-run is idempotent. "
                    "Filter by --lanes / --scenes to iterate on subsets fast.")
    ap.add_argument("--lanes", nargs="+", default=None,
                    help="Only update these lane names (e.g. CHOIR_NECRO SCREAM_BLEACH). "
                         "Default: all lanes.")
    ap.add_argument("--scenes", nargs="+", type=int, default=None,
                    help="Only update these scene indices (0-15). Default: all 16.")
    ap.add_argument("--skip-tempo", action="store_true",
                    help="Skip the scene tempo/name/color bake (saves 48 RPCs).")
    ap.add_argument("--skip-volumes", action="store_true",
                    help="Skip setting track volumes.")
    args = ap.parse_args()

    only_lanes = set(args.lanes) if args.lanes else None
    only_scenes = set(args.scenes) if args.scenes else None
    if only_lanes:
        invalid = only_lanes - set(LANE_NAMES)
        if invalid:
            print(f"ERROR: unknown lane name(s): {invalid}")
            print(f"  available: {LANE_NAMES}")
            return

    ch = LiveChannel(enabled=True)
    ch.start()
    try:
        t_start = time.monotonic()
        print("\n--- ROTTERDAM_CHAIN build ---")
        if only_lanes:
            print(f"  FILTER lanes: {sorted(only_lanes)}")
        if only_scenes:
            print(f"  FILTER scenes: {sorted(only_scenes)}")

        info = ch.get_session_info().result(timeout=5)
        print(f"start track count: {info.get('track_count') or info.get('num_tracks')}")

        # 1. Lanes — always reconcile (creates missing, cheap if already there)
        print("\n[1] ensuring lanes")
        lane_idx = ensure_lanes(ch)
        name_to_idx = dict(zip(LANE_NAMES, lane_idx))

        # 2. Scenes
        if not args.skip_tempo and not only_lanes and not only_scenes:
            print("\n[2] ensuring scenes")
            ensure_scenes(ch, N_SCENES)

            # 3. Per-scene tempo bake + names + colors — submit in batch
            print(f"\n[3] baking {BPM} BPM, names, colors into all {N_SCENES} scenes")
            futs = []
            for s in range(N_SCENES):
                futs.append(ch.set_scene_tempo(s, BPM))
                futs.append(ch.set_scene_name(s, SCENE_NAMES[s]))
                futs.append(ch.set_scene_color(s, SCENE_COLORS[s]))
            for f in futs:
                try: f.result(timeout=10)
                except Exception as e: print(f"  scene-meta RPC failed: {e}")
        else:
            print("\n[2-3] SKIPPED (filtered run)")

        # 4. Wipe + write clips per scene per lane.
        #
        # S0-S7 (base):     only CORE_LANES fire (original 7).
        # S8-S15 (depraved): CORE_LANES + DEPRAVED_LANES fire (all 15).
        #
        # Pipelining strategy: enqueue all RPCs for a (scene,lane) without
        # awaiting individually, then await per-lane. The bridge dispatcher
        # is strictly serial (one send-recv per command on the same TCP
        # socket), so we can't go FASTER than N × round-trip — but we can
        # avoid Python-side blocking between calls. The biggest win is
        # SKIPPING lanes/scenes when --lanes / --scenes filter is used.
        print("\n[4] writing clips (S0-S7 base, S8-S15 depraved)")
        total_rpcs = 0
        for s in range(N_SCENES):
            if only_scenes and s not in only_scenes:
                continue
            pattern_idx = s % N_BASE_SCENES
            is_depraved_band = s >= N_BASE_SCENES
            print(f"\n  S{s} {SCENE_NAMES[s]} (pattern_idx={pattern_idx})")
            scene_futs = []
            for name in LANE_NAMES:
                if only_lanes and name not in only_lanes:
                    continue
                t = name_to_idx[name]
                is_core = name in CORE_LANES
                fires = True if is_core else is_depraved_band
                # Submit the clear (no await — failures are silent regardless)
                scene_futs.append(("clear", name, ch.clear_clip(t, s)))
                if not fires:
                    continue
                # Submit create + meta + notes without awaiting yet
                scene_futs.append(("create", name,
                                   ch.create_clip(t, s, SCENE_LEN)))
                scene_futs.append(("name", name,
                                   ch.set_clip_name(t, s, f"{SCENE_NAMES[s]}_{name.lower()}")))
                scene_futs.append(("color", name,
                                   ch.set_clip_color(t, s, SCENE_COLORS[s])))
                notes = PATTERN_FNS[name](pattern_idx)
                if notes:
                    scene_futs.append(("notes", name,
                                       ch.add_notes_to_clip(t, s, notes)))
                print(f"    T{t:2d} {name:17s}: {len(notes):3d} notes queued")
            # Await this scene's futures so we can report failures and don't
            # let the queue grow unbounded
            for tag, name, f in scene_futs:
                try:
                    f.result(timeout=15)
                    total_rpcs += 1
                except Exception as e:
                    if tag != "clear" and tag != "color":  # these can fail silently
                        print(f"    RPC failed [{tag} {name} S{s}]: {e}")

        # 5a. Safe gain staging on distortion stages (only on full runs)
        if not only_lanes and not only_scenes and not args.skip_volumes:
            print("\n[5a] applying safe gain staging (Saturator/Drum Buss)")
            apply_safe_gain_staging(ch, name_to_idx)

        # 5. Volumes
        if not args.skip_volumes:
            print("\n[5] setting track volumes")
            vfuts = []
            for name, v in TRACK_VOLUMES.items():
                if only_lanes and name not in only_lanes:
                    continue
                t = name_to_idx[name]
                vfuts.append((name, t, v, ch.set_track_volume(t, v)))
            for name, t, v, f in vfuts:
                try:
                    f.result(timeout=5)
                    print(f"  T{t} {name}: {v}")
                except Exception as e:
                    print(f"  T{t} {name}: vol set failed: {e}")
        else:
            print("\n[5] SKIPPED (--skip-volumes)")

        elapsed = time.monotonic() - t_start
        print(f"\nfired {total_rpcs} clip RPCs in {elapsed:.1f} s ({total_rpcs/max(elapsed, 0.01):.0f} rpc/s)")

        # 6. Summary
        print("\n--- FINAL TRACK LIST ---")
        info_f = ch.get_session_info().result(timeout=5)
        for i in range(info_f.get("track_count") or 0):
            ti = ch.get_track_info(i).result(timeout=3)
            print(f"  T{i:2d}  {ti.get('name','')!r}")
        print(f"\nDONE — ROTTERDAM_CHAIN, 7 lanes × {N_SCENES} scenes at {BPM} BPM in Am.")
        print("Next: drop a bare DrumGroupDevice (Selectah Kit) on T0+T1, hot-swap pads")
        print("      to a distorted gabber kick (T0/36) + industrial perc (T1/39/42/46/47).")
        print("      Drop Operator on T2-T6 with appropriate patches (sub sine / hoover saw /")
        print("      supersaw / siren-LFO / shout-blip). Then EQ + print.")
    finally:
        ch.stop()


if __name__ == "__main__":
    main()
