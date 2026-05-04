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

# 8x4 meta-layout for jungle. Sessions targeting this pack use this for
# bootstrap; the legacy 16-track basis (EXPECTED_TRACKS above) stays for
# back-compat with already-built sessions.
from thelmic.meta import MetaLayout, ChannelSpec, SceneSpec, ChannelKind

from .compose_8x4 import SCENE_PLAN, CLIP_LENGTH_BEATS
from thelmic.meta import (
    FreqRegion, LevelTarget, ChannelAudio, StageCheckpoint,
)

# Per-role audio meta — frequency territory + level discipline.
# Reads as an intent declaration: this is what each channel SHOULD do
# at the EQ and gain-staging layers. Mix pass + audit pass consult this.
CHANNEL_AUDIO: dict[str, ChannelAudio] = {
    "drums": ChannelAudio(
        freq=FreqRegion(hp_hz=40, lp_hz=None, peak_band_hz=(50, 120), exclusive=True),
        level=LevelTarget(
            peak_db=-3.0, rms_db=-12.0, headroom_db=3.0,
            chain_caps=[
                StageCheckpoint("input", peak_db=-3.0),       # cap pre-saturator
                StageCheckpoint("Saturator", peak_db=-3.0),   # cap pre-EQ8
                StageCheckpoint("output", peak_db=-3.0),
            ],
        ),
    ),
    "break": ChannelAudio(
        freq=FreqRegion(hp_hz=80, lp_hz=12000, peak_band_hz=(200, 4000)),
        level=LevelTarget(peak_db=-6.0, rms_db=-15.0, sidechain_source="perc_bus"),
    ),
    "sub": ChannelAudio(
        freq=FreqRegion(hp_hz=30, lp_hz=700, peak_band_hz=(35, 80), exclusive=True),
        level=LevelTarget(peak_db=-6.0, rms_db=-14.0, sidechain_source="perc_bus"),
    ),
    "bass": ChannelAudio(
        freq=FreqRegion(hp_hz=50, lp_hz=400, peak_band_hz=(80, 200)),
        level=LevelTarget(peak_db=-7.0, rms_db=-16.0, sidechain_source="perc_bus"),
    ),
    "stab": ChannelAudio(
        freq=FreqRegion(hp_hz=200, lp_hz=None, peak_band_hz=(300, 1500)),
        level=LevelTarget(peak_db=-8.0, rms_db=-18.0, sidechain_source="perc_bus"),
    ),
    "pad": ChannelAudio(
        freq=FreqRegion(hp_hz=250, lp_hz=None, peak_band_hz=(400, 2000)),
        level=LevelTarget(peak_db=-12.0, rms_db=-22.0, sidechain_source="perc_bus"),
    ),
    "vox": ChannelAudio(
        freq=FreqRegion(hp_hz=150, lp_hz=8000, peak_band_hz=(300, 3500)),
        level=LevelTarget(peak_db=-6.0, rms_db=-15.0),
    ),
    "fx": ChannelAudio(
        freq=FreqRegion(hp_hz=180, lp_hz=None, peak_band_hz=(500, 6000)),
        level=LevelTarget(peak_db=-10.0, rms_db=-20.0, sidechain_source="perc_bus"),
    ),
}

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
        SceneSpec(name="BUILD",  archetype="build",
                  description="tension rising, no drop drums yet"),
        SceneSpec(name="DROP",   archetype="drop",
                  description="full slam — drums + sub + bass + vox"),
        SceneSpec(name="BREAK",  archetype="break",
                  description="rhythmic flip, drums thinned, vox foreground"),
        SceneSpec(name="DROP2",  archetype="drop2",
                  description="Rotterdam/gabber variant — distorted, faster pulse"),
    ],
)
