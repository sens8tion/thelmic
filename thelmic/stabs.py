from __future__ import annotations

from dataclasses import dataclass
from dataclasses import replace

from thelmic.bank_generator import MIDIEvent
from thelmic.behaviour_field import BehaviourField
from thelmic.rhythm import conformance_for_landscape

MID_NOTE = 60
OFFSET_1_16 = 6
OFFSET_1_8 = 12
TICKS_PER_BAR = 96
TICKS_PER_STEP = 6    # 1 sixteenth note = 6 ticks; valid steps are multiples of this


@dataclass
class CallEvent:
    time: str
    source_role: str
    strength: float
    was_withheld: bool = False


def _parse_time(time_str: str) -> tuple[int, int, int]:
    bar, beat, tick = time_str.split(".")
    return int(bar), int(beat), int(tick)


def _snap_to_grid_step(time_str: str) -> str:
    """Snap a time string to the nearest 16th-note grid step.

    Hard invariant: all stab events must land on valid step indices (0..15
    per bar). Any free timing introduced by floating arithmetic or non-step
    offsets is removed here.
    """
    bar, beat, tick = _parse_time(time_str)
    abs_tick = (bar - 1) * TICKS_PER_BAR + (beat - 1) * 24 + tick
    snapped    = round(abs_tick / TICKS_PER_STEP) * TICKS_PER_STEP
    new_bar    = snapped // TICKS_PER_BAR + 1
    within_bar = snapped % TICKS_PER_BAR
    new_beat   = within_bar // 24 + 1
    new_tick   = within_bar % 24
    return f"{new_bar}.{new_beat}.{new_tick}"


def _is_grid_aligned(time_str: str) -> bool:
    """Return True iff the time falls on a 16th-note step boundary."""
    bar, beat, tick = _parse_time(time_str)
    abs_tick = (bar - 1) * TICKS_PER_BAR + (beat - 1) * 24 + tick
    return abs_tick % TICKS_PER_STEP == 0


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


def _gate_value(time_str: str, salt: int = 0) -> float:
    bar, beat, tick = _parse_time(time_str)
    value = (bar * 41 + beat * 19 + tick * 5 + salt * 31) % 100
    return value / 100.0


def _response_delay_ticks(behaviour: BehaviourField, landscape_position: float) -> int:
    """Return a response delay in ticks, always a multiple of TICKS_PER_STEP.

    All return values are multiples of 6 (= one 16th-note step).
    """
    if landscape_position <= 0.33:
        return OFFSET_1_8                                 # 12 = 2 steps
    if landscape_position >= 0.67:
        return 24                                         # 24 = 4 steps (1 beat)
    # Chaos: scale 1–4 steps based on anticipation, snapped to nearest step
    raw = OFFSET_1_16 + int(round(behaviour.anticipation * OFFSET_1_8))
    return round(raw / TICKS_PER_STEP) * TICKS_PER_STEP  # snap: 6, 12, 18, or 24


def _stab_velocity_scale(behaviour: BehaviourField) -> float:
    ghost = min(behaviour.ghost_velocity, max(0.0, behaviour.anchor_velocity - 0.1))
    anchor = max(behaviour.anchor_velocity, ghost + 0.1)
    candidate = max(ghost + 0.05, behaviour.energy_level * 0.8)
    return max(0.0, min(anchor - 0.05, candidate, 1.0))


def collect_call_events(events: list[MIDIEvent]) -> list[CallEvent]:
    calls: list[CallEvent] = []
    seen_phrase_bars: set[int] = set()
    for event in events:
        if event.layer not in {"kick", "snare"}:
            continue

        bar, beat, tick = _parse_time(event.time)
        was_withheld = "anchor_withholding" in event.deformation
        is_anchor = event.role in {"anchor", "impact"}
        is_strong = is_anchor and event.expected_weight >= 0.7 and tick == 0

        if event.layer == "snare" and (is_anchor or was_withheld):
            calls.append(CallEvent(
                time=event.time,
                source_role="dropped_snare" if was_withheld else "snare_anchor",
                strength=1.0 if was_withheld else max(0.5, event.emphasis),
                was_withheld=was_withheld,
            ))
        elif is_strong:
            calls.append(CallEvent(
                time=event.time,
                source_role=f"strong_{event.layer}",
                strength=max(0.35, event.emphasis * 0.65),
                was_withheld=was_withheld,
            ))

        if bar % 4 == 0 and bar not in seen_phrase_bars:
            calls.append(CallEvent(
                time=f"{bar}.4.12",
                source_role="phrase_boundary",
                strength=0.45,
                was_withheld=False,
            ))
            seen_phrase_bars.add(bar)
    return calls


