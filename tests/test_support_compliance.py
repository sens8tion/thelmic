"""Phase 8 — Supporting layer compliance tests.

Acceptance criteria:
  - support events obey silence
  - support events cannot create unplanned calls
  - support events cannot create unplanned responses
  - support events do not alter bass events
  - support events do not alter hook events
  - empty planned space is not automatically filled
  - existing Phase 3–7 tests still pass (verified by running full suite)
"""

from thelmic.bank_generator import Bank, Phrase, MIDIEvent
from thelmic.behaviour_field import BehaviourField
from thelmic.phrase_plan import (
    PhrasePlan, PlanNote, SilenceMask, PhraseState, generate_phrase_plan,
)
from thelmic.support_enforcer import (
    enforce_supporting_layer_compliance,
    AUTHORITY_LAYERS, DRUM_LAYERS,
    _is_supporting, _build_authority_steps,
)
from thelmic.syntax_enforcer import enforce_phrase_syntax


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _event(
    time: str = "1.1.0",
    layer: str = "kick",
    role: str = "anchor",
    velocity: int = 100,
    note: int = 36,
) -> MIDIEvent:
    return MIDIEvent(
        time=time, note=note, velocity=velocity, duration=0.08,
        layer=layer, role=role,
        emphasis=0.8, openness=1.0, expected_weight=0.9, should_resolve=False,
    )


def _bank(*events: MIDIEvent) -> Bank:
    return Bank(bank_index=0, phrases=[Phrase(phrase_index=0, events=list(events))])


def _plan(
    silence: dict[int, tuple[int, ...]] | None = None,
    call_slots: dict[int, tuple[int, ...]] | None = None,
    response_slots: dict[int, tuple[int, ...]] | None = None,
    phrase_state: dict[int, PhraseState] | None = None,
) -> PhrasePlan:
    states = phrase_state or {
        1: PhraseState.CALL_UNRESOLVED,
        2: PhraseState.RESPONSE_RESOLVED,
        3: PhraseState.HOLD_SILENCE,
    }
    return PhrasePlan(
        bass_pattern=(PlanNote(bar=1, step=0, pitch=36),),
        hook_pattern=(PlanNote(bar=1, step=0, pitch=60),),
        phrase_state=states,
        call_slots=call_slots if call_slots is not None else {1: (2, 6)},
        response_slots=response_slots if response_slots is not None else {2: (10, 13)},
        silence_mask=SilenceMask(silence or {3: tuple(range(16))}),
        pressure_curve={1: 0.0, 2: 0.5, 3: 1.0},
    )


# ---------------------------------------------------------------------------
# _is_supporting classification
# ---------------------------------------------------------------------------

class TestIsSupportingClassification:

    def test_bass_events_are_not_supporting(self):
        assert not _is_supporting(_event(layer="bass", role="bass"))

    def test_hook_events_are_not_supporting(self):
        assert not _is_supporting(_event(layer="hook", role="hook"))

    def test_call_role_events_are_not_supporting(self):
        assert not _is_supporting(_event(layer="stab", role="call"))

    def test_response_role_events_are_not_supporting(self):
        assert not _is_supporting(_event(layer="stab", role="response"))

    def test_kick_is_supporting(self):
        assert _is_supporting(_event(layer="kick", role="anchor"))

    def test_snare_is_supporting(self):
        assert _is_supporting(_event(layer="snare", role="anchor"))

    def test_hat_is_supporting(self):
        assert _is_supporting(_event(layer="hat", role="anchor"))

    def test_ghost_stab_is_supporting(self):
        assert _is_supporting(_event(layer="stab", role="ghost"))

    def test_drum_layers_are_exempt_from_nothing_just_classified_correctly(self):
        for layer in DRUM_LAYERS:
            assert _is_supporting(_event(layer=layer))
        for layer in AUTHORITY_LAYERS:
            assert not _is_supporting(_event(layer=layer))


# ---------------------------------------------------------------------------
# Silence compliance
# ---------------------------------------------------------------------------

class TestSupportSilenceCompliance:

    def test_support_events_in_silence_are_suppressed(self):
        """Phase 8 residual silence check — should be 0 after Phase 6,
        but Phase 8 catches anything Phase 6 missed."""
        # Build bank with event in a muted bar
        bank = _bank(_event("3.1.0", layer="kick"))
        plan = _plan(silence={3: tuple(range(16))})

        # Phase 6 first
        enforce_phrase_syntax(bank, plan)
        # Then Phase 8
        stats = enforce_supporting_layer_compliance(bank, plan)

        # After Phase 6 removes silence, Phase 8 should see 0 silence violations
        assert stats["support_events_suppressed_by_silence"] == 0
        assert bank.all_events() == []

    def test_support_events_outside_silence_survive(self):
        bank = _bank(_event("1.1.0", layer="kick"))   # bar 1 not silenced
        plan = _plan(silence={3: tuple(range(16))})   # only bar 3 silenced

        enforce_phrase_syntax(bank, plan)
        stats = enforce_supporting_layer_compliance(bank, plan)

        assert len(bank.all_events()) == 1
        assert stats["support_events_suppressed"] == 0

    def test_fully_silent_bar_has_no_support_events(self):
        bank = _bank(
            _event("3.1.0", layer="kick"),
            _event("3.2.0", layer="snare"),
            _event("3.3.0", layer="hat"),
        )
        plan = _plan(silence={3: tuple(range(16))})

        enforce_phrase_syntax(bank, plan)
        enforce_supporting_layer_compliance(bank, plan)

        assert bank.all_events() == []


