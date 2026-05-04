"""Ragga-style 8×4 arrangement — parallel to compose_8x4 (the jungle default).

Same channel set (drums, break, sub, bass, stab, pad, vox, fx), different
scene archetypes and patterns. Channel roles map slightly differently:
  - 'stab'  carries the off-beat ragga organ skank (MIDI chords, not stabs)
  - 'bass'  walks root/fifth/octave reggae-style instead of reese sustains
  - 'break' carries the chopped amen audio in the jungle-ragga scene
  - 'vox'   is the toaster — call on 1, response on 3, chant in dubout

Scenes:
  DUB_IN       sparse, atmospheric, no drums; vox call, fx echoes, sub holds, skank teases
  STEPPER      half-time roots-rock — kick 1+3, snare 3, organ skanks every off-beat,
               walking bass, vox toast
  RAGGAJUNGLE  full slam — chopped amen (audio break), busy drums, sub bonks,
               organ skanks, walking bass, vox toast, stab bursts
  DUBOUT       drums drop, fx swirls, vocal echo, sub holds, pad blooms; let the
               sound system breathe
"""
from __future__ import annotations

from thelmic.meta.layout import MetaLayout, ChannelSpec, SceneSpec, ChannelKind


# E natural minor (jungle root); ragga keeps the root pivot
ROOT       = 40        # E2
FIFTH      = ROOT + 7  # B2
OCT_UP     = ROOT + 12
ORGAN_ROOT = ROOT + 24 # E4 — organ chord voicing octave

# Em chord up an octave for skank stabs (E G B)
EM_CHORD = (ORGAN_ROOT + 0, ORGAN_ROOT + 3, ORGAN_ROOT + 7)
# A-minor passing chord for movement
AM_CHORD = (ORGAN_ROOT + 5, ORGAN_ROOT + 8, ORGAN_ROOT + 12)

# Drum-rack pad notes
KICK   = 36
SNARE  = 38
HAT_C  = 42
HAT_O  = 46
CRASH  = 49

VOX_TRIGGER = 60   # C3 — Simpler trigger note

CLIP_LENGTH_BEATS = 16.0   # 4 bars


# ---- drum patterns ----------------------------------------------------

def drums_dub_in() -> list[dict]:
    """No drums proper — just a slow rim-tap on 3 of bar 4 to signal arrival."""
    return [
        {"pitch": HAT_C, "time": 14.0, "duration": 0.25, "velocity": 50},
        {"pitch": HAT_C, "time": 15.0, "duration": 0.25, "velocity": 70},
        {"pitch": CRASH, "time": 15.5, "duration": 0.5,  "velocity": 95},
    ]


def drums_stepper() -> list[dict]:
    """Half-time roots-rock — KICK on 1+3, SNARE on 3, hats off-beat."""
    notes = []
    for bar in range(4):
        b0 = bar * 4
        notes.append({"pitch": KICK,  "time": b0 + 0.0, "duration": 0.4, "velocity": 115})
        notes.append({"pitch": KICK,  "time": b0 + 2.0, "duration": 0.4, "velocity": 110})
        notes.append({"pitch": SNARE, "time": b0 + 2.0, "duration": 0.25,"velocity": 108})
        # ragga off-beat hat skip — closed hats on the &'s
        for off in (0.5, 1.5, 2.5, 3.5):
            notes.append({"pitch": HAT_C, "time": b0 + off, "duration": 0.125,
                          "velocity": 70 + (12 if off in (1.5, 3.5) else 0)})
        # open hat on 4& for that classic skank breath
        notes.append({"pitch": HAT_O, "time": b0 + 3.5, "duration": 0.5, "velocity": 85})
    return notes


def drums_raggajungle() -> list[dict]:
    """Chopped amen feel — busy syncopated kick/snare, ghost notes, 16th hats."""
    notes = []
    for bar in range(4):
        b0 = bar * 4
        # Off-grid kicks (amen style) — varies per bar
        kick_times = (0.0, 2.5, 3.5) if bar % 2 == 0 else (0.0, 1.75, 2.5)
        for t in kick_times:
            notes.append({"pitch": KICK, "time": b0 + t, "duration": 0.25, "velocity": 113})
        # Snares with ghost
        notes.append({"pitch": SNARE, "time": b0 + 1.0,  "duration": 0.25, "velocity": 112})
        notes.append({"pitch": SNARE, "time": b0 + 1.75, "duration": 0.125,"velocity": 65})  # ghost
        notes.append({"pitch": SNARE, "time": b0 + 3.0,  "duration": 0.25, "velocity": 110})
        notes.append({"pitch": SNARE, "time": b0 + 3.5,  "duration": 0.125,"velocity": 70})  # ghost
        # 16th hat carpet
        for s in range(16):
            notes.append({"pitch": HAT_C, "time": b0 + s * 0.25, "duration": 0.125,
                          "velocity": 72 if s % 2 == 0 else 55})
        # Open hat splash
        notes.append({"pitch": HAT_O, "time": b0 + 2.75, "duration": 0.375, "velocity": 88})
    notes.append({"pitch": CRASH, "time": 0.0, "duration": 1.0, "velocity": 105})
    return notes


