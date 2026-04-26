"""Pressure curves — chainable time-varying 0→1 functions.

A PressureCurve spans a fixed number of bars and outputs a value in [0, 1]
at any point through its duration.  Curves chain: when one completes its
next curve (if any) begins immediately, inheriting exact timing.

Two roles
---------
  deformation modulator  — target is a deformation name (e.g. "ghost_inject").
                           The curve value replaces the force-derived intensity
                           that apply_deformations() would otherwise compute.

  MIDI CC output         — target is "cc:<channel>:<cc_number>" (e.g. "cc:0:74").
                           The curve value is sent as a CC message each bar.

Shapes (defined by behaviour of the first differential)
-------------------------------------------------------
  linear        — constant slope; straight ramp
  accelerating  — slow start, fast finish  (ease-in)
  decelerating  — fast start, slow finish  (ease-out)
  sinusoidal    — smooth full cycle (or half-cycle via from/to values)
  step          — holds at from_value until final bar, then jumps to to_value
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional


CURVE_SHAPES = ("linear", "accelerating", "decelerating", "sinusoidal", "step")


@dataclass
class PressureCurve:
    """A single segment of a pressure curve chain.

    Attributes
    ----------
    id          Unique integer assigned by CurveEngine on registration.
    shape       One of CURVE_SHAPES.
    bars        Duration in bars (≥ 1).
    from_value  Value at t=0 (start of curve).
    to_value    Value at t=1 (end of curve).
    target      Deformation name or "cc:<ch>:<cc>" string.
    next_id     ID of the next curve in the chain, or None to stop.
    loop        If True and next_id is None, the curve restarts on completion.
    """
    id:         int
    shape:      str
    bars:       int
    from_value: float
    to_value:   float
    target:     str
    next_id:    Optional[int] = None
    loop:       bool = False


def _shape_t(shape: str, t: float) -> float:
    """Map linear t ∈ [0, 1] through the chosen shape curve."""
    t = max(0.0, min(1.0, t))
    if shape == "linear":
        return t
    elif shape == "accelerating":
        return t * t
    elif shape == "decelerating":
        return 1.0 - (1.0 - t) * (1.0 - t)
    elif shape == "sinusoidal":
        # Full sine cycle: 0 → peak → 0 (use from/to to shift the range)
        return (1.0 - math.cos(math.pi * 2 * t)) / 2.0
    elif shape == "step":
        return 0.0 if t < 1.0 else 1.0
    return t


def evaluate(curve: PressureCurve, bar_progress: float) -> float:
    """Return the curve's output value given bar_progress ∈ [0, 1].

    bar_progress = bars_elapsed / curve.bars
    Output is linearly interpolated between from_value and to_value
    after applying the shape transformation.
    """
    shaped = _shape_t(curve.shape, bar_progress)
    return curve.from_value + (curve.to_value - curve.from_value) * shaped


# ---------------------------------------------------------------------------
# Serialisation helpers for the WebSocket state
# ---------------------------------------------------------------------------

def curve_to_dict(curve: PressureCurve, bars_elapsed: float) -> dict:
    """Serialise a curve + its current progress for the UI."""
    progress = min(1.0, bars_elapsed / max(1, curve.bars))
    return {
        "id":           curve.id,
        "shape":        curve.shape,
        "bars":         curve.bars,
        "from_value":   curve.from_value,
        "to_value":     curve.to_value,
        "target":       curve.target,
        "next_id":      curve.next_id,
        "loop":         curve.loop,
        "progress":     round(progress, 3),
        "current_value": round(evaluate(curve, progress), 3),
        "sparkline":    _sparkline(curve),
    }


def _sparkline(curve: PressureCurve, steps: int = 32) -> list[float]:
    """Return `steps` evenly-spaced values across the curve for UI rendering."""
    return [round(evaluate(curve, i / (steps - 1)), 3) for i in range(steps)]


# ---------------------------------------------------------------------------
# CurveEngine — manages active curves and advances them with the clock
# ---------------------------------------------------------------------------

@dataclass
class _ActiveCurve:
    curve:        PressureCurve
    bars_elapsed: float = 0.0


class CurveEngine:
    """Owns the set of active pressure curves and advances them bar-by-bar.

    Usage
    -----
    engine = CurveEngine()
    curve_id = engine.add(PressureCurve(id=0, shape="linear", bars=8,
                                         from_value=0.0, to_value=1.0,
                                         target="ghost_inject"))
    engine.start(curve_id)

    # Called by playback loop after each bar completes:
    engine.advance(bars=1)

    # Read current intensity for a deformation target:
    val = engine.current_value("ghost_inject")   # None if no active curve for target
    """

    def __init__(self) -> None:
        self._curves:  dict[int, PressureCurve] = {}
        self._active:  dict[str, _ActiveCurve]  = {}   # target → active slot
        self._next_id: int = 1

    # ------------------------------------------------------------------
    # Registration

    def add(self, shape: str, bars: int, from_value: float, to_value: float,
            target: str, next_id: Optional[int] = None, loop: bool = False) -> int:
        """Register a new curve and return its ID.

        Deformation targets are single-slot: a deformer can have at most one
        registered pressure curve. CC targets may still have multiple curves.
        """
        existing_id = self._curve_id_for_deformer(target)
        if existing_id is not None:
            return existing_id

        curve_id = self._next_id
        self._next_id += 1
        self._curves[curve_id] = PressureCurve(
            id=curve_id, shape=shape, bars=bars,
            from_value=from_value, to_value=to_value,
            target=target, next_id=next_id, loop=loop,
        )
        return curve_id

    def _curve_id_for_deformer(self, target: str) -> Optional[int]:
        if target.startswith("cc:"):
            return None
        for curve_id, curve in self._curves.items():
            if curve.target == target:
                return curve_id
        return None

    def remove(self, curve_id: int) -> None:
        self._curves.pop(curve_id, None)
        # Stop active slot if it was running this curve
        for target, slot in list(self._active.items()):
            if slot.curve.id == curve_id:
                del self._active[target]

    def start(self, curve_id: int) -> None:
        """Begin playing a curve from its start, overriding any existing curve
        on the same target."""
        curve = self._curves.get(curve_id)
        if curve:
            self._active[curve.target] = _ActiveCurve(curve=curve)

    def stop(self, target: str) -> None:
        self._active.pop(target, None)

    # ------------------------------------------------------------------
    # Clock advance

    def advance(self, bars: float = 1.0) -> list[tuple[str, int, float]]:
        """Advance all active curves by `bars`.

        Returns a list of (target, cc_number, value) tuples for any CC targets
        that should be sent as MIDI CC messages after this advance step.
        For deformation targets the caller reads current_value() instead.
        """
        cc_outputs: list[tuple[str, int, float]] = []
        completed = []

        for target, slot in self._active.items():
            slot.bars_elapsed += bars
            val = evaluate(slot.curve, min(1.0, slot.bars_elapsed / max(1, slot.curve.bars)))

            if target.startswith("cc:"):
                # "cc:<channel>:<cc_number>"
                parts = target.split(":")
                cc_num = int(parts[2]) if len(parts) > 2 else 0
                cc_outputs.append((target, cc_num, val))

            if slot.bars_elapsed >= slot.curve.bars:
                completed.append((target, slot.curve))

        # Handle completions: chain or loop
        for target, curve in completed:
            if curve.next_id and curve.next_id in self._curves:
                next_curve = self._curves[curve.next_id]
                self._active[target] = _ActiveCurve(curve=next_curve)
            elif curve.loop:
                self._active[target] = _ActiveCurve(curve=curve)
            else:
                del self._active[target]

        return cc_outputs

    # ------------------------------------------------------------------
    # Read

    def current_value(self, target: str) -> Optional[float]:
        """Return the current output value for the given target, or None if
        no curve is active for that target."""
        slot = self._active.get(target)
        if slot is None:
            return None
        t = min(1.0, slot.bars_elapsed / max(1, slot.curve.bars))
        return evaluate(slot.curve, t)

    def overrides(self) -> dict[str, float]:
        """Return {target: value} for all currently active curves."""
        return {
            target: self.current_value(target)
            for target in self._active
        }

    def projected_overrides(self, bars_ahead: float) -> dict[str, float]:
        """Return active curve values projected `bars_ahead` into the future.

        Generation happens ahead of playback at quantized phrase boundaries. Using
        the projected value lets the next generated block contain the deformation
        that will be reached during that block, instead of an empty curve-start
        value of 0.0.
        """
        out: dict[str, float] = {}
        for target, slot in self._active.items():
            t = min(1.0, (slot.bars_elapsed + bars_ahead) / max(1, slot.curve.bars))
            out[target] = evaluate(slot.curve, t)
        return out

    # ------------------------------------------------------------------
    # Serialisation

    def state_dict(self) -> dict:
        """Full state for WebSocket broadcast."""
        all_curves = []
        for curve_id, curve in self._curves.items():
            slot = self._active.get(curve.target)
            bars_elapsed = slot.bars_elapsed if (slot and slot.curve.id == curve_id) else 0.0
            all_curves.append(curve_to_dict(curve, bars_elapsed))
        active_targets = {t: self.current_value(t) for t in self._active}
        return {
            "curves": all_curves,
            "active_targets": {k: round(v, 3) for k, v in active_targets.items()},
        }
