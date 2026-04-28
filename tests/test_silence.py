"""Phase 6 — silence mask compliance tests.

Acceptance criteria:
  - No non-exempt events appear inside silence_mask
  - Silence overrides call_slots
  - Silence overrides response_slots
  - Silence overrides behaviour-driven events
  - Bass is suppressed when inside silence_mask
  - Hook is suppressed when inside silence_mask
  - System produces events again immediately after silence ends
  - silence_regions_active counter is correct
  - Per-layer suppression counts are tracked
  - Off-grid events in muted bars are silenced
"""

from thelmic.bank_generator import Bank, Phrase, MIDIEvent
from thelmic.bass import generate_planned_bass
from thelmic.behaviour_field import BehaviourField
from thelmic.calls import generate_planned_calls
from thelmic.hook import generate_planned_hook
from thelmic.phrase_plan import (
    PhrasePlan, PlanNote, SilenceMask, PhraseState, generate_phrase_plan,
)
from thelmic.responses import generate_planned_responses
from thelmic.syntax_enforcer import enforce_phrase_syntax, time_to_bar_step


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

LAYERS = ["kick", "snare", "hat", "bass", "hook", "stab", "call", "response"]


def _event(
    time: str = "1.1.0",
    layer: str = "kick",
    role: str = "anchor",
    note: int = 36,
    velocity: int = 100,
) -> MIDIEvent:
    return MIDIEvent(
        time=time, note=note, velocity=velocity,
        duration=0.08, layer=layer, role=role,
        emphasis=0.8, openness=1.0, expected_weight=0.9, should_resolve=False,
    )


def _bank(*events: MIDIEvent) -> Bank:
    return Bank(bank_index=0, phrases=[Phrase(phrase_index=0, events=list(events))])


def _behaviour() -> BehaviourField:
    return BehaviourField(
        ghost_intensity=0.0, ghost_clustering=0.0, anchor_drop_prob=0.0,
        filter_target=0.0, gate_tightness=0.0, energy_level=0.7,
        accent_strength=0.0, ghost_velocity=0.4, anchor_velocity=0.8,
    )


def _plan_with_silence(
    muted: dict[int, tuple[int, ...]],
    call_slots: dict[int, tuple[int, ...]] | None = None,
    response_slots: dict[int, tuple[int, ...]] | None = None,
    phrase_state: dict[int, PhraseState] | None = None,
) -> PhrasePlan:
    states = phrase_state or {
        1: PhraseState.CALL_UNRESOLVED,
        2: PhraseState.HOLD_SILENCE,
        3: PhraseState.RESPONSE_RESOLVED,
    }
    return PhrasePlan(
        bass_pattern=(PlanNote(bar=1, step=0, pitch=36),),
        hook_pattern=(PlanNote(bar=1, step=0, pitch=60),),
        phrase_state=states,
        call_slots=call_slots if call_slots is not None else {1: (2, 6)},
        response_slots=response_slots if response_slots is not None else {3: (10, 13)},
        silence_mask=SilenceMask(muted),
        pressure_curve={1: 0.0, 2: 0.5, 3: 1.0},
    )


# ---------------------------------------------------------------------------
# Hard constraint: all layers silenced
# ---------------------------------------------------------------------------

