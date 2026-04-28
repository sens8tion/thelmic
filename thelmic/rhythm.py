from __future__ import annotations


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def conformance_for_landscape(position: float) -> float:
    distance_from_chaos = abs(position - 0.5) * 2.0
    return _clamp(distance_from_chaos, 0.0, 1.0)
