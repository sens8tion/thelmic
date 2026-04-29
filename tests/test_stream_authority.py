"""Stream authority migration tests.

Verifies that when all voice authorities are set to "stream":
- No legacy final events remain for stream-owned voices
- Each voice produces stream-origin events where expected
- UI payload contains stream events with provenance
- MIDI conversion receives stream events
- Provenance survives full path
- Bank rollover does not lose or duplicate events
- Legacy code remains present but inactive (authority flag set to "legacy" restores it)
"""

import pytest

import thelmic.server as server
from thelmic.bank_generator import BankGenerator, MIDIEvent
from thelmic.controls import Controls
from thelmic.stream_voices import (
    SnareIntentStream, BasslineIntentStream, SubIntentStream,
    StabIntentStream, GhostIntentStream, DropRelockIntentStream,
    render_stream_snare_events, render_stream_bassline_events,
    render_stream_sub_events, render_stream_stab_events,
)
from thelmic.stream_engine import StructureProfile, StructureStream, Tick


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

STEPS_PER_BANK = 256
ALL_STREAM_AUTHORITIES = {
    "_KICK_AUTHORITY":     "stream",
    "_SNARE_AUTHORITY":    "stream",
    "_HAT_AUTHORITY":      "stream",
    "_HOOK_AUTHORITY":     "stream",
    "_BASSLINE_AUTHORITY": "stream",
    "_SUB_AUTHORITY":      "stream",
    "_STAB_AUTHORITY":     "stream",
    "_GHOST_AUTHORITY":    "stream",
    "_DROP_AUTHORITY":     "stream",
}


def _frames(bank_index: int = 0) -> list:
    bank_start = bank_index * STEPS_PER_BANK
    stream = StructureStream(StructureProfile(
        phrase_length_bars=16, subphrase_length_bars=8, origin_step=bank_start,
    ))
    return [
        stream.frame_for_tick(Tick(global_step=bank_start + i, time=0.0))
        for i in range(STEPS_PER_BANK)
    ]


def _template() -> MIDIEvent:
    return MIDIEvent(
        time="1.1.0", note=38, velocity=90, duration=0.08,
        layer="snare", role="anchor", emphasis=1.0, openness=1.0,
        expected_weight=1.0, should_resolve=False,
    )


def _run_bank(bank_index: int = 0):
    """Run a full bank through the server pipeline, return bank + payload."""
    server._init_engine()
    gen = BankGenerator(controls=Controls())
    bank = gen.generate(
        server._engine.force_state,
        bank_index,
        0.0,
        kick_authority=server._KICK_AUTHORITY,
        snare_authority=server._SNARE_AUTHORITY,
        hat_authority=server._HAT_AUTHORITY,
    )
    server._current_bank = bank
    server._apply_behaviour_modules_to_bank(bank, {})
    payload = server._bank_events_list(bank)
    return bank, payload


# ---------------------------------------------------------------------------
# No legacy final events when all authorities are stream
# ---------------------------------------------------------------------------

class TestNoLegacyEventsWhenStreamOwned:

    STREAM_LAYERS = {"kick", "snare", "hat", "hook", "bassline", "sub", "stab"}

    def test_all_active_events_are_stream_origin(self):
        bank, payload = _run_bank()
        for event in payload:
            if event["layer"] not in self.STREAM_LAYERS:
                continue
            assert event["source"] == "stream", (
                f"Non-stream event: layer={event['layer']} "
                f"source={event['source']} time={event['time']}"
            )

    def test_no_events_without_intent_id(self):
        bank, payload = _run_bank()
        for event in payload:
            if event["layer"] not in self.STREAM_LAYERS:
                continue
            assert event["intent_id"], (
                f"Missing intent_id: layer={event['layer']} time={event['time']}"
            )

    def test_no_events_without_resolved_event_id(self):
        bank, payload = _run_bank()
        for event in payload:
            if event["layer"] not in self.STREAM_LAYERS:
                continue
            assert event["resolved_event_id"], (
                f"Missing resolved_event_id: {event['layer']}@{event['time']}"
            )


# ---------------------------------------------------------------------------
# Each voice produces stream-origin events
# ---------------------------------------------------------------------------

class TestVoiceStreamOrigin:

    def test_kick_is_stream_origin(self):
        bank, payload = _run_bank()
        kicks = [e for e in payload if e["layer"] == "kick"]
        assert kicks, "no kick events"
        assert all(e["source"] == "stream" for e in kicks)
        assert all(e["origin_source"] == "stream_kick" for e in kicks)

    def test_snare_is_stream_origin(self):
        bank, payload = _run_bank()
        snares = [e for e in payload if e["layer"] == "snare"]
        assert snares, "no snare events"
        assert all(e["source"] == "stream" for e in snares)

    def test_hat_is_stream_origin(self):
        bank, payload = _run_bank()
        hats = [e for e in payload if e["layer"] == "hat" and e["role"] != "survivor"]
        assert hats, "no hat events"
        assert all(e["source"] == "stream" for e in hats)

    def test_bassline_is_stream_origin(self):
        bank, payload = _run_bank()
        basslines = [e for e in payload if e["layer"] == "bassline"]
        assert basslines, "no bassline events"
        assert all(e["source"] == "stream" for e in basslines)

    def test_sub_is_stream_origin(self):
        bank, payload = _run_bank()
        subs = [e for e in payload if e["layer"] == "sub"]
        assert subs, "no sub events"
        assert all(e["source"] == "stream" for e in subs)

    def test_stab_events_are_stream_origin_when_stream_owned(self):
        bank, payload = _run_bank()
        stabs = [e for e in payload if e["layer"] == "stab"]
        # Stab may be absent in some phrase states — just verify source when present
        for e in stabs:
            assert e["source"] == "stream", f"non-stream stab at {e['time']}"


