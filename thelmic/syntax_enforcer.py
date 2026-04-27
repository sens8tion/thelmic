"""Phase syntax enforcement — silence mask and slot compliance.

Silence is a hard constraint. It overrides call_slots, response_slots,
behaviour_field output, and deformation output. Nothing overrides silence.

Enforcement order per event (both checks always happen in order):
  1. Silence mask  — absolute; suppresses all layers including kick.
  2. Slot checks   — call/response events must be inside their planned slots.

Off-grid events (tick not aligned to a 16th-note step) are checked for
silence via floor-step mapping so that events between step boundaries are
still caught when the containing step is muted.

Phase 6 contract:
  - All layers are silenced by silence_mask.
  - No generator or behaviour module may override silence.
  - Pression, behaviour_field, and deformations must not bypass silence.
  - Kick may be exempt if required for timing stability; exemption must be
    explicit and is currently NOT applied — kick is silenced like all layers.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from thelmic.bank_generator import Bank, MIDIEvent
from thelmic.phrase_plan import PhrasePlan, PhraseState

TICKS_PER_BEAT = 24
TICKS_PER_BAR  = 96
TICKS_PER_STEP = 6


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

@dataclass
class SyntaxFilterStats:
    # Silence stats (Phase 6)
    events_blocked_by_silence:          int = 0
    silence_regions_active:             int = 0   # bars in plan with any muted steps
    events_blocked_by_silence_by_layer: dict = field(default_factory=dict)

    # Slot compliance stats (Phases 3-5)
    events_outside_call_slots:     int = 0
    events_outside_response_slots: int = 0
    syntax_filtered_events_total:  int = 0

    def to_dict(self) -> dict:
        return {
            "events_blocked_by_silence":          self.events_blocked_by_silence,
            "silence_regions_active":              self.silence_regions_active,
            "events_blocked_by_silence_by_layer": dict(self.events_blocked_by_silence_by_layer),
            "events_outside_call_slots":           self.events_outside_call_slots,
            "events_outside_response_slots":       self.events_outside_response_slots,
            "syntax_filtered_events_total":        self.syntax_filtered_events_total,
        }


# ---------------------------------------------------------------------------
# Time helpers
# ---------------------------------------------------------------------------

def time_to_bar_step(time_str: str) -> tuple[int, int]:
    """Parse a time string to (bar, step).  step = -1 if off-grid."""
    parts = time_str.split(".")
    bar  = int(parts[0])
    beat = int(parts[1])
    tick = int(parts[2]) if len(parts) > 2 else 0
    tick_in_bar = (beat - 1) * TICKS_PER_BEAT + tick
    if tick_in_bar % TICKS_PER_STEP != 0:
        return bar, -1
    return bar, tick_in_bar // TICKS_PER_STEP


def _time_to_bar_floor_step(time_str: str) -> tuple[int, int]:
    """Parse a time string to (bar, step) using floor division.

    Unlike time_to_bar_step, this never returns step=-1 — off-grid ticks
    are mapped to the step they fall inside.  Used for silence checking so
    that events between step boundaries are still caught when the containing
    step is muted.
    """
    parts = time_str.split(".")
    bar  = int(parts[0])
    beat = int(parts[1])
    tick = int(parts[2]) if len(parts) > 2 else 0
    tick_in_bar = (beat - 1) * TICKS_PER_BEAT + tick
    step = min(15, max(0, tick_in_bar // TICKS_PER_STEP))
    return bar, step


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _plan_bar(bar: int, plan_bars: int) -> int:
    return ((bar - 1) % max(1, plan_bars)) + 1


def _role_kind(event: MIDIEvent) -> str | None:
    role = event.role.lower()
    if "response" in role:
        return "response"
    if "call" in role:
        return "call"
    return None


def _state_allows_role(state: PhraseState | None, role_kind: str) -> bool:
    if role_kind == "call":
        return state == PhraseState.CALL_UNRESOLVED
    if role_kind == "response":
        return state == PhraseState.RESPONSE_RESOLVED
    return True


def _should_filter_event(
    event: MIDIEvent,
    plan: PhrasePlan,
    stats: SyntaxFilterStats,
    plan_bars: int,
    has_any_call_slots: bool,
) -> bool:
    """Return True if this event must be removed from the bank.

    Silence is checked first and is absolute — it overrides all other rules.
    """
    # --- 1. Silence check (absolute; uses floor-step so off-grid events are caught) ---
    bar, floor_step = _time_to_bar_floor_step(event.time)
    pbar = _plan_bar(bar, plan_bars)
    muted_steps = set(plan.silence_mask.muted_steps_by_bar.get(pbar, ()))
    if floor_step in muted_steps:
        stats.events_blocked_by_silence += 1
        layer = getattr(event, "layer", "unknown")
        stats.events_blocked_by_silence_by_layer[layer] = (
            stats.events_blocked_by_silence_by_layer.get(layer, 0) + 1
        )
        return True

    # --- 2. Slot compliance (call / response events must be in planned slots) ---
    _, step = time_to_bar_step(event.time)
    if step < 0:
        # Off-grid, not silenced — leave it in.
        return False

    role_kind = _role_kind(event)
    if role_kind is None:
        return False

    state = plan.phrase_state.get(pbar)
    if not _state_allows_role(state, role_kind):
        if role_kind == "call":
            stats.events_outside_call_slots += 1
        else:
            stats.events_outside_response_slots += 1
        return True

    if role_kind == "call":
        if step not in set(plan.call_slots.get(pbar, ())):
            stats.events_outside_call_slots += 1
            return True
    elif role_kind == "response":
        if not has_any_call_slots or step not in set(plan.response_slots.get(pbar, ())):
            stats.events_outside_response_slots += 1
            return True

    return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def enforce_phrase_syntax(bank: Bank, plan: PhrasePlan) -> dict:
    """Remove events that violate PhrasePlan syntax authority.

    Silence is a hard constraint that overrides all other rules.  All layers
    including bass, hook, kick, snare, hat, stab, call, and response are
    subject to silence filtering.

    Returns a dict of suppression counters for debug broadcast.
    """
    stats = SyntaxFilterStats()

    plan_bars = max(
        [1,
         *plan.phrase_state.keys(),
         *plan.call_slots.keys(),
         *plan.response_slots.keys(),
         *plan.silence_mask.muted_steps_by_bar.keys()]
    )

    # Count how many plan bars have at least one muted step.
    stats.silence_regions_active = sum(
        1 for steps in plan.silence_mask.muted_steps_by_bar.values() if steps
    )

    has_any_call_slots = any(plan.call_slots.values())

    for phrase in bank.phrases:
        kept: list[MIDIEvent] = []
        for event in phrase.events:
            if _should_filter_event(event, plan, stats, plan_bars, has_any_call_slots):
                stats.syntax_filtered_events_total += 1
                continue
            kept.append(event)
        phrase.events = kept

    return stats.to_dict()
