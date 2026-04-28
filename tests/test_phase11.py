from thelmic.bank_generator import Bank, MIDIEvent, Phrase
from thelmic.drop_enforcer import DROP_STEP, enforce_drop_relock
from thelmic.phase11 import (
    INSTRUMENT_PRIORITY,
    Phase11State,
    SparsityMode,
    StructuralChange,
    can_apply_instant_structural_change,
    can_apply_progressive_structural_change,
    evaluate_structural_change,
    enforce_priority_and_sparsity,
    plan_trajectory,
)
from thelmic.phrase_plan import PhrasePlan, PlanNote, SilenceMask, PhraseState
from thelmic.syntax_enforcer import time_to_bar_step


def _event(time="1.1.0", layer="hat", role="anchor", note=42, velocity=80):
    return MIDIEvent(
        time=time,
        note=note,
        velocity=velocity,
        duration=0.08,
        layer=layer,
        role=role,
        emphasis=0.7,
        openness=1.0,
        expected_weight=0.8,
        should_resolve=False,
    )


def _bank(*events):
    return Bank(bank_index=0, phrases=[Phrase(phrase_index=0, events=list(events))])


def _plan(state=PhraseState.RESOLVED_STABLE):
    return PhrasePlan(
        bass_pattern=(PlanNote(bar=1, step=0, pitch=36),),
        hook_pattern=(PlanNote(bar=1, step=0, pitch=60),),
        phrase_state={1: state},
        call_slots={},
        response_slots={},
        silence_mask=SilenceMask({1: tuple(range(0, DROP_STEP))} if state == PhraseState.DROP_RELOCK else {}),
        pressure_curve={1: 0.5},
    )


def test_slider_inertia_target_changes_immediately_actual_follows_smoothly():
    state = Phase11State()
    state.set_immediate(0.0)
    state.set_target(1.0)

    first = state.advance(1.0)
    second = state.advance(1.0)

    assert state.slider.target_position == 1.0
    assert 0.0 < first < 1.0
    assert first < second < 1.0


def test_slider_actual_clamps_and_velocity_decays_when_stable():
    state = Phase11State()
    state.set_immediate(0.95)
    state.set_target(2.0)
    for _ in range(20):
        state.advance(1.0)
    assert 0.0 <= state.slider.actual_position <= 1.0

    state.set_target(state.slider.actual_position)
    before = abs(state.slider.velocity)
    for _ in range(8):
        state.advance(1.0)
    assert abs(state.slider.velocity) < before


def test_static_morphing_changes_without_leaving_constraint_basin():
    state = Phase11State()
    state.set_immediate(0.5)
    first = state.slider.internal_motion()
    state.advance(1.0)
    second = state.slider.internal_motion()

    assert first != second
    assert second["constraint_basin_min"] <= state.slider.actual_position <= second["constraint_basin_max"]


def test_trajectory_planning_short_vs_long_movement():
    short = plan_trajectory(0.1, 0.18, velocity=0.03, duration=8.0)
    long = plan_trajectory(0.1, 0.9, velocity=0.6, duration=4.0)

    assert short.distance < long.distance
    assert len(short.drop_plan) < len(long.drop_plan)
    assert [item["role"] for item in long.drop_plan] == [
        "transition", "intensify", "peak", "resolve",
    ]


def test_priority_enforcement_softens_beat_bed_conflict_instead_of_removing():
    bank = _bank(
        _event("1.1.0", layer="kick", note=36),
        _event("1.1.0", layer="hat", note=42),
    )
    stats = enforce_priority_and_sparsity(bank, _plan(), Phase11State())

    assert [event.layer for event in bank.all_events()] == ["kick", "hat"]
    assert stats["priority_conflicts_resolved"] == 0
    assert stats["events_shifted_by_priority"] == 1


def test_priority_enforcement_keeps_snare_populated_with_foundation_layers():
    bank = _bank(
        _event("1.2.0", layer="sub", note=24),
        _event("1.2.0", layer="bassline", note=36),
        _event("1.2.0", layer="snare", note=38),
        _event("1.2.0", layer="hat", note=42),
    )
    stats = enforce_priority_and_sparsity(bank, _plan(), Phase11State())

    assert [event.layer for event in bank.all_events()] == ["sub", "bassline", "snare", "hat"]
    assert stats["priority_conflicts_resolved"] == 0
    assert stats["events_shifted_by_priority"] == 2


def test_priority_enforcement_keeps_hook_identity_audible_with_foundation_layers():
    bank = _bank(
        _event("1.1.0", layer="sub", note=24),
        _event("1.1.0", layer="bassline", note=36),
        _event("1.1.0", layer="hook", note=60, velocity=90),
    )
    stats = enforce_priority_and_sparsity(bank, _plan(), Phase11State())

    hooks = [event for event in bank.all_events() if event.layer == "hook"]
    assert len(hooks) == 1
    assert hooks[0].velocity > 0
    assert hooks[0].velocity < 90
    assert stats["priority_conflicts_resolved"] == 0
    assert stats["events_shifted_by_priority"] == 1


