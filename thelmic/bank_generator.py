"""Bank generator — Phase 1: kick, snare, hi-hat."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Optional

from thelmic.archetypes import DrumBlend, select_blend
from thelmic.controls import Controls
from thelmic.force_engine import ForceState, _clamp

BARS_PER_PHRASE = 4
PHRASES_PER_BANK = 4
TICKS_PER_BEAT = 24
BEATS_PER_BAR = 4
SIXTEENTH = TICKS_PER_BEAT // 4   # 6 ticks per 16th note

KICK_NOTE        = 36   # GM kick
SNARE_NOTE       = 38   # GM acoustic snare
CLOSED_HAT_NOTE  = 42   # GM closed hi-hat
OPEN_HAT_NOTE    = 46   # GM open hi-hat  (slot%4 == 2 → open)

# Expectation threshold above which a slot is considered "strongly expected"
EXPECTATION_ANCHOR_THRESHOLD = 0.7
EXPECTATION_GHOST_THRESHOLD  = 0.25


@dataclass
class MIDIEvent:
    time: str              # "bar.beat.tick" — bar is 1-indexed within bank
    note: int
    velocity: int          # 0 = withheld (display only, no MIDI output)
    duration: float
    layer: str
    role: str              # anchor | ghost | disruption | impact | withheld_resolution
    emphasis: float
    openness: float
    expected_weight: float
    should_resolve: bool


@dataclass
class Phrase:
    phrase_index: int
    events: list[MIDIEvent] = field(default_factory=list)


@dataclass
class Bank:
    bank_index: int
    phrases: list[Phrase] = field(default_factory=list)

    def all_events(self) -> list[MIDIEvent]:
        return [e for p in self.phrases for e in p.events]


class BankGenerator:
    """Generates a Bank from a ForceState and Controls.

    Instruments: kick, snare, hi-hat. Each is generated independently from
    the same archetype blend — no inter-instrument role logic yet (Phase 3).

    Kick placement is driven by archetype probability distributions (archetypes.py).
    Snare and hat follow their own per-archetype distributions. The expectation map
    drives role assignment for all three layers.
    """

    def __init__(self, controls: Optional[Controls] = None, seed: Optional[int] = None) -> None:
        self.controls = controls or Controls()
        self._rng = random.Random(seed)
        self.locked_archetype: Optional[str] = None

    def generate(
        self, force: ForceState, bank_index: int, landscape_position: float = 0.0
    ) -> Bank:
        effective = ForceState(
            anticipation=force.anticipation,
            release_pressure=force.release_pressure,
            instability=_clamp(force.instability, hi=self.controls.chaos_limit),
            density=_clamp(force.density, hi=self.controls.density_ceiling),
            control_vs_chaos=force.control_vs_chaos,
        )

        # Select archetype blend once per bank so all phrases share the same feel
        blend = select_blend(
            density=effective.density,
            instability=effective.instability,
            landscape_position=landscape_position,
            locked_archetype=self.locked_archetype,
        )

        bank = Bank(bank_index=bank_index)
        for phrase_idx in range(PHRASES_PER_BANK):
            phrase = self._generate_phrase(
                effective, bank_index, phrase_idx, blend
            )
            bank.phrases.append(phrase)
        return bank

    # ------------------------------------------------------------------

    def _roll_slots(self, probs: list[float], density_scale: float) -> set[int]:
        """Decide which of the 16 slots fire. Called once per phrase per instrument."""
        return {
            slot for slot in range(16)
            if self._should_fire(probs[slot], density_scale)
        }

    def _generate_phrase(
        self,
        force: ForceState,
        bank_index: int,
        phrase_idx: int,
        blend: DrumBlend,
    ) -> Phrase:
        phrase = Phrase(phrase_index=phrase_idx)
        bar_offset = phrase_idx * BARS_PER_PHRASE

        # Roll fired slots once — all 4 bars in the phrase share the same pattern
        kick_fired  = self._roll_slots(blend.kick_probs,  0.5 + force.density * 0.5)
        snare_fired = self._roll_slots(blend.snare_probs, 0.4 + force.density * 0.6)
        hat_fired   = self._roll_slots(blend.hat_probs,   0.35 + force.density * 0.5)

        for bar in range(BARS_PER_PHRASE):
            abs_bar = bar_offset + bar + 1
            phrase.events.extend(self._generate_kick_bar(
                force, abs_bar, bar, phrase_idx, kick_fired, blend.kick_exp
            ))
            phrase.events.extend(self._generate_snare_bar(
                force, abs_bar, bar, phrase_idx, snare_fired, blend.snare_exp
            ))
            phrase.events.extend(self._generate_hat_bar(
                force, abs_bar, hat_fired, blend.hat_exp
            ))
        return phrase

    # ------------------------------------------------------------------
    # Kick

    def _generate_kick_bar(
        self,
        force: ForceState,
        abs_bar: int,
        bar_in_phrase: int,
        phrase_idx: int,
        fired_slots: set[int],
        expectation: list[float],
    ) -> list[MIDIEvent]:
        events: list[MIDIEvent] = []
        groove = self.controls.groove_lock * (1.0 - force.instability * 0.4)

        for slot in sorted(fired_slots):
            beat = slot // 4 + 1
            sub  = slot % 4
            tick = sub * SIXTEENTH

            if not self.locked_archetype and groove < 0.9 and slot % 4 != 0:
                jitter_range = int((1.0 - groove) * 3)
                tick = max(0, tick + self._rng.randint(-jitter_range, jitter_range))

            time_str = f"{abs_bar}.{beat}.{tick}"
            exp = expectation[slot]
            role = self._assign_role(exp, force, slot, bar_in_phrase, phrase_idx)
            velocity = self._kick_velocity(force, role)

            events.append(MIDIEvent(
                time=time_str,
                note=KICK_NOTE,
                velocity=velocity,
                duration=0.08,
                layer="kick",
                role=role,
                emphasis=self._emphasis(role),
                openness=1.0 - force.density * 0.3,
                expected_weight=exp,
                should_resolve=(
                    force.release_pressure > 0.6 and bar_in_phrase == BARS_PER_PHRASE - 1
                ),
            ))

        # Withheld resolutions — high-expectation slots deliberately left empty
        if force.anticipation > 0.55 and bar_in_phrase == BARS_PER_PHRASE - 1:
            for slot in range(16):
                if slot in fired_slots:
                    continue
                exp = expectation[slot]
                if exp >= EXPECTATION_ANCHOR_THRESHOLD:
                    if self._rng.random() < force.anticipation * 0.5:
                        beat = slot // 4 + 1
                        tick = (slot % 4) * SIXTEENTH
                        events.append(MIDIEvent(
                            time=f"{abs_bar}.{beat}.{tick}",
                            note=KICK_NOTE,
                            velocity=0,
                            duration=0.0,
                            layer="kick",
                            role="withheld_resolution",
                            emphasis=0.3,
                            openness=1.0,
                            expected_weight=exp,
                            should_resolve=True,
                        ))

        return events

    # ------------------------------------------------------------------
    # Snare

    def _generate_snare_bar(
        self,
        force: ForceState,
        abs_bar: int,
        bar_in_phrase: int,
        phrase_idx: int,
        fired_slots: set[int],
        snare_exp: list[float],
    ) -> list[MIDIEvent]:
        events: list[MIDIEvent] = []

        for slot in sorted(fired_slots):
            beat = slot // 4 + 1
            tick = (slot % 4) * SIXTEENTH
            exp = snare_exp[slot]
            role = self._assign_role(exp, force, slot, bar_in_phrase, phrase_idx)
            events.append(MIDIEvent(
                time=f"{abs_bar}.{beat}.{tick}",
                note=SNARE_NOTE,
                velocity=self._snare_velocity(force, role),
                duration=0.05,
                layer="snare",
                role=role,
                emphasis=self._emphasis(role),
                openness=1.0 - force.density * 0.2,
                expected_weight=exp,
                should_resolve=False,
            ))

        return events

    # ------------------------------------------------------------------
    # Hi-hat

    def _generate_hat_bar(
        self,
        force: ForceState,
        abs_bar: int,
        fired_slots: set[int],
        hat_exp: list[float],
    ) -> list[MIDIEvent]:
        events: list[MIDIEvent] = []

        for slot in sorted(fired_slots):
            beat = slot // 4 + 1
            tick = (slot % 4) * SIXTEENTH
            exp = hat_exp[slot]
            note = OPEN_HAT_NOTE if slot % 4 == 2 else CLOSED_HAT_NOTE
            role = "anchor" if exp >= 0.5 else "ghost"
            events.append(MIDIEvent(
                time=f"{abs_bar}.{beat}.{tick}",
                note=note,
                velocity=self._hat_velocity(force, role),
                duration=0.03 if note == CLOSED_HAT_NOTE else 0.06,
                layer="hat",
                role=role,
                emphasis=self._emphasis(role),
                openness=1.0,
                expected_weight=exp,
                should_resolve=False,
            ))

        return events

    # ------------------------------------------------------------------
    # Shared helpers

    def _should_fire(self, prob: float, density_scale: float) -> bool:
        """Deterministic when locked (prob >= 0.5); probabilistic otherwise."""
        if self.locked_archetype:
            return prob >= 0.5
        return self._rng.random() < prob * density_scale

    def _assign_role(
        self,
        exp: float,
        force: ForceState,
        slot: int,
        bar_in_phrase: int,
        phrase_idx: int,
    ) -> str:
        if exp >= EXPECTATION_ANCHOR_THRESHOLD:
            if force.release_pressure > 0.6 and phrase_idx == PHRASES_PER_BANK - 1:
                return "impact"
            return "anchor"

        if exp < EXPECTATION_GHOST_THRESHOLD and force.instability > 0.4:
            if self._rng.random() < force.instability * 0.55:
                return "disruption"

        if exp < EXPECTATION_GHOST_THRESHOLD:
            return "ghost"

        return "anchor"

    def _kick_velocity(self, force: ForceState, role: str) -> int:
        base = {
            "anchor":              100,
            "ghost":               52,
            "disruption":          112,
            "impact":              127,
            "withheld_resolution": 0,
        }.get(role, 90)
        if base == 0:
            return 0
        vel = int(base * (0.8 + force.density * 0.2))
        return max(1, min(127, vel))

    def _snare_velocity(self, force: ForceState, role: str) -> int:
        base = {
            "anchor":     95,
            "ghost":      40,
            "disruption": 108,
            "impact":     120,
        }.get(role, 80)
        vel = int(base * (0.8 + force.density * 0.2))
        return max(1, min(127, vel))

    def _hat_velocity(self, force: ForceState, role: str) -> int:
        base = 72 if role == "anchor" else 38
        vel = int(base * (0.75 + force.density * 0.25))
        return max(1, min(127, vel))

    def _emphasis(self, role: str) -> float:
        return {
            "anchor":              0.8,
            "ghost":               0.2,
            "disruption":          0.9,
            "impact":              1.0,
            "withheld_resolution": 0.3,
        }.get(role, 0.6)
