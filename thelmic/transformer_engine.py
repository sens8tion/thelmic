"""Transformer execution engine.

Reads transformer metadata from sub-phrase definitions, applies rule-defined
mutations via static action handlers, and validates every proposed change
through the motif mutation validator.

Pipeline
--------
  motif_engine (observe)
    → transformer_engine (execute)
      → classify_motif_change (validate)
        → bank (apply or reject)

Separation of concerns
----------------------
  motif_engine        — describes structure; never mutates
  transformer_engine  — executes rule-defined mutations; calls the validator
  bank_generator      — holds final event state

Hard constraints (from musical_rules.md)
----------------------------------------
  - No action may target an instrument not listed for that transformer.
  - No mutation may be applied until classify_motif_change returns LEGAL.
  - No randomness.
  - No runtime parsing of musical_rules.md.

v1.0 status
-----------
  Action handlers are stubs.  No mutations are currently proposed, so the
  validator is never triggered and bank content is always returned unchanged.
  Future work fills in the handlers.  The pipeline, tables, and result schema
  are fully wired.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from thelmic.bank_generator import Bank
from thelmic.motif_engine import Motif, classify_motif_change


VERSION = "v1.1"   # add_subdivision still deferred; velocity+simplify now live

# ---------------------------------------------------------------------------
# Static execution tables (mirror musical_rules.md; no markdown parsed at runtime)
# ---------------------------------------------------------------------------

# Transformer → allowed target instruments.
# Only instruments listed here may be acted on for a given transformer.
TRANSFORMER_TARGETS: dict[str, list[str]] = {
    "density_increase":    ["kick", "snare", "hat"],
    "density_hold":        ["kick", "snare", "hat"],
    "density_thin":        ["kick", "snare", "hat"],
    "stabilise":           ["kick", "snare", "hat"],
    "destabilise":         ["hat"],
    "kick_emphasis":       ["kick"],
    "snare_suppression":   ["snare"],
    "hat_drive":           ["hat"],
    "anticipation_build":  ["hat", "kick"],
    "pre_drop_non_silent": ["kick", "snare", "hat"],
    "withholding":         ["snare", "hat"],
    "release_resolve":     ["kick", "snare", "hat"],
    "release_thin":        ["hat", "snare"],
    "relock":              ["kick"],
}

# Transformer → allowed action identifiers for each transformer.
# These name what the transformer is permitted to do; they do not dictate
# the implementation (see _ACTION_HANDLERS below).
TRANSFORMER_ACTIONS: dict[str, list[str]] = {
    "density_increase":    ["add_subdivision"],
    "density_hold":        ["maintain_pattern"],
    "density_thin":        ["remove_subdivision"],
    "stabilise":           ["simplify_pattern"],
    "destabilise":         ["add_offbeat"],
    "kick_emphasis":       ["increase_velocity"],
    "snare_suppression":   ["reduce_velocity"],
    "hat_drive":           ["add_subdivision"],
    "anticipation_build":  ["add_subdivision"],
    "pre_drop_non_silent": ["maintain_pattern"],
    "withholding":         ["remove_subdivision"],
    "release_resolve":     ["restore_pattern"],
    "release_thin":        ["remove_subdivision"],
    "relock":              ["maintain_pattern"],
}


# ---------------------------------------------------------------------------
# Execution result
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TransformerExecutionResult:
    phrase_index:   int
    subphrase_role: str
    transformer:    str
    target_lane:    str
    action:         str
    step_or_range:  dict     # {"start": int, "end": int} — sub-phrase window attempted
    accepted:       bool
    reason:         str

    @property
    def target(self) -> str:
        return self.target_lane

    def to_dict(self) -> dict:
        return {
            "phrase_index":   self.phrase_index,
            "subphrase_role": self.subphrase_role,
            "transformer":    self.transformer,
            "target_lane":    self.target_lane,
            "action":         self.action,
            "step_or_range":  self.step_or_range,
            "accepted":       self.accepted,
            "reason":         self.reason,
        }


# ---------------------------------------------------------------------------
# Action handlers
# ---------------------------------------------------------------------------
# Returns: (motif_before, proposed_refs, reason, apply_fn | None)
# apply_fn() mutates the bank in place — called only after LEGAL validation.
# (None, None, reason, None) = no proposal; validator not called.

from typing import Callable

_ActionResult = tuple[
    "Motif | None",
    "list[str] | None",
    str,
    "Callable[[], None] | None",
]


def _event_ref(event) -> str:
    return event.resolved_event_id or event.intent_id


def _window_events(bank: Bank, layer: str, start: int, end: int):
    """Events for the given layer within the musical_step window [start, end)."""
    return [
        e for phrase in bank.phrases
        for e in phrase.events
        if e.layer == layer and start <= e.musical_step < end
    ]


def _handle_action(
    action:               str,
    bank:                 Bank,
    target:               str,
    subphrase_start_step: int,
    subphrase_end_step:   int,
    motifs_by_instrument: dict[str, Motif],
) -> _ActionResult:

    motif = motifs_by_instrument.get(target)

    # ── maintain_pattern ────────────────────────────────────────────────────
    if action == "maintain_pattern":
        # No change — propose current refs; validator will return LEGAL (0 delta).
        if motif is None:
            return None, None, "no_motif_for_target", None
        return motif, list(motif.event_references), "pattern_maintained", None

    # ── remove_subdivision ──────────────────────────────────────────────────
    if action == "remove_subdivision":
        if motif is None:
            return None, None, "no_motif_for_target", None
        # Only thin non-structural layers to preserve musical backbone
        if target in ("kick", "snare", "bass"):
            return None, None, "structural_layer_protected", None
        events = _window_events(bank, target, subphrase_start_step, subphrase_end_step)
        # Need at least 2 events to thin (never remove the last one)
        removable = [e for e in events if not getattr(e, "structural_authority", False)]
        if len(removable) < 2:
            return None, None, "too_few_events_to_thin", None
        # Remove the quietest non-anchor event
        to_remove = min(removable, key=lambda e: e.velocity)
        ref       = _event_ref(to_remove)
        proposed  = [r for r in motif.event_references if r != ref]

        def apply_remove():
            for phrase in bank.phrases:
                phrase.events = [e for e in phrase.events if e is not to_remove]

        return motif, proposed, "remove_subdivision", apply_remove

    # ── add_subdivision ─────────────────────────────────────────────────────
    if action == "add_subdivision":
        # Deferred — Phase 8 (Transformer evolution / Mutation system).
        #
        # To add events we need to invoke voice intent streams (kick, snare, hat)
        # at specific steps, which requires full phrase context and arc state.
        # Implementing here would duplicate the generation pipeline.
        #
        # Correct implementation path:
        #   1. generate_bank produces a bank with current voice output
        #   2. transformer_engine proposes a NEW bank step using the voice stream
        #   3. classify_motif_change validates the delta (≤1 event = LEGAL)
        #   4. apply_fn inserts the new event
        #
        # Until Phase 8 is scheduled, anticipation_build and hat_drive
        # gracefully no-op here (pre-drop hat thinning still handled by
        # anticipation_engine.py which operates at generation time).
        return None, None, "add_requires_voice_context_phase8", None

    # ── increase_velocity ───────────────────────────────────────────────────
    if action == "increase_velocity":
        if motif is None:
            return None, None, "no_motif_for_target", None
        import dataclasses
        events = _window_events(bank, target, subphrase_start_step, subphrase_end_step)
        if not events:
            return None, None, "no_events_in_window", None

        def apply_increase():
            for phrase in bank.phrases:
                new_events = []
                for e in phrase.events:
                    if e in events and e.layer == target:
                        new_vel = min(127, int(e.velocity * 1.15))
                        new_events.append(dataclasses.replace(e, velocity=new_vel))
                    else:
                        new_events.append(e)
                phrase.events = new_events

        # Velocity changes don't alter event refs — always legal
        return motif, list(motif.event_references), "increase_velocity", apply_increase

    # ── reduce_velocity ─────────────────────────────────────────────────────
    if action == "reduce_velocity":
        if motif is None:
            return None, None, "no_motif_for_target", None
        import dataclasses
        events = _window_events(bank, target, subphrase_start_step, subphrase_end_step)
        if not events:
            return None, None, "no_events_in_window", None

        def apply_reduce():
            for phrase in bank.phrases:
                new_events = []
                for e in phrase.events:
                    if e in events and e.layer == target:
                        new_vel = max(15, int(e.velocity * 0.75))
                        new_events.append(dataclasses.replace(e, velocity=new_vel))
                    else:
                        new_events.append(e)
                phrase.events = new_events

        return motif, list(motif.event_references), "reduce_velocity", apply_reduce

    # ── simplify_pattern ───────────────────────────────────────────────────
    if action == "simplify_pattern":
        if motif is None:
            return None, None, "no_motif_for_target", None
        events   = _window_events(bank, target, subphrase_start_step, subphrase_end_step)
        anchors  = [e for e in events if getattr(e, "structural_authority", False)]
        non_anch = [e for e in events if not getattr(e, "structural_authority", False)]
        if not non_anch:
            return None, None, "already_simplified", None
        # Remove one non-anchor per call (legal mutation: single event)
        to_remove = non_anch[0]
        ref       = _event_ref(to_remove)
        proposed  = [r for r in motif.event_references if r != ref]

        def apply_simplify():
            for phrase in bank.phrases:
                phrase.events = [e for e in phrase.events if e is not to_remove]

        return motif, proposed, "simplify_pattern", apply_simplify

    # ── restore_pattern ────────────────────────────────────────────────────
    if action == "restore_pattern":
        # Restoration requires knowing what was removed — not tracked.
        # Use maintain_pattern as fallback (no-op).
        if motif is None:
            return None, None, "no_motif_for_target", None
        return motif, list(motif.event_references), "restore_maintained", None

    return None, None, "unknown_action", None


# ---------------------------------------------------------------------------
# Public execution function
# ---------------------------------------------------------------------------

def execute_transformers(
    bank:       Bank,
    motifs:     Sequence[Motif],
    subphrases: list[dict],
) -> tuple[Bank, list[TransformerExecutionResult]]:
    """Execute all transformers attached to sub-phrases.

    For each (transformer, target, action) triple:
      1.  Propose a mutation via the action handler.
      2.  If a proposal exists, validate via classify_motif_change.
      3.  If LEGAL, apply to bank in place.  If STRUCTURAL, reject.
      4.  Record the result.
    """
    motifs_by_instrument: dict[str, Motif] = {
        m.instrument: m for m in motifs
        if m.state == "observed"
    }
    results: list[TransformerExecutionResult] = []

    for sp in subphrases:
        sp_start       = sp["start_step"]
        sp_end         = sp_start + sp["length_steps"] - 1
        phrase_index   = sp.get("phrase_index", 0)
        step_or_range  = {"start": sp_start, "end": sp_end}

        for tx in sp.get("transformers", []):
            name    = tx["name"]
            targets = TRANSFORMER_TARGETS.get(name, [])
            actions = TRANSFORMER_ACTIONS.get(name, [])

            for target in targets:
                for action in actions:
                    motif_before, proposed_refs, proposal_reason, apply_fn = _handle_action(
                        action, bank, target,
                        sp_start, sp_end + 1,
                        motifs_by_instrument,
                    )

                    if motif_before is None or proposed_refs is None:
                        results.append(TransformerExecutionResult(
                            phrase_index=phrase_index,
                            subphrase_role=sp["role"],
                            transformer=name,
                            target_lane=target,
                            action=action,
                            step_or_range=step_or_range,
                            accepted=False,
                            reason=proposal_reason,
                        ))
                        continue

                    validation = classify_motif_change(motif_before, proposed_refs)

                    if validation.is_legal and apply_fn is not None:
                        apply_fn()

                    results.append(TransformerExecutionResult(
                        phrase_index=phrase_index,
                        subphrase_role=sp["role"],
                        transformer=name,
                        target_lane=target,
                        action=action,
                        step_or_range=step_or_range,
                        accepted=validation.is_legal,
                        reason=validation.reason,
                    ))

    return bank, results
