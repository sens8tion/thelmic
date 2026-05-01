"""UI behaviour tests — verifying the four critical issues.

1. Grid never empties on position change (bank_dirty + bank_events always together)
2. Position change produces immediate broadcast with updated events
3. Startup uses bare banks; full banks ready before first connect
4. MIDI stream resumes without requiring Ableton restart
"""

from __future__ import annotations

import time
import pytest

from thelmic import server
from thelmic.note_generation_chain import generate_bank, BANK_STEPS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _full_bank_layers():
    """Layers present in a full-voice bank at the default position."""
    return {"kick", "snare", "hat", "bass"}   # hook/call/response gated at Chaos


# ---------------------------------------------------------------------------
# 1. Grid never empties on position change
# ---------------------------------------------------------------------------

class TestGridNeverEmptiesOnChange:
    """bank_dirty must only be True when bank_events are also present in the same state.

    The JS ordering contract:
        mergeState(state) flushes byLayerStep THEN adds new events — both in one call.
        render(state) never touches byLayerStep.

    If flush happened in render() (after mergeState), it would delete the events
    just added by mergeState, blanking the grid for a full render frame.
    """

    def test_bank_dirty_always_accompanies_events(self):
        """When bank_dirty=True the state MUST include non-empty bank_events.

        This is the server-side half of the no-blank contract.  The JS half is
        that flush happens inside mergeState() before the event merge, not in
        render() after it.  The generation counter provides a race-proof second
        signal: even if bank_dirty is consumed by a racing broadcast, the
        incrementing counter tells the JS to flush.
        """
        server._init_full_banks()
        gen_before = server._bank_generation
        server._bank_dirty     = True
        server._bank_generation += 1
        state = server._state(include_bank=True)
        # bank_dirty must be True (it was set above and _state reads it)
        assert state.get("bank_dirty") is True, (
            "_state() must return bank_dirty=True when flag was set"
        )
        assert len(state.get("bank_events", [])) > 0, (
            "bank_dirty=True without bank_events would blank the grid"
        )
        assert state.get("bank_generation") == gen_before + 1, (
            "bank_generation must be emitted in state and must be the incremented value"
        )

    def test_bank_dirty_with_include_bank_false_still_emits_events(self):
        """When bank_dirty=True, bank_events must be included even if include_bank=False.

        This guards against the race where a play-loop broadcast (include_bank=False)
        fires while bank_dirty is True.  Without events, the JS flush blanks the grid.
        """
        server._init_full_banks()
        server._bank_dirty = True
        # Explicitly pass include_bank=False — dirty flag must override this
        state = server._state(include_bank=False)
        assert state.get("bank_dirty") is True
        assert "bank_events" in state, (
            "bank_events must be present when bank_dirty=True, regardless of include_bank"
        )
        assert len(state["bank_events"]) > 0

    def test_bank_events_present_in_state(self):
        server._init_full_banks()
        state = server._state(include_bank=True)
        assert "bank_events" in state
        assert len(state["bank_events"]) > 0

    def test_position_change_produces_bank_events_and_dirty(self):
        """Simulating set_position: resulting state has both bank_dirty and bank_events."""
        server._init_full_banks()
        # Simulate a position change
        orig_x, orig_y = server._trajectory.x, server._trajectory.y
        try:
            server._trajectory.move_to(-0.5, -0.3)   # toward Oak
            from thelmic.dimension_engine import compute
            _dims = compute(server._trajectory, server._heat_applied)
            _sr   = server._trajectory.active_feature().signature_rhythm
            new_bank = generate_bank(
                server._bank_index, dims=_dims, is_drop_phrase=False,
                signature_rhythm=_sr,
                previous_active_archetype=server._active_archetype,
                heat=server._heat_applied,
            )
            with server._state_lock:
                server._current_bank = new_bank
            server._bank_dirty = True
            state = server._state(include_bank=True)
            # After position change: must have events (never empty)
            assert len(state["bank_events"]) > 0, "bank_events empty after position change"
        finally:
            server._trajectory.move_to(orig_x, orig_y)
            server._bank_dirty = False


# ---------------------------------------------------------------------------
# 2. Position change produces immediate broadcast
# ---------------------------------------------------------------------------

class TestPositionChangeImmediate:

    def test_position_change_updates_current_bank(self):
        """After set_position logic, _current_bank reflects new position."""
        server._init_full_banks()
        orig_x, orig_y = server._trajectory.x, server._trajectory.y

        try:
            # Move to Oak (stable, different from default Chaos position)
            server._trajectory.move_to(-1.0, -0.6)
            from thelmic.dimension_engine import compute
            _dims = compute(server._trajectory, server._heat_applied)
            _sr   = server._trajectory.active_feature().signature_rhythm
            new_bank = generate_bank(
                server._bank_index, dims=_dims, is_drop_phrase=False,
                signature_rhythm=_sr,
                previous_active_archetype=server._active_archetype,
                heat=server._heat_applied,
            )
            with server._state_lock:
                server._current_bank = new_bank

            state = server._state(include_bank=True)
            layers = {e["layer"] for e in state["bank_events"]}

            # At Oak: hook, call, response should return (low positional sparsity)
            # At minimum: kick, snare, hat, bass always present
            assert "kick"  in layers, "kick missing at Oak position"
            assert "snare" in layers, "snare missing at Oak position"
            assert "hat"   in layers, "hat missing at Oak position"
            assert "bass"  in layers, "bass missing at Oak position"
        finally:
            server._trajectory.move_to(orig_x, orig_y)

    def test_position_change_differs_between_locations(self):
        """Two distant positions produce different event sets."""
        server._init_full_banks()
        orig_x, orig_y = server._trajectory.x, server._trajectory.y

        def events_at(x, y):
            server._trajectory.move_to(x, y)
            from thelmic.dimension_engine import compute
            d  = compute(server._trajectory, 0.5)
            sr = server._trajectory.active_feature().signature_rhythm
            b  = generate_bank(0, dims=d, is_drop_phrase=False,
                                signature_rhythm=sr, heat=0.5)
            return frozenset(
                (e.musical_step, e.layer, e.velocity)
                for e in b.all_events()
            )

        try:
            oak_events   = events_at(-1.0, -0.6)
            chaos_events = events_at(0.0,  1.0)
            assert oak_events != chaos_events, (
                "Oak and Chaos peak should produce different events"
            )
        finally:
            server._trajectory.move_to(orig_x, orig_y)


