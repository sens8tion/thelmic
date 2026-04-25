"""Bank generator — Phase 1: kick only."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Optional

from thelmic.controls import Controls
from thelmic.force_engine import ForceState, _clamp

BARS_PER_PHRASE = 4
PHRASES_PER_BANK = 4
TICKS_PER_BEAT = 24   # MIDI standard
BEATS_PER_BAR = 4

KICK_NOTE = 36        # GM kick


@dataclass
class MIDIEvent:
    time: str              # "bar.beat.tick" (1-indexed bar within bank)
    note: int
    velocity: int
    duration: float        # seconds
    layer: str
    role: str              # anchor | ghost | disruption | impact | withheld_resolution
    emphasis: float
    openness: float
    expected_weight: float
    should_resolve: bool


@dataclass
class Phrase:
    phrase_index: int      # 0–3 within bank
    events: list[MIDIEvent] = field(default_factory=list)


@dataclass
class Bank:
    bank_index: int
    phrases: list[Phrase] = field(default_factory=list)

    def all_events(self) -> list[MIDIEvent]:
        return [e for p in self.phrases for e in p.events]


class BankGenerator:
    """Generates a Bank from a ForceState and Controls.

    Phase 1: kick drum only.
    """

    def __init__(self, controls: Optional[Controls] = None, seed: Optional[int] = None) -> None:
        self.controls = controls or Controls()
        self._rng = random.Random(seed)

    def generate(self, force: ForceState, bank_index: int) -> Bank:
        # Apply control ceilings before generation
        effective = ForceState(
            anticipation=force.anticipation,
            release_pressure=force.release_pressure,
            instability=_clamp(force.instability, hi=self.controls.chaos_limit),
            density=_clamp(force.density, hi=self.controls.density_ceiling),
            control_vs_chaos=force.control_vs_chaos,
        )

        bank = Bank(bank_index=bank_index)
        for phrase_idx in range(PHRASES_PER_BANK):
            phrase = self._generate_phrase(effective, bank_index, phrase_idx)
            bank.phrases.append(phrase)
        return bank

    def _generate_phrase(
        self, force: ForceState, bank_index: int, phrase_idx: int
    ) -> Phrase:
        phrase = Phrase(phrase_index=phrase_idx)
        bar_offset = phrase_idx * BARS_PER_PHRASE  # bars are 1-indexed in the bank

        for bar in range(BARS_PER_PHRASE):
            abs_bar = bar_offset + bar + 1  # 1-indexed
            events = self._generate_kick_bar(force, abs_bar, bar, phrase_idx)
            phrase.events.extend(events)
        return phrase

    def _generate_kick_bar(
        self, force: ForceState, abs_bar: int, bar_in_phrase: int, phrase_idx: int
    ) -> list[MIDIEvent]:
        events: list[MIDIEvent] = []

        # Density drives how many kick hits per bar (base range: 2–8 per bar at 4/4)
        base_hits = 2 + int(force.density * 6)
        # Instability allows deviation from grid
        groove = self.controls.groove_lock * (1.0 - force.instability * 0.4)

        # Generate candidate beat positions (quantised to 16th notes = beat * 6 ticks)
        sixteenth = TICKS_PER_BEAT // 4   # 6 ticks per 16th note
        grid_positions = [b * sixteenth for b in range(BEATS_PER_BAR * 4)]  # 16 slots

        chosen = self._rng.sample(grid_positions, min(base_hits, len(grid_positions)))
        chosen.sort()

        for tick_pos in chosen:
            beat = tick_pos // TICKS_PER_BEAT + 1
            tick = tick_pos % TICKS_PER_BEAT

            # Jitter if groove is loose
            if groove < 0.9:
                jitter_range = int((1.0 - groove) * 4)
                tick = max(0, tick + self._rng.randint(-jitter_range, jitter_range))

            time_str = f"{abs_bar}.{beat}.{tick}"

            # Assign role
            role = self._assign_role(force, beat, bar_in_phrase, phrase_idx)

            # Velocity shaped by role and force
            velocity = self._velocity(force, role)

            events.append(MIDIEvent(
                time=time_str,
                note=KICK_NOTE,
                velocity=velocity,
                duration=0.1,
                layer="kick",
                role=role,
                emphasis=self._emphasis(force, role),
                openness=1.0 - force.density * 0.3,
                expected_weight=1.0 if beat == 1 else 0.5,
                should_resolve=(force.release_pressure > 0.6 and bar_in_phrase == 3),
            ))

        return events

    def _assign_role(
        self, force: ForceState, beat: int, bar_in_phrase: int, phrase_idx: int
    ) -> str:
        # Beat 1 of bar 1 of a phrase is always an anchor
        if beat == 1 and bar_in_phrase == 0:
            return "anchor"

        # High anticipation + last bar of phrase → withheld_resolution
        if force.anticipation > 0.65 and bar_in_phrase == BARS_PER_PHRASE - 1:
            if self._rng.random() < force.anticipation * 0.4:
                return "withheld_resolution"

        # Instability drives disruptions
        if force.instability > 0.5:
            if self._rng.random() < force.instability * 0.3:
                return "disruption"

        # High release + last phrase → impact
        if force.release_pressure > 0.6 and phrase_idx == PHRASES_PER_BANK - 1:
            if beat in (1, 3):
                return "impact"

        # Default
        if self._rng.random() < 0.25:
            return "ghost"
        return "anchor"

    def _velocity(self, force: ForceState, role: str) -> int:
        base = {
            "anchor": 100,
            "ghost": 55,
            "disruption": 110,
            "impact": 127,
            "withheld_resolution": 40,
        }.get(role, 90)
        # Scale slightly by density
        vel = int(base * (0.8 + force.density * 0.2))
        return max(1, min(127, vel))

    def _emphasis(self, force: ForceState, role: str) -> float:
        return {
            "anchor": 0.8,
            "ghost": 0.2,
            "disruption": 0.9,
            "impact": 1.0,
            "withheld_resolution": 0.3,
        }.get(role, 0.6)
