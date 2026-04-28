"""Phase 7 — Pression compliance tests.

Proves that Pression is strictly control-only:
  - Does not create note events
  - Does not alter event timing
  - Does not override silence_mask
  - Does not introduce call/response events
  - Modifies velocity/CC only (via apply_behaviour_dynamics)
  - pression_attempted_event_creations == 0
"""

from thelmic.bank_generator import Bank, Phrase, MIDIEvent
from thelmic.behaviour_field import BehaviourField
from thelmic.call_response import Mode
from thelmic.deformations_dynamics import apply_behaviour_dynamics
from thelmic.force_engine import ForceEngine, ForceState
from thelmic.phrase_plan import (
    PhrasePlan, PlanNote, SilenceMask, PhraseState, generate_phrase_plan,
)
from thelmic.pression import (
    PressionBar, compute_bank_timeline, audit_pression_compliance,
    DIMENSION_NAMES, DEFAULT_CC_MAP,
)
from thelmic.syntax_enforcer import enforce_phrase_syntax


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _event(time: str = "1.1.0", layer: str = "kick", role: str = "anchor",
           velocity: int = 100, note: int = 36) -> MIDIEvent:
    return MIDIEvent(
        time=time, note=note, velocity=velocity, duration=0.08,
        layer=layer, role=role,
        emphasis=0.8, openness=1.0, expected_weight=0.9, should_resolve=False,
    )


def _bank(*events: MIDIEvent) -> Bank:
    return Bank(bank_index=0, phrases=[Phrase(phrase_index=0, events=list(events))])


def _behaviour(energy_level: float = 0.7) -> BehaviourField:
    return BehaviourField(
        ghost_intensity=0.0, ghost_clustering=0.0, anchor_drop_prob=0.0,
        filter_target=0.0, gate_tightness=0.0,
        energy_level=energy_level, accent_strength=0.0,
        ghost_velocity=0.4, anchor_velocity=0.8,
    )


def _force() -> ForceState:
    return ForceEngine(landscape_position=0.5).force_state


def _timeline_from_bank(bank: Bank) -> list[PressionBar]:
    return compute_bank_timeline(
        force=_force(),
        behaviour=_behaviour(),
        transition=None,
        cr_mode=Mode.STAB_LEADS,
        bank=bank,
    )


# ---------------------------------------------------------------------------
# Pression does not create events
# ---------------------------------------------------------------------------

class TestPressionDoesNotCreateEvents:

    def test_compute_bank_timeline_does_not_add_events(self):
        bank = _bank(_event("1.1.0"), _event("1.2.0"))
        count_before = len(list(bank.all_events()))
        _timeline_from_bank(bank)
        count_after = len(list(bank.all_events()))
        assert count_after == count_before

    def test_compute_bank_timeline_on_empty_bank(self):
        bank = _bank()
        _timeline_from_bank(bank)
        assert list(bank.all_events()) == []

    def test_pression_timeline_contains_only_pression_bars(self):
        bank = _bank(_event("1.1.0"))
        timeline = _timeline_from_bank(bank)
        assert all(isinstance(bar, PressionBar) for bar in timeline)
        assert not any(isinstance(bar, MIDIEvent) for bar in timeline)

    def test_audit_attempted_event_creations_is_zero(self):
        bank = _bank(_event("1.1.0"))
        timeline = _timeline_from_bank(bank)
        audit = audit_pression_compliance(timeline, bank, DEFAULT_CC_MAP)
        assert audit["pression_attempted_event_creations"] == 0

    def test_audit_event_creations_zero_across_full_bank(self):
        events = [_event(f"{b}.1.0") for b in range(1, 17)]
        bank = _bank(*events)
        timeline = _timeline_from_bank(bank)
        audit = audit_pression_compliance(timeline, bank, DEFAULT_CC_MAP)
        assert audit["pression_attempted_event_creations"] == 0


# ---------------------------------------------------------------------------
# Pression does not alter event timing
# ---------------------------------------------------------------------------

