"""Per-(scene, channel) clip recipes for the 8x4 jungle layout.

Scene index = slot index:
  0 = BUILD, 1 = DROP, 2 = BREAK, 3 = DROP2

For audio/sampler channels: an "audio" entry means duplicate the loaded
sample (slot 0) into this scene slot.

For drum_rack/synth channels: a pattern function returns a list of notes
(pitch, time, duration, velocity) for the clip.
"""
from __future__ import annotations

# MIDI pitches for jungle in E natural minor (root E2 = 40)
ROOT = 40
E_MINOR = [40, 42, 43, 45, 47, 48, 50]   # E F# G A B C D — E natural minor

# Drum-rack pad notes (matches our PAD bindings)
KICK   = 36
SNARE  = 38
HAT_C  = 42
HAT_O  = 46
CRASH  = 49


# ---- drum patterns (4-bar = 16 beats) ----------------------------------

def drums_build() -> list[dict]:
    """Sparse hat tension — closed hats on 8ths, no kick."""
    notes = []
    for i in range(32):  # 8th notes across 4 bars
        notes.append({"pitch": HAT_C, "time": i * 0.5, "duration": 0.25, "velocity": 60 + (i % 4) * 8})
    notes.append({"pitch": CRASH, "time": 15.0, "duration": 1.0, "velocity": 100})
    return notes


def drums_drop() -> list[dict]:
    """Full ragga jungle — kick on 1, snare on 2/4, syncopated extras, hats."""
    notes = []
    # 4 bars
    for bar in range(4):
        b0 = bar * 4
        notes.append({"pitch": KICK, "time": b0 + 0.0, "duration": 0.25, "velocity": 115})
        notes.append({"pitch": KICK, "time": b0 + 2.5, "duration": 0.25, "velocity": 100})
        notes.append({"pitch": SNARE, "time": b0 + 1.0, "duration": 0.25, "velocity": 110})
        notes.append({"pitch": SNARE, "time": b0 + 3.0, "duration": 0.25, "velocity": 110})
        # 16th hats
        for s in range(16):
            notes.append({"pitch": HAT_C, "time": b0 + s * 0.25, "duration": 0.125,
                          "velocity": 70 if s % 2 == 0 else 55})
        notes.append({"pitch": HAT_O, "time": b0 + 3.5, "duration": 0.5, "velocity": 90})
    return notes


def drums_break() -> list[dict]:
    """Thinned — snare-led syncopation, less kick, sparse."""
    notes = []
    for bar in range(4):
        b0 = bar * 4
        notes.append({"pitch": KICK, "time": b0 + 0.0, "duration": 0.25, "velocity": 100})
        notes.append({"pitch": SNARE, "time": b0 + 0.75, "duration": 0.25, "velocity": 95})
        notes.append({"pitch": SNARE, "time": b0 + 1.5, "duration": 0.25, "velocity": 105})
        notes.append({"pitch": SNARE, "time": b0 + 2.25, "duration": 0.25, "velocity": 90})
        notes.append({"pitch": SNARE, "time": b0 + 3.5, "duration": 0.25, "velocity": 100})
        # very sparse hats
        for s in (0.0, 1.0, 2.0, 3.0):
            notes.append({"pitch": HAT_C, "time": b0 + s, "duration": 0.125, "velocity": 50})
    return notes


def drums_drop2() -> list[dict]:
    """Gabber/Rotterdam — 4-on-the-floor distorted kicks, double-time hats."""
    notes = []
    for bar in range(4):
        b0 = bar * 4
        for beat in range(4):
            notes.append({"pitch": KICK, "time": b0 + beat * 1.0, "duration": 0.5, "velocity": 120})
        notes.append({"pitch": SNARE, "time": b0 + 1.0, "duration": 0.25, "velocity": 110})
        notes.append({"pitch": SNARE, "time": b0 + 3.0, "duration": 0.25, "velocity": 110})
        for s in range(32):  # 32nd note hats
            notes.append({"pitch": HAT_C, "time": b0 + s * 0.125, "duration": 0.0625,
                          "velocity": 65 if s % 2 == 0 else 50})
    return notes


# ---- bass patterns -----------------------------------------------------

def bass_drop() -> list[dict]:
    """Reese-style — sustained low E with rhythm pulses."""
    notes = []
    for bar in range(4):
        b0 = bar * 4
        notes.append({"pitch": ROOT, "time": b0 + 0.0,  "duration": 1.5, "velocity": 110})
        notes.append({"pitch": ROOT, "time": b0 + 2.0,  "duration": 0.75,"velocity": 105})
        notes.append({"pitch": ROOT, "time": b0 + 3.0,  "duration": 0.5, "velocity": 100})
    return notes


def bass_drop2() -> list[dict]:
    """Gabber bass — straight 8ths on root, distorted feel."""
    notes = []
    for bar in range(4):
        b0 = bar * 4
        for s in range(8):
            notes.append({"pitch": ROOT, "time": b0 + s * 0.5, "duration": 0.4, "velocity": 115})
    return notes


# ---- stab patterns -----------------------------------------------------

def stab_drop() -> list[dict]:
    """Em chord stabs on the off-beats."""
    chord = [E_MINOR[0] + 12, E_MINOR[2] + 12, E_MINOR[4] + 12]  # E G B
    notes = []
    for bar in range(4):
        b0 = bar * 4
        for offset in (1.5, 2.5, 3.75):
            for p in chord:
                notes.append({"pitch": p, "time": b0 + offset, "duration": 0.25, "velocity": 95})
    return notes


# ---- vox patterns (Simpler triggered at C3 = 60) -----------------------

VOX_TRIGGER = 60

def vox_call() -> list[dict]:
    """Sample triggered on the 1 and 3 of each bar."""
    notes = []
    for bar in range(4):
        b0 = bar * 4
        notes.append({"pitch": VOX_TRIGGER, "time": b0 + 0.0, "duration": 0.5, "velocity": 110})
        if bar % 2 == 1:
            notes.append({"pitch": VOX_TRIGGER, "time": b0 + 2.0, "duration": 0.5, "velocity": 105})
    return notes


def vox_chant() -> list[dict]:
    """Repeated trigger every beat — drop2 chant feel."""
    notes = []
    for bar in range(4):
        b0 = bar * 4
        for beat in (0.0, 1.0, 2.0, 3.0):
            notes.append({"pitch": VOX_TRIGGER, "time": b0 + beat, "duration": 0.5, "velocity": 108})
    return notes


# ---- participation matrix ---------------------------------------------
#
# For each scene archetype, what each channel does.
# - "audio"      : duplicate the loaded slot-0 sample into this scene slot
# - callable     : MIDI pattern function (returns notes)
# - omitted/None : channel is silent in this scene

CLIP_LENGTH_BEATS = 16.0   # 4 bars per scene clip

SCENE_PLAN: dict[str, dict[str, object]] = {
    "BUILD": {
        "drums": drums_build,
        "pad":   "audio",
        "vox":   vox_call,
        "fx":    "audio",
    },
    "DROP": {
        "drums": drums_drop,
        "sub":   "audio",
        "bass":  bass_drop,
        "stab":  stab_drop,
        "pad":   "audio",
        "vox":   vox_call,
        "fx":    "audio",
    },
    "BREAK": {
        "drums": drums_break,
        "break": "audio",
        "pad":   "audio",
        "vox":   vox_call,
    },
    "DROP2": {
        "drums": drums_drop2,
        "sub":   "audio",
        "bass":  bass_drop2,
        "vox":   vox_chant,
    },
}
