from __future__ import annotations

from dataclasses import dataclass

from thelmic.bank_generator import Bank, MIDIEvent
from thelmic.phrase_plan import PhrasePlan, PhraseState

TICKS_PER_BEAT = 24
TICKS_PER_BAR = 96
TICKS_PER_STEP = 6


@dataclass
class SyntaxFilterStats:
    events_blocked_by_silence: int = 0
    events_outside_call_slots: int = 0
    events_outside_response_slots: int = 0
    syntax_filtered_events_total: int = 0

    def to_dict(self) -> dict[str, int]:
        return {
            "events_blocked_by_silence": self.events_blocked_by_silence,
            "events_outside_call_slots": self.events_outside_call_slots,
            "events_outside_response_slots": self.events_outside_response_slots,
            "syntax_filtered_events_total": self.syntax_filtered_events_total,
        }


def time_to_bar_step(time_str: str) -> tuple[int, int]:
    parts = time_str.split(".")
    bar = int(parts[0])
    beat = int(parts[1])
    tick = int(parts[2]) if len(parts) > 2 else 0
    tick_in_bar = (beat - 1) * TICKS_PER_BEAT + tick
    if tick_in_bar % TICKS_PER_STEP != 0:
        return bar, -1
    return bar, tick_in_bar // TICKS_PER_STEP


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
    bar, step = time_to_bar_step(event.time)
    if step < 0:
        return False

    pbar = _plan_bar(bar, plan_bars)
    muted_steps = set(plan.silence_mask.muted_steps_by_bar.get(pbar, ()))
    if step in muted_steps:
        stats.events_blocked_by_silence += 1
        return True

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


def enforce_phrase_syntax(bank: Bank, plan: PhrasePlan) -> dict[str, int]:
    """Remove events that violate PhrasePlan syntax authority."""
    stats = SyntaxFilterStats()
    plan_bars = max(
        [1, *plan.phrase_state.keys(), *plan.call_slots.keys(),
         *plan.response_slots.keys(), *plan.silence_mask.muted_steps_by_bar.keys()]
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
