from thelmic.bank_generator import MIDIEvent
from thelmic.stream_engine import (
    Intent,
    ResolveStream,
    StructureStream,
    Tick,
)
from thelmic.stream_voices import (
    SurvivorIntentStream,
    render_stream_survivor_events,
)


def _template() -> MIDIEvent:
    return MIDIEvent(
        time="1.1.0",
        note=42,
        velocity=70,
        duration=0.03,
        layer="hat",
        role="anchor",
        emphasis=0.4,
        openness=1.0,
        expected_weight=0.5,
        should_resolve=False,
    )


def test_structure_frame_exposes_density_and_silence_as_separate_intents():
    frame = StructureStream().frame_for_tick(Tick(global_step=255, time=0.0))

    assert frame.silence == 1.0
    assert frame.silence_intent == frame.silence
    assert frame.density_intent == frame.density
    assert frame.density > 0.75

    data = frame.to_dict()
    assert data["density_intent"] == data["density"]
    assert data["silence_intent"] == data["silence"]


def test_survivor_intent_survives_resolve_stream_silence():
    frame = StructureStream().frame_for_tick(Tick(global_step=255, time=0.0))
    normal = Intent(
        step=frame.global_step,
        instrument="hat",
        role="anchor",
        velocity=70,
        duration=0.03,
        phrase_index=frame.phrase_index,
        subphrase_index=frame.subphrase_index,
        priority=2,
        source="test_hat",
        reason="normal_hat",
    )
    survivor = SurvivorIntentStream().intents_for_frame(frame)

    assert survivor
    result = ResolveStream().resolve(frame, (normal, *survivor))

    assert [event.origin_intent.role for event in result.events] == ["survivor"]
    assert [suppression.reason for suppression in result.suppressions] == ["silence"]
    assert survivor[0].payload["survives_silence"] is True
    assert survivor[0].payload["structural_authority"] is False


def test_survivor_render_emits_stream_hat_events_with_metadata():
    frames = [
        StructureStream().frame_for_tick(Tick(global_step=step, time=0.0))
        for step in range(224, 256)
    ]

    events, stats = render_stream_survivor_events(frames, [_template()])

    assert events
    assert stats["survivor_events_resolved"] == len(events)
    assert all(event.layer == "hat" for event in events)
    assert all(event.role == "survivor" for event in events)
    assert all(event.source == "stream" for event in events)
    assert all(event.origin_source == "stream_survivor" for event in events)
    assert all(event.survives_silence for event in events)
    assert max(event.velocity for event in events) <= 24