class TestAllLayersSilenced:

    def test_kick_suppressed_inside_silence(self):
        bank = _bank(_event("2.1.0", layer="kick", role="anchor"))
        plan = _plan_with_silence({2: (0,)})
        stats = enforce_phrase_syntax(bank, plan)
        assert bank.all_events() == []
        assert stats["events_blocked_by_silence"] == 1

    def test_snare_suppressed_inside_silence(self):
        bank = _bank(_event("2.2.0", layer="snare", role="anchor"))
        plan = _plan_with_silence({2: (4,)})
        stats = enforce_phrase_syntax(bank, plan)
        assert bank.all_events() == []

    def test_hat_suppressed_inside_silence(self):
        bank = _bank(_event("2.1.12", layer="hat", role="anchor"))
        plan = _plan_with_silence({2: (2,)})
        stats = enforce_phrase_syntax(bank, plan)
        assert bank.all_events() == []

    def test_stab_suppressed_inside_silence(self):
        bank = _bank(_event("2.1.0", layer="stab", role="stab"))
        plan = _plan_with_silence({2: (0,)})
        stats = enforce_phrase_syntax(bank, plan)
        assert bank.all_events() == []

    def test_all_layers_suppressed_in_full_bar_silence(self):
        all_steps = tuple(range(16))
        events = [
            _event("2.1.0",  layer=lyr, role="anchor")
            for lyr in LAYERS
        ]
        bank = _bank(*events)
        plan = _plan_with_silence({2: all_steps})
        stats = enforce_phrase_syntax(bank, plan)
        assert bank.all_events() == []
        assert stats["events_blocked_by_silence"] == len(LAYERS)

    def test_events_outside_silence_region_are_kept(self):
        bank = _bank(
            _event("1.1.0", layer="kick"),   # bar 1 — not silenced
            _event("2.1.0", layer="kick"),   # bar 2 — silenced
        )
        plan = _plan_with_silence({2: tuple(range(16))})
        enforce_phrase_syntax(bank, plan)
        kept = bank.all_events()
        assert len(kept) == 1
        assert kept[0].time == "1.1.0"


# ---------------------------------------------------------------------------
# Silence overrides call_slots and response_slots
# ---------------------------------------------------------------------------

class TestSilenceOverridesSlots:

    def test_silence_overrides_call_slots(self):
        """An event in a valid call slot must be removed if the step is muted."""
        # bar 1 state = CALL_UNRESOLVED, step 2 is in call_slots → but also muted
        bank = _bank(_event("1.1.12", layer="stab", role="call"))
        plan = _plan_with_silence(
            muted={1: (2,)},
            call_slots={1: (2, 6)},
        )
        stats = enforce_phrase_syntax(bank, plan)
        assert bank.all_events() == []
        assert stats["events_blocked_by_silence"] == 1

    def test_silence_overrides_response_slots(self):
        """An event in a valid response slot must be removed if the step is muted."""
        # bar 3 state = RESPONSE_RESOLVED, step 10 is in response_slots → but also muted
        bank = _bank(_event("3.3.12", layer="stab", role="response"))
        plan = _plan_with_silence(
            muted={3: (10,)},
            call_slots={1: (2,)},
            response_slots={3: (10, 13)},
        )
        stats = enforce_phrase_syntax(bank, plan)
        assert bank.all_events() == []
        assert stats["events_blocked_by_silence"] == 1

    def test_call_in_non_silenced_slot_is_kept(self):
        """Confirm calls survive when the step is in call_slots and NOT muted."""
        bank = _bank(_event("1.1.12", layer="stab", role="call"))
        plan = _plan_with_silence(
            muted={2: tuple(range(16))},   # bar 2 muted, not bar 1
            call_slots={1: (2, 6)},
        )
        enforce_phrase_syntax(bank, plan)
        assert any(e.time == "1.1.12" for e in bank.all_events())


# ---------------------------------------------------------------------------
# Bass and hook suppression
# ---------------------------------------------------------------------------

class TestBassAndHookSuppression:

    def test_bassline_suppressed_inside_silence(self):
        """Bassline events rendered in a silenced bar are removed by the enforcer."""
        kick = _event("2.1.0", layer="kick", role="anchor")
        plan_full = generate_phrase_plan()
        bass = generate_planned_bass([kick], _behaviour(), plan_full)

        # Re-check: build a plan that mutes bar 2 entirely
        plan = _plan_with_silence({2: tuple(range(16))})
        bank = _bank(*[
            MIDIEvent(
                time=e.time, note=e.note, velocity=e.velocity,
                duration=e.duration, layer=e.layer, role=e.role,
                emphasis=e.emphasis, openness=e.openness,
                expected_weight=e.expected_weight, should_resolve=e.should_resolve,
            )
            for e in bass
            if e.time.startswith("2.")
        ])
        stats = enforce_phrase_syntax(bank, plan)
        assert bank.all_events() == []
        assert stats["events_blocked_by_silence_by_layer"].get("bassline", 0) >= (
            len([e for e in bass if e.time.startswith("2.")])
        )

    def test_hook_suppressed_inside_silence(self):
        """Hook events rendered in a silenced bar are removed by the enforcer."""
        kick = _event("2.1.0", layer="kick", role="anchor")
        plan_full = generate_phrase_plan()
        hook = generate_planned_hook([kick], _behaviour(), plan_full)

        plan = _plan_with_silence({2: tuple(range(16))})
        bank = _bank(*[
            MIDIEvent(
                time=e.time, note=e.note, velocity=e.velocity,
                duration=e.duration, layer=e.layer, role=e.role,
                emphasis=e.emphasis, openness=e.openness,
                expected_weight=e.expected_weight, should_resolve=e.should_resolve,
            )
            for e in hook
            if e.time.startswith("2.")
        ])
        if bank.all_events():  # only test if hook produces bar-2 events
            enforce_phrase_syntax(bank, plan)
            assert bank.all_events() == []

    def test_bass_outside_silence_region_survives(self):
        """Bass events in non-muted bars must not be affected."""
        bank = _bank(_event("1.1.0", layer="bass", role="bass"))
        plan = _plan_with_silence({2: tuple(range(16))})  # only bar 2 muted
        enforce_phrase_syntax(bank, plan)
        assert len(bank.all_events()) == 1


