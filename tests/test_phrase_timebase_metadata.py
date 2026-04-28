from thelmic.server import _phrase_metadata_list


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
