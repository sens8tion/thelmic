"""Phase 9 — Drop construction and enforcement.

A DROP_RELOCK bar is a planned relock point where:
  - bass truth is asserted
  - hook identity is present or re-enters
  - kick, bass, and hook align at the drop step
  - prior silence/thinning provides contrast
  - instability is resolved, discharged, or transformed

The drop enforcer identifies DROP_RELOCK regions from PhrasePlan.phrase_state
and ensures structural requirements are met after all Phases 3-8 passes.

It may ADD events (bass, kick, hook at the drop step) only when they are
missing due to the silence mask removing planned step-0 events.  It does not
invent new material — it reasserts planned authority at the first available
step in the drop bar.

DROP_STEP = 4  (steps 0-3 are muted by silence_mask in DROP_RELOCK bars)

Rules enforced
--------------
  - Bass must assert tonal centre at the drop step.
  - Hook must be present at or near the drop step.
  - Kick and bass should align at the drop step.
  - Unresolved call/response material must not leak into the drop.
  - No echo-style lower-velocity copies of authority material.
  - Pre-drop contrast must exist (adjacent HOLD_SILENCE or low density).
  - Pression does not create notes (this enforcer creates notes; Pression cannot).
  - No density compensation for natural silence.

Planner-first contract
----------------------
Notes added by this pass are reassertions of planned identity (from
phrase_plan.bass_pattern and phrase_plan.hook_pattern), not independent
inventions.  The PhrasePlan defines the tonal centre and hook pitch;
this pass ensures they are present at the structurally required moment.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from thelmic.bank_generator import Bank, MIDIEvent, CLOSED_HAT_NOTE, KICK_NOTE, SNARE_NOTE
from thelmic.phrase_plan import PhrasePlan, PhraseState
from thelmic.syntax_enforcer import time_to_bar_step, _plan_bar

TICKS_PER_BEAT = 24
TICKS_PER_STEP = 6
STEPS_PER_BAR  = 16

# First non-muted step in a DROP_RELOCK bar (silence mask covers steps 0-3)
DROP_STEP: int = 4

# Velocity at which the drop authority events are anchored
DROP_BASS_VELOCITY:  int = 110
DROP_KICK_VELOCITY:  int = 115
DROP_HOOK_VELOCITY:  int = 90
SURVIVOR_NOTE: int = 84
SURVIVOR_RENDER_LANE: str = "hat"
SURVIVOR_RENDER_NOTE: int = CLOSED_HAT_NOTE
SURVIVOR_LANE_PRIORITY: tuple[str, ...] = (
    "hat", "ghost", "snare", "stab", "hook", "kick", "bass",
)
SURVIVOR_SECONDARY_LANE: str = "snare"
SURVIVOR_SECONDARY_NOTE: int = SNARE_NOTE
SURVIVOR_MAX_VELOCITY: int = 24
SURVIVOR_MIN_VELOCITY: int = 5
SURVIVOR_DURATION: float = 0.025
SURVIVOR_SECONDARY_START: float = 0.80

# A supporting event is an "echo" if its velocity is below this fraction
# of the authority event at the same step/pitch
ECHO_VELOCITY_THRESHOLD: float = 0.80


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

@dataclass
class DropStats:
    drop_regions_detected:       int = 0
    drop_relock_events_added:    int = 0
    drop_relock_events_adjusted: int = 0
    drop_missing_contrast:       int = 0
    drop_illegal_events_suppressed: int = 0
    drop_step: int = DROP_STEP
    survivor_events_before_drop: int = 0
    normal_events_suppressed_before_drop: int = 0
    commit_applied: int = 0
    active_state_before: str = ""
    pending_state: str = ""
    active_state_after: str = ""
    kick_at_drop: int = 0
    bass_at_drop: int = 0

    def to_dict(self) -> dict[str, int | str]:
        return {
            "drop_regions_detected":           self.drop_regions_detected,
            "drop_relock_events_added":        self.drop_relock_events_added,
            "drop_relock_events_adjusted":     self.drop_relock_events_adjusted,
            "drop_missing_contrast":           self.drop_missing_contrast,
            "drop_illegal_events_suppressed":  self.drop_illegal_events_suppressed,
            "drop_step":                       self.drop_step,
            "survivor_events_before_drop":     self.survivor_events_before_drop,
            "normal_events_suppressed_before_drop": self.normal_events_suppressed_before_drop,
            "commit_applied":                  self.commit_applied,
            "active_state_before":             self.active_state_before,
            "pending_state":                   self.pending_state,
            "active_state_after":              self.active_state_after,
            "kick_at_drop":                    self.kick_at_drop,
            "bass_at_drop":                    self.bass_at_drop,
        }


@dataclass
class DropCommitState:
    active_state: str = "resolved_stable"
    pending_state: str = "drop_relock"
    committed_drop_ids: set[str] = field(default_factory=set)

    def commit_once(self, drop_id: str) -> tuple[bool, str, str, str]:
        before = self.active_state
        pending = self.pending_state
        if drop_id in self.committed_drop_ids:
            return False, before, pending, self.active_state
        self.active_state = self.pending_state
        self.committed_drop_ids.add(drop_id)
        return True, before, pending, self.active_state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _step_to_time(bar: int, step: int) -> str:
    tick_in_bar = step * TICKS_PER_STEP
    beat = tick_in_bar // TICKS_PER_BEAT + 1
    tick = tick_in_bar % TICKS_PER_BEAT
    return f"{bar}.{beat}.{tick}"


def _events_for_bar(bank: Bank, bar: int) -> list[MIDIEvent]:
    result = []
    for phrase in bank.phrases:
        for e in phrase.events:
            b, _ = time_to_bar_step(e.time)
            if b == bar:
                result.append(e)
    return result


def _has_layer_at_step(events: list[MIDIEvent], bar: int, step: int,
                        layer: str) -> bool:
    for e in events:
        b, s = time_to_bar_step(e.time)
        if b == bar and s == step and e.layer == layer:
            return True
    return False


def _plan_bars(plan: PhrasePlan) -> int:
    return max([1, *plan.phrase_state.keys()])


def _planned_pitch(plan: PhrasePlan, bar: int, layer: str) -> int | None:
    """Return the planned pitch for bass or hook at this bar (from pattern)."""
    pattern = plan.bass_pattern if layer == "bass" else plan.hook_pattern
    if not pattern:
        return None
    pb = _plan_bars(plan)
    pbar = _plan_bar(bar, pb)
    # Find a note in the pattern for this plan bar
    for note in pattern:
        if note.bar == pbar:
            return note.pitch
    # Fallback: first note in pattern
    return pattern[0].pitch


def _source_template(bank: Bank) -> MIDIEvent:
    """Return any event as a template for replace(), or a minimal default."""
    for phrase in bank.phrases:
        if phrase.events:
            return phrase.events[0]
    # Fallback: create a minimal template when the bank is empty
    return MIDIEvent(
        time="1.1.0", note=36, velocity=100, duration=0.08,
        layer="kick", role="anchor",
        emphasis=0.8, openness=1.0, expected_weight=0.9, should_resolve=False,
    )


def _append_to_bar(bank: Bank, event: MIDIEvent) -> None:
    """Add an event to the phrase that owns its bar."""
    bar, _ = time_to_bar_step(event.time)
    for phrase in bank.phrases:
        phrase_bars = {time_to_bar_step(e.time)[0] for e in phrase.events}
        if bar in phrase_bars:
            phrase.events.append(event)
            return
    # If no phrase owns that bar yet, add to the last phrase
    if bank.phrases:
        bank.phrases[-1].events.append(event)


def _bar_density(bank: Bank, bar: int) -> int:
    """Count events in a bar (for contrast detection)."""
    return sum(
        1 for phrase in bank.phrases
        for e in phrase.events
        if time_to_bar_step(e.time)[0] == bar
    )


def _existing_event_keys(bank: Bank) -> set[tuple[str, str, str]]:
    return {
        (event.time, event.layer, event.role)
        for phrase in bank.phrases
        for event in phrase.events
    }


def _survivor_velocity(tightening_factor: float) -> int:
    span = SURVIVOR_MAX_VELOCITY - SURVIVOR_MIN_VELOCITY
    return max(
        SURVIVOR_MIN_VELOCITY,
        min(SURVIVOR_MAX_VELOCITY, int(SURVIVOR_MAX_VELOCITY - span * tightening_factor)),
    )


def _survivor_render_specs(step: int, tightening_factor: float) -> tuple[tuple[str, int, float], ...]:
    specs: list[tuple[str, int, float]] = [(SURVIVOR_RENDER_LANE, SURVIVOR_RENDER_NOTE, 1.0)]
    if (
        tightening_factor >= SURVIVOR_SECONDARY_START
        and step not in {0, DROP_STEP}
    ):
        specs.append((SURVIVOR_SECONDARY_LANE, SURVIVOR_SECONDARY_NOTE, 0.45))
    return tuple(specs)


def _survivor_step_selected(index: int, tightening_factor: float) -> bool:
    if tightening_factor < 0.50:
        return index % 4 == 0
    if tightening_factor < 0.80:
        return index % 2 == 0
    return True


def _pre_drop_survivor_positions(
    plan: PhrasePlan, drop_bar: int, plan_bars: int,
) -> list[tuple[int, int]]:
    positions: list[tuple[int, int]] = []
    drop_pbar = _plan_bar(drop_bar, plan_bars)
    cycle_start = drop_bar - (drop_pbar - 1)
    window_start = cycle_start
    for bar in range(cycle_start, drop_bar):
        if plan.phrase_state.get(_plan_bar(bar, plan_bars)) == PhraseState.DROP_RELOCK:
            window_start = bar + 1
    for bar in range(window_start, drop_bar + 1):
        pbar = _plan_bar(bar, plan_bars)
        for step in plan.silence_mask.muted_steps_by_bar.get(pbar, ()):
            if bar < drop_bar or step < DROP_STEP:
                positions.append((bar, step))
    return sorted(set(positions))


def _position_label(position: tuple[int, int] | None) -> str | None:
    if position is None:
        return None
    bar, step = position
    return f"{bar}.{step}"


def _survivor_event(
    template: MIDIEvent,
    time_str: str,
    note: int,
    velocity: int,
    layer: str,
    tightening: float,
) -> MIDIEvent:
    return replace(
        template,
        time=time_str,
        note=note,
        velocity=velocity,
        duration=SURVIVOR_DURATION,
        layer=layer,
        role="survivor",
        emphasis=0.05,
        openness=0.0,
        expected_weight=0.0,
        should_resolve=False,
        active=True,
        survives_silence=True,
        structural_authority=False,
        deformation={"survivor_signal": round(tightening, 3)},
    )


def add_survivor_signal(bank: Bank, plan: PhrasePlan) -> dict:
    """Add a low-amplitude timing carrier inside pre-drop silence windows.

    Survivor events are explicitly marked so Phase 6 silence enforcement can
    preserve them. They carry no structural authority and never replace kick,
    bass, hook, or groove events.
    """
    stats = {
        "survivor_events_before_drop": 0,
        "survivor_drop_regions": 0,
        "survivor_ticks_generated": 0,
        "silence_window_start": None,
        "silence_window_end": None,
        "drop_step": DROP_STEP,
        "survivor_render_lane": SURVIVOR_RENDER_LANE,
        "survivor_render_lanes": [SURVIVOR_RENDER_LANE],
        "survivor_lane_priority": list(SURVIVOR_LANE_PRIORITY),
        "survivor_windows": [],
    }
    plan_bars = _plan_bars(plan)
    existing = _existing_event_keys(bank)
    template = _source_template(bank)

    bank_bars = {
        time_to_bar_step(event.time)[0]
        for phrase in bank.phrases
        for event in phrase.events
        if time_to_bar_step(event.time)[0] >= 1
    }
    for drop_bar in sorted(bank_bars | set(range(1, plan_bars + 1))):
        pbar = _plan_bar(drop_bar, plan_bars)
        if plan.phrase_state.get(pbar) != PhraseState.DROP_RELOCK:
            continue
        positions = _pre_drop_survivor_positions(plan, drop_bar, plan_bars)
        if not positions:
            continue
        stats["survivor_drop_regions"] += 1
        stats["silence_window_start"] = stats["silence_window_start"] or _position_label(positions[0])
        stats["silence_window_end"] = _position_label(positions[-1])
        stats["survivor_windows"].append({
            "start": _position_label(positions[0]),
            "end": _position_label(positions[-1]),
            "drop_step": DROP_STEP,
            "drop_bar": drop_bar,
        })
        total = max(1, len(positions) - 1)
        for idx, (bar, step) in enumerate(positions):
            tightening = idx / total
            if not _survivor_step_selected(idx, tightening):
                continue
            time_str = _step_to_time(bar, step)
            velocity = _survivor_velocity(tightening)
            emitted = 0
            render_specs = _survivor_render_specs(step, tightening)
            for layer, note, multiplier in (
                ("survivor", SURVIVOR_NOTE, 0.0),
                *render_specs,
            ):
                key = (time_str, layer, "survivor")
                if key in existing:
                    continue
                event_velocity = 0 if layer == "survivor" else max(1, int(velocity * multiplier))
                event = _survivor_event(
                    template, time_str, note, event_velocity, layer, tightening
                )
                _append_to_bar(bank, event)
                existing.add(key)
                emitted += 1
                stats["survivor_events_before_drop"] += 1
                if layer != "survivor" and layer not in stats["survivor_render_lanes"]:
                    stats["survivor_render_lanes"].append(layer)
            if emitted:
                stats["survivor_ticks_generated"] += 1
    return stats


# ---------------------------------------------------------------------------
# Drop construction rules
# ---------------------------------------------------------------------------

def _ensure_bass_at_drop(
    bank: Bank, plan: PhrasePlan, bar: int,
    bar_events: list[MIDIEvent], stats: DropStats,
) -> None:
    """Assert bass tonal centre at the drop step (step 4)."""
    if _has_layer_at_step(bar_events, bar, DROP_STEP, "bass"):
        return  # already present
    pitch = _planned_pitch(plan, bar, "bass")
    if pitch is None:
        return
    tmpl = _source_template(bank)
    if tmpl is None:
        return
    bass_event = replace(
        tmpl,
        time=_step_to_time(bar, DROP_STEP),
        note=pitch,
        velocity=DROP_BASS_VELOCITY,
        duration=0.14,
        layer="bass",
        role="bass",
        emphasis=0.90,
        openness=0.0,
        expected_weight=1.0,
        should_resolve=False,
        active=True,
        deformation={"drop_relock": 1.0},
    )
    _append_to_bar(bank, bass_event)
    stats.drop_relock_events_added += 1


def _ensure_kick_at_drop(
    bank: Bank, bar: int, bar_events: list[MIDIEvent], stats: DropStats,
) -> None:
    """Assert kick presence at the drop step."""
    if _has_layer_at_step(bar_events, bar, DROP_STEP, "kick"):
        return
    tmpl = _source_template(bank)
    if tmpl is None:
        return
    kick_event = replace(
        tmpl,
        time=_step_to_time(bar, DROP_STEP),
        note=KICK_NOTE,
        velocity=DROP_KICK_VELOCITY,
        duration=0.08,
        layer="kick",
        role="anchor",
        emphasis=1.0,
        openness=0.8,
        expected_weight=1.0,
        should_resolve=False,
        active=True,
        deformation={"drop_relock": 1.0},
    )
    _append_to_bar(bank, kick_event)
    stats.drop_relock_events_added += 1


def _ensure_hook_at_drop(
    bank: Bank, plan: PhrasePlan, bar: int,
    bar_events: list[MIDIEvent], stats: DropStats,
) -> None:
    """Assert hook identity at or near the drop step."""
    if _has_layer_at_step(bar_events, bar, DROP_STEP, "hook"):
        return
    pitch = _planned_pitch(plan, bar, "hook")
    if pitch is None:
        return
    tmpl = _source_template(bank)
    if tmpl is None:
        return
    hook_event = replace(
        tmpl,
        time=_step_to_time(bar, DROP_STEP),
        note=pitch,
        velocity=DROP_HOOK_VELOCITY,
        duration=0.10,
        layer="hook",
        role="hook",
        emphasis=0.85,
        openness=0.6,
        expected_weight=0.9,
        should_resolve=False,
        active=True,
        deformation={"drop_relock": 1.0},
    )
    _append_to_bar(bank, hook_event)
    stats.drop_relock_events_added += 1


def _check_pre_drop_contrast(
    bank: Bank, plan: PhrasePlan, drop_bar: int,
    plan_bars: int, stats: DropStats,
) -> None:
    """Verify silence or low density precedes the drop.

    A DROP_RELOCK bar must be preceded by contrast.  Contrast exists if:
    - the previous bar has state HOLD_SILENCE, or
    - the previous bar has very low event density (≤ 3 events).
    """
    prev_bar = drop_bar - 1
    if prev_bar < 1:
        return  # no preceding bar in this bank

    prev_pbar = _plan_bar(prev_bar, plan_bars)
    prev_state = plan.phrase_state.get(prev_pbar)
    if prev_state == PhraseState.HOLD_SILENCE:
        return  # silence precedes drop — good contrast

    prev_density = _bar_density(bank, prev_bar)
    if prev_density <= 3:
        return  # low density — acceptable contrast

    stats.drop_missing_contrast += 1


def _suppress_illegal_events(
    bank: Bank, plan: PhrasePlan, drop_bar: int,
    plan_bars: int, stats: DropStats,
) -> None:
    """Remove events that must not exist in a DROP_RELOCK bar.

    Illegal in DROP_RELOCK:
    1. Call/response role events — unresolved structural material.
    2. Echo-style events: non-authority events at the same step/pitch as
       bass/hook but at lower velocity (< ECHO_VELOCITY_THRESHOLD).
    """
    pbar = _plan_bar(drop_bar, plan_bars)

    # Collect authority events for echo detection
    authority_by_step_pitch: dict[tuple[int, int], int] = {}
    for phrase in bank.phrases:
        for e in phrase.events:
            b, s = time_to_bar_step(e.time)
            if b == drop_bar and e.layer in {"bass", "hook"}:
                authority_by_step_pitch[(s, e.note)] = e.velocity

    for phrase in bank.phrases:
        kept: list[MIDIEvent] = []
        for e in phrase.events:
            b, s = time_to_bar_step(e.time)
            if b != drop_bar:
                kept.append(e)
                continue

            # 1. Suppress unresolved call/response
            role = e.role.lower()
            if "call" in role or "response" in role:
                stats.drop_illegal_events_suppressed += 1
                continue

            # 2. Suppress echo-style lower-velocity authority copies
            if e.layer not in {"bass", "hook", "kick"}:
                key = (s, e.note)
                if key in authority_by_step_pitch:
                    auth_vel = authority_by_step_pitch[key]
                    if e.velocity < auth_vel * ECHO_VELOCITY_THRESHOLD:
                        stats.drop_illegal_events_suppressed += 1
                        continue

            kept.append(e)
        phrase.events = kept


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def enforce_drop_relock(
    bank: Bank,
    plan: PhrasePlan,
    commit_state: DropCommitState | None = None,
    syntax_stats: dict | None = None,
) -> dict[str, int | str]:
    """Enforce DROP_RELOCK construction and compliance.

    Must be called AFTER all Phase 3-8 passes have completed.

    For each DROP_RELOCK bar:
      1. Suppress illegal events (call/response leakage, echo copies)
      2. Ensure bass presence at the drop step (adds if missing)
      3. Ensure kick presence at the drop step (adds if missing)
      4. Ensure hook presence at the drop step (adds if missing)
      5. Check for pre-drop contrast

    Events added by this pass are planner-authorised reassertions of
    planned bass/hook identity at the structurally required step.
    """
    stats = DropStats()
    if syntax_stats:
        stats.normal_events_suppressed_before_drop = int(
            syntax_stats.get("events_blocked_by_silence", 0)
        )
    if commit_state is None:
        commit_state = DropCommitState()
    plan_bars = _plan_bars(plan)

    # Collect bars actually present in the bank, then add any bars that map
    # to a DROP_RELOCK plan bar but may have had all events removed already.
    bank_bars: set[int] = set()
    for phrase in bank.phrases:
        for e in phrase.events:
            b, _ = time_to_bar_step(e.time)
            if b >= 1:
                bank_bars.add(b)
    # Also include bars that map to a DROP_RELOCK plan bar (they may be empty
    # but still need bass/kick/hook added)
    for bar in list(bank_bars) + list(range(1, plan_bars + 1)):
        bank_bars.add(bar)

    for bar in sorted(bank_bars):
        pbar = _plan_bar(bar, plan_bars)
        state = plan.phrase_state.get(pbar)
        if state != PhraseState.DROP_RELOCK:
            continue

        stats.drop_regions_detected += 1
        committed, before, pending, after = commit_state.commit_once(
            f"{bank.bank_index}:{bar}:{DROP_STEP}"
        )
        if stats.active_state_before == "":
            stats.active_state_before = before
            stats.pending_state = pending
        if committed:
            stats.commit_applied += 1
        stats.active_state_after = after

        # Illegal event suppression runs first (before we add new events)
        _suppress_illegal_events(bank, plan, bar, plan_bars, stats)

        # Snapshot bar events after suppression
        bar_events = _events_for_bar(bank, bar)

        # Structural presence at the drop step
        _ensure_bass_at_drop(bank, plan, bar, bar_events, stats)
        _ensure_kick_at_drop(bank, bar, bar_events, stats)
        _ensure_hook_at_drop(bank, plan, bar, bar_events, stats)
        refreshed = _events_for_bar(bank, bar)
        if _has_layer_at_step(refreshed, bar, DROP_STEP, "kick"):
            stats.kick_at_drop += 1
        if _has_layer_at_step(refreshed, bar, DROP_STEP, "bass"):
            stats.bass_at_drop += 1

        # Pre-drop contrast check
        _check_pre_drop_contrast(bank, plan, bar, plan_bars, stats)

    return stats.to_dict()