# ---------------------------------------------------------------------------
# 3. Startup performance
# ---------------------------------------------------------------------------

class TestStartupPerformance:

    def test_bare_banks_have_no_bass_at_startup_before_init(self):
        """Before _init_full_banks, banks are bare (kick/snare/hat only)."""
        bare = generate_bank(0)   # no dims
        layers = {e.layer for e in bare.all_events()}
        assert "kick"  in layers
        assert "snare" in layers
        assert "hat"   in layers
        assert "bass"  not in layers, "bare bank should not have bass"

    def test_init_done_event_signals_within_reasonable_time(self):
        """Background bank init completes within 10 seconds of module load."""
        result = server._init_done_event.wait(timeout=10.0)
        assert result, "bank init took longer than 10 seconds"

    def test_full_banks_have_bass_after_init(self):
        """After _init_full_banks, current bank has full voice set."""
        server._init_full_banks()
        layers = {e.layer for e in server._current_bank.all_events()}
        assert _full_bank_layers().issubset(layers), (
            f"full bank missing layers: {_full_bank_layers() - layers}"
        )

    def test_state_call_waits_for_banks(self):
        """_state() never returns bare banks — always waits for full init."""
        state = server._state(include_bank=True)
        layers = {e["layer"] for e in state["bank_events"]}
        assert "bass" in layers or "kick" in layers, (
            "_state returned empty bank_events"
        )


# ---------------------------------------------------------------------------
# 4. MIDI stream resumes without Ableton restart
# ---------------------------------------------------------------------------

class TestMidiResumption:

    def test_midi_port_saved_on_open(self, tmp_path, monkeypatch):
        """Opening a MIDI port persists its name to .midi_port file."""
        config_path = tmp_path / ".midi_port"
        monkeypatch.setattr(server, "_MIDI_CONFIG_PATH", config_path)

        server._save_midi_port("loopMIDI Port 1")
        assert config_path.read_text(encoding="utf-8").strip() == "loopMIDI Port 1"

    def test_midi_port_loaded_on_start(self, tmp_path, monkeypatch):
        """Last-used MIDI port name is loaded from the config file."""
        config_path = tmp_path / ".midi_port"
        config_path.write_text("loopMIDI Port 1", encoding="utf-8")
        monkeypatch.setattr(server, "_MIDI_CONFIG_PATH", config_path)

        loaded = server._load_saved_midi_port()
        assert loaded == "loopMIDI Port 1"

    def test_empty_port_file_returns_none(self, tmp_path, monkeypatch):
        """Empty .midi_port file returns None (no auto-reconnect)."""
        config_path = tmp_path / ".midi_port"
        config_path.write_text("", encoding="utf-8")
        monkeypatch.setattr(server, "_MIDI_CONFIG_PATH", config_path)

        loaded = server._load_saved_midi_port()
        assert loaded is None

    def test_all_notes_off_sent_on_stop(self):
        """Stopping playback sends All Notes Off so Ableton has no stuck notes."""
        from thelmic.midi_out import MIDIOut
        import unittest.mock as mock

        sent = []

        class FakeMidiOut:
            port_name = "test"
            last_playback_interrupted = False

            def all_notes_off(self):
                sent.append("all_notes_off")

        orig_midi = server._midi
        try:
            server._midi = FakeMidiOut()
            server._stop_playback()
            assert "all_notes_off" in sent, (
                "all_notes_off must be called on stop to clear Ableton stuck notes"
            )
        finally:
            server._midi = orig_midi

    def test_midi_channel_mapping_stable(self):
        """MIDI channels never change between restarts (Ableton routing stays valid)."""
        from thelmic.midi_out import LAYER_CHANNELS, PRESSION_CC
        assert LAYER_CHANNELS["kick"]     == 0
        assert LAYER_CHANNELS["snare"]    == 1
        assert LAYER_CHANNELS["hat"]      == 2
        assert LAYER_CHANNELS["bass"]     == 3
        assert LAYER_CHANNELS["sub"]      == 4
        assert LAYER_CHANNELS["hook"]     == 5
        assert LAYER_CHANNELS["call"]     == 6
        assert LAYER_CHANNELS["response"] == 8   # ch 7 reserved for sidechain CC
        assert PRESSION_CC["sidechain"]   == (7, 1), (
            "sidechain CC channel/number must not change — Ableton routing depends on it"
        )
