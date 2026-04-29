"""Behaviour-transparent MIDI output renderer."""

from __future__ import annotations

import time
from typing import Optional

import rtmidi

from thelmic.bank_generator import BEATS_PER_BAR, BARS_PER_PHRASE, Bank, Phrase, TICKS_PER_BEAT


LAYER_CHANNELS: dict[str, int] = {
    "kick": 0,
    "snare": 1,
    "hat": 2,
}


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

    def send_note_on(self, channel: int, note: int, velocity: int) -> None:
        if self._port_open:
            self._midiout.send_message([0x90 | (channel & 0xF), note & 0x7F, velocity & 0x7F])

    def send_note_off(self, channel: int, note: int) -> None:
        if self._port_open:
            self._midiout.send_message([0x80 | (channel & 0xF), note & 0x7F, 0])

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

    def play_bank_blocking(
        self,
        bank: Bank,
        bpm: float = 174.0,
        start_time: Optional[float] = None,
    ) -> float:
        seconds_per_tick = 60.0 / (bpm * TICKS_PER_BEAT)
        ticks_per_bar = TICKS_PER_BEAT * BEATS_PER_BAR
        events = [event for event in bank.all_events() if is_grid_midi_event(event)]
        n_bars = max((event_to_abs_tick(event.time) // ticks_per_bar + 1) for event in events)
        timeline: list[tuple[float, str, int, int, int]] = []
        for event in events:
            on_time = event_to_abs_tick(event.time) * seconds_per_tick
            off_time = on_time + event.duration
            channel = LAYER_CHANNELS[event.layer]
            timeline.append((on_time, "on", channel, event.note, event.velocity))
            timeline.append((off_time, "off", channel, event.note, 0))
        timeline.sort(key=lambda item: item[0])
        start = start_time or time.perf_counter()
        self._play_timeline(timeline, start)
        bank_end = start + n_bars * ticks_per_bar * seconds_per_tick
        remaining = bank_end - time.perf_counter()
        if remaining > 0:
            time.sleep(remaining)
        return bank_end

    def _play_timeline(self, timeline: list[tuple[float, str, int, int, int]], start: float) -> None:
        send_ms = 0.0
        for relative_time, action, channel, note, velocity in timeline:
            target = start + relative_time
            now = time.perf_counter()
            if target > now:
                time.sleep(target - now)
            t_send = time.perf_counter()
            if action == "on":
                self.send_note_on(channel, note, velocity)
            else:
                self.send_note_off(channel, note)
            send_ms += (time.perf_counter() - t_send) * 1000
        self.last_send_ms = round(send_ms, 3)
        self.last_cleanup_ms = 0.0

    def close(self) -> None:
        if self._port_open:
            self._midiout.close_port()
            self._port_open = False

    def __enter__(self) -> "MIDIOut":
        return self

    def __exit__(self, *_) -> None:
        self.close()