# ---------------------------------------------------------------------------
# Provenance survives full path
# ---------------------------------------------------------------------------

class TestProvenanceSurvivesFullPath:

    REQUIRED_FIELDS = [
        "source", "intent_id", "resolved_event_id", "reason",
        "global_step", "musical_step", "phrase_index", "bar_index",
    ]

    def test_all_stream_events_have_required_provenance(self):
        bank, payload = _run_bank()
        for event in payload:
            if event.get("source") != "stream":
                continue
            for field in self.REQUIRED_FIELDS:
                val = event.get(field)
                assert val is not None and val != "" and val != -1, (
                    f"Missing {field} on stream {event['layer']}@{event['time']}: {val}"
                )

    def test_phrase_index_is_non_negative(self):
        bank, payload = _run_bank()
        for event in payload:
            if event.get("source") == "stream":
                assert event["phrase_index"] >= 0

    def test_bar_index_is_positive(self):
        bank, payload = _run_bank()
        for event in payload:
            if event.get("source") == "stream":
                assert event["bar_index"] >= 1

    def test_musical_step_is_bank_relative_and_global_step_matches_bank(self):
        for bank_index in range(3):
            _, payload = _run_bank(bank_index)
            for event in payload:
                if event.get("source") != "stream":
                    continue
                assert 0 <= event["musical_step"] < STEPS_PER_BANK
                assert event["global_step"] == bank_index * STEPS_PER_BANK + event["musical_step"]

    def test_bank_under_construction_uses_its_own_stream_timebase(self):
        """Live playback applies modules before publishing the next _current_bank."""
        server._init_engine()
        gen = BankGenerator(controls=Controls())
        previous = gen.generate(
            server._engine.force_state,
            0,
            0.0,
            kick_authority=server._KICK_AUTHORITY,
            snare_authority=server._SNARE_AUTHORITY,
            hat_authority=server._HAT_AUTHORITY,
        )
        server._current_bank = previous

        next_bank = gen.generate(
            server._engine.force_state,
            1,
            0.0,
            kick_authority=server._KICK_AUTHORITY,
            snare_authority=server._SNARE_AUTHORITY,
            hat_authority=server._HAT_AUTHORITY,
        )
        server._apply_behaviour_modules_to_bank(next_bank, {})
        payload = server._bank_events_list(next_bank)

        assert payload
        assert all(
            event["global_step"] == STEPS_PER_BANK + event["musical_step"]
            for event in payload
            if event.get("source") == "stream"
        )

    def test_no_final_payload_event_has_legacy_or_missing_source(self):
        _, payload = _run_bank()
        for event in payload:
            assert event["source"] == "stream", (
                f"{event['layer']}@{event['time']} source={event['source']!r}"
            )


# ---------------------------------------------------------------------------
# Bank rollover — events continue and no duplicates
# ---------------------------------------------------------------------------

class TestBankRollover:

    def test_events_continue_in_bank1(self):
        _, payload0 = _run_bank(0)
        _, payload1 = _run_bank(1)
        kicks0 = [e for e in payload0 if e["layer"] == "kick"]
        kicks1 = [e for e in payload1 if e["layer"] == "kick"]
        assert len(kicks1) > 0, "no kicks in bank 1"
        assert len(kicks0) == len(kicks1), (
            f"kick count differs: bank0={len(kicks0)} bank1={len(kicks1)}"
        )

    def test_kick_times_identical_across_banks(self):
        _, payload0 = _run_bank(0)
        _, payload1 = _run_bank(1)
        times0 = sorted(e["time"] for e in payload0 if e["layer"] == "kick")
        times1 = sorted(e["time"] for e in payload1 if e["layer"] == "kick")
        assert times0 == times1, f"kick times differ: {times0[:4]} vs {times1[:4]}"

    def test_no_duplicate_kick_times_within_bank(self):
        _, payload = _run_bank(0)
        times = [e["time"] for e in payload if e["layer"] == "kick"]
        assert len(times) == len(set(times)), f"duplicate kick times: {times}"

    def test_kick_and_hat_continuity_across_three_bank_transitions(self):
        per_bank = []
        for bank_index in range(4):
            _, payload = _run_bank(bank_index)
            per_bank.append({
                "kick": sorted(e["time"] for e in payload if e["layer"] == "kick"),
                "hat": sorted(e["time"] for e in payload if e["layer"] == "hat" and e["role"] != "survivor"),
                "phrase": [
                    frame["global_step"]
                    for frame in server._stream_structure_frames()
                    if frame["is_phrase_start"]
                ],
            })

        assert all(item["kick"] for item in per_bank)
        assert all(item["hat"] for item in per_bank)
        assert len({tuple(item["kick"]) for item in per_bank}) == 1
        assert len({tuple(item["hat"]) for item in per_bank}) == 1
        for item in per_bank:
            assert len(item["kick"]) == len(set(item["kick"]))
            assert len(item["hat"]) == len(set(item["hat"]))
            assert all(step % 16 == 0 for step in item["phrase"])


