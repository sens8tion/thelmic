"""EQ8 helpers — # mechanical, genre-neutral.

Hz → normalized 0..1 mapping for EQ8's Frequency parameter, plus filter
type constants. Only BELL=3 and HIGH_SHELF=5 are confidently verified
on Live 12; the others are educated guesses (use and verify by listening).
"""
from __future__ import annotations
import math


EQ8_BELL = 3
EQ8_HIGH_SHELF = 5
EQ8_LOW_SHELF_GUESS = 2
EQ8_HP_12_GUESS = 1
EQ8_HP_48_GUESS = 0
EQ8_LP_12_GUESS = 6
EQ8_LP_48_GUESS = 7


def hz_to_norm(hz: float, low_hz: float = 30.0, high_hz: float = 22000.0) -> float:
    """Convert Hz to EQ8's normalized 0..1 frequency parameter (log mapping)."""
    hz = max(low_hz, min(high_hz, hz))
    return math.log(hz / low_hz) / math.log(high_hz / low_hz)


def set_eq_band(ch, track_index: int, eq_device_index: int, band: int, *,
                ftype: int, hz: float, gain: float = 0.0, q_norm: float = 0.5,
                on: bool = True) -> None:
    """Set one EQ8 band — wraps param-name lookup + Hz→normalized conversion.

    Use ftype=EQ8_BELL or EQ8_HIGH_SHELF confidently; other types are fragile."""
    di = ch.get_device_info(track_index, eq_device_index).result(timeout=5)
    idx = {p["name"]: p["index"] for p in di["parameters"]}
    ch.set_device_param(track_index, eq_device_index, idx[f"{band} Filter On A"],
                         1 if on else 0).result(timeout=3)
    if not on:
        return
    ch.set_device_param(track_index, eq_device_index, idx[f"{band} Filter Type A"],
                         ftype).result(timeout=3)
    ch.set_device_param(track_index, eq_device_index, idx[f"{band} Frequency A"],
                         hz_to_norm(hz)).result(timeout=3)
    ch.set_device_param(track_index, eq_device_index, idx[f"{band} Gain A"],
                         gain).result(timeout=3)
    ch.set_device_param(track_index, eq_device_index, idx[f"{band} Resonance A"],
                         q_norm).result(timeout=3)


def disable_all_eq_bands(ch, track_index: int, eq_device_index: int) -> None:
    di = ch.get_device_info(track_index, eq_device_index).result(timeout=5)
    idx = {p["name"]: p["index"] for p in di["parameters"]}
    for b in range(1, 9):
        ch.set_device_param(track_index, eq_device_index, idx[f"{b} Filter On A"],
                             0).result(timeout=3)
