"""Intent layer — stub for Phase 1. Axis position only."""

from __future__ import annotations

from thelmic.force_engine import ForceEngine


class IntentInput:
    """Accepts axis position from a MIDI CC knob (0–127 → 0.0–1.0)."""

    def __init__(self, engine: ForceEngine) -> None:
        self._engine = engine

    def set_axis_from_cc(self, cc_value: int) -> None:
        position = max(0, min(127, cc_value)) / 127.0
        self._engine.set_landscape_position(position)

    def set_axis(self, position: float) -> None:
        self._engine.set_landscape_position(position)