def _response_slot(call: CallEvent, behaviour: BehaviourField, landscape_position: float) -> str:
    """Compute the stab response time, snapped to the nearest 16th-note step.

    _snap_to_grid_step is the hard guarantee: no matter what internal arithmetic
    produces, the output is always on a valid step boundary.
    """
    if 0.33 < landscape_position < 0.67:
        # Slots are [12, 18, 24] — all multiples of 6; snapping is a no-op but
        # defensive in case call.time itself is somehow off-grid.
        slots = [OFFSET_1_8, 18, 24]
        idx = min(len(slots) - 1, int(_gate_value(call.time, salt=2) * len(slots)))
        raw = _offset_time(call.time, slots[idx])
    else:
        raw = _offset_time(call.time, _response_delay_ticks(behaviour, landscape_position))
    return _snap_to_grid_step(raw)


def _should_emit_response(
    call: CallEvent,
    behaviour: BehaviourField,
    landscape_position: float,
    stabs_in_bar: int,
) -> bool:
    conformance = conformance_for_landscape(landscape_position)
    chaos_response_factor = 1.0 - conformance

    if landscape_position <= 0.33:
        bar, _, _ = _parse_time(call.time)
        return call.source_role == "snare_anchor" and bar % 2 == 1 and stabs_in_bar == 0

    if landscape_position >= 0.67:
        bar, _, _ = _parse_time(call.time)
        return (
            call.was_withheld or call.source_role == "phrase_boundary"
        ) and bar % 4 == 0 and stabs_in_bar == 0

    probability = call.strength * behaviour.energy_level * chaos_response_factor
    if call.was_withheld:
        probability += 0.35
    if stabs_in_bar >= 1:
        probability *= 0.3
    probability = max(0.0, min(0.85, probability))
    return _gate_value(call.time, salt=1 if call.was_withheld else 0) < probability


def generate_stabs_from_calls(
    calls: list[CallEvent],
    events: list[MIDIEvent],
    behaviour: BehaviourField,
    landscape_position: float = 0.0,
    debug: dict | None = None,
) -> list[MIDIEvent]:
    stab_events: list[MIDIEvent] = []
    counters = {
        "call_candidates": len(calls),
        "valid_response_slots": 0,
        "stabs_attempted": 0,
        "stabs_emitted": 0,
        "stabs_suppressed_by_probability": 0,
        "stabs_suppressed_by_slot": 0,
        "stabs_suppressed_by_conformance": 0,
        "stabs_suppressed_by_overlap": 0,
        "stabs_suppressed_by_density": 0,
    }
    if not events:
        if debug is not None:
            debug.update(counters)
        return stab_events
    velocity_scale = _stab_velocity_scale(behaviour)
    stabs_per_bar: dict[int, int] = {}
    occupied_response_times: set[str] = set()
    source_by_time = {event.time: event for event in events}

    for call in calls:
        response_time = _response_slot(call, behaviour, landscape_position)
        # Hard rule: reject any response not on a 16th-note boundary.
        # _response_slot applies _snap_to_grid_step, so this should never
        # trigger; the check is a defensive invariant guard.
        if not _is_grid_aligned(response_time):
            counters["stabs_suppressed_by_slot"] += 1
            continue
        if response_time == call.time:
            counters["stabs_suppressed_by_slot"] += 1
            continue
        counters["valid_response_slots"] += 1
        if response_time in occupied_response_times:
            counters["stabs_suppressed_by_overlap"] += 1
            continue

        bar = int(response_time.split(".")[0])
        stabs_in_bar = stabs_per_bar.get(bar, 0)
        if stabs_in_bar >= 1:
            counters["stabs_suppressed_by_density"] += 1
        counters["stabs_attempted"] += 1
        if _should_emit_response(call, behaviour, landscape_position, stabs_in_bar):
            source = source_by_time.get(call.time)
            source_velocity = source.velocity if source and source.velocity > 0 else 80
            source_deformation = source.deformation if source else {}
            source_emphasis = source.emphasis if source else call.strength
            source_expected = source.expected_weight if source else 0.0
            note = MID_NOTE - 12 if landscape_position >= 0.67 else MID_NOTE
            stab_events.append(replace(
                source or events[0],
                time=response_time,
                note=note,
                velocity=_clamp_velocity(source_velocity * velocity_scale),
                duration=0.08,
                layer="stab",
                role="stab",
                emphasis=max(0.45, source_emphasis * 0.7),
                openness=0.5,
                expected_weight=source_expected,
                should_resolve=False,
                active=True,
                deformation={**source_deformation, "stab": behaviour.energy_level},
            ))
            stabs_per_bar[bar] = stabs_per_bar.get(bar, 0) + 1
            occupied_response_times.add(response_time)
            counters["stabs_emitted"] += 1
        else:
            if conformance_for_landscape(landscape_position) > 0.75:
                counters["stabs_suppressed_by_conformance"] += 1
            else:
                counters["stabs_suppressed_by_probability"] += 1

    if debug is not None:
        debug.update(counters)
    return stab_events


def generate_stabs(
    events: list[MIDIEvent],
    behaviour: BehaviourField,
    landscape_position: float = 0.0,
) -> list[MIDIEvent]:
    calls = collect_call_events(events)
    if not calls or not events:
        return []
    return generate_stabs_from_calls(calls, events, behaviour, landscape_position)
