"""REAPER ALIGNMENT - do the layers of the reference change together?

The user's model: every layer (bass riff, sub tone, kick pattern, 16th carrier) holds its state
inside a sub-section and only changes at its boundaries. The bass and rhythm analyses each found
per-layer change points; this lines them up on one bar timeline and asks whether they coincide
more than chance, using the per-bar tables those analyses saved:

  <cache>/bass_bars.npz     riff_segment_id, timbre_segment_id    (bars from grid.npz)
  <cache>/rhythm_bars.npz   kick_segment_id, carrier_segment_id   (bars from its own drift-tracked grid)

Rhythm bars are mapped onto the bass bars by nearest start time. A change "coincides" with another
layer's change when it lands within +-1 bar of it; chance comes from circular shifts of the other
layer's change sequence. Structural analysis only - nothing is extracted from the audio.

    python scripts/reaper_alignment.py
"""
from __future__ import annotations

import numpy as np

CACHE = r"C:\Users\eric\Downloads\reaper_cache"
SHIFTS = 2000
TOL = 1                     # bars either side


def load():
    b = np.load(CACHE + r"\bass_bars.npz", allow_pickle=True)
    r = np.load(CACHE + r"\rhythm_bars.npz", allow_pickle=True)
    tb, tr = b["bar_start_s"], r["bar_start_s"]
    near = np.abs(tb[None, :] - tr[:, None]).argmin(axis=1)
    return b, r, tb, near


def changes(seg, n, idx_map=None):
    seg = np.asarray(seg)
    out = np.zeros(n, bool)
    moved = seg[1:] != seg[:-1]
    out[(np.arange(1, len(seg)) if idx_map is None else idx_map[1:])[moved]] = True
    return out


def dilate(v, w=TOL):
    out = v.copy()
    for s in range(1, w + 1):
        out[s:] |= v[:-s]
        out[:-s] |= v[s:]
    return out


def coincide(a, b):
    pa = np.flatnonzero(a)
    return dilate(b)[pa].mean() if len(pa) else np.nan


def clusters(anchor, gap=2):
    ev = np.flatnonzero(anchor)
    out, cur = [], [ev[0]]
    for e in ev[1:]:
        if e - cur[-1] <= gap:
            cur.append(e)
        else:
            out.append(cur)
            cur = [e]
    out.append(cur)
    return out


def main():
    rng = np.random.default_rng(0)
    b, r, tb, near = load()
    n = len(tb)
    layers = {"riff": changes(b["riff_segment_id"], n), "timbre": changes(b["timbre_segment_id"], n),
              "kick": changes(r["kick_segment_id"], n, near), "carrier": changes(r["carrier_segment_id"], n, near)}
    for k, v in layers.items():
        seg = np.diff(np.concatenate([[0], np.flatnonzero(v), [n]]))
        print(f"{k:<8} {v.sum():>3} changes, segments median {np.median(seg):.0f} bars "
              f"(IQR {np.percentile(seg, 25):.0f}-{np.percentile(seg, 75):.0f})")
    names = list(layers)
    print("\nrow-layer changes within +-1 bar of a column-layer change: observed vs chance, p")
    for a in names:
        cells = []
        for c in names:
            if a == c:
                cells.append(f"{'-':>20}")
                continue
            obs = coincide(layers[a], layers[c])
            null = np.array([coincide(layers[a], np.roll(layers[c], rng.integers(8, n - 8))) for _ in range(SHIFTS)])
            cells.append(f"{obs:>5.0%} vs {null.mean():>3.0%} p{(np.sum(null >= obs) + 1) / (SHIFTS + 1):.3f}")
        print(f"{a:<8}" + "".join(cells))

    def joint(ls):
        stack = np.vstack([dilate(v) for v in ls]).astype(int).sum(axis=0)
        anchor = np.zeros(n, bool)
        for v in ls:
            anchor |= v
        cl = clusters(anchor)
        return cl, [max(stack[c] for c in x) for x in cl]

    cl, ks = joint(list(layers.values()))
    null = [np.mean([k >= 3 for k in joint([np.roll(v, rng.integers(8, n - 8)) for v in layers.values()])[1]])
            for _ in range(500)]
    obs3 = np.mean([k >= 3 for k in ks])
    print(f"\n{len(cl)} boundary events: " + ", ".join(f"{k} layer(s) {ks.count(k)}" for k in (1, 2, 3, 4)))
    print(f">=3 layers together: {obs3:.0%} vs chance {np.mean(null):.0%} (p {(np.sum(np.array(null) >= obs3) + 1) / 501:.3f})")
    sec = b["section"]
    seams = np.flatnonzero(sec[1:] != sec[:-1]) + 1
    for c, k in zip(cl, ks):
        if k >= 3:
            t = tb[c[0]]
            seam = any(abs(c[0] - s) <= 2 for s in seams)
            print(f"  bar {c[0]:>3}  {int(t // 60)}:{t % 60:04.1f}  {k} layers  {'record seam' if seam else 'inside a record'}")


if __name__ == "__main__":
    main()
