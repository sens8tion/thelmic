"""Step-wise stream-processing spine.

This module is intentionally parallel to the existing sequencer.  It provides
the new canonical musical timeline without changing legacy generation yet.

TransportClock -> TickStream -> StructureStream -> Intent/Transform/Resolve/Event

Only StructureStream may calculate bar, phrase, sub-phrase, drop, relock, and
pressure-position fields.  Downstream streams consume StructureFrame instances.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Iterable, Iterator, Optional, Sequence


STEPS_PER_BAR = 16


class PhraseRole(str, Enum):
    INTRO = "intro"
    GROOVE = "groove"
    HOOK = "hook"
    CALL = "call"
    RESPONSE = "response"
    BUILD = "build"
    PRE_DROP = "pre_drop"
    DROP = "drop"
    RECOVERY = "recovery"
    TRANSITION = "transition"


class SubphraseRole(str, Enum):
    SETUP = "setup"
    STATEMENT = "statement"
    ANSWER = "answer"
    WITHHOLDING = "withholding"
    TRANSFORMATION = "transformation"
    RELEASE = "release"
    RESET = "reset"


@dataclass(frozen=True)
class Tick:
    global_step: int
    time: float


@dataclass(frozen=True)
class StructureProfile:
    """Deterministic structure settings for StructureStream.

    relock_offset_steps maps legacy/relock placement into canonical musical
    time.  For example, if a relock hit occurs four global steps after the
    visual bar boundary, relock_offset_steps=4 makes that hit musical step 0
    of a canonical bar.
    """

    phrase_length_bars: int = 16
    subphrase_length_bars: int = 8
    origin_step: int = 0
    relock_offset_steps: int = 0
    phrase_roles: tuple[PhraseRole, ...] = (
        PhraseRole.GROOVE,
        PhraseRole.HOOK,
        PhraseRole.CALL,
        PhraseRole.RESPONSE,
        PhraseRole.BUILD,
        PhraseRole.PRE_DROP,
        PhraseRole.DROP,
        PhraseRole.RECOVERY,
        PhraseRole.TRANSITION,
    )
    subphrase_roles: tuple[SubphraseRole, ...] = (
        SubphraseRole.SETUP,
        SubphraseRole.STATEMENT,
        SubphraseRole.ANSWER,
        SubphraseRole.WITHHOLDING,
        SubphraseRole.TRANSFORMATION,
        SubphraseRole.RELEASE,
        SubphraseRole.RESET,
    )

    def __post_init__(self) -> None:
        if self.phrase_length_bars <= 0:
            raise ValueError("phrase_length_bars must be positive")
        if self.subphrase_length_bars <= 0:
            raise ValueError("subphrase_length_bars must be positive")
        if self.phrase_length_bars % self.subphrase_length_bars != 0:
            raise ValueError("phrase_length_bars must divide into subphrases")
        if self.phrase_length_bars % 4 != 0:
            raise ValueError("phrase_length_bars must align to 4-bar boundaries")
        if self.subphrase_length_bars not in (4, 8, 16):
            raise ValueError("subphrase_length_bars must be 4, 8, or 16")
        if self.relock_offset_steps < 0:
            raise ValueError("relock_offset_steps must be non-negative")
        if self.origin_step < 0:
            raise ValueError("origin_step must be non-negative")
        if not self.phrase_roles:
            raise ValueError("at least one phrase role is required")
        if not self.subphrase_roles:
            raise ValueError("at least one subphrase role is required")

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
    is_relock: bool
    pressure: float
    impact: float
    density: float
    silence: float

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
            "is_relock": self.is_relock,
            "pressure": round(self.pressure, 3),
            "impact": round(self.impact, 3),
            "density": round(self.density, 3),
            "silence": round(self.silence, 3),
        }


@dataclass(frozen=True)
class ControlFrame:
    landscape_position: float = 0.0
    archetype: str = "oak"
    transport_running: bool = False
    lookahead_steps: int = 0


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


@dataclass(frozen=True)
class ResolvedEvent:
    step: int
    instrument: str
    velocity: int
    duration: float
    origin_intent: Intent
    resolution_reason: str


@dataclass(frozen=True)
class SuppressionEvent:
    step: int
    instrument: str
    origin_intent: Intent
    reason: str


@dataclass(frozen=True)
class ResolveResult:
    events: tuple[ResolvedEvent, ...] = field(default_factory=tuple)
    suppressions: tuple[SuppressionEvent, ...] = field(default_factory=tuple)


class TransportClock:
    """Produces canonical global ticks at step resolution."""

    def __init__(self, *, bpm: float = 174.0, steps_per_bar: int = STEPS_PER_BAR) -> None:
        if bpm <= 0:
            raise ValueError("bpm must be positive")
        if steps_per_bar <= 0:
            raise ValueError("steps_per_bar must be positive")
        self.bpm = bpm
        self.steps_per_bar = steps_per_bar

    @property
    def seconds_per_step(self) -> float:
        beats_per_bar = 4
        return (60.0 / self.bpm) * beats_per_bar / self.steps_per_bar

    def ticks(self, *, start_step: int = 0, count: Optional[int] = None) -> Iterator[Tick]:
        if start_step < 0:
            raise ValueError("start_step must be non-negative")
        emitted = 0
        step = start_step
        while count is None or emitted < count:
            yield Tick(global_step=step, time=step * self.seconds_per_step)
            step += 1
            emitted += 1


class StructureStream:
    """Canonical structure authority.

    No downstream component should calculate bar, phrase, sub-phrase, drop, or
    relock fields.  They receive these fields through StructureFrame.
    """

    def __init__(self, profile: StructureProfile | None = None) -> None:
        self.profile = profile or StructureProfile()

    def frames(self, ticks: Iterable[Tick]) -> Iterator[StructureFrame]:
        for tick in ticks:
            yield self.frame_for_tick(tick)

    def frame_for_tick(self, tick: Tick) -> StructureFrame:
        profile = self.profile
        musical_step = tick.global_step - profile.origin_step - profile.relock_offset_steps
        bar_index = _floor_div(musical_step, STEPS_PER_BAR)
        step_in_bar = musical_step - bar_index * STEPS_PER_BAR
        phrase_index = _floor_div(musical_step, profile.phrase_length_steps)
        step_in_phrase = musical_step - phrase_index * profile.phrase_length_steps
        subphrase_index = step_in_phrase // profile.subphrase_length_steps
        step_in_subphrase = step_in_phrase - subphrase_index * profile.subphrase_length_steps
        phrase_role = profile.phrase_roles[phrase_index % len(profile.phrase_roles)]
        subphrase_role = profile.subphrase_roles[
            subphrase_index % len(profile.subphrase_roles)
        ]
        is_bar_start = step_in_bar == 0
        is_phrase_start = step_in_phrase == 0
        is_subphrase_start = step_in_subphrase == 0
        pressure, impact, density, silence = _macro_values(
            step_in_phrase,
            profile.phrase_length_steps,
        )
        return StructureFrame(
            global_step=tick.global_step,
            time=tick.time,
            musical_step=musical_step,
            bar_index=bar_index + 1,
            step_in_bar=step_in_bar,
            phrase_index=phrase_index,
            step_in_phrase=step_in_phrase,
            subphrase_index=subphrase_index,
            step_in_subphrase=step_in_subphrase,
            phrase_role=phrase_role,
            subphrase_role=subphrase_role,
            is_bar_start=is_bar_start,
            is_phrase_start=is_phrase_start,
            is_subphrase_start=is_subphrase_start,
            is_drop=is_phrase_start,
            is_relock=is_phrase_start,
            pressure=pressure,
            impact=impact,
            density=density,
            silence=silence,
        )


class IntentStream:
    """Base class for voice intent generators.

    Subclasses consume StructureFrame and emit Intent.  They must not calculate
    phrase or bar positions and must not produce final MIDI events.
    """

    source = "intent"

    def intents(self, frames: Iterable[StructureFrame]) -> Iterator[Intent]:
        for frame in frames:
            yield from self.intents_for_frame(frame)

    def intents_for_frame(self, frame: StructureFrame) -> tuple[Intent, ...]:
        return ()


class TransformStream:
    """Transforms intents without resolving conflicts."""

    def transform(
        self,
        frame: StructureFrame,
        intents: Sequence[Intent],
    ) -> tuple[Intent, ...]:
        return tuple(intents)


class ResolveStream:
    """Central authority for permission, silence, priority, and collisions."""

    def resolve(
        self,
        frame: StructureFrame,
        intents: Sequence[Intent],
    ) -> ResolveResult:
        kept: dict[str, Intent] = {}
        suppressions: list[SuppressionEvent] = []
        for intent in intents:
            if frame.silence >= 1.0 and intent.role != "survivor":
                suppressions.append(
                    SuppressionEvent(
                        step=frame.global_step,
                        instrument=intent.instrument,
                        origin_intent=intent,
                        reason="silence",
                    )
                )
                continue
            current = kept.get(intent.instrument)
            if current is not None and current.priority >= intent.priority:
                suppressions.append(
                    SuppressionEvent(
                        step=frame.global_step,
                        instrument=intent.instrument,
                        origin_intent=intent,
                        reason="priority_collision",
                    )
                )
                continue
            if current is not None:
                suppressions.append(
                    SuppressionEvent(
                        step=frame.global_step,
                        instrument=current.instrument,
                        origin_intent=current,
                        reason="priority_replaced",
                    )
                )
            kept[intent.instrument] = intent
        events = tuple(
            ResolvedEvent(
                step=frame.global_step,
                instrument=intent.instrument,
                velocity=intent.velocity if intent.velocity is not None else 80,
                duration=intent.duration if intent.duration is not None else 0.08,
                origin_intent=intent,
                resolution_reason="resolved",
            )
            for intent in kept.values()
        )
        return ResolveResult(events=events, suppressions=tuple(suppressions))


class EventStream:
    """Final stream of resolved musical events."""

    def __init__(
        self,
        intent_streams: Sequence[IntentStream],
        *,
        transform_stream: TransformStream | None = None,
        resolve_stream: ResolveStream | None = None,
    ) -> None:
        self.intent_streams = tuple(intent_streams)
        self.transform_stream = transform_stream or TransformStream()
        self.resolve_stream = resolve_stream or ResolveStream()

    def events(self, frames: Iterable[StructureFrame]) -> Iterator[ResolvedEvent]:
        for frame in frames:
            intents: list[Intent] = []
            for stream in self.intent_streams:
                intents.extend(stream.intents_for_frame(frame))
            transformed = self.transform_stream.transform(frame, intents)
            result = self.resolve_stream.resolve(frame, transformed)
            yield from result.events


def enrich_with_control(frame: StructureFrame, control: ControlFrame) -> StructureFrame:
    """Return a frame enriched by external control without changing time fields."""

    density = _clamp(frame.density * (0.75 + control.landscape_position * 0.5))
    return replace(frame, density=density)


def _macro_values(step_in_phrase: int, phrase_length_steps: int) -> tuple[float, float, float, float]:
    progress = 0.0 if phrase_length_steps <= 1 else step_in_phrase / (phrase_length_steps - 1)
    pressure = progress
    impact = 1.0 if step_in_phrase == 0 else 0.0
    density = _clamp(0.35 + 0.45 * min(progress, 1.0 - max(0.0, progress - 0.75) * 2.0))
    silence = _clamp((progress - 0.875) / 0.125) if progress >= 0.875 else 0.0
    return pressure, impact, density, silence


def _floor_div(value: int, divisor: int) -> int:
    return value // divisor


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))
