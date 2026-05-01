"""Behaviour-transparent MIDI output renderer."""

from __future__ import annotations

import threading
import time
from typing import Optional

import rtmidi

from thelmic.bank_generator import BEATS_PER_BAR, BARS_PER_PHRASE, Bank, Phrase, TICKS_PER_BEAT


LAYER_CHANNELS: dict[str, int] = {
    "kick":     0,
    "snare":    1,
    "hat":      2,    # closed hat
    "open_hat": 15,  # open hat — ch 16 in DAW
    "bass":     3,
    "sub":      4,   # sub bass — one octave below bass root, sparse/stable only
    "hook":     5,
    "call":     6,
    "response":      8,    # separate channel from call; ch7 reserved for sidechain CC
    "drone_spacey":  10,   # ch11 in DAW — spacey atmospheric, high register
    "drone_rumble":  11,   # ch12 in DAW — low rumble, sub-bass register
    "drone_tension": 12,   # ch13 in DAW — tension chord, mid register bar downbeats
}

# Pression CC outputs — control lanes for DAW routing.
# These carry expression signals, not note events.
# Route these to compressors, filters, and modulation targets in your DAW.
PRESSION_CC: dict[str, tuple[int, int]] = {
    # name: (channel, cc_number)
    "sidechain": (7, 1),   # ch 8 in DAW; CC 1 — kicks 127, between 0; compressor sidechain
    "heat":      (9, 2),   # ch 10 in DAW; CC 2 — heat 0-127 per bar; filter/distortion

    # Pression dimension CCs — channel is configurable at runtime (_PRESSION_CHANNEL).
    # Default ch 13 (DAW ch 14).  CC numbers are fixed:
    "stability": (13, 10),  # terrain stability 0–127
    "pressure":  (13, 11),  # movement pressure 0–127
    "sparsity":  (13, 12),  # instrumentation density 0–127 (inverted: 127=sparse)
    "release":   (13, 13),  # post-drop release burst 0–127
    "emphasis":  (13, 14),  # phrase emphasis 0–127
}

# Pression dimension names in display order
PRESSION_DIMS = ("stability", "pressure", "sparsity", "release", "emphasis")

# CC number for each pression dimension (fixed — only channel is configurable)
PRESSION_DIM_CC = {name: PRESSION_CC[name][1] for name in PRESSION_DIMS}


def is_grid_midi_event(event) -> bool:
    return (
        getattr(event, "active", True)
        and getattr(event, "velocity", 0) > 0
        and getattr(event, "layer", "") in LAYER_CHANNELS
    )


def list_output_ports() -> list[str]:
    tmp = rtmidi.MidiOut()
    ports = tmp.get_ports()
    del tmp
    return ports


def event_to_abs_tick(time_str: str) -> int:
    bar, beat, tick = _parse_time(time_str)
    ticks_per_bar = TICKS_PER_BEAT * BEATS_PER_BAR
    return (bar - 1) * ticks_per_bar + (beat - 1) * TICKS_PER_BEAT + tick


def _parse_time(time_str: str) -> tuple[int, int, int]:
    parts = time_str.split(".")
    bar = int(parts[0])
    beat = int(parts[1])
    tick = int(parts[2]) if len(parts) > 2 else 0
    return bar, beat, tick


