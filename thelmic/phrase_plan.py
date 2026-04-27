"""Phrase planner foundation.

Phase 0 contract:
- build a visible, deterministic musical plan
- do not drive generators yet
- keep all existing playback behaviour unchanged
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


STEPS_PER_BAR = 16
DEFAULT_BARS = 8
ROOT_NOTE = 36
HOOK_ROOT = 60


class PhraseState(str, Enum):
    RESOLVED_STABLE = "RESOLVED_STABLE"
    CALL_UNRESOLVED = "CALL_UNRESOLVED"
    HOLD_SILENCE = "HOLD_SILENCE"
    RESPONSE_RESOLVED = "RESPONSE_RESOLVED"
    DROP_RELOCK = "DROP_RELOCK"


@dataclass(frozen=True)
class PlanNote:
    bar: int
    step: int
    pitch: int
    velocity: int = 96
    duration_steps: int = 1

    def to_dict(self) -> dict:
        return {
            "bar": self.bar,
            "step": self.step,
            "pitch": self.pitch,
            "velocity": self.velocity,
            "duration_steps": self.duration_steps,
        }


@dataclass(frozen=True)
class SilenceMask:
    muted_steps_by_bar: dict[int, tuple[int, ...]] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            str(bar): list(steps)
            for bar, steps in sorted(self.muted_steps_by_bar.items())
        }


@dataclass(frozen=True)
class PhrasePlan:
    bass_pattern: tuple[PlanNote, ...]
    hook_pattern: tuple[PlanNote, ...]
    phrase_state: dict[int, PhraseState]
    call_slots: dict[int, tuple[int, ...]]
    response_slots: dict[int, tuple[int, ...]]
    silence_mask: SilenceMask
    pressure_curve: dict[int, float]

    def to_dict(self) -> dict:
        return {
            "bass_pattern": [note.to_dict() for note in self.bass_pattern],
            "hook_pattern": [note.to_dict() for note in self.hook_pattern],
            "phrase_state": {
                str(bar): state.value
                for bar, state in sorted(self.phrase_state.items())
            },
            "call_slots": {
                str(bar): list(steps)
                for bar, steps in sorted(self.call_slots.items())
            },
            "response_slots": {
                str(bar): list(steps)
                for bar, steps in sorted(self.response_slots.items())
            },
            "silence_mask": self.silence_mask.to_dict(),
            "pressure_curve": {
                str(bar): round(value, 3)
                for bar, value in sorted(self.pressure_curve.items())
            },
        }


def _default_phrase_state(bars: int) -> dict[int, PhraseState]:
    template = {
        1: PhraseState.RESOLVED_STABLE,
        2: PhraseState.RESOLVED_STABLE,
        3: PhraseState.CALL_UNRESOLVED,
        4: PhraseState.CALL_UNRESOLVED,
        5: PhraseState.HOLD_SILENCE,
        6: PhraseState.RESPONSE_RESOLVED,
        7: PhraseState.RESPONSE_RESOLVED,
        8: PhraseState.DROP_RELOCK,
    }
    return {bar: template[((bar - 1) % DEFAULT_BARS) + 1] for bar in range(1, bars + 1)}


def _default_bass_pattern(bars: int) -> tuple[PlanNote, ...]:
    notes: list[PlanNote] = []
    for bar in range(1, bars + 1):
        notes.append(PlanNote(bar=bar, step=0, pitch=ROOT_NOTE, velocity=108))
        if bar % 2 == 1:
            notes.append(PlanNote(bar=bar, step=8, pitch=ROOT_NOTE, velocity=96))
    return tuple(notes)


def _default_hook_pattern(bars: int) -> tuple[PlanNote, ...]:
    motif = (
        (0, HOOK_ROOT),
        (3, HOOK_ROOT + 3),
        (6, HOOK_ROOT + 7),
        (10, HOOK_ROOT + 3),
    )
    return tuple(
        PlanNote(bar=bar, step=step, pitch=pitch, velocity=82, duration_steps=1)
        for bar in range(1, bars + 1)
        for step, pitch in motif
    )


def _default_call_slots(states: dict[int, PhraseState]) -> dict[int, tuple[int, ...]]:
    return {
        bar: (2, 6)
        for bar, state in states.items()
        if state == PhraseState.CALL_UNRESOLVED
    }


def _default_response_slots(states: dict[int, PhraseState]) -> dict[int, tuple[int, ...]]:
    return {
        bar: (10, 13, 14)
        for bar, state in states.items()
        if state == PhraseState.RESPONSE_RESOLVED
    }


def _default_silence_mask(states: dict[int, PhraseState]) -> SilenceMask:
    muted: dict[int, tuple[int, ...]] = {}
    for bar, state in states.items():
        if state == PhraseState.HOLD_SILENCE:
            muted[bar] = tuple(range(STEPS_PER_BAR))
        elif state == PhraseState.DROP_RELOCK:
            muted[bar] = tuple(range(0, 4))
        elif state == PhraseState.CALL_UNRESOLVED:
            muted[bar] = tuple(range(8, STEPS_PER_BAR))
    return SilenceMask(muted)


def _default_pressure_curve(bars: int) -> dict[int, float]:
    if bars <= 1:
        return {1: 1.0}
    return {
        bar: min(1.0, max(0.0, (bar - 1) / (bars - 1)))
        for bar in range(1, bars + 1)
    }


def generate_phrase_plan(bars: int = DEFAULT_BARS) -> PhrasePlan:
    """Return a deterministic planning scaffold for inspection."""
    bars = max(1, bars)
    states = _default_phrase_state(bars)
    return PhrasePlan(
        bass_pattern=_default_bass_pattern(bars),
        hook_pattern=_default_hook_pattern(bars),
        phrase_state=states,
        call_slots=_default_call_slots(states),
        response_slots=_default_response_slots(states),
        silence_mask=_default_silence_mask(states),
        pressure_curve=_default_pressure_curve(bars),
    )
