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
    "kick", "sub", "bassline", "bass", "snare", "hook", "stab", "hat", "ghost", "survivor",
)
PRIORITY_INDEX: dict[str, int] = {
    layer: index for index, layer in enumerate(INSTRUMENT_PRIORITY)
}
CORE_DROP_LAYERS: frozenset[str] = frozenset({"kick", "sub", "bassline"})
BEAT_BED_LAYERS: frozenset[str] = frozenset({"kick", "snare", "hat"})
IDENTITY_LAYERS: frozenset[str] = frozenset({"hook"})
COEXISTENT_FOUNDATION_LAYERS: frozenset[str] = frozenset(
    {"kick", "sub", "bassline", "bass", "snare", "hat"}
)
ALLOWED_PROGRESSIVE_STEP_DELTA: float = 0.2
CALL_RESPONSE_LEADERS: tuple[str, ...] = ("stab", "bass", "hook", "snare")


class SparsityMode(str, Enum):
    SOFT = "soft"
    HARD = "hard"
    PULSED = "pulsed"
    DOMINANT_BURST = "dominant_burst"


@dataclass(frozen=True)
class StructuralChange:
    mutation_type: str
    step: int
    nearest_drop_step: int
    change_magnitude: float
    change_mode: str
    is_continuous: bool = True


def can_apply_instant_structural_change(step: int, drop_step: int) -> bool:
    return step == drop_step


def can_apply_progressive_structural_change(
    change: StructuralChange,
    allowed_step_delta: float = ALLOWED_PROGRESSIVE_STEP_DELTA,
) -> bool:
    return change.is_continuous and change.change_magnitude <= allowed_step_delta


