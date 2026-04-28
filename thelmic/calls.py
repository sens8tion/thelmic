from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Optional

from thelmic.bank_generator import MIDIEvent
from thelmic.behaviour_field import BehaviourField
from thelmic.phrase_plan import PhrasePlan
from thelmic.syntax_enforcer import time_to_bar_step

TICKS_PER_BEAT = 24
TICKS_PER_STEP = 6
CALL_ROOT = 62


@dataclass
class PlannedCallResult:
    events: list[MIDIEvent]
    stats: dict


def _step_to_time(bar: int, step: int) -> str:
    tick_in_bar = step * TICKS_PER_STEP
    beat = tick_in_bar // TICKS_PER_BEAT + 1
    tick = tick_in_bar % TICKS_PER_BEAT
    return f"{bar}.{beat}.{tick}"


def _event_bar(event: MIDIEvent) -> Optional[int]:
    try:
        return int(event.time.split(".")[0])
    except (AttributeError, ValueError):
        return None


def _bars_in_events(events: list[MIDIEvent]) -> list[int]:
    bars = {
        bar
        for event in events
        if getattr(event, "active", True) and event.layer in {"kick", "snare", "hat"}
        for bar in [_event_bar(event)]
        if bar is not None
    }
    return sorted(bars)


def _source_for_bar(events: list[MIDIEvent], bar: int) -> Optional[MIDIEvent]:
    for event in events:
        if not getattr(event, "active", True):
            continue
        if event.layer in {"snare", "kick", "hat"} and _event_bar(event) == bar:
            return event
    return next((event for event in events if getattr(event, "active", True)), None)


def _plan_bars(plan: PhrasePlan) -> int:
    return max([1, *plan.phrase_state.keys(), *plan.call_slots.keys()])


def _plan_bar(bar: int, plan_bars: int) -> int:
    return ((bar - 1) % max(1, plan_bars)) + 1


def _call_pitch(index: int) -> int:
    return CALL_ROOT + (index % 3) * 2


def _call_velocity(index: int, behaviour: BehaviourField) -> int:
    base = 72 + index * 8
    return max(1, min(127, int(base * max(0.45, behaviour.energy_level))))


def _planned_slots_for_rendered_bars(plan: PhrasePlan, bars: list[int]) -> dict[int, list[int]]:
    plan_bars = _plan_bars(plan)
    result: dict[int, list[int]] = {}
    for bar in bars:
        pbar = _plan_bar(bar, plan_bars)
        slots = sorted(set(plan.call_slots.get(pbar, ())))
        if slots:
            result[bar] = slots
    return result


def generate_planned_calls(
    events: list[MIDIEvent],
    behaviour: BehaviourField,
    plan: PhrasePlan,
    leader_layer: str = "stab",
) -> PlannedCallResult:
    """Render planner-owned call events from PhrasePlan.call_slots."""
    bars = _bars_in_events(events)
    planned_by_bar = _planned_slots_for_rendered_bars(plan, bars)
    planned_total = sum(len(slots) for slots in planned_by_bar.values())
    stats = {
        "planned_call_slots": planned_total,
        "call_events_rendered": 0,
        "call_events_suppressed": 0,
        "call_events_outside_slots": 0,
    }
    if planned_total == 0:
        return PlannedCallResult([], stats)

    plan_bars = _plan_bars(plan)
    rendered: list[MIDIEvent] = []
    for bar, slots in planned_by_bar.items():
        source = _source_for_bar(events, bar)
        if source is None:
            stats["call_events_suppressed"] += len(slots)
            continue

        pbar = _plan_bar(bar, plan_bars)
        muted = set(plan.silence_mask.muted_steps_by_bar.get(pbar, ()))
        for index, step in enumerate(slots):
            if not 0 <= step < 16:
                stats["call_events_outside_slots"] += 1
                stats["call_events_suppressed"] += 1
                continue
            if step in muted:
                stats["call_events_suppressed"] += 1
                continue

            event = replace(
                source,
                time=_step_to_time(bar, step),
                note=_call_pitch(index),
                velocity=_call_velocity(index, behaviour),
                duration=0.06,
                layer=leader_layer,
                role="call",
                emphasis=0.62,
                openness=0.55,
                expected_weight=0.35,
                should_resolve=True,
                active=True,
                deformation={**source.deformation, "planned_call": 1.0},
            )
            _, rendered_step = time_to_bar_step(event.time)
            if rendered_step not in slots:
                stats["call_events_outside_slots"] += 1
                stats["call_events_suppressed"] += 1
                continue
            rendered.append(event)
            stats["call_events_rendered"] += 1

    return PlannedCallResult(rendered, stats)
