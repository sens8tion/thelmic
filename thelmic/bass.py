from __future__ import annotations

from dataclasses import replace

from thelmic.bank_generator import MIDIEvent
from thelmic.behaviour_field import BehaviourField
from thelmic.rhythm import conformance_for_landscape
from thelmic.call_response import CALL_WINDOW, RESPONSE_WINDOW_MIN

LOW_NOTE = 36
OFFBEAT_TICKS = 12
TICKS_PER_BAR = 96
TICKS_PER_BEAT = 24
TICKS_PER_STEP = 6


def _step_to_bass_time(bar: int, step: int) -> str:
    """Convert (bar, step) to bar.beat.tick string. Steps 0..15."""
    tick_in_bar = step * TICKS_PER_STEP
    beat = tick_in_bar // TICKS_PER_BEAT + 1
    tick = tick_in_bar % TICKS_PER_BEAT
    return f"{bar}.{beat}.{tick}"


def _bars_in_events(events: list[MIDIEvent]) -> list[int]:
    """Return sorted unique bar indices present in the event list."""
    bars: set[int] = set()
    for e in events:
        try:
            bars.add(int(e.time.split(".")[0]))
        except (ValueError, AttributeError):
            pass
    return sorted(bars)


def _parse_time(time_str: str) -> tuple[int, int, int]:
    bar, beat, tick = time_str.split(".")
    return int(bar), int(beat), int(tick)


def _offset_time(time_str: str, ticks: int) -> str:
    bar, beat, tick = _parse_time(time_str)
    absolute = (bar - 1) * TICKS_PER_BAR + (beat - 1) * 24 + tick + ticks
    new_bar = absolute // TICKS_PER_BAR + 1
    within_bar = absolute % TICKS_PER_BAR
    new_beat = within_bar // 24 + 1
    new_tick = within_bar % 24
    return f"{new_bar}.{new_beat}.{new_tick}"


def _clamp_velocity(value: float) -> int:
    return max(1, min(127, int(round(value))))


def _bar(time_str: str) -> int:
    return int(time_str.split(".")[0])


def _gate_value(time_str: str, salt: int = 0) -> float:
    bar, beat, tick = _parse_time(time_str)
    value = (bar * 37 + beat * 17 + tick * 3 + salt * 29) % 100
    return value / 100.0


def _copy_bass_event(
    event: MIDIEvent,
    time: str,
    behaviour: BehaviourField,
    weight: float = 0.9,
) -> MIDIEvent:
    velocity = _clamp_velocity(event.velocity * behaviour.anchor_velocity * weight)
    bass_event = replace(
        event,
        time=time,
        note=LOW_NOTE,
        velocity=velocity,
        duration=0.12,
        layer="bass",
        role="bass",
        emphasis=0.7,
        openness=0.0,
        expected_weight=event.expected_weight,
        should_resolve=False,
        active=True,
        deformation={**event.deformation, "bass": behaviour.energy_level},
    )
    return bass_event


def _is_selected_oak_kick(event: MIDIEvent) -> bool:
    _, beat, tick = _parse_time(event.time)
    return event.role in {"anchor", "impact"} and tick == 0 and beat in {1, 3}


def _is_selected_nott_kick(event: MIDIEvent) -> bool:
    bar, beat, tick = _parse_time(event.time)
    return event.role in {"anchor", "impact"} and tick == 0 and beat == 1 and bar % 2 == 1


