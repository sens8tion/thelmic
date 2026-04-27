from __future__ import annotations

from dataclasses import replace
from typing import Optional

from thelmic.bank_generator import MIDIEvent
from thelmic.behaviour_field import BehaviourField
from thelmic.phrase_plan import PhrasePlan, PlanNote

TICKS_PER_BEAT = 24
TICKS_PER_STEP = 6


def _step_to_hook_time(bar: int, step: int) -> str:
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
        if event.layer in {"kick", "snare", "hat"} and _event_bar(event) == bar:
            return event
    return next((event for event in events if getattr(event, "active", True)), None)


def _clamp_velocity(value: int) -> int:
    return max(1, min(127, int(value)))


def generate_planned_hook(
    events: list[MIDIEvent],
    behaviour: BehaviourField,
    plan: PhrasePlan,
) -> list[MIDIEvent]:
    """Render first-class hook identity from PhrasePlan.hook_pattern.

    Hook is independent of call/response material. It follows the authored plan
    and repeats across the bars present in the rendered bank.
    """
    if not plan.hook_pattern:
        return []

    bars = _bars_in_events(events)
    if not bars:
        return []

    plan_bars = max((note.bar for note in plan.hook_pattern), default=1)
    by_plan_bar: dict[int, list[PlanNote]] = {}
    for note in plan.hook_pattern:
        by_plan_bar.setdefault(note.bar, []).append(note)

    hook_events: list[MIDIEvent] = []
    for bar in bars:
        source = _source_for_bar(events, bar)
        if source is None:
            continue
        plan_bar = ((bar - 1) % plan_bars) + 1
        for note in by_plan_bar.get(plan_bar, []):
            hook_events.append(replace(
                source,
                time=_step_to_hook_time(bar, note.step),
                note=note.pitch,
                velocity=_clamp_velocity(note.velocity),
                duration=max(1, note.duration_steps) * 0.08,
                layer="hook",
                role="hook",
                emphasis=0.72,
                openness=0.4 + behaviour.energy_level * 0.2,
                expected_weight=0.7,
                should_resolve=False,
                active=True,
                deformation={**source.deformation, "hook": 1.0},
            ))

    return hook_events