def drums_dubout() -> list[dict]:
    """Drums drop almost entirely — single splash and a soft kick on bar 1, then space."""
    return [
        {"pitch": CRASH, "time": 0.0,  "duration": 1.5, "velocity": 100},
        {"pitch": KICK,  "time": 0.0,  "duration": 0.5, "velocity": 95},
        {"pitch": HAT_O, "time": 8.0,  "duration": 0.5, "velocity": 60},
        {"pitch": SNARE, "time": 14.0, "duration": 0.25,"velocity": 70},  # delay echo trail entry
    ]


# ---- bass patterns (walking reggae line) ------------------------------

def bass_stepper() -> list[dict]:
    """Roots-rock walking bass — root on 1, fifth on 3, octave drop on 4&."""
    notes = []
    for bar in range(4):
        b0 = bar * 4
        notes.append({"pitch": ROOT,   "time": b0 + 0.0, "duration": 1.5, "velocity": 110})
        notes.append({"pitch": FIFTH,  "time": b0 + 2.0, "duration": 1.0, "velocity": 105})
        # bar-end pickup
        if bar < 3:
            notes.append({"pitch": ROOT - 2, "time": b0 + 3.5, "duration": 0.5, "velocity": 95})
    return notes


def bass_raggajungle() -> list[dict]:
    """Busier walking line — root, octave, fifth — leaving holes for kick."""
    notes = []
    for bar in range(4):
        b0 = bar * 4
        notes.append({"pitch": ROOT,   "time": b0 + 0.0, "duration": 0.75, "velocity": 112})
        notes.append({"pitch": OCT_UP, "time": b0 + 0.75,"duration": 0.25, "velocity": 100})
        notes.append({"pitch": FIFTH,  "time": b0 + 1.5, "duration": 0.5,  "velocity": 105})
        notes.append({"pitch": ROOT,   "time": b0 + 2.5, "duration": 0.5,  "velocity": 108})
        notes.append({"pitch": ROOT - 2, "time": b0 + 3.25, "duration": 0.25, "velocity": 95})  # passing tone
    return notes


# ---- ragga organ skank (on the 'stab' channel) ------------------------

def organ_skank_stepper() -> list[dict]:
    """Classic ragga skank — chord stab on every off-beat (the &'s)."""
    notes = []
    for bar in range(4):
        b0 = bar * 4
        # 2.5 (the & of 2) is the strongest skank in stepper feel
        for off in (0.5, 1.5, 2.5, 3.5):
            chord = EM_CHORD if (bar + int(off)) % 4 != 3 else AM_CHORD  # tiny chord movement
            for p in chord:
                notes.append({"pitch": p, "time": b0 + off, "duration": 0.25,
                              "velocity": 90 if off in (1.5, 3.5) else 75})
    return notes


def organ_skank_full() -> list[dict]:
    """Skank + extra accents on the strongest off-beats and bar-ends."""
    notes = []
    for bar in range(4):
        b0 = bar * 4
        for off in (0.5, 1.5, 2.5, 3.5):
            chord = EM_CHORD if bar % 2 == 0 else AM_CHORD
            for p in chord:
                notes.append({"pitch": p, "time": b0 + off, "duration": 0.2,
                              "velocity": 95 if off in (1.5, 3.5) else 80})
        # extra 16th flick on bar-end for momentum
        for p in EM_CHORD:
            notes.append({"pitch": p, "time": b0 + 3.875, "duration": 0.125, "velocity": 88})
    return notes


def organ_skank_tease() -> list[dict]:
    """Sparse — one tease skank per bar to set up the genre signal."""
    notes = []
    for bar in range(4):
        b0 = bar * 4
        for p in EM_CHORD:
            notes.append({"pitch": p, "time": b0 + 1.5, "duration": 0.25, "velocity": 70})
        if bar == 3:  # closing skank lands harder
            for p in EM_CHORD:
                notes.append({"pitch": p, "time": b0 + 3.5, "duration": 0.25, "velocity": 95})
    return notes


# ---- vox patterns -----------------------------------------------------

def vox_call_in() -> list[dict]:
    """Sparse call — just bar 1 and bar 4 of the intro."""
    return [
        {"pitch": VOX_TRIGGER, "time": 0.0,  "duration": 0.5, "velocity": 105},
        {"pitch": VOX_TRIGGER, "time": 12.0, "duration": 0.5, "velocity": 100},
    ]


