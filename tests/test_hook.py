from thelmic.bank_generator import MIDIEvent
from thelmic.bass import generate_planned_bass
from thelmic.behaviour_field import BehaviourField
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
        energy_level=0.5,
        accent_strength=0.0,
        ghost_velocity=0.4,
        anchor_velocity=0.8,
    )


def _event(layer: str = "kick", time: str = "1.1.0") -> MIDIEvent:
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


def _plan(notes: tuple[PlanNote, ...]) -> PhrasePlan:
    return PhrasePlan(
        bass_pattern=(),
        hook_pattern=notes,
        phrase_state={1: PhraseState.RESOLVED_STABLE},
        call_slots={},
        response_slots={},
        silence_mask=SilenceMask(),
        pressure_curve={1: 0.0},
    )


def test_planned_hook_renders_hook_pattern():
    plan = _plan((
        PlanNote(bar=1, step=0, pitch=60, velocity=80, duration_steps=1),
        PlanNote(bar=1, step=3, pitch=63, velocity=82, duration_steps=2),
    ))

    hook = generate_planned_hook([_event()], _behaviour(), plan)

    assert [(event.time, event.note, event.velocity) for event in hook] == [
        ("1.1.0", 60, 80),
        ("1.1.18", 63, 82),
    ]
    assert all(event.layer == "hook" and event.role == "hook" for event in hook)


def test_planned_hook_repeats_across_rendered_bars():
    plan = _plan((PlanNote(bar=1, step=6, pitch=67, velocity=84),))

    hook = generate_planned_hook([
        _event(time="1.1.0"),
        _event(time="2.1.0"),
    ], _behaviour(), plan)

    assert [(event.time, event.note) for event in hook] == [
        ("1.2.12", 67),
        ("2.2.12", 67),
    ]


def test_planned_hook_is_independent_of_call_response_material():
    kick = _event(time="1.1.0")
    stab_call = _event(layer="stab", time="1.1.12")
    stab_call.role = "stab_call"
    bass_response = _event(layer="bass", time="1.3.0")
    bass_response.role = "bass_response"
    plan = generate_phrase_plan()

    with_call_response = generate_planned_hook(
        [kick, stab_call, bass_response], _behaviour(), plan,
    )
    without_call_response = generate_planned_hook([kick], _behaviour(), plan)

    assert [(e.time, e.note, e.velocity) for e in with_call_response] == [
        (e.time, e.note, e.velocity) for e in without_call_response
    ]


def test_rendering_hook_does_not_change_planned_bass_output():
    kick = _event(time="1.1.0")
    plan = generate_phrase_plan()

    before = generate_planned_bass([kick], _behaviour(), plan)
    generate_planned_hook([kick], _behaviour(), plan)
    after = generate_planned_bass([kick], _behaviour(), plan)

    assert [(e.time, e.note, e.velocity) for e in after] == [
        (e.time, e.note, e.velocity) for e in before
    ]


def test_empty_hook_pattern_emits_no_events():
    assert generate_planned_hook([_event()], _behaviour(), _plan(())) == []
