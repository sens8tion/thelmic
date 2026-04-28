from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Optional

from thelmic.bank_generator import MIDIEvent
from thelmic.behaviour_field import BehaviourField
from thelmic.phrase_plan import PhrasePlan, PlanNote, ROOT_NOTE
from thelmic.rhythm import conformance_for_landscape
from thelmic.call_response import (
    CALL_WINDOW, RESPONSE_WINDOW_MIN,
    response_velocity, response_duration_steps,
)

LOW_NOTE = 36
OFFBEAT_TICKS = 12
TICKS_PER_BAR = 96
TICKS_PER_BEAT = 24
TICKS_PER_STEP = 6
ALLOWED_BASS_INTERVALS = {0, 7, 12}
ALLOWED_BASSLINE_DURATIONS = {1, 2, 3, 4, 8, 16}


@dataclass(frozen=True)
class BasslinePattern:
    pattern_type: str
    steps: tuple[int, ...]
    duration_steps: tuple[int, ...]
    phrase_length_bars: int = 1

    def __post_init__(self) -> None:
        assert len(self.steps) == len(self.duration_steps)
        assert all(0 <= step < 16 for step in self.steps)
        assert all(duration in ALLOWED_BASSLINE_DURATIONS for duration in self.duration_steps)


BASSLINE_PATTERNS: dict[str, BasslinePattern] = {
    "offbeat_pulse": BasslinePattern("offbeat_pulse", (2, 6, 10, 14), (2, 2, 2, 2)),
    "kick_answer": BasslinePattern("kick_answer", (2, 6, 10, 14), (2, 3, 2, 3)),
    "held_fill": BasslinePattern("held_fill", (0, 12, 14), (8, 1, 2)),
    "syncopated_cluster": BasslinePattern("syncopated_cluster", (2, 6, 11, 12, 14), (2, 2, 1, 1, 2)),
    "driving_loop": BasslinePattern("driving_loop", (0, 4, 8, 12), (2, 2, 2, 2)),
    "nott_hold": BasslinePattern("nott_hold", (0,), (16,), phrase_length_bars=2),
}


def _step_to_bass_time(bar: int, step: int) -> str:
    """Convert (bar, step) to bar.beat.tick string. Steps 0..15."""
    tick_in_bar = step * TICKS_PER_STEP
    beat = tick_in_bar // TICKS_PER_BEAT + 1
    tick = tick_in_bar % TICKS_PER_BEAT
    return f"{bar}.{beat}.{tick}"


def _time_to_step(time_str: str) -> tuple[int, int]:
    bar, beat, tick = _parse_time(time_str)
    abs_tick_in_bar = (beat - 1) * TICKS_PER_BEAT + tick
    if abs_tick_in_bar % TICKS_PER_STEP != 0:
        return bar, -1
    return bar, abs_tick_in_bar // TICKS_PER_STEP


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


def _source_for_planned_note(
    events: list[MIDIEvent],
    bar: int,
    step: int,
) -> Optional[MIDIEvent]:
    fallback = next((e for e in events if getattr(e, "active", True)), None)
    for event in events:
        if not getattr(event, "active", True) or event.layer != "kick":
            continue
        event_bar, event_step = _time_to_step(event.time)
        if event_bar == bar and event_step == step:
            return event
    return fallback


def _kick_steps_by_bar(events: list[MIDIEvent]) -> dict[int, set[int]]:
    result: dict[int, set[int]] = {}
    for event in events:
        if not getattr(event, "active", True) or event.layer != "kick":
            continue
        bar, step = _time_to_step(event.time)
        if step >= 0:
            result.setdefault(bar, set()).add(step)
    return result


def _planned_pitch(note: PlanNote, tonal_centre: int = ROOT_NOTE) -> int:
    interval = note.pitch - tonal_centre
    while interval < 0:
        interval += 12
    interval %= 12
    if interval not in ALLOWED_BASS_INTERVALS:
        return tonal_centre
    octave = 12 if note.pitch - tonal_centre >= 12 else 0
    return tonal_centre + interval + octave


