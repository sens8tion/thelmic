"""Tests for EQ Eight's Hz ↔ raw mapping (thelmic.bridge.helpers.eq).

The bug these pin: the helper used to map Hz onto a curve that bottomed out at
30 Hz, while Live's own curve bottoms out at 10 Hz. Everything written through it
landed roughly an octave low (500 Hz asked, 266 Hz shown) — silently, because
nothing read back what Live displayed.

The DISPLAY_CURVE below is Live 12.4.6's, measured over the bridge on 2026-09-16
by writing raw values to a disabled band and reading the display string back.
The MEASURED pairs are raw/display readings taken straight off that session.
"""
import math

import pytest

from thelmic.bridge.helpers import (
    hz_to_norm, norm_to_hz, set_band_frequency, set_eq_band, parse_display,
    EQ8_FREQ_LOW_HZ, EQ8_FREQ_HIGH_HZ,
    EQ8_HP_48, EQ8_HP_12, EQ8_LOW_SHELF, EQ8_BELL,
    EQ8_NOTCH, EQ8_HIGH_SHELF, EQ8_LP_12, EQ8_LP_48,
)

# (raw value, what Live displayed) — read off the jungle set's EQ Eights.
MEASURED = [
    (0.0436040461063385, 14.0), (0.14274713397026062, 30.0),
    (0.16651694476604462, 36.0), (0.24394291639328003, 65.4),
    (0.2991841733455658, 100.0), (0.3490034341812134, 147.0),
    (0.44171905517578125, 300.0), (0.5983683466911316, 1000.0),
    (0.8074891567230225, 5000.0), (0.8975525498390198, 10000.0),
    (0.9739260673522949, 18000.0),
]


def display_curve(raw):
    """Live's own Frequency display, as a number of Hz."""
    return 10.0 * 2200.0 ** raw


class _Imm:
    def __init__(self, val): self._val = val
    def result(self, timeout=None): return self._val


class FakeEq8:
    """An EQ Eight band whose display follows `curve` (Live's, unless overridden)."""

    def __init__(self, curve=display_curve):
        self._curve = curve
        self._raw = {}          # index -> raw value
        self.writes = []

    def _entry(self, i, name):
        raw = self._raw.get(i, 0.0)
        e = {"name": name, "index": i, "value": raw, "min": 0.0, "max": 1.0,
             "is_quantized": False}
        if "Frequency" in name:
            e["display"] = f"{self._curve(raw):.6g} Hz"
        elif "Filter On" in name:
            e["display"] = "On" if raw else "Off"
        else:
            e["display"] = f"{raw:.2f}"
        return e

    def get_device_info(self, t, d):
        names = [f"1 {n} A" for n in ("Filter On", "Filter Type", "Frequency", "Gain", "Q")]
        return _Imm({"class_name": "Eq8",
                     "parameters": [self._entry(i, n) for i, n in enumerate(names)]})

    def set_device_param(self, t, d, idx, val):
        self._raw[idx] = val
        self.writes.append((idx, val))
        return _Imm({"ok": True})


@pytest.mark.parametrize("raw,shown", MEASURED)
def test_curve_matches_what_live_displays(raw, shown):
    """norm_to_hz reproduces every measured read-back to within display rounding."""
    assert norm_to_hz(raw) == pytest.approx(shown, rel=0.002)


@pytest.mark.parametrize("raw,shown", MEASURED)
def test_hz_to_norm_is_the_inverse(raw, shown):
    """Live displays 3 significant figures ("147 Hz" is really 146.7), so a raw
    value recovered from a display string is only good to ~0.35% in Hz, which is
    ln(1.0035)/ln(2200) ≈ 4.5e-4 in raw. Anything looser would hide a real error:
    the old 30 Hz curve was out by 0.1 raw, two hundred times this."""
    assert hz_to_norm(shown) == pytest.approx(raw, abs=6e-4)


def test_endpoints_are_lives_own():
    """raw 0.0 displays 10.0 Hz and raw 1.0 displays 22.0 kHz — both measured."""
    assert norm_to_hz(0.0) == pytest.approx(EQ8_FREQ_LOW_HZ)
    assert norm_to_hz(1.0) == pytest.approx(EQ8_FREQ_HIGH_HZ)
    assert hz_to_norm(EQ8_FREQ_LOW_HZ) == 0.0
    assert hz_to_norm(EQ8_FREQ_HIGH_HZ) == 1.0


def test_out_of_range_clamps_to_the_curve():
    assert hz_to_norm(1.0) == 0.0
    assert hz_to_norm(50000.0) == 1.0


def test_the_old_30hz_curve_stays_dead():
    """The regression itself: 500 Hz must not land near 266 Hz again."""
    old = math.log(500.0 / 30.0) / math.log(22000.0 / 30.0)
    assert display_curve(old) == pytest.approx(266.0, rel=0.01)   # what the bug did
    assert norm_to_hz(hz_to_norm(500.0)) == pytest.approx(500.0, rel=0.002)


@pytest.mark.parametrize("hz", [20, 40, 90, 120, 150, 200, 300, 500, 1000, 5000, 18000])
def test_set_band_frequency_lands_on_target(hz):
    ch = FakeEq8()
    shown = set_band_frequency(ch, 0, 0, 1, hz)
    assert parse_display(shown) == pytest.approx(hz, rel=0.002)


def test_set_band_frequency_bisects_when_the_curve_is_wrong():
    """A device whose curve differs (an older Live, say) is corrected, not trusted."""
    ch = FakeEq8(curve=lambda raw: 20.0 * 1000.0 ** raw)
    shown = set_band_frequency(ch, 0, 0, 1, 500.0)
    assert parse_display(shown) == pytest.approx(500.0, rel=0.01)
    assert len(ch.writes) > 1          # it did not accept the first write


def test_set_eq_band_writes_every_part_of_the_band():
    ch = FakeEq8()
    shown = set_eq_band(ch, 0, 0, 1, ftype=EQ8_BELL, hz=300.0, gain=-3.0, q_norm=0.4)
    assert parse_display(shown) == pytest.approx(300.0, rel=0.002)
    written = dict(ch.writes)
    assert written[0] == 1                                  # Filter On
    assert written[1] == EQ8_BELL                           # Filter Type
    assert written[2] == pytest.approx(hz_to_norm(300.0))   # Frequency
    assert written[3] == -3.0                               # Gain, in dB
    assert written[4] == 0.4                                # Q, normalized


def test_set_eq_band_off_touches_nothing_else():
    ch = FakeEq8()
    assert set_eq_band(ch, 0, 0, 1, ftype=EQ8_BELL, hz=300.0, on=False) is None
    assert ch.writes == [(0, 0)]


def test_filter_type_constants_are_lives_order():
    """All eight read off Live's display on a disabled band, 2026-09-16."""
    assert [EQ8_HP_48, EQ8_HP_12, EQ8_LOW_SHELF, EQ8_BELL,
            EQ8_NOTCH, EQ8_HIGH_SHELF, EQ8_LP_12, EQ8_LP_48] == list(range(8))


@pytest.mark.parametrize("text,want", [
    ("120 Hz", 120.0), ("5.00 kHz", 5000.0), ("10.0 Hz", 10.0),
    ("-15.0 dB", -15.0), ("4.00 : 1", 4.0), ("1.00 ms", 1.0), ("1.20 s", 1200.0),
    ("inf", math.inf), ("-inf", -math.inf),
])
def test_parse_display_units(text, want):
    assert parse_display(text) == want
