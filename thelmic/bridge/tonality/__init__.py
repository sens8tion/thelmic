"""Tonality abstractions — # mechanical, genre-neutral.

Key + Scale + Chord + Voicing types so pattern generators can express
melodic intent independent of root note, mode, or tuning system.

Aesthetic packs supply chord progressions and voicings; the Key handles
the transposition arithmetic.
"""
from .keys     import Key, Scale, NaturalMinor, NaturalMajor, Dorian, \
                       Phrygian, Mixolydian, Aeolian, Locrian, Lydian, \
                       Chromatic, Custom
from .chords   import Chord
from .voicings import Voicing

__all__ = [
    "Key", "Scale", "NaturalMinor", "NaturalMajor", "Dorian", "Phrygian",
    "Mixolydian", "Aeolian", "Locrian", "Lydian", "Chromatic", "Custom",
    "Chord", "Voicing",
]
