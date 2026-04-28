from dataclasses import replace

from thelmic.bank_generator import Bank, MIDIEvent, Phrase
from thelmic.drop_enforcer import (
    DROP_STEP,
    SURVIVOR_RENDER_LANE,
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
    assert {event.layer for event in survivors} == {"survivor", SURVIVOR_RENDER_LANE}
    assert all(event.survives_silence for event in survivors)
    assert all(not event.structural_authority for event in survivors)
    assert all(event.note >= 72 for event in survivors if event.layer == "survivor")
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


def test_survives_silence_flag_alone_is_enough():
    plan = _drop_plan()
    flagged = replace(
        _event("1.1.6", layer="survivor", role="timing_carrier", note=84),
        survives_silence=True,
        structural_authority=False,
    )
    bank = _bank(flagged)

    stats = enforce_phrase_syntax(bank, plan)

    assert bank.all_events() == [flagged]
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


def test_unmarked_non_survivor_role_does_not_bypass_silence():
    plan = _drop_plan()
    unmarked = _event("1.1.6", layer="texture", role="timing_carrier", note=84)
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


def test_survivor_reaches_final_output_while_normal_event_is_suppressed():
    plan = _drop_plan()
    normal = _event("1.1.0", layer="hook", role="hook", note=60)
    bank = _bank(normal, _event("2.2.0", layer="kick", role="anchor"))

    generation_stats = add_survivor_signal(bank, plan)
    generated_survivors = [event for event in bank.all_events() if event.role == "survivor"]
    assert generation_stats["survivor_events_before_drop"] > 0
    assert generated_survivors

    syntax_stats = enforce_phrase_syntax(bank, plan)
    after_silence = [event for event in bank.all_events() if event.role == "survivor"]
    assert after_silence
    assert normal not in bank.all_events()
    assert syntax_stats["events_blocked_by_silence"] == 1

    enforce_supporting_layer_compliance(bank, plan)
    after_support = [event for event in bank.all_events() if event.role == "survivor"]
    assert after_support

    enforce_drop_relock(bank, plan, syntax_stats=syntax_stats)
    final_survivors = [event for event in bank.all_events() if event.role == "survivor"]
    assert final_survivors
    assert {event.layer for event in final_survivors} == {"survivor", SURVIVOR_RENDER_LANE}
    assert all(event.structural_authority is False for event in final_survivors)


def test_survivor_spans_multiple_pre_drop_silence_windows():
    plan = PhrasePlan(
        bass_pattern=(PlanNote(bar=4, step=0, pitch=36), PlanNote(bar=8, step=0, pitch=36)),
        hook_pattern=(PlanNote(bar=4, step=0, pitch=60), PlanNote(bar=8, step=0, pitch=60)),
        phrase_state={
            1: PhraseState.HOLD_SILENCE,
            2: PhraseState.RESOLVED_STABLE,
            3: PhraseState.HOLD_SILENCE,
            4: PhraseState.DROP_RELOCK,
            5: PhraseState.HOLD_SILENCE,
            6: PhraseState.CALL_UNRESOLVED,
            7: PhraseState.HOLD_SILENCE,
            8: PhraseState.DROP_RELOCK,
        },
        call_slots={},
        response_slots={},
        silence_mask=SilenceMask({
            1: tuple(range(16)),
            3: tuple(range(16)),
            4: tuple(range(0, DROP_STEP)),
            5: tuple(range(16)),
            6: tuple(range(8, 16)),
            7: tuple(range(16)),
            8: tuple(range(0, DROP_STEP)),
        }),
        pressure_curve={bar: 0.5 for bar in range(1, 9)},
    )
    bank = _bank(_event("4.2.0"), _event("8.2.0"))

    stats = add_survivor_signal(bank, plan)
    survivor_times = {event.time for event in bank.all_events() if event.role == "survivor"}

    assert len(stats["survivor_windows"]) == 2
    assert stats["survivor_windows"][0]["start"] == "1.0"
    assert stats["survivor_windows"][0]["end"] == "4.3"
    assert stats["survivor_windows"][1]["start"] == "5.0"
    assert stats["survivor_windows"][1]["end"] == "8.3"
    assert any(time.startswith("1.") for time in survivor_times)
    assert any(time.startswith("3.") for time in survivor_times)
    assert any(time.startswith("5.") for time in survivor_times)
    assert any(time.startswith("7.") for time in survivor_times)


def test_survivor_renders_to_hat_lane_and_remains_subordinate():
    plan = _drop_plan()
    bank = _bank(_event("2.2.0"))

    add_survivor_signal(bank, plan)
    render_events = [
        event for event in bank.all_events()
        if event.role == "survivor" and event.layer == SURVIVOR_RENDER_LANE
    ]
    diagnostic_events = [
        event for event in bank.all_events()
        if event.role == "survivor" and event.layer == "survivor"
    ]

    assert render_events
    assert diagnostic_events
    assert {event.layer for event in render_events}.isdisjoint({"kick", "bass", "snare"})
    assert all(0 < event.velocity <= 24 for event in render_events)
    assert all(event.velocity == 0 for event in diagnostic_events)
    assert all(event.structural_authority is False for event in render_events)
