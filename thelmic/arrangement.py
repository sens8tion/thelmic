"""Arrangement patch helpers.

These helpers do not plan syntax. They keep rendered layers aligned with the
existing PhrasePlan and Phase 11 arrangement state.
"""

from __future__ import annotations

from dataclasses import replace

from thelmic.bank_generator import (
    Bank, MIDIEvent, KICK_NOTE, SNARE_NOTE, CLOSED_HAT_NOTE,
)
from thelmic.behaviour_field import BehaviourField
from thelmic.phrase_plan import PhrasePlan
from thelmic.syntax_enforcer import time_to_bar_step, _plan_bar

TICKS_PER_BEAT = 24
TICKS_PER_STEP = 6
STEPS_PER_BAR = 16
SUB_NOTE = 24
ALLOWED_SUB_DURATIONS = {4, 8, 16, 32, 64}


def _step_to_time(bar: int, step: int) -> str:
    tick_in_bar = step * TICKS_PER_STEP
    beat = tick_in_bar // TICKS_PER_BEAT + 1
    tick = tick_in_bar % TICKS_PER_BEAT
    return f"{bar}.{beat}.{tick}"


def _plan_bars(plan: PhrasePlan) -> int:
    return max([1, *plan.phrase_state.keys(), *plan.silence_mask.muted_steps_by_bar.keys()])


def _is_muted(plan: PhrasePlan, bar: int, step: int) -> bool:
    pbar = _plan_bar(bar, _plan_bars(plan))
    return step in set(plan.silence_mask.muted_steps_by_bar.get(pbar, ()))


def _append_to_bar(bank: Bank, event: MIDIEvent) -> None:
    bar, _ = time_to_bar_step(event.time)
    for phrase in bank.phrases:
        phrase_bars = {time_to_bar_step(e.time)[0] for e in phrase.events}
        if bar in phrase_bars:
            phrase.events.append(event)
            return
    if bank.phrases:
        bank.phrases[-1].events.append(event)


def _source_template(bank: Bank) -> MIDIEvent | None:
    for phrase in bank.phrases:
        for event in phrase.events:
            if getattr(event, "active", True):
                return event
    return None


def _bank_bars(bank: Bank) -> list[int]:
    bars = {
        time_to_bar_step(event.time)[0]
        for event in bank.all_events()
        if time_to_bar_step(event.time)[0] >= 1
    }
    return sorted(bars)


def _existing_layer_steps(bank: Bank) -> set[tuple[int, int, str]]:
    result: set[tuple[int, int, str]] = set()
    for event in bank.all_events():
        bar, step = time_to_bar_step(event.time)
        if step >= 0:
            result.add((bar, step, event.layer))
    return result


def _clamp_velocity(value: float) -> int:
    return max(1, min(127, int(round(value))))


def _sparsity_reason(state) -> str:
    dominant = getattr(state, "dominant_instrument", None)
    mode = getattr(getattr(state, "sparsity_mode", None), "value", None)
    level = float(getattr(state, "sparsity_level", 0.0))
    if dominant == "hook":
        return "hook_focus"
    if dominant in {"bassline", "bass", "sub"}:
        return "bass_sub_dominance"
    if mode in {"hard", "dominant_burst"} and level > 0.4:
        return "intentional_stripped_impact"
    if level > 0.35:
        return "trajectory_sparsity"
    return "none"


def ensure_beat_bed(bank: Bank, plan: PhrasePlan, state) -> dict:
    """Populate kick/snare/hat as the default rhythmic bed.

    Silence remains authoritative: muted steps are never repopulated here.
    Later sparsity/priority passes may thin this bed when they have a reason.
    """
    template = _source_template(bank)
    if template is None:
        return {
            "beat_bed_presence": {"kick": False, "snare": False, "hat": False},
            "beat_bed_density": 0,
            "kick_density": 0,
            "snare_density": 0,
            "hat_density": 0,
            "sparsity_reason": _sparsity_reason(state),
            "beat_bed_events_added": 0,
        }

    existing = _existing_layer_steps(bank)
    added = 0
    targets = {
        "kick": (KICK_NOTE, (0, 8), 96, 0.08),
        "snare": (SNARE_NOTE, (4, 12), 88, 0.06),
        "hat": (CLOSED_HAT_NOTE, tuple(range(0, STEPS_PER_BAR, 2)), 58, 0.03),
    }
    for bar in _bank_bars(bank):
        for layer, (note, steps, velocity, duration) in targets.items():
            for step in steps:
                if _is_muted(plan, bar, step) or (bar, step, layer) in existing:
                    continue
                event = replace(
                    template,
                    time=_step_to_time(bar, step),
                    note=note,
                    velocity=velocity,
                    duration=duration,
                    layer=layer,
                    role="anchor" if layer != "hat" else "ghost",
                    emphasis=0.65 if layer != "hat" else 0.35,
                    openness=1.0,
                    expected_weight=0.75 if layer != "hat" else 0.45,
                    should_resolve=False,
                    active=True,
                    deformation={**template.deformation, "beat_bed": 1.0},
                )
                _append_to_bar(bank, event)
                existing.add((bar, step, layer))
                added += 1

    stats = arrangement_diagnostics(bank, state)
    stats["beat_bed_events_added"] = added
    return stats


def _sub_pattern_for_position(landscape_position: float, behaviour: BehaviourField) -> tuple[str, tuple[int, ...], int]:
    if landscape_position >= 0.67:
        return "long_multi_bar_hold", (0,), 32
    if 0.33 < landscape_position < 0.67:
        if behaviour.energy_level > 0.75:
            return "kick_aligned_reinforcement", (0, 8), 4
        return "half_bar_pulse", (0, 8), 8
    return "full_bar_hold", (0,), 16