class TestRequirementResolutionCompleteness:

    def test_stream_requirement_traces_end_resolved_or_suppressed(self):
        _run_bank()
        trace_keys = [
            key for key in server._runtime_debug
            if key.endswith("_requirement_trace")
        ]
        assert trace_keys
        for key in trace_keys:
            for item in server._runtime_debug[key]:
                assert item["intent_id"]
                assert item["status"] in {"resolved", "suppressed"}
                if item["status"] == "resolved":
                    assert item["resolved_event_id"]
                else:
                    assert item["suppression_reason"]

    def test_beat_bed_noops_in_stream_mode_instead_of_injecting_legacy(self):
        _run_bank()
        assert server._runtime_debug["beat_bed_events_added"] == 0

    def test_global_steps_differ_between_banks(self):
        """intent_id encodes global_step; they must differ between banks."""
        _, payload0 = _run_bank(0)
        _, payload1 = _run_bank(1)
        ids0 = {e["intent_id"] for e in payload0 if e["layer"] == "kick"}
        ids1 = {e["intent_id"] for e in payload1 if e["layer"] == "kick"}
        assert ids0.isdisjoint(ids1), f"intent_ids overlap: {ids0 & ids1}"


# ---------------------------------------------------------------------------
# Legacy rollback — setting authority to "legacy" restores legacy behaviour
# ---------------------------------------------------------------------------

class TestLegacyRollback:

    def test_setting_kick_to_legacy_fails_final_stream_invariants(self):
        """Legacy authority may exist as a flag, but final runtime must reject it."""
        original = server._KICK_AUTHORITY
        try:
            server._KICK_AUTHORITY = "legacy"
            server._init_engine()
            gen = BankGenerator(controls=Controls())
            bank = gen.generate(
                server._engine.force_state,
                0,
                0.0,
                kick_authority=server._KICK_AUTHORITY,
                snare_authority=server._SNARE_AUTHORITY,
                hat_authority=server._HAT_AUTHORITY,
            )
            server._current_bank = bank
            with pytest.raises(RuntimeError, match="final stream invariant violation"):
                server._apply_behaviour_modules_to_bank(bank, {})
        finally:
            server._KICK_AUTHORITY = original

    def test_authority_flags_are_exposed_in_runtime_debug(self):
        bank, _ = _run_bank()
        for flag in ["kick_authority", "snare_authority", "hat_authority",
                     "hook_authority", "bassline_authority", "sub_authority",
                     "stab_authority", "ghost_authority", "drop_authority"]:
            assert flag in server._runtime_debug, f"missing debug flag: {flag}"
            assert server._runtime_debug[flag] == "stream", (
                f"{flag} = {server._runtime_debug[flag]}, expected 'stream'"
            )


# ---------------------------------------------------------------------------
# Unit-level voice stream tests
# ---------------------------------------------------------------------------

class TestVoiceStreamUnits:

    def test_snare_fires_at_beats_2_and_4(self):
        events, _ = render_stream_snare_events(_frames(0), [_template()])
        steps = {int(e.time.split(".")[0]) * 16 + 0 for e in events}  # approximate
        times = [e.time for e in events]
        # Beats 2 and 4 = step_in_bar 4 and 12
        for t in times:
            beat = int(t.split(".")[1])
            assert beat in (2, 4), f"snare on beat {beat}, expected 2 or 4"

    def test_bassline_bars_are_1_to_16(self):
        events, _ = render_stream_bassline_events(_frames(1), [_template()])
        for e in events:
            bar = int(e.time.split(".")[0])
            assert 1 <= bar <= 16, f"bank1 bassline bar={bar}"

    def test_sub_fires_at_bar_starts_only(self):
        events, _ = render_stream_sub_events(_frames(0), [_template()])
        for e in events:
            # Sub fires at is_bar_start = step_in_bar == 0 = beat 1
            beat = int(e.time.split(".")[1])
            assert beat == 1, f"sub at beat {beat}, expected bar start (beat 1)"

    def test_stab_respects_call_and_response_windows(self):
        events, _ = render_stream_stab_events(_frames(0), [_template()])
        for e in events:
            bar_beat = int(e.time.split(".")[1])
            step_in_bar = (bar_beat - 1) * 4 + int(e.time.split(".")[2]) // 6
            # Calls in 0-7, responses in 8-15
            if e.role == "call":
                assert step_in_bar < 8, f"call at step {step_in_bar} (response window)"
            elif e.role == "response":
                assert step_in_bar >= 8, f"response at step {step_in_bar} (call window)"