def test_sparsity_dominance_thins_competing_layers_not_dominant():
    state = Phase11State()
    state.dominant_instrument = "hook"
    state.sparsity_mode = SparsityMode.HARD
    state.sparsity_level = 0.9
    bank = _bank(
        _event("1.1.0", layer="kick", note=36),
        _event("1.2.6", layer="hook", note=60),
        _event("1.2.6", layer="hat", note=42),
        _event("1.3.6", layer="ghost", note=44),
    )

    stats = enforce_priority_and_sparsity(bank, _plan(), state)
    layers = {event.layer for event in bank.all_events()}

    assert "kick" in layers
    assert "hook" in layers
    assert "ghost" not in layers
    assert stats["events_suppressed_by_sparsity"] >= 1


def test_drop_presentation_preserves_phase10_kick_bass_reanchor():
    state = Phase11State()
    state.dominant_instrument = "hook"
    state.sparsity_mode = SparsityMode.HARD
    state.sparsity_level = 1.0
    plan = _plan(PhraseState.DROP_RELOCK)
    bank = _bank(_event("1.2.0", layer="hat", note=42))

    enforce_priority_and_sparsity(bank, plan, state)
    enforce_drop_relock(bank, plan)

    drop_layers = {
        event.layer for event in bank.all_events()
        if time_to_bar_step(event.time) == (1, DROP_STEP)
    }
    assert {"kick", "bassline"}.issubset(drop_layers)


def test_instrument_priority_stack_is_stable():
    assert INSTRUMENT_PRIORITY == (
        "kick", "sub", "bassline", "bass", "snare", "hook", "stab", "hat", "ghost", "survivor",
    )


def test_progressive_hook_change_allowed_between_drops():
    change = StructuralChange(
        mutation_type="hook_motif_variation",
        step=2,
        nearest_drop_step=DROP_STEP,
        change_magnitude=0.08,
        change_mode="progressive",
        is_continuous=True,
    )

    result = evaluate_structural_change(change)

    assert can_apply_progressive_structural_change(change)
    assert result["allowed"] is True
    assert result["reason"] == "continuous_delta_within_basin"


def test_hook_replacement_is_drop_gated():
    before_drop = StructuralChange(
        mutation_type="hook_replacement",
        step=2,
        nearest_drop_step=DROP_STEP,
        change_magnitude=1.0,
        change_mode="instantaneous",
        is_continuous=False,
    )
    at_drop = StructuralChange(
        mutation_type="hook_replacement",
        step=DROP_STEP,
        nearest_drop_step=DROP_STEP,
        change_magnitude=1.0,
        change_mode="instantaneous",
        is_continuous=False,
    )

    assert evaluate_structural_change(before_drop)["allowed"] is False
    assert evaluate_structural_change(at_drop)["allowed"] is True


def test_archetype_snap_is_drop_gated_but_bias_can_be_progressive():
    bias = StructuralChange(
        mutation_type="archetype_bias",
        step=1,
        nearest_drop_step=DROP_STEP,
        change_magnitude=0.12,
        change_mode="progressive",
        is_continuous=True,
    )
    snap = StructuralChange(
        mutation_type="archetype_snap",
        step=1,
        nearest_drop_step=DROP_STEP,
        change_magnitude=0.8,
        change_mode="instantaneous",
        is_continuous=False,
    )

    assert evaluate_structural_change(bias)["allowed"] is True
    assert evaluate_structural_change(snap)["allowed"] is False
    assert can_apply_instant_structural_change(DROP_STEP, DROP_STEP)


def test_drop_is_only_instantaneous_knee():
    large_between = StructuralChange(
        mutation_type="dominant_instrument_hard_switch",
        step=3,
        nearest_drop_step=DROP_STEP,
        change_magnitude=0.9,
        change_mode="instantaneous",
        is_continuous=False,
    )
    same_at_drop = StructuralChange(
        mutation_type="dominant_instrument_hard_switch",
        step=DROP_STEP,
        nearest_drop_step=DROP_STEP,
        change_magnitude=0.9,
        change_mode="instantaneous",
        is_continuous=False,
    )

    assert evaluate_structural_change(large_between)["allowed"] is False
    assert evaluate_structural_change(same_at_drop)["allowed"] is True


def test_phase11_diagnostics_distinguish_progressive_and_instantaneous():
    state = Phase11State()
    state.set_immediate(0.2)
    state.advance(1.0)
    state.mark_drop_committed()

    mutations = state.to_dict()["structural_mutations"]
    assert any(item["change_mode"] == "progressive" and item["allowed"] for item in mutations)
    assert any(
        item["change_mode"] == "instantaneous"
        and item["step"] == item["nearest_drop_step"]
        and item["allowed"]
        for item in mutations
    )
