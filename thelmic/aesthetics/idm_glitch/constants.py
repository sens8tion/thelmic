"""idm_glitch pack constants."""
from __future__ import annotations

PACK_NAME = "idm_glitch"
PACK_BPM = 138.0
PACK_KEY_ROOT = 38               # D2 (slightly off-centre tonality)

FREQ_SEPARATION = {
    "broken_drums":   (60,   None),
    "granular_lead":  (200,  None),
    "modulating_bass":(35,   600),
    "atmospheric":    (300,  None),
    "click_layer":    (1500, None),
}

TRACK_LEVELS = {
    "broken_drums":     0.78,
    "granular_lead":    0.65,
    "modulating_bass":  0.65,
    "atmospheric":      0.55,
    "click_layer":      0.50,
}
