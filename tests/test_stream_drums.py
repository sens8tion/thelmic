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
    # KickIntentStream now emits territory-aware patterns.
    # At default landscape_position=0 (Oak, low density), kicks fire on
    # beats 1+3 per bar (steps 0 and 8), with beat 1 at bar start.
    events, stats = render_stream_kick_events(_frames(64), [_template()])

    # All events must be kick layer with stream provenance
    assert events, "no kick events generated"
    assert all(event.layer == "kick" for event in events)
    assert all(event.origin_source == "stream_kick" for event in events)
    assert all(event.source == "stream" for event in events)

    # All events must have bar numbers 1–4 (bank-relative)
    bars = [int(e.time.split(".")[0]) for e in events]
    assert all(1 <= b <= 4 for b in bars), f"out-of-range bars: {bars}"

    # Every bar-1 beat-1 must be present (beat 1 = step 0 = "1.1.0")
    times = [e.time for e in events]
    assert "1.1.0" in times, "beat 1 of bar 1 missing"

    # Drop event (step 0 of bank, is_drop=True) must use drop reason
    first = stats["kick_event_frames"][0]
    assert first["reason"] == "drop_relock_kick"
    assert first["intent_id"].startswith("stream_kick:0:")
    assert first["resolved_event_id"].startswith("resolved:")
    assert first["global_step"] == 0
    assert first["musical_step"] == 0
    assert all(event.source == "stream" for event in events)
    assert all(event.intent_id for event in events)
    assert all(event.resolved_event_id for event in events)
    assert all(event.phrase_index >= 0 for event in events)
    assert all(event.bar_index >= 1 for event in events)
    assert all(event.reason for event in events)


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
        snare_authority="stream",
        hat_authority="stream",
    )

    layers = [event.layer for event in bank.all_events()]

    assert "kick" not in layers
    assert "snare" not in layers
    assert "hat" not in layers


def test_stream_hat_events_are_resolved_with_origin_metadata():
    events, stats = render_stream_hat_events(_frames(16), [_template()])

    assert events
    assert all(event.layer == "hat" for event in events)
    assert all(event.origin_source == "stream_hat" for event in events)
    assert all(event.origin_reason == "density_subdivision_hat" for event in events)
    assert all(event.source == "stream" for event in events)
    assert all(event.intent_id.startswith("stream_hat:") for event in events)
    assert all(event.resolved_event_id.startswith("resolved:stream_hat:") for event in events)
    assert all(event.phrase_index >= 0 for event in events)
    assert all(event.bar_index >= 1 for event in events)
    assert all(event.reason == "density_subdivision_hat" for event in events)
    assert stats["hat_source"] == "stream_engine"
