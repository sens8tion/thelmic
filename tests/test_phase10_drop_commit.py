from dataclasses import replace

from thelmic.bank_generator import Bank, MIDIEvent, Phrase
from thelmic.drop_enforcer import (
    DROP_STEP,
    DropCommitState,
    add_survivor_signal,
    enforce_drop_relock,
)
from thelmic.phrase_plan import PhrasePlan, PlanNote, SilenceMask, PhraseState
from thelmic.support_enforcer import enforce_supporting_layer_compliance
from thelmic.syntax_enforcer import enforce_phrase_syntax, time_to_bar_step


def _event(
    time: str,
    layer: str = "kick",
    role: str = "anchor",
    note: int = 36,
    velocity: int = 100,
) -> MIDIEvent:
    return MIDIEvent(
        time=time,
        note=note,
        velocity=velocity,
        duration=0.08,
        layer=layer,
        role=role,
        emphasis=0.8,
        openness=1.0,
        expected_weight=0.9,
        should_resolve=False,
    )


def _bank(*events: MIDIEvent) -> Bank:
    return Bank(bank_index=0, phrases=[Phrase(phrase_index=0, events=list(events))])


def _drop_plan() -> PhrasePlan:
    return PhrasePlan(
        bass_pattern=(PlanNote(bar=2, step=0, pitch=36),),
        hook_pattern=(PlanNote(bar=2, step=0, pitch=60),),
        phrase_state={
            1: PhraseState.HOLD_SILENCE,
            2: PhraseState.DROP_RELOCK,
        },
        call_slots={},
        response_slots={},
        silence_mask=SilenceMask({
            1: tuple(range(16)),
            2: tuple(range(0, DROP_STEP)),
        }),
        pressure_curve={1: 0.8, 2: 1.0},
    )


def _has_layer_at(bank: Bank, bar: int, step: int, layer: str) -> bool:
    return any(
        time_to_bar_step(event.time) == (bar, step) and event.layer == layer
        for event in bank.all_events()
    )


def test_survivor_events_are_marked_and_generated_before_drop():
    plan = _drop_plan()
    bank = _bank(_event("2.2.0"))

    stats = add_survivor_signal(bank, plan)
    survivors = [event for event in bank.all_events() if event.role == "survivor"]

    assert stats["survivor_events_before_drop"] > 0
    assert survivors
    assert all(event.layer == "survivor" for event in survivors)
    assert all(event.survives_silence for event in survivors)
    assert all(not event.structural_authority for event in survivors)
    assert all(event.note >= 72 for event in survivors)
    assert all(event.velocity <= 24 for event in survivors)
    assert all(time_to_bar_step(event.time)[0] <= 2 for event in survivors)


def test_survivor_is_only_silence_exemption():
    plan = _drop_plan()
    normal = _event("1.1.0", layer="hook", role="hook")
    survivor = replace(
        _event("1.1.6", layer="survivor", role="survivor", note=84, velocity=12),
        survives_silence=True,
        structural_authority=False,
    )
    bank = _bank(normal, survivor)

    stats = enforce_phrase_syntax(bank, plan)

    remaining = bank.all_events()
    assert remaining == [survivor]
    assert stats["events_blocked_by_silence"] == 1
    assert stats["survivor_events_preserved_by_silence"] == 1


def test_survivor_survives_support_compliance_after_syntax():
    plan = _drop_plan()
    survivor = replace(
        _event("1.1.6", layer="survivor", role="survivor", note=84, velocity=12),
        survives_silence=True,
        structural_authority=False,
    )
    bank = _bank(survivor)

    enforce_phrase_syntax(bank, plan)
    support_stats = enforce_supporting_layer_compliance(bank, plan)

    assert bank.all_events() == [survivor]
    assert support_stats["support_events_suppressed_by_silence"] == 0


def test_unmarked_survivor_role_does_not_bypass_silence():
    plan = _drop_plan()
    unmarked = _event("1.1.6", layer="survivor", role="survivor", note=84)
    bank = _bank(unmarked)

    stats = enforce_phrase_syntax(bank, plan)

    assert bank.all_events() == []
    assert stats["events_blocked_by_silence"] == 1
    assert stats["survivor_events_preserved_by_silence"] == 0


def test_drop_commit_is_applied_once_at_drop_step():
    plan = _drop_plan()
    bank = _bank(_event("2.2.0"))
    commit_state = DropCommitState(active_state="pre_drop", pending_state="drop_relock")

    stats = enforce_drop_relock(bank, plan, commit_state)

    assert stats["drop_step"] == DROP_STEP
    assert stats["commit_applied"] == 1
    assert stats["active_state_before"] == "pre_drop"
    assert stats["pending_state"] == "drop_relock"
    assert stats["active_state_after"] == "drop_relock"
    assert commit_state.active_state == "drop_relock"

    second = enforce_drop_relock(bank, plan, commit_state)
    assert second["commit_applied"] == 0
    assert commit_state.active_state == "drop_relock"


def test_drop_reanchor_has_kick_and_bass_at_committed_step():
    plan = _drop_plan()
    bank = _bank(_event("2.2.0", layer="hat", note=42))

    stats = enforce_drop_relock(bank, plan, DropCommitState())

    assert stats["kick_at_drop"] == 1
    assert stats["bass_at_drop"] == 1
    assert _has_layer_at(bank, 2, DROP_STEP, "kick")
    assert _has_layer_at(bank, 2, DROP_STEP, "bass")


def test_survivor_events_do_not_continue_after_drop_step():
    plan = _drop_plan()
    bank = _bank(_event("2.2.0"))

    add_survivor_signal(bank, plan)

    assert not any(
        event.role == "survivor"
        and time_to_bar_step(event.time)[0] == 2
        and time_to_bar_step(event.time)[1] >= DROP_STEP
        for event in bank.all_events()
    )