class TestPressionDoesNotAlterTiming:

    def test_event_times_unchanged_after_timeline_computation(self):
        bank = _bank(
            _event("1.1.0", layer="kick"),
            _event("1.2.0", layer="snare"),
            _event("2.3.0", layer="hat"),
        )
        times_before = [e.time for e in bank.all_events()]
        _timeline_from_bank(bank)
        times_after = [e.time for e in bank.all_events()]
        assert times_before == times_after

    def test_event_notes_unchanged_after_timeline_computation(self):
        bank = _bank(_event("1.1.0", note=36))
        _timeline_from_bank(bank)
        assert bank.all_events()[0].note == 36


# ---------------------------------------------------------------------------
# Pression does not override silence
# ---------------------------------------------------------------------------

class TestPressionDoesNotOverrideSilence:

    def _plan_with_silence(self, muted_bar: int) -> PhrasePlan:
        states = {
            1: PhraseState.HOLD_SILENCE,
            2: PhraseState.RESOLVED_STABLE,
        }
        return PhrasePlan(
            bass_pattern=(PlanNote(bar=2, step=0, pitch=36),),
            hook_pattern=(PlanNote(bar=2, step=0, pitch=60),),
            phrase_state=states,
            call_slots={},
            response_slots={},
            silence_mask=SilenceMask({muted_bar: tuple(range(16))}),
            pressure_curve={1: 0.0, 2: 1.0},
        )

    def test_pression_does_not_restore_silenced_events(self):
        """Silenced events removed by enforce_phrase_syntax must not reappear."""
        silenced_event = _event("1.1.0", layer="kick")
        surviving_event = _event("2.1.0", layer="kick")
        bank = _bank(silenced_event, surviving_event)
        plan = self._plan_with_silence(muted_bar=1)

        # Enforce silence
        enforce_phrase_syntax(bank, plan)
        assert len(list(bank.all_events())) == 1

        # Compute pression AFTER enforcement (as server.py does)
        _timeline_from_bank(bank)

        # Event count must not increase
        assert len(list(bank.all_events())) == 1
        assert bank.all_events()[0].time == "2.1.0"

    def test_pression_timeline_sees_only_post_enforcement_events(self):
        """Pression values are computed from post-enforcement events,
        so silenced events do not influence pression output."""
        silenced_kick = _event("1.1.0", layer="kick", velocity=127)
        bank = _bank(silenced_kick)
        plan = self._plan_with_silence(muted_bar=1)

        # Enforce silence first
        enforce_phrase_syntax(bank, plan)
        assert list(bank.all_events()) == []

        # Pression computed on empty bank — no note events should be added.
        count_before = len(list(bank.all_events()))
        _timeline_from_bank(bank)
        # The bank must stay empty — pression must not add events back.
        assert len(list(bank.all_events())) == count_before == 0


# ---------------------------------------------------------------------------
# Pression does not introduce call/response events
# ---------------------------------------------------------------------------

class TestPressionDoesNotCreateCallOrResponse:

    def test_no_call_events_in_pression_output(self):
        bank = _bank(_event("1.1.0"))
        _timeline_from_bank(bank)
        for event in bank.all_events():
            assert event.role != "call", (
                f"Unexpected call event found after pression computation: {event}"
            )

    def test_no_response_events_in_pression_output(self):
        bank = _bank(_event("1.1.0"))
        _timeline_from_bank(bank)
        for event in bank.all_events():
            assert event.role != "response"

    def test_pression_timeline_has_no_midi_events(self):
        bank = _bank(_event("1.1.0"))
        timeline = _timeline_from_bank(bank)
        for bar in timeline:
            assert not isinstance(bar, MIDIEvent)
            for dim in DIMENSION_NAMES:
                val = getattr(bar, dim, None)
                assert isinstance(val, list), f"dim {dim} should be a list"
                assert not any(isinstance(v, MIDIEvent) for v in val)


# ---------------------------------------------------------------------------
# apply_behaviour_dynamics modifies velocity only, not structure
# ---------------------------------------------------------------------------

