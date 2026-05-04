"""Sidechain compression — # mechanical, intensity-parameterised.

Setting up sidechain in Live needs: load Compressor if missing, set
S/C On + Threshold + Ratio + Attack + Release, then set the source
track via the dedicated routing-type RPC (sidechain isn't a parameter).

Intensity presets are aesthetic-flavoured (subtle/medium/heavy); a pack
that wants different defaults can pass explicit kwargs.
"""
from __future__ import annotations
from .discovery import find_device


def sidechain_pump(ch, target_track: int, source_track: int,
                    compressor_uri: str,
                    intensity: str = "medium",
                    **overrides) -> int:
    """Apply sidechain pump on target_track keyed from source_track.

    intensity: 'subtle' | 'medium' | 'heavy' (or pass explicit threshold,
    ratio, attack, release, sc_gain via **overrides). Returns the
    compressor device index.
    """
    cmp_idx = find_device(ch, target_track, "Compressor2")
    if cmp_idx is None:
        ch.load_device(target_track, compressor_uri).result(timeout=15)
        cmp_idx = find_device(ch, target_track, "Compressor2")
    di = ch.get_device_info(target_track, cmp_idx).result(timeout=5)
    idx = {p["name"]: p["index"] for p in di["parameters"]}
    presets = {
        "subtle": dict(threshold=0.55, ratio=0.45, attack=0.06, release=0.30, sc_gain=0.50),
        "medium": dict(threshold=0.45, ratio=0.65, attack=0.04, release=0.22, sc_gain=0.55),
        "heavy":  dict(threshold=0.35, ratio=0.85, attack=0.03, release=0.18, sc_gain=0.65),
    }
    settings = presets[intensity].copy()
    settings.update(overrides)

    ch.set_device_param(target_track, cmp_idx, idx["S/C On"], 1).result(timeout=3)
    ch.set_device_param(target_track, cmp_idx, idx["S/C Listen"], 0).result(timeout=3)
    ch.set_device_param(target_track, cmp_idx, idx["Threshold"], settings["threshold"]).result(timeout=3)
    ch.set_device_param(target_track, cmp_idx, idx["Ratio"], settings["ratio"]).result(timeout=3)
    ch.set_device_param(target_track, cmp_idx, idx["Attack"], settings["attack"]).result(timeout=3)
    ch.set_device_param(target_track, cmp_idx, idx["Release"], settings["release"]).result(timeout=3)
    ch.set_device_param(target_track, cmp_idx, idx["S/C Gain"], settings["sc_gain"]).result(timeout=3)
    if "LookAhead" in idx:
        ch.set_device_param(target_track, cmp_idx, idx["LookAhead"], 2).result(timeout=3)  # 10ms
    ch.set_device_sidechain_source(target_track, cmp_idx, source_track).result(timeout=10)
    return cmp_idx
