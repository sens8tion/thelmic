from thelmic.bank_generator import MIDIEvent
from thelmic.bass import generate_bass, generate_planned_bass
from thelmic.behaviour_field import BehaviourField
from thelmic.phrase_plan import PhrasePlan, PlanNote, SilenceMask, PhraseState, generate_phrase_plan


def _behaviour(energy_level: float = 0.5, ghost_intensity: float = 0.0, instability: float = 0.0) -> BehaviourField:
    return BehaviourField(
        ghost_intensity=ghost_intensity,
        ghost_clustering=0.0,
        anchor_drop_prob=0.0,
        filter_target=0.0,
        gate_tightness=0.0,
        energy_level=energy_level,
        accent_strength=0.0,
        ghost_velocity=0.4,
        anchor_velocity=0.8,
        instability=instability,
    )


def _event(layer: str = "kick", velocity: int = 100) -> MIDIEvent:
    return MIDIEvent(
        time="1.1.0",
        note=36,
        velocity=velocity,
        duration=0.08,
        layer=layer,
        role="anchor",
        emphasis=0.8,
        openness=1.0,
        expected_weight=0.9,
        should_resolve=False,
    )


def test_bass_follows_kick_when_gate_hits():
    bass = generate_bass([_event()], _behaviour(), landscape_position=0.0)

    assert bass[0].layer == "bass"
    assert bass[0].role == "bass"
    assert bass[0].time == "1.1.0"
    assert bass[0].note == 36
    assert bass[0].velocity == 72


def test_bass_ignores_non_kick_events():
    assert generate_bass([_event(layer="snare")], _behaviour()) == []


def test_chaos_bass_uses_deterministic_kick_gate():
    event = _event()
    event.time = "1.1.0"

    bass = generate_bass([event], _behaviour(ghost_intensity=1.0, instability=1.0), landscape_position=0.5)

    assert [event.time for event in bass] == ["1.1.0"]


def test_offbeat_bass_limited_to_one_per_bar():
    first = _event()
    first.time = "7.1.0"
    second = _event()
    second.time = "2.2.0"

    bass = generate_bass([first, second], _behaviour(ghost_intensity=1.0, instability=1.0), landscape_position=0.5)

    assert sum(1 for event in bass if event.time.endswith(".12")) <= 1


def test_nott_bass_is_sparse_and_kick_locked():
    first = _event()
    first.time = "1.1.0"
    second = _event()
    second.time = "2.1.0"

    bass = generate_bass([first, second], _behaviour(), landscape_position=1.0)

    assert [event.time for event in bass] == ["1.1.0"]


def test_planned_bassline_uses_dnb_offbeat_pattern_by_default():
    kick_one = _event()
    kick_one.time = "1.1.0"
    plan = generate_phrase_plan()

    bass = generate_planned_bass([kick_one], _behaviour(), plan)

    assert [event.time for event in bass] == ["1.1.12", "1.2.12", "1.3.12", "1.4.12"]
    assert {round(event.duration / 0.08) for event in bass} == {2}
    assert {event.note for event in bass} == {36}
    assert all(event.layer == "bassline" and event.role == "bassline" for event in bass)


def test_planned_bassline_plan_step_does_not_create_free_timing():
    kick = _event()
    kick.time = "1.1.0"
    plan = PhrasePlan(
        bass_pattern=(PlanNote(bar=1, step=2, pitch=36),),
        hook_pattern=(),
        phrase_state={1: PhraseState.RESOLVED_STABLE},
        call_slots={},
        response_slots={},
        silence_mask=SilenceMask(),
        pressure_curve={1: 0.0},
    )

    bass = generate_planned_bass([kick], _behaviour(), plan)

    assert bass
    assert all(event.time != "1.1.12" or event.layer == "bassline" for event in bass)
    assert {event.role for event in bass} == {"bassline"}


def test_planned_bassline_pitch_is_restricted_to_root_fifth_or_octave():
    kick = _event()
    kick.time = "1.1.0"
    plan = PhrasePlan(
        bass_pattern=(
            PlanNote(bar=1, step=0, pitch=38),
            PlanNote(bar=1, step=0, pitch=43),
            PlanNote(bar=1, step=0, pitch=48),
        ),
        hook_pattern=(),
        phrase_state={1: PhraseState.RESOLVED_STABLE},
        call_slots={},
        response_slots={},
        silence_mask=SilenceMask(),
        pressure_curve={1: 0.0},
    )

    bass = generate_planned_bass([kick], _behaviour(), plan)

    assert {event.note for event in bass} == {36}


def test_planned_bassline_selects_archetype_specific_pattern_family():
    kick = _event()
    kick.time = "1.1.0"
    plan = generate_phrase_plan()

    oak = generate_planned_bass([kick], _behaviour(), plan, landscape_position=0.0)
    nott = generate_planned_bass([kick], _behaviour(), plan, landscape_position=1.0)

    assert [event.time for event in oak] == ["1.1.0", "1.2.0", "1.3.0", "1.4.0"]
    assert len(nott) == 1
    assert round(nott[0].duration / 0.08) == 16


def test_planned_bass_is_independent_of_stab_material():
    kick = _event()
    kick.time = "1.1.0"
    stab = _event(layer="stab")
    stab.time = "1.1.0"
    stab.note = 72

    with_stab = generate_planned_bass([kick, stab], _behaviour(), generate_phrase_plan())
    without_stab = generate_planned_bass([kick], _behaviour(), generate_phrase_plan())

    assert [(e.time, e.note) for e in with_stab] == [(e.time, e.note) for e in without_stab]
