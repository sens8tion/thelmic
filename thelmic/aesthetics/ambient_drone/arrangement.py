"""ambient_drone arrangement — long sections, slow blends, no impacts.

Builds a Timeline of section markers + ramps. No `drop` events, no
silence events. Each section transitions via slow filter morphing,
volume swelling, or stereo-image opening.
"""
from __future__ import annotations
from thelmic.bridge.timeline import Timeline, RampSpec
from thelmic.bridge.helpers import SemanticParam


def build_timeline() -> Timeline:
    tl = Timeline()
    # Drone needs a played clip on the drone tracks; we still fire scenes
    # but each scene is held for a long time and parameter ramps do the work.
    # Slot 0 is the only firing — everything else is parameter automation.
    tl.add_scene(0, 256.0, tag="ground")

    # 32 bars warming: slowly bring shimmer track up
    tl.add_ramp(RampSpec(
        track="shimmer", semantic=SemanticParam.GAIN, device_substring="eq8",
        param_name="Output Gain", from_value=-1.0, to_value=0.0,
        duration_bars=32, steps=64, curve="log", tag="shimmer warming"))

    # 32 bars darkening: drone_mid filter closes (LP descending)
    tl.add_ramp(RampSpec(
        track="drone_mid", device_substring="eq8",
        param_name="8 Frequency A", from_value=0.85, to_value=0.45,
        duration_bars=32, steps=48, curve="exp", tag="drone_mid darkening"))

    # 32 bars shimmering: shimmer track HP rises (more high partials)
    tl.add_ramp(RampSpec(
        track="shimmer", device_substring="eq8",
        param_name="1 Frequency A", from_value=0.55, to_value=0.85,
        duration_bars=32, steps=48, curve="log", tag="shimmer ascending"))

    # 32 bars thickening: noise_layer comes in via volume ramp
    tl.add_ramp(RampSpec(
        track="noise_layer", semantic=SemanticParam.DRY_WET,
        device_substring="eq8", param_name="Output Gain",
        from_value=-1.0, to_value=-0.3, duration_bars=32, steps=48,
        curve="log", tag="noise thickening"))

    # 32 bars stillness: hold (no ramps)
    tl.add_section_marker("stillness", 32, "stillness")

    # 64 bars dissolution: everything fades. Long crossfades.
    tl.add_ramp(RampSpec(
        track="drone_fundamental", semantic=SemanticParam.GAIN,
        device_substring="eq8", param_name="Output Gain",
        from_value=0.0, to_value=-1.0, duration_bars=64, steps=128,
        curve="exp", tag="fundamental dissolves"))
    tl.add_ramp(RampSpec(
        track="shimmer", semantic=SemanticParam.GAIN,
        device_substring="eq8", param_name="Output Gain",
        from_value=0.0, to_value=-1.0, duration_bars=64, steps=128,
        curve="exp", tag="shimmer dissolves"))

    return tl
