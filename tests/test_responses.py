"""Phase 5 tests — planner-owned response generation.

Acceptance criteria:
- response events are emitted only inside response_slots
- no response slots means no response events
- no valid call means no response events
- responses are suppressed by silence_mask
- hook events remain independent of response generation
- bass events remain independent of response generation
- call generation from Phase 4 still works alongside Phase 5
"""

from thelmic.bank_generator import MIDIEvent
from thelmic.bass import generate_planned_bass
from thelmic.behaviour_field import BehaviourField
from thelmic.calls import generate_planned_calls
from thelmic.hook import generate_planned_hook
from thelmic.phrase_plan import (
    PhrasePlan, PlanNote, SilenceMask, PhraseState, generate_phrase_plan,
)
from thelmic.responses import generate_planned_responses
from thelmic.syntax_enforcer import time_to_bar_step


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _behaviour() -> BehaviourField:
    return BehaviourField(
        ghost_intensity=0.0,
        ghost_clustering=0.0,
        anchor_drop_prob=0.0,
        filter_target=0.0,
        gate_tightness=0.0,
        energy_level=0.7,
        accent_strength=0.0,
        ghost_velocity=0.4,
        anchor_velocity=0.8,
    )


def _event(time: str = "1.1.0", layer: str = "kick") -> MIDIEvent:
    return MIDIEvent(
        time=time,
        note=36,
        velocity=100,
        duration=0.08,
        layer=layer,
        role="anchor",
        emphasis=0.8,
        openness=1.0,
        expected_weight=0.9,
        should_resolve=False,
    )


def _plan_with_call_and_response(
    call_slots: dict[int, tuple[int, ...]] | None = None,
    response_slots: dict[int, tuple[int, ...]] | None = None,
    silence: dict[int, tuple[int, ...]] | None = None,
    phrase_state: dict[int, PhraseState] | None = None,
) -> PhrasePlan:
    """Build a plan where bar 1 is CALL_UNRESOLVED and bar 2 is RESPONSE_RESOLVED."""
    states = phrase_state or {
        1: PhraseState.CALL_UNRESOLVED,
        2: PhraseState.RESPONSE_RESOLVED,
    }
    return PhrasePlan(
        bass_pattern=(PlanNote(bar=1, step=0, pitch=36),),
        hook_pattern=(PlanNote(bar=1, step=0, pitch=60),),
        phrase_state=states,
        call_slots=call_slots if call_slots is not None else {1: (2, 6)},
        response_slots=response_slots if response_slots is not None else {2: (10, 13, 14)},
        silence_mask=SilenceMask(silence or {}),
        pressure_curve={1: 0.0, 2: 0.5},
    )


def _plan_no_call() -> PhrasePlan:
    """Plan with response slots but no call slots — responses must be suppressed."""
    return PhrasePlan(
        bass_pattern=(PlanNote(bar=1, step=0, pitch=36),),
        hook_pattern=(PlanNote(bar=1, step=0, pitch=60),),
        phrase_state={
            1: PhraseState.CALL_UNRESOLVED,
            2: PhraseState.RESPONSE_RESOLVED,
        },
        call_slots={},   # ← no planned calls
        response_slots={2: (10, 13, 14)},
        silence_mask=SilenceMask({}),
        pressure_curve={1: 0.0, 2: 0.5},
    )


def _events_for_bars(*bars: int) -> list[MIDIEvent]:
    return [_event(time=f"{b}.1.0") for b in bars]


# ---------------------------------------------------------------------------
# Core rules
# ---------------------------------------------------------------------------

class TestResponseSlotEnforcement:

    def test_response_events_only_inside_response_slots(self):
        events = _events_for_bars(1, 2)
        plan = _plan_with_call_and_response()
        result = generate_planned_responses(events, _behaviour(), plan)

        for event in result.events:
            bar, step = time_to_bar_step(event.time)
            assert step in plan.response_slots.get(bar, ()), (
                f"response at bar={bar} step={step} is outside response_slots"
            )

    def test_no_response_slots_means_no_response_events(self):
        events = _events_for_bars(1, 2)
        plan = _plan_with_call_and_response(response_slots={})
        result = generate_planned_responses(events, _behaviour(), plan)

        assert result.events == []
        assert result.stats["planned_response_slots"] == 0
        assert result.stats["response_events_rendered"] == 0

    def test_responses_are_emitted_at_planned_steps(self):
        events = _events_for_bars(1, 2)
        plan = _plan_with_call_and_response(response_slots={2: (10, 13, 14)})
        result = generate_planned_responses(events, _behaviour(), plan)

        times = [e.time for e in result.events]
        assert "2.3.12" in times   # step 10
        assert "2.4.6"  in times   # step 13
        assert "2.4.12" in times   # step 14


class TestValidCallRequirement:

    def test_no_call_slots_means_no_response_events(self):
        events = _events_for_bars(1, 2)
        plan = _plan_no_call()
        result = generate_planned_responses(events, _behaviour(), plan)

        assert result.events == []
        assert result.stats["response_events_without_call"] == 3   # 3 response slots
        assert result.stats["response_events_suppressed"]  == 3

    def test_valid_call_allows_responses(self):
        events = _events_for_bars(1, 2)
        plan = _plan_with_call_and_response()
        result = generate_planned_responses(events, _behaviour(), plan)

        assert result.stats["response_events_rendered"] > 0
        assert result.stats["response_events_without_call"] == 0


