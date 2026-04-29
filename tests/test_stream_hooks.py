from thelmic.bank_generator import MIDIEvent
from thelmic.phrase_plan import PhrasePlan, PlanNote, SilenceMask
from thelmic.stream_engine import ResolveStream, StructureProfile, StructureStream, Tick
from thelmic.stream_hooks import HookIntentStream, render_stream_hook_events


def _template() -> MIDIEvent:
    return MIDIEvent(
        time="1.1.0",
        note=36,
        velocity=90,
        duration=0.08,
        layer="kick",
        role="anchor",
        emphasis=1.0,
        openness=1.0,
        expected_weight=1.0,
        should_resolve=False,
    )


def _plan() -> PhrasePlan:
    return PhrasePlan(
        bass_pattern=(),
        hook_pattern=(
            PlanNote(bar=1, step=0, pitch=60, velocity=90, duration_steps=1),
            PlanNote(bar=1, step=6, pitch=63, velocity=86, duration_steps=1),
        ),
        phrase_state={},
        call_slots={},
        response_slots={},
        silence_mask=SilenceMask(),
        pressure_curve={},
    )


def _frames(count=256):
    stream = StructureStream(StructureProfile(phrase_length_bars=16, subphrase_length_bars=8))
    return [stream.frame_for_tick(Tick(step, 0.0)) for step in range(count)]


def test_hook_intents_are_structure_frame_candidates():
    frame = _frames(1)[0]

    intents = HookIntentStream(_plan()).intents_for_frame(frame)

    assert len(intents) == 1
    assert intents[0].step == frame.global_step
    assert intents[0].instrument == "hook"
    assert intents[0].source == "stream_hook"
    assert intents[0].reason == "phrase_start_hook"
    assert intents[0].payload["pitch"] == 60


def test_resolved_stream_hooks_align_to_phrase_start_and_authorised_recap():
    events, stats = render_stream_hook_events(_frames(), _plan(), [_template()])

    assert [(event.time, event.note) for event in events] == [
        ("1.1.0", 60),
        ("1.2.12", 63),
        ("9.1.0", 60),
        ("9.2.12", 63),
    ]
    assert all(event.origin_source == "stream_hook" for event in events)
    assert all(event.origin_reason for event in events)
    assert all(event.resolution_reason == "resolved" for event in events)
    assert stats["hook_source"] == "stream_engine"
    assert stats["hook_events_resolved"] == 4


def test_hook_candidates_outside_structure_windows_are_suppressed():
    events, stats = render_stream_hook_events(_frames(), _plan(), [_template()])

    assert events
    assert stats["hook_intents_attempted"] > stats["hook_events_resolved"]
    assert stats["hook_intents_suppressed"] > 0
    assert stats["hook_suppressions"]["hook_not_permitted_by_structure"] > 0


def test_resolve_stream_logs_suppressed_hook_attempt_reason():
    frame = _frames()[16]
    intent = HookIntentStream(_plan()).intents_for_frame(frame)[0]

    result = ResolveStream().resolve(frame, (intent,))

    assert result.events == ()
    assert len(result.suppressions) == 1
    assert result.suppressions[0].reason == "hook_not_permitted_by_structure"
