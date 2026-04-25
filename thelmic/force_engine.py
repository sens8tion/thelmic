from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ForceState:
    anticipation: float = 0.0       # pressure building toward an event
    release_pressure: float = 0.0   # accumulated need to resolve
    instability: float = 0.0        # degree of principled corruption active
    density: float = 0.5            # rhythmic and textural fullness
    control_vs_chaos: float = 0.0   # position on Oak–Chaos axis

    def clamp(self) -> "ForceState":
        return ForceState(
            anticipation=_clamp(self.anticipation),
            release_pressure=_clamp(self.release_pressure),
            instability=_clamp(self.instability),
            density=_clamp(self.density),
            control_vs_chaos=_clamp(self.control_vs_chaos),
        )

    def __add__(self, other: "ForceState") -> "ForceState":
        return ForceState(
            anticipation=self.anticipation + other.anticipation,
            release_pressure=self.release_pressure + other.release_pressure,
            instability=self.instability + other.instability,
            density=self.density + other.density,
            control_vs_chaos=self.control_vs_chaos + other.control_vs_chaos,
        )

    def lerp(self, target: "ForceState", t: float) -> "ForceState":
        t = _clamp(t)
        return ForceState(
            anticipation=_lerp(self.anticipation, target.anticipation, t),
            release_pressure=_lerp(self.release_pressure, target.release_pressure, t),
            instability=_lerp(self.instability, target.instability, t),
            density=_lerp(self.density, target.density, t),
            control_vs_chaos=_lerp(self.control_vs_chaos, target.control_vs_chaos, t),
        )


@dataclass
class TransitionEvent:
    from_territory: str       # 'oak' | 'chaos' | 'nott'
    to_territory: str
    axis_position: float
    bank_index: int
    left_unresolved: bool


@dataclass
class BankSnapshot:
    bank_index: int
    force_state: ForceState
    transition: Optional[TransitionEvent]
    completed: bool = True    # False if bank was interrupted


@dataclass
class Trajectory:
    delta_per_bank: ForceState = field(default_factory=ForceState)
    # direction of axis movement; positive = toward Nott
    axis_velocity: float = 0.0


class ForceEngine:
    """Owns force state and trajectory across banks."""

    def __init__(self, landscape_position: float = 0.0) -> None:
        from thelmic.landscape import axis_to_force, territory_at

        self.landscape_position: float = _clamp(landscape_position)
        self._prev_position: float = self.landscape_position
        self.force_state: ForceState = axis_to_force(self.landscape_position)
        self.bank_history: list[BankSnapshot] = []
        self.trajectory: Trajectory = Trajectory()
        self.resolution_likelihood: float = self._calc_resolution_likelihood()
        self._bank_index: int = 0

    # ------------------------------------------------------------------
    # Live input
    # ------------------------------------------------------------------

    def set_landscape_position(self, position: float) -> None:
        from thelmic.landscape import axis_to_force, territory_at

        prev_territory = territory_at(self.landscape_position)
        self._prev_position = self.landscape_position
        self.landscape_position = _clamp(position)
        new_territory = territory_at(self.landscape_position)

        self.trajectory.axis_velocity = self.landscape_position - self._prev_position
        self.force_state = axis_to_force(self.landscape_position)
        self.resolution_likelihood = self._calc_resolution_likelihood()

    # ------------------------------------------------------------------
    # Bank lifecycle
    # ------------------------------------------------------------------

    def begin_bank(self) -> BankSnapshot:
        """Called at the start of each bank generation."""
        from thelmic.landscape import territory_at

        prev_territory = territory_at(self._prev_position)
        curr_territory = territory_at(self.landscape_position)

        transition: Optional[TransitionEvent] = None
        if prev_territory != curr_territory and self._bank_index > 0:
            prev_snapshot = self.bank_history[-1] if self.bank_history else None
            left_unresolved = (
                prev_snapshot is not None
                and prev_snapshot.force_state.release_pressure > 0.4
            )
            transition = TransitionEvent(
                from_territory=prev_territory,
                to_territory=curr_territory,
                axis_position=self.landscape_position,
                bank_index=self._bank_index,
                left_unresolved=left_unresolved,
            )

        snapshot = BankSnapshot(
            bank_index=self._bank_index,
            force_state=ForceState(
                anticipation=self.force_state.anticipation,
                release_pressure=self.force_state.release_pressure,
                instability=self.force_state.instability,
                density=self.force_state.density,
                control_vs_chaos=self.force_state.control_vs_chaos,
            ),
            transition=transition,
            completed=True,
        )
        return snapshot

    def commit_bank(self, snapshot: BankSnapshot) -> None:
        """Record a completed (or interrupted) bank."""
        self._update_trajectory(snapshot)
        self.bank_history.append(snapshot)
        self._bank_index += 1
        self._prev_position = self.landscape_position

    def interrupt_bank(self, snapshot: BankSnapshot, exit_position: float) -> None:
        """Called when a bank is cut short. Records actual exit state."""
        from thelmic.landscape import axis_to_force

        snapshot.completed = False
        # Update force state from actual exit position, not intended destination
        self.landscape_position = _clamp(exit_position)
        self.force_state = axis_to_force(self.landscape_position)
        self.resolution_likelihood = self._calc_resolution_likelihood()
        self.commit_bank(snapshot)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _calc_resolution_likelihood(self) -> float:
        # High release_pressure + low instability → likely to resolve soon
        rp = self.force_state.release_pressure
        inst = self.force_state.instability
        return _clamp(rp * (1.0 - inst * 0.5))

    def _update_trajectory(self, snapshot: BankSnapshot) -> None:
        if not self.bank_history:
            return
        prev = self.bank_history[-1].force_state
        cur = snapshot.force_state
        self.trajectory.delta_per_bank = ForceState(
            anticipation=cur.anticipation - prev.anticipation,
            release_pressure=cur.release_pressure - prev.release_pressure,
            instability=cur.instability - prev.instability,
            density=cur.density - prev.density,
            control_vs_chaos=cur.control_vs_chaos - prev.control_vs_chaos,
        )


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t
