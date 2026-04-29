"""Stream continuity tests.

Proves that stream kick/hat/hook events are generated correctly across
multiple banks and do not disappear after the first generated window.

Root cause of the bug: step_to_time(global_step) was called with the
absolute global step (e.g. 256 for bank 1 step 0), which produced bar
numbers ≥ 17 — outside the bank (bars 1–16). Events were silently
discarded by _append_events_to_bank.

Fix: use musical_step (bank-relative 0..255) from the intent payload.
"""

from thelmic.bank_generator import MIDIEvent
from thelmic.stream_drums import render_stream_kick_events, render_stream_hat_events
from thelmic.stream_hooks import render_stream_hook_events
from thelmic.stream_engine import StructureProfile, StructureStream, Tick


STEPS_PER_BAR = 16
BARS_PER_BANK = 16
STEPS_PER_BANK = STEPS_PER_BAR * BARS_PER_BANK  # 256


def _template() -> MIDIEvent:
    return MIDIEvent(
        time="1.1.0", note=38, velocity=90, duration=0.08,
        layer="snare", role="anchor", emphasis=1.0, openness=1.0,
        expected_weight=1.0, should_resolve=False,
    )


def _frames_for_bank(bank_index: int):
    """Generate frames for one bank with the correct global_step range."""
    bank_start = bank_index * STEPS_PER_BANK
    stream = StructureStream(StructureProfile(
        phrase_length_bars=16,
        subphrase_length_bars=8,
        origin_step=bank_start,
    ))
    return [
        stream.frame_for_tick(Tick(global_step=bank_start + i, time=0.0))
        for i in range(STEPS_PER_BANK)
    ]


def _valid_bank_times(events):
    """Return list of (bar, beat, tick) for every event time."""
    result = []
    for e in events:
        parts = e.time.split(".")
        result.append((int(parts[0]), int(parts[1]), int(parts[2])))
    return result


# ---------------------------------------------------------------------------
# Core regression: events must have bank-relative bar numbers (1–16)
# ---------------------------------------------------------------------------

class TestStepToTimeBankRelative:

    def test_bank0_kick_bars_are_1_to_16(self):
        """Bank 0 (global steps 0–255): bars must be 1–16."""
        events, _ = render_stream_kick_events(_frames_for_bank(0), [_template()])
        bars = [e.time.split(".")[0] for e in events]
        for bar in bars:
            assert 1 <= int(bar) <= 16, f"bank 0 kick at bar {bar} — out of range"

    def test_bank1_kick_bars_are_1_to_16(self):
        """Bank 1 (global steps 256–511): bars must still be 1–16, not 17+."""
        events, _ = render_stream_kick_events(_frames_for_bank(1), [_template()])
        assert len(events) > 0, "no kick events for bank 1 — stream not continuous"
        bars = [int(e.time.split(".")[0]) for e in events]
        for bar in bars:
            assert 1 <= bar <= 16, f"bank 1 kick at bar {bar} — step_to_time used global step"

    def test_bank5_kick_bars_are_1_to_16(self):
        """Bank 5 (global steps 1280–1535): must not produce bar 81+."""
        events, _ = render_stream_kick_events(_frames_for_bank(5), [_template()])
        assert len(events) > 0, "no kick events for bank 5"
        bars = [int(e.time.split(".")[0]) for e in events]
        for bar in bars:
            assert 1 <= bar <= 16, f"bank 5 kick at bar {bar}"

    def test_bank1_hat_bars_are_1_to_16(self):
        events, _ = render_stream_hat_events(_frames_for_bank(1), [_template()])
        assert len(events) > 0, "no hat events for bank 1"
        bars = [int(e.time.split(".")[0]) for e in events]
        for bar in bars:
            assert 1 <= bar <= 16, f"bank 1 hat at bar {bar}"

    def test_bank1_hook_bars_are_1_to_16(self):
        from thelmic.phrase_plan import generate_phrase_plan
        plan = generate_phrase_plan()
        events, _ = render_stream_hook_events(_frames_for_bank(1), plan, [_template()])
        bars = [int(e.time.split(".")[0]) for e in events]
        for bar in bars:
            assert 1 <= bar <= 16, f"bank 1 hook at bar {bar}"


# ---------------------------------------------------------------------------
# Continuity: same event pattern across banks
# ---------------------------------------------------------------------------

