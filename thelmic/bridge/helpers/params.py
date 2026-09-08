"""Device parameter helpers — # mechanical.

Includes the SemanticParam abstraction: rather than hardcoding device-
specific param names ("Saturator.Drive"), aesthetic packs name semantic
intent (DRIVE, CUTOFF, RESONANCE, ...) and the bridge resolves to the
correct param on whatever device class is at hand.
"""
from __future__ import annotations
from enum import Enum
from typing import Optional


class SemanticParam(Enum):
    """Genre-neutral semantic parameter labels.

    Aesthetic packs target these; the bridge resolves to the actual
    device param via DEVICE_PARAM_MAP. Lets a 'drive ramp' work on
    Saturator, Drum Buss, FabFilter Saturn, or any future device.
    """
    GAIN        = "gain"
    CUTOFF      = "cutoff"          # filter cutoff
    RESONANCE   = "resonance"
    PITCH       = "pitch"           # in semitones
    DETUNE      = "detune"          # in cents
    DRIVE       = "drive"           # any saturation amount
    DENSITY     = "density"         # for granular / glitch
    CHARACTER   = "character"       # FM index, wavetable position, etc.
    DRY_WET     = "dry_wet"
    THRESHOLD   = "threshold"       # comp / gate
    RATIO       = "ratio"
    ATTACK      = "attack"
    RELEASE     = "release"
    LFO_RATE    = "lfo_rate"
    LFO_AMOUNT  = "lfo_amount"
    LFO_SHAPE   = "lfo_shape"
    DELAY_TIME  = "delay_time"
    DELAY_FB    = "delay_feedback"
    REVERB_SIZE = "reverb_size"


# Device-class → SemanticParam → param name on that device
DEVICE_PARAM_MAP: dict[str, dict[SemanticParam, str]] = {
    "Saturator": {
        SemanticParam.DRIVE: "Drive",
        SemanticParam.DRY_WET: "Dry/Wet",
        SemanticParam.GAIN: "Output",
    },
    "Eq8": {
        # Cutoff is band-specific; aesthetic packs typically target
        # band-named params directly (e.g. "1 Frequency A" for HP)
        SemanticParam.CUTOFF: "1 Frequency A",
        SemanticParam.RESONANCE: "1 Resonance A",
    },
    "Operator": {
        SemanticParam.PITCH: "Transpose",
        SemanticParam.GAIN: "Volume",
        SemanticParam.CUTOFF: "Filter Freq",
    },
    "AutoPan": {
        SemanticParam.LFO_AMOUNT: "Amount",
        SemanticParam.LFO_RATE: "Frequency",
    },
    "Compressor2": {
        SemanticParam.THRESHOLD: "Threshold",
        SemanticParam.RATIO: "Ratio",
        SemanticParam.ATTACK: "Attack",
        SemanticParam.RELEASE: "Release",
    },
    "GlueCompressor": {
        SemanticParam.THRESHOLD: "Threshold",
        SemanticParam.RATIO: "Ratio",
        SemanticParam.ATTACK: "Attack",
        SemanticParam.RELEASE: "Release",
        SemanticParam.DRY_WET: "Dry/Wet",
        SemanticParam.GAIN: "Makeup",
    },
    "DrumBuss": {
        SemanticParam.DRIVE: "Drive",
        SemanticParam.GAIN: "Output Gain",
    },
    "BeatRepeat": {
        SemanticParam.DENSITY: "Grid",
        SemanticParam.DRY_WET: "Chance",
    },
    "FilterDelay": {
        SemanticParam.DELAY_TIME: "Beat Swing",
        SemanticParam.DELAY_FB: "Feedback",
    },
    "Reverb": {
        SemanticParam.REVERB_SIZE: "Room Size",
        SemanticParam.DRY_WET: "Dry/Wet",
    },
}


