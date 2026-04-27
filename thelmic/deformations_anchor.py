from __future__ import annotations

import random
from collections import defaultdict

from thelmic.bank_generator import Bank, MIDIEvent
from thelmic.behaviour_field import BehaviourField


def is_anchor_event(event: MIDIEvent) -> bool:
    return event.role == "anchor"


def drop_event(event: MIDIEvent) -> None:
    event.velocity = 0
    event.active = False
    event.deformation["anchor_withholding"] = 1.0


def _event_bar(event: MIDIEvent) -> int:
    return int(event.time.split(".")[0])


def _drop_probability(behaviour: BehaviourField, transition_progress: float = 0.0) -> float:
    probability = behaviour.anchor_drop_prob
    if probability < 0.1:
        return 0.0
    if transition_progress > 0.7:
        probability = min(1.0, probability + 0.15)
    return probability


def apply_anchor_withholding(
    bank: Bank,
    behaviour: BehaviourField,
    transition_progress: float = 0.0,
) -> dict[str, dict[int, int]]:
    probability = _drop_probability(behaviour, transition_progress)
    dropped_per_bar: dict[int, int] = defaultdict(int)
    if probability <= 0.0:
        return {"anchors_dropped_per_bar": {}}

    anchors_by_bar: dict[int, list[MIDIEvent]] = defaultdict(list)
    for event in bank.all_events():
        if getattr(event, "active", True) and is_anchor_event(event):
            anchors_by_bar[_event_bar(event)].append(event)

    for bar, anchors in anchors_by_bar.items():
        remaining = len(anchors)
        if remaining <= 1:
            continue

        candidates = [event for event in anchors if event.layer == "snare"] or anchors
        for event in candidates:
            if remaining <= 1:
                break
            if random.random() < probability:
                drop_event(event)
                dropped_per_bar[bar] += 1
                remaining -= 1

    return {"anchors_dropped_per_bar": dict(dropped_per_bar)}
