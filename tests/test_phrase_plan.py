from thelmic.phrase_plan import PhraseState, generate_phrase_plan


def test_default_phrase_plan_has_required_outputs():
    plan = generate_phrase_plan()

    assert plan.bass_pattern
    assert plan.hook_pattern
    assert plan.phrase_state
    assert plan.call_slots
    assert plan.response_slots
    assert plan.silence_mask.muted_steps_by_bar
    assert plan.pressure_curve


def test_default_phrase_plan_uses_legible_state_order():
    plan = generate_phrase_plan()

    assert plan.phrase_state[1] == PhraseState.RESOLVED_STABLE
    assert plan.phrase_state[3] == PhraseState.CALL_UNRESOLVED
    assert plan.phrase_state[5] == PhraseState.HOLD_SILENCE
    assert plan.phrase_state[6] == PhraseState.RESPONSE_RESOLVED
    assert plan.phrase_state[8] == PhraseState.DROP_RELOCK


def test_default_call_response_and_silence_are_separated():
    plan = generate_phrase_plan()

    assert set(plan.call_slots) == {3, 4}
    assert set(plan.response_slots) == {6, 7}
    assert all(step < 8 for steps in plan.call_slots.values() for step in steps)
    assert all(step >= 8 for steps in plan.response_slots.values() for step in steps)
    assert 5 in plan.silence_mask.muted_steps_by_bar
    assert 8 in plan.silence_mask.muted_steps_by_bar