class MIDIOut:
    def __init__(self, port_name: Optional[str] = None) -> None:
        self._midiout = rtmidi.MidiOut()
        self._port_open = False
        self._port_name: Optional[str] = None
        self.last_send_ms = 0.0
        self.last_cleanup_ms = 0.0
        self.last_playback_interrupted = False   # True if last bank was stopped early
        self._open_port(port_name)

    @property
    def port_name(self) -> Optional[str]:
        return self._port_name

    def _open_port(self, port_name: Optional[str]) -> None:
        available = self._midiout.get_ports()
        if not available:
            raise RuntimeError("No MIDI output ports found.")
        if port_name is None:
            self._midiout.open_port(0)
            self._port_name = available[0]
            self._port_open = True
            return
        for index, name in enumerate(available):
            if port_name.lower() in name.lower():
                self._midiout.open_port(index)
                self._port_name = name
                self._port_open = True
                return
        raise RuntimeError(f"MIDI port '{port_name}' not found. Available: {available}")

    def send_cc(self, channel: int, cc: int, value: int) -> None:
        """Send a MIDI Control Change message."""
        if self._port_open:
            self._midiout.send_message([0xB0 | (channel & 0xF), cc & 0x7F, value & 0x7F])

    def send_note_on(self, channel: int, note: int, velocity: int) -> None:
        if self._port_open:
            self._midiout.send_message([0x90 | (channel & 0xF), note & 0x7F, velocity & 0x7F])

    def send_note_off(self, channel: int, note: int) -> None:
        if self._port_open:
            self._midiout.send_message([0x80 | (channel & 0xF), note & 0x7F, 0])

    def all_notes_off(self) -> None:
        """Send All Notes Off (CC 123) on every active channel."""
        if not self._port_open:
            return
        for channel in LAYER_CHANNELS.values():
            self._midiout.send_message([0xB0 | (channel & 0xF), 123, 0])

    def play_bar_in_phrase_blocking(
        self,
        phrase: Phrase,
        bar_in_phrase: int,
        bpm: float,
        bank_start: float,
    ) -> float:
        seconds_per_tick = 60.0 / (bpm * TICKS_PER_BEAT)
        ticks_per_bar = TICKS_PER_BEAT * BEATS_PER_BAR
        abs_bar_idx = phrase.phrase_index * BARS_PER_PHRASE + bar_in_phrase
        bar_start_tick = abs_bar_idx * ticks_per_bar
        bar_end_tick = bar_start_tick + ticks_per_bar
        bar_end_s = bar_end_tick * seconds_per_tick

        timeline: list[tuple[float, str, int, int, int]] = []
        for event in phrase.events:
            if not is_grid_midi_event(event):
                continue
            event_tick = event_to_abs_tick(event.time)
            if bar_start_tick <= event_tick < bar_end_tick:
                on_time = event_tick * seconds_per_tick
                off_time = min(on_time + event.duration, bar_end_s)
                channel = LAYER_CHANNELS[event.layer]
                timeline.append((on_time, "on", channel, event.note, event.velocity))
                timeline.append((off_time, "off", channel, event.note, 0))
        timeline.sort(key=lambda item: item[0])
        self._play_timeline(timeline, bank_start)
        bar_end_abs = bank_start + bar_end_tick * seconds_per_tick
        remaining = bar_end_abs - time.perf_counter()
        if remaining > 0:
            time.sleep(remaining)
        return bar_end_abs

    def play_bank_bar_by_bar(
        self,
        get_current_bank,
        bpm: float = 174.0,
        start_time: Optional[float] = None,
        stop_event: Optional[threading.Event] = None,
        on_bar_start=None,      # optional callable(bar_abs: int)
        get_heat=None,          # callable() → float [0,1]
        get_pression=None,      # callable() → dict[str → float [0,1]]  (stability, pressure, etc.)
        get_pression_channel=None,  # callable() → int (0-based MIDI channel)
        get_mapping_mode=None,  # callable() → str|None  (dim name being mapped, or None)
    ) -> float:
        """Beat-level playback with pression CC emission.

        Mapping mode: when get_mapping_mode() returns a dimension name,
        ONLY that dimension's CC is emitted.  Note-on events are suppressed
        so Ableton's MIDI learn sees only the one CC signal.
        Pending note-offs are still sent to avoid stuck notes.
        """
        """Play one bank beat-by-beat, reading the current bank at every beat boundary.

        get_current_bank is called at every beat (quarter-note) so position changes
        take effect within ~350ms at 174 BPM rather than a full bar (~1.4s).

        Timing is anchored to start_time — no cumulative drift.
        Returns the projected wall-clock end of the bank.
        """
        seconds_per_tick = 60.0 / (bpm * TICKS_PER_BEAT)
        ticks_per_bar    = TICKS_PER_BEAT * BEATS_PER_BAR
        ticks_per_beat   = TICKS_PER_BEAT              # one quarter note
        n_bars           = BARS_PER_PHRASE * 4         # 16 bars per bank
        n_beats          = n_bars * BEATS_PER_BAR      # 64 beats per bank
        sc_channel, sc_cc = PRESSION_CC["sidechain"]
        start = start_time or time.perf_counter()
        self.last_playback_interrupted = False

        # pending_offs: deferred note-offs for sustained notes keyed by target beat.
        # When a note's off_time falls beyond the current beat, we defer it to the
        # beat where it actually belongs so the beat loop never blocks waiting for
        # a far-future note-off.
        pending_offs: dict[int, list[tuple[float, str, int, int, int]]] = {}

        heat_ch, heat_cc = PRESSION_CC["heat"]
        ticks_per_step   = ticks_per_bar // 16    # 6 ticks per 16th note

        for beat_abs in range(n_beats):
            # ── Bar-start: journey advance + heat CC ─────────────────────────
            if beat_abs % BEATS_PER_BAR == 0:
                bar_abs = beat_abs // BEATS_PER_BAR
                if on_bar_start:
                    on_bar_start(bar_abs)
                if get_heat:
                    heat_val = max(0, min(127, int(get_heat() * 127)))
                    self.send_cc(heat_ch, heat_cc, heat_val)

            # ── Mapping mode: suppress note-ons; only CCs above are emitted ──
            mapping = get_mapping_mode() if get_mapping_mode else None

            # Read the current bank at every beat — position changes land within one beat.
            bank = get_current_bank()

            beat_start_tick = beat_abs * ticks_per_beat
            beat_end_tick   = beat_start_tick + ticks_per_beat

            # Start with any deferred note-offs due this beat.
            timeline: list[tuple[float, str, int, int, int]] = list(
                pending_offs.pop(beat_abs, [])
            )

            # ── Pression CCs at every 16th note step within this beat ─────────
            # Interleaved with note events so each step has its own CC values.
            # get_pression(step_in_bar) returns per-step values shaped by the
            # archetype's kick/snare grid — different for each of the 16 steps.
            if get_pression:
                mode = get_mapping_mode() if get_mapping_mode else None
                pch  = (get_pression_channel() if get_pression_channel
                        else PRESSION_CC["stability"][0])
                beat_in_bar = beat_abs % BEATS_PER_BAR
                for sub in range(4):
                    step_in_bar = beat_in_bar * 4 + sub   # 0-15
                    step_tick   = beat_start_tick + sub * ticks_per_step
                    step_time   = step_tick * seconds_per_tick
                    # Per-step values shaped by archetype event grid
                    pression = get_pression(step_in_bar)
                    for dim, val_01 in pression.items():
                        if dim not in PRESSION_DIM_CC:
                            continue
                        if mode is not None and dim != mode:
                            continue
                        cc_num = PRESSION_DIM_CC[dim]
                        cc_val = max(0, min(127, int(val_01 * 127)))
                        timeline.append((step_time, "cc", pch, cc_num, cc_val))

            for event in bank.all_events():
                if not is_grid_midi_event(event):
                    continue
                event_tick = event_to_abs_tick(event.time)
                if beat_start_tick <= event_tick < beat_end_tick:
                    on_time  = event_tick * seconds_per_tick
                    off_time = on_time + event.duration
                    channel  = LAYER_CHANNELS[event.layer]
                    # In mapping mode: suppress note-ons so Ableton sees only CCs.
                    # Note-offs are still deferred normally to prevent stuck notes.
                    if mapping is None:
                        timeline.append((on_time, "on", channel, event.note, event.velocity))
                        if event.layer == "kick":
                            timeline.append((on_time, "cc", sc_channel, sc_cc, 127))

                    # Determine which beat the note-off belongs to.
                    off_ticks_abs  = int(off_time / seconds_per_tick)
                    off_beat       = min(off_ticks_abs // ticks_per_beat, n_beats - 1)
                    off_entry      = (off_time, "off", channel, event.note, 0)
                    sc_off_entry   = (off_time, "cc",  sc_channel, sc_cc, 0)
                    if off_beat <= beat_abs:
                        # Short note — off_time within same beat
                        timeline.append(off_entry)
                        if event.layer == "kick":
                            timeline.append(sc_off_entry)
                    else:
                        # Sustained note — defer note-off to its correct future beat
                        pending_offs.setdefault(off_beat, []).append(off_entry)
                        if event.layer == "kick":
                            pending_offs[off_beat].append(sc_off_entry)

            timeline.sort(key=lambda item: item[0])

            stopped = self._play_timeline(timeline, start, stop_event=stop_event)
            if stopped:
                self.last_playback_interrupted = True
                return time.perf_counter()

            # Sleep until the absolute beat end — anchored to start, no drift.
            beat_end_abs = start + beat_end_tick * seconds_per_tick
            remaining    = beat_end_abs - time.perf_counter()
            if remaining > 0:
                self._interruptible_sleep(remaining, stop_event)
            if stop_event and stop_event.is_set():
                self.last_playback_interrupted = True
                return time.perf_counter()

        # Fire any remaining deferred note-offs (notes sustaining past bank end).
        if pending_offs:
            leftovers = []
            for offs in pending_offs.values():
                leftovers.extend(offs)
            if leftovers:
                self._play_timeline(sorted(leftovers), start, stop_event=stop_event)

        return start + n_beats * ticks_per_beat * seconds_per_tick

    def play_bank_blocking(
        self,
        bank: Bank,
        bpm: float = 174.0,
        start_time: Optional[float] = None,
        stop_event: Optional[threading.Event] = None,
    ) -> float:
        seconds_per_tick = 60.0 / (bpm * TICKS_PER_BEAT)
        ticks_per_bar = TICKS_PER_BEAT * BEATS_PER_BAR
        events = [event for event in bank.all_events() if is_grid_midi_event(event)]
        n_bars = max((event_to_abs_tick(event.time) // ticks_per_bar + 1) for event in events)
        sc_channel, sc_cc = PRESSION_CC["sidechain"]
        timeline: list[tuple[float, str, int, int, int]] = []
        for event in events:
            on_time  = event_to_abs_tick(event.time) * seconds_per_tick
            off_time = on_time + event.duration
            channel  = LAYER_CHANNELS[event.layer]
            timeline.append((on_time,  "on",  channel, event.note, event.velocity))
            timeline.append((off_time, "off", channel, event.note, 0))
            # Sidechain CC: spike 127 on every kick, release to 0 after kick duration
            if event.layer == "kick":
                timeline.append((on_time,  "cc", sc_channel, sc_cc, 127))
                timeline.append((off_time, "cc", sc_channel, sc_cc, 0))
        timeline.sort(key=lambda item: item[0])
        start = start_time or time.perf_counter()
        self.last_playback_interrupted = False
        stopped = self._play_timeline(timeline, start, stop_event=stop_event)
        if stopped:
            self.last_playback_interrupted = True
            return time.perf_counter()
        bank_end = start + n_bars * ticks_per_bar * seconds_per_tick
        remaining = bank_end - time.perf_counter()
        if remaining > 0:
            self._interruptible_sleep(remaining, stop_event)
        if stop_event and stop_event.is_set():
            self.last_playback_interrupted = True
            return time.perf_counter()
        return bank_end

    def _interruptible_sleep(
        self,
        duration: float,
        stop_event: Optional[threading.Event],
    ) -> None:
        """Sleep for duration seconds, waking every 20 ms to check stop_event."""
        if stop_event is None:
            time.sleep(duration)
            return
        deadline = time.perf_counter() + duration
        while time.perf_counter() < deadline:
            if stop_event.is_set():
                return
            remaining = deadline - time.perf_counter()
            time.sleep(min(0.02, max(0.0, remaining)))

    def _play_timeline(
        self,
        timeline: list[tuple[float, str, int, int, int]],
        start: float,
        stop_event: Optional[threading.Event] = None,
    ) -> bool:
        """Play timeline events.  Returns True if interrupted by stop_event."""
        send_ms = 0.0
        for relative_time, action, channel, note, velocity in timeline:
            target = start + relative_time
            now = time.perf_counter()
            if target > now:
                self._interruptible_sleep(target - now, stop_event)
            if stop_event and stop_event.is_set():
                self.all_notes_off()
                return True
            t_send = time.perf_counter()
            if action == "on":
                self.send_note_on(channel, note, velocity)
            elif action == "off":
                self.send_note_off(channel, note)
            elif action == "cc":
                self.send_cc(channel, note, velocity)   # note=cc_number, velocity=value
            send_ms += (time.perf_counter() - t_send) * 1000
        self.last_send_ms = round(send_ms, 3)
        self.last_cleanup_ms = 0.0
        return False

    def close(self) -> None:
        if self._port_open:
            self._midiout.close_port()
            self._port_open = False

    def __enter__(self) -> "MIDIOut":
        return self

    def __exit__(self, *_) -> None:
        self.close()
