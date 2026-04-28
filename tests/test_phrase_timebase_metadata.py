from thelmic.server import _phrase_context_steps, _phrase_metadata_list


def test_phrase_metadata_exposes_canonical_timebase_markers():
    metadata = _phrase_metadata_list()

    assert [m["musical_step"] for m in metadata] == [116, 244]
    assert [m["bar_index"] for m in metadata] == [8, 16]
    assert all(m["start_step"] == m["phrase_start_step"] for m in metadata)


def test_phrase_entries_use_same_start_steps_as_timebase():
    metadata = _phrase_metadata_list()
    context = _phrase_context_steps()
    phrase_starts = [ctx for ctx in context if ctx["is_phrase_start"]]

    assert [m["start_step"] for m in metadata] == [
        ctx["musical_step"]
        for ctx in phrase_starts
    ]
    assert [m["phrase_index"] for m in metadata] == [
        ctx["phrase_index"]
        for ctx in phrase_starts
    ]


def test_phrase_context_steps_are_resolved_per_musical_step():
    context = _phrase_context_steps()

    assert len(context) == 256
    assert context[0]["musical_step"] == 0
    assert context[0]["bar_index"] == 1
    assert context[0]["phrase_index"] == 0
    assert context[0]["sub_phrase_index"] == 0
    assert context[0]["phrase_start_step"] == -12
    assert context[0]["is_phrase_start"] is False
    assert context[0]["is_sub_phrase_start"] is False

    assert context[116]["musical_step"] == 116
    assert context[116]["bar_index"] == 8
    assert context[116]["step_in_bar"] == 4
    assert context[116]["phrase_index"] == 1
    assert context[116]["is_phrase_start"] is True
    assert context[116]["is_sub_phrase_start"] is True

    assert context[117]["is_phrase_start"] is False
    assert context[117]["is_sub_phrase_start"] is False


def test_phrase_context_puts_pre_drop_silence_inside_previous_phrase():
    context = _phrase_context_steps()

    assert context[112]["bar_index"] == 8
    assert context[112]["step_in_bar"] == 0
    assert context[112]["phrase_index"] == 0
    assert context[112]["phrase_start_step"] == -12
    assert context[112]["is_phrase_start"] is False

    assert context[116]["phrase_index"] == 1
    assert context[116]["phrase_start_step"] == 116


def test_ui_has_no_independent_phrase_marker_calculation():
    source = open("thelmic/static/index.html", encoding="utf-8").read()

    assert "updatePhraseTimebase" not in source
    assert "_extractTimebase" not in source
    assert "phrase_markers" not in source
    assert "sub_phrase_markers" not in source
    assert "sourceStep % (STEPS * 4)" not in source
    assert "s.phrase_context" in source
    assert "is_phrase_start" in source
    assert "is_subphrase_start" in source
