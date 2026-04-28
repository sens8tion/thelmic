"""Phase 11 — slider dynamics, trajectory, priority, and sparsity.

This module is intentionally small and post-planner. It does not author phrase
syntax and does not alter Phase 10 drop commit semantics.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum

from thelmic.bank_generator import Bank, MIDIEvent
from thelmic.force_engine import _clamp
from thelmic.phrase_plan import PhrasePlan, PhraseState
from thelmic.syntax_enforcer import time_to_bar_step, _plan_bar


INSTRUMENT_PRIORITY: tuple[str, ...] = (
    "kick", "bass", "snare", "hook", "stab", "hat", "ghost", "survivor",
)
PRIORITY_INDEX: dict[str, int] = {
    layer: index for index, layer in enumerate(INSTRUMENT_PRIORITY)
}
CORE_DROP_LAYERS: frozenset[str] = frozenset({"kick", "bass"})


class SparsityMode(str, Enum):
    SOFT = "soft"
    HARD = "hard"
    PULSED = "pulsed"
    DOMINANT_BURST = "dominant_burst"


@dataclass
class SliderDynamics:
    target_position: float = 0.0
    actual_position: float = 0.0
    velocity: float = 0.0
    phase: float = 0.0
    stiffness: float = 0.18
    damping: float = 0.72
    last_target_position: float = 0.0
    gesture_velocity: float = 0.0
    reversal_instability: float = 0.0

    def set_target(self, position: float) -> None:
        position = _clamp(position)
        delta = position - self.target_position
        if delta * self.gesture_velocity < 0:
            self.reversal_instability = min(1.0, self.reversal_instability + abs(delta) * 2.0)
        self.last_target_position = self.target_position
        self.target_position = position
        self.gesture_velocity = delta

    def set_immediate(self, position: float) -> None:
        position = _clamp(position)
        self.target_position = position
        self.actual_position = position
        self.velocity = 0.0
        self.gesture_velocity = 0.0
        self.reversal_instability = 0.0

    def advance(self, bars: float = 1.0) -> float:
        bars = max(0.0, bars)
        self.phase += bars
        self.reversal_instability *= 0.86 ** bars

        accel = (self.target_position - self.actual_position) * self.stiffness * bars
        self.velocity = (self.velocity + accel) * (self.damping ** bars)
        self.actual_position = _clamp(self.actual_position + self.velocity)
        if self.actual_position in {0.0, 1.0}:
            self.velocity *= 0.25
        return self.actual_position

    def internal_motion(self) -> dict[str, float]:
        basin = constraint_basin(self.actual_position)
        # Bounded periodic motion: changes continue, but remain centred on the
        # current position basin rather than walking into another territory.
        fast = math.sin(self.phase * math.tau) * 0.5 + 0.5
        medium = math.sin(self.phase * math.tau / 4.0 + 0.7) * 0.5 + 0.5
        slow = math.sin(self.phase * math.tau / 16.0 + 1.3) * 0.5 + 0.5
        return {
            "micro_variation": round(fast * basin["variation"], 3),
            "phrase_evolution": round(medium * basin["variation"], 3),
            "energy_breathing": round(slow * basin["energy"], 3),
            "constraint_basin_min": round(basin["min"], 3),
            "constraint_basin_max": round(basin["max"], 3),
        }

    def to_dict(self) -> dict:
        return {
            "target_position": round(self.target_position, 3),
            "actual_position": round(self.actual_position, 3),
            "slider_velocity": round(self.velocity, 3),
            "gesture_velocity": round(self.gesture_velocity, 3),
            "reversal_instability": round(self.reversal_instability, 3),
            **self.internal_motion(),
        }


def constraint_basin(position: float) -> dict[str, float]:
    position = _clamp(position)
    if position < 0.33:
        centre, width = 0.165, 0.33
    elif position < 0.67:
        centre, width = 0.5, 0.34
    else:
        centre, width = 0.835, 0.33
    distance = abs(position - centre) / max(width / 2.0, 1e-6)
    stability = _clamp(1.0 - distance)
    return {
        "min": max(0.0, centre - width / 2.0),
        "max": min(1.0, centre + width / 2.0),
        "variation": 0.04 + (1.0 - stability) * 0.04,
        "energy": 0.08 + (1.0 - stability) * 0.08,
    }


@dataclass
class TrajectoryPlan:
    start_position: float = 0.0
    end_position: float = 0.0
    distance: float = 0.0
    velocity: float = 0.0
    duration: float = 0.0
    drop_plan: list[dict[str, str]] = field(default_factory=list)
    current_drop_index: int = 0
    active: bool = False

    @property
    def drop_role(self) -> str | None:
        if not self.drop_plan:
            return None
        index = min(self.current_drop_index, len(self.drop_plan) - 1)
        return self.drop_plan[index]["role"]

    def to_dict(self) -> dict:
        return {
            "trajectory_active": self.active,
            "trajectory_distance": round(self.distance, 3),
            "trajectory_velocity": round(self.velocity, 3),
            "trajectory_duration": round(self.duration, 3),
            "drop_plan": list(self.drop_plan),
            "current_drop_index": self.current_drop_index,
            "drop_role": self.drop_role,
        }


def plan_trajectory(start: float, end: float, velocity: float, duration: float) -> TrajectoryPlan:
    distance = abs(end - start)
    roles = ["transition"]
    if distance > 0.18:
        roles.append("intensify")
    if distance > 0.38 or abs(velocity) > 0.25:
        roles.append("peak")
    if distance > 0.08:
        roles.append("resolve")
    return TrajectoryPlan(
        start_position=_clamp(start),
        end_position=_clamp(end),
        distance=distance,
        velocity=abs(velocity),
        duration=max(0.0, duration),
        drop_plan=[{"role": role} for role in roles],
        current_drop_index=0,
        active=distance > 0.005,
    )


@dataclass
class Phase11State:
    slider: SliderDynamics = field(default_factory=SliderDynamics)
    trajectory: TrajectoryPlan = field(default_factory=TrajectoryPlan)
    dominant_instrument: str | None = None
    sparsity_level: float = 0.0
    sparsity_mode: SparsityMode = SparsityMode.SOFT

    def set_target(self, position: float) -> None:
        start = self.slider.actual_position
        previous_target = self.slider.target_position
        self.slider.set_target(position)
        distance = abs(position - previous_target)
        gesture_velocity = self.slider.gesture_velocity
        duration = max(1.0, 12.0 * (1.0 - min(0.8, abs(gesture_velocity))))
        self.trajectory = plan_trajectory(start, position, gesture_velocity, duration)
        self._update_arrangement_state()

    def set_immediate(self, position: float) -> None:
        self.slider.set_immediate(position)
        self.trajectory = plan_trajectory(position, position, 0.0, 0.0)
        self._update_arrangement_state()

    def advance(self, bars: float = 1.0) -> float:
        actual = self.slider.advance(bars)
        self._update_arrangement_state()
        return actual

    def mark_drop_committed(self) -> None:
        if self.trajectory.drop_plan:
            self.trajectory.current_drop_index = min(
                self.trajectory.current_drop_index + 1,
                len(self.trajectory.drop_plan) - 1,
            )
            if self.trajectory.current_drop_index >= len(self.trajectory.drop_plan) - 1:
                self.trajectory.active = False
        self._update_arrangement_state()

    def _update_arrangement_state(self) -> None:
        role = self.trajectory.drop_role
        distance = self.trajectory.distance
        energy = self.slider.internal_motion()["energy_breathing"]
        if role == "peak":
            self.dominant_instrument = "bass"
            self.sparsity_mode = SparsityMode.HARD
            self.sparsity_level = _clamp(0.55 + distance * 0.7)
        elif role == "intensify":
            self.dominant_instrument = "snare"
            self.sparsity_mode = SparsityMode.PULSED
            self.sparsity_level = _clamp(0.25 + energy * 0.6)
        elif role == "resolve":
            self.dominant_instrument = "hook"
            self.sparsity_mode = SparsityMode.DOMINANT_BURST
            self.sparsity_level = _clamp(0.25 + distance * 0.3)
        else:
            self.dominant_instrument = None
            self.sparsity_mode = SparsityMode.SOFT
            self.sparsity_level = _clamp(0.10 + energy * 0.25)

    def to_dict(self) -> dict:
        return {
            **self.slider.to_dict(),
            **self.trajectory.to_dict(),
            "dominant_instrument": self.dominant_instrument,
            "sparsity_mode": self.sparsity_mode.value,
            "sparsity_level": round(self.sparsity_level, 3),
        }


@dataclass
class PriorityStats:
    priority_conflicts_resolved: int = 0
    events_suppressed_by_sparsity: int = 0
    events_shifted_by_priority: int = 0

    def to_dict(self) -> dict[str, int]:
        return {
            "priority_conflicts_resolved": self.priority_conflicts_resolved,
            "events_suppressed_by_sparsity": self.events_suppressed_by_sparsity,
            "events_shifted_by_priority": self.events_shifted_by_priority,
        }


def _priority(layer: str) -> int:
    return PRIORITY_INDEX.get(layer, len(INSTRUMENT_PRIORITY))


def _is_drop_core(event: MIDIEvent, plan: PhrasePlan, plan_bars: int) -> bool:
    bar, _ = time_to_bar_step(event.time)
    pbar = _plan_bar(bar, plan_bars)
    return (
        plan.phrase_state.get(pbar) == PhraseState.DROP_RELOCK
        and event.layer in CORE_DROP_LAYERS
    )


def _sparsity_allows(event: MIDIEvent, state: Phase11State, plan: PhrasePlan, plan_bars: int) -> bool:
    if getattr(event, "survives_silence", False) or event.role == "survivor":
        return True
    if _is_drop_core(event, plan, plan_bars):
        return True
    dominant = state.dominant_instrument
    if dominant is None or event.layer == dominant:
        return True
    if event.layer in CORE_DROP_LAYERS:
        return True
    level = state.sparsity_level
    bar, step = time_to_bar_step(event.time)
    if step < 0:
        return True
    if state.sparsity_mode == SparsityMode.HARD:
        return _priority(event.layer) <= 3 or step in {0, 8}
    if state.sparsity_mode == SparsityMode.DOMINANT_BURST:
        return _priority(event.layer) <= 4 and step in {0, 4, 8, 12}
    if state.sparsity_mode == SparsityMode.PULSED:
        return ((bar + step // 4) % 2 == 0) or _priority(event.layer) <= 2
    return not (_priority(event.layer) > 4 and level > 0.25 and step % 2 == 1)


def enforce_priority_and_sparsity(
    bank: Bank, plan: PhrasePlan, state: Phase11State,
) -> dict[str, int]:
    stats = PriorityStats()
    plan_bars = max([1, *plan.phrase_state.keys(), *plan.silence_mask.muted_steps_by_bar.keys()])
    for phrase in bank.phrases:
        by_step: dict[tuple[int, int], MIDIEvent] = {}
        kept: list[MIDIEvent] = []
        for event in sorted(phrase.events, key=lambda e: (_priority(e.layer), e.time)):
            if not _sparsity_allows(event, state, plan, plan_bars):
                stats.events_suppressed_by_sparsity += 1
                continue
            bar, step = time_to_bar_step(event.time)
            key = (bar, step)
            winner = by_step.get(key)
            if winner is not None and _priority(event.layer) > _priority(winner.layer):
                if event.layer not in CORE_DROP_LAYERS and not getattr(event, "survives_silence", False):
                    stats.priority_conflicts_resolved += 1
                    continue
            by_step.setdefault(key, event)
            kept.append(event)
        phrase.events = kept
    return stats.to_dict()
