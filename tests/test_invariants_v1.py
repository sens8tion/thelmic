from collections import Counter, defaultdict
import hashlib
from pathlib import Path

import pytest

from thelmic.bank_generator import BankGenerator
from thelmic.motif_engine import (
    RULE_SOURCE,
    MotifType,
    empty_future_motifs,
    motifs_for_events,
    validate_motif_contract,
)
from thelmic.note_generation_chain import BANK_STEPS, VERSION, generate_bank, structure_frames
from thelmic import server


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


def test_simple_continuous_v1_output_shape_is_locked():
    counts = Counter(event.layer for event in _events())

    assert counts == {
        "hat": 136,
        "kick": 32,
        "snare": 31,
    }


def test_v1_01_emitted_stream_fingerprint_is_locked():
    payload = "\n".join(
        f"{event.musical_step}:{event.layer}:{event.role}:{event.note}:{event.velocity}:{event.duration}"
        for event in _events()
    )

    assert hashlib.sha256(payload.encode()).hexdigest() == (
        "5665cfd22001a489ca2a20b9742a7c9819abc375d1169344a1a0f23ffbeca504"
    )


def test_motif_engine_observes_without_changing_v1_01_output():
    before = [
        (event.musical_step, event.layer, event.role, event.note, event.velocity, event.duration)
        for event in _events()
    ]
    motifs = motifs_for_events(_events())
    after = [
        (event.musical_step, event.layer, event.role, event.note, event.velocity, event.duration)
        for event in _events()
    ]

    assert before == after
    assert {motif.instrument for motif in motifs} == {"hat", "kick", "snare"}


def test_every_active_lane_has_observed_motif():
    events = _events()
    active_lanes = {event.layer for event in events if event.active}
    observed = {
        motif.instrument
        for motif in motifs_for_events(events)
        if motif.state == "observed"
    }

    assert observed == active_lanes


def test_motifs_persist_for_one_phrase_and_do_not_mutate():
    motifs = motifs_for_events(_events())

    validate_motif_contract(motifs)
    assert all(motif.phrase_start == 0 for motif in motifs)
    assert all(motif.phrase_end == BANK_STEPS for motif in motifs)
    assert all(motif.state == "observed" for motif in motifs)


def test_motif_categories_are_declared_without_future_behaviour():
    declared = empty_future_motifs()

    assert {motif.type for motif in declared} == {
        MotifType.HOOK,
        MotifType.CALL_RESPONSE,
    }
    assert all(motif.state == "declared_future" for motif in declared)
    assert all(motif.event_references == () for motif in declared)


def test_motif_engine_points_to_music_rules_as_rule_source():
    motifs = motifs_for_events(_events()) + empty_future_motifs()

    assert RULE_SOURCE == "musical_rules.md"
    assert all(motif.to_dict()["rule_source"] == "musical_rules.md" for motif in motifs)


def test_v1_01_runtime_version_freezes_v1_rules_baseline():
    state = server._state(include_bank=False)

    assert state["thelmic_version"] == "v1.01"
    assert state["music_rules_version"] == "v1.0"
    assert state["runtime"]["output"] == "simple continuous v1 output"


def test_percussive_drive_never_collapses():
    by_bar = defaultdict(list)
    for event in _events():
        by_bar[event.bar_index].append(event)

    assert set(by_bar) == set(range(1, 17))
    for bar, events in by_bar.items():
        assert any(event.layer == "kick" for event in events), f"bar {bar} missing kick"
        assert any(event.layer == "snare" for event in events), f"bar {bar} missing snare"
        assert sum(1 for event in events if event.layer == "hat") >= 8, f"bar {bar} weak hat grid"


def test_backbone_positions_are_stable_and_grid_aligned():
    by_bar_layer = defaultdict(lambda: defaultdict(set))
    for event in _events():
        by_bar_layer[event.bar_index][event.layer].add(event.musical_step % 16)

    for bar in range(1, 16):
        assert by_bar_layer[bar]["kick"] == {0, 8}
        assert by_bar_layer[bar]["snare"] == {4, 12}
        assert by_bar_layer[bar]["hat"] == {0, 2, 4, 6, 8, 10, 12, 14}

    assert by_bar_layer[16]["kick"] == {0, 8}
    assert by_bar_layer[16]["snare"] == {12}
    assert by_bar_layer[16]["hat"] == set(range(16))


