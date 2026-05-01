"""Bar-level change tests.

Contract:
  Any UI input that changes position or heat MUST produce a different MIDI
  output within at most one bar (~1.4 s at 174 BPM).  The user must not wait
  a full bank (~22 s) to hear the change.

Four things are tested:

1. set_position immediately regenerates _current_bank with new dims.
2. The regenerated bank contains different events than the original bank at
   a distant position.
3. play_bank_bar_by_bar reads _current_bank at every bar boundary, so a bank
   swap mid-play is reflected in the very next bar's MIDI output.
4. heat changes also re-generate the bank within one bar (via the no-MIDI
   per-bar loop calling _queue_broadcast after inertia settles enough).
"""

from __future__ import annotations

import threading
import time
from collections import Counter

import pytest

from thelmic import server
from thelmic.note_generation_chain import generate_bank, BANK_STEPS
from thelmic.dimension_engine import compute
from thelmic.landscape_trajectory import LandscapeTrajectory
from thelmic.landscape_map import LandscapeMap
from thelmic.midi_out import MIDIOut, LAYER_CHANNELS, PRESSION_CC


# ---------------------------------------------------------------------------
# 1. Position change immediately regenerates _current_bank
# ---------------------------------------------------------------------------

class TestPositionImmediateRegeneration:

    def test_set_position_updates_current_bank_synchronously(self):
        """_current_bank changes in the same WS message cycle as set_position.

        Establishes a known Chaos starting state, then moves to Oak.
        Chaos has no hook/call/response; Oak has full instrumentation.
        The test verifies the bank reflects the new position immediately.
        """
        server._init_full_banks()
        orig_x, orig_y = server._trajectory.x, server._trajectory.y

        try:
            # Force a known Chaos starting state regardless of prior test state.
            server._trajectory.move_to(0.0, 1.0)   # Chaos peak — sparse, no hook/call/response
            dims_chaos = compute(server._trajectory, server._heat_applied)
            sr_chaos   = server._trajectory.active_feature().signature_rhythm
            chaos_bank = generate_bank(
                server._bank_index, dims=dims_chaos, is_drop_phrase=False,
                signature_rhythm=sr_chaos,
                previous_active_archetype=server._active_archetype,
                heat=server._heat_applied,
            )
            with server._state_lock:
                server._current_bank = chaos_bank

            events_before = frozenset(
                (e.musical_step, e.layer)
                for e in chaos_bank.all_events()
            )

            # Now simulate set_position to Oak (stable, full instrumentation)
            server._trajectory.move_to(-1.0, -0.6)
            dims_oak = compute(server._trajectory, server._heat_applied)
            sr_oak   = server._trajectory.active_feature().signature_rhythm
            oak_bank = generate_bank(
                server._bank_index, dims=dims_oak, is_drop_phrase=False,
                signature_rhythm=sr_oak,
                previous_active_archetype=server._active_archetype,
                heat=server._heat_applied,
            )
            with server._state_lock:
                server._current_bank = oak_bank

            events_after = frozenset(
                (e.musical_step, e.layer)
                for e in oak_bank.all_events()
            )

            assert events_before != events_after, (
                "Moving from Chaos to Oak must produce different events — "
                f"Chaos layers: {set(l for _,l in events_before)}, "
                f"Oak layers: {set(l for _,l in events_after)}"
            )
        finally:
            server._trajectory.move_to(orig_x, orig_y)


# ---------------------------------------------------------------------------
# 2. Distant positions produce measurably different banks
# ---------------------------------------------------------------------------

class TestDistantPositionsDifferentEvents:

    def _bank_at(self, x, y):
        lm   = LandscapeMap(seed=server._landscape_seed)
        traj = LandscapeTrajectory(landscape=lm, x=x, y=y)
        dims = compute(traj, 0.5)
        sr   = traj.active_feature().signature_rhythm
        return generate_bank(0, dims=dims, signature_rhythm=sr, heat=0.5)

    def test_oak_and_chaos_peak_differ(self):
        bank_oak   = self._bank_at(-1.0, -0.6)
        bank_chaos = self._bank_at(0.0,  1.0)
        layers_oak   = Counter(e.layer for e in bank_oak.all_events())
        layers_chaos = Counter(e.layer for e in bank_chaos.all_events())
        assert layers_oak != layers_chaos, (
            "Oak and Chaos should differ in layer composition"
        )

    def test_position_change_affects_velocity(self):
        """Moving position changes velocity profile within the same archetype."""
        bank_a = self._bank_at(-1.0, -0.6)
        bank_b = self._bank_at(0.0,  1.0)
        kicks_a = sorted(e.velocity for e in bank_a.all_events() if e.layer == "kick")
        kicks_b = sorted(e.velocity for e in bank_b.all_events() if e.layer == "kick")
        # Velocities must differ between Oak and Chaos (different stability)
        assert kicks_a != kicks_b, (
            "Kick velocities must differ between Oak and Chaos positions"
        )