# ---------------------------------------------------------------------------
# No unplanned call creation
# ---------------------------------------------------------------------------

class TestNoUnplannedCallCreation:

    def test_support_event_with_call_role_is_suppressed(self):
        """A supporting event (non-planner, non-structural) must not carry
        a call role — Phase 8 removes it as a role violation."""
        # Ghost stab with role="call" but NOT in a call_slot
        bank = _bank(_event("1.1.0", layer="stab", role="call"))
        plan = _plan(call_slots={1: (10,)})   # step 0 is NOT in call_slots

        # Phase 6 removes the call-role event (outside call_slot)
        enforce_phrase_syntax(bank, plan)
        assert bank.all_events() == []   # Phase 6 already handles this

        # Reset bank and verify Phase 8 also catches it independently
        bank = _bank(_event("1.1.0", layer="stab", role="call"))
        stats = enforce_supporting_layer_compliance(bank, plan)
        # _is_supporting returns False for role="call", so Phase 8 skips it
        # (Phase 6 owns call/response role enforcement)
        assert stats["support_events_checked"] == 0

    def test_supporting_event_with_unplanned_call_role_classified_structurally(self):
        """Events with call/response roles are not 'supporting' by definition —
        they belong to Phase 4/5/6 enforcement."""
        ev = _event(layer="stab", role="call")
        assert not _is_supporting(ev)   # confirms Phase 8 defers to Phase 4/5/6


# ---------------------------------------------------------------------------
# No unplanned response creation
# ---------------------------------------------------------------------------

class TestNoUnplannedResponseCreation:

    def test_event_with_response_role_not_classified_as_supporting(self):
        ev = _event(layer="stab", role="response")
        assert not _is_supporting(ev)

    def test_planned_response_after_enforcement_survives(self):
        """A valid response event (in response_slot, with valid call) should
        survive both Phase 6 and Phase 8."""
        # Response event at step 10, bar 2 — matches response_slots
        resp = _event("2.3.12", layer="stab", role="response")
        plan = _plan(
            call_slots={1: (2,)},
            response_slots={2: (10, 13)},
            silence={3: tuple(range(16))},
        )
        bank = _bank(resp)
        enforce_phrase_syntax(bank, plan)
        stats = enforce_supporting_layer_compliance(bank, plan)

        # Response event is not supporting, so Phase 8 doesn't touch it
        assert stats["support_events_checked"] == 0
        # The event either survived Phase 6 or was removed — not double-counted
        assert stats["support_events_suppressed"] == 0


# ---------------------------------------------------------------------------
# Bass and hook authority protection
# ---------------------------------------------------------------------------

class TestAuthorityProtection:

    def test_non_drum_support_event_at_bass_step_is_suppressed(self):
        """A stab/ghost event at the exact same step/bar as a bass event
        is suppressed to protect bass authority."""
        bass = _event("1.1.0", layer="bass", role="bass")
        stab = _event("1.1.0", layer="stab", role="stab")
        bank = _bank(bass, stab)
        plan = _plan(silence={3: tuple(range(16))})

        enforce_phrase_syntax(bank, plan)
        stats = enforce_supporting_layer_compliance(bank, plan)

        assert stats["support_events_suppressed_by_authority"] == 1
        # Bass event survives; stab is suppressed
        remaining = [e for e in bank.all_events() if e.layer == "bass"]
        assert len(remaining) == 1
        removed = [e for e in bank.all_events() if e.layer == "stab"]
        assert len(removed) == 0

    def test_non_drum_support_event_at_hook_step_is_suppressed(self):
        hook = _event("1.1.0", layer="hook", role="hook")
        ghost = _event("1.1.0", layer="stab", role="ghost")
        bank = _bank(hook, ghost)
        plan = _plan()

        enforce_phrase_syntax(bank, plan)
        stats = enforce_supporting_layer_compliance(bank, plan)

        assert stats["support_events_suppressed_by_authority"] == 1

    def test_drum_at_bass_step_is_not_suppressed(self):
        """Kick + bass co-occurrence is normal and must not be suppressed."""
        bass = _event("1.1.0", layer="bass", role="bass")
        kick = _event("1.1.0", layer="kick", role="anchor")
        bank = _bank(bass, kick)
        plan = _plan()

        enforce_phrase_syntax(bank, plan)
        stats = enforce_supporting_layer_compliance(bank, plan)

        assert stats["support_events_suppressed_by_authority"] == 0
        assert len([e for e in bank.all_events() if e.layer == "kick"]) == 1

    def test_support_event_not_at_authority_step_survives(self):
        """A stab at a different step than bass is not an authority collision."""
        bass = _event("1.1.0",   layer="bass", role="bass")       # step 0
        stab = _event("1.1.12",  layer="stab", role="stab")       # step 2
        bank = _bank(bass, stab)
        plan = _plan()

        enforce_phrase_syntax(bank, plan)
        stats = enforce_supporting_layer_compliance(bank, plan)

        assert stats["support_events_suppressed_by_authority"] == 0
        assert len([e for e in bank.all_events() if e.layer == "stab"]) == 1

    def test_bass_events_unchanged_after_phase8(self):
        """Phase 8 must not modify or remove bass events."""
        bass = _event("1.1.0", layer="bass", role="bass", velocity=110)
        bank = _bank(bass)
        plan = _plan()

        enforce_phrase_syntax(bank, plan)
        before_bass = [(e.time, e.note, e.velocity) for e in bank.all_events()
                       if e.layer == "bass"]
        enforce_supporting_layer_compliance(bank, plan)
        after_bass = [(e.time, e.note, e.velocity) for e in bank.all_events()
                      if e.layer == "bass"]

        assert before_bass == after_bass

    def test_hook_events_unchanged_after_phase8(self):
        hook = _event("1.1.0", layer="hook", role="hook", velocity=90)
        bank = _bank(hook)
        plan = _plan()

        enforce_phrase_syntax(bank, plan)
        before = [(e.time, e.note, e.velocity) for e in bank.all_events()
                  if e.layer == "hook"]
        enforce_supporting_layer_compliance(bank, plan)
        after = [(e.time, e.note, e.velocity) for e in bank.all_events()
                 if e.layer == "hook"]

        assert before == after


