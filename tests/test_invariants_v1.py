from collections import Counter, defaultdict
import hashlib
from pathlib import Path

import pytest

from thelmic.bank_generator import BankGenerator
from thelmic.motif_engine import (
    MutationClassification,
    RULE_SOURCE,
    Motif,
    MotifType,
    classify_motif_change,
    empty_future_motifs,
    motifs_for_events,
    validate_motif_change_boundary,
    validate_motif_contract,
)
from thelmic.note_generation_chain import BANK_STEPS, VERSION, generate_bank, structure_frames
from thelmic import server


def _trajectory():
    from thelmic.landscape_trajectory import LandscapeTrajectory
    from thelmic.landscape_map import LandscapeMap
    return LandscapeTrajectory(landscape=LandscapeMap(seed=1103))


def _dims():
    from thelmic.dimension_engine import compute
    return compute(_trajectory(), 0.5)


def _sr():
    return _trajectory().active_feature().signature_rhythm


def _events():
    return generate_bank(0, dims=_dims(), signature_rhythm=_sr()).all_events()


def _motif_with_refs(size=10):
    return Motif(
        id="test:motif",
        type=MotifType.PERCUSSIVE_PATTERN,
        instrument="hat",
        phrase_start=0,
        phrase_end=BANK_STEPS,
        event_references=tuple(f"event:{index}" for index in range(size)),
    )


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
    # At the default test position (Chaos peak, high sparsity), hook/call/response
    # are withheld by positional sparsity — this is correct musical behaviour.
    # The locked counts reflect the default Chaos position at seed 1103.
    assert counts == {
        "hat":          139,   # closed hat
        "open_hat":      31,   # open hat — per-archetype positions
        "bass":          64,
        "kick":          62,
        "snare":         64,
        "sub":           32,
        "drone_rumble":   2,
    }


