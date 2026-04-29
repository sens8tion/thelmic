from thelmic import server
from thelmic.archetypes import select_archetype
from thelmic.server import _phrase_context_steps, _phrase_metadata_list
from thelmic.syntax_enforcer import time_to_bar_step


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
    assert "s.structure_frames" in source
    assert "s.phrase_context" not in source
    assert "is_phrase_start" in source
    assert "is_subphrase_start" in source


def test_drop_relock_events_align_with_phrase_starts():
    server._init_engine()
    server._pending_archetype_name = select_archetype(
        server._engine.force_state.density,
        server._generator.selected_archetype,
    ).name
    server._active_archetype_name = server._pending_archetype_name
    bank = server._generator.generate(
        server._engine.force_state,
        0,
        server._engine.landscape_position,
        active_archetype=server._active_archetype_name,
        kick_authority="stream",
        hat_authority="stream",
    )
    server._current_bank = bank
    server._apply_behaviour_modules_to_bank(bank, {})

    phrase_starts = {
        ctx["musical_step"]
        for ctx in server._phrase_context_steps()
        if ctx["is_phrase_start"]
    }
    drop_steps = set()
    for event in bank.all_events():
        if not event.deformation.get("drop_relock"):
            continue
        bar, step = time_to_bar_step(event.time)
        drop_steps.add((bar - 1) * 16 + step)

    assert drop_steps
    assert drop_steps <= phrase_starts


def test_phrase_metadata_does_not_label_survivor_as_phrase_rule():
    original = dict(server._runtime_debug)
    try:
        server._runtime_debug["survivor_events_final"] = 99
        metadata = server._phrase_metadata_list()
    finally:
        server._runtime_debug = original

    assert metadata
    assert all("survivor" not in meta["rules"] for meta in metadata)


def test_ui_hides_survivor_signal_as_non_midi_diagnostic_strip():
    source = open("thelmic/static/index.html", encoding="utf-8").read()

    assert "HIDDEN_DEFORMATION_STRIPS" in source
    assert "survivor_signal" in source
