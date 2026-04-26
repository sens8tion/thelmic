"""rtmidi wrapper — connects to a named loopMIDI (or any) output port."""

from __future__ import annotations

import time
from typing import Optional

import rtmidi

from thelmic.bank_generator import Bank, TICKS_PER_BEAT, BEATS_PER_BAR

# MIDI channel per instrument layer (0-indexed, i.e. ch 1–3 in DAW)
LAYER_CHANNELS: dict[str, int] = {
    "kick":  0,
    "snare": 1,
    "hat":   2,
}


def list_output_ports() -> list[str]:
    """Return names of all available MIDI output ports."""
    tmp = rtmidi.MidiOut()
    ports = tmp.get_ports()
    del tmp
    return ports


def _parse_time(time_str: str) -> tuple[int, int, int]:
    parts = time_str.split(".")
    bar  = int(parts[0])
    beat = int(parts[1])
    tick = int(parts[2]) if len(parts) > 2 else 0
    return bar, beat, tick


def event_to_abs_tick(time_str: str) -> int:
    bar, beat, tick = _parse_time(time_str)
    ticks_per_bar = TICKS_PER_BEAT * BEATS_PER_BAR
    return (bar - 1) * ticks_per_bar + (beat - 1) * TICKS_PER_BEAT + tick


class MIDIOut:
    """Opens a named MIDI output port and sends note events."""

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

    def play_bank_blocking(
        self,
        bank: Bank,
        bpm: float = 174.0,
        start_time: Optional[float] = None,
    ) -> float:
        """Play a bank synchronously, blocking until complete.

        Builds a flat timeline of (note-on, note-off) events sorted by time,
        then steps through them with a single sleep per event — no blocking
        inside the loop for note duration.

        start_time: absolute perf_counter time the bank should begin. Defaults
        to now. Pass the expected start (previous bank's end) to prevent drift
        accumulating across banks.

        Returns the expected end time of this bank (= start_time + bank_duration).
        """
        seconds_per_tick = 60.0 / (bpm * TICKS_PER_BEAT)
        ticks_per_bar    = TICKS_PER_BEAT * BEATS_PER_BAR

        # Total bank length in ticks — used to compute the expected end time
        # even if the bank has no events (e.g. all slots silent).
        n_bars = max(
            (event_to_abs_tick(e.time) // ticks_per_bar + 1)
            for e in bank.all_events()
        ) if bank.all_events() else 0
        bank_duration_s = n_bars * ticks_per_bar * seconds_per_tick

        # Build a flat sorted timeline of (abs_time_s, action, ch, note, vel)
        timeline: list[tuple[float, str, int, int, int]] = []
        for event in bank.all_events():
            if event.velocity == 0:
                continue
            t_on  = event_to_abs_tick(event.time) * seconds_per_tick
            t_off = t_on + event.duration
            ch    = LAYER_CHANNELS.get(event.layer, 0)
            timeline.append((t_on,  "on",  ch, event.note, event.velocity))
            timeline.append((t_off, "off", ch, event.note, 0))

        timeline.sort(key=lambda x: x[0])

        if start_time is None:
            start_time = time.perf_counter()

        for t_rel, action, ch, note, vel in timeline:
            target = start_time + t_rel
            now    = time.perf_counter()
            if target > now:
                time.sleep(target - now)
            if action == "on":
                self.send_note_on(ch, note, vel)
            else:
                self.send_note_off(ch, note)

        # Wait out the rest of the bank if events finished early
        bank_end = start_time + bank_duration_s
        remaining = bank_end - time.perf_counter()
        if remaining > 0:
            time.sleep(remaining)

        return bank_end

    def close(self) -> None:
        if self._port_open:
            self._midiout.close_port()
            self._port_open = False

    def __enter__(self) -> "MIDIOut":
        return self

    def __exit__(self, *_) -> None:
        self.close()
