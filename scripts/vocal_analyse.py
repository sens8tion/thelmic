"""VOCAL ANALYSE - what a vocal sample actually sings: key, register, held notes, how wet.

Splice tags a key by its root alone ("C", "F#"), sometimes wrongly, and says nothing of register or
how long the notes are. For a sung line to sit in the set (F# minor) and do the job of a drone - long,
high notes - that has to be measured:

- key: YIN pitch track -> sung notes -> pitch-class histogram weighted by time -> the Krumhansl key
  it correlates with best, and the smallest shift that puts most of the singing in F# minor
- register: the 10th, 50th and 90th percentile of the pitch
- held notes: runs where the pitch stays within about half a semitone; the longest, and the share of
  singing spent in notes of LONG_S or more
- wet: side/mid under the words against in the gaps (see reference memory: a reverb tail shows
  as stereo in the gaps)

    python scripts/vocal_analyse.py <folder or files...>
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rap_audition import read_wav  # noqa: E402

NAMES = "C C# D D# E F F# G G# A A# B".split()
F_SHARP_MINOR = {6, 8, 9, 11, 1, 2, 4}
MAJOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
MINOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
LONG_S = 0.5


def yin(x: np.ndarray, sr: int, fmin=110.0, fmax=1100.0, win=2048, hop=441, threshold=0.15):
    """f0 per hop (NaN where unvoiced or quiet), and the hop in seconds."""
    peak = float(np.abs(x).max()) or 1e-9
    tmin, tmax = int(sr / fmax), int(sr / fmin)
    out = []
    for s in range(0, len(x) - win - tmax, hop):
        f = x[s:s + win + tmax]
        if np.sqrt(np.mean(f[:win] ** 2)) < peak * 10 ** (-35 / 20):
            out.append(np.nan)
            continue
        n = 1 << int(np.ceil(np.log2(len(f) * 2)))
        r = np.fft.irfft(np.fft.rfft(f, n) * np.conj(np.fft.rfft(f[:win], n)), n)[:tmax + 1]
        e = np.concatenate([[0.0], np.cumsum(f ** 2)])
        energy = e[np.arange(tmax + 1) + win] - e[np.arange(tmax + 1)]
        d = e[win] + energy - 2 * r
        cmnd = np.ones_like(d)
        cmnd[1:] = d[1:] * np.arange(1, tmax + 1) / np.maximum(np.cumsum(d[1:]), 1e-12)
        below = np.nonzero(cmnd[tmin:] < threshold)[0]
        if not len(below):
            out.append(np.nan)
            continue
        t = tmin + below[0]
        while t + 1 <= tmax and cmnd[t + 1] < cmnd[t]:
            t += 1
        out.append(sr / t)
    return np.array(out), hop / sr


def note_name(m: float) -> str:
    return f"{NAMES[int(round(m)) % 12]}{int(round(m)) // 12 - 1}"


def analyse(path: Path) -> dict:
    x, sr = read_wav(path)
    f0, dt = yin(x.mean(axis=1), sr)
    midi = 69 + 12 * np.log2(f0 / 440.0)
    voiced = ~np.isnan(midi)
    if voiced.sum() < 10:
        return {"file": path.name, "seconds": len(x) / sr, "voiced": float(voiced.mean())}
    hist = np.bincount(np.round(midi[voiced]).astype(int) % 12, minlength=12).astype(float)
    key = max(((k, q) for k in range(12) for q in ("major", "minor")),
              key=lambda kq: np.corrcoef(np.roll(MAJOR if kq[1] == "major" else MINOR, kq[0]), hist)[0, 1])
    fit, _, shift = max((sum(hist[pc] for pc in range(12) if (pc + s) % 12 in F_SHARP_MINOR) / hist.sum(), -abs(s), s)
                        for s in range(-6, 6))
    runs, cur, start = [], None, 0
    for i, m in enumerate(list(midi) + [np.nan]):
        if np.isnan(m) or cur is None or abs(m - cur) > 0.6:
            if cur is not None:
                runs.append(((i - start) * dt, cur))
            cur, start = (None if np.isnan(m) else m), i
    held = sum(d for d, _ in runs if d >= LONG_S) / max(voiced.sum() * dt, 1e-9)
    longest = max(runs) if runs else (0.0, 0.0)
    lo, med, hi = np.percentile(midi[voiced], [10, 50, 90])
    mid, side = (x[:, 0] + x[:, -1]) / 2, (x[:, 0] - x[:, -1]) / 2
    w = int(0.02 * sr)
    em = np.array([np.mean(mid[k:k + w] ** 2) for k in range(0, len(mid) - w, w)])
    es = np.array([np.mean(side[k:k + w] ** 2) for k in range(0, len(side) - w, w)])
    db = 10 * np.log10(np.maximum(em, 1e-20) / em.max())

    def ratio(mask):
        return float(10 * np.log10(max(es[mask].sum(), 1e-20) / max(em[mask].sum(), 1e-20))) if mask.any() else float("nan")
    return {"file": path.name, "seconds": len(x) / sr, "voiced": float(voiced.mean()),
            "key": f"{NAMES[key[0]]} {key[1]}", "shift": shift, "fit": fit,
            "low": note_name(lo), "median": note_name(med), "high": note_name(hi), "median_midi": float(med),
            "longest_s": longest[0], "longest_on": note_name(longest[1]), "held_share": held,
            "side_words_db": ratio(db > -15), "side_gaps_db": ratio((db < -25) & (db > -60))}


if __name__ == "__main__":
    paths = []
    for a in sys.argv[1:]:
        p = Path(a)
        paths += sorted(p.glob("*.wav")) if p.is_dir() else [p]
    for p in paths:
        r = analyse(p)
        if "key" not in r:
            print(f"== {r['file']}: barely voiced ({r['voiced']:.0%})")
            continue
        print(f"== {r['file']}  {r['seconds']:.1f} s, voiced {r['voiced']:.0%}")
        print(f"   sings in {r['key']}; to F# minor: {r['shift']:+d} st -> {r['fit']:.0%} in scale")
        print(f"   register {r['low']}-{r['high']} (median {r['median']}); longest note {r['longest_s']:.2f} s on "
              f"{r['longest_on']}; {r['held_share']:.0%} of the singing in notes of {LONG_S}s+")
        print(f"   stereo under words {r['side_words_db']:.0f} dB, in gaps {r['side_gaps_db']:.0f} dB")
