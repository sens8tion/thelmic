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


def safe_set_param(ch, track_index: int, device_index: int,
                    param_name: str, value: float) -> dict:
    """Set a param and clamp to its actual range — many Live params are normalized
    0..1 even when their UI shows dB or Hz. Logs the clamp for debugging."""
    di = ch.get_device_info(track_index, device_index).result(timeout=5)
    p = next((p for p in di["parameters"] if p["name"] == param_name), None)
    if p is None:
        raise ValueError(f"param '{param_name}' not on device")
    target = max(p["min"], min(p["max"], value))
    if abs(target - value) > 1e-6:
        print(f"  [warn] {param_name}: requested {value} clamped to {target} "
              f"(range {p['min']}..{p['max']})")
    return ch.set_device_param(track_index, device_index, p["index"], target).result(timeout=3)
