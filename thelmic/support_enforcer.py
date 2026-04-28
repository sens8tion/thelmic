"""Phase 8 — Supporting layer compliance.

Supporting layers (drums, hats, ghost events, anchor withholding events,
decorative stabs, FX events) must be compliant consumers of PhrasePlan.

They may add texture, motion, emphasis, and colour.
They must not invent phrase structure.

This pass runs AFTER enforce_phrase_syntax (Phase 6).  Events that reach
here have already passed silence and slot compliance.  This pass is a
safety net and audit layer — it counts, classifies, and where necessary
removes residual supporting-layer violations.

Checks applied to each supporting event:
  1. Silence:    event must not be in a muted step (Phase 6 removes these;
                 this counter proves Phase 6 coverage by staying at 0).
  2. Role:       supporting events must not carry call/response roles that
                 slipped through Phase 4/5/6 slot validation.
  3. Authority:  non-drum supporting events must not collide with a bass or
                 hook event at the same step/bar, where they could obscure
                 tonal or identity authority.

Supporting event definition:
  Any event whose layer is not "bass" or "hook" AND whose role does not
  contain "call" or "response" (those are handled by Phase 4/5).
  Drum events (kick, snare, hat) are supporting but are exempt from
  authority collision suppression (kick + bass co-occurrence is normal).

Density compensation:
  This pass only suppresses.  It never adds events to fill gaps.
  Do not add compensatory events here.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from thelmic.bank_generator import Bank, MIDIEvent
from thelmic.phrase_plan import PhrasePlan
from thelmic.syntax_enforcer import time_to_bar_step, _plan_bar

TICKS_PER_BEAT = 24
TICKS_PER_STEP = 6

# Layers that are planner-owned first-class authority
AUTHORITY_LAYERS: frozenset[str] = frozenset({"bass", "hook"})

# Drum layers are supporting but exempt from authority-collision suppression
DRUM_LAYERS: frozenset[str] = frozenset({"kick", "snare", "hat"})


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

@dataclass
class SupportLayerStats:
    support_events_checked:                int = 0
    support_events_suppressed:             int = 0
    support_events_suppressed_by_silence:  int = 0   # should be 0 after Phase 6
    support_events_suppressed_by_role:     int = 0
    support_events_suppressed_by_authority: int = 0

    def to_dict(self) -> dict[str, int]:
        return {
            "support_events_checked":                 self.support_events_checked,
            "support_events_suppressed":              self.support_events_suppressed,
            "support_events_suppressed_by_silence":   self.support_events_suppressed_by_silence,
            "support_events_suppressed_by_role":      self.support_events_suppressed_by_role,
            "support_events_suppressed_by_authority": self.support_events_suppressed_by_authority,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_supporting(event: MIDIEvent) -> bool:
    """Return True for supporting (non-authority, non-structural) events."""
    if event.layer in AUTHORITY_LAYERS:
        return False
    role = event.role.lower()
    if "call" in role or "response" in role:
        return False   # structural role — Phase 4/5/6 owns these
    return True


def _role_is_structural(event: MIDIEvent) -> bool:
    """Return True if event carries a structural role (call/response) that
    should have been caught by Phase 4/5/6 validation."""
    role = event.role.lower()
    return "call" in role or "response" in role


def _build_authority_steps(bank: Bank) -> set[tuple[int, int]]:
    """Return {(bar, step)} for all bass and hook events in the bank."""
    authority: set[tuple[int, int]] = set()
    for event in bank.all_events():
        if event.layer not in AUTHORITY_LAYERS:
            continue
        bar, step = time_to_bar_step(event.time)
        if step >= 0:
            authority.add((bar, step))
    return authority


def _is_in_silence(event: MIDIEvent, plan: PhrasePlan, plan_bars: int) -> bool:
    """Check whether the event's step is inside the silence mask."""
    bar, step = time_to_bar_step(event.time)
    if step < 0:
        # Use floor-step for off-grid events (matches Phase 6 logic)
        parts = event.time.split(".")
        bar  = int(parts[0])
        beat = int(parts[1])
        tick = int(parts[2]) if len(parts) > 2 else 0
        tick_in_bar = (beat - 1) * TICKS_PER_BEAT + tick
        step = min(15, max(0, tick_in_bar // TICKS_PER_STEP))
    pbar   = _plan_bar(bar, plan_bars)
    muted  = set(plan.silence_mask.muted_steps_by_bar.get(pbar, ()))
    return step in muted


def _should_suppress_supporting(
    event: MIDIEvent,
    plan: PhrasePlan,
    plan_bars: int,
    authority_steps: set[tuple[int, int]],
    stats: SupportLayerStats,
) -> bool:
    """Return True (and update stats) if this supporting event must be removed."""
    if event.role == "survivor" and bool(getattr(event, "survives_silence", False)):
        return False

    # 1. Silence check — should be 0 after Phase 6; counted for audit completeness.
    if _is_in_silence(event, plan, plan_bars):
        stats.support_events_suppressed_by_silence += 1
        stats.support_events_suppressed += 1
        return True

    # 2. Role check — supporting events must not carry structural roles.
    #    Phase 4/5/6 should have handled all call/response events; a non-zero
    #    count here indicates a gap in earlier compliance passes.
    if _role_is_structural(event):
        stats.support_events_suppressed_by_role += 1
        stats.support_events_suppressed += 1
        return True

    # 3. Authority-collision check — non-drum supporting events at the same
    #    step as a bass or hook event could obscure tonal/identity authority.
    if event.layer not in DRUM_LAYERS:
        bar, step = time_to_bar_step(event.time)
        if step >= 0 and (bar, step) in authority_steps:
            stats.support_events_suppressed_by_authority += 1
            stats.support_events_suppressed += 1
            return True

    return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def enforce_supporting_layer_compliance(
    bank: Bank, plan: PhrasePlan,
) -> dict[str, int]:
    """Enforce PhrasePlan compliance for supporting-layer events.

    Runs AFTER enforce_phrase_syntax (Phase 6).  Checks events that are not
    first-class planner-owned (not bass, not hook, not call/response) for:
      - residual silence violations
      - structural role mis-labelling
      - authority collision with bass/hook events

    Never adds events.  Never compensates for suppressed events.
    Returns a dict of counters for debug broadcast.
    """
    stats = SupportLayerStats()

    plan_bars = max(
        [1,
         *plan.phrase_state.keys(),
         *plan.call_slots.keys(),
         *plan.response_slots.keys(),
         *plan.silence_mask.muted_steps_by_bar.keys()]
    )

    # Snapshot bass/hook step positions before mutating the bank.
    authority_steps = _build_authority_steps(bank)

    for phrase in bank.phrases:
        kept: list[MIDIEvent] = []
        for event in phrase.events:
            if not _is_supporting(event):
                kept.append(event)
                continue

            stats.support_events_checked += 1

            if _should_suppress_supporting(event, plan, plan_bars, authority_steps, stats):
                continue

            kept.append(event)
        phrase.events = kept

    return stats.to_dict()
