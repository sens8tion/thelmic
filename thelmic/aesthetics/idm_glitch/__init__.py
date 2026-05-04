"""idm_glitch aesthetic pack.

IDM in the Autechre / Squarepusher / early Aphex sense — broken-time
drum programming, granular textures, microtiming. Uses Rotational
grammar: variations cycling around a fixed cell, no global climax.
"""
from .constants import PACK_NAME, PACK_BPM, PACK_KEY_ROOT, FREQ_SEPARATION
from .arrangement import build_timeline
from thelmic.bridge.grammars import Rotational

PACK_GRAMMAR = Rotational()
