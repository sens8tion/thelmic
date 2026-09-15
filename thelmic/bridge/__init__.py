"""Genre-neutral Live-control bridge.

The bridge contains everything that's NOT an aesthetic choice — the LOM
RPC client, mediated-session scaffolding, mechanical helpers (find_track,
EQ utils, sidechain, transport rituals), the abstract event-timeline
engine, the tonality and narrative-grammar abstractions.

NO statements like "the impact is sacred", no genre-specific frequencies,
no fixed track names. Pure mechanism.

Aesthetic packs (`thelmic.aesthetics.*`) layer on top, providing
patterns, anticipation grammar, mix recipes, and the section palette
for a specific musical form.

Re-exports the foundation classes so existing user code keeps working.
"""
from __future__ import annotations

# Re-export the LOM bridge primitives at their original import paths
from thelmic.live_channel import LiveChannel
from thelmic.mediated_session import MediatedSession, open_session
from thelmic.session_log import SessionLog, LoggingChannel

# Mechanical helpers (split out from the monolithic agent_helpers)
from thelmic.bridge.helpers import (
    # discovery
    find_track, find_device, ensure_device, health_check,
    # eq
    hz_to_norm, norm_to_hz, set_eq_band, set_band_frequency, disable_all_eq_bands,
    EQ8_HP_48, EQ8_HP_12, EQ8_LOW_SHELF, EQ8_BELL, EQ8_NOTCH, EQ8_HIGH_SHELF,
    EQ8_LP_12, EQ8_LP_48, EQ8_FREQ_LOW_HZ, EQ8_FREQ_HIGH_HZ,
    EQ8_LOW_SHELF_GUESS,
    EQ8_HP_12_GUESS, EQ8_HP_48_GUESS, EQ8_LP_12_GUESS, EQ8_LP_48_GUESS,
    # transport
    hard_reset, arm_take, disarm_take, ms_to_beats,
    # params
    set_param, describe_param, safe_set_param, SemanticParam, resolve_semantic_param,
    parse_display, param_with_display, set_by_display,
    # sidechain
    sidechain_pump,
    # patterns / utilities
    to_clip_notes, repeat_pattern,
)

# Tonality
from thelmic.bridge.tonality import (
    Key, Scale, Chord, Voicing,
    NaturalMinor, NaturalMajor, Dorian, Phrygian, Mixolydian,
    Aeolian, Locrian, Lydian, Chromatic, Custom,
)

# Narrative grammars
from thelmic.bridge.grammars import (
    Grammar, Section, Fragment, TransitionSpec, AnticipationSpec,
    BuildDropRelease, StaticDrone, IsoRhythm, ThroughComposed, Rotational,
)

# Event-timeline engine
from thelmic.bridge.timeline import (
    Timeline, fire_arrangement, schedule_ramp, RampSpec,
)

__all__ = [
    "LiveChannel", "MediatedSession", "open_session",
    "SessionLog", "LoggingChannel",
    "find_track", "find_device", "ensure_device", "health_check",
    "hz_to_norm", "norm_to_hz", "set_eq_band", "set_band_frequency",
    "disable_all_eq_bands",
    "EQ8_HP_48", "EQ8_HP_12", "EQ8_LOW_SHELF", "EQ8_BELL", "EQ8_NOTCH",
    "EQ8_HIGH_SHELF", "EQ8_LP_12", "EQ8_LP_48",
    "EQ8_FREQ_LOW_HZ", "EQ8_FREQ_HIGH_HZ", "EQ8_LOW_SHELF_GUESS",
    "EQ8_HP_12_GUESS", "EQ8_HP_48_GUESS", "EQ8_LP_12_GUESS", "EQ8_LP_48_GUESS",
    "hard_reset", "arm_take", "disarm_take", "ms_to_beats",
    "set_param", "describe_param", "safe_set_param", "SemanticParam", "resolve_semantic_param",
    "parse_display", "param_with_display", "set_by_display",
    "sidechain_pump", "to_clip_notes", "repeat_pattern",
    "Key", "Scale", "Chord", "Voicing",
    "NaturalMinor", "NaturalMajor", "Dorian", "Phrygian", "Mixolydian",
    "Aeolian", "Locrian", "Lydian", "Chromatic", "Custom",
    "Grammar", "Section", "Fragment", "TransitionSpec", "AnticipationSpec",
    "BuildDropRelease", "StaticDrone", "IsoRhythm", "ThroughComposed", "Rotational",
    "Timeline", "fire_arrangement", "schedule_ramp", "RampSpec",
]
