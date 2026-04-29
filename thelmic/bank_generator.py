"""Bank generator — kick, snare, hi-hat.

With no deformations registered, the output is fully deterministic: the archetype
plays exactly as defined by its probability arrays (prob >= 0.5 fires, < 0.5 does not).
All variation — jitter, ghost injection, density fills, withheld resolutions — belongs
in deformations.py and is a no-op until algorithms are added there.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from thelmic.archetypes import Anchors, DrumBlend, select_archetype, to_blend
from thelmic.controls import Controls
from thelmic.deformations import apply_deformations
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
    velocity: int
    duration: float
    layer: str
    role: str              # anchor | ghost | impact
    emphasis: float
    openness: float
    expected_weight: float
    should_resolve: bool
    active: bool = True
    survives_silence: bool = False
    structural_authority: bool = True
    origin_source: str = ""
    origin_reason: str = ""
    resolution_reason: str = ""
    deformation: dict[str, float] = field(default_factory=dict)  # name→intensity 0→1


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

    Pipeline per bank:
      1. select_archetype(density, selected_archetype) → RhythmArchetype
      2. to_blend(archetype) → DrumBlend  (identity conversion)
      3. apply_deformations(blend, anchors, force, landscape_position) → DrumBlend
           (no-op until deformation algorithms are registered in deformations.py)
      4. Deterministic phrase/bar generation from the resulting DrumBlend

    Slot firing: prob >= 0.5 fires, < 0.5 does not. No RNG.
    All variation (jitter, ghost notes, density fills, etc.) lives in deformations.
    """

    def __init__(self, controls: Optional[Controls] = None, seed: Optional[int] = None) -> None:
        self.controls = controls or Controls()
        # seed retained for API compatibility; unused until deformations introduce RNG
        self.selected_archetype: Optional[str] = None

    def generate(
        self, force: ForceState, bank_index: int, landscape_position: float = 0.0,
        curve_overrides: dict[str, float] | None = None,
        active_archetype: Optional[str] = None,
        kick_authority: str = "legacy",
        hat_authority: str = "legacy",
    ) -> Bank:
        """Generate a Bank.

        active_archetype: when provided, bypasses density-based archetype
        selection and uses this name instead.  Used to lock archetype for
        the duration of a bank so within-bank regeneration (quantize
        boundaries) does not silently change the archetype mid-phrase.

        active_archetype = None  →  select from density as normal (bank start)
        active_archetype = name  →  use this name (within-bank regen / preview)
        """
        effective = ForceState(
            anticipation=force.anticipation,
            release_pressure=force.release_pressure,
            instability=_clamp(force.instability, hi=self.controls.chaos_limit),
            density=_clamp(force.density, hi=self.controls.density_ceiling),
            control_vs_chaos=force.control_vs_chaos,
        )

        # 1. Select archetype.
        #    During within-bank regeneration active_archetype is set so we never
        #    re-derive from density mid-phrase.  Only at bank start (active_archetype
        #    is None) do we allow the density to pick a new archetype.
        archetype = select_archetype(effective.density, active_archetype or self.selected_archetype)

        # 2. Extract anchor slots — passed to every deformation as a hard constraint
        anchors = Anchors(
            kick=archetype.kick_anchors,
            snare=archetype.snare_anchors,
            hat=archetype.hat_anchors,
        )

        # 3. Convert to blend and run deformation pipeline
        blend, named_maps = apply_deformations(
            to_blend(archetype), anchors, effective, landscape_position,
            curve_overrides=curve_overrides,
        )

        # Build per-layer named deform arrays: {name: [16 floats]} for each layer
        kick_deforms:  dict[str, list[float]] = {n: m.kick  for n, m in named_maps.items()}
        snare_deforms: dict[str, list[float]] = {n: m.snare for n, m in named_maps.items()}
        hat_deforms:   dict[str, list[float]] = {n: m.hat   for n, m in named_maps.items()}

        bank = Bank(bank_index=bank_index)
        for phrase_idx in range(PHRASES_PER_BANK):
            phrase = self._generate_phrase(
                effective, bank_index, phrase_idx, blend,
                kick_deforms, snare_deforms, hat_deforms,
                kick_authority=kick_authority,
                hat_authority=hat_authority,
            )
            bank.phrases.append(phrase)
        return bank

    # ------------------------------------------------------------------

    def _fired_slots(self, probs: list[float]) -> set[int]:
        """Deterministic: a slot fires if its probability is >= 0.5."""
        return {slot for slot, p in enumerate(probs) if p >= 0.5}

    def _generate_phrase(
        self,
        force: ForceState,
        bank_index: int,
        phrase_idx: int,
        blend: DrumBlend,
        kick_deforms:  dict[str, list[float]],
        snare_deforms: dict[str, list[float]],
        hat_deforms:   dict[str, list[float]],
        kick_authority: str = "legacy",
        hat_authority: str = "legacy",
    ) -> Phrase:
        phrase = Phrase(phrase_index=phrase_idx)
        bar_offset = phrase_idx * BARS_PER_PHRASE

        kick_fired  = self._fired_slots(blend.kick_probs)
        snare_fired = self._fired_slots(blend.snare_probs)
        hat_fired   = self._fired_slots(blend.hat_probs)

        for bar in range(BARS_PER_PHRASE):
            abs_bar = bar_offset + bar + 1
            if kick_authority != "stream":
                phrase.events.extend(self._generate_kick_bar(
                    force, abs_bar, bar, phrase_idx, kick_fired, blend.kick_exp, kick_deforms
                ))
            phrase.events.extend(self._generate_snare_bar(
                force, abs_bar, bar, phrase_idx, snare_fired, blend.snare_exp, snare_deforms
            ))
            if hat_authority != "stream":
                phrase.events.extend(self._generate_hat_bar(
                    force, abs_bar, hat_fired, blend.hat_exp, hat_deforms
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
        deform_by_name: dict[str, list[float]],
    ) -> list[MIDIEvent]:
        events: list[MIDIEvent] = []

        for slot in sorted(fired_slots):
            beat = slot // 4 + 1
            tick = (slot % 4) * SIXTEENTH
            exp = expectation[slot]
            role = self._assign_role(exp, force, phrase_idx)
            slot_deform = {n: slots[slot] for n, slots in deform_by_name.items() if slots[slot] > 0}

            events.append(MIDIEvent(
                time=f"{abs_bar}.{beat}.{tick}",
                note=KICK_NOTE,
                velocity=self._kick_velocity(force, role),
                duration=0.08,
                layer="kick",
                role=role,
                emphasis=self._emphasis(role),
                openness=1.0 - force.density * 0.3,
                expected_weight=exp,
                should_resolve=(
                    force.release_pressure > 0.6 and bar_in_phrase == BARS_PER_PHRASE - 1
                ),
                deformation=slot_deform,
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
        deform_by_name: dict[str, list[float]],
    ) -> list[MIDIEvent]:
        events: list[MIDIEvent] = []

        for slot in sorted(fired_slots):
            beat = slot // 4 + 1
            tick = (slot % 4) * SIXTEENTH
            exp = snare_exp[slot]
            role = self._assign_role(exp, force, phrase_idx)
            slot_deform = {n: slots[slot] for n, slots in deform_by_name.items() if slots[slot] > 0}
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
                deformation=slot_deform,
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
        deform_by_name: dict[str, list[float]],
    ) -> list[MIDIEvent]:
        events: list[MIDIEvent] = []

        for slot in sorted(fired_slots):
            beat = slot // 4 + 1
            tick = (slot % 4) * SIXTEENTH
            exp = hat_exp[slot]
            note = OPEN_HAT_NOTE if slot % 4 == 2 else CLOSED_HAT_NOTE
            role = "anchor" if exp >= 0.5 else "ghost"
            slot_deform = {n: slots[slot] for n, slots in deform_by_name.items() if slots[slot] > 0}
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
                deformation=slot_deform,
            ))

        return events

    # ------------------------------------------------------------------
    # Shared helpers

    def _assign_role(self, exp: float, force: ForceState, phrase_idx: int) -> str:
        """Deterministic role from expectation value and force state."""
        if exp >= EXPECTATION_ANCHOR_THRESHOLD:
            if force.release_pressure > 0.6 and phrase_idx == PHRASES_PER_BANK - 1:
                return "impact"
            return "anchor"
        if exp < EXPECTATION_GHOST_THRESHOLD:
            return "ghost"
        return "anchor"

    def _kick_velocity(self, force: ForceState, role: str) -> int:
        base = {"anchor": 100, "ghost": 52, "impact": 127}.get(role, 90)
        return max(1, min(127, int(base * (0.8 + force.density * 0.2))))

    def _snare_velocity(self, force: ForceState, role: str) -> int:
        base = {"anchor": 95, "ghost": 40, "impact": 120}.get(role, 80)
        return max(1, min(127, int(base * (0.8 + force.density * 0.2))))

    def _hat_velocity(self, force: ForceState, role: str) -> int:
        base = 72 if role == "anchor" else 38
        return max(1, min(127, int(base * (0.75 + force.density * 0.25))))

    def _emphasis(self, role: str) -> float:
        return {"anchor": 0.8, "ghost": 0.2, "impact": 1.0}.get(role, 0.6)
