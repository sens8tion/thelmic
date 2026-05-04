"""DEPRECATED — use thelmic.bridge for genre-neutral helpers and
thelmic.aesthetics.<pack> for genre-specific patterns.

This file re-exports the new locations so existing code keeps working.
The historical content has been split into:

  thelmic.bridge.helpers       — discovery, eq, transport, params, sidechain, midi
  thelmic.bridge.tonality      — Key, Scale, Chord, Voicing
  thelmic.bridge.grammars      — narrative grammars
  thelmic.bridge.timeline      — event-timeline engine + ramps
  thelmic.aesthetics.dnb_jungle — drum patterns, anticipation, ARRANGEMENT,
                                  freq-separation table, gain-staging defaults

A future Claude prompt should import from those locations directly.
"""
from __future__ import annotations
import math
import time

# Re-export bridge mechanical helpers
from thelmic.bridge.helpers import (
    find_track, find_device, ensure_device, health_check,
    hz_to_norm, set_eq_band, disable_all_eq_bands,
    EQ8_BELL, EQ8_HIGH_SHELF, EQ8_LOW_SHELF_GUESS,
    EQ8_HP_12_GUESS, EQ8_HP_48_GUESS, EQ8_LP_12_GUESS, EQ8_LP_48_GUESS,
    hard_reset, arm_take, disarm_take, ms_to_beats,
    safe_set_param,
    sidechain_pump,
    to_clip_notes, repeat_pattern,
)

# Re-export aesthetic-pack content for backward compatibility
# (legacy scripts import these from agent_helpers directly)
from thelmic.aesthetics.dnb_jungle.constants import (
    KICK, SNARE, HAT_C, HAT_O, RIDE, CRASH,
    SIDESTICK, HAND_CLAP, LOW_TOM, HI_TOM,
    DEFAULT_ARRANGEMENT, TRACK_LEVELS, FREQ_SEPARATION,
    HARD_CUT_SAFE_VOICES, HARSH_VOICES_NEED_TAPER, TAPER_MS,
    STAGGER_MS_BETWEEN_VOICES,
    OUTRO_FADE_MS_DEFAULT, OUTRO_INSTRUMENT_STAGGER_MS,
    OUTRO_LET_REVERB_RING_MS,
    ENTRY_FADE_MS_DEFAULT, ENTRY_FILTER_SWEEP_MS_DEFAULT,
    TAKE_GAP_BARS,
    DRUM_PAD_INDIVIDUAL_LOAD_BROKEN, SIMPLER_SLICING_VIA_PROPERTY,
    COMPRESSOR_GAIN_REDUCTION_NOT_EXPOSED, LIMITER_ON_MASTER_KILLS_BASS,
    SIDECHAIN_VIA_ROUTING_TYPE, LIVE_DEFAULTS_TO_4_TRACKS,
    RELOAD_SCRIPT_AFTER_RPC_ADD, WINDOWS_NEEDS_UTF8_ENV,
    SNAP_LAYERED_AT_37, HATS_MUST_LOCK_TO_KICK_GRID,
    LIVE_DEFAULT_TRACK_COUNT,
)

from thelmic.aesthetics.dnb_jungle.patterns import (
    amen_4bar, gabber_4bar, breakcore_4bar,
    anticipation_fill, hat_acceleration,
)

from thelmic.aesthetics.dnb_jungle.transforms import (
    breathe_velocity, pull_back_before_drop,
    crash_decay_tail, low_kick_decay_tail,
    soft_outro_offsets, take_start_bar, thin_build_for_massive_drop,
    smooth_clip_entry, apply_freq_separation, gain_stage_track,
    midbass_thump_recipe, sub_track_recipe, drop_anticipation_recipe,
    configure_master_glue,
)


__all__ = [
    # bridge
    "find_track", "find_device", "ensure_device", "health_check",
    "hz_to_norm", "set_eq_band", "disable_all_eq_bands",
    "EQ8_BELL", "EQ8_HIGH_SHELF", "EQ8_LOW_SHELF_GUESS",
    "EQ8_HP_12_GUESS", "EQ8_HP_48_GUESS", "EQ8_LP_12_GUESS", "EQ8_LP_48_GUESS",
    "hard_reset", "arm_take", "disarm_take", "ms_to_beats",
    "safe_set_param", "sidechain_pump",
    "to_clip_notes", "repeat_pattern",
    # dnb_jungle aesthetic — re-exported for back-compat
    "KICK", "SNARE", "HAT_C", "HAT_O", "RIDE", "CRASH",
    "SIDESTICK", "HAND_CLAP", "LOW_TOM", "HI_TOM",
    "DEFAULT_ARRANGEMENT", "TRACK_LEVELS", "FREQ_SEPARATION",
    "HARD_CUT_SAFE_VOICES", "HARSH_VOICES_NEED_TAPER", "TAPER_MS",
    "STAGGER_MS_BETWEEN_VOICES", "OUTRO_FADE_MS_DEFAULT",
    "OUTRO_INSTRUMENT_STAGGER_MS", "OUTRO_LET_REVERB_RING_MS",
    "ENTRY_FADE_MS_DEFAULT", "ENTRY_FILTER_SWEEP_MS_DEFAULT",
    "TAKE_GAP_BARS",
    "DRUM_PAD_INDIVIDUAL_LOAD_BROKEN", "SIMPLER_SLICING_VIA_PROPERTY",
    "COMPRESSOR_GAIN_REDUCTION_NOT_EXPOSED", "LIMITER_ON_MASTER_KILLS_BASS",
    "SIDECHAIN_VIA_ROUTING_TYPE", "LIVE_DEFAULTS_TO_4_TRACKS",
    "RELOAD_SCRIPT_AFTER_RPC_ADD", "WINDOWS_NEEDS_UTF8_ENV",
    "SNAP_LAYERED_AT_37", "HATS_MUST_LOCK_TO_KICK_GRID",
    "LIVE_DEFAULT_TRACK_COUNT",
    "amen_4bar", "gabber_4bar", "breakcore_4bar",
    "anticipation_fill", "hat_acceleration",
    "breathe_velocity", "pull_back_before_drop",
    "crash_decay_tail", "low_kick_decay_tail",
    "soft_outro_offsets", "take_start_bar", "thin_build_for_massive_drop",
    "smooth_clip_entry", "apply_freq_separation", "gain_stage_track",
    "midbass_thump_recipe", "sub_track_recipe", "drop_anticipation_recipe",
    "configure_master_glue",
]
