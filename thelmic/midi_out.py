"""rtmidi wrapper — connects to a named loopMIDI (or any) output port."""

from __future__ import annotations

import time
from typing import Optional

import rtmidi

from thelmic.bank_generator import Bank, Phrase, TICKS_PER_BEAT, BEATS_PER_BAR, BARS_PER_PHRASE

# MIDI channel per instrument layer (0-indexed, i.e. ch 1–3 in DAW)
LAYER_CHANNELS: dict[str, int] = {
    "kick":  0,
    "snare": 1,
    "hat":   2,
    "bass":  3,
    "stab":  4,
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
        self.last_send_ms: float = 0.0
        self.last_cleanup_ms: float = 0.0
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

    def send_cc(self, channel: int, cc_num: int, value: float) -> None:
        """Send a MIDI CC message. value in [0.0, 1.0] — scaled to 0–127."""
        if self._port_open:
            self._midiout.send_message([
                0xB0 | (channel & 0xF),
                cc_num & 0x7F,
                max(0, min(127, int(value * 127))),
            ])

    def play_bar_in_phrase_blocking(
        self,
        phrase: Phrase,
        bar_in_phrase: int,
        bpm: float,
        bank_start: float,
    ) -> float:
        """Play one bar from a phrase, blocking until the bar ends.

        bar_in_phrase: 0-indexed bar within the phrase (0..BARS_PER_PHRASE-1).
        bank_start:    perf_counter time the bank began.

        Returns the expected bar-end time (= bank_start + bar_end_tick * spt).
        """
        seconds_per_tick = 60.0 / (bpm * TICKS_PER_BEAT)
        ticks_per_bar    = TICKS_PER_BEAT * BEATS_PER_BAR

        abs_bar_idx    = phrase.phrase_index * BARS_PER_PHRASE + bar_in_phrase
        bar_start_tick = abs_bar_idx * ticks_per_bar
        bar_end_tick   = bar_start_tick + ticks_per_bar
        bar_end_s      = bar_end_tick * seconds_per_tick   # bar-relative end time

        timeline: list[tuple[float, str, int, int, int]] = []
        for event in phrase.events:
            if not getattr(event, "active", True) or event.velocity == 0:
                continue
            t_tick = event_to_abs_tick(event.time)
            if bar_start_tick <= t_tick < bar_end_tick:
                t_on  = t_tick * seconds_per_tick
                # Cap note-off at bar boundary so the function always returns on time.
                # Long-duration notes (bass, stabs) would otherwise sleep past bar_end_abs,
                # delaying the next bar's start and causing an audible stutter.
                t_off = min(t_on + event.duration, bar_end_s)
                ch    = LAYER_CHANNELS.get(event.layer, 0)
                timeline.append((t_on,  "on",  ch, event.note, event.velocity))
                timeline.append((t_off, "off", ch, event.note, 0))

        timeline.sort(key=lambda x: x[0])

        send_ms = 0.0
        for t_rel, action, ch, note, vel in timeline:
            target_time = bank_start + t_rel
            now = time.perf_counter()
            if target_time > now:
                time.sleep(target_time - now)
            t_send = time.perf_counter()
            if action == "on":
                self.send_note_on(ch, note, vel)
            else:
                self.send_note_off(ch, note)
            send_ms += (time.perf_counter() - t_send) * 1000
        self.last_send_ms = round(send_ms, 3)

        bar_end_abs = bank_start + bar_end_tick * seconds_per_tick
        remaining   = bar_end_abs - time.perf_counter()
        self.last_cleanup_ms = 0.0
        if remaining > 0:
            time.sleep(remaining)

        return bar_end_abs

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
            if not getattr(event, "active", True) or event.velocity == 0:
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

    def play_phrase_blocking(
        self,
        phrase: Phrase,
        bpm: float,
        bank_start: float,
    ) -> float:
        """Play one phrase from a pre-generated bank, blocking until the phrase ends.

        bank_start: perf_counter time the bank began — event times are absolute
        within the bank so we just offset from here.

        Returns the expected end time of this phrase (= bank_start + phrase_end_s).
        """
        seconds_per_tick = 60.0 / (bpm * TICKS_PER_BEAT)
        ticks_per_bar    = TICKS_PER_BEAT * BEATS_PER_BAR

        # Phrase spans BARS_PER_PHRASE bars; last bar index = phrase_bar_offset + BARS_PER_PHRASE
        phrase_end_tick = (phrase.phrase_index + 1) * BARS_PER_PHRASE * ticks_per_bar
        phrase_end_s    = phrase_end_tick * seconds_per_tick

        timeline: list[tuple[float, str, int, int, int]] = []
        for event in phrase.events:
            if not getattr(event, "active", True) or event.velocity == 0:
                continue
            t_on  = event_to_abs_tick(event.time) * seconds_per_tick
            t_off = t_on + event.duration
            ch    = LAYER_CHANNELS.get(event.layer, 0)
            timeline.append((t_on,  "on",  ch, event.note, event.velocity))
            timeline.append((t_off, "off", ch, event.note, 0))

        timeline.sort(key=lambda x: x[0])

        for t_rel, action, ch, note, vel in timeline:
            target = bank_start + t_rel
            now    = time.perf_counter()
            if target > now:
                time.sleep(target - now)
            if action == "on":
                self.send_note_on(ch, note, vel)
            else:
                self.send_note_off(ch, note)

        phrase_end_abs = bank_start + phrase_end_s
        remaining = phrase_end_abs - time.perf_counter()
        if remaining > 0:
            time.sleep(remaining)

        return phrase_end_abs

    def close(self) -> None:
        if self._port_open:
            self._midiout.close_port()
            self._port_open = False

    def __enter__(self) -> "MIDIOut":
        return self

    def __exit__(self, *_) -> None:
        self.close()
