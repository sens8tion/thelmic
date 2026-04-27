"""Stab generator — rhythmically locked punctuation events.

Architectural contract
----------------------
Generate musical intent as step indices first.
Convert step indices to scheduled time only at the final output stage.

  musical intent
  → call events (from rhythm)
  → valid step indices
  → note events with exact bar.beat.tick timestamps
  → scheduled MIDI

Never: compute a time offset, then try to quantize later.

Grid definition
---------------
  STEPS_PER_BAR = 16        (16th-note resolution)
  TICKS_PER_STEP = 6        (24 PPQN / 4 = 6 ticks per 16th)
  valid steps: 0 .. 15

Debug test mode
---------------
Set STAB_TEST_PATTERN to a list of step indices to bypass normal generation
and emit stabs at exactly those steps every bar. Use to verify grid alignment
before tuning musical behaviour.

  STAB_TEST_PATTERN = [4, 10, 14]   # or [3, 7, 11, 15]

Set back to None to return to musical generation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from typing import Optional

from thelmic.bank_generator import MIDIEvent
from thelmic.behaviour_field import BehaviourField
from thelmic.rhythm import conformance_for_landscape

# ---------------------------------------------------------------------------
# Grid constants
# ---------------------------------------------------------------------------

TICKS_PER_BAR  = 96
TICKS_PER_BEAT = 24
TICKS_PER_STEP = 6     # 1 sixteenth note
STEPS_PER_BAR  = 16    # valid step indices: 0 .. 15

# Musical grid masks
OFFBEAT_STEPS   = frozenset([2, 6, 10, 14])   # "e" and "ah" of each beat
BEAT_STEPS      = frozenset([0, 4, 8, 12])    # strong beat positions (avoid)
LATE_PHRASE     = frozenset([11, 14, 15])      # tension / late-phrase feel

# Note
MID_NOTE = 60

# ---------------------------------------------------------------------------
# Debug test mode
# ---------------------------------------------------------------------------

# Set to a list of step indices to override normal generation with a fixed
# pattern. Every bar that has any call events will fire stabs at exactly these
# steps. Set to None to restore musical generation.
#
#   STAB_TEST_PATTERN = [4, 10, 14]
#   STAB_TEST_PATTERN = [3, 7, 11, 15]
STAB_TEST_PATTERN: Optional[list[int]] = None

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

_log = logging.getLogger("thelmic.stab_timing")


def _log_stab_event(event: MIDIEvent, bar: int, step: int) -> None:
    if not _log.isEnabledFor(logging.DEBUG):
        return
    abs_tick = (bar - 1) * TICKS_PER_BAR + step * TICKS_PER_STEP
    # Duration as step count (always 1 step for now — pitch/duration tuning later)
    _log.debug(
        "bar=%d\tstep=%d\tabs_tick=%d\tnote=%d\tvelocity=%d\tduration_steps=1",
        bar, step, abs_tick, event.note, event.velocity,
    )


# ---------------------------------------------------------------------------
# Grid primitives — the only place time strings are constructed or parsed
# ---------------------------------------------------------------------------

def _step_to_time(bar: int, step: int) -> str:
    """Convert a (bar, step) pair to a bar.beat.tick string.

    bar:  1-indexed bar number
    step: 0-indexed step within the bar (0..STEPS_PER_BAR-1)
    """
    assert 0 <= step < STEPS_PER_BAR, f"invalid step {step}"
    tick_in_bar = step * TICKS_PER_STEP
    beat = tick_in_bar // TICKS_PER_BEAT + 1
    tick = tick_in_bar % TICKS_PER_BEAT
    return f"{bar}.{beat}.{tick}"


def _time_to_bar_step(time_str: str) -> tuple[int, int]:
    """Parse a time string to (bar, step).  Returns step=-1 if off-grid."""
    parts = time_str.split(".")
    bar  = int(parts[0])
    beat = int(parts[1])
    tick = int(parts[2]) if len(parts) > 2 else 0
    abs_tick = (bar - 1) * TICKS_PER_BAR + (beat - 1) * TICKS_PER_BEAT + tick
    if abs_tick % TICKS_PER_STEP != 0:
        return bar, -1
    step = (abs_tick % TICKS_PER_BAR) // TICKS_PER_STEP
    return bar, step


def _is_grid_aligned(time_str: str) -> bool:
    _, step = _time_to_bar_step(time_str)
    return step >= 0


# ---------------------------------------------------------------------------
# Call events — identify rhythmic anchor points that invite a stab response
# ---------------------------------------------------------------------------

@dataclass
class CallEvent:
    time:        str
    source_role: str
    strength:    float
    was_withheld: bool = False


def collect_call_events(events: list[MIDIEvent]) -> list[CallEvent]:
    calls: list[CallEvent] = []
    seen_phrase_bars: set[int] = set()
    for event in events:
        if event.layer not in {"kick", "snare"}:
            continue
        bar, step = _time_to_bar_step(event.time)
        if step < 0:
            continue  # off-grid source — skip

        was_withheld = "anchor_withholding" in event.deformation
        is_anchor    = event.role in {"anchor", "impact"}
        is_strong    = is_anchor and event.expected_weight >= 0.7 and step % 4 == 0

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
            # Phrase boundary call — step 14 (late, high-tension)
            calls.append(CallEvent(
                time=_step_to_time(bar, 14),
                source_role="phrase_boundary",
                strength=0.45,
                was_withheld=False,
            ))
            seen_phrase_bars.add(bar)
    return calls


# ---------------------------------------------------------------------------
# Step selection — step indices only, no time arithmetic
# ---------------------------------------------------------------------------

def _gate_value(bar: int, step: int, salt: int = 0) -> float:
    """Deterministic pseudo-random value in [0, 1) from bar/step/salt."""
    return ((bar * 41 + step * 19 + salt * 31) % 100) / 100.0


def _candidate_steps(
    call_step: int,
    bar: int,
    occupied: set[int],
    landscape_position: float,
) -> list[int]:
    """Return valid stab step indices for a response to a call at call_step.

    Rules:
    - Must be an offbeat step (not on a strong beat)
    - Must come after the call (leave at least 1 step gap)
    - Must not be occupied by an existing stab or avoided anchor
    - Landscape colours which offbeats are preferred
    """
    # Window: respond within 4 steps of the call, wrapping into the next bar
    # is handled at the call site by using bar+1.
    candidates = [
        s for s in sorted(OFFBEAT_STEPS)
        if s > call_step                   # after the call
        and s not in occupied              # not already taken
        and s not in BEAT_STEPS            # not on a strong beat
    ]

    # Nott: prefer late-phrase steps
    if landscape_position >= 0.67:
        late = [s for s in candidates if s in LATE_PHRASE]
        if late:
            return late

    return candidates


def _select_step(candidates: list[int], bar: int, call_step: int, strength: float) -> int:
    """Deterministically pick one step from candidates."""
    h = int(_gate_value(bar, call_step, salt=int(strength * 10))) * len(candidates)
    return candidates[h % len(candidates)]


# ---------------------------------------------------------------------------
# Velocity / note helpers
# ---------------------------------------------------------------------------

def _clamp_velocity(v: float) -> int:
    return max(1, min(127, int(round(v))))


def _stab_velocity(behaviour: BehaviourField, source_velocity: int) -> int:
    ghost  = min(behaviour.ghost_velocity, max(0.0, behaviour.anchor_velocity - 0.1))
    anchor = max(behaviour.anchor_velocity, ghost + 0.1)
    scale  = max(0.0, min(anchor - 0.05, max(ghost + 0.05, behaviour.energy_level * 0.8), 1.0))
    return _clamp_velocity(source_velocity * scale)


def _should_emit(
    call: CallEvent,
    call_step: int,
    bar: int,
    behaviour: BehaviourField,
    landscape_position: float,
    stabs_in_bar: int,
) -> bool:
    """Deterministic gate: should this call produce a stab?"""
    conformance = conformance_for_landscape(landscape_position)

    # Oak: sparse — only odd bars, only snare anchors, at most 1 per bar
    if landscape_position <= 0.33:
        return (
            call.source_role == "snare_anchor"
            and bar % 2 == 1
            and stabs_in_bar == 0
        )

    # Nott: phrase-locked — only on phrase boundaries or withheld anchors
    if landscape_position >= 0.67:
        return (
            (call.was_withheld or call.source_role == "phrase_boundary")
            and bar % 4 == 0
            and stabs_in_bar == 0
        )

    # Chaos: probability gate
    probability = call.strength * behaviour.energy_level * (1.0 - conformance)
    if call.was_withheld:
        probability += 0.35
    if stabs_in_bar >= 1:
        probability *= 0.3
    probability = max(0.0, min(0.85, probability))
    return _gate_value(bar, call_step, salt=2) < probability


# ---------------------------------------------------------------------------
# Main generators
# ---------------------------------------------------------------------------

def generate_stabs_from_calls(
    calls: list[CallEvent],
    events: list[MIDIEvent],
    behaviour: BehaviourField,
    landscape_position: float = 0.0,
    debug: dict | None = None,
) -> list[MIDIEvent]:
    """Generate stab events from a list of calls.

    Step-index-first flow:
      call → (bar, call_step) → candidate steps → selected step → time string
    """
    if STAB_TEST_PATTERN is not None:
        return _generate_test_pattern(events, behaviour, landscape_position)

    counters: dict = {
        "call_candidates": len(calls),
        "stabs_emitted": 0,
        "stabs_suppressed_by_no_candidates": 0,
        "stabs_suppressed_by_probability": 0,
        "stabs_suppressed_by_density": 0,
        "stabs_off_grid_rejected": 0,
    }

    stab_events: list[MIDIEvent] = []
    stabs_per_bar: dict[int, int] = {}
    occupied_per_bar: dict[int, set[int]] = {}
    source_by_time = {e.time: e for e in events}

    for call in calls:
        bar, call_step = _time_to_bar_step(call.time)
        if call_step < 0:
            counters["stabs_off_grid_rejected"] += 1
            continue

        stabs_in_bar = stabs_per_bar.get(bar, 0)
        if stabs_in_bar >= 1:
            counters["stabs_suppressed_by_density"] += 1

        if not _should_emit(call, call_step, bar, behaviour, landscape_position, stabs_in_bar):
            counters["stabs_suppressed_by_probability"] += 1
            continue

        occupied = occupied_per_bar.setdefault(bar, set())
        candidates = _candidate_steps(call_step, bar, occupied, landscape_position)

        if not candidates:
            # Try early offbeats in the next bar
            next_bar_occupied = occupied_per_bar.get(bar + 1, set())
            next_candidates = [
                s for s in [2, 6] if s not in next_bar_occupied
            ]
            if next_candidates:
                selected_step = _select_step(next_candidates, bar + 1, call_step, call.strength)
                stab_bar = bar + 1
            else:
                counters["stabs_suppressed_by_no_candidates"] += 1
                continue
        else:
            selected_step = _select_step(candidates, bar, call_step, call.strength)
            stab_bar = bar

        stab_time = _step_to_time(stab_bar, selected_step)

        source = source_by_time.get(call.time)
        src_velocity = source.velocity if source and source.velocity > 0 else 80
        src_deformation = source.deformation if source else {}
        src_emphasis    = source.emphasis if source else call.strength
        src_weight      = source.expected_weight if source else 0.0

        note = MID_NOTE - 12 if landscape_position >= 0.67 else MID_NOTE

        stab = replace(
            source or events[0],
            time=stab_time,
            note=note,
            velocity=_stab_velocity(behaviour, src_velocity),
            duration=0.08,
            layer="stab",
            role="stab",
            emphasis=max(0.45, src_emphasis * 0.7),
            openness=0.5,
            expected_weight=src_weight,
            should_resolve=False,
            active=True,
            deformation={**src_deformation, "stab": behaviour.energy_level},
        )

        stab_events.append(stab)
        occupied_per_bar.setdefault(stab_bar, set()).add(selected_step)
        stabs_per_bar[stab_bar] = stabs_per_bar.get(stab_bar, 0) + 1
        counters["stabs_emitted"] += 1
        _log_stab_event(stab, stab_bar, selected_step)

    if debug is not None:
        debug.update(counters)
    return stab_events


def _generate_test_pattern(
    events: list[MIDIEvent],
    behaviour: BehaviourField,
    landscape_position: float,
) -> list[MIDIEvent]:
    """Emit stabs at STAB_TEST_PATTERN steps in every bar that has events.

    Used to verify grid alignment before enabling musical generation.
    """
    if not events or STAB_TEST_PATTERN is None:
        return []

    bars_with_events: set[int] = set()
    for e in events:
        bar, _ = _time_to_bar_step(e.time)
        bars_with_events.add(bar)

    note = MID_NOTE - 12 if landscape_position >= 0.67 else MID_NOTE
    stab_events: list[MIDIEvent] = []

    for bar in sorted(bars_with_events):
        for step in STAB_TEST_PATTERN:
            if not (0 <= step < STEPS_PER_BAR):
                continue
            stab_time = _step_to_time(bar, step)
            stab = replace(
                events[0],
                time=stab_time,
                note=note,
                velocity=80,
                duration=0.08,
                layer="stab",
                role="stab",
                emphasis=0.7,
                openness=0.5,
                expected_weight=0.0,
                should_resolve=False,
                active=True,
                deformation={"stab": 1.0},
            )
            stab_events.append(stab)
            _log_stab_event(stab, bar, step)

    return stab_events


def generate_stabs(
    events: list[MIDIEvent],
    behaviour: BehaviourField,
    landscape_position: float = 0.0,
) -> list[MIDIEvent]:
    calls = collect_call_events(events)
    if not calls and STAB_TEST_PATTERN is None:
        return []
    return generate_stabs_from_calls(calls, events, behaviour, landscape_position)
