"""Intent layer — translates axis input into transition targets or direct position.

When playing:
    set_axis() / set_axis_from_cc() call TransitionEngine.set_target().
    The engine performs the journey over musical time bar-by-bar.

When stopped:
    set_axis_immediate() sets landscape_position directly on ForceEngine.
    No transition is created — the performer is previewing positions.

This separation keeps intent (destination) cleanly distinct from
execution (time-based advancement), per the architecture plan.
"""

from __future__ import annotations

from thelmic.force_engine import ForceEngine
from thelmic.transition_engine import TransitionEngine


class IntentInput:
    """Accepts axis position and routes it to the correct engine path."""

    def __init__(self, engine: ForceEngine, transition_engine: TransitionEngine) -> None:
        self._engine = engine
        self._transition_engine = transition_engine

    def set_axis_from_cc(self, cc_value: int) -> None:
        """Set target from a MIDI CC value (0–127 → 0.0–1.0)."""
        position = max(0, min(127, cc_value)) / 127.0
        self._transition_engine.set_target(position)

    def set_axis(self, position: float) -> None:
        """Set transition target (use when playing)."""
        self._transition_engine.set_target(position)

    def set_axis_immediate(self, position: float) -> None:
        """Set landscape position directly, bypassing transition (use when stopped)."""
        self._transition_engine.cancel()
        self._engine.set_landscape_position(position)
