"""Transition engine — intent vector and traversal state.

A Transition represents the performer's current intent: a journey from
one landscape position to another over a fixed number of bars.

Dependency direction:
    TransitionEngine → ForceEngine → Deformations

Transition state is traversal/intent — it does not belong in ForceEngine
(which owns force/landscape state).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

from thelmic.force_engine import ForceEngine, _clamp


DEFAULT_TRANSITION_BARS: float = 8.0
_COMPLETION_THRESHOLD: float = 0.005   # snap-to-complete within this distance


@dataclass
class Transition:
    """Active journey from start_position to target_position.

    All positions are normalised to [0.0, 1.0] on the Oak → Nott axis.
    """
    start_position:   float
    target_position:  float
    current_position: float
    duration_bars:    float
    elapsed_bars:     float = 0.0
    active:           bool  = True

    # ------------------------------------------------------------------
    # Derived values
    # ------------------------------------------------------------------

    @property
    def progress(self) -> float:
        """0.0 at journey start, 1.0 at completion."""
        if self.duration_bars <= 0:
            return 1.0
        return _clamp(self.elapsed_bars / self.duration_bars)

    @property
    def remaining(self) -> float:
        """Remaining distance as a fraction of the full span (0.0 = arrived)."""
        span = abs(self.target_position - self.start_position)
        if span < 1e-6:
            return 0.0
        return _clamp(abs(self.target_position - self.current_position) / span)

    @property
    def direction(self) -> str:
        """'toward_nott' | 'toward_oak' | 'none'"""
        delta = self.target_position - self.current_position
        if abs(delta) < 1e-4:
            return "none"
        return "toward_nott" if delta > 0 else "toward_oak"

    @property
    def velocity(self) -> float:
        """Normalised rate: total-distance / duration_bars, clamped [0, 1]."""
        if self.duration_bars <= 0:
            return 0.0
        return _clamp(abs(self.target_position - self.start_position) / self.duration_bars)


class TransitionEngine:
    """Owns the active Transition and advances landscape position over time.

    Separation of concerns
    ----------------------
    set_target()  — called by the UI/intent layer when the performer
                    chooses a destination; creates or retargets a Transition
    advance()     — called by the playback loop once per bar; steps
                    current_position toward target and pushes the result
                    into ForceEngine.set_landscape_position()

    When not playing, the slider sets the position directly via
    ForceEngine.set_landscape_position() — no advance_fractional() call.
    This keeps intent (target-setting) cleanly separated from execution
    (time-based advancement).
    """

    def __init__(
        self,
        force_engine: ForceEngine,
        default_duration_bars: float = DEFAULT_TRANSITION_BARS,
    ) -> None:
        self._engine = force_engine
        self._default_duration_bars = default_duration_bars
        self._transition: Optional[Transition] = None

    # ------------------------------------------------------------------
    # Input
    # ------------------------------------------------------------------

    def set_target(self, target_position: float, duration_bars: Optional[float] = None) -> None:
        """Set a new destination.

        If no transition is active, creates one from current landscape position.
        If one is already active, retargets from current_position (fresh journey
        from wherever the system currently is, not from the original start).
        """
        target_position = _clamp(target_position)
        duration = duration_bars if duration_bars is not None else self._default_duration_bars
        current = self._engine.landscape_position

        if abs(target_position - current) < _COMPLETION_THRESHOLD:
            # Already there — clear any active transition and do nothing
            self._transition = None
            return

        self._transition = Transition(
            start_position=current,
            target_position=target_position,
            current_position=current,
            duration_bars=duration,
            elapsed_bars=0.0,
            active=True,
        )

    def cancel(self) -> None:
        """Cancel the active transition and stop at current position."""
        self._transition = None

    # ------------------------------------------------------------------
    # Clock advance — called from the playback loop
    # ------------------------------------------------------------------

    def advance(self, bars: float = 1.0) -> None:
        """Advance by `bars` and update ForceEngine.

        Linear interpolation from start → target over duration_bars.
        Marks the transition inactive and snaps to target on completion.
        """
        if self._transition is None or not self._transition.active:
            return

        t = self._transition
        t.elapsed_bars += bars

        frac = _clamp(t.elapsed_bars / max(1.0, t.duration_bars))
        new_pos = t.start_position + (t.target_position - t.start_position) * frac
        t.current_position = new_pos
        self._engine.set_landscape_position(new_pos)

        if abs(new_pos - t.target_position) <= _COMPLETION_THRESHOLD or frac >= 1.0:
            t.current_position = t.target_position
            t.active = False
            self._engine.set_landscape_position(t.target_position)

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    @property
    def transition(self) -> Optional[Transition]:
        return self._transition

    @property
    def is_active(self) -> bool:
        return self._transition is not None and self._transition.active

    def state_dict(self) -> dict:
        """Serialised transition state for WebSocket broadcast.

        Always included in the state push so the UI can display transition
        progress and direction without polling.
        """
        current = self._engine.landscape_position
        if self._transition is None:
            return {
                "active":           False,
                "start_position":   None,
                "current_position": round(current, 3),
                "target_position":  None,
                "progress":         0.0,
                "remaining":        0.0,
                "direction":        "none",
                "velocity":         0.0,
                "duration_bars":    self._default_duration_bars,
                "elapsed_bars":     0.0,
            }
        t = self._transition
        return {
            "active":           t.active,
            "start_position":   round(t.start_position, 3),
            "current_position": round(t.current_position, 3),
            "target_position":  round(t.target_position, 3),
            "progress":         round(t.progress, 3),
            "remaining":        round(t.remaining, 3),
            "direction":        t.direction,
            "velocity":         round(t.velocity, 3),
            "duration_bars":    t.duration_bars,
            "elapsed_bars":     round(t.elapsed_bars, 2),
        }