def resolve_semantic_param(device_class_name: str,
                            semantic: SemanticParam) -> Optional[str]:
    """Map (device class, semantic intent) → actual param name. None if unknown."""
    return DEVICE_PARAM_MAP.get(device_class_name, {}).get(semantic)


def describe_param(ch, track_index: int, device_index: int,
                   param_name: str, *, timeout: float = 5.0) -> dict:
    """Source-of-truth read for one device param — the range is never guessed.

    Returns {'index','name','value','min','max','quantized'}. Raises ValueError
    (listing what IS on the device) when the name doesn't match.
    """
    di = ch.get_device_info(track_index, device_index).result(timeout=timeout)
    p = next((p for p in di["parameters"] if p["name"] == param_name), None)
    if p is None:
        have = ", ".join(pp["name"] for pp in di["parameters"][:14])
        raise ValueError(
            f"param {param_name!r} not on {di.get('class_name', 'device')} "
            f"(have: {have}{'...' if len(di['parameters']) > 14 else ''})")
    return {"index": p["index"], "name": p["name"], "value": p["value"],
            "min": p["min"], "max": p["max"],
            "quantized": bool(p.get("is_quantized", False))}


def set_param(ch, track_index: int, device_index: int, param_name: str,
              value: float | None = None, *,
              frac: float | None = None,
              expect: tuple[float, float] | None = None,
              timeout: float = 3.0, quiet: bool = False) -> dict:
    """Canonical range-aware param write — the device's real range is READ first,
    so a value is never set on a guessed scale.

    This is the primitive to reach for. The recurring bug it kills: Live params
    don't share one scale (Operator Volume is 0..1, Overdrive Drive is 0..100,
    Saturator Drive is 0..1-mapped-to-dB, EQ Gain is raw dB). A raw setter happily
    writes 0.55 to a 0..100 param (= ~0.5%, effectively bypassed) with no warning.

    Specify the target exactly ONE way:
      • frac=0..1   scale-independent intent. Maps to min + frac*(max-min), so
                    "70% driven" is frac=0.70 whether the param is 0..1, 0..100,
                    or a dB range. Quantized params snap to the nearest step.
      • value=x     absolute. Pair with expect=(lo,hi) to assert the param's real
                    (min,max); a mismatch RAISES rather than silently setting a
                    valid-but-wrong-scale number. Out-of-range values are clamped
                    (with a printed note) when no expect guard is given.

    Returns the describe_param dict plus 'set' (value actually written) and
    'frac' (its normalized position in range).
    """
    if (value is None) == (frac is None):
        raise ValueError("set_param: pass exactly one of value= or frac=")
    info = describe_param(ch, track_index, device_index, param_name, timeout=5.0)
    lo, hi = info["min"], info["max"]
    if frac is not None:
        f = max(0.0, min(1.0, float(frac)))
        target = lo + f * (hi - lo)
    else:
        if expect is not None and (abs(lo - expect[0]) > 1e-6 or abs(hi - expect[1]) > 1e-6):
            raise ValueError(
                f"{param_name!r} real range is {lo}..{hi}, not the expected "
                f"{expect[0]}..{expect[1]} — value {value} would be on the wrong scale")
        target = float(value)
        if target < lo or target > hi:
            clamped = max(lo, min(hi, target))
            if not quiet:
                print(f"  [clamp] {param_name}: {target} -> {clamped} (range {lo}..{hi})")
            target = clamped
    if info["quantized"]:
        target = float(round(target))
    ch.set_device_param(track_index, device_index, info["index"], target).result(timeout=timeout)
    span = (hi - lo) or 1.0
    info["set"] = target
    info["frac"] = (target - lo) / span
    return info


def safe_set_param(ch, track_index: int, device_index: int,
                    param_name: str, value: float) -> dict:
    """Back-compat shim: absolute write, clamped to the real range. New code should
    prefer set_param (frac= for scale-independent intent, expect= to assert range)."""
    return set_param(ch, track_index, device_index, param_name, value=value)
