"""rtmidi wrapper — connects to a named loopMIDI (or any) output port."""

from __future__ import annotations

import time
from typing import Optional

import rtmidi

from thelmic.bank_generator import Bank, TICKS_PER_BEAT, BEATS_PER_BAR


def list_output_ports() -> list[str]:
    """Return names of all available MIDI output ports."""
    tmp = rtmidi.MidiOut()
    ports = tmp.get_ports()
    del tmp
    return ports


def _parse_time(time_str: str) -> tuple[int, int, int]:
    parts = time_str.split(".")
    bar = int(parts[0])
    beat = int(parts[1])
    tick = int(parts[2]) if len(parts) > 2 else 0
    return bar, beat, tick


def event_to_abs_tick(time_str: str) -> int:
    bar, beat, tick = _parse_time(time_str)
    ticks_per_bar = TICKS_PER_BEAT * BEATS_PER_BAR
    return (bar - 1) * ticks_per_bar + (beat - 1) * TICKS_PER_BEAT + tick


class MIDIOut:
    """Opens a named MIDI output port and sends note events.

    Pass port_name to connect to a specific loopMIDI port.
    If port_name is None, opens the first available port.
    Raises RuntimeError if no matching port is found.
    """

    def __init__(self, port_name: Optional[str] = None) -> None:
        self._midiout = rtmidi.MidiOut()
        self._port_open = False
        self._port_name: Optional[str] = None
        self._open_port(port_name)

    def _open_port(self, port_name: Optional[str]) -> None:
        available = self._midiout.get_ports()
        if not available:
            raise RuntimeError("No MIDI output ports found. Create a port in loopMIDI first.")

        if port_name is None:
            self._midiout.open_port(0)
            self._port_name = available[0]
            self._port_open = True
            return

        for idx, name in enumerate(available):
            if port_name.lower() in name.lower():
                self._midiout.open_port(idx)
                self._port_name = name
                self._port_open = True
                return

        raise RuntimeError(
            f"MIDI port '{port_name}' not found. Available: {available}"
        )

    @property
    def port_name(self) -> Optional[str]:
        return self._port_name

    def send_note_on(self, channel: int, note: int, velocity: int) -> None:
        if self._port_open:
            self._midiout.send_message([0x90 | (channel & 0xF), note & 0x7F, velocity & 0x7F])

    def send_note_off(self, channel: int, note: int) -> None:
        if self._port_open:
            self._midiout.send_message([0x80 | (channel & 0xF), note & 0x7F, 0])

    def play_bank_blocking(self, bank: Bank, bpm: float = 174.0, channel: int = 0) -> None:
        """Play a bank synchronously, blocking until complete."""
        seconds_per_tick = 60.0 / (bpm * TICKS_PER_BEAT)
        events = sorted(bank.all_events(), key=lambda e: event_to_abs_tick(e.time))

        start_time = time.perf_counter()
        for event in events:
            abs_tick = event_to_abs_tick(event.time)
            target_time = start_time + abs_tick * seconds_per_tick
            now = time.perf_counter()
            if target_time > now:
                time.sleep(target_time - now)
            if event.velocity > 0:   # velocity 0 = withheld_resolution, display only
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
