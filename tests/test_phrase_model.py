import pytest

from thelmic.phrase_model import (
    PhraseMode,
    PhraseRole,
    SubPhraseRole,
    TransformerSpec,
    build_phrase_model,
)


def test_phrases_start_at_drops_and_end_before_next_drop():
    model = build_phrase_model(
        drop_bars=(1, 17, 33),
        total_bars=48,
        phrase_roles=(PhraseRole.GROOVE, PhraseRole.BUILD, PhraseRole.RECOVERY),
    )

    assert [(phrase.start_bar, phrase.end_bar, phrase.length_bars) for phrase in model.phrases] == [
        (1, 16, 16),
        (17, 32, 16),
        (33, 48, 16),
    ]


def test_cursor_lookup_is_stable_and_predictable():
    model = build_phrase_model(drop_bars=(1, 17), total_bars=32, sub_phrase_bars=8)

    first = model.cursor_at_bar(1)
    boundary = model.cursor_at_bar(17)
    second_sub_phrase = model.cursor_at_bar(25)

    assert first.phrase_index == 0
    assert first.phrase_bar == 1
    assert first.sub_phrase_index == 0

    assert boundary.phrase_index == 1
    assert boundary.phrase_bar == 1
    assert boundary.sub_phrase_index == 0

    assert second_sub_phrase.phrase_index == 1
    assert second_sub_phrase.phrase_bar == 9
    assert second_sub_phrase.sub_phrase_index == 1
    assert second_sub_phrase.sub_phrase_bar == 1


def test_sub_phrases_default_to_eight_bar_boundaries():
    model = build_phrase_model(drop_bars=(1,), total_bars=24, sub_phrase_bars=8)

    assert [(sub.start_bar, sub.end_bar) for sub in model.phrases[0].sub_phrases] == [
        (1, 8),
        (9, 16),
        (17, 24),
    ]


def test_sub_phrase_lengths_support_chaos_and_nott_alignment():
    chaos = build_phrase_model(drop_bars=(1,), total_bars=16, sub_phrase_bars=4)
    nott = build_phrase_model(drop_bars=(1,), total_bars=32, sub_phrase_bars=16)

    assert [sub.length_bars for sub in chaos.phrases[0].sub_phrases] == [4, 4, 4, 4]
    assert [sub.length_bars for sub in nott.phrases[0].sub_phrases] == [16, 16]


def test_transformer_sub_phrase_is_a_mutation_zone_not_event_type():
    transformer = TransformerSpec(
        target="hook_signature",
        source_signature="hook_a",
        destination_bias="hook_a_prime",
        progress=0.5,
    )

    assert transformer.creates_events is False
    assert transformer.to_dict()["creates_events"] is False

    model = build_phrase_model(
        drop_bars=(1,),
        total_bars=24,
        phrase_modes=(PhraseMode.HOOK_MODE,),
        sub_phrase_bars=8,
    )

    middle = model.cursor_at_bar(9)
    assert middle.sub_phrase_role == SubPhraseRole.TRANSFORMATION
    assert middle.transformer is not None
    assert middle.transformer.creates_events is False


def test_phrase_mode_sets_active_constraints():
    model = build_phrase_model(
        drop_bars=(1, 17),
        total_bars=40,
        phrase_modes=(PhraseMode.HOOK_MODE, PhraseMode.CALL_RESPONSE_MODE),
        sub_phrase_bars=8,
    )

    hook_cursor = model.cursor_at_bar(1)
    call_cursor = model.cursor_at_bar(25)

    assert hook_cursor.constraints.allow_hook is True
    assert hook_cursor.constraints.allow_call is False
    assert hook_cursor.constraints.allow_response is False

    assert call_cursor.constraints.allow_hook is False
    assert call_cursor.constraints.allow_call is True
    assert call_cursor.constraints.allow_response is False


def test_pre_drop_phrase_marks_withholding_and_silence_constraints():
    model = build_phrase_model(
        drop_bars=(1,),
        total_bars=16,
        phrase_roles=(PhraseRole.PRE_DROP,),
        phrase_modes=(PhraseMode.CALL_RESPONSE_MODE,),
        sub_phrase_bars=8,
    )

    cursor = model.cursor_at_bar(16)

    assert cursor.sub_phrase_role == SubPhraseRole.WITHHOLDING
    assert cursor.constraints.silence_protected is True
    assert cursor.constraints.pre_drop_gap is True
    assert cursor.constraints.allow_call is False
    assert cursor.constraints.allow_response is False


def test_phrase_lengths_must_align_to_four_bar_boundaries():
    with pytest.raises(ValueError, match="4-bar"):
        build_phrase_model(drop_bars=(1, 11), total_bars=20)