def vox_toast_stepper() -> list[dict]:
    """Toaster phrasing — call on 1, response on 3 of every other bar."""
    notes = []
    for bar in range(4):
        b0 = bar * 4
        notes.append({"pitch": VOX_TRIGGER, "time": b0 + 0.0, "duration": 0.5, "velocity": 108})
        if bar % 2 == 1:
            notes.append({"pitch": VOX_TRIGGER, "time": b0 + 2.5, "duration": 0.5, "velocity": 102})
    return notes


def vox_toast_full() -> list[dict]:
    """Busy toast — call/response on every bar plus a 4& flick."""
    notes = []
    for bar in range(4):
        b0 = bar * 4
        notes.append({"pitch": VOX_TRIGGER, "time": b0 + 0.0, "duration": 0.4, "velocity": 110})
        notes.append({"pitch": VOX_TRIGGER, "time": b0 + 2.0, "duration": 0.4, "velocity": 105})
        if bar in (1, 3):
            notes.append({"pitch": VOX_TRIGGER, "time": b0 + 3.5, "duration": 0.25, "velocity": 100})
    return notes


def vox_echo_dubout() -> list[dict]:
    """Single trigger early — let Live's delay/reverb carry it across the bar."""
    return [
        {"pitch": VOX_TRIGGER, "time": 0.0, "duration": 0.5, "velocity": 110},
        {"pitch": VOX_TRIGGER, "time": 8.0, "duration": 0.5, "velocity": 95},
    ]


# ---- stab bursts ------------------------------------------------------

def stab_bursts() -> list[dict]:
    """Quick chord punctuations on bar-ends — used in raggajungle alongside organ skank
    when stab is its own channel. (In ragga we route skank to 'stab', so this isn't used
    in the default plan; kept for variant arrangements.)"""
    notes = []
    for bar in range(4):
        b0 = bar * 4
        for p in EM_CHORD:
            notes.append({"pitch": p, "time": b0 + 3.75, "duration": 0.25, "velocity": 100})
    return notes


# ---- the participation matrix -----------------------------------------
#
# 'audio'  → duplicate slot-0 sample to scene slot
# callable → MIDI clip from notes
# omitted  → channel silent in this scene
#
# Note: in this ragga arrangement, the 'stab' synth channel CARRIES the
# ragga organ skank rather than chord stabs — that's the genre signature.

SCENE_PLAN: dict[str, dict[str, object]] = {
    "DUB_IN": {
        "drums": drums_dub_in,
        "sub":   "audio",
        "stab":  organ_skank_tease,
        "pad":   "audio",
        "vox":   vox_call_in,
        "fx":    "audio",
    },
    "STEPPER": {
        "drums": drums_stepper,
        "sub":   "audio",
        "bass":  bass_stepper,
        "stab":  organ_skank_stepper,
        "pad":   "audio",
        "vox":   vox_toast_stepper,
    },
    "RAGGAJUNGLE": {
        "drums": drums_raggajungle,
        "break": "audio",
        "sub":   "audio",
        "bass":  bass_raggajungle,
        "stab":  organ_skank_full,
        "pad":   "audio",
        "vox":   vox_toast_full,
        "fx":    "audio",
    },
    "DUBOUT": {
        "drums": drums_dubout,
        "sub":   "audio",
        "stab":  organ_skank_tease,
        "pad":   "audio",
        "vox":   vox_echo_dubout,
        "fx":    "audio",
    },
}


# ---- the layout (same channels, ragga scene names) --------------------

LAYOUT = MetaLayout(
    channels=[
        ChannelSpec(role="drums", kind=ChannelKind.DRUM_RACK,
                    default_device="Drum Rack", default_browser_path="instruments"),
        ChannelSpec(role="break", kind=ChannelKind.AUDIO),
        ChannelSpec(role="sub",   kind=ChannelKind.AUDIO),
        ChannelSpec(role="bass",  kind=ChannelKind.SYNTH,
                    default_device="Operator", default_browser_path="instruments"),
        ChannelSpec(role="stab",  kind=ChannelKind.SYNTH,
                    default_device="Operator", default_browser_path="instruments"),
        ChannelSpec(role="pad",   kind=ChannelKind.AUDIO),
        ChannelSpec(role="vox",   kind=ChannelKind.SAMPLER,
                    default_device="Simpler", default_browser_path="instruments"),
        ChannelSpec(role="fx",    kind=ChannelKind.AUDIO),
    ],
    scenes=[
        SceneSpec(name="DUB_IN",      archetype="build",
                  description="atmospheric intro — no drums, vox call, skank tease"),
        SceneSpec(name="STEPPER",     archetype="drop",
                  description="roots-rock half-time — kick 1+3, organ skank, walking bass"),
        SceneSpec(name="RAGGAJUNGLE", archetype="drop2",
                  description="chopped amen + skank + sub bonks + toast — full slam"),
        SceneSpec(name="DUBOUT",      archetype="break",
                  description="drums drop, vocal echo, sub holds, fx swirls"),
    ],
)