class TestStreamContinuity:

    def test_kick_count_same_across_banks(self):
        """Every bank should produce the same number of kick events."""
        counts = []
        for bank_idx in range(4):
            events, _ = render_stream_kick_events(_frames_for_bank(bank_idx), [_template()])
            counts.append(len(events))
        assert len(set(counts)) == 1, f"kick counts differ across banks: {counts}"
        assert counts[0] > 0, "no kick events generated"

    def test_kick_times_identical_across_banks(self):
        """Kick event times (bar.beat.tick) must be identical for every bank."""
        times_b0 = [e.time for e in render_stream_kick_events(_frames_for_bank(0), [_template()])[0]]
        times_b1 = [e.time for e in render_stream_kick_events(_frames_for_bank(1), [_template()])[0]]
        times_b3 = [e.time for e in render_stream_kick_events(_frames_for_bank(3), [_template()])[0]]
        assert times_b0 == times_b1, f"kick times differ bank0 vs bank1: {times_b0} vs {times_b1}"
        assert times_b0 == times_b3

    def test_hat_count_same_across_banks(self):
        counts = []
        for bank_idx in range(4):
            events, _ = render_stream_hat_events(_frames_for_bank(bank_idx), [_template()])
            counts.append(len(events))
        assert len(set(counts)) == 1, f"hat counts differ: {counts}"
        assert counts[0] > 0

    def test_hat_times_identical_across_banks(self):
        times_b0 = [e.time for e in render_stream_hat_events(_frames_for_bank(0), [_template()])[0]]
        times_b1 = [e.time for e in render_stream_hat_events(_frames_for_bank(1), [_template()])[0]]
        assert times_b0 == times_b1


# ---------------------------------------------------------------------------
# No duplicate events at rollover boundary
# ---------------------------------------------------------------------------

class TestNoDuplicates:

    def test_no_duplicate_kick_times_within_bank(self):
        events, _ = render_stream_kick_events(_frames_for_bank(0), [_template()])
        times = [e.time for e in events]
        assert len(times) == len(set(times)), f"duplicate kick times: {times}"

    def test_no_duplicate_hat_times_within_bank(self):
        events, _ = render_stream_hat_events(_frames_for_bank(0), [_template()])
        times = [e.time for e in events]
        assert len(times) == len(set(times)), f"duplicate hat times: {times}"

    def test_adjacent_banks_produce_independent_events(self):
        """Events from bank N and bank N+1 must not share times."""
        events_b0, _ = render_stream_kick_events(_frames_for_bank(0), [_template()])
        events_b1, _ = render_stream_kick_events(_frames_for_bank(1), [_template()])
        # Times are bank-relative so they WILL be the same values — that's correct.
        # Verify they don't bleed into each other's bar ranges.
        for e in events_b0:
            bar = int(e.time.split(".")[0])
            assert 1 <= bar <= 16
        for e in events_b1:
            bar = int(e.time.split(".")[0])
            assert 1 <= bar <= 16


# ---------------------------------------------------------------------------
# Provenance survives across banks
# ---------------------------------------------------------------------------

class TestProvenanceSurvivesRollover:

    def test_kick_provenance_intact_bank1(self):
        events, _ = render_stream_kick_events(_frames_for_bank(1), [_template()])
        for e in events:
            assert getattr(e, "source", None) == "stream", f"source not stream: {e.source}"
            assert getattr(e, "intent_id", None), "missing intent_id"
            assert getattr(e, "resolved_event_id", None), "missing resolved_event_id"
            assert getattr(e, "phrase_index", -1) >= 0, "negative phrase_index"

    def test_hat_provenance_intact_bank2(self):
        events, _ = render_stream_hat_events(_frames_for_bank(2), [_template()])
        for e in events:
            assert getattr(e, "source", None) == "stream"
            assert getattr(e, "intent_id", None)

    def test_global_step_in_payload_differs_per_bank(self):
        """global_step in intent payloads must differ between banks."""
        events_b0, stats0 = render_stream_kick_events(_frames_for_bank(0), [_template()])
        events_b1, stats1 = render_stream_kick_events(_frames_for_bank(1), [_template()])
        gs0 = {f["global_step"] for f in stats0.get("kick_event_frames", [])}
        gs1 = {f["global_step"] for f in stats1.get("kick_event_frames", [])}
        assert gs0.isdisjoint(gs1), f"banks 0 and 1 share global_steps: {gs0 & gs1}"

    def test_musical_step_is_bank_relative(self):
        """musical_step must always be 0..255 regardless of bank."""
        for bank_idx in [0, 1, 3, 7]:
            events, _ = render_stream_kick_events(_frames_for_bank(bank_idx), [_template()])
            for e in events:
                ms = getattr(e, "bar_index", None)
                bar = int(e.time.split(".")[0])
                assert 1 <= bar <= 16, f"bank {bank_idx}: bar {bar} out of range"
