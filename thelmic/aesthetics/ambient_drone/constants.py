"""ambient_drone pack constants.

No drum-pitch map (no drums). No drop slots, no anticipation tables.
A small frequency-separation table for textural roles.
"""
from __future__ import annotations

PACK_NAME    = "ambient_drone"
PACK_BPM     = 60.0                 # slow — but tempo is largely irrelevant in drone
PACK_KEY_ROOT = 36                   # C2 — long-held drone fundamental

# Section length defaults (in BARS — meaningless grid in drone, but the
# engine still wants bar-counted sections; choose long defaults)
DEFAULT_SECTION_BARS = 32

# Frequency separation: keep drones full-spectrum but separate textural roles
FREQ_SEPARATION = {
    "drone_fundamental": (25,   None),     # the long-held bass / sub
    "drone_mid":         (60,   2200),
    "shimmer":           (1500, None),     # high partials only
    "noise_layer":       (200,  6000),
    "field_recording":   (50,   None),
}

TRACK_LEVELS = {
    "drone_fundamental": 0.62,
    "drone_mid":         0.68,
    "shimmer":           0.55,
    "noise_layer":       0.50,
    "field_recording":   0.45,
}