def generate_bass(
    events: list[MIDIEvent],
    behaviour: BehaviourField,
    landscape_position: float = 0.0,
) -> list[MIDIEvent]:
    bass_events: list[MIDIEvent] = []
    offbeats_by_bar: set[int] = set()
    conformance = conformance_for_landscape(landscape_position)
    chaos_factor = 1.0 - conformance

    for event in events:
        if not getattr(event, "active", True) or event.layer != "kick":
            continue

        if landscape_position >= 0.67:
            if _is_selected_nott_kick(event):
                bass_events.append(_copy_bass_event(event, event.time, behaviour, weight=1.05))
            continue

        if landscape_position <= 0.33:
            if _is_selected_oak_kick(event):
                bass_events.append(_copy_bass_event(event, event.time, behaviour, weight=0.9))
            continue

        probability = 0.55 + behaviour.energy_level * 0.25
        if _gate_value(event.time) < probability:
            bass_events.append(_copy_bass_event(event, event.time, behaviour, weight=0.95))

            bar = _bar(event.time)
            if behaviour.instability > 0.4 and bar not in offbeats_by_bar:
                offbeat_probability = min(0.25, chaos_factor * (behaviour.instability - 0.4) * 0.6)
                if offbeat_probability > 0.0 and _gate_value(event.time, salt=1) < offbeat_probability:
                    bass_events.append(_copy_bass_event(
                        event, _offset_time(event.time, OFFBEAT_TICKS), behaviour, weight=0.75,
                    ))
                    offbeats_by_bar.add(bar)

    return bass_events


# ---------------------------------------------------------------------------
# Dual-modal generators (call_response system)
# ---------------------------------------------------------------------------

def generate_bass_call(
    events: list[MIDIEvent],
    behaviour: BehaviourField,
    landscape_position: float = 0.0,
) -> list[MIDIEvent]:
    """Generate bass events in CALL_WINDOW (steps 0–7, beats 1–2).

    BASS_LEADS mode: bass fires as the leader, unconditionally at steps 0
    and 4 (beats 1 and 2) for every bar present in events.

    Returns events with layer='bass', role='bass_call'.
    """
    bass_events: list[MIDIEvent] = []
    source = next((e for e in events if getattr(e, "active", True)), None)
    if source is None:
        return bass_events

    for bar in _bars_in_events(events):
        for step in [0, 4]:   # beats 1 and 2
            assert step in CALL_WINDOW, f"bug: step {step} not in CALL_WINDOW"
            time_str = _step_to_bass_time(bar, step)
            velocity = _clamp_velocity(
                source.velocity * behaviour.anchor_velocity * 0.9
            )
            ev = replace(
                source,
                time=time_str,
                note=LOW_NOTE,
                velocity=velocity,
                duration=0.10,
                layer="bass",
                role="bass_call",
                emphasis=0.8,
                openness=0.0,
                expected_weight=0.9,
                should_resolve=False,
                active=True,
                deformation={**source.deformation, "bass": behaviour.energy_level},
            )
            bass_events.append(ev)

    return bass_events


def generate_bass_response_from_steps(
    leader_steps_by_bar: dict[int, list[int]],
    events: list[MIDIEvent],
    behaviour: BehaviourField,
    landscape_position: float = 0.0,
) -> list[MIDIEvent]:
    """Generate bass response events in RESPONSE_WINDOW (steps 8–15).

    STAB_LEADS mode: stab is the leader; bass answers in beats 3–4.

    leader_steps_by_bar: {bar: [response_step, ...]} — steps already
    derived by derive_response_steps(), guaranteed to be in {8..15}.

    Hard constraint: asserts no event fires below RESPONSE_WINDOW_MIN.
    """
    bass_events: list[MIDIEvent] = []
    source = next((e for e in events if getattr(e, "active", True)), None)
    if source is None:
        return bass_events

    for bar, resp_steps in sorted(leader_steps_by_bar.items()):
        for step in resp_steps:
            assert step >= RESPONSE_WINDOW_MIN, (
                f"bass response step {step} violates HARD RULE (< {RESPONSE_WINDOW_MIN})"
            )
            time_str = _step_to_bass_time(bar, step)
            velocity = _clamp_velocity(
                source.velocity * behaviour.anchor_velocity * 0.85
            )
            ev = replace(
                source,
                time=time_str,
                note=LOW_NOTE,
                velocity=velocity,
                duration=0.10,
                layer="bass",
                role="bass_response",
                emphasis=0.65,
                openness=0.0,
                expected_weight=0.7,
                should_resolve=False,
                active=True,
                deformation={**source.deformation, "bass": behaviour.energy_level},
            )
            bass_events.append(ev)

    return bass_events
