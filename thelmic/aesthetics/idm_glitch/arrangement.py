"""idm_glitch arrangement — rotational form with parameter drift.

A 'head' cell repeats; each rotation drifts a parameter slightly so
the listener perceives evolution without resolution. No drops.
"""
from __future__ import annotations
from thelmic.bridge.timeline import Timeline, RampSpec


def build_timeline() -> Timeline:
    tl = Timeline()
    # head: state the cell
    tl.add_scene(0, 16, tag="head")

    # 4 variations, each 16 bars, with drifting Beat Repeat density
    for variation_idx in range(4):
        tl.add_scene(1 + variation_idx, 16, tag=f"variation {variation_idx+1}")
        # drift the granular_lead's filter cutoff over each variation
        tl.add_ramp(RampSpec(
            track="granular_lead", device_substring="eq8",
            param_name="1 Frequency A",
            from_value=0.30 + 0.05 * variation_idx,
            to_value=0.30 + 0.05 * (variation_idx + 1),
            duration_bars=16, steps=24, curve="linear",
            tag=f"granular drift v{variation_idx+1}"))

    # outhead: return to head
    tl.add_scene(0, 16, tag="outhead (return to head)")
    return tl
