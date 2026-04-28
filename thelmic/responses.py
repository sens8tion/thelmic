"""Phase 5 — planner-owned response generation.

Responses are rendered only from PhrasePlan.response_slots.

Contract:
- A response event may only exist inside a planned response_slot.
- A response requires a valid preceding call (call_slots non-empty for the
  preceding CALL_UNRESOLVED bar in the same phrase cycle).
- No response_slot  → no response event.
- No valid call     → no response event; increment response_events_without_call.
- Silence mask      → suppress; increment response_events_suppressed.
- Role must be "response".
- Hook events are independent; responses must not overwrite hook identity.
- Bass events are independent; responses must not redefine bass meaning.

Suppression counters exposed via PlannedResponseResult.stats:
  planned_response_slots
  response_events_rendered
  response_events_suppressed
  response_events_outside_slots
  response_events_without_call
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Optional

from thelmic.bank_generator import MIDIEvent
from thelmic.behaviour_field import BehaviourField
from thelmic.phrase_plan import PhrasePlan, PhraseState
from thelmic.syntax_enforcer import time_to_bar_step

TICKS_PER_BEAT  = 24
TICKS_PER_STEP  = 6
# A perfect 4th below the call root (calls use CALL_ROOT = 62).
# Responses resolve downward toward the tonal centre.
RESPONSE_ROOT   = 57   # A3 — P4 below D4 (call root 62)


@dataclass
class PlannedResponseResult:
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
    return next((e for e in events if getattr(e, "active", True)), None)


def _plan_bars(plan: PhrasePlan) -> int:
    return max([1, *plan.phrase_state.keys(), *plan.response_slots.keys()])


def _plan_bar(bar: int, plan_bars: int) -> int:
    return ((bar - 1) % max(1, plan_bars)) + 1


def _response_pitch(index: int) -> int:
    """Resolving pitches: A3, G3, E3 — descend toward tonal centre."""
    return RESPONSE_ROOT - (index % 3) * 3


def _response_velocity(index: int, behaviour: BehaviourField) -> int:
    # Landing emphasis: first note lighter, last heavier.
    base = 80 + index * 6
    return max(1, min(127, int(base * max(0.5, behaviour.energy_level))))


def _preceding_call_bar(response_pbar: int, states: dict[int, PhraseState]) -> Optional[int]:
    """Return the most recent CALL_UNRESOLVED bar strictly before response_pbar."""
    for bar in range(response_pbar - 1, 0, -1):
        if states.get(bar) == PhraseState.CALL_UNRESOLVED:
            return bar
    return None


def _has_valid_call(response_pbar: int, plan: PhrasePlan) -> bool:
    """A valid call exists iff the preceding CALL_UNRESOLVED bar has call_slots."""
    call_bar = _preceding_call_bar(response_pbar, plan.phrase_state)
    if call_bar is None:
        return False
    return bool(plan.call_slots.get(call_bar))


def _planned_response_slots_for_bars(
    plan: PhrasePlan, bars: list[int],
) -> dict[int, list[int]]:
    """Map rendered bar → sorted response step list from PhrasePlan."""
    plan_bars = _plan_bars(plan)
    result: dict[int, list[int]] = {}
    for bar in bars:
        pbar = _plan_bar(bar, plan_bars)
        slots = sorted(set(plan.response_slots.get(pbar, ())))
        if slots:
            result[bar] = slots
    return result


def generate_planned_responses(
    events: list[MIDIEvent],
    behaviour: BehaviourField,
    plan: PhrasePlan,
    leader_layer: str = "stab",
) -> PlannedResponseResult:
    """Render planner-owned response events from PhrasePlan.response_slots."""
    bars = _bars_in_events(events)
    slots_by_bar = _planned_response_slots_for_bars(plan, bars)
    planned_total = sum(len(s) for s in slots_by_bar.values())
    stats: dict = {
        "planned_response_slots":        planned_total,
        "response_events_rendered":      0,
        "response_events_suppressed":    0,
        "response_events_outside_slots": 0,
        "response_events_without_call":  0,
    }

    if planned_total == 0:
        return PlannedResponseResult([], stats)

    plan_bars = _plan_bars(plan)
    rendered: list[MIDIEvent] = []

    for bar, slots in slots_by_bar.items():
        pbar = _plan_bar(bar, plan_bars)

        # Rule: no valid call → suppress all responses for this bar.
        if not _has_valid_call(pbar, plan):
            stats["response_events_without_call"] += len(slots)
            stats["response_events_suppressed"]   += len(slots)
            continue

        source = _source_for_bar(events, bar)
        if source is None:
            stats["response_events_suppressed"] += len(slots)
            continue

        muted = set(plan.silence_mask.muted_steps_by_bar.get(pbar, ()))

        for index, step in enumerate(slots):
            # Range guard
            if not 0 <= step < 16:
                stats["response_events_outside_slots"] += 1
                stats["response_events_suppressed"]    += 1
                continue

            # Silence mask
            if step in muted:
                stats["response_events_suppressed"] += 1
                continue

            event = replace(
                source,
                time=_step_to_time(bar, step),
                note=_response_pitch(index),
                velocity=_response_velocity(index, behaviour),
                duration=0.08,
                layer=leader_layer,
                role="response",
                emphasis=0.70,
                openness=0.45,
                expected_weight=0.40,
                should_resolve=True,
                active=True,
                deformation={**source.deformation, "planned_response": 1.0},
            )

            # Verify the rendered step is inside a response slot (hard guard).
            _, rendered_step = time_to_bar_step(event.time)
            if rendered_step not in slots:
                stats["response_events_outside_slots"] += 1
                stats["response_events_suppressed"]    += 1
                continue

            rendered.append(event)
            stats["response_events_rendered"] += 1

    return PlannedResponseResult(rendered, stats)
