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
