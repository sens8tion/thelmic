"""Generic event-timeline engine — # mechanical.

The timeline is a list of typed events. The engine walks them in
wall-clock-calibrated order during session_record so all parameter
changes get captured into the printed arrangement automation.

Event kinds (all genre-neutral):
  ("scene",    slot_index, duration_bars)         — fire scene + hold
  ("silence",  duration_beats, tag)               — stop_all_clips, hold
  ("ramp",     RampSpec)                          — set_device_param ramp
  ("tempo",    bpm, tag)                          — immediate set_tempo
  ("track_solo", [track_names], slot, bars)       — fire only some tracks
  ("section_marker", role, duration_bars, name)   — informational only

Aesthetic packs construct event lists from their Section objects via
their grammar. The engine doesn't know what a "drop" or "drone" is.
"""
from .ramps    import RampSpec, schedule_ramp, drain_ramps, resolve_ramp_target
from .engine   import Timeline, fire_arrangement, calibrate, wait_until_beat

__all__ = [
    "RampSpec", "schedule_ramp", "drain_ramps", "resolve_ramp_target",
    "Timeline", "fire_arrangement", "calibrate", "wait_until_beat",
]