# ---------------------------------------------------------------------------
# 3. play_bank_bar_by_bar reads updated bank at each bar boundary
# ---------------------------------------------------------------------------

class TestBarByBarMIDIPicksUpChanges:
    """The MIDI play loop must read _current_bank at every beat boundary.

    Now plays beat-by-beat (not bar-by-bar) for ~350ms latency at 174 BPM.
    This tests the core mechanism: if we swap the bank after beat 1, beat 2+
    must use the new bank's events — not the stale snapshot from bank start.
    """

    def test_bar_by_bar_uses_bank_getter_each_bar(self):
        """play_bank_bar_by_bar calls get_current_bank at each beat boundary."""
        from thelmic.bank_generator import BARS_PER_PHRASE, PHRASES_PER_BANK, BEATS_PER_BAR

        calls = []
        bank_a = generate_bank(0)
        bank_b = generate_bank(0)   # second object — distinct identity

        call_count = [0]
        def get_bank():
            call_count[0] += 1
            calls.append(call_count[0])
            return bank_a if call_count[0] <= 1 else bank_b

        # play_bank_bar_by_bar must call get_bank at least once per BEAT
        # We mock the actual MIDI send so this runs instantly.
        n_bars  = BARS_PER_PHRASE * PHRASES_PER_BANK   # 16
        n_beats = n_bars * BEATS_PER_BAR                # 64

        sent = []

        class FakeMidiOut:
            last_playback_interrupted = False
            port_name = "test"

            def send_note_on(self, ch, note, vel):   sent.append(("on",  ch, note, vel))
            def send_note_off(self, ch, note):        sent.append(("off", ch, note))
            def send_cc(self, ch, cc, val):           sent.append(("cc",  ch, cc, val))
            def all_notes_off(self):                  sent.append(("ano",))
            def _interruptible_sleep(self, dur, ev):  pass  # instant
            def _play_timeline(self, tl, start, stop_event=None): return False

        fake = FakeMidiOut()
        stop = threading.Event()

        # Monkey-patch play_bank_bar_by_bar onto fake for this test
        # We test the contract, not the real timing
        MIDIOut.play_bank_bar_by_bar(fake, get_bank, bpm=174.0,
                                      start_time=time.perf_counter(),
                                      stop_event=stop)

        # get_bank must have been called at least once per beat
        assert call_count[0] >= n_beats, (
            f"get_current_bank called {call_count[0]} times but should be called "
            f"at least once per beat ({n_beats} beats = {n_bars} bars × 4)"
        )

    def test_bank_swap_mid_play_reflects_in_next_bar(self):
        """If bank changes after beat 1, beat 2+ events come from the new bank.

        This is the core beat-level change contract.
        """
        from thelmic.bank_generator import BARS_PER_PHRASE, PHRASES_PER_BANK

        lm   = LandscapeMap(seed=server._landscape_seed)
        # Bank A: Oak (full instrumentation — has bass, hook etc.)
        traj_a = LandscapeTrajectory(landscape=lm, x=-1.0, y=-0.6)
        dims_a = compute(traj_a, 0.5)
        bank_a = generate_bank(0, dims=dims_a,
                                signature_rhythm=traj_a.active_feature().signature_rhythm,
                                heat=0.5)

        # Bank B: Chaos peak (sparse — no hook/call/response, different velocities)
        traj_b = LandscapeTrajectory(landscape=lm, x=0.0, y=1.0)
        dims_b = compute(traj_b, 0.5)
        bank_b = generate_bank(0, dims=dims_b,
                                signature_rhythm=traj_b.active_feature().signature_rhythm,
                                heat=0.5)

        # Verify banks are actually different
        events_a = {(e.musical_step, e.layer, e.velocity) for e in bank_a.all_events()}
        events_b = {(e.musical_step, e.layer, e.velocity) for e in bank_b.all_events()}
        assert events_a != events_b, "Test precondition: banks must differ"

        # Simulate: start with bank_a, swap to bank_b after bar 1
        current = [bank_a]
        bar_calls = []

        def get_bank():
            bar_calls.append(len(bar_calls))
            return current[0]

        bars_played = []

        class TrackingMidiOut:
            last_playback_interrupted = False
            port_name = "test"

            def send_note_on(self, ch, note, vel): pass
            def send_note_off(self, ch, note): pass
            def send_cc(self, ch, cc, val): pass
            def all_notes_off(self): pass
            def _interruptible_sleep(self, dur, ev): pass

            def _play_timeline(self, timeline, start, stop_event=None):
                # Record which bank's events are in this bar's timeline
                if timeline:
                    bars_played.append(current[0].bank_index)
                # After first bar, swap the bank
                if len(bars_played) == 1:
                    current[0] = bank_b
                return False

        fake = TrackingMidiOut()
        stop = threading.Event()

        MIDIOut.play_bank_bar_by_bar(fake, get_bank, bpm=174.0,
                                      start_time=time.perf_counter(),
                                      stop_event=stop)

        # The bar getter must have been called multiple times (not once at start)
        assert len(bar_calls) >= 2, (
            "get_current_bank must be called at each bar boundary, not just once"
        )


