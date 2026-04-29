import pytest

from thelmic.bank_generator import Bank, MIDIEvent, Phrase
from thelmic import server


def test_server_payload_includes_structure_frames_for_visible_grid():
    server._init_engine()

    state = server._force_state_dict(include_bank=True)
    frames = state["structure_frames"]

    assert len(frames) == 256
    assert frames[0]["global_step"] == 0
    assert frames[0]["musical_step"] == 0
    assert frames[0]["bar_index"] == 1
    assert frames[0]["is_bar_start"] is True
    assert frames[0]["is_phrase_start"] is True
    assert frames[0]["is_subphrase_start"] is True


def test_structure_frame_phrase_boundaries_align_to_bar_starts():
    server._init_engine()

    frames = server._force_state_dict(include_bank=True)["structure_frames"]
    phrase_starts = [frame for frame in frames if frame["is_phrase_start"]]

    assert phrase_starts
    assert all(frame["is_bar_start"] for frame in phrase_starts)
    assert all(frame["step_in_bar"] == 0 for frame in phrase_starts)


def test_structure_frame_subphrases_sit_inside_phrase_spans():
    server._init_engine()

    frames = server._force_state_dict(include_bank=True)["structure_frames"]
    phrase_starts = [frame["musical_step"] for frame in frames if frame["is_phrase_start"]]
    subphrase_starts = [
        frame["musical_step"]
        for frame in frames
        if frame["is_subphrase_start"] and not frame["is_phrase_start"]
    ]

    assert phrase_starts == [0]
    assert subphrase_starts == [128]
    assert all(phrase_starts[0] < step < 256 for step in subphrase_starts)


def test_ui_consumes_structure_frames_for_structure_overlay():
    source = open("thelmic/static/index.html", encoding="utf-8").read()

    assert "s.structure_frames" in source
    assert "updateStructureFrames(s.structure_frames)" in source
    assert "updatePhraseContext" not in source
    assert "_phraseContextByStep" not in source
    assert "sourceStep % STEPS" not in source


def test_server_bank_payload_uses_stream_hook_events():
    server._init_engine()
    bank = server._generator.generate(
        server._engine.force_state,
        0,
        server._engine.landscape_position,
        kick_authority="stream",
        hat_authority="stream",
    )
    server._current_bank = bank
    server._apply_behaviour_modules_to_bank(bank, {})

    payload = server._bank_events_list(bank)
    hook_events = [event for event in payload if event["layer"] == "hook"]

    assert hook_events
    assert all(event["origin_source"] == "stream_hook" for event in hook_events)
    assert all(event["origin_reason"] for event in hook_events)
    assert all(event["resolution_reason"] == "resolved" for event in hook_events)
    assert server._runtime_debug["hook_source"] == "stream_engine"
    assert server._runtime_debug["hook_intents_suppressed"] > 0


def test_server_bank_payload_uses_stream_kick_and_hat_events():
    server._init_engine()
    bank = server._generator.generate(
        server._engine.force_state,
        0,
        server._engine.landscape_position,
        kick_authority="stream",
        hat_authority="stream",
    )
    server._current_bank = bank
    server._apply_behaviour_modules_to_bank(bank, {})

    payload = server._bank_events_list(bank)
    kicks = [event for event in payload if event["layer"] == "kick"]
    hats = [
        event for event in payload
        if event["layer"] == "hat" and event["role"] != "survivor"
    ]

    assert kicks
    assert hats
    assert all(event["origin_source"] == "stream_kick" for event in kicks)
    assert all(event["origin_source"] == "stream_hat" for event in hats)
    assert all(event["source"] == "stream" for event in kicks + hats)
    assert all(event["intent_id"] for event in kicks + hats)
    assert all(event["resolved_event_id"] for event in kicks + hats)
    assert all(event["phrase_index"] >= 0 for event in kicks + hats)
    assert all(event["bar_index"] >= 1 for event in kicks + hats)
    assert all(event["reason"] for event in kicks + hats)
    assert all(event["resolution_reason"] == "resolved" for event in kicks + hats)
    assert server._runtime_debug["kick_source"] == "stream_engine"
    assert server._runtime_debug["hat_source"] == "stream_engine"
    assert server._runtime_debug["hook_source"] == "stream_engine"


def test_legacy_modules_receive_stream_anchors_without_reclassifying_them():
    server._init_engine()
    bank = server._generator.generate(
        server._engine.force_state,
        0,
        server._engine.landscape_position,
        kick_authority="stream",
        hat_authority="stream",
    )
    server._current_bank = bank
    server._apply_behaviour_modules_to_bank(bank, {})

    seen = server._runtime_debug["stream_anchor_sources_seen_by_legacy"]
    payload = server._bank_events_list(bank)
    normal_kicks = [event for event in payload if event["layer"] == "kick"]
    normal_hats = [
        event for event in payload
        if event["layer"] == "hat" and event["role"] != "survivor"
    ]

    assert seen["kick"] > 0
    assert seen["hat"] > 0
    assert any(event["layer"] == "bassline" for event in payload)
    assert all(event["source"] == "stream" for event in normal_kicks + normal_hats)
    assert all(event["origin_source"] in {"stream_kick", "stream_hat"} for event in normal_kicks + normal_hats)


def test_stream_authority_guard_fails_loudly_on_legacy_kick_or_hat():
    bank = Bank(
        bank_index=0,
        phrases=[
            Phrase(
                phrase_index=0,
                events=[
                    MIDIEvent(
                        time="1.1.0",
                        note=36,
                        velocity=100,
                        duration=0.08,
                        layer="kick",
                        role="anchor",
                        emphasis=1.0,
                        openness=1.0,
                        expected_weight=1.0,
                        should_resolve=False,
                    ),
                    MIDIEvent(
                        time="1.1.6",
                        note=42,
                        velocity=70,
                        duration=0.03,
                        layer="hat",
                        role="anchor",
                        emphasis=0.6,
                        openness=1.0,
                        expected_weight=0.5,
                        should_resolve=False,
                    ),
                ],
            )
        ],
    )

    with pytest.raises(RuntimeError, match="stream authority violation"):
        server._assert_stream_authority(bank)
