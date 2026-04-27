from thelmic.bank_generator import Bank, Phrase, MIDIEvent
from thelmic.bass import generate_planned_bass
from thelmic.behaviour_field import BehaviourField
from thelmic.hook import generate_planned_hook
from thelmic.phrase_plan import (
    PhrasePlan, PlanNote, SilenceMask, PhraseState, generate_phrase_plan,
)
from thelmic.pression import compute_bank_timeline, PressionBar
from thelmic.syntax_enforcer import enforce_phrase_syntax
from thelmic.call_response import Mode
from thelmic.force_engine import ForceState


def _event(
    time: str,
    layer: str = "stab",
    role: str = "stab_call",
    note: int = 60,
) -> MIDIEvent:
    return MIDIEvent(
        time=time,
        note=note,
        velocity=100,
        duration=0.08,
        layer=layer,
        role=role,
        emphasis=0.8,
        openness=1.0,
        expected_weight=0.9,
        should_resolve=False,
    )


def _bank(events: list[MIDIEvent]) -> Bank:
    return Bank(bank_index=0, phrases=[Phrase(phrase_index=0, events=events)])


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


def _syntax_plan(
    call_slots: dict[int, tuple[int, ...]] | None = None,
    response_slots: dict[int, tuple[int, ...]] | None = None,
    silence: dict[int, tuple[int, ...]] | None = None,
) -> PhrasePlan:
    return PhrasePlan(
        bass_pattern=(PlanNote(bar=1, step=0, pitch=36),),
        hook_pattern=(PlanNote(bar=1, step=0, pitch=60),),
        phrase_state={
            1: PhraseState.RESOLVED_STABLE,
            2: PhraseState.CALL_UNRESOLVED,
            3: PhraseState.HOLD_SILENCE,
            4: PhraseState.RESPONSE_RESOLVED,
        },
        call_slots=call_slots if call_slots is not None else {2: (2, 6)},
        response_slots=response_slots if response_slots is not None else {4: (10, 13)},
        silence_mask=SilenceMask(silence or {3: tuple(range(16))}),
        pressure_curve={1: 0.0, 2: 0.3, 3: 0.6, 4: 1.0},
    )


def test_no_non_exempt_events_remain_inside_silence_mask():
    bank = _bank([
        _event("3.1.0", layer="kick", role="anchor"),
        _event("3.2.0", layer="hook", role="hook"),
    ])

    stats = enforce_phrase_syntax(bank, _syntax_plan())

    assert bank.all_events() == []
    assert stats["events_blocked_by_silence"] == 2
    assert stats["syntax_filtered_events_total"] == 2


def test_call_role_events_only_remain_inside_call_slots():
    bank = _bank([
        _event("2.1.12", role="stab_call"),  # step 2 allowed
        _event("2.3.0", role="stab_call"),   # step 8 blocked
    ])

    stats = enforce_phrase_syntax(bank, _syntax_plan())

    assert [event.time for event in bank.all_events()] == ["2.1.12"]
    assert stats["events_outside_call_slots"] == 1


def test_response_role_events_only_remain_inside_response_slots():
    bank = _bank([
        _event("4.3.12", role="stab_response"),  # step 10 allowed
        _event("4.4.0", role="stab_response"),   # step 12 blocked
    ])

    stats = enforce_phrase_syntax(bank, _syntax_plan())

    assert [event.time for event in bank.all_events()] == ["4.3.12"]
    assert stats["events_outside_response_slots"] == 1


def test_responses_are_not_emitted_when_no_call_exists():
    bank = _bank([_event("4.3.12", role="stab_response")])

    stats = enforce_phrase_syntax(bank, _syntax_plan(call_slots={}))

    assert bank.all_events() == []
    assert stats["events_outside_response_slots"] == 1


def test_bass_still_renders_from_phrase_plan_bass_pattern():
    kick = _event("1.1.0", layer="kick", role="anchor")
    plan = generate_phrase_plan()

    bass = generate_planned_bass([kick], _behaviour(), plan)

    assert [(event.layer, event.time, event.note) for event in bass] == [
        ("bass", "1.1.0", 36)
    ]


def test_hook_still_renders_from_phrase_plan_hook_pattern():
    kick = _event("1.1.0", layer="kick", role="anchor")
    plan = generate_phrase_plan()

    hook = generate_planned_hook([kick], _behaviour(), plan)

    assert [(event.layer, event.time, event.note) for event in hook[:2]] == [
        ("hook", "1.1.0", 60),
        ("hook", "1.1.18", 63),
    ]


def test_pression_does_not_create_note_events():
    timeline = compute_bank_timeline(
        force=ForceState(),
        behaviour=_behaviour(),
        transition=None,
        cr_mode=Mode.BASS_LEADS,
        bank=_bank([]),
    )

    assert timeline
    assert all(isinstance(bar, PressionBar) for bar in timeline)
    assert not any(isinstance(item, MIDIEvent) for item in timeline)
