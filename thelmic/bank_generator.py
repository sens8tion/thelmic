"""Behaviour-transparent event model for Thelmic v1.0.

This module intentionally contains data structures and timing constants only.
The v0.9 ``BankGenerator`` entrypoint is disabled; musical behaviour belongs
inside the versioned v1.0 note generation chain.
"""

from __future__ import annotations

from dataclasses import dataclass, field


BARS_PER_PHRASE = 4
PHRASES_PER_BANK = 4
TICKS_PER_BEAT = 24
BEATS_PER_BAR = 4
SIXTEENTH = TICKS_PER_BEAT // 4

KICK_NOTE = 36
SNARE_NOTE = 38
CLOSED_HAT_NOTE = 42
OPEN_HAT_NOTE = 46


@dataclass
class MIDIEvent:
    time: str
    note: int
    velocity: int
    duration: float
    layer: str
    role: str
    emphasis: float
    openness: float
    expected_weight: float
    should_resolve: bool
    active: bool = True
    structural_authority: bool = True
    origin_source: str = ""
    origin_reason: str = ""
    resolution_reason: str = ""
    source: str = ""
    reason: str = ""
    intent_id: str = ""
    resolved_event_id: str = ""
    global_step: int = -1
    musical_step: int = -1
    phrase_index: int = -1
    bar_index: int = -1


@dataclass
class Phrase:
    phrase_index: int
    events: list[MIDIEvent] = field(default_factory=list)


@dataclass
class Bank:
    bank_index: int
    phrases: list[Phrase] = field(default_factory=list)

    def all_events(self) -> list[MIDIEvent]:
        return [event for phrase in self.phrases for event in phrase.events]


class BankGenerator:
    """Disabled v0.9 entrypoint."""

    def __init__(self, *_, **__) -> None:
        pass

    def generate(self, *_, **__) -> Bank:
        raise RuntimeError("v0.9 engine disabled - use Thelmic v1.0 path")