class TestBehaviourDynamicsIsVelocityOnly:

    def test_apply_dynamics_does_not_change_event_count(self):
        bank = _bank(
            _event("1.1.0", layer="kick", role="anchor"),
            _event("1.2.0", layer="snare", role="ghost"),
        )
        count_before = len(list(bank.all_events()))
        apply_behaviour_dynamics(bank, _behaviour())
        assert len(list(bank.all_events())) == count_before

    def test_apply_dynamics_does_not_change_timing(self):
        bank = _bank(
            _event("1.1.0", layer="kick"),
            _event("1.3.0", layer="snare"),
        )
        times_before = [e.time for e in bank.all_events()]
        apply_behaviour_dynamics(bank, _behaviour())
        assert [e.time for e in bank.all_events()] == times_before

    def test_apply_dynamics_does_not_change_notes(self):
        bank = _bank(_event("1.1.0", note=36))
        apply_behaviour_dynamics(bank, _behaviour())
        assert bank.all_events()[0].note == 36

    def test_apply_dynamics_modifies_ghost_velocity(self):
        ghost = _event("1.1.0", layer="snare", role="ghost", velocity=100)
        bank = _bank(ghost)
        apply_behaviour_dynamics(bank, _behaviour(energy_level=0.5))
        # Ghost velocity should be reduced (ghost_velocity < 1.0)
        assert bank.all_events()[0].velocity < 100

    def test_apply_dynamics_returns_modulation_count(self):
        bank = _bank(
            _event("1.1.0", layer="kick", role="anchor"),
            _event("1.2.0", layer="snare", role="ghost"),
            _event("1.3.0", layer="hat", role="hat"),  # not ghost or anchor
        )
        count = apply_behaviour_dynamics(bank, _behaviour())
        assert count == 2   # kick anchor + snare ghost


# ---------------------------------------------------------------------------
# Debug counters
# ---------------------------------------------------------------------------

class TestPressionDebugCounters:

    def test_all_required_counters_in_audit(self):
        bank = _bank(_event("1.1.0"))
        timeline = _timeline_from_bank(bank)
        audit = audit_pression_compliance(timeline, bank, DEFAULT_CC_MAP)
        required = {
            "pression_attempted_event_creations",
            "pression_cc_outputs",
            "pression_targets_active",
            "pression_bank_events_at_audit",
        }
        assert required.issubset(audit.keys())

    def test_attempted_event_creations_is_always_zero(self):
        for event_count in [0, 1, 5, 16]:
            events = [_event(f"{b}.1.0") for b in range(1, event_count + 1)]
            bank = _bank(*events)
            timeline = _timeline_from_bank(bank)
            audit = audit_pression_compliance(timeline, bank, DEFAULT_CC_MAP)
            assert audit["pression_attempted_event_creations"] == 0, (
                f"attempted_event_creations should always be 0, got "
                f"{audit['pression_attempted_event_creations']} for {event_count} events"
            )

    def test_targets_active_bounded_by_dimension_count(self):
        bank = _bank(_event("1.1.0"))
        timeline = _timeline_from_bank(bank)
        audit = audit_pression_compliance(timeline, bank, DEFAULT_CC_MAP)
        assert 0 <= audit["pression_targets_active"] <= len(DIMENSION_NAMES)

    def test_bank_events_at_audit_matches_actual_count(self):
        events = [_event(f"{b}.1.0") for b in range(1, 5)]
        bank = _bank(*events)
        timeline = _timeline_from_bank(bank)
        audit = audit_pression_compliance(timeline, bank, DEFAULT_CC_MAP)
        assert audit["pression_bank_events_at_audit"] == len(list(bank.all_events()))

    def test_cc_outputs_zero_when_no_active_targets(self):
        bank = _bank()   # no events → pression values all zero
        timeline = _timeline_from_bank(bank)
        audit = audit_pression_compliance(timeline, bank, {})  # empty cc_map
        assert audit["pression_cc_outputs"] == 0
