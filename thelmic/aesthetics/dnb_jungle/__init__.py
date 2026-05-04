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

# 16-track instrument basis. ROLE-NAMED — the names communicate musical
# function, not historical content. Setup creates tracks with these names;
# legacy session names (HARDKIT / TECTONIC / etc.) still resolve via the
# fallback hints in lifecycle.setup_session.
EXPECTED_TRACKS = (
    # Drums
    "DRUMS",            # main drum rack (or HARDKIT for legacy)
    "AMEN",             # chopped amen break rack
    "BREAK",            # audio break sample (or BREAKBEAST for legacy)
    # Bass
    "SUB",              # sub bass (or SUBBONK)
    "MID_BASS",         # mid-bass synth (or TECTONIC)
    # Harmonic
    "STAB",             # chord stabs
    "ORGAN",            # ragga organ
    "PAD",              # pad (or COLD MIST)
    # Vocal one-shots
    "VOX_CALL",         # the call vocal (or VOX / VOX YO)
)

# Logical role → list of acceptable track-name substrings (in priority order).
# Lifecycle uses this to map session tracks to roles.
ROLE_TRACK_HINTS = {
    "drums":         ["DRUMS",     "HARDKIT"],
    "drums_alt":     ["AMEN",      "AMEN CHOPPED"],
    "break":         ["BREAK",     "BREAKBEAST"],
    "sub":           ["SUB",       "SUBBONK"],
    "mid_bass":      ["MID_BASS",  "TECTONIC"],
    "stab":          ["STAB"],
    "organ":         ["ORGAN"],
    "pad":           ["PAD",       "COLD MIST"],
    "vox_call":      ["VOX_CALL",  "VOX YO", "VOX"],
    "vox_response":  ["VOX_RESP",  "VOX BIG"],
    "vox_chorus":    ["VOX_CHOR",  "VOX SEL"],
}

from .arrangement import build_timeline
from .lifecycle  import (
    setup_session, pull_samples, compose_clips,
    configure_mix, prepare_clips, preview_session,
)
