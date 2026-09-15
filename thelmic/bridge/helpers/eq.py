"""EQ8 helpers — # mechanical, genre-neutral.

Hz ↔ EQ Eight's Frequency parameter, plus the filter type constants. Nothing here
is guessed: every mapping below was measured against Live 12.4.6 over the bridge
on 2026-09-16, by writing raw values to a DISABLED band and reading back the
per-parameter "display" string Live shows in its own UI.

    Frequency A     min 0.0, max 1.0 — NOT Hz. Live displays

                        hz = 10 * 2200 ** raw          (log over 10 Hz .. 22 kHz)

                    raw 0.0 -> "10.0 Hz", 0.5 -> "469 Hz", 1.0 -> "22.0 kHz".
                    Eleven read-back points fit this to within 0.2% (display
                    rounding). The old mapping here bottomed out at 30 Hz, which
                    put every frequency written through this module roughly an
                    octave low (500 Hz asked -> 266 Hz shown).
    Filter Type A   0..7 = HP48, HP12, Low Shelf, Bell, Notch, High Shelf,
                    LP12, LP48 — all eight read off Live's own display.
    Gain A          raw dB, -15.0 .. +15.0, so gain= is passed straight through.
    Q A             0.0 .. 1.0 normalized (0.5 displays 1.34) — hence q_norm.
"""
from __future__ import annotations
import math

from .params import parse_display, param_with_display, set_by_display


# Filter types — all verified against Live 12's display strings.
EQ8_HP_48 = 0
EQ8_HP_12 = 1
EQ8_LOW_SHELF = 2
EQ8_BELL = 3
EQ8_NOTCH = 4
EQ8_HIGH_SHELF = 5
EQ8_LP_12 = 6
EQ8_LP_48 = 7

# Older names, kept so existing call sites keep working. They were right.
EQ8_LOW_SHELF_GUESS = EQ8_LOW_SHELF
EQ8_HP_12_GUESS = EQ8_HP_12
EQ8_HP_48_GUESS = EQ8_HP_48
EQ8_LP_12_GUESS = EQ8_LP_12
EQ8_LP_48_GUESS = EQ8_LP_48

# The ends of EQ8's frequency curve, as Live displays them at raw 0.0 and 1.0.
EQ8_FREQ_LOW_HZ = 10.0
EQ8_FREQ_HIGH_HZ = 22000.0


def hz_to_norm(hz: float, low_hz: float = EQ8_FREQ_LOW_HZ,
               high_hz: float = EQ8_FREQ_HIGH_HZ) -> float:
    """Hz → EQ8's normalized 0..1 Frequency value (Live's own log curve)."""
    hz = max(low_hz, min(high_hz, hz))
    return math.log(hz / low_hz) / math.log(high_hz / low_hz)


def norm_to_hz(norm: float, low_hz: float = EQ8_FREQ_LOW_HZ,
               high_hz: float = EQ8_FREQ_HIGH_HZ) -> float:
    """The inverse of hz_to_norm — what Live will show for a raw 0..1 value."""
    norm = max(0.0, min(1.0, norm))
    return low_hz * (high_hz / low_hz) ** norm


def set_band_frequency(ch, track_index: int, eq_device_index: int, band: int,
                       hz: float, *, param_index: int | None = None,
                       tolerance: float = 0.02, verify: bool = True,
                       timeout: float = 3.0) -> str | None:
    """Set one band's frequency in Hz and confirm it against what Live DISPLAYS.

    The curve above is the one Live 12 uses, so the first write lands exactly.
    Verification is what keeps it honest: if some other Live version or device
    disagrees by more than `tolerance` (fractional), the raw value is bisected
    against the display until it agrees, so a wrong curve can never again pass
    silently the way the 30 Hz one did. Returns Live's display string.

    Pass param_index when the caller has already read the device info, to save a
    round trip (get_device_info on an EQ8 is ~90 parameters).

    The bisect fallback probes the parameter's extremes first, so it briefly
    sweeps the band to 10 Hz and 22 kHz — inaudible on a disabled band, a short
    sweep on a live one. It does not run on Live 12.
    """
    name = f"{band} Frequency A"
    if param_index is None:
        param_index = param_with_display(ch, track_index, eq_device_index, name)["index"]
    ch.set_device_param(track_index, eq_device_index, param_index,
                        hz_to_norm(hz)).result(timeout=timeout)
    if not verify:
        return None
    shown = param_with_display(ch, track_index, eq_device_index, name)["display"]
    target = max(EQ8_FREQ_LOW_HZ, min(EQ8_FREQ_HIGH_HZ, float(hz)))
    if abs(parse_display(shown) - target) <= tolerance * target:
        return shown
    return set_by_display(ch, track_index, eq_device_index, name, target,
                          timeout=timeout)


def set_eq_band(ch, track_index: int, eq_device_index: int, band: int, *,
                ftype: int, hz: float, gain: float = 0.0, q_norm: float = 0.5,
                on: bool = True, verify: bool = True) -> str | None:
    """Set one EQ8 band — param-name lookup, Hz→raw, and a read-back of the
    frequency against Live's display. Returns that display string.

    ftype takes the EQ8_* constants above (all eight verified). gain is in dB;
    q_norm is 0..1, not a Q value."""
    di = ch.get_device_info(track_index, eq_device_index).result(timeout=5)
    idx = {p["name"]: p["index"] for p in di["parameters"]}
    ch.set_device_param(track_index, eq_device_index, idx[f"{band} Filter On A"],
                         1 if on else 0).result(timeout=3)
    if not on:
        return None
    ch.set_device_param(track_index, eq_device_index, idx[f"{band} Filter Type A"],
                         ftype).result(timeout=3)
    shown = set_band_frequency(ch, track_index, eq_device_index, band, hz,
                               param_index=idx[f"{band} Frequency A"], verify=verify)
    ch.set_device_param(track_index, eq_device_index, idx[f"{band} Gain A"],
                         gain).result(timeout=3)
    # Resonance is named "Q A" on Live 12, "Resonance A" on older versions.
    q_key = next((f"{band} {n} A" for n in ("Q", "Resonance")
                  if f"{band} {n} A" in idx), None)
    if q_key is not None:
        ch.set_device_param(track_index, eq_device_index, idx[q_key],
                             q_norm).result(timeout=3)
    return shown


def disable_all_eq_bands(ch, track_index: int, eq_device_index: int) -> None:
    di = ch.get_device_info(track_index, eq_device_index).result(timeout=5)
    idx = {p["name"]: p["index"] for p in di["parameters"]}
    for b in range(1, 9):
        ch.set_device_param(track_index, eq_device_index, idx[f"{b} Filter On A"],
                             0).result(timeout=3)
