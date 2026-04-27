"""Stab generator — mini catch motif system.

Architectural contract
----------------------
Generate musical intent as a motif object first.
Render that motif into timed events only at the output stage.

  select motif
  → apply variation (constrained)
  → render call / response notes per bar
  → convert steps to bar.beat.tick timestamps

Grid definition
---------------
  STEPS_PER_BAR = 16        (16th-note resolution)
  TICKS_PER_STEP = 6        (24 PPQN / 4 = 6 ticks per 16th)
  valid steps: 0 .. 15

Phrase structure
----------------
  2-bar call / response:
    call bar  (bar_in_pair == 0): first note only — setup / anticipation
    resp bar  (bar_in_pair == 1): full motif — answer

  Variation every 4 bars (pair_idx // 2):
    level 0 (bars  1–4): base motif
    level 1 (bars  5–8): drop middle note
    level 2 (bars  9–12): shift final step by +1
    level 3 (bars 13–16): extend final duration

  Every 8 bars (level 3 → wraps back to 0 on the next bank).

Debug test mode
---------------
Set STAB_TEST_PATTERN to a list of step indices to emit a fixed pattern
for grid verification. Set to None to restore musical generation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, replace
from typing import Optional

from thelmic.bank_generator import MIDIEvent
from thelmic.behaviour_field import BehaviourField
from thelmic.call_response import (
    CALL_WINDOW, RESPONSE_WINDOW,
    RESPONSE_WINDOW_MIN, RESPONSE_WINDOW_MAX,
    derive_response_steps, response_velocity, response_duration_steps,
)
from thelmic.rhythm import conformance_for_landscape

# ---------------------------------------------------------------------------
# Grid constants
# ---------------------------------------------------------------------------

TICKS_PER_BAR  = 96
TICKS_PER_BEAT = 24
TICKS_PER_STEP = 6
STEPS_PER_BAR  = 16

# Step duration in seconds at 174 BPM (approximate; bar timing is absolute)
_STEP_SECONDS = 60.0 / (174.0 * TICKS_PER_BEAT / TICKS_PER_STEP)   # ≈ 0.086 s

# Musical grid masks
OFFBEAT_STEPS = frozenset([2, 6, 10, 14])
BEAT_STEPS    = frozenset([0, 4, 8, 12])
LATE_PHRASE   = frozenset([11, 14, 15])

MID_NOTE = 60

# ---------------------------------------------------------------------------
# Debug test mode
# ---------------------------------------------------------------------------

STAB_TEST_PATTERN: Optional[list[int]] = None

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

_log = logging.getLogger("thelmic.stab_timing")


def _log_stab_event(event: MIDIEvent, bar: int, step: int) -> None:
    if not _log.isEnabledFor(logging.DEBUG):
        return
    abs_tick = (bar - 1) * TICKS_PER_BAR + step * TICKS_PER_STEP
    _log.debug(
        "bar=%d\tstep=%d\tabs_tick=%d\tnote=%d\tvelocity=%d\tduration_steps=%d",
        bar, step, abs_tick, event.note, event.velocity,
        max(1, round(event.duration / _STEP_SECONDS)),
    )


# ---------------------------------------------------------------------------
# Grid primitives
# ---------------------------------------------------------------------------

def _step_to_time(bar: int, step: int) -> str:
    assert 0 <= step < STEPS_PER_BAR, f"invalid step {step}"
    tick_in_bar = step * TICKS_PER_STEP
    beat = tick_in_bar // TICKS_PER_BEAT + 1
    tick = tick_in_bar % TICKS_PER_BEAT
    return f"{bar}.{beat}.{tick}"


def _time_to_bar_step(time_str: str) -> tuple[int, int]:
    parts = time_str.split(".")
    bar  = int(parts[0])
    beat = int(parts[1])
    tick = int(parts[2]) if len(parts) > 2 else 0
    abs_tick = (bar - 1) * TICKS_PER_BAR + (beat - 1) * TICKS_PER_BEAT + tick
    if abs_tick % TICKS_PER_STEP != 0:
        return bar, -1
    return bar, (abs_tick % TICKS_PER_BAR) // TICKS_PER_STEP


def _is_grid_aligned(time_str: str) -> bool:
    _, step = _time_to_bar_step(time_str)
    return step >= 0


# ---------------------------------------------------------------------------
# Motif data model
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class StabMotif:
    """A short rhythmic and melodic motif to be rendered into one bar.

    All fields are parallel lists of the same length.

    steps:      step indices within the bar (0..15)
    intervals:  semitone offset from root note
    durations:  note length in steps (1 = 1/16th)
    velocities: MIDI velocities (0–127)
    """
    steps:      tuple[int, ...]
    intervals:  tuple[int, ...]
    durations:  tuple[int, ...]
    velocities: tuple[int, ...]

    def __post_init__(self) -> None:
        n = len(self.steps)
        assert n >= 1
        assert len(self.intervals)  == n
        assert len(self.durations)  == n
        assert len(self.velocities) == n
        assert all(0 <= s < STEPS_PER_BAR for s in self.steps), f"out-of-range steps: {self.steps}"
        assert self.steps == tuple(sorted(self.steps)), "steps must be sorted ascending"

    def __len__(self) -> int:
        return len(self.steps)

    def first_note_only(self) -> "StabMotif":
        """Return a single-note version using only the first note."""
        return StabMotif(
            steps=(self.steps[0],),
            intervals=(self.intervals[0],),
            durations=(self.durations[0],),
            velocities=(int(self.velocities[0] * 0.75),),   # lighter on the call
        )

    def drop_middle(self) -> "StabMotif":
        """Drop the middle note (variation level 1)."""
        if len(self) < 3:
            return self
        idx = [0, len(self) - 1]
        return StabMotif(
            steps=tuple(self.steps[i] for i in idx),
            intervals=tuple(self.intervals[i] for i in idx),
            durations=(self.durations[0], self.durations[-1] + 1),
            velocities=tuple(self.velocities[i] for i in idx),
        )

    def shift_final_step(self, delta: int = 1) -> "StabMotif":
        """Shift the final step by delta, clamped to 0..15 (variation level 2)."""
        new_last = max(0, min(STEPS_PER_BAR - 1, self.steps[-1] + delta))
        # Avoid landing on a beat step
        if new_last in BEAT_STEPS:
            new_last = max(0, min(STEPS_PER_BAR - 1, new_last + 1))
        new_steps = self.steps[:-1] + (new_last,)
        if not (new_steps == tuple(sorted(new_steps))):
            return self   # shift would invert order — skip
        return StabMotif(
            steps=new_steps,
            intervals=self.intervals,
            durations=self.durations,
            velocities=self.velocities,
        )

    def extend_final_duration(self) -> "StabMotif":
        """Extend the final note duration by 1 step (variation level 3)."""
        new_dur = self.durations[:-1] + (min(self.durations[-1] + 1, 4),)
        return StabMotif(
            steps=self.steps,
            intervals=self.intervals,
            durations=new_dur,
            velocities=self.velocities,
        )


# ---------------------------------------------------------------------------
# Built-in motifs
# ---------------------------------------------------------------------------

LATE_ANSWER = StabMotif(
    steps=(10, 13, 14),
    intervals=(0, 3, 5),
    durations=(1, 1, 2),
    velocities=(90, 78, 105),
)

PICKUP_CATCH = StabMotif(
    steps=(11, 14, 15),
    intervals=(0, 2, 0),
    durations=(1, 1, 1),
    velocities=(85, 75, 95),
)

SYNCOPATED_HOOK = StabMotif(
    steps=(6, 10, 13),
    intervals=(0, 5, 3),
    durations=(1, 1, 2),
    velocities=(88, 82, 100),
)

_MOTIFS = [LATE_ANSWER, PICKUP_CATCH, SYNCOPATED_HOOK]

# Call-window motifs — steps must be in CALL_WINDOW (0–7)
CALL_EARLY = StabMotif(
    steps=(2, 6),
    intervals=(0, 3),
    durations=(1, 1),
    velocities=(88, 80),
)

CALL_SYNCO = StabMotif(
    steps=(1, 5, 7),
    intervals=(0, 5, 3),
    durations=(1, 1, 1),
    velocities=(90, 78, 85),
)

CALL_OFFBEAT = StabMotif(
    steps=(2, 4, 6),
    intervals=(0, 2, 5),
    durations=(1, 1, 2),
    velocities=(85, 78, 95),
)

_CALL_MOTIFS = [CALL_EARLY, CALL_SYNCO, CALL_OFFBEAT]


def _select_call_motif(landscape_position: float, bank_idx: int) -> StabMotif:
    """Pick a call-window motif deterministically (offset from response motif)."""
    idx = (bank_idx + int(landscape_position * 10) + 1) % len(_CALL_MOTIFS)
    return _CALL_MOTIFS[idx]


# ---------------------------------------------------------------------------
# Motif selection and variation
# ---------------------------------------------------------------------------

def _select_motif(landscape_position: float, bank_idx: int) -> StabMotif:
    """Pick a motif deterministically from landscape position and bank index."""
    idx = (bank_idx + int(landscape_position * 10)) % len(_MOTIFS)
    return _MOTIFS[idx]


def _varied_motif(base: StabMotif, abs_bar: int) -> StabMotif:
    """Apply deterministic variation based on bar position.

    Level escalates every 4 bars:
      bars  1–4:  base
      bars  5–8:  drop middle note
      bars  9–12: shift final step +1
      bars 13–16: extend final duration
    """
    level = ((abs_bar - 1) // 4) % 4
    if level == 0:
        return base
    if level == 1:
        return base.drop_middle()
    if level == 2:
        return base.shift_final_step(+1)
    return base.extend_final_duration()


# ---------------------------------------------------------------------------
# Landscape-based firing rules
# ---------------------------------------------------------------------------

def _should_fire_in_bar(
    abs_bar: int,
    bar_in_pair: int,   # 0 = call bar, 1 = response bar
    landscape_position: float,
) -> bool:
    """Decide whether the motif fires at all in this bar."""
    if landscape_position <= 0.33:
        # Oak: sparse — response bars only, every 2 bars (even pairs)
        return bar_in_pair == 1
    if landscape_position >= 0.67:
        # Nott: very sparse — only phrase-boundary response bars (bar 4, 8, 12, 16)
        return bar_in_pair == 1 and abs_bar % 4 == 0
    # Chaos: both call and response bars
    return True


def _velocity_scale(behaviour: BehaviourField, bar_in_pair: int) -> float:
    """Scale velocity by energy and call/response role."""
    base = max(0.5, behaviour.energy_level)
    return base * (0.75 if bar_in_pair == 0 else 1.0)


# ---------------------------------------------------------------------------
# Call event collection (kept for compatibility / bar detection)
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
            continue
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
            calls.append(CallEvent(
                time=_step_to_time(bar, 14),
                source_role="phrase_boundary",
                strength=0.45,
            ))
            seen_phrase_bars.add(bar)
    return calls


# ---------------------------------------------------------------------------
# Motif rendering
# ---------------------------------------------------------------------------

def _make_stab_event(
    source: Optional[MIDIEvent],
    time_str: str,
    note: int,
    velocity: int,
    duration_steps: int,
    behaviour: BehaviourField,
) -> MIDIEvent:
    duration_s = duration_steps * _STEP_SECONDS * 0.9   # slight gap to next note
    src_deform = source.deformation if source else {}
    base = source if source else MIDIEvent(
        time="1.1.0", note=note, velocity=velocity, duration=duration_s,
        layer="stab", role="stab", emphasis=0.7, openness=0.5,
        expected_weight=0.0, should_resolve=False,
    )
    return replace(
        base,
        time=time_str,
        note=note,
        velocity=max(1, min(127, velocity)),
        duration=duration_s,
        layer="stab",
        role="stab",
        emphasis=max(0.45, behaviour.energy_level * 0.8),
        openness=0.5,
        expected_weight=0.0,
        should_resolve=False,
        active=True,
        deformation={**src_deform, "stab": behaviour.energy_level},
    )


def _render_motif_in_bar(
    motif: StabMotif,
    abs_bar: int,
    bar_in_pair: int,
    root_note: int,
    behaviour: BehaviourField,
    source: Optional[MIDIEvent],
) -> list[MIDIEvent]:
    """Render a motif into MIDIEvents for one bar.

    call bar (bar_in_pair=0): first note only — anticipation
    resp bar (bar_in_pair=1): full motif — answer
    """
    render_motif = motif.first_note_only() if bar_in_pair == 0 else motif
    vel_scale = _velocity_scale(behaviour, bar_in_pair)
    events = []
    for i in range(len(render_motif)):
        step     = render_motif.steps[i]
        note     = max(0, min(127, root_note + render_motif.intervals[i]))
        velocity = max(1, min(127, int(render_motif.velocities[i] * vel_scale)))
        duration = render_motif.durations[i]
        time_str = _step_to_time(abs_bar, step)
        ev = _make_stab_event(source, time_str, note, velocity, duration, behaviour)
        events.append(ev)
        _log_stab_event(ev, abs_bar, step)
    return events


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
    """Generate stab mini-catch motif across all bars in the bank.

    The motif is selected once per bank, varied every 4 bars, and rendered
    as call (first note) / response (full motif) pairs every 2 bars.
    """
    if STAB_TEST_PATTERN is not None:
        return _generate_test_pattern(events, behaviour, landscape_position)

    if not events:
        if debug is not None:
            debug.update({"stabs_emitted": 0})
        return []

    # Determine which bars are present in the bank
    bars_with_events: set[int] = set()
    for e in events:
        bar, _ = _time_to_bar_step(e.time)
        bars_with_events.add(bar)

    if not bars_with_events:
        return []

    # Select motif for this bank (deterministic from landscape + bar context)
    min_bar = min(bars_with_events)
    bank_idx = (min_bar - 1) // 16   # approximate bank index from bar numbers
    root = MID_NOTE - 12 if landscape_position >= 0.67 else MID_NOTE
    base_motif = _select_motif(landscape_position, bank_idx)

    # Source event for attribute copying (any event will do)
    source = next(
        (e for e in events if e.layer in {"kick", "snare"}),
        events[0] if events else None,
    )

    stab_events: list[MIDIEvent] = []
    emitted = 0

    for abs_bar in sorted(bars_with_events):
        pair_idx   = (abs_bar - 1) // 2   # which 2-bar pair: 0, 1, 2, ...
        bar_in_pair = (abs_bar - 1) % 2   # 0 = call, 1 = response

        if not _should_fire_in_bar(abs_bar, bar_in_pair, landscape_position):
            continue

        motif = _varied_motif(base_motif, abs_bar)
        bar_events = _render_motif_in_bar(
            motif, abs_bar, bar_in_pair, root, behaviour, source,
        )
        stab_events.extend(bar_events)
        emitted += len(bar_events)

    if debug is not None:
        debug.update({"stabs_emitted": emitted, "motif": base_motif.steps})
    return stab_events


def _generate_test_pattern(
    events: list[MIDIEvent],
    behaviour: BehaviourField,
    landscape_position: float,
) -> list[MIDIEvent]:
    """Emit stabs at STAB_TEST_PATTERN steps in every bar that has events."""
    if not events or STAB_TEST_PATTERN is None:
        return []
    bars: set[int] = set()
    for e in events:
        bar, _ = _time_to_bar_step(e.time)
        bars.add(bar)
    note = MID_NOTE - 12 if landscape_position >= 0.67 else MID_NOTE
    out: list[MIDIEvent] = []
    for bar in sorted(bars):
        for step in STAB_TEST_PATTERN:
            if not (0 <= step < STEPS_PER_BAR):
                continue
            time_str = _step_to_time(bar, step)
            ev = _make_stab_event(events[0], time_str, note, 80, 1, behaviour)
            out.append(ev)
            _log_stab_event(ev, bar, step)
    return out


# ---------------------------------------------------------------------------
# Bass → stab derivation
# ---------------------------------------------------------------------------

def extract_bass_steps(bass_events: list[MIDIEvent]) -> dict[int, list[int]]:
    """Return {bar: [step, ...]} for all bass events, sorted ascending per bar."""
    result: dict[int, list[int]] = {}
    for e in bass_events:
        bar, step = _time_to_bar_step(e.time)
        if step >= 0:
            result.setdefault(bar, []).append(step)
    return {b: sorted(set(steps)) for b, steps in result.items()}


def _derive_stab_steps(bass_steps: list[int]) -> list[int]:
    """Derive stab step positions from a list of bass steps.

    Rules:
    - Each derived step follows its seed bass step by +2..+5
    - Avoids the bass step positions
    - Prefers offbeat steps; avoids beat steps if possible
    - Returns at most 3 steps, sorted ascending
    """
    if not bass_steps:
        return []

    bass_set = set(bass_steps)
    derived: list[int] = []

    for bs in sorted(bass_steps)[:3]:
        candidates = [
            bs + off for off in range(2, 6)
            if bs + off < STEPS_PER_BAR
            and bs + off not in bass_set
            and bs + off not in set(derived)
        ]
        if not candidates:
            continue
        offbeat = [c for c in candidates if c in OFFBEAT_STEPS]
        non_beat = [c for c in candidates if c not in BEAT_STEPS]
        chosen = (offbeat or non_beat or candidates)[0]
        derived.append(chosen)

    return sorted(derived)


def _derive_stab_root(bass_note: int, landscape_position: float) -> int:
    """Derive stab root note from bass note + landscape position.

    Oak   (≤0.33): echo — same pitch class, two octaves up
    Chaos (0.33–0.67): lift — two octaves up + perfect 5th
    Nott  (≥0.67): resolve — two octaves up, minor 3rd (tension toward root)
    """
    two_octaves_up = bass_note + 24
    if landscape_position <= 0.33:
        return two_octaves_up           # C4 when bass_note=36
    if landscape_position >= 0.67:
        return two_octaves_up - 3       # A3 — minor 3rd, unresolved tension
    return two_octaves_up + 7           # G4 — perfect 5th above, harmonic lift


def generate_stabs_from_bass(
    bass_events: list[MIDIEvent],
    all_events: list[MIDIEvent],
    behaviour: BehaviourField,
    landscape_position: float = 0.0,
    debug: dict | None = None,
) -> list[MIDIEvent]:
    """Generate stab events explicitly derived from bass events.

    Flow:
      bass_steps (per bar)
        → _derive_stab_steps  (shift +2..+5, avoid collisions)
        → apply motif intervals + velocities
        → call/response rendering (first note on call bars, full on response)

    The stab is the answer to the bass — same rhythm shifted later, harmonic
    relationship determined by landscape position.
    """
    if STAB_TEST_PATTERN is not None:
        return _generate_test_pattern(all_events, behaviour, landscape_position)

    if not bass_events:
        if debug is not None:
            debug.update({"stabs_emitted": 0})
        return []

    bass_steps_by_bar = extract_bass_steps(bass_events)
    if not bass_steps_by_bar:
        return []

    # Determine bass root note (all bass events use the same note)
    bass_note = next((e.note for e in bass_events), 36)
    root = _derive_stab_root(bass_note, landscape_position)

    # Select motif (for intervals, durations, velocities)
    min_bar = min(bass_steps_by_bar)
    bank_idx = (min_bar - 1) // 16
    base_motif = _select_motif(landscape_position, bank_idx)

    source = next(
        (e for e in all_events if e.layer in {"kick", "snare"}),
        all_events[0] if all_events else None,
    )

    stab_events: list[MIDIEvent] = []
    emitted = 0

    for abs_bar in sorted(bass_steps_by_bar):
        bar_in_pair  = (abs_bar - 1) % 2       # 0 = call, 1 = response
        variation    = _varied_motif(base_motif, abs_bar)

        if not _should_fire_in_bar(abs_bar, bar_in_pair, landscape_position):
            continue

        bass_steps = bass_steps_by_bar[abs_bar]
        derived    = _derive_stab_steps(bass_steps)

        if not derived:
            continue

        # Build a StabMotif from derived steps + selected motif's intervals
        n = min(len(derived), len(variation))
        try:
            bar_motif = StabMotif(
                steps=tuple(derived[:n]),
                intervals=variation.intervals[:n],
                durations=variation.durations[:n],
                velocities=variation.velocities[:n],
            )
        except AssertionError:
            continue   # out-of-range or unsorted — skip silently

        render_motif = bar_motif.first_note_only() if bar_in_pair == 0 else bar_motif
        vel_scale    = _velocity_scale(behaviour, bar_in_pair)

        for i in range(len(render_motif)):
            step     = render_motif.steps[i]
            note     = max(0, min(127, root + render_motif.intervals[i]))
            velocity = max(1, min(127, int(render_motif.velocities[i] * vel_scale)))
            duration = render_motif.durations[i]
            time_str = _step_to_time(abs_bar, step)
            ev = _make_stab_event(source, time_str, note, velocity, duration, behaviour)
            stab_events.append(ev)
            emitted += 1
            _log_stab_event(ev, abs_bar, step)

        if _log.isEnabledFor(logging.DEBUG):
            _log.debug(
                "bar=%d bass_steps=%s → stab_steps=%s | bass_note=%d → stab_root=%d intervals=%s",
                abs_bar, bass_steps, list(render_motif.steps),
                bass_note, root, list(render_motif.intervals),
            )

    if debug is not None:
        debug.update({
            "stabs_emitted": emitted,
            "bass_root_note": bass_note,
            "stab_root_note": root,
        })
    return stab_events


# ---------------------------------------------------------------------------
# Dual-modal generators (call_response system)
# ---------------------------------------------------------------------------

def generate_stab_call(
    abs_bar: int,
    behaviour: BehaviourField,
    landscape_position: float = 0.0,
    source: Optional[MIDIEvent] = None,
) -> tuple[list[MIDIEvent], list[int]]:
    """Generate stab call events in CALL_WINDOW (steps 0–7, beats 1–2).

    STAB_LEADS mode: stab fires as the leader in beats 1–2.

    Returns (events, leader_steps) where:
    - events: rendered MIDIEvent list for this bar
    - leader_steps: call-window step indices (for derive_response_steps())

    Motif is selected and varied deterministically from abs_bar.
    Steps that drift out of CALL_WINDOW after variation are dropped.
    """
    bank_idx   = (abs_bar - 1) // 16
    base_motif = _select_call_motif(landscape_position, bank_idx)
    varied     = _varied_motif(base_motif, abs_bar)

    # Filter to CALL_WINDOW — variation may push steps out
    valid_indices = [i for i, s in enumerate(varied.steps) if s in CALL_WINDOW]
    if not valid_indices:
        return [], []

    try:
        call_motif = StabMotif(
            steps=tuple(varied.steps[i] for i in valid_indices),
            intervals=tuple(varied.intervals[i] for i in valid_indices),
            durations=tuple(varied.durations[i] for i in valid_indices),
            velocities=tuple(varied.velocities[i] for i in valid_indices),
        )
    except AssertionError:
        return [], []

    root   = MID_NOTE - 12 if landscape_position >= 0.67 else MID_NOTE
    events = []
    for i in range(len(call_motif)):
        step     = call_motif.steps[i]
        note     = max(0, min(127, root + call_motif.intervals[i]))
        velocity = max(1, min(127, int(call_motif.velocities[i]
                                       * max(0.5, behaviour.energy_level))))
        ev = _make_stab_event(
            source, _step_to_time(abs_bar, step),
            note, velocity, call_motif.durations[i], behaviour,
        )
        events.append(ev)
        _log_stab_event(ev, abs_bar, step)

    leader_steps = list(call_motif.steps)

    if _log.isEnabledFor(logging.DEBUG):
        _log.debug(
            "bar=%d STAB_CALL leader_steps=%s root=%d",
            abs_bar, leader_steps, root,
        )

    return events, leader_steps


def generate_stab_response_from_steps(
    leader_steps: list[int],
    abs_bar: int,
    behaviour: BehaviourField,
    landscape_position: float = 0.0,
    source: Optional[MIDIEvent] = None,
) -> list[MIDIEvent]:
    """Generate stab response events in RESPONSE_WINDOW (steps 8–15).

    BASS_LEADS mode: bass is the leader; stab answers in beats 3–4.

    leader_steps: call-window steps (0–7) from the bass leader.
    derive_response_steps() maps them to {8..15}.

    Hard constraint: asserts every event has step >= RESPONSE_WINDOW_MIN.
    """
    response_steps = derive_response_steps(leader_steps)
    if not response_steps:
        return []

    bank_idx   = (abs_bar - 1) // 16
    base_motif = _select_motif(landscape_position, bank_idx)
    root       = _derive_stab_root(36, landscape_position)

    n = min(len(response_steps), len(base_motif))
    try:
        resp_motif = StabMotif(
            steps=tuple(response_steps[:n]),
            intervals=base_motif.intervals[:n],
            durations=base_motif.durations[:n],
            velocities=base_motif.velocities[:n],
        )
    except AssertionError:
        return []

    n = len(resp_motif)
    events = []
    for i in range(n):
        step = resp_motif.steps[i]
        assert step >= RESPONSE_WINDOW_MIN, (
            f"stab response step {step} violates HARD RULE (< {RESPONSE_WINDOW_MIN})"
        )
        note = max(0, min(127, root + resp_motif.intervals[i]))

        # Response emphasis: escalate toward the landing note.
        # Base velocity from the motif, then apply approach→landing curve.
        base_vel = max(1, int(resp_motif.velocities[i] * max(0.5, behaviour.energy_level)))
        velocity = response_velocity(i, n, base_vel)

        # Hold the final response note — creates arrival, not just a later tap.
        dur_steps = response_duration_steps(i, n, resp_motif.durations[i])

        ev = _make_stab_event(
            source, _step_to_time(abs_bar, step),
            note, velocity, dur_steps, behaviour,
        )
        events.append(ev)
        _log_stab_event(ev, abs_bar, step)

    if _log.isEnabledFor(logging.DEBUG):
        _log.debug(
            "bar=%d STAB_RESPONSE leader=%s → resp_steps=%s root=%d",
            abs_bar, leader_steps, list(resp_motif.steps), root,
        )

    return events


def generate_stabs(
    events: list[MIDIEvent],
    behaviour: BehaviourField,
    landscape_position: float = 0.0,
) -> list[MIDIEvent]:
    """Generate stabs from drum events only (no bass context — used in tests)."""
    calls = collect_call_events(events)
    return generate_stabs_from_calls(calls, events, behaviour, landscape_position)
