"""Generic MIDI / note-list helpers — # mechanical."""
from __future__ import annotations
from typing import Iterable


def to_clip_notes(quads: Iterable[tuple[int, float, float, int]]) -> list[dict]:
    """Convert (pitch, start_time, duration, velocity) tuples to add_notes_to_clip dicts."""
    return [{"pitch": p, "start_time": float(t), "duration": float(dur), "velocity": int(vel)}
             for (p, t, dur, vel) in quads]


def repeat_pattern(pattern_fn, n_repeats: int, period_beats: float = 16.0,
                    offset: float = 0.0) -> list[tuple[int, float, float, int]]:
    """Tile a pattern N times. pattern_fn is called with (offset + rep * period)."""
    out = []
    for rep in range(n_repeats):
        out.extend(pattern_fn(offset + rep * period_beats))
    return out
