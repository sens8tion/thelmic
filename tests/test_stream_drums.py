from thelmic.bank_generator import BankGenerator, MIDIEvent
from thelmic.force_engine import ForceState
from thelmic.stream_drums import (
    HatIntentStream,
    KickIntentStream,
    render_stream_hat_events,
    render_stream_kick_events,
)
from thelmic.stream_engine import StructureProfile, StructureStream, Tick


def _template() -> MIDIEvent:
    return MIDIEvent(
        time="1.1.0",
        note=38,
        velocity=90,
        duration=0.08,
        layer="snare",
        role="anchor",
        emphasis=1.0,
        openness=1.0,
        expected_weight=1.0,
        should_resolve=False,
    )


def _frames(count=256):
    stream = StructureStream(StructureProfile(phrase_length_bars=16, subphrase_length_bars=8))
    return [stream.frame_for_tick(Tick(step, 0.0)) for step in range(count)]


def test_stream_kick_events_align_with_bar_starts_and_drop():
    events, stats = render_stream_kick_events(_frames(64), [_template()])

    assert [event.time for event in events] == ["1.1.0", "2.1.0", "3.1.0", "4.1.0"]
    assert all(event.layer == "kick" for event in events)
    assert all(event.origin_source == "stream_kick" for event in events)
    assert stats["kick_event_frames"][0] == {
        "global_step": 0,
        "musical_step": 0,
        "bar_index": 1,
        "phrase_index": 0,
        "step_in_bar": 0,
        "is_bar_start": True,
        "is_phrase_start": True,
        "is_drop": True,
        "source": "stream_kick",
        "reason": "drop_relock_kick",
    }


def test_stream_hat_uses_structure_frame_step_and_density():
    frames = _frames(180)

    early = HatIntentStream().intents_for_frame(frames[0])
    off_grid = HatIntentStream().intents_for_frame(frames[1])
    dense = HatIntentStream().intents_for_frame(frames[178])

    assert early and early[0].source == "stream_hat"
    assert early[0].payload["step_in_bar"] == 0
    assert early[0].payload["density"] == frames[0].density
    assert off_grid == ()
    assert dense and dense[0].payload["step_in_bar"] == 2


def test_bank_generator_noops_legacy_kick_and_hat_when_stream_authority_enabled():
    bank = BankGenerator().generate(
        ForceState(),
        0,
        kick_authority="stream",
        hat_authority="stream",
    )

    layers = [event.layer for event in bank.all_events()]

    assert "kick" not in layers
    assert "hat" not in layers
    assert "snare" in layers


def test_stream_hat_events_are_resolved_with_origin_metadata():
    events, stats = render_stream_hat_events(_frames(16), [_template()])

    assert events
    assert all(event.layer == "hat" for event in events)
    assert all(event.origin_source == "stream_hat" for event in events)
    assert all(event.origin_reason == "density_subdivision_hat" for event in events)
    assert stats["hat_source"] == "stream_engine"
