from thelmic.bank_generator import MIDIEvent
from thelmic.bass import generate_planned_bass
from thelmic.behaviour_field import BehaviourField
from thelmic.calls import generate_planned_calls
from thelmic.hook import generate_planned_hook
from thelmic.phrase_plan import (
    PhrasePlan, PlanNote, SilenceMask, PhraseState, generate_phrase_plan,
)


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


def _plan(
    call_slots: dict[int, tuple[int, ...]] | None = None,
    silence: dict[int, tuple[int, ...]] | None = None,
) -> PhrasePlan:
    return PhrasePlan(
        bass_pattern=(PlanNote(bar=1, step=0, pitch=36),),
        hook_pattern=(PlanNote(bar=1, step=0, pitch=60),),
        phrase_state={1: PhraseState.CALL_UNRESOLVED},
        call_slots=call_slots if call_slots is not None else {1: (2, 6)},
        response_slots={},
        silence_mask=SilenceMask(silence or {}),
        pressure_curve={1: 0.0},
    )


def test_call_events_are_emitted_only_inside_call_slots():
    result = generate_planned_calls([_event()], _behaviour(), _plan())

    assert [event.role for event in result.events] == ["call", "call"]
    assert [event.time for event in result.events] == ["1.1.12", "1.2.12"]
    assert result.stats["planned_call_slots"] == 2
    assert result.stats["call_events_rendered"] == 2
    assert result.stats["call_events_outside_slots"] == 0


def test_no_call_slots_means_no_call_events():
    result = generate_planned_calls([_event()], _behaviour(), _plan(call_slots={}))

    assert result.events == []
    assert result.stats["planned_call_slots"] == 0
    assert result.stats["call_events_rendered"] == 0


def test_calls_are_suppressed_by_silence_mask():
    result = generate_planned_calls(
        [_event()], _behaviour(), _plan(silence={1: (2,)}),
    )

    assert [event.time for event in result.events] == ["1.2.12"]
    assert result.stats["call_events_rendered"] == 1
    assert result.stats["call_events_suppressed"] == 1


def test_hook_events_remain_independent_of_call_generation():
    kick = _event()
    plan = generate_phrase_plan()

    before = generate_planned_hook([kick], _behaviour(), plan)
    generate_planned_calls([kick], _behaviour(), _plan())
    after = generate_planned_hook([kick], _behaviour(), plan)

    assert [(e.time, e.note, e.velocity) for e in after] == [
        (e.time, e.note, e.velocity) for e in before
    ]


def test_bass_events_remain_independent_of_call_generation():
    kick = _event()
    plan = generate_phrase_plan()

    before = generate_planned_bass([kick], _behaviour(), plan)
    generate_planned_calls([kick], _behaviour(), _plan())
    after = generate_planned_bass([kick], _behaviour(), plan)

    assert [(e.time, e.note, e.velocity) for e in after] == [
        (e.time, e.note, e.velocity) for e in before
    ]


def test_phase4_does_not_emit_response_events():
    result = generate_planned_calls([_event()], _behaviour(), _plan())

    assert result.events
    assert not any("response" in event.role for event in result.events)
