"""ambient_drone aesthetic pack.

Slow-evolving drones with no climax, no impacts, only continuous textural
transformation. Tim Hecker, Eliane Radigue, late Tony Conrad, La Monte Young.

Uses StaticDrone grammar — sections are textural states (warming, shimmering,
darkening), transitions are always slow blends, anticipation is replaced
with continuous swell.
"""
from .constants  import PACK_NAME, PACK_BPM, PACK_KEY_ROOT, FREQ_SEPARATION
from .arrangement import build_timeline
from thelmic.bridge.grammars import StaticDrone

PACK_GRAMMAR = StaticDrone()
