from thelmic.server import _phrase_context_steps, _phrase_metadata_list


def test_phrase_metadata_exposes_canonical_timebase_markers():
    metadata = _phrase_metadata_list()
    timebase = metadata[-1]

    assert timebase["type"] == "timebase"
    assert timebase["steps_per_bar"] == 16
    assert [m["musical_step"] for m in timebase["phrase_markers"]] == [0, 64, 128, 192]


def test_phrase_entries_use_same_start_steps_as_timebase():
    metadata = _phrase_metadata_list()
    phrase_entries = [m for m in metadata if m.get("type") != "timebase"]
    timebase = metadata[-1]

    assert [m["start_step"] for m in phrase_entries] == [
        marker["musical_step"]
        for marker in timebase["phrase_markers"]
    ]
    assert all(m["start_step"] == m["phrase_start_step"] for m in phrase_entries)


def test_phrase_context_steps_are_resolved_per_musical_step():
    context = _phrase_context_steps()

    assert len(context) == 256
    assert context[0]["musical_step"] == 0
    assert context[0]["bar_index"] == 1
    assert context[0]["phrase_index"] == 0
    assert context[0]["sub_phrase_index"] == 0
    assert context[0]["is_phrase_start"] is True
    assert context[0]["is_sub_phrase_start"] is True

    assert context[64]["musical_step"] == 64
    assert context[64]["bar_index"] == 5
    assert context[64]["phrase_index"] == 1
    assert context[64]["is_phrase_start"] is True

    assert context[65]["is_phrase_start"] is False
    assert context[65]["is_sub_phrase_start"] is False
