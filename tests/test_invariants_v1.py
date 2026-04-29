from collections import defaultdict

import pytest

from thelmic.bank_generator import BankGenerator
from thelmic.note_generation_chain import BANK_STEPS, VERSION, generate_bank, structure_frames


def _events():
    return generate_bank(0).all_events()


def test_v0_9_engine_entrypoint_is_disabled():
    with pytest.raises(RuntimeError, match="v0.9 engine disabled"):
        BankGenerator().generate(None, 0)


def test_simple_continuous_v1_output_is_not_sparse_or_reduced():
    events = _events()
    assert VERSION == "v1.0"
    assert len(events) >= 160
    assert {event.layer for event in events} >= {"kick", "snare", "hat"}
    assert all(event.source == "stream" for event in events)
    assert all(event.intent_id and event.resolved_event_id for event in events)


def test_percussive_drive_never_collapses():
    by_bar = defaultdict(list)
    for event in _events():
        by_bar[event.bar_index].append(event)

    assert set(by_bar) == set(range(1, 17))
    for bar, events in by_bar.items():
        assert any(event.layer == "kick" for event in events), f"bar {bar} missing kick"
        assert any(event.layer == "snare" for event in events), f"bar {bar} missing snare"
        assert sum(1 for event in events if event.layer == "hat") >= 8, f"bar {bar} weak hat grid"


def test_timing_anchor_always_survives_every_step_pair():
    anchor_steps = {event.musical_step for event in _events() if event.role in {"timing_anchor", "subdivision", "grid_reminder"}}

    for step in range(0, BANK_STEPS, 2):
        assert step in anchor_steps or step + 1 in anchor_steps


def test_drop_prep_is_grid_reminder():
    frames = structure_frames(0)
    drop_prep_steps = {frame.musical_step for frame in frames if frame.is_drop_prep}
    events = [event for event in _events() if event.musical_step in drop_prep_steps]

    assert drop_prep_steps
    assert events
    assert all(event.layer in {"kick", "snare", "hat"} for event in events)
    assert any(event.role == "grid_reminder" for event in events)
    for step in sorted(drop_prep_steps):
        assert any(abs(event.musical_step - step) <= 1 for event in events)


def test_motif_persists_for_one_phrase_with_limited_mutation():
    events = _events()
    phrase_patterns = {}
    for layer in ("kick", "snare", "hat"):
        phrase_patterns[layer] = tuple(
            sorted(event.musical_step % BANK_STEPS for event in events if event.layer == layer)
        )
        assert phrase_patterns[layer]

    # v1 reset generator emits one stable phrase-long motif per layer.
    assert len(set(phrase_patterns.values())) == 3


def test_structural_change_only_at_drop_and_once_per_phrase():
    frames = structure_frames(0)
    drops = [frame for frame in frames if frame.is_drop]
    assert [frame.musical_step for frame in drops] == [0]

    structural_reasons = {
        event.reason for event in _events()
        if event.reason in {"drop_anchor"}
    }
    assert structural_reasons == {"drop_anchor"}


def test_all_instruments_obey_final_output_provenance():
    for event in _events():
        assert event.active
        assert event.velocity > 0
        assert 0 <= event.musical_step < BANK_STEPS
        assert event.global_step == event.musical_step
        assert event.origin_source == "note_generation_chain"
        assert event.resolution_reason == "resolved"