# ---------------------------------------------------------------------------
# Silence from generated calls and responses
# ---------------------------------------------------------------------------

class TestSilenceSuppressesGeneratedEvents:

    def _events_for_bars(self, *bars: int) -> list[MIDIEvent]:
        return [_event(f"{b}.1.0") for b in bars]

    def test_planned_calls_suppressed_by_silence(self):
        """generate_planned_calls + enforce_phrase_syntax = no calls in muted bar."""
        events = self._events_for_bars(1)
        # call_slots for bar 1, but bar 1 is fully muted
        plan = PhrasePlan(
            bass_pattern=(PlanNote(bar=1, step=0, pitch=36),),
            hook_pattern=(PlanNote(bar=1, step=0, pitch=60),),
            phrase_state={1: PhraseState.CALL_UNRESOLVED},
            call_slots={1: (2, 6)},
            response_slots={},
            silence_mask=SilenceMask({1: tuple(range(16))}),
            pressure_curve={1: 0.0},
        )
        calls = generate_planned_calls(events, _behaviour(), plan)
        bank = _bank(*calls.events)
        enforce_phrase_syntax(bank, plan)
        assert bank.all_events() == []

    def test_planned_responses_suppressed_by_silence(self):
        """generate_planned_responses + enforce = no responses in muted bar."""
        events = self._events_for_bars(1, 2)
        plan = PhrasePlan(
            bass_pattern=(PlanNote(bar=1, step=0, pitch=36),),
            hook_pattern=(PlanNote(bar=1, step=0, pitch=60),),
            phrase_state={
                1: PhraseState.CALL_UNRESOLVED,
                2: PhraseState.RESPONSE_RESOLVED,
            },
            call_slots={1: (2,)},
            response_slots={2: (10, 13)},
            silence_mask=SilenceMask({2: tuple(range(16))}),
            pressure_curve={1: 0.0, 2: 0.5},
        )
        responses = generate_planned_responses(events, _behaviour(), plan)
        bank = _bank(*responses.events)
        enforce_phrase_syntax(bank, plan)
        assert bank.all_events() == []


# ---------------------------------------------------------------------------
# Recovery: events appear immediately after silence ends
# ---------------------------------------------------------------------------

class TestSilenceRecovery:

    def test_events_resume_after_silence_ends(self):
        """Events in the bar immediately after a fully muted bar must survive."""
        bank = _bank(
            _event("2.1.0", layer="kick"),   # bar 2 — fully silenced
            _event("3.1.0", layer="kick"),   # bar 3 — not silenced
        )
        plan = _plan_with_silence({2: tuple(range(16))})
        enforce_phrase_syntax(bank, plan)
        kept = bank.all_events()
        assert len(kept) == 1
        assert kept[0].time.startswith("3.")

    def test_event_at_step_after_muted_steps_survives(self):
        """Events at the first non-muted step in a bar must survive."""
        # Bar 1, steps 0-3 muted; step 4 should survive
        bank = _bank(
            _event("1.1.0",  layer="kick"),   # step 0 — muted
            _event("1.2.0",  layer="kick"),   # step 4 — clear
        )
        plan = _plan_with_silence({1: (0, 1, 2, 3)},
            phrase_state={1: PhraseState.RESOLVED_STABLE, 2: PhraseState.RESOLVED_STABLE, 3: PhraseState.RESOLVED_STABLE})
        enforce_phrase_syntax(bank, plan)
        kept = bank.all_events()
        assert len(kept) == 1
        assert kept[0].time == "1.2.0"