def generate_sub_from_bassline(
    bassline_events: list[MIDIEvent],
    behaviour: BehaviourField,
    landscape_position: float = 0.0,
) -> list[MIDIEvent]:
    """Render a sparse sustained sub voice from bassline root intent."""
    by_bar: dict[int, list[MIDIEvent]] = {}
    for event in bassline_events:
        bar, step = time_to_bar_step(event.time)
        if step >= 0:
            by_bar.setdefault(bar, []).append(event)

    out: list[MIDIEvent] = []
    held_pitch: int | None = None
    pattern_type, trigger_steps, duration_steps = _sub_pattern_for_position(
        landscape_position, behaviour
    )
    assert duration_steps in ALLOWED_SUB_DURATIONS
    for bar, events in sorted(by_bar.items()):
        source = sorted(events, key=lambda e: time_to_bar_step(e.time)[1])[0]
        pitch = SUB_NOTE + ((source.note - 36) % 12)
        if pattern_type == "long_multi_bar_hold" and held_pitch == pitch and (bar - 1) % 4 != 0:
            continue
        held_pitch = pitch
        for step in trigger_steps:
            out.append(replace(
                source,
                time=_step_to_time(bar, step),
                note=pitch,
                velocity=_clamp_velocity(source.velocity * behaviour.anchor_velocity * 0.82),
                duration=0.08 * duration_steps,
                layer="sub",
                role="sub",
                emphasis=0.9,
                openness=0.0,
                expected_weight=1.0,
                should_resolve=False,
                active=True,
                deformation={
                    **source.deformation,
                    "sub": 1.0,
                    f"sub_pattern:{pattern_type}": 1.0,
                    "sub_hold_length": float(duration_steps),
                },
            ))
    return out


def generate_sub_from_bass(
    bass_events: list[MIDIEvent],
    behaviour: BehaviourField,
) -> list[MIDIEvent]:
    """Compatibility wrapper for older tests/call sites."""
    return generate_sub_from_bassline(bass_events, behaviour)


def _step_from_time(time_str: str) -> int:
    _, step = time_to_bar_step(time_str)
    return step


def _duration_steps(event: MIDIEvent) -> int:
    return max(1, int(round(event.duration / 0.08)))


def _pattern_type_from_event(event: MIDIEvent, prefix: str) -> str | None:
    marker = f"{prefix}_pattern:"
    for key in event.deformation:
        if key.startswith(marker):
            return key.split(":", 1)[1]
    return None


def _alignment_score(bassline_events: list[MIDIEvent], sub_events: list[MIDIEvent]) -> float:
    if not bassline_events or not sub_events:
        return 0.0
    bass_roots = {event.note % 12 for event in bassline_events}
    aligned = sum(1 for event in sub_events if event.note % 12 in bass_roots)
    return round(aligned / max(1, len(sub_events)), 3)


def arrangement_diagnostics(bank: Bank, state) -> dict:
    counts = {
        "kick": 0, "snare": 0, "hat": 0,
        "bass": 0, "bassline": 0, "sub": 0, "stab": 0,
    }
    lengths = {"bassline": [], "sub": []}
    velocities: list[int] = []
    bassline_events: list[MIDIEvent] = []
    sub_events: list[MIDIEvent] = []
    for event in bank.all_events():
        layer = event.layer
        if layer in counts:
            counts[layer] += 1
        if layer in lengths:
            lengths[layer].append(_duration_steps(event))
        if layer == "bassline":
            bassline_events.append(event)
        elif layer == "sub":
            sub_events.append(event)
        if getattr(event, "active", True):
            velocities.append(event.velocity)
    bed_total = counts["kick"] + counts["snare"] + counts["hat"]
    return {
        "beat_bed_presence": {
            "kick": counts["kick"] > 0,
            "snare": counts["snare"] > 0,
            "hat": counts["hat"] > 0,
        },
        "beat_bed_density": bed_total,
        "kick_density": counts["kick"],
        "snare_density": counts["snare"],
        "hat_density": counts["hat"],
        "sparsity_reason": _sparsity_reason(state),
        "bassline_active": counts["bassline"] > 0,
        "bassline_channel_exists": True,
        "bassline_pattern_id": "phrase_plan_bass_v1",
        "bassline_note_lengths": lengths["bassline"][:16],
        "bass_pattern_type": (
            _pattern_type_from_event(bassline_events[0], "bass")
            if bassline_events else None
        ),
        "bass_note_durations": lengths["bassline"][:16],
        "bass_phrase_length": int(
            bassline_events[0].deformation.get("bass_phrase_length", 1)
        ) if bassline_events else 0,
        "sub_active": counts["sub"] > 0,
        "sub_channel_exists": True,
        "sub_pattern_id": "bass_root_hold_v1",
        "sub_note_lengths": lengths["sub"][:16],
        "sub_pattern_type": (
            _pattern_type_from_event(sub_events[0], "sub")
            if sub_events else None
        ),
        "sub_note_durations": lengths["sub"][:16],
        "sub_hold_length": int(
            sub_events[0].deformation.get("sub_hold_length", 0)
        ) if sub_events else 0,
        "bass_sub_alignment_score": _alignment_score(bassline_events, sub_events),
        "note_velocity_source": "note_event_bus",
        "event_velocity": {
            "min": min(velocities) if velocities else 0,
            "max": max(velocities) if velocities else 0,
        },
        "cc_volume_control_used": False,
    }
