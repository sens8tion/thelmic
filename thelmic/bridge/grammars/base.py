"""Grammar protocol + Section / Fragment / Transition primitives.

A `Section` is a duration-bounded block of a piece. A `Fragment` is a
unit of content within a section (a drum pattern, a chord progression,
a vocal line, a texture). A `Grammar` describes the shape of a whole
piece: which sections occur, in what order, with what transitions.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Protocol, Optional, Any, Callable


@dataclass
class Fragment:
    """One content layer within a section."""
    role: str                   # "drum_pattern", "harmony", "lead", "texture", "vocal"
    generator: str              # registered generator name (resolved by pack)
    params: dict = field(default_factory=dict)
    track_role: Optional[str] = None    # which track-role this fragment targets


@dataclass
class TransitionSpec:
    """How to move between two sections."""
    type: str = "cut"           # "cut" | "fade" | "drop" | "halt" | "modulate" | "phase"
    pre_window_beats: float = 0.0
    post_window_beats: float = 0.0
    silence_beats: float = 0.0
    tempo_target: Optional[float] = None    # ramp tempo to this BPM during transition
    extras: dict = field(default_factory=dict)


@dataclass
class AnticipationSpec:
    """Pre-section anticipation pattern. Different grammars handle this very differently."""
    enabled: bool = False
    pattern: str = "none"       # "tightening_hats" | "snare_roll" | "filter_open" | "drone_swell" | ...
    duration_beats: float = 0.0
    intensity_curve: str = "linear"   # "linear" | "exp" | "log"
    extras: dict = field(default_factory=dict)


@dataclass
class Section:
    """A duration-bounded block of music."""
    role: str                   # "intro", "verse", "drop", "drone", "exposition", ...
    duration_bars: float
    fragments: list[Fragment] = field(default_factory=list)
    transition_in:  TransitionSpec = field(default_factory=TransitionSpec)
    transition_out: TransitionSpec = field(default_factory=TransitionSpec)
    anticipation: AnticipationSpec = field(default_factory=AnticipationSpec)
    tempo_bpm: Optional[float] = None
    meter: tuple[int, int] = (4, 4)
    metadata: dict = field(default_factory=dict)


class Grammar(Protocol):
    """A musical-form grammar.

    Aesthetic packs reference a grammar by name; the timeline engine
    consults `transition_between` and `anticipation_for` when walking
    a Section list.
    """
    name: str
    section_palette: list[str]            # which section roles this grammar uses

    def transition_between(self, prev: Section, nxt: Section) -> TransitionSpec:
        """How to transition from prev → nxt."""
        ...

    def anticipation_for(self, section: Section,
                          previous: Optional[Section] = None) -> AnticipationSpec:
        """What anticipation pattern (if any) should precede this section."""
        ...

    def supports_role(self, role: str) -> bool:
        """Does this grammar admit a section of this role?"""
        return role in self.section_palette