# ---------------------------------------------------------------------------
# Off-grid events in muted bars
# ---------------------------------------------------------------------------

class TestOffGridSilence:

    def test_off_grid_event_in_muted_bar_is_silenced(self):
        """An event at a non-step-boundary tick inside a muted bar must be removed.

        The floor-step mapping ensures off-grid events are still silenced.
        """
        # Create an off-grid event: tick=3 which is not a 16th-note step
        off_grid = _event("1.1.3", layer="bass")
        bank = _bank(off_grid)
        # Bar 1 step 0 contains tick 3 (floor(3/6) = 0)
        plan = _plan_with_silence({1: (0,)},
            phrase_state={1: PhraseState.RESOLVED_STABLE, 2: PhraseState.RESOLVED_STABLE, 3: PhraseState.RESOLVED_STABLE})
        stats = enforce_phrase_syntax(bank, plan)
        assert bank.all_events() == []
        assert stats["events_blocked_by_silence"] == 1

    def test_off_grid_event_not_in_muted_step_passes(self):
        """Off-grid event at tick 7 (floor step 1) survives if step 1 is not muted."""
        off_grid = _event("1.1.7", layer="bass")
        bank = _bank(off_grid)
        # Only step 0 muted; tick 7 → floor step 1 (not muted)
        plan = _plan_with_silence({1: (0,)},
            phrase_state={1: PhraseState.RESOLVED_STABLE, 2: PhraseState.RESOLVED_STABLE, 3: PhraseState.RESOLVED_STABLE})
        enforce_phrase_syntax(bank, plan)
        assert len(bank.all_events()) == 1


# ---------------------------------------------------------------------------
# Debug counters
# ---------------------------------------------------------------------------

class TestDebugCounters:

    def test_silence_regions_active_counts_muted_bars(self):
        """silence_regions_active should equal the number of bars with muted steps."""
        bank = _bank()
        plan = _plan_with_silence({1: (0,), 2: (0, 1), 3: tuple(range(16))})
        stats = enforce_phrase_syntax(bank, plan)
        assert stats["silence_regions_active"] == 3

    def test_silence_regions_active_zero_when_no_silence(self):
        bank = _bank()
        plan = _plan_with_silence({})
        stats = enforce_phrase_syntax(bank, plan)
        assert stats["silence_regions_active"] == 0

    def test_per_layer_counts_tracked(self):
        bank = _bank(
            _event("2.1.0", layer="kick"),
            _event("2.1.0", layer="bass"),
            _event("2.1.0", layer="hook"),
        )
        plan = _plan_with_silence({2: (0,)})
        stats = enforce_phrase_syntax(bank, plan)
        by_layer = stats["events_blocked_by_silence_by_layer"]
        assert by_layer.get("kick", 0) == 1
        assert by_layer.get("bass", 0) == 1
        assert by_layer.get("hook", 0) == 1
        assert sum(by_layer.values()) == stats["events_blocked_by_silence"]

    def test_events_blocked_by_silence_counter_is_accurate(self):
        all_steps = tuple(range(16))
        # 4 events all in bar 2, which is fully muted
        events = [_event("2.1.0", layer=lyr) for lyr in ["kick", "snare", "hat", "bass"]]
        bank = _bank(*events)
        plan = _plan_with_silence({2: all_steps})
        stats = enforce_phrase_syntax(bank, plan)
        assert stats["events_blocked_by_silence"] == 4
        assert stats["syntax_filtered_events_total"] == 4

    def test_required_counters_all_present(self):
        bank = _bank()
        plan = _plan_with_silence({1: (0,)})
        stats = enforce_phrase_syntax(bank, plan)
        required = {
            "events_blocked_by_silence",
            "silence_regions_active",
            "events_blocked_by_silence_by_layer",
            "events_outside_call_slots",
            "events_outside_response_slots",
            "syntax_filtered_events_total",
        }
        assert required.issubset(stats.keys())
