from __future__ import annotations

from thelmic.bank_generator import Bank, MIDIEvent
from thelmic.behaviour_field import BehaviourField


def _clamp_velocity(value: float) -> int:
    return max(1, min(127, int(round(value))))


def _is_ghost_event(event: MIDIEvent) -> bool:
    return event.role == "ghost" or "ghost_inject" in event.deformation


def _is_anchor_event(event: MIDIEvent) -> bool:
    return event.layer in {"kick", "snare"} and event.role in {"anchor", "impact"}


def _velocity_scales(behaviour: BehaviourField) -> tuple[float, float]:
    ghost = min(behaviour.ghost_velocity, max(0.0, behaviour.anchor_velocity - 0.1))
    anchor = max(behaviour.anchor_velocity, ghost + 0.1)
    return max(0.0, min(1.0, ghost)), max(0.0, min(1.0, anchor))


def apply_behaviour_dynamics(bank: Bank, behaviour: BehaviourField) -> None:
    ghost_velocity, anchor_velocity = _velocity_scales(behaviour)
    for event in bank.all_events():
        if not getattr(event, "active", True) or event.velocity <= 0:
            continue

        original = event.velocity
        if _is_ghost_event(event):
            event.velocity = _clamp_velocity(original * ghost_velocity)
            event.deformation["behaviour_dynamics"] = ghost_velocity
        elif _is_anchor_event(event):
            event.velocity = _clamp_velocity(original * anchor_velocity)
            event.deformation["behaviour_dynamics"] = anchor_velocity