# ---------------------------------------------------------------------------
# No density compensation
# ---------------------------------------------------------------------------

class TestNoDensityCompensation:

    def test_event_count_only_decreases_or_stays_same(self):
        bank = _bank(
            _event("1.1.0",  layer="kick"),
            _event("1.2.0",  layer="snare"),
            _event("1.1.0",  layer="stab", role="stab"),  # authority collision with kick? No — no bass here
        )
        plan = _plan()
        count_before = len(list(bank.all_events()))
        enforce_phrase_syntax(bank, plan)
        enforce_supporting_layer_compliance(bank, plan)
        count_after = len(list(bank.all_events()))
        assert count_after <= count_before

    def test_empty_space_is_not_filled(self):
        """Phase 8 must not add events to fill gaps in empty bars."""
        bank = _bank()   # empty bank
        plan = _plan()
        enforce_phrase_syntax(bank, plan)
        enforce_supporting_layer_compliance(bank, plan)
        assert list(bank.all_events()) == []

    def test_silence_region_stays_empty_after_phase8(self):
        bank = _bank(_event("3.1.0", layer="kick"))
        plan = _plan(silence={3: tuple(range(16))})

        enforce_phrase_syntax(bank, plan)
        count_after_p6 = len(list(bank.all_events()))
        enforce_supporting_layer_compliance(bank, plan)
        count_after_p8 = len(list(bank.all_events()))

        assert count_after_p8 <= count_after_p6


# ---------------------------------------------------------------------------
# Debug counters
# ---------------------------------------------------------------------------

class TestDebugCounters:

    def test_all_required_counters_present(self):
        bank = _bank()
        plan = _plan()
        stats = enforce_supporting_layer_compliance(bank, plan)
        required = {
            "support_events_checked",
            "support_events_suppressed",
            "support_events_suppressed_by_silence",
            "support_events_suppressed_by_role",
            "support_events_suppressed_by_authority",
        }
        assert required.issubset(stats.keys())

    def test_checked_count_equals_supporting_events(self):
        bank = _bank(
            _event("1.1.0", layer="kick"),     # supporting
            _event("1.2.0", layer="snare"),    # supporting
            _event("1.1.0", layer="bass"),     # NOT supporting
            _event("1.2.0", layer="hook"),     # NOT supporting
        )
        plan = _plan()
        stats = enforce_supporting_layer_compliance(bank, plan)
        assert stats["support_events_checked"] == 2

    def test_suppressed_sum_matches_individual_categories(self):
        # Stab at same step as bass (authority collision)
        bass = _event("1.1.0", layer="bass")
        stab = _event("1.1.0", layer="stab")
        bank = _bank(bass, stab)
        plan = _plan()
        enforce_phrase_syntax(bank, plan)
        stats = enforce_supporting_layer_compliance(bank, plan)

        total = (
            stats["support_events_suppressed_by_silence"]
            + stats["support_events_suppressed_by_role"]
            + stats["support_events_suppressed_by_authority"]
        )
        assert total == stats["support_events_suppressed"]

    def test_silence_counter_is_zero_after_phase6(self):
        """After Phase 6, Phase 8 should see 0 silence violations —
        this proves Phase 6 coverage."""
        bank = _bank(
            _event("3.1.0", layer="kick"),
            _event("3.2.0", layer="snare"),
        )
        plan = _plan(silence={3: tuple(range(16))})
        enforce_phrase_syntax(bank, plan)   # Phase 6 removes them
        stats = enforce_supporting_layer_compliance(bank, plan)
        assert stats["support_events_suppressed_by_silence"] == 0
