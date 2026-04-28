from thelmic.arrangement import ensure_beat_bed, generate_sub_from_bassline, arrangement_diagnostics
from thelmic.bank_generator import Bank, MIDIEvent, Phrase
from thelmic.behaviour_field import BehaviourField
from thelmic.calls import generate_planned_calls
from thelmic.drop_enforcer import DROP_STEP, enforce_drop_relock
from thelmic.phase11 import Phase11State
from thelmic.phrase_plan import PhrasePlan, PlanNote, SilenceMask, PhraseState, generate_phrase_plan
from thelmic.responses import generate_planned_responses
from thelmic.syntax_enforcer import time_to_bar_step


def _behaviour():
    return BehaviourField(
        ghost_intensity=0.4,
        ghost_clustering=0.4,
        anchor_drop_prob=0.0,
        filter_target=0.5,
        gate_tightness=0.4,
        energy_level=0.8,
        accent_strength=0.6,
        ghost_velocity=0.5,
        anchor_velocity=0.9,
    )


def _event(time="1.1.0", layer="kick", role="anchor", note=36, velocity=100):
    return MIDIEvent(
        time=time,
        note=note,
        velocity=velocity,
        duration=0.08,
        layer=layer,
        role=role,
        emphasis=0.8,
        openness=1.0,
        expected_weight=0.8,
        should_resolve=False,
    )


def _bank(*events):
    return Bank(bank_index=0, phrases=[Phrase(phrase_index=0, events=list(events))])


def test_stab_is_default_committed_call_response_leader():
    state = Phase11State()

    assert state.call_response_leader == "stab"
    assert state.pending_call_response_leader == "stab"

    state.set_target(0.41)
    assert state.call_response_leader == "stab"
    state.mark_drop_committed()
    assert state.call_response_leader in {"stab", "bass", "hook", "snare"}


def test_planned_call_response_uses_committed_leader_layer():
    plan = generate_phrase_plan()
    events = [_event("3.1.0"), _event("6.1.0")]

    calls = generate_planned_calls(events, _behaviour(), plan, leader_layer="stab")
    responses = generate_planned_responses(events, _behaviour(), plan, leader_layer="stab")

    assert calls.events
    assert responses.events
    assert {event.layer for event in calls.events + responses.events} == {"stab"}


def test_beat_bed_populates_kick_snare_hat_outside_silence():
    plan = PhrasePlan(
        bass_pattern=(),
        hook_pattern=(),
        phrase_state={1: PhraseState.RESOLVED_STABLE},
        call_slots={},
        response_slots={},
        silence_mask=SilenceMask({}),
        pressure_curve={1: 0.0},
    )
    bank = _bank(_event("1.1.0"))

    stats = ensure_beat_bed(bank, plan, Phase11State())
    layers = {event.layer for event in bank.all_events()}

    assert {"kick", "snare", "hat"}.issubset(layers)
    assert stats["beat_bed_presence"] == {"kick": True, "snare": True, "hat": True}
    assert stats["hat_density"] >= stats["snare_density"]
    assert stats["sparsity_reason"] == "none"


def test_sub_is_sparse_sustained_and_derived_from_bass():
    bass = [_event("1.1.0", layer="bassline", role="bassline", note=36, velocity=100)]

    sub = generate_sub_from_bassline(bass, _behaviour())

    assert len(sub) == 1
    assert sub[0].layer == "sub"
    assert sub[0].role == "sub"
    assert sub[0].duration >= 1.0
    assert sub[0].note == 24


def test_sub_pattern_uses_long_duration_vocabulary():
    bass = [
        _event("1.1.0", layer="bassline", role="bassline", note=36, velocity=100),
        _event("2.1.0", layer="bassline", role="bassline", note=36, velocity=100),
    ]

    chaos_sub = generate_sub_from_bassline(bass, _behaviour(), landscape_position=0.5)
    nott_sub = generate_sub_from_bassline(bass, _behaviour(), landscape_position=1.0)

    assert {round(event.duration / 0.08) for event in chaos_sub}.issubset({4, 8})
    assert {round(event.duration / 0.08) for event in nott_sub} == {32}
    assert all(round(event.duration / 0.08) >= 4 for event in chaos_sub + nott_sub)


def test_bass_sub_diagnostics_expose_pattern_types_and_alignment():
    bass = _event("1.1.12", layer="bassline", role="bassline", note=36, velocity=100)
    bass.duration = 0.16
    bass.deformation["bass_pattern:offbeat_pulse"] = 1.0
    bass.deformation["bass_phrase_length"] = 1.0
    sub = _event("1.1.0", layer="sub", role="sub", note=24, velocity=80)
    sub.duration = 1.28
    sub.deformation["sub_pattern:full_bar_hold"] = 1.0
    sub.deformation["sub_hold_length"] = 16.0

    stats = arrangement_diagnostics(_bank(bass, sub), Phase11State())

    assert stats["bass_pattern_type"] == "offbeat_pulse"
    assert stats["bass_note_durations"] == [2]
    assert stats["bass_phrase_length"] == 1
    assert stats["sub_pattern_type"] == "full_bar_hold"
    assert stats["sub_note_durations"] == [16]
    assert stats["sub_hold_length"] == 16
    assert stats["bass_sub_alignment_score"] == 1.0


def test_drop_relock_ensures_sub_with_kick_and_bassline():
    plan = PhrasePlan(
        bass_pattern=(PlanNote(bar=1, step=DROP_STEP, pitch=36),),
        hook_pattern=(),
        phrase_state={1: PhraseState.DROP_RELOCK},
        call_slots={},
        response_slots={},
        silence_mask=SilenceMask({1: tuple(range(0, DROP_STEP))}),
        pressure_curve={1: 1.0},
    )
    bank = _bank(_event("1.2.0", layer="hat", note=42))

    stats = enforce_drop_relock(bank, plan)
    layers_at_drop = {
        event.layer
        for event in bank.all_events()
        if time_to_bar_step(event.time) == (1, DROP_STEP)
    }

    assert {"kick", "bassline", "sub"}.issubset(layers_at_drop)
    assert stats["sub_at_drop"] == 1
    assert stats["bassline_at_drop"] == 1


def test_velocity_diagnostics_assign_loudness_to_note_event_bus():
    bank = _bank(_event("1.1.0", velocity=91))
    stats = arrangement_diagnostics(bank, Phase11State())

    assert stats["note_velocity_source"] == "note_event_bus"
    assert stats["cc_volume_control_used"] is False
    assert stats["event_velocity"]["max"] == 91
