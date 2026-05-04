"""Chord — a set of pitches relative to a root.

Provides ergonomic constructors (minor_triad, dom7, sus2, cluster, ...)
and arithmetic (transpose, invert).
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Sequence


@dataclass(frozen=True)
class Chord:
    name: str
    intervals: tuple[int, ...]   # semitones above root
    root: int = 0                 # MIDI pitch of the root

    @classmethod
    def minor_triad(cls, root: int = 0) -> "Chord":
        return cls("min", (0, 3, 7), root)

    @classmethod
    def major_triad(cls, root: int = 0) -> "Chord":
        return cls("maj", (0, 4, 7), root)

    @classmethod
    def diminished(cls, root: int = 0) -> "Chord":
        return cls("dim", (0, 3, 6), root)

    @classmethod
    def augmented(cls, root: int = 0) -> "Chord":
        return cls("aug", (0, 4, 8), root)

    @classmethod
    def dom7(cls, root: int = 0) -> "Chord":
        return cls("dom7", (0, 4, 7, 10), root)

    @classmethod
    def maj7(cls, root: int = 0) -> "Chord":
        return cls("maj7", (0, 4, 7, 11), root)

    @classmethod
    def min7(cls, root: int = 0) -> "Chord":
        return cls("min7", (0, 3, 7, 10), root)

    @classmethod
    def sus2(cls, root: int = 0) -> "Chord":
        return cls("sus2", (0, 2, 7), root)

    @classmethod
    def sus4(cls, root: int = 0) -> "Chord":
        return cls("sus4", (0, 5, 7), root)

    @classmethod
    def cluster(cls, root: int = 0, span_semitones: int = 4) -> "Chord":
        """Adjacent-note cluster — for tension or dissonant textures."""
        return cls(f"cluster{span_semitones}", tuple(range(span_semitones + 1)), root)

    @classmethod
    def quartal(cls, root: int = 0, n: int = 3) -> "Chord":
        """Stacked-fourths chord (often jazz/contemporary classical)."""
        return cls("quartal", tuple(i * 5 for i in range(n)), root)

    @classmethod
    def custom(cls, name: str, intervals: Sequence[int], root: int = 0) -> "Chord":
        return cls(name, tuple(intervals), root)

    def pitches(self) -> tuple[int, ...]:
        return tuple(self.root + iv for iv in self.intervals)

    def transpose(self, semitones: int) -> "Chord":
        return Chord(self.name, self.intervals, self.root + semitones)
