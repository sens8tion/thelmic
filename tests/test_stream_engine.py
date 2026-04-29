from thelmic.stream_engine import (
    ControlFrame,
    EventStream,
    Intent,
    IntentStream,
    PhraseRole,
    ResolveStream,
    StructureProfile,
    StructureStream,
    SubphraseRole,
    Tick,
    TransportClock,
    enrich_with_control,
)


def test_transport_clock_emits_canonical_step_ticks():
    clock = TransportClock(bpm=120.0)

    ticks = list(clock.ticks(start_step=8, count=3))

    assert [tick.global_step for tick in ticks] == [8, 9, 10]
    assert ticks[1].time - ticks[0].time == clock.seconds_per_step


def test_structure_stream_is_single_source_for_bar_phrase_and_subphrase():
    profile = StructureProfile(
        phrase_length_bars=16,
        subphrase_length_bars=8,
        phrase_roles=(PhraseRole.GROOVE, PhraseRole.BUILD),
        subphrase_roles=(SubphraseRole.SETUP, SubphraseRole.RELEASE),
    )
    stream = StructureStream(profile)

    frame = stream.frame_for_tick(Tick(global_step=16 * 16, time=0.0))

    assert frame.global_step == 256
    assert frame.musical_step == 256
    assert frame.bar_index == 17
    assert frame.step_in_bar == 0
    assert frame.phrase_index == 1
    assert frame.step_in_phrase == 0
    assert frame.subphrase_index == 0
    assert frame.step_in_subphrase == 0
    assert frame.phrase_role == PhraseRole.BUILD
    assert frame.subphrase_role == SubphraseRole.SETUP
    assert frame.is_bar_start is True
    assert frame.is_phrase_start is True
    assert frame.is_subphrase_start is True
    assert frame.is_drop is True
    assert frame.is_relock is True


def test_structure_stream_accounts_for_relock_offset_in_musical_time():
    stream = StructureStream(
        StructureProfile(
            phrase_length_bars=16,
            subphrase_length_bars=8,
            relock_offset_steps=4,
        )
    )

    frame = stream.frame_for_tick(Tick(global_step=4, time=0.0))

    assert frame.global_step == 4
    assert frame.musical_step == 0
    assert frame.bar_index == 1
    assert frame.step_in_bar == 0
    assert frame.is_bar_start is True
    assert frame.is_phrase_start is True
    assert frame.is_drop is True
    assert frame.is_relock is True


def test_structure_stream_supports_visible_window_origin():
    stream = StructureStream(
        StructureProfile(
            phrase_length_bars=16,
            subphrase_length_bars=8,
            origin_step=512,
        )
    )

    frame = stream.frame_for_tick(Tick(global_step=512, time=0.0))

    assert frame.global_step == 512
    assert frame.musical_step == 0
    assert frame.bar_index == 1
    assert frame.is_bar_start is True
    assert frame.is_phrase_start is True


def test_phrase_and_subphrase_boundaries_are_deterministic():
    stream = StructureStream(StructureProfile(phrase_length_bars=16, subphrase_length_bars=4))

    frames = list(stream.frames(Tick(step, 0.0) for step in range(0, 16 * 20)))
    phrase_starts = [frame.global_step for frame in frames if frame.is_phrase_start]
    subphrase_starts = [frame.global_step for frame in frames if frame.is_subphrase_start]

    assert phrase_starts == [0, 256]
    assert subphrase_starts == [0, 64, 128, 192, 256]


def test_control_stream_enrichment_cannot_override_time_fields():
    frame = StructureStream().frame_for_tick(Tick(global_step=32, time=1.0))

    enriched = enrich_with_control(frame, ControlFrame(landscape_position=1.0))

    assert enriched.global_step == frame.global_step
    assert enriched.musical_step == frame.musical_step
    assert enriched.bar_index == frame.bar_index
    assert enriched.phrase_index == frame.phrase_index
    assert enriched.subphrase_index == frame.subphrase_index
    assert enriched.density >= frame.density


class _HookIntentStream(IntentStream):
    source = "test_hook"

    def intents_for_frame(self, frame):
        if not frame.is_phrase_start:
            return ()
        return (
            Intent(
                step=frame.global_step,
                instrument="hook",
                role="hook",
                velocity=90,
                duration=0.1,
                phrase_index=frame.phrase_index,
                subphrase_index=frame.subphrase_index,
                priority=4,
                source=self.source,
                reason="phrase_start",
            ),
        )


def test_intent_stream_consumes_structure_frame_without_final_midi():
    frame = StructureStream().frame_for_tick(Tick(global_step=0, time=0.0))

    intents = _HookIntentStream().intents_for_frame(frame)

    assert len(intents) == 1
    assert intents[0].step == frame.global_step
    assert intents[0].phrase_index == frame.phrase_index
    assert intents[0].source == "test_hook"
    assert not hasattr(intents[0], "midi_channel")


def test_resolve_stream_is_central_suppression_authority():
    frame = StructureStream().frame_for_tick(Tick(global_step=255, time=0.0))
    intent = Intent(
        step=frame.global_step,
        instrument="hook",
        role="hook",
        velocity=80,
        priority=4,
        source="test",
        reason="near_drop",
    )

    result = ResolveStream().resolve(frame, (intent,))

    assert frame.silence == 1.0
    assert result.events == ()
    assert len(result.suppressions) == 1
    assert result.suppressions[0].reason == "silence"


def test_event_stream_outputs_only_resolved_events_with_traceable_origin():
    stream = EventStream((_HookIntentStream(),))
    frame = StructureStream().frame_for_tick(Tick(global_step=0, time=0.0))

    events = list(stream.events((frame,)))

    assert len(events) == 1
    assert events[0].step == frame.global_step
    assert events[0].instrument == "hook"
    assert events[0].origin_intent.source == "test_hook"
    assert events[0].resolution_reason == "resolved"


def test_structure_frame_dict_is_render_stream_ready():
    frame = StructureStream().frame_for_tick(Tick(global_step=0, time=0.0))

    data = frame.to_dict()

    assert data["global_step"] == 0
    assert data["musical_step"] == 0
    assert data["bar_index"] == 1
    assert data["phrase_index"] == 0
    assert data["subphrase_index"] == 0
    assert data["is_phrase_start"] is True
    assert data["is_subphrase_start"] is True
