from thelmic.behaviour_field import compute_behaviour_field
from thelmic.call_response import Mode
from thelmic.bank_generator import Bank
from thelmic.force_engine import ForceState
from thelmic.pression import (
    DEFAULT_CC_MAP,
    DIMENSION_NAMES,
    compute_bank_timeline,
    compute_pression_bar,
)


def _bar(mode: Mode):
    force = ForceState(anticipation=0.4, release_pressure=0.2, instability=0.3)
    behaviour = compute_behaviour_field(force, transition=None)
    return compute_pression_bar(
        force=force,
        behaviour=behaviour,
        transition=None,
        cr_mode=mode,
        bar_events=[],
        bar_idx=0,
    )


def test_instrument_resolved_pression_dimensions_are_exported():
    for name in ("bass_intensity", "stab_intensity"):
        assert name in DIMENSION_NAMES
        assert name in DEFAULT_CC_MAP
        assert DEFAULT_CC_MAP[name][1] in {30, 31}

    for removed in (
        "bass_call_intensity",
        "bass_response_intensity",
        "stab_call_intensity",
        "stab_response_intensity",
    ):
        assert removed not in DIMENSION_NAMES
        assert removed not in DEFAULT_CC_MAP


def test_bass_leads_routes_call_to_bass_and_response_to_stab():
    bar = _bar(Mode.BASS_LEADS)

    assert bar.bass_intensity == bar.call_intensity
    assert bar.stab_intensity == bar.response_intensity


def test_stab_leads_routes_call_to_stab_and_response_to_bass():
    bar = _bar(Mode.STAB_LEADS)

    assert bar.stab_intensity == bar.call_intensity
    assert bar.bass_intensity == bar.response_intensity


def test_phrase_level_targets_move_over_eight_bars_without_resetting():
    force = ForceState(anticipation=0.8, release_pressure=0.5, instability=0.45)
    behaviour = compute_behaviour_field(force, transition=None)
    timeline = compute_bank_timeline(
        force=force,
        behaviour=behaviour,
        transition=None,
        cr_mode=Mode.BASS_LEADS,
        bank=Bank(bank_index=0),
        phrase_length_bars=8,
        phrase_strength=1.0,
    )

    lanes = (
        "pressure",
        "density",
        "silence",
        "bass_intensity",
        "stab_intensity",
    )
    for lane in lanes:
        first = timeline[0].phrase_state[lane]
        middle = timeline[4].phrase_state[lane]
        last = timeline[7].phrase_state[lane]
        next_phrase = timeline[8].phrase_state[lane]

        assert first.phrase_length_bars == 8
        assert first.phrase_position == 0.0
        assert middle.phrase_position == 0.5
        assert first.current_value != first.target_value
        assert next_phrase.current_value == first.target_value
        assert next_phrase.target_value != first.target_value

        peaks = [max(getattr(timeline[i], lane)) for i in range(8)]
        assert max(peaks) - min(peaks) > 5


def test_phrase_drop_build_sparse_predrop_and_arrival_spike():
    force = ForceState(anticipation=0.75, release_pressure=0.45, instability=0.5)
    behaviour = compute_behaviour_field(force, transition=None)
    timeline = compute_bank_timeline(
        force=force,
        behaviour=behaviour,
        transition=None,
        cr_mode=Mode.BASS_LEADS,
        bank=Bank(bank_index=0),
        phrase_length_bars=8,
        phrase_strength=1.0,
    )

    early = timeline[1]
    mid = timeline[4]
    pre_gap = timeline[6]
    predrop = timeline[7]
    drop = timeline[8]

    assert max(mid.pressure) > max(early.pressure)
    assert max(predrop.riser) > max(mid.riser)
    assert max(predrop.riser) <= max(pre_gap.riser)
    assert max(predrop.silence) > max(mid.silence)
    assert max(predrop.density) < max(mid.density)
    assert max(predrop.density) < max(pre_gap.density)
    assert max(predrop.impact) < max(mid.pressure)
    assert max(predrop.impact) < max(pre_gap.impact)
    assert max(predrop.landing_strength) < max(pre_gap.landing_strength)
    assert max(predrop.pressure) > max(mid.pressure)
    assert max(drop.impact) > max(predrop.impact)
    assert max(drop.landing_strength) > max(predrop.landing_strength)
    assert max(drop.silence) < max(predrop.silence)
    assert max(drop.riser) < max(predrop.riser)
    assert drop.phrase_state["pressure"].tension == 0.0
    assert predrop.phrase_state["pressure"].anticipation > 0.5
    assert predrop.phrase_state["silence"].thinning > 0.5
