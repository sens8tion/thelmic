"""Drum + rhythmic pattern generators for the dnb_jungle pack.

Each generator returns a list of (pitch, start_beat, duration, velocity)
tuples for a 4-bar phrase, parameterised by `offset` (start beat).
"""
from __future__ import annotations
from .constants import KICK, SNARE, HAT_C, HAT_O, RIDE, CRASH, LOW_TOM, HI_TOM


def amen_4bar(offset: float = 0.0) -> list[tuple[int, float, float, int]]:
    """Classic Amen-style breakbeat. 4 bars × 4 beats = 16 beats."""
    base = [
        (KICK, 0.0, 0.4, 110), (SNARE, 1.0, 0.35, 100),
        (KICK, 1.5, 0.4, 95),  (SNARE, 3.0, 0.35, 105),
        (KICK, 4.0, 0.4, 110), (SNARE, 5.0, 0.35, 100),
        (SNARE, 5.5, 0.2, 75), (SNARE, 6.5, 0.3, 95),
        (KICK, 7.5, 0.35, 90),
        (KICK, 8.0, 0.4, 110), (SNARE, 9.0, 0.35, 100),
        (KICK, 10.5, 0.35, 95),(SNARE, 11.0, 0.35, 105),
        (KICK, 12.0, 0.4, 110),(SNARE, 13.0, 0.3, 95),
        (SNARE, 13.5, 0.2, 75),(SNARE, 14.0, 0.35, 100),
        (KICK, 14.5, 0.35, 90),(SNARE, 15.0, 0.3, 95),
        (SNARE, 15.5, 0.25, 80),
    ]
    notes = [(p, t + offset, dur, vel) for (p, t, dur, vel) in base]
    for i in range(64):
        t = i * 0.25 + offset
        slot = i % 4
        notes.append((HAT_C, t, 0.18, {0: 92, 1: 65, 2: 78, 3: 65}[slot]))
    return notes


def gabber_4bar(offset: float = 0.0, double: bool = False) -> list[tuple[int, float, float, int]]:
    """Gabber 4-on-the-floor. double=True gives 8th-note kicks."""
    notes = []
    rate_beats = 0.5 if double else 1.0
    n_kicks = int(16 / rate_beats)
    for i in range(n_kicks):
        t = offset + i * rate_beats
        vel = 122 if (i * rate_beats) % 1 == 0 else 110
        notes.append((KICK, t, 0.18 if double else 0.4, vel))
    for bar in range(4):
        for sb in (1.0, 3.0):
            notes.append((SNARE, offset + bar * 4.0 + sb, 0.35, 110))
    for i in range(64):
        t = offset + i * 0.25
        slot = i % 4
        notes.append((HAT_C, t, 0.14, {0: 88, 1: 60, 2: 75, 3: 60}[slot]))
    return notes


def breakcore_4bar(offset: float = 0.0) -> list[tuple[int, float, float, int]]:
    """16th-note kicks throughout (4× density vs gabber). Industrial chaos."""
    notes = []
    for i in range(64):
        t = offset + i * 0.25
        slot = i % 4
        vel = {0: 124, 1: 110, 2: 117, 3: 110}[slot]
        notes.append((KICK, t, 0.10, vel))
    for bar in range(4):
        for sb in (1.0, 3.0):
            notes.append((SNARE, offset + bar * 4.0 + sb, 0.3, 115))
    return notes


def anticipation_fill(bs: float = 0.0) -> list[tuple[int, float, float, int]]:
    """Last bar pre-drop fill: tightening ticks → snare flam → drop-out → impact."""
    out = []
    for i in range(6):
        out.append((HAT_C, bs + i * 0.25, 0.10, 80 + i * 4))
    for i in range(12):
        out.append((HAT_C, bs + 1.5 + i * 0.125, 0.05, 90 + i * 2))
    for i in range(4):
        out.append((SNARE, bs + 3.0 + i * 0.125, 0.08, 100 + i * 6))
    out.append((KICK, bs + 3.875, 0.2, 127))
    out.append((SNARE, bs + 3.875, 0.2, 127))
    out.append((CRASH, bs + 3.875, 4.0, 127))
    return out


def hat_acceleration(bs: float = 0.0, span_beats: float = 4.0) -> list[tuple[int, float, float, int]]:
    """Hat roll accelerating 8th → 16th → 32nd → 64th, rising velocity."""
    out = []
    n8 = max(1, int(span_beats * 0.25 / 0.5))
    for i in range(n8):
        out.append((HAT_C, bs + i * 0.5, 0.10, 80 + i * 5))
    s16 = bs + span_beats * 0.25
    for i in range(int(span_beats * 0.25 / 0.25)):
        out.append((HAT_C, s16 + i * 0.25, 0.08, 92 + i * 3))
    s32 = bs + span_beats * 0.5
    for i in range(int(span_beats * 0.25 / 0.125)):
        out.append((HAT_C, s32 + i * 0.125, 0.06, 102 + i * 2))
    s64 = bs + span_beats * 0.75
    for i in range(int(span_beats * 0.25 / 0.0625)):
        out.append((HAT_C, s64 + i * 0.0625, 0.05, min(115 + i, 127)))
    return out
