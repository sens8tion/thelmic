"""Thelmic v1.0 behaviour-neutral stream scheduler.

The stream engine owns canonical musical time and resolution mechanics. It
does not choose musical patterns. Musical decisions are made by the v1.0 note
generation chain before intents are handed to this scheduler.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable, Iterator, Optional, Sequence


VERSION = "v1.0"
STEPS_PER_BAR = 16


class PhraseRole(str, Enum):
    GROOVE = "groove"
    DROP_PREP = "drop_prep"
    DROP = "drop"


class SubphraseRole(str, Enum):
    STATEMENT = "statement"
    DEVELOPMENT = "development"
    GRID_REMINDER = "grid_reminder"
    RESET = "reset"


@dataclass(frozen=True)
class Tick:
    global_step: int
    time: float = 0.0


@dataclass(frozen=True)
class StructureProfile:
    phrase_length_bars: int = 16
    subphrase_length_bars: int = 4
    origin_step: int = 0

    def __post_init__(self) -> None:
        if self.phrase_length_bars <= 0:
            raise ValueError("phrase_length_bars must be positive")
        if self.subphrase_length_bars <= 0:
            raise ValueError("subphrase_length_bars must be positive")
        if self.phrase_length_bars % self.subphrase_length_bars:
            raise ValueError("phrase_length_bars must divide into subphrases")

    @property
    def phrase_length_steps(self) -> int:
        return self.phrase_length_bars * STEPS_PER_BAR

    @property
    def subphrase_length_steps(self) -> int:
        return self.subphrase_length_bars * STEPS_PER_BAR


@dataclass(frozen=True)
class StructureFrame:
    global_step: int
    time: float
    musical_step: int
    bar_index: int
    step_in_bar: int
    phrase_index: int
    step_in_phrase: int
    subphrase_index: int
    step_in_subphrase: int
    phrase_role: PhraseRole
    subphrase_role: SubphraseRole
    is_bar_start: bool
    is_phrase_start: bool
    is_subphrase_start: bool
    is_drop: bool
    is_drop_prep: bool
    grid_anchor_required: bool = True

    def to_dict(self) -> dict:
        return {
            "global_step": self.global_step,
            "time": self.time,
            "musical_step": self.musical_step,
            "bar_index": self.bar_index,
            "step_in_bar": self.step_in_bar,
            "phrase_index": self.phrase_index,
            "step_in_phrase": self.step_in_phrase,
            "subphrase_index": self.subphrase_index,
            "step_in_subphrase": self.step_in_subphrase,
            "phrase_role": self.phrase_role.value,
            "subphrase_role": self.subphrase_role.value,
            "is_bar_start": self.is_bar_start,
            "is_phrase_start": self.is_phrase_start,
            "is_subphrase_start": self.is_subphrase_start,
            "is_drop": self.is_drop,
            "is_drop_prep": self.is_drop_prep,
            "grid_anchor_required": self.grid_anchor_required,
        }


@dataclass(frozen=True)
class Intent:
    step: int
    instrument: str
    role: str
    velocity: Optional[int] = None
    duration: Optional[float] = None
    phrase_index: int = 0
    subphrase_index: int = 0
    priority: int = 0
    source: str = ""
    reason: str = ""
    intent_id: str = ""
    payload: dict = field(default_factory=dict)


@dataclass(frozen=True)
class ResolvedEvent:
    step: int
    instrument: str
    velocity: int
    duration: float
    origin_intent: Intent
    resolution_reason: str
    resolved_event_id: str


@dataclass(frozen=True)
class ResolveResult:
    events: tuple[ResolvedEvent, ...]


class StructureStream:
    def __init__(self, profile: StructureProfile | None = None) -> None:
        self.profile = profile or StructureProfile()

    def frames(self, ticks: Iterable[Tick]) -> Iterator[StructureFrame]:
        for tick in ticks:
            yield self.frame_for_tick(tick)

    def frame_for_tick(self, tick: Tick) -> StructureFrame:
        profile = self.profile
        musical_step = tick.global_step - profile.origin_step
        bar_zero = musical_step // STEPS_PER_BAR
        step_in_bar = musical_step % STEPS_PER_BAR
        phrase_index = musical_step // profile.phrase_length_steps
        step_in_phrase = musical_step % profile.phrase_length_steps
        subphrase_index = step_in_phrase // profile.subphrase_length_steps
        step_in_subphrase = step_in_phrase % profile.subphrase_length_steps
        is_phrase_start = step_in_phrase == 0
        is_drop = is_phrase_start
        drop_prep_start = profile.phrase_length_steps - STEPS_PER_BAR
        is_drop_prep = step_in_phrase >= drop_prep_start
        phrase_role = (
            PhraseRole.DROP if is_drop
            else PhraseRole.DROP_PREP if is_drop_prep
            else PhraseRole.GROOVE
        )
        subphrase_role = (
            SubphraseRole.RESET if is_drop
            else SubphraseRole.GRID_REMINDER if is_drop_prep
            else SubphraseRole.STATEMENT if subphrase_index == 0
            else SubphraseRole.DEVELOPMENT
        )
        return StructureFrame(
            global_step=tick.global_step,
            time=tick.time,
            musical_step=musical_step,
            bar_index=bar_zero + 1,
            step_in_bar=step_in_bar,
            phrase_index=phrase_index,
            step_in_phrase=step_in_phrase,
            subphrase_index=subphrase_index,
            step_in_subphrase=step_in_subphrase,
            phrase_role=phrase_role,
            subphrase_role=subphrase_role,
            is_bar_start=step_in_bar == 0,
            is_phrase_start=is_phrase_start,
            is_subphrase_start=step_in_subphrase == 0,
            is_drop=is_drop,
            is_drop_prep=is_drop_prep,
        )


class ResolveStream:
    """Resolve valid intents into events without rescue behaviour."""

    def resolve(self, frame: StructureFrame, intents: Sequence[Intent]) -> ResolveResult:
        events = tuple(
            ResolvedEvent(
                step=frame.global_step,
                instrument=intent.instrument,
                velocity=intent.velocity if intent.velocity is not None else 80,
                duration=intent.duration if intent.duration is not None else 0.08,
                origin_intent=intent,
                resolution_reason="resolved",
                resolved_event_id=f"resolved:{intent.intent_id}",
            )
            for intent in intents
        )
        return ResolveResult(events=events)