def evaluate_structural_change(change: StructuralChange) -> dict:
    if change.change_mode == "instantaneous":
        allowed = can_apply_instant_structural_change(change.step, change.nearest_drop_step)
        reason = "drop_step" if allowed else "instantaneous_change_requires_drop"
    else:
        allowed = can_apply_progressive_structural_change(change)
        reason = "continuous_delta_within_basin" if allowed else "progressive_delta_too_large"
    return {
        "mutation_type": change.mutation_type,
        "step": change.step,
        "nearest_drop_step": change.nearest_drop_step,
        "change_magnitude": round(change.change_magnitude, 3),
        "change_mode": change.change_mode,
        "allowed": allowed,
        "reason": reason,
    }


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
    structural_mutations: list[dict] = field(default_factory=list)
    call_response_leader: str = "stab"
    pending_call_response_leader: str = "stab"
    leader_committed_at_drop: bool = False
    build_length_bars: int = 8
    silence_length_bars: int = 1

    def set_target(self, position: float) -> None:
        start = self.slider.actual_position
        previous_target = self.slider.target_position
        self.slider.set_target(position)
        distance = abs(position - previous_target)
        gesture_velocity = self.slider.gesture_velocity
        duration = max(1.0, 12.0 * (1.0 - min(0.8, abs(gesture_velocity))))
        self.trajectory = plan_trajectory(start, position, gesture_velocity, duration)
        self._update_arrangement_state()
        self._prepare_pending_call_response_leader()

    def set_immediate(self, position: float) -> None:
        self.slider.set_immediate(position)
        self.trajectory = plan_trajectory(position, position, 0.0, 0.0)
        self._update_arrangement_state()
        self._prepare_pending_call_response_leader()

    def advance(self, bars: float = 1.0) -> float:
        actual = self.slider.advance(bars)
        motion = self.slider.internal_motion()
        self._record_structural_change(
            StructuralChange(
                mutation_type="bounded_internal_motion",
                step=-1,
                nearest_drop_step=-1,
                change_magnitude=max(
                    motion["micro_variation"],
                    motion["phrase_evolution"],
                    motion["energy_breathing"],
                ),
                change_mode="progressive",
                is_continuous=True,
            )
        )
        self._update_arrangement_state()
        return actual

    def mark_drop_committed(self) -> None:
        self._record_structural_change(
            StructuralChange(
                mutation_type="drop_role_advancement",
                step=4,
                nearest_drop_step=4,
                change_magnitude=1.0,
                change_mode="instantaneous",
                is_continuous=False,
            )
        )
        if self.trajectory.drop_plan:
            self.trajectory.current_drop_index = min(
                self.trajectory.current_drop_index + 1,
                len(self.trajectory.drop_plan) - 1,
            )
            if self.trajectory.current_drop_index >= len(self.trajectory.drop_plan) - 1:
                self.trajectory.active = False
        self.call_response_leader = self.pending_call_response_leader
        self.leader_committed_at_drop = True
        self._prepare_pending_call_response_leader()
        self._update_arrangement_state()

    def _prepare_pending_call_response_leader(self) -> None:
        """Pick the next structural call/response leader.

        Stab is intentionally dominant. The non-stab branch is deterministic
        and rare so tests and playback remain repeatable while approximating
        the requested 90/10 section split.
        """
        seed = int(self.slider.target_position * 1000)
        seed += int(self.trajectory.distance * 1000)
        seed += int(self.trajectory.velocity * 1000)
        seed += self.trajectory.current_drop_index * 17
        if seed % 10 != 0:
            self.pending_call_response_leader = "stab"
            return
        alternatives = CALL_RESPONSE_LEADERS[1:]
        self.pending_call_response_leader = alternatives[(seed // 10) % len(alternatives)]

    def _record_structural_change(self, change: StructuralChange) -> dict:
        entry = evaluate_structural_change(change)
        self.structural_mutations.append(entry)
        self.structural_mutations = self.structural_mutations[-16:]
        return entry

    def _update_arrangement_state(self) -> None:
        role = self.trajectory.drop_role
        distance = self.trajectory.distance
        energy = self.slider.internal_motion()["energy_breathing"]
        if role == "peak":
            self.dominant_instrument = "bassline"
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
        self.build_length_bars = expected_build_length_bars(
            self.slider.actual_position,
            self.trajectory.distance,
            self.trajectory.velocity,
        )
        self.silence_length_bars = 1

    def to_dict(self) -> dict:
        return {
            **self.slider.to_dict(),
            **self.trajectory.to_dict(),
            "dominant_instrument": self.dominant_instrument,
            "sparsity_mode": self.sparsity_mode.value,
            "sparsity_level": round(self.sparsity_level, 3),
            "call_response_leader": self.call_response_leader,
            "pending_call_response_leader": self.pending_call_response_leader,
            "leader_committed_at_drop": self.leader_committed_at_drop,
            "build_length_bars": self.build_length_bars,
            "silence_length_bars": self.silence_length_bars,
            "structural_mutations": list(self.structural_mutations),
        }


def expected_build_length_bars(
    actual_position: float,
    trajectory_distance: float = 0.0,
    trajectory_velocity: float = 0.0,
) -> int:
    """Return an archetype-aligned build length diagnostic.

    Build length is separate from Phase 10 silence length. It shapes the
    expected tension runway without moving committed drop boundaries here.
    """
    position = _clamp(actual_position)
    if position < 0.33:
        low, high, preferred = 4, 8, 6
    elif position < 0.67:
        low, high, preferred = 2, 12, 6
    else:
        low, high, preferred = 8, 24, 16
    distance_lift = trajectory_distance * (high - preferred)
    velocity_compress = trajectory_velocity * (preferred - low)
    value = preferred + distance_lift - velocity_compress
    return int(round(max(low, min(high, value))))


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


def _can_coexist_at_step(existing: MIDIEvent, candidate: MIDIEvent) -> bool:
    """Return True for layers that intentionally share timing.

    Priority still exists, but for the rhythmic/foundation bed a lower-priority
    layer yields by becoming less forceful rather than disappearing. This keeps
    kick/snare/hat populated while allowing bassline/sub to align at drops.
    """
    layers = {existing.layer, candidate.layer}
    if layers.issubset(COEXISTENT_FOUNDATION_LAYERS):
        return True
    if candidate.layer in BEAT_BED_LAYERS and existing.layer in COEXISTENT_FOUNDATION_LAYERS:
        return True
    if existing.layer in BEAT_BED_LAYERS and candidate.layer in COEXISTENT_FOUNDATION_LAYERS:
        return True
    if candidate.layer in IDENTITY_LAYERS and existing.layer in COEXISTENT_FOUNDATION_LAYERS:
        return True
    return False


def _soften_priority_yield(event: MIDIEvent) -> bool:
    if event.layer in {"snare", "hat"}:
        event.velocity = max(1, min(127, int(round(event.velocity * 0.78))))
        return True
    if event.layer == "hook":
        event.velocity = max(1, min(127, int(round(event.velocity * 0.88))))
        return True
    return False


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
                if _can_coexist_at_step(winner, event):
                    if _soften_priority_yield(event):
                        stats.events_shifted_by_priority += 1
                    kept.append(event)
                    continue
                if event.layer not in CORE_DROP_LAYERS and not getattr(event, "survives_silence", False):
                    stats.priority_conflicts_resolved += 1
                    continue
            by_step.setdefault(key, event)
            kept.append(event)
        phrase.events = kept
    return stats.to_dict()
