"""Voicing — how a chord is laid out in pitch space.

A Chord describes interval content. A Voicing is a specific arrangement
of those notes across octaves: drop2, drop3, close, open, spread, etc.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Sequence
from .chords import Chord


@dataclass(frozen=True)
class Voicing:
    notes: tuple[int, ...]   # actual MIDI pitches, in order

    @classmethod
    def close(cls, chord: Chord) -> "Voicing":
        """Tightest voicing — root + intervals as given."""
        return cls(chord.pitches())

    @classmethod
    def drop2(cls, chord: Chord) -> "Voicing":
        """Drop-2 voicing: 2nd-highest note dropped an octave (jazz standard)."""
        ps = list(chord.pitches())
        if len(ps) >= 2:
            ps[-2] -= 12
        return cls(tuple(sorted(ps)))

    @classmethod
    def drop3(cls, chord: Chord) -> "Voicing":
        ps = list(chord.pitches())
        if len(ps) >= 3:
            ps[-3] -= 12
        return cls(tuple(sorted(ps)))

    @classmethod
    def open(cls, chord: Chord) -> "Voicing":
        """Open voicing — every other note dropped an octave."""
        ps = list(chord.pitches())
        for i in range(1, len(ps), 2):
            ps[i] -= 12
        return cls(tuple(sorted(ps)))

    @classmethod
    def spread(cls, chord: Chord, octave_span: int = 2) -> "Voicing":
        """Spread voicing — chord pitches distributed across N octaves."""
        ps = list(chord.pitches())
        spread_step = (octave_span * 12) // max(1, len(ps) - 1)
        return cls(tuple(p + i * spread_step for i, p in enumerate(ps)))

    @classmethod
    def stacked_octaves(cls, chord: Chord, n_octaves: int = 2) -> "Voicing":
        """Same chord at multiple octaves stacked — fat unison feel."""
        out = []
        for o in range(n_octaves):
            out.extend(p + o * 12 for p in chord.pitches())
        return cls(tuple(sorted(out)))

    def transpose(self, semitones: int) -> "Voicing":
        return Voicing(tuple(p + semitones for p in self.notes))

    def invert(self, n: int = 1) -> "Voicing":
        """Move bottom n notes up an octave, n times (chord inversion)."""
        ps = list(self.notes)
        for _ in range(n):
            if ps:
                ps[0] += 12
                ps.sort()
        return Voicing(tuple(ps))
