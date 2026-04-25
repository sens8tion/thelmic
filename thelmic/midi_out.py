"""rtmidi wrapper — virtual port named 'thelmic'."""

from __future__ import annotations

import time
from typing import Optional

import rtmidi

from thelmic.bank_generator import Bank, MIDIEvent, TICKS_PER_BEAT, BEATS_PER_BAR

PORT_NAME = "thelmic"


def _parse_time(time_str: str) -> tuple[int, int, int]:
    """Parse 'bar.beat.tick' → (bar, beat, tick), all 1-indexed except tick (0-indexed)."""
    parts = time_str.split(".")
    bar = int(parts[0])
    beat = int(parts[1])
    tick = int(parts[2]) if len(parts) > 2 else 0
    return bar, beat, tick


def event_to_abs_tick(time_str: str) -> int:
    """Convert 'bar.beat.tick' to absolute tick offset from bank start."""
    bar, beat, tick = _parse_time(time_str)
    ticks_per_bar = TICKS_PER_BEAT * BEATS_PER_BAR
    return (bar - 1) * ticks_per_bar + (beat - 1) * TICKS_PER_BEAT + tick


class MIDIOut:
    """Manages a virtual MIDI output port and sends note events."""

    def __init__(self) -> None:
        self._midiout = rtmidi.MidiOut()
        self._port_open = False
        self._open_virtual_port()

    def _open_virtual_port(self) -> None:
        try:
            self._midiout.open_virtual_port(PORT_NAME)
            self._port_open = True
        except Exception as e:
            # Fall back to first available port if virtual ports aren't supported
            available = self._midiout.get_ports()
            if available:
                self._midiout.open_port(0)
                self._port_open = True
            else:
                raise RuntimeError(
                    f"Cannot open virtual MIDI port '{PORT_NAME}' and no physical ports found."
                ) from e

    def send_note_on(self, channel: int, note: int, velocity: int) -> None:
        self._midiout.send_message([0x90 | (channel & 0xF), note & 0x7F, velocity & 0x7F])

    def send_note_off(self, channel: int, note: int) -> None:
        self._midiout.send_message([0x80 | (channel & 0xF), note & 0x7F, 0])

    def play_bank_blocking(self, bank: Bank, bpm: float = 174.0, channel: int = 0) -> None:
        """Play a bank synchronously, blocking until complete. For testing/examples."""
        seconds_per_tick = 60.0 / (bpm * TICKS_PER_BEAT)

        events = sorted(bank.all_events(), key=lambda e: event_to_abs_tick(e.time))

        start_time = time.perf_counter()
        for event in events:
            abs_tick = event_to_abs_tick(event.time)
            target_time = start_time + abs_tick * seconds_per_tick
            now = time.perf_counter()
            if target_time > now:
                time.sleep(target_time - now)
            self.send_note_on(channel, event.note, event.velocity)
            time.sleep(event.duration)
            self.send_note_off(channel, event.note)

    def close(self) -> None:
        if self._port_open:
            self._midiout.close_port()
            self._port_open = False

    def __enter__(self) -> "MIDIOut":
        return self

    def __exit__(self, *_) -> None:
        self.close()