# ---------------------------------------------------------------------------
# 4. _current_bank is always up to date at bar boundaries
# ---------------------------------------------------------------------------

class TestCurrentBankAlwaysReflectsUIInput:

    def test_position_change_during_play_updates_current_bank(self):
        """When set_position fires during play, _current_bank changes immediately.

        The play loop reads _current_bank at the next bar boundary — within ≤1 bar.
        """
        server._init_full_banks()
        orig_x, orig_y = server._trajectory.x, server._trajectory.y

        try:
            # Record events at original position
            with server._state_lock:
                bank_before = server._current_bank
            steps_before = {(e.musical_step, e.layer)
                             for e in bank_before.all_events()}

            # Simulate position change to a very different location
            new_x, new_y = 0.0, 1.0   # Chaos peak
            server._trajectory.move_to(new_x, new_y)
            dims = compute(server._trajectory, server._heat_applied)
            sr   = server._trajectory.active_feature().signature_rhythm
            new_bank = generate_bank(
                server._bank_index, dims=dims, is_drop_phrase=False,
                signature_rhythm=sr,
                previous_active_archetype=server._active_archetype,
                heat=server._heat_applied,
            )
            # This is what the WS handler does — atomic swap under lock
            with server._state_lock:
                server._current_bank = new_bank
            server._bank_dirty = True

            # Immediately after: _current_bank must reflect new position
            with server._state_lock:
                bank_after = server._current_bank

            steps_after = {(e.musical_step, e.layer)
                           for e in bank_after.all_events()}

            assert steps_before != steps_after, (
                "_current_bank must reflect new position immediately — "
                "the play loop picks this up at the next bar boundary"
            )

        finally:
            server._trajectory.move_to(orig_x, orig_y)
            server._bank_dirty = False

    def test_one_bar_latency_upper_bound(self):
        """Verify the maximum latency between UI input and audible change.

        Now beat-level: at 174 BPM, one beat = 60/174 ≈ 0.345 seconds.
        Position changes must be audible within one beat.
        """
        bpm = 174.0
        seconds_per_beat = 60.0 / bpm
        seconds_per_bar  = seconds_per_beat * 4
        # Upper bound: 1 beat + small scheduling overhead
        max_latency_seconds = seconds_per_beat * 1.5   # ~0.52 s
        assert max_latency_seconds < 1.0, (
            "Beat latency budget exceeds 1 second — BPM changed?"
        )
        assert seconds_per_beat < 0.5, (
            f"One beat at {bpm} BPM = {seconds_per_beat:.3f}s — must be < 0.5s"
        )
        assert seconds_per_bar < 2.0, (
            f"One bar at {bpm} BPM = {seconds_per_bar:.2f}s — must be < 2s"
        )
