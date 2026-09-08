"""Tests for the range-aware param primitive (thelmic.bridge.helpers.set_param).

The whole point of the primitive: the device's real range is read first, so a
value is never written on a guessed scale. These tests pin that contract with a
fake channel (no Live required).
"""
import pytest
from thelmic.bridge.helpers import set_param, describe_param, safe_set_param


class _Imm:
    """Minimal stand-in for a concurrent.futures.Future."""
    def __init__(self, val): self._val = val
    def result(self, timeout=None): return self._val


class FakeChannel:
    """Mimics the bits of LiveChannel that set_param touches."""
    def __init__(self, params):
        # params: list of dicts with name/index/value/min/max/is_quantized
        self._params = params
        self.writes = []  # (index, value)

    def get_device_info(self, t, d):
        return _Imm({"class_name": "FakeDev", "parameters": self._params})

    def set_device_param(self, t, d, idx, val):
        self.writes.append((idx, val))
        # reflect into state so re-reads see it
        for p in self._params:
            if p["index"] == idx:
                p["value"] = val
        return _Imm({"ok": True})


def _dev():
    return FakeChannel([
        {"name": "OD Drive", "index": 0, "value": 0.0, "min": 0.0, "max": 100.0, "is_quantized": False},
        {"name": "Sat Drive", "index": 1, "value": 0.0, "min": 0.0, "max": 1.0, "is_quantized": False},
        {"name": "Type", "index": 2, "value": 0.0, "min": 0.0, "max": 7.0, "is_quantized": True},
        {"name": "Gain", "index": 3, "value": 0.0, "min": -15.0, "max": 15.0, "is_quantized": False},
    ])


def test_frac_is_scale_independent():
    ch = _dev()
    # 70% of a 0..100 param -> 70.0
    r = set_param(ch, 0, 0, "OD Drive", frac=0.70)
    assert ch.writes[-1] == (0, 70.0)
    assert r["set"] == 70.0 and abs(r["frac"] - 0.70) < 1e-9
    # 70% of a 0..1 param -> 0.70, SAME intent, different scale
    r = set_param(ch, 0, 0, "Sat Drive", frac=0.70)
    assert ch.writes[-1] == (1, 0.70)


def test_frac_clamped_to_unit():
    ch = _dev()
    set_param(ch, 0, 0, "OD Drive", frac=2.5)   # >1 -> clamp to 1.0 -> max
    assert ch.writes[-1] == (0, 100.0)


def test_value_with_correct_expect_writes():
    ch = _dev()
    set_param(ch, 0, 0, "OD Drive", value=70.0, expect=(0.0, 100.0))
    assert ch.writes[-1] == (0, 70.0)


def test_value_with_wrong_expect_raises():
    ch = _dev()
    # caller thinks OD Drive is 0..1 but it's 0..100 -> the bug we keep hitting
    with pytest.raises(ValueError, match="wrong scale"):
        set_param(ch, 0, 0, "OD Drive", value=0.55, expect=(0.0, 1.0))
    assert ch.writes == []  # nothing written on a guarded mismatch


def test_value_out_of_range_clamps():
    ch = _dev()
    set_param(ch, 0, 0, "Sat Drive", value=5.0)   # 0..1 param
    assert ch.writes[-1] == (1, 1.0)


def test_quantized_rounds_to_step():
    ch = _dev()
    # 0.86 * 7 = 6.02 -> rounds to 6 (Digital Clip)
    r = set_param(ch, 0, 0, "Type", frac=0.86)
    assert ch.writes[-1] == (2, 6.0) and r["set"] == 6.0


def test_unknown_param_raises_with_options():
    ch = _dev()
    with pytest.raises(ValueError, match="not on FakeDev"):
        set_param(ch, 0, 0, "Nonexistent", value=1.0)


def test_exactly_one_of_value_or_frac():
    ch = _dev()
    with pytest.raises(ValueError, match="exactly one"):
        set_param(ch, 0, 0, "Gain", value=3.0, frac=0.5)
    with pytest.raises(ValueError, match="exactly one"):
        set_param(ch, 0, 0, "Gain")


def test_describe_param_reports_range():
    ch = _dev()
    info = describe_param(ch, 0, 0, "OD Drive")
    assert (info["min"], info["max"], info["quantized"]) == (0.0, 100.0, False)


def test_safe_set_param_still_clamps():
    ch = _dev()
    safe_set_param(ch, 0, 0, "Sat Drive", 9.0)   # back-compat shim -> clamp
    assert ch.writes[-1] == (1, 1.0)
