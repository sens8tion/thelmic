"""Syllables without a speech model, and what they imply for arrangement.

Nuclei are found the way phoneticians count syllables in a recording of
unknown content (De Jong & Wempe 2009): peaks in the voiced intensity contour
that stand clear of the valleys beside them. One nucleus is one syllable-beat
whatever the word is, so this layer works on a vocal in any language, on a
vocal too processed to transcribe, and on a wordless one.

What comes out is the part that matters for arrangement: which grid slot each
syllable lands on, how far off the grid it is, how loud and how long it is, and
- from all of that - where the token *never* puts anything, which is where
another lane can answer without collision.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict

import numpy as np

from .audio import Grid, envelope_db, f0_contour

__all__ = ["Syllable", "Pattern", "find_syllables", "bar_pattern"]

# A peak must stand this far above the valleys either side to be its own
# syllable. 2 dB is the De Jong & Wempe value and is not arbitrary: below it,
# amplitude vibrato inside one long vowel starts registering as extra
# syllables.
DEFAULT_DIP_DB = 2.0
# Anything more than this far below the loudest moment of the bar is not
# speech, it is the tail of the last syllable or bleed from another lane.
DEFAULT_FLOOR_DB = 25.0
# Two nuclei closer together than this are one syllable seen twice. The
# rhythmic floor for distinct events is ~100 ms; 90 ms leaves a little room
# for genuinely fast delivery without letting vibrato through.
MIN_NUCLEUS_GAP = 0.09


@dataclass
class Syllable:
    """One syllable-beat, placed on the grid."""

    bar: int
    slot: int                 # nearest grid slot, 0..subdivision-1
    slot_exact: float         # fractional slot, before rounding
    offset_ms: float          # signed distance from the grid slot
    level_db: float           # relative to the loudest syllable in its bar
    duration_ms: float | None  # to the next nucleus; None if last in the bar
    f0_hz: float              # median pitch over the nucleus, 0 if unvoiced
    word: str | None = None   # filled in by ouvido.speech, if used
    word_confidence: float | None = None

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class Pattern:
    """What one token does to a bar, aggregated over every bar it plays."""

    bars: int
    occupancy: list[float]     # per slot, fraction of bars with a syllable
    level_db: list[float]      # per slot, mean level relative to bar peak
    hits: list[int]            # slots occupied in most bars
    free: list[int]            # slots occupied in almost no bars
    clear_runs: list[tuple[int, int]]   # runs of >=2 free slots
    peak_slot: int             # where the loudest syllable usually lands
    syllables_per_bar: float
    on_beat_ratio: float       # share of syllables on an even slot (an 8th)

    def as_dict(self) -> dict:
        d = asdict(self)
        d["clear_runs"] = [list(r) for r in self.clear_runs]
        return d


def find_syllables(x: np.ndarray, sr: int, grid: Grid, bars: range | list[int],
                   dip_db: float = DEFAULT_DIP_DB,
                   floor_db: float = DEFAULT_FLOOR_DB) -> list[Syllable]:
    """Detect syllable nuclei bar by bar and place them on ``grid``.

    Detection is done per bar so that ``level_db`` is relative to the phrase
    the listener is actually hearing, not to the loudest moment of the whole
    track. A syllable 3 dB down in a quiet bar reads as stressed; the same
    absolute level in a loud bar does not.
    """
    db, fps = envelope_db(x, sr)
    f0 = f0_contour(x, sr)
    n = min(len(db), len(f0))
    db, f0 = db[:n], f0[:n]
    out: list[Syllable] = []

    for bar in bars:
        t0, t1 = grid.bar_bounds(bar)
        a, b = int(max(0.0, t0) * fps), int(min(t1, n / fps) * fps)
        if b - a < 5:
            continue
        seg, voiced = db[a:b], f0[a:b]
        if not np.isfinite(seg).any():
            continue
        thresh = seg.max() - floor_db
        picks: list[int] = []
        for i in range(1, len(seg) - 1):
            if not (seg[i] >= seg[i - 1] and seg[i] > seg[i + 1]
                    and seg[i] > thresh and voiced[i] > 0):
                continue
            left = seg[max(0, i - 20):i]
            right = seg[i + 1:i + 21]
            valley = max(left.min() if len(left) else seg[i],
                         right.min() if len(right) else seg[i])
            if seg[i] - valley < dip_db:
                continue
            if picks and (i - picks[-1]) / fps < MIN_NUCLEUS_GAP:
                if seg[i] > seg[picks[-1]]:
                    picks[-1] = i                # keep the louder of the pair
                continue
            picks.append(i)
        if not picks:
            continue
        peak = max(seg[i] for i in picks)
        for j, i in enumerate(picks):
            t = (a + i) / fps
            frac, slot, err = grid.position(t, bar)
            nxt = (picks[j + 1] - i) / fps * 1000.0 if j + 1 < len(picks) else None
            lo, hi = max(0, i - 2), min(len(voiced), i + 3)
            voiced_win = voiced[lo:hi][voiced[lo:hi] > 0]
            out.append(Syllable(
                bar=bar, slot=slot, slot_exact=round(frac, 2),
                offset_ms=round(err, 1), level_db=round(float(seg[i] - peak), 1),
                duration_ms=round(nxt, 1) if nxt else None,
                f0_hz=round(float(np.median(voiced_win)), 1) if len(voiced_win) else 0.0))
    return out


def bar_pattern(syllables: list[Syllable], subdivision: int = 16,
                hit_at: float = 0.5, free_at: float = 0.2) -> Pattern:
    """Aggregate syllables into the token's characteristic bar.

    ``hit_at`` and ``free_at`` are deliberately asymmetric. A slot counts as a
    hit if it is used in most bars, but only counts as *free* if it is used in
    almost none - because the cost of putting something into a slot that turns
    out to be occupied is higher than the cost of leaving a usable slot empty.
    """
    bars = sorted({s.bar for s in syllables})
    occ = np.zeros(subdivision)
    lvl: list[list[float]] = [[] for _ in range(subdivision)]
    for bar in bars:
        seen = set()
        for s in (s for s in syllables if s.bar == bar):
            if s.slot in seen:
                continue
            seen.add(s.slot)
            occ[s.slot] += 1
            lvl[s.slot].append(s.level_db)
    nbars = max(len(bars), 1)
    rate = occ / nbars
    hits = [i for i in range(subdivision) if rate[i] >= hit_at]
    free = [i for i in range(subdivision) if rate[i] <= free_at]

    runs: list[tuple[int, int]] = []
    run: list[int] = []
    for i in list(range(subdivision)) + [None]:
        if i is not None and i in free:
            run.append(i)
        else:
            if len(run) >= 2:
                runs.append((run[0], run[-1]))
            run = []

    # the peak slot is judged only among slots that actually recur, so a single
    # loud accident in one bar cannot claim it
    candidates = [i for i in range(subdivision) if rate[i] >= 0.4 and lvl[i]]
    peak = max(candidates, key=lambda i: float(np.mean(lvl[i]))) if candidates else -1
    on_beat = float(np.mean([s.slot % 2 == 0 for s in syllables])) if syllables else 0.0

    return Pattern(
        bars=nbars,
        occupancy=[round(float(v), 3) for v in rate],
        level_db=[round(float(np.mean(v)), 1) if v else None for v in lvl],
        hits=hits, free=free, clear_runs=runs, peak_slot=peak,
        syllables_per_bar=round(len(syllables) / nbars, 2),
        on_beat_ratio=round(on_beat, 3),
    )