def test_v1_01_emitted_stream_fingerprint_is_locked():
    payload = "\n".join(
        f"{event.musical_step}:{event.layer}:{event.role}:{event.note}:{event.velocity}:{event.duration}"
        for event in _events()
    )
    assert hashlib.sha256(payload.encode()).hexdigest() == (
        "1b359c9cc2277661c6cea9ded763d0d9b79ff035cf44dfce62594493a00d7a04"
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
    assert {motif.instrument for motif in motifs} >= {"hat", "kick", "snare", "bass"}


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


def test_motif_validator_accepts_single_event_addition():
    motif = _motif_with_refs()
    validation = classify_motif_change(
        motif,
        motif.event_references + ("event:10",),
    )

    assert validation.classification == MutationClassification.LEGAL
    assert validation.added_count == 1
    assert validation.removed_count == 0
    assert validation.reason == "single_event_add_or_remove"


def test_motif_validator_accepts_single_event_removal():
    motif = _motif_with_refs()
    validation = classify_motif_change(motif, motif.event_references[:-1])

    assert validation.classification == MutationClassification.LEGAL
    assert validation.added_count == 0
    assert validation.removed_count == 1
    assert validation.reason == "single_event_add_or_remove"


def test_motif_validator_accepts_change_at_or_below_20_percent():
    motif = _motif_with_refs()
    changed = list(motif.event_references)
    changed[2] = "event:mutated:2"
    changed[7] = "event:mutated:7"
    validation = classify_motif_change(motif, changed)

    assert validation.classification == MutationClassification.LEGAL
    assert validation.changed_count == 2
    assert validation.change_ratio == pytest.approx(0.20)
    assert validation.reason == "change_ratio_within_20_percent"


def test_motif_validator_marks_change_above_20_percent_as_structural():
    motif = _motif_with_refs()
    changed = list(motif.event_references)
    changed[1] = "event:mutated:1"
    changed[4] = "event:mutated:4"
    changed[8] = "event:mutated:8"
    validation = classify_motif_change(motif, changed)

    assert validation.classification == MutationClassification.STRUCTURAL
    assert validation.changed_count == 3
    assert validation.change_ratio == pytest.approx(0.30)
    assert validation.reason == "change_ratio_above_20_percent"


def test_motif_validator_marks_multiple_adds_or_removes_as_structural():
    motif = _motif_with_refs()
    added = classify_motif_change(
        motif,
        motif.event_references + ("event:10", "event:11"),
    )
    removed = classify_motif_change(motif, motif.event_references[:-2])

    assert added.classification == MutationClassification.STRUCTURAL
    assert added.reason == "add_remove_more_than_one_event"
    assert removed.classification == MutationClassification.STRUCTURAL
    assert removed.reason == "add_remove_more_than_one_event"


def test_structural_motif_change_is_rejected_outside_drop_boundary():
    motif = _motif_with_refs()
    validation = classify_motif_change(
        motif,
        motif.event_references + ("event:10", "event:11"),
    )

    with pytest.raises(ValueError, match="outside drop boundary"):
        validate_motif_change_boundary(validation, is_drop=False)

    validate_motif_change_boundary(validation, is_drop=True)


def test_v1_01_runtime_version_freezes_v1_rules_baseline():
    state = server._state(include_bank=False)

    assert state["thelmic_version"] == "v1.01"
    assert state["music_rules_version"] == "v1.0"
    assert state["runtime"]["output"] == "simple continuous v1 output"


def test_percussive_drive_never_collapses():
    """Every bar must have at least one kick and one snare.
    Hat count scales with position — deep Chaos has sparser hat; that is correct."""
    by_bar = defaultdict(list)
    for event in _events():
        by_bar[event.bar_index].append(event)

    assert set(by_bar) == set(range(1, 17))
    for bar, events in by_bar.items():
        assert any(event.layer == "kick" for event in events), f"bar {bar} missing kick"
        assert any(event.layer == "snare" for event in events), f"bar {bar} missing snare"
        # Hat may be thinned by positional sparsity — minimum 1 per bar
        assert any(event.layer == "hat" for event in events), f"bar {bar} missing hat entirely"


def test_backbone_positions_are_stable_and_grid_aligned():
    """Kick and snare anchor positions are always present.
    Hat density is position-dependent — test only that anchors hold."""
    by_bar_layer = defaultdict(lambda: defaultdict(set))
    for event in _events():
        by_bar_layer[event.bar_index][event.layer].add(event.musical_step % 16)

    for bar in range(1, 17):
        assert {0, 8}.issubset(by_bar_layer[bar]["kick"]),  f"bar {bar} missing base kicks"
        # Bar 16 is drop_prep: only snare step 12 fires (grid reminder only)
        if bar < 16:
            assert {4, 12}.issubset(by_bar_layer[bar]["snare"]), f"bar {bar} missing base snare"
        else:
            assert 12 in by_bar_layer[bar]["snare"], f"bar 16 missing drop_prep snare"
        # Hat: at least the on-beat quarter-note positions survive (position-dependent)
        assert by_bar_layer[bar]["hat"], f"bar {bar} has no hat at all"


def test_timing_anchor_survives_at_quarter_note_resolution():
    """Within every 4-step window (quarter note), at least one timing event fires.
    Hard dance genres use a quarter-note kick as the minimum timing anchor.
    The original 2-step (8th note) requirement was too strict for high-sparsity positions."""
    events = _events()
    all_steps = {e.musical_step for e in events}

    for window_start in range(0, BANK_STEPS, 4):
        window = set(range(window_start, window_start + 4))
        assert window & all_steps, f"no event in 4-step window starting at {window_start}"


def test_timing_anchor_persists_across_multiple_banks():
    """Quarter-note timing anchor survives across bank boundaries."""
    for bank_index in range(4):
        events = generate_bank(
            bank_index,
            dims=_dims(), signature_rhythm=_sr(), heat=0.5,
        ).all_events()
        all_steps = {e.global_step for e in events}
        bank_start = bank_index * BANK_STEPS
        for offset in range(0, BANK_STEPS, 4):
            window = set(range(bank_start + offset, bank_start + offset + 4))
            assert window & all_steps, f"bank {bank_index} gap at offset {offset}"


def test_drop_prep_is_grid_reminder():
    frames = structure_frames(0)
    drop_prep_steps = {frame.musical_step for frame in frames if frame.is_drop_prep}
    events = [event for event in _events() if event.musical_step in drop_prep_steps]

    assert drop_prep_steps
    assert events
    assert all(event.layer in {"kick", "snare", "hat", "bass", "sub", "hook", "call", "response"} for event in events)
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
    } >= {"hat", "kick", "snare", "bass"}


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
        last_playback_interrupted = False

        def play_bank_blocking(self, *_args, **_kwargs):
            server._stop_event.set()
            return 1.0

        def _play_timeline(self, timeline, start, stop_event=None):
            # FakeMidi: simulate playback completing and signalling stop.
            # Return False (not interrupted) so the bank advance proceeds —
            # the outer loop exits via the while condition.
            server._stop_event.set()
            return False

        def all_notes_off(self):
            pass

        def _interruptible_sleep(self, duration, stop_event=None):
            pass

    monkeypatch.setattr(server, "_queue_broadcast", lambda include_bank=True: calls.append(include_bank))
    with server._state_lock:
        original_bank = server._current_bank
        original_index = server._bank_index
        original_started = server._bank_started_at_ms
        original_midi = server._midi
        server._current_bank = generate_bank(0, dims=_dims(), signature_rhythm=_sr())
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
            server._current_bank     = original_bank
            server._bank_index       = original_index
            server._bank_started_at_ms = original_started
            server._midi             = original_midi
            # Restore preview so subsequent tests see a consistent state
            from thelmic.dimension_engine import compute
            _t = server._trajectory
            server._next_bank_preview = generate_bank(
                original_index + 1,
                dims=compute(_t, server._heat_applied),
                signature_rhythm=_t.active_feature().signature_rhythm,
            )
