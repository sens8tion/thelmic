"""dnb_jungle pack constants — drum-pitch map, mix tables, gotcha flags.

These are aesthetic-pack-scoped, not bridge-level. A different pack
might map drums to different MIDI pitches (orchestral percussion has
no GM standard) or use entirely different mix targets.
"""
from __future__ import annotations

# Drum pitches (GM mapping, applies to most drum racks)
KICK = 36
SNARE = 38
HAT_C = 42
HAT_O = 46
RIDE = 51
CRASH = 49
SIDESTICK = 37
HAND_CLAP = 39
LOW_TOM = 41
HI_TOM = 50

# Frequency separation table (Hz: HP, LP)
FREQ_SEPARATION = {
    "kick":      (35,   None),
    "snare":     (90,   None),
    "hat":       (250,  None),
    "perc":      (120,  None),
    "sub":       (30,   700),
    "mid_bass":  (50,   400),
    "bass":      (40,   None),
    "stab":      (200,  None),
    "lead":      (140,  None),
    "pad":       (250,  None),
    "organ":     (180,  None),
    "vox":       (150,  None),
    "drums_bus": (40,   None),
    "fx":        (180,  None),
}

# Track-level gain defaults by role
TRACK_LEVELS = {
    "kick":      0.85,
    "snare":     0.80,
    "hat":       0.65,
    "perc":      0.70,
    "sub":       0.55,
    "bass":      0.72,
    "lead":      0.78,
    "pad":       0.55,
    "fx":        0.60,
    "vox":       0.78,
    "perc_bus":  0.80,
    "melo_bus":  0.78,
}

# Studio engineer voice categorisation
HARD_CUT_SAFE_VOICES = {
    "kick", "snare", "sub", "impact", "perc_bus",
}
HARSH_VOICES_NEED_TAPER = {
    "saturated_lead", "stab", "ride", "crash_loop", "fm_bell",
    "hardkit_loop", "vox_chop", "organ", "noise_riser",
}
TAPER_MS = {"soft": 8, "medium": 25, "long": 60}
STAGGER_MS_BETWEEN_VOICES = (3, 12)

# Outro shaping
OUTRO_FADE_MS_DEFAULT = 350
OUTRO_INSTRUMENT_STAGGER_MS = 40
OUTRO_LET_REVERB_RING_MS = 800

# Entry smoothing defaults
ENTRY_FADE_MS_DEFAULT = 250
ENTRY_FILTER_SWEEP_MS_DEFAULT = 400

# Multi-take printing
TAKE_GAP_BARS = 4

# Gotcha flags (named so future code can grep them)
DRUM_PAD_INDIVIDUAL_LOAD_BROKEN = True
SIMPLER_SLICING_VIA_PROPERTY = True
COMPRESSOR_GAIN_REDUCTION_NOT_EXPOSED = True
LIMITER_ON_MASTER_KILLS_BASS = True
SIDECHAIN_VIA_ROUTING_TYPE = True
LIVE_DEFAULTS_TO_4_TRACKS = True
RELOAD_SCRIPT_AFTER_RPC_ADD = True
WINDOWS_NEEDS_UTF8_ENV = True
SNAP_LAYERED_AT_37 = True
HATS_MUST_LOCK_TO_KICK_GRID = True

LIVE_DEFAULT_TRACK_COUNT = 4

# Default arrangement (legacy DEFAULT_ARRANGEMENT used by older scripts)
DEFAULT_ARRANGEMENT = [
    (0, 16),  (1, 16),  (2, 16),  (3, 16),
    (4, 32),  (5, 16),  (6, 16),  (7, 32),
    (9, 32),  (10, 8),  (12, 16), (13, 16),
    (14, 32), (15, 32), (16, 16),
]
