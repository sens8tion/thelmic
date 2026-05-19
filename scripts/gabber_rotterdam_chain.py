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
N_SCENES   = 8

LANE_NAMES = [
    "KICK_ROTTERDAM",
    "PERC_INDUSTRIAL",
    "SUB_PUNCH",
    "HOOVER_LEAD",
    "STAB_HARDCORE",
    "SIREN_FX",
    "VOX_SHOUT",
]
LANE_COLORS = [3, 13, 1, 14, 5, 7, 10]  # vary so the session view is readable

SCENE_NAMES = [
    "BLACKOUT",
    "KICK_ENTRY",
    "IRON_MARCH",
    "HOOVER_DROP",
    "ANNIHILATION",
    "BREAKDOWN_BLOOD",
    "REBUILD_HAMMER",
    "NUCLEAR",
]
# Scene colors: dark/blue intro -> orange -> red peak -> black breakdown ->
# orange rebuild -> magenta nuclear. Live's palette indices are 0-69.
SCENE_COLORS = [
    20,  # BLACKOUT          — dark navy
    14,  # KICK_ENTRY        — desaturated red
     6,  # IRON_MARCH        — orange
     3,  # HOOVER_DROP       — bright red
     1,  # ANNIHILATION      — neon red
    20,  # BREAKDOWN_BLOOD   — dark navy (return-to-void)
     6,  # REBUILD_HAMMER    — orange
     2,  # NUCLEAR           — hot magenta
]

# Drum pads (Selectah Kit GM mapping)
KICK   = 36
SNARE  = 38   # snare drum — stacked with clap on 2/4 for the classic gabber thump
CLAP   = 39
METAL  = 47
HATC   = 42
HATO   = 46

# Am pitches — root octave centred at A2=45
A1, E2, A2, B2, C3, D3, E3, F3, G3, A3, B3, C4, D4, E4, F4, G4 = (
    33, 40, 45, 47, 48, 50, 52, 53, 55, 57, 59, 60, 62, 64, 65, 67
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
    # bar 1 — CALL
    (0.0,  A3, 1.5,  108),
    (1.5,  A3, 0.5,   95),
    (2.0,  E4, 2.0,  115),
    # bar 2 — ANSWER
    (4.0,  A3, 1.0,  100),
    (5.0,  B3, 0.5,   95),
    (5.5,  A3, 0.5,   95),
    (6.0,  G3, 2.0,  108),
    # bar 3 — PUSH
    (8.0,  A3, 1.5,  110),
    (9.5,  A3, 0.5,   95),
    (10.0, F4, 2.0,  118),
    # bar 4 — DESCENT
    (12.0, G3, 0.5,  100),
    (12.5, F3, 0.5,  100),
    (13.0, E3, 0.5,  100),
    (13.5, D3, 0.5,  100),
    (14.0, A2, 2.0,  105),
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
    pads on bar 1 + 3 of each bar to fill harmonic body."""
    notes: list[dict] = []
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


# --- main ---------------------------------------------------------------
def find_track_by_name(ch: LiveChannel, name: str) -> int | None:
    info = ch.get_session_info().result(timeout=5)
    tc = info.get("track_count") or info.get("num_tracks") or 0
    for i in range(tc):
        ti = ch.get_track_info(i).result(timeout=3)
        if ti.get("name", "") == name:
            return i
    return None


def ensure_lanes(ch: LiveChannel) -> list[int]:
    """Create any missing lanes (by name). Return ordered list of indices."""
    indices: list[int] = []
    for name, color in zip(LANE_NAMES, LANE_COLORS):
        t = find_track_by_name(ch, name)
        if t is None:
            ch.create_midi_track(-1).result(timeout=10)
            t = find_track_by_name(ch, name)
            if t is None:
                # New track lands at the end — find it
                info = ch.get_session_info().result(timeout=5)
                t = (info.get("track_count") or info.get("num_tracks")) - 1
            ch.set_track_name(t, name).result(timeout=5)
            ch.set_track_color(t, color).result(timeout=5)
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
}

# Suggested per-track volumes (gabber mixing keeps kick HOT, everything else
# below it). 0.85 ≈ 0 dB on Live's fader.
TRACK_VOLUMES = {
    "KICK_ROTTERDAM":  0.90,
    "PERC_INDUSTRIAL": 0.72,
    "SUB_PUNCH":       0.78,
    "HOOVER_LEAD":     0.74,
    "STAB_HARDCORE":   0.70,
    "SIREN_FX":        0.65,
    "VOX_SHOUT":       0.72,
}


def main():
    ch = LiveChannel(enabled=True)
    ch.start()
    try:
        print("\n--- ROTTERDAM_CHAIN build ---")
        info = ch.get_session_info().result(timeout=5)
        print(f"start track count: {info.get('track_count') or info.get('num_tracks')}")

        # 1. Lanes
        print("\n[1] ensuring lanes")
        lane_idx = ensure_lanes(ch)
        name_to_idx = dict(zip(LANE_NAMES, lane_idx))

        # 2. Scenes
        print("\n[2] ensuring scenes")
        ensure_scenes(ch, N_SCENES)

        # 3. Per-scene tempo bake + names + colors
        print(f"\n[3] baking {BPM} BPM, names, colors into all {N_SCENES} scenes")
        for s in range(N_SCENES):
            ch.set_scene_tempo(s, BPM).result(timeout=5)
            ch.set_scene_name(s, SCENE_NAMES[s]).result(timeout=5)
            ch.set_scene_color(s, SCENE_COLORS[s]).result(timeout=5)
            print(f"  S{s} -> name={SCENE_NAMES[s]!r} color={SCENE_COLORS[s]}")

        # 4. Wipe + write clips per scene per lane
        print("\n[4] writing clips")
        for s in range(N_SCENES):
            print(f"\n  S{s} {SCENE_NAMES[s]}")
            for name in LANE_NAMES:
                t = name_to_idx[name]
                # Wipe any existing clip first
                try:
                    ch.delete_clip(t, s).result(timeout=5)
                except Exception:
                    pass
                ch.create_clip(t, s, SCENE_LEN).result(timeout=10)
                ch.set_clip_name(t, s, f"{SCENE_NAMES[s]}_{name.lower()}").result(timeout=5)
                # Color the clip to match the scene's dramaturgy
                try:
                    ch.set_clip_color(t, s, SCENE_COLORS[s]).result(timeout=3)
                except Exception:
                    pass
                notes = PATTERN_FNS[name](s)
                if notes:
                    ch.add_notes_to_clip(t, s, notes).result(timeout=10)
                print(f"    T{t:2d} {name:17s}: {len(notes):3d} notes")

        # 5. Volumes
        print("\n[5] setting track volumes")
        for name, v in TRACK_VOLUMES.items():
            t = name_to_idx[name]
            ch.set_track_volume(t, v).result(timeout=5)
            print(f"  T{t} {name}: {v}")

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