def _select_bassline_pattern(
    landscape_position: float,
    behaviour: BehaviourField,
    bar: int,
) -> BasslinePattern:
    """Select a bounded genre-aligned bassline pattern."""
    if landscape_position <= 0.33:
        return BASSLINE_PATTERNS["driving_loop"]
    if landscape_position >= 0.67:
        if behaviour.energy_level > 0.75 and bar % 4 == 0:
            return BASSLINE_PATTERNS["held_fill"]
        return BASSLINE_PATTERNS["nott_hold"]
    if behaviour.instability > 0.55 and bar % 4 == 0:
        return BASSLINE_PATTERNS["syncopated_cluster"]
    if behaviour.energy_level > 0.65:
        return BASSLINE_PATTERNS["kick_answer"]
    return BASSLINE_PATTERNS["offbeat_pulse"]


def _planned_root_for_bar(
    plan: PhrasePlan,
    plan_bar: int,
    tonal_centre: int,
) -> int:
    notes = [note for note in plan.bass_pattern if note.bar == plan_bar]
    source = notes[0] if notes else (plan.bass_pattern[0] if plan.bass_pattern else None)
    if source is None:
        return tonal_centre
    return _planned_pitch(source, tonal_centre)


def generate_planned_bass(
    events: list[MIDIEvent],
    behaviour: BehaviourField,
    plan: PhrasePlan,
    tonal_centre: int = ROOT_NOTE,
    landscape_position: float = 0.5,
) -> list[MIDIEvent]:
    """Render authored bassline from phrase-plan root intent.

    This is the Phase 1 truth layer: bass comes from the plan first, not from
    stab/call-response material. Timing is rendered from constrained
    genre-aligned pattern families rather than arbitrary plan steps.
    """
    kick_steps = _kick_steps_by_bar(events)
    if not kick_steps:
        return []

    bass_events: list[MIDIEvent] = []
    bars = sorted(kick_steps)
    plan_bars = max((note.bar for note in plan.bass_pattern), default=1)

    for bar in bars:
        plan_bar = ((bar - 1) % plan_bars) + 1
        root = _planned_root_for_bar(plan, plan_bar, tonal_centre)
        pattern = _select_bassline_pattern(landscape_position, behaviour, bar)
        for index, step in enumerate(pattern.steps):
            source = _source_for_planned_note(events, bar, step)
            if source is None:
                continue
            accent = 1.08 if step in kick_steps.get(bar, set()) else 0.92
            velocity = _clamp_velocity(104 * behaviour.anchor_velocity * accent)
            duration_steps = pattern.duration_steps[index]
            bass_event = replace(
                source,
                time=_step_to_bass_time(bar, step),
                note=root,
                velocity=velocity,
                duration=duration_steps * 0.08,
                layer="bassline",
                role="bassline",
                emphasis=0.85,
                openness=0.0,
                expected_weight=max(0.8, source.expected_weight),
                should_resolve=False,
                active=True,
                deformation={
                    **source.deformation,
                    "bassline": behaviour.energy_level,
                    f"bass_pattern:{pattern.pattern_type}": 1.0,
                    "bass_phrase_length": float(pattern.phrase_length_bars),
                },
            )
            bass_events.append(bass_event)

    return bass_events


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
        n = len(resp_steps)
        for i, step in enumerate(resp_steps):
            assert step >= RESPONSE_WINDOW_MIN, (
                f"bass response step {step} violates HARD RULE (< {RESPONSE_WINDOW_MIN})"
            )
            time_str = _step_to_bass_time(bar, step)

            # Response emphasis: escalate velocity, hold the final note.
            # The bass response should feel heavier than the call — it's the landing.
            base_vel = int(source.velocity * behaviour.anchor_velocity)
            vel = response_velocity(i, n, base_vel)
            dur_steps = response_duration_steps(i, n, base_steps=1)
            duration_s = dur_steps * TICKS_PER_STEP * (60.0 / (174.0 * 24.0)) * 0.9

            ev = replace(
                source,
                time=time_str,
                note=LOW_NOTE,
                velocity=_clamp_velocity(vel),
                duration=duration_s,
                layer="bass",
                role="bass_response",
                emphasis=0.85 if i == n - 1 else 0.65,
                openness=0.0,
                expected_weight=0.8 if i == n - 1 else 0.7,
                should_resolve=False,
                active=True,
                deformation={**source.deformation, "bass": behaviour.energy_level},
            )
            bass_events.append(ev)

    return bass_events