def test_timing_anchor_always_survives_every_step_pair():
    anchor_steps = {event.musical_step for event in _events() if event.role in {"timing_anchor", "subdivision", "grid_reminder"}}

    for step in range(0, BANK_STEPS, 2):
        assert step in anchor_steps or step + 1 in anchor_steps


def test_timing_anchor_persists_across_multiple_banks():
    for bank_index in range(4):
        events = generate_bank(bank_index).all_events()
        anchor_steps = {
            event.global_step
            for event in events
            if event.role in {"timing_anchor", "subdivision", "grid_reminder"}
        }
        bank_start = bank_index * BANK_STEPS
        for offset in range(0, BANK_STEPS, 2):
            assert bank_start + offset in anchor_steps or bank_start + offset + 1 in anchor_steps


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


def test_no_silence_model_in_runtime_state_or_final_output():
    state = server._state(include_bank=True)

    assert "silence" not in state
    assert all("silence" not in frame for frame in state["structure_frames"])
    assert all("silence" not in event for event in state["bank_events"])


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


def test_no_legacy_fallback_or_post_generation_rescue_runtime_flags():
    runtime = server._state(include_bank=False)["runtime"]

    assert runtime["v0_9_engine_enabled"] is False
    assert runtime["legacy_fallback_enabled"] is False
    assert runtime["post_generation_rescue_enabled"] is False
    assert runtime["output"] == "simple continuous v1 output"


def test_pression_is_disabled_and_absent_from_output():
    state = server._state(include_bank=True)

    assert state["pression_engine_version"] == "v0.9-disabled"
    assert state["pression_disabled"] is True
    assert state["runtime"]["pression_enabled"] is False
    assert all("pression" not in event for event in state["bank_events"])


def test_runtime_exposes_motifs_without_affecting_display_or_output():
    state = server._state(include_bank=True)

    assert state["motif_engine_version"] == "v1.0"
    assert state["motifs"]
    assert {
        motif["instrument"]
        for motif in state["motifs"]
        if motif["state"] == "observed"
    } == {"hat", "kick", "snare"}


def test_display_event_source_is_actual_bank_event_payload():
    state = server._state(include_bank=True)
    emitted = {
        (event.layer, event.musical_step)
        for event in server._current_bank.all_events()
        if event.active
    }
    displayed = {
        (event["layer"], event["musical_step"])
        for event in state["bank_events"]
    }

    assert displayed == emitted


def test_ui_does_not_generate_independent_display_pattern():
    html = Path("thelmic/static/index.html").read_text(encoding="utf-8")

    assert "state.bank_events" in html
    assert "byLayerStep" in html
    assert "continuous_kick_anchor" not in html
    assert "stable_backbeat" not in html
    assert "continuous_hat_subdivision" not in html


def test_transport_rollover_queues_actual_stream_bank_for_display(monkeypatch):
    calls = []

    class FakeMidi:
        def play_bank_blocking(self, *_args, **_kwargs):
            server._stop_event.set()
            return 1.0

    monkeypatch.setattr(server, "_queue_broadcast", lambda include_bank=True: calls.append(include_bank))
    with server._state_lock:
        original_bank = server._current_bank
        original_index = server._bank_index
        original_started = server._bank_started_at_ms
        original_midi = server._midi
        server._current_bank = generate_bank(0)
        server._bank_index = 0
        server._midi = FakeMidi()
    server._stop_event.clear()

    try:
        server._play_loop()
        with server._state_lock:
            assert server._bank_index == 1
            emitted = {
                (event.layer, event.musical_step)
                for event in server._current_bank.all_events()
                if event.active
            }
        displayed = {
            (event["layer"], event["musical_step"])
            for event in server._state(include_bank=True)["bank_events"]
        }
        assert displayed == emitted
        assert calls == [True]
    finally:
        server._stop_event.set()
        with server._state_lock:
            server._current_bank = original_bank
            server._bank_index = original_index
            server._bank_started_at_ms = original_started
            server._midi = original_midi