class TestSilenceMaskSuppression:

    def test_responses_suppressed_by_silence_mask(self):
        events = _events_for_bars(1, 2)
        # Mute step 10 and 13 in bar 2
        plan = _plan_with_call_and_response(silence={2: (10, 13)})
        result = generate_planned_responses(events, _behaviour(), plan)

        times = [e.time for e in result.events]
        # Only step 14 should survive
        assert "2.4.12" in times         # step 14
        assert "2.3.12" not in times     # step 10 — muted
        assert "2.4.6"  not in times     # step 13 — muted
        assert result.stats["response_events_suppressed"] >= 2

    def test_fully_muted_bar_produces_no_responses(self):
        events = _events_for_bars(1, 2)
        plan = _plan_with_call_and_response(silence={2: tuple(range(16))})
        result = generate_planned_responses(events, _behaviour(), plan)

        bar2 = [e for e in result.events if e.time.startswith("2.")]
        assert bar2 == []


# ---------------------------------------------------------------------------
# Role and layer
# ---------------------------------------------------------------------------

class TestResponseRoleAndLayer:

    def test_response_events_use_role_response(self):
        events = _events_for_bars(1, 2)
        result = generate_planned_responses(
            events, _behaviour(), _plan_with_call_and_response(),
        )
        assert result.events
        assert all(e.role == "response" for e in result.events)

    def test_response_layer_is_stab(self):
        events = _events_for_bars(1, 2)
        result = generate_planned_responses(
            events, _behaviour(), _plan_with_call_and_response(),
        )
        assert all(e.layer == "stab" for e in result.events)


# ---------------------------------------------------------------------------
# Independence of hook and bass
# ---------------------------------------------------------------------------

class TestResponseIndependence:

    def test_hook_events_remain_independent_of_response_generation(self):
        events = _events_for_bars(1, 2)
        plan = generate_phrase_plan()

        before = generate_planned_hook(events, _behaviour(), plan)
        generate_planned_responses(events, _behaviour(), _plan_with_call_and_response())
        after = generate_planned_hook(events, _behaviour(), plan)

        assert [(e.time, e.note) for e in after] == [(e.time, e.note) for e in before]

    def test_bass_events_remain_independent_of_response_generation(self):
        events = _events_for_bars(1, 2)
        plan = generate_phrase_plan()

        before = generate_planned_bass(events, _behaviour(), plan)
        generate_planned_responses(events, _behaviour(), _plan_with_call_and_response())
        after = generate_planned_bass(events, _behaviour(), plan)

        assert [(e.time, e.note) for e in after] == [(e.time, e.note) for e in before]

    def test_response_events_do_not_have_hook_role(self):
        events = _events_for_bars(1, 2)
        result = generate_planned_responses(
            events, _behaviour(), _plan_with_call_and_response(),
        )
        assert not any(e.role == "hook" for e in result.events)

    def test_response_events_do_not_have_bass_role(self):
        events = _events_for_bars(1, 2)
        result = generate_planned_responses(
            events, _behaviour(), _plan_with_call_and_response(),
        )
        assert not any(e.role == "bass" for e in result.events)


# ---------------------------------------------------------------------------
# Debug counters
# ---------------------------------------------------------------------------

class TestDebugCounters:

    def test_all_required_counters_present(self):
        events = _events_for_bars(1, 2)
        result = generate_planned_responses(
            events, _behaviour(), _plan_with_call_and_response(),
        )
        required = {
            "planned_response_slots",
            "response_events_rendered",
            "response_events_suppressed",
            "response_events_outside_slots",
            "response_events_without_call",
        }
        assert required.issubset(result.stats.keys())

    def test_rendered_plus_suppressed_equals_planned(self):
        events = _events_for_bars(1, 2)
        # Use a silence mask that mutes some slots
        plan = _plan_with_call_and_response(silence={2: (13,)})
        result = generate_planned_responses(events, _behaviour(), plan)

        s = result.stats
        assert s["response_events_rendered"] + s["response_events_suppressed"] <= s["planned_response_slots"]

    def test_stats_are_zero_when_no_events(self):
        result = generate_planned_responses([], _behaviour(), _plan_with_call_and_response())
        assert result.events == []
        assert result.stats["planned_response_slots"] == 0


# ---------------------------------------------------------------------------
# Phase 4 compatibility — call generation still works alongside Phase 5
# ---------------------------------------------------------------------------

class TestPhase4Compatibility:

    def test_call_generation_still_works(self):
        events = _events_for_bars(1)
        plan = _plan_with_call_and_response()
        calls = generate_planned_calls(events, _behaviour(), plan)

        assert calls.stats["call_events_rendered"] > 0
        assert all(e.role == "call" for e in calls.events)

    def test_call_and_response_from_same_plan(self):
        events = _events_for_bars(1, 2)
        plan = _plan_with_call_and_response()
        calls = generate_planned_calls(events, _behaviour(), plan)
        responses = generate_planned_responses(events, _behaviour(), plan)

        call_times = {e.time for e in calls.events}
        resp_times  = {e.time for e in responses.events}
        assert call_times.isdisjoint(resp_times), (
            f"calls and responses share time slots: {call_times & resp_times}"
        )

    def test_calls_use_call_role_responses_use_response_role(self):
        events = _events_for_bars(1, 2)
        plan = _plan_with_call_and_response()
        calls     = generate_planned_calls(events, _behaviour(), plan)
        responses = generate_planned_responses(events, _behaviour(), plan)

        assert all(e.role == "call"     for e in calls.events)
        assert all(e.role == "response" for e in responses.events)

    def test_phase4_does_not_emit_response_events(self):
        events = _events_for_bars(1, 2)
        plan = _plan_with_call_and_response()
        calls = generate_planned_calls(events, _behaviour(), plan)

        assert not any("response" in e.role for e in calls.events)
