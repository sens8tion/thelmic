"""Key + Scale.

A Scale is a sequence of intervals from the root (in semitones for tonal
music; floats for microtonal). A Key combines a Scale with a root note
and exposes degree → MIDI-pitch arithmetic.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Sequence


@dataclass(frozen=True)
class Scale:
    name: str
    intervals: Sequence[float]   # cumulative semitone offsets from root, e.g. [0,2,3,5,7,8,10] for natural minor
    octave: float = 12.0          # how many semitones in an octave (12 standard, alter for microtonal)

    def degree(self, n: int) -> float:
        """Return the n-th scale degree's offset from root (in semitones).
        Wraps positively/negatively across octaves. Degree 0 = root."""
        oct_count, idx = divmod(n, len(self.intervals))
        return self.intervals[idx] + oct_count * self.octave


# Standard 7-tone diatonic modes
NaturalMinor   = Scale("natural_minor",   [0, 2, 3, 5, 7, 8, 10])
NaturalMajor   = Scale("natural_major",   [0, 2, 4, 5, 7, 9, 11])
Aeolian        = NaturalMinor                                       # alias
Dorian         = Scale("dorian",          [0, 2, 3, 5, 7, 9, 10])
Phrygian       = Scale("phrygian",        [0, 1, 3, 5, 7, 8, 10])
Mixolydian     = Scale("mixolydian",      [0, 2, 4, 5, 7, 9, 10])
Lydian         = Scale("lydian",          [0, 2, 4, 6, 7, 9, 11])
Locrian        = Scale("locrian",         [0, 1, 3, 5, 6, 8, 10])

# 12-tone — for atonal, serial, or chromatic walks
Chromatic      = Scale("chromatic",       [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11])

# Custom factory for non-standard scales (user-defined intervals)
def Custom(name: str, intervals: Sequence[float], octave: float = 12.0) -> Scale:
    return Scale(name, list(intervals), octave)


@dataclass(frozen=True)
class Key:
    """A musical key — root note + scale.

    root: MIDI note number for the tonic (e.g. 60 = C4, 36 = C2)
    scale: Scale instance
    """
    root: int
    scale: Scale = NaturalMinor

    def degree(self, n: int) -> float:
        """MIDI pitch of the n-th scale degree above the root."""
        return self.root + self.scale.degree(n)

    def transpose(self, semitones: int) -> "Key":
        return Key(self.root + semitones, self.scale)

    def relative(self, mode: Scale) -> "Key":
        """Same root, different scale (e.g. major → natural minor at same root)."""
        return Key(self.root, mode)

    def parallel_major(self) -> "Key":
        return Key(self.root, NaturalMajor)

    def parallel_minor(self) -> "Key":
        return Key(self.root, NaturalMinor)
