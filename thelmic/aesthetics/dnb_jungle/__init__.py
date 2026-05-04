"""dnb_jungle aesthetic pack — ragga jungle / dnb / breakcore / gabber arc.

The pack that the Live session is set up around. Encodes:
  - 165 bpm, 4/4, C natural minor
  - Track-role mapping: drums, sub, mid_bass, stab, pad, organ, vox
  - BuildDropRelease grammar (intro/build/riser/drop/breakdown/outro)
  - Anticipation: tightening hats → silence → sacred impact
  - Mix: heavy sidechain, master glue compression, saturator drive ramps
  - Vocabulary: "drop", "rotterdam", "ragga", "breakcore"
"""
from .constants    import (
    KICK, SNARE, HAT_C, HAT_O, RIDE, CRASH,
    SIDESTICK, HAND_CLAP, LOW_TOM, HI_TOM,
    DEFAULT_ARRANGEMENT, TRACK_LEVELS, FREQ_SEPARATION,
    OUTRO_LET_REVERB_RING_MS, OUTRO_INSTRUMENT_STAGGER_MS,
    TAKE_GAP_BARS,
)
from .patterns     import (
    amen_4bar, gabber_4bar, breakcore_4bar,
    anticipation_fill, hat_acceleration,
)
from .transforms   import (
    breathe_velocity, pull_back_before_drop,
    crash_decay_tail, low_kick_decay_tail,
    smooth_clip_entry, gain_stage_track, apply_freq_separation,
    midbass_thump_recipe, sub_track_recipe, drop_anticipation_recipe,
    configure_master_glue, soft_outro_offsets, take_start_bar,
    thin_build_for_massive_drop,
)
from thelmic.bridge.grammars import BuildDropRelease

PACK_NAME = "dnb_jungle"
PACK_GRAMMAR = BuildDropRelease()
PACK_BPM = 165.0
PACK_KEY_ROOT = 36                # C2 MIDI

# 16-track instrument basis for compositional surface area.
# health_check uses these as substring matches against actual track names —
# the session can have additional tracks beyond these.
EXPECTED_TRACKS = (
    # Drums
    "HARDKIT",          # main drum rack (kicks/snares/hats)
    "AMEN",             # chopped amen break rack (or any percussion-2)
    "BREAKBEAST",       # break sample track
    # Bass
    "SUBBONK",          # sub bass sample
    "TECTONIC",         # mid-bass synth (Operator)
    # Harmonic
    "STAB",             # chord stabs
    "ORGAN",            # ragga organ
    "COLD MIST",        # pad
    # Vocal one-shots
    "VOX",              # at least one VOX (matches VOX YO / VOX BIG / VOX SEL)
)

# Map of role → tracks that satisfy it (substring match). Lifecycle
# hooks consult this to know "what to write to as kick" etc.
ROLE_TRACK_HINTS = {
    "drums":         ["HARDKIT"],
    "drums_alt":     ["AMEN", "AMEN CHOPPED"],
    "break":         ["BREAKBEAST"],
    "sub":           ["SUBBONK"],
    "mid_bass":      ["TECTONIC"],
    "stab":          ["STAB"],
    "organ":         ["ORGAN"],
    "pad":           ["COLD MIST"],
    "vox_call":      ["VOX YO"],
    "vox_response":  ["VOX BIG"],
    "vox_chorus":    ["VOX SEL"],
}

from .arrangement import build_timeline
from .lifecycle  import (
    setup_session, pull_samples, compose_clips,
    configure_mix, prepare_clips, preview_session,
)
