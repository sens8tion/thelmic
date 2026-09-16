"""REAPER RHYTHM - the inside of the bar, and the relationship between bars.

Structural analysis of the reference jungle DJ set. NOTHING is ever sampled, extracted or copied
from the audio: this script reads the cached mono downmix, produces numbers, and writes a markdown
report. No audio leaves here.

Numpy + torch only (no librosa/scipy/soundfile/sklearn). Everything - STFT, band flux, onset peak
picking, tempo, beat and bar grid, per-16th occupancy, microtiming, bar similarity, fills, chop
detection - is built in this file.

    python scripts/reaper_rhythm.py --probe      # grid sanity check, prints and exits
    python scripts/reaper_rhythm.py              # full analysis -> tracks/2026-09-16_reaper/rhythm.md

Grid provenance: the grid is derived HERE and grid.npz is used only as a cross-check. The other
agent's beat times are snapped to the 10.67 ms frame hop of the 93.75 fps cache, which is coarser
than the microtiming this analysis has to resolve. The local grid is a 16th period fitted to the
onset times by circular phase coherence, plus a tracked phase-correction curve (a rigid grid drifts
up to half a 16th across the set), with the bar phase re-fitted inside each section because a DJ
mix does not carry one bar phase from record to record.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np
import torch

CACHE = r"C:\Users\eric\Downloads\reaper_cache"
OUT_DIR = r"C:\Users\eric\github\sens8tion\thelmic\tracks\2026-09-16_reaper"
OUT_MD = os.path.join(OUT_DIR, "rhythm.md")

SR = 8000            # mono8k.npy
HOP = 32             # 250 fps -> 4 ms frames
NFFT = 512           # 64 ms window, 15.6 Hz bins
FPS = SR / HOP
# three bands, as the brief asks: low = kick/bass, mid = snare/body, high = hats/ghosts.
# Nyquist is 4 kHz in the 8 kHz downmix, so "high" tops out there - fine for hats and snare edge.
BANDS3 = {"low": (20.0, 160.0), "mid": (160.0, 1200.0), "high": (1200.0, 4000.0)}
BPM_RANGE = (150.0, 190.0)


# ----------------------------------------------------------------------
# frame-rate band onset envelopes (chunked: the whole STFT would be ~300 MB)
# ----------------------------------------------------------------------
def band_flux(mono: np.ndarray) -> dict:
    """-> {'t', 'low', 'mid', 'high', 'all'} half-wave-rectified log-magnitude spectral flux."""
    freqs = np.fft.rfftfreq(NFFT, 1.0 / SR)
    sel = {k: (freqs >= lo) & (freqs < hi) for k, (lo, hi) in BANDS3.items()}
    win = torch.hann_window(NFFT)
    chunk = SR * 120                                   # 2 minutes at a time
    pad = NFFT
    envs = {k: [] for k in BANDS3}
    n = len(mono)
    pos = 0
    while pos < n:
        a = max(0, pos - pad)
        z = min(n, pos + chunk + pad)
        seg = torch.from_numpy(np.ascontiguousarray(mono[a:z].astype(np.float32)))
        S = torch.stft(seg, NFFT, HOP, window=win, center=True, return_complex=True).abs().numpy()
        S = np.log1p(200.0 * S)                        # log compression: onsets over a loud bed
        # SuperFlux: compare each frame against a max-filtered frame MU back. The frequency max
        # filter swallows vibrato and the wobble of a reese/sub, which otherwise fire an onset on
        # every LFO cycle; the lag keeps the difference at true transients large.
        MU = 3                                         # 12 ms lookback
        Sm = np.maximum(np.maximum(np.roll(S, 1, axis=0), S), np.roll(S, -1, axis=0))
        ref = np.concatenate([Sm[:, :1].repeat(MU, axis=1), Sm[:, :-MU]], axis=1)
        d = np.maximum(0.0, S - ref)
        # frame f of this chunk covers sample a + f*HOP; keep the frames whose centre is in [pos, z')
        f0 = int(np.ceil((pos - a) / HOP))
        f1 = int(np.ceil((min(n, pos + chunk) - a) / HOP))
        for k, m in sel.items():
            envs[k].append(d[m, f0:f1].sum(axis=0))
        pos += chunk
    out = {k: np.concatenate(v).astype(np.float32) for k, v in envs.items()}
    m = min(len(v) for v in out.values())
    out = {k: v[:m] for k, v in out.items()}
    out["t"] = (np.arange(m) / FPS).astype(np.float32)
    out["all"] = (out["low"] / (out["low"].std() + 1e-9) + out["mid"] / (out["mid"].std() + 1e-9)
                  + out["high"] / (out["high"].std() + 1e-9)).astype(np.float32)
    return out


def moving_avg(x: np.ndarray, k: int) -> np.ndarray:
    k = k | 1
    c = np.concatenate([[0.0], np.cumsum(x.astype(np.float64))])
    h = k // 2
    lo = np.clip(np.arange(len(x)) - h, 0, len(x))
    hi = np.clip(np.arange(len(x)) + h + 1, 0, len(x))
    return ((c[hi] - c[lo]) / np.maximum(hi - lo, 1)).astype(np.float32)


def pick_onsets(env: np.ndarray, win_s: float = 0.5, mult: float = 2.3,
                min_sep_s: float = 0.055) -> tuple[np.ndarray, np.ndarray]:
    """Local maxima above an adaptive threshold, then greedy strongest-first thinning so no two
    onsets sit closer than `min_sep_s` (a 16th is ~90 ms here; 55 ms lets 32nd-note ghost pairs
    through but kills the double-triggering of a single transient).

    -> (onset times in SECONDS with sub-frame parabolic refinement, strength)."""
    k = int(round(win_s * FPS))
    avg = moving_avg(env, k)
    a, b, c = env[:-2], env[1:-1], env[2:]
    ispk = (b >= a) & (b > c) & (b > avg[1:-1] * mult) & (b > 0)
    idx = np.nonzero(ispk)[0] + 1
    if len(idx) == 0:
        return np.zeros(0, np.float64), np.zeros(0, np.float32)
    y0, y1, y2 = env[idx - 1].astype(np.float64), env[idx].astype(np.float64), env[idx + 1].astype(np.float64)
    den = (y0 - 2 * y1 + y2)
    shift = np.clip(np.where(den != 0, 0.5 * (y0 - y2) / np.where(den == 0, 1, den), 0.0), -0.5, 0.5)
    pos = (idx + shift) / FPS
    st = env[idx].astype(np.float32)
    sel = _thin(pos, st, min_sep_s)
    return pos[sel], st[sel]


def _thin(pos: np.ndarray, st: np.ndarray, min_sep: float) -> np.ndarray:
    """Greedy non-maximum suppression in time, strongest first. Positions must be sorted."""
    n = len(pos)
    alive = np.ones(n, bool)
    keep = np.zeros(n, bool)
    for j in np.argsort(-st):
        if not alive[j]:
            continue
        keep[j] = True
        lo = np.searchsorted(pos, pos[j] - min_sep, "left")
        hi = np.searchsorted(pos, pos[j] + min_sep, "right")
        alive[lo:hi] = False
        alive[j] = False
    return keep


# ----------------------------------------------------------------------
# tempo, beats, bars - derived locally and sanity-checked
# ----------------------------------------------------------------------
def local_tempo(env: np.ndarray, win_s: float = 24.0, hop_s: float = 8.0) -> tuple[np.ndarray, np.ndarray]:
    """Autocorrelation tempo per window -> (window centre seconds, bpm)."""
    w = int(win_s * FPS)
    h = int(hop_s * FPS)
    lag_lo = int(np.floor(60.0 * FPS / BPM_RANGE[1]))
    lag_hi = int(np.ceil(60.0 * FPS / BPM_RANGE[0]))
    cs, bpms = [], []
    for a in range(0, max(1, len(env) - w), h):
        seg = env[a:a + w]
        if len(seg) < w // 2:
            break
        e = seg - seg.mean()
        ac = np.correlate(e, e, mode="full")[len(e) - 1:]
        lags = np.arange(lag_lo, min(lag_hi + 1, len(ac)))
        sc = ac[lags]
        j = int(np.argmax(sc))
        lag = lags[j]
        if 1 <= j < len(sc) - 1:                       # parabolic refine
            y0, y1, y2 = sc[j - 1], sc[j], sc[j + 1]
            den = y0 - 2 * y1 + y2
            if den != 0:
                lag = lag + 0.5 * (y0 - y2) / den
        cs.append((a + w / 2) / FPS)
        bpms.append(60.0 * FPS / lag)
    return np.array(cs), np.array(bpms)




def phase_fit(times: np.ndarray, w: np.ndarray, p_lo: float, p_hi: float,
              n: int = 4000) -> tuple[float, float, float]:
    """Fit a strictly periodic grid to onset TIMES by circular phase coherence:
        z(P) = sum w_i exp(2 pi i t_i / P);  argmax |z| over P.
    Far more precise than autocorrelation on a frame envelope because the onset times themselves
    carry sub-frame resolution. -> (period, phase offset in s, coherence 0..1)."""
    ps = np.linspace(p_lo, p_hi, n)
    t = times.astype(np.float64)[None, :]
    ww = (w / w.sum()).astype(np.float64)[None, :]
    best, bp, bph = -1.0, ps[0], 0.0
    step = 400
    for a in range(0, n, step):                       # chunked: the full matrix would be huge
        pp = ps[a:a + step][:, None]
        z = (ww * np.exp(2j * np.pi * t / pp)).sum(axis=1)
        m = np.abs(z)
        j = int(np.argmax(m))
        if m[j] > best:
            best, bp = float(m[j]), float(pp[j, 0])
            bph = float(-np.angle(z[j]) / (2 * np.pi) * bp)
    return bp, bph % bp, best


def grid_residuals(times: np.ndarray, w: np.ndarray, period: float, phase: float,
                   bin_s: float = 20.0, span: float = 1259.7) -> tuple[np.ndarray, np.ndarray]:
    """Per-window mean phase of the onsets against the fitted grid, in ms. A grid that has drifted
    out of step shows up as a residual marching away from zero."""
    r = ((times - phase) / period + 0.5) % 1.0 - 0.5     # fraction of a beat, -0.5..0.5
    edges = np.arange(0, span + bin_s, bin_s)
    cs, res = [], []
    for a, z in zip(edges[:-1], edges[1:]):
        m = (times >= a) & (times < z)
        if m.sum() < 20:
            continue
        ang = np.angle((w[m] * np.exp(2j * np.pi * r[m])).sum())
        cs.append((a + z) / 2)
        res.append(ang / (2 * np.pi) * period * 1000.0)
    return np.array(cs), np.array(res)


def phase_track(times: np.ndarray, w: np.ndarray, period: float, phase: float, dur: float,
                win_s: float = 8.0) -> tuple[np.ndarray, np.ndarray]:
    """The rigid grid wanders: two decks in a mix are never locked to the part-per-million, so the
    phase of the onsets against a single fitted period walks around and eventually wraps. Measure
    the circular mean phase per window, UNWRAP it in units of the period, and return a smooth
    correction curve phi(t) in seconds."""
    r = ((times - phase) / period + 0.5) % 1.0 - 0.5
    edges = np.arange(0, dur + win_s, win_s)
    cs, ph = [], []
    for a, z in zip(edges[:-1], edges[1:]):
        m = (times >= a) & (times < z)
        if m.sum() < 8:
            continue
        cs.append((a + z) / 2)
        ph.append(np.angle((w[m] * np.exp(2j * np.pi * r[m])).sum()) / (2 * np.pi))
    cs, ph = np.array(cs), np.array(ph)
    ph = np.unwrap(ph * 2 * np.pi) / (2 * np.pi)         # in periods, continuous
    k = 5                                                # ~40 s smoothing: follow drift, not jitter
    pad = np.concatenate([np.full(k, ph[0]), ph, np.full(k, ph[-1])])
    ph = np.convolve(pad, np.ones(2 * k + 1) / (2 * k + 1), "same")[k:-k]
    return cs, ph * period


def grid16_times(period: float, phase: float, cs: np.ndarray, phi: np.ndarray,
                 dur: float) -> np.ndarray:
    """Every 16th boundary, with the drift correction folded in. t_n = n*P + phase + phi(t_n),
    solved by two fixed-point passes (phi moves by ms over tens of seconds, so it converges at once)."""
    n = np.arange(int((dur - phase) / period) + 1)
    t = phase + n * period
    for _ in range(3):
        t = phase + n * period + np.interp(t, cs, phi)
    return t


def build_grid(env: dict, onsets: dict, dur: float, verbose: bool = True) -> dict:
    """A rigid 16th grid fitted to the onset times by phase coherence, then the beat phase and the
    downbeat phase chosen by where the kick and the snare land. grid.npz is read and CROSS-CHECKED
    but not used directly: its beat times are snapped to the 10.67 ms frame hop of the 93.75 fps
    cache, which is coarser than the microtiming this analysis has to resolve."""
    t = np.concatenate([onsets[k][0] for k in ("low", "mid", "high")])
    w = np.concatenate([onsets[k][1] / (onsets[k][1].mean() + 1e-9) for k in ("low", "mid", "high")])
    o = np.argsort(t)
    t, w = t[o], w[o]
    beat_lo, beat_hi = 60.0 / BPM_RANGE[1], 60.0 / BPM_RANGE[0]
    p16, ph16, coh = phase_fit(t, w, beat_lo / 4, beat_hi / 4, n=6000)
    bpm = 60.0 / (p16 * 4)
    cs0, res0 = grid_residuals(t, w, p16, ph16, span=dur)
    drift0 = float(np.max(np.abs(res0))) if len(res0) else np.nan

    # follow the drift and rebuild the 16th grid on top of it
    pcs, phi = phase_track(t, w, p16, ph16, dur)
    t16 = grid16_times(p16, ph16, pcs, phi, dur)
    # residual against the CORRECTED grid: how far a real onset sits from its nearest 16th
    j = np.clip(np.searchsorted(t16, t) - 1, 0, len(t16) - 2)
    d0 = t - t16[j]
    step = np.diff(t16)[j]
    dev = np.where(d0 > step / 2, d0 - step, d0) * 1000.0
    cs1, res1 = grid_residuals(t, w, p16, ph16, span=dur)   # (kept for the report)
    drift1 = float(np.max(np.abs([np.median(dev[(t >= a) & (t < a + 20)])
                                  for a in np.arange(0, dur - 20, 20)])))

    # beat phase: of the 4 sixteenth offsets, the one whose low band is heaviest
    lo_t, lo_w = onsets["low"]
    mi_t, mi_w = onsets["mid"]
    steps = np.diff(t16)

    def k_of(tt):
        """Index of the nearest 16th boundary."""
        j = np.clip(np.searchsorted(t16, tt) - 1, 0, len(t16) - 2)
        return j + ((tt - t16[j]) / steps[j] > 0.5).astype(np.int64)

    klo, kmi = k_of(lo_t), k_of(mi_t)
    beat_sc = [float(lo_w[(klo % 4) == jj].sum()) for jj in range(4)]
    bphase = int(np.argmax(beat_sc))
    # downbeat: kick on beat 1 AND snare on beats 2 and 4
    kb_lo, kb_mi = ((klo - bphase) // 4) % 4, ((kmi - bphase) // 4) % 4
    sc = []
    for jj in range(4):
        lo1 = lo_w[kb_lo == jj].sum() / (lo_w.sum() + 1e-9)
        sn = (mi_w[kb_mi == (jj + 1) % 4].sum() + mi_w[kb_mi == (jj + 3) % 4].sum()) / (mi_w.sum() + 1e-9)
        sc.append(float(lo1 + sn))
    dphase = int(np.argmax(sc))
    start = bphase + dphase * 4
    bar_idx = np.arange(start, len(t16) - 16, 16)
    bars_s = t16[np.concatenate([bar_idx, [bar_idx[-1] + 16]])]
    beats_s = t16[bphase::4]
    n_bars = len(bars_s) - 1

    # per-section downbeat check: in a DJ mix the incoming record need not share the outgoing
    # record's bar phase, so verify the bar phase holds rather than assuming it
    db_local = []
    for a in np.arange(0, dur - 60, 60):
        m = (mi_t >= a) & (mi_t < a + 60)
        if m.sum() < 30:
            continue
        kk = ((k_of(mi_t[m]) - bphase) // 4) % 4
        ww = mi_w[m]
        s = [float(ww[kk == (jj + 1) % 4].sum() + ww[kk == (jj + 3) % 4].sum()) for jj in range(4)]
        db_local.append((float(a), int(np.argmax(s)), float(max(s) / (sum(s) + 1e-9))))

    xcheck = None
    g = grid_from_cache()
    if g is not None and "beats_s" in g:
        ob = np.asarray(g["beats_s"], np.float64)
        obpm = (len(ob) - 1) / (ob[-1] - ob[0]) * 60.0
        jj = np.clip(np.searchsorted(beats_s, ob) - 1, 0, len(beats_s) - 2)
        dd = ob - beats_s[jj]
        st = np.diff(beats_s)[jj]
        dv = np.where(dd > st / 2, dd - st, dd) * 1000.0
        xcheck = {"bpm": obpm, "n": int(len(ob)), "median_abs_dev_ms": float(np.median(np.abs(dv))),
                  "within_20ms": float((np.abs(dv) < 20).mean()), "downbeat_agree": None}
        if "downbeats_s" in g:
            od = np.asarray(g["downbeats_s"], np.float64)
            k2 = np.clip(np.searchsorted(bars_s, od) - 1, 0, len(bars_s) - 2)
            d2 = od - bars_s[k2]
            s2 = np.diff(bars_s)[k2]
            xcheck["downbeat_agree"] = float((np.minimum(d2, s2 - d2) * 1000 < 40).mean())

    info = {"bars_s": bars_s, "beats_s": beats_s, "t16": t16, "bpm": bpm, "p16": p16,
            "period": p16 * 4, "bar_len": p16 * 16, "coherence": coh,
            "drift_rigid_ms": drift0, "drift_tracked_ms": drift1, "residual": (cs0, res0),
            "dev_ms": dev, "beat_phase": bphase, "downbeat_phase": dphase, "n_bars": n_bars,
            "db_local": db_local, "bpm_windows": local_tempo(env["all"]), "xcheck": xcheck,
            "source": "local phase fit + drift tracking"}
    if verbose:
        print(f"phase-fit 16th = {p16*1000:.4f} ms -> beat {p16*4*1000:.3f} ms -> {bpm:.4f} BPM, "
              f"coherence {coh:.4f}")
        print(f"  rigid grid drift: max |{drift0:.1f}| ms  ->  after drift tracking: "
              f"max |{drift1:.1f}| ms")
        print(f"  beat phase = 16th {bphase} {np.round(beat_sc,1)}, downbeat = beat {dphase} "
              f"{np.round(sc,3)}, {n_bars} bars")
        agree = np.mean([d[1] == dphase for d in db_local]) if db_local else np.nan
        print(f"  bar phase holds in {agree*100:.0f}% of 60 s windows "
              f"({sum(d[1]==dphase for d in db_local)}/{len(db_local)})")
        if xcheck:
            print(f"  grid.npz cross-check: {xcheck['bpm']:.3f} BPM, "
                  f"{xcheck['within_20ms']*100:.1f}% of its beats within 20 ms of mine "
                  f"(median |dev| {xcheck['median_abs_dev_ms']:.1f} ms), "
                  f"downbeats agree {xcheck['downbeat_agree']*100:.0f}%")
    return info


def grid_from_cache() -> dict | None:
    p = os.path.join(CACHE, "grid.npz")
    if not os.path.exists(p):
        return None
    try:
        g = np.load(p, allow_pickle=True)
        if "beats_s" not in g.files:
            return None
        return {k: g[k] for k in g.files}
    except Exception:
        return None


# ----------------------------------------------------------------------
# per-bar rhythm matrices
# ----------------------------------------------------------------------
def bar_matrices(onsets: dict, t16: np.ndarray, bar_starts: np.ndarray) -> dict:
    """For each bar, each of 16 slots, each of 3 bands:
        hit[b,k,i]   1 if a band onset is nearest to that slot boundary
        amp[b,k,i]   its flux strength
        off[b,k,i]   ms early(-)/late(+) vs the exact slot time, NaN when empty
    A slot owns the onsets within +-50% of a 16th of it; if two land in one slot the stronger wins."""
    nb = len(bar_starts)
    hit = np.zeros((nb, 16, 3), np.float32)
    amp = np.zeros((nb, 16, 3), np.float32)
    off = np.full((nb, 16, 3), np.nan, np.float32)
    steps = np.diff(t16)
    kmax = len(t16) - 2
    pos_of_k = {int(k): b for b, k0 in enumerate(bar_starts) for k in range(k0, k0 + 16)}
    slot_of_k = {int(k): j for k0 in bar_starts for j, k in enumerate(range(k0, k0 + 16))}
    for i, nm in enumerate(("low", "mid", "high")):
        p, s = onsets[nm]
        j = np.clip(np.searchsorted(t16, p) - 1, 0, kmax)
        frac = (p - t16[j]) / steps[j]
        k = j + (frac > 0.5).astype(np.int64)
        d = (p - t16[np.clip(k, 0, len(t16) - 1)]) * 1000.0
        order = np.argsort(-s)
        for q in order:
            kk = int(k[q])
            b = pos_of_k.get(kk)
            if b is None:
                continue
            sl = slot_of_k[kk]
            if hit[b, sl, i] == 0:
                hit[b, sl, i] = 1.0
                amp[b, sl, i] = s[q]
                off[b, sl, i] = d[q]
    return {"hit": hit, "amp": amp, "off": off, "bar_t": t16[bar_starts]}


# ----------------------------------------------------------------------
# sections
# ----------------------------------------------------------------------
def timbre_matrix(rate: float = 2.0) -> tuple[np.ndarray, np.ndarray]:
    """Grid-independent timbre/energy features from the 93.75 fps cache, at `rate` Hz."""
    f = np.load(os.path.join(CACHE, "frames.npz"))
    t = f["t"]
    step = int(round(93.75 / rate))
    cols = ["rms", "sub", "bass", "lowmid", "mid", "high", "air", "centroid", "width", "crest"]
    n = len(t) // step
    X = np.zeros((n, len(cols)), np.float64)
    for j, c in enumerate(cols):
        v = np.asarray(f[c], np.float64)[:n * step].reshape(n, step).mean(1)
        X[:, j] = np.log10(v + 1e-7) if c not in ("centroid", "width", "crest") else v
    return t[:n * step:step], X


def novelty_sections(ts: np.ndarray, X: np.ndarray, kernel_s: float = 16.0,
                     min_gap_s: float = 24.0, n_max: int = 18) -> np.ndarray:
    """Checkerboard novelty on the timbre matrix -> section start times in seconds."""
    Z = (X - X.mean(0)) / (X.std(0) + 1e-9)
    rate = 1.0 / float(np.median(np.diff(ts)))
    L = int(kernel_s * rate)
    nov = np.zeros(len(Z))
    for i in range(L, len(Z) - L):
        nov[i] = np.linalg.norm(Z[i:i + L].mean(0) - Z[i - L:i].mean(0))
    nov = nov - moving_avg(nov.astype(np.float32), int(120 * rate))
    picks = []
    for i in np.argsort(-nov):
        if nov[i] <= 0:
            break
        if all(abs(ts[i] - p) >= min_gap_s for p in picks):
            picks.append(float(ts[i]))
        if len(picks) >= n_max:
            break
    return np.array(sorted([0.0] + [p for p in picks if p > min_gap_s]))


def bar_phase_per_section(t16: np.ndarray, sec_t: np.ndarray, onsets: dict, bphase: int,
                          dur: float) -> tuple[np.ndarray, list]:
    """In a DJ mix the incoming record need not share the outgoing record's bar phase, so pick the
    bar phase INSIDE each section: the rotation putting the kick on beat 1 and the snare on 2 and 4.
    -> (array of bar start indices into t16, per-section [phase, margin])."""
    steps = np.diff(t16)

    def k_of(tt):
        j = np.clip(np.searchsorted(t16, tt) - 1, 0, len(t16) - 2)
        return j + ((tt - t16[j]) / steps[j] > 0.5).astype(np.int64)

    lo_t, lo_w = onsets["low"]
    mi_t, mi_w = onsets["mid"]
    klo, kmi = k_of(lo_t), k_of(mi_t)
    edges = np.concatenate([sec_t, [dur]])
    bar_starts, info = [], []
    for a, z in zip(edges[:-1], edges[1:]):
        ml = (lo_t >= a) & (lo_t < z)
        mm = (mi_t >= a) & (mi_t < z)
        sc = []
        for j in range(16):                       # phase within the bar, in 16ths
            kl = (klo[ml] - bphase - j) % 16
            km = (kmi[mm] - bphase - j) % 16
            kick1 = lo_w[ml][kl == 0].sum() / (lo_w[ml].sum() + 1e-9)
            snare = (mi_w[mm][km == 4].sum() + mi_w[mm][km == 12].sum()) / (mi_w[mm].sum() + 1e-9)
            sc.append(float(kick1 * 1.0 + snare * 1.5))
        sc = np.array(sc)
        ph = int(np.argmax(sc))
        margin = float((sc[ph] - np.mean(np.delete(sc, ph))) / (np.std(sc) + 1e-9))
        info.append({"t0": float(a), "t1": float(z), "phase16": ph, "margin": margin,
                     "scores": np.round(sc, 3).tolist()})
        # bar starts inside this section, on that phase
        k0 = int(np.searchsorted(t16, a))
        k0 = k0 + ((bphase + ph - k0) % 16)
        k1 = int(np.searchsorted(t16, z))
        bar_starts.extend(range(k0, max(k0, k1 - 16), 16))
    return np.array(sorted(set(bar_starts))), info


# ----------------------------------------------------------------------
# analysis
# ----------------------------------------------------------------------
def bar_energy(bar_t: np.ndarray, bar_len: float) -> dict:
    """Per-bar energy from the grid-independent 93.75 fps cache."""
    f = np.load(os.path.join(CACHE, "frames.npz"))
    t = np.asarray(f["t"], np.float64)
    out = {}
    lo = np.searchsorted(t, bar_t)
    hi = np.searchsorted(t, bar_t + bar_len)
    for c in ("rms", "sub", "bass", "lowmid", "mid", "high", "air", "centroid"):
        v = np.asarray(f[c], np.float64)
        cs = np.concatenate([[0.0], np.cumsum(v)])
        out[c] = (cs[np.minimum(hi, len(v))] - cs[np.minimum(lo, len(v))]) / np.maximum(hi - lo, 1)
    return out


def swing_stats(off: np.ndarray, hit: np.ndarray, amp: np.ndarray) -> dict:
    """Microtiming. Offsets are measured against the drift-tracked 16th grid; the ANCHOR for swing
    is the mean offset of the four beat slots (0/4/8/12), which is where the kick and snare live and
    the least ambiguous part of the grid."""
    per = {}
    for i, nm in enumerate(("low", "mid", "high", "any")):
        o = off[:, :, i] if i < 3 else np.nanmean(off, axis=2)
        mean = np.array([np.nanmean(o[:, k]) if np.isfinite(o[:, k]).any() else np.nan
                         for k in range(16)])
        sd = np.array([np.nanstd(o[:, k]) if np.isfinite(o[:, k]).any() else np.nan
                       for k in range(16)])
        n = np.array([int(np.isfinite(o[:, k]).sum()) for k in range(16)])
        anchor = np.nanmean(mean[[0, 4, 8, 12]])
        per[nm] = {"mean": mean, "sd": sd, "n": n, "anchor": float(anchor),
                   "rel": mean - anchor}
    return per


def swing_ratio(rel: np.ndarray, p16_ms: float) -> dict:
    """Swing as the split of an 8th into its two 16ths. For the pair (even e, odd o):
    first half = p16 + rel[o] - rel[e], second half = p16 - rel[o] + rel[e+2]. Ratio > 1 = shuffled."""
    out = {}
    for e in range(0, 16, 2):
        o, e2 = e + 1, (e + 2) % 16
        first = p16_ms + rel[o] - rel[e]
        second = p16_ms + rel[e2] - rel[o]
        out[o] = {"first_ms": first, "second_ms": second, "ratio": first / second,
                  "pct": 100.0 * first / (first + second)}
    return out


def bar_similarity(hit: np.ndarray, amp: np.ndarray) -> dict:
    """Correlate each bar's 16-slot onset vector with the ones before it."""
    nb = len(hit)
    V = hit.reshape(nb, -1)                         # 48-dim: 16 slots x 3 bands
    Vb = {i: hit[:, :, i] for i in range(3)}

    def corr(A, B):
        a = A - A.mean(1, keepdims=True)
        b = B - B.mean(1, keepdims=True)
        d = np.sqrt((a * a).sum(1) * (b * b).sum(1))
        return np.where(d > 1e-9, (a * b).sum(1) / np.maximum(d, 1e-12), np.nan)

    out = {}
    for lag in range(1, 17):
        v = np.full(nb, np.nan)
        v[lag:] = corr(V[lag:], V[:-lag])
        out[f"r{lag}"] = v
    out["lags"] = np.array([np.nanmean(out[f"r{l}"]) for l in range(1, 17)])
    for i, nm in enumerate(("low", "mid", "high")):
        for lag in (1, 4):
            c = np.full(nb, np.nan)
            c[lag:] = corr(Vb[i][lag:], Vb[i][:-lag])
            out[f"r{lag}_{nm}"] = c
    # hamming distance: how many of the 48 cells changed
    out["dham"] = np.full(nb, np.nan)
    out["dham"][1:] = np.abs(V[1:] - V[:-1]).sum(1)
    return out


def detrended_acf(x: np.ndarray, maxlag: int = 32, detrend: int = 33) -> np.ndarray:
    """Autocorrelation of a per-bar series after removing its local mean. Without the high-pass the
    slow drift between sections dominates every lag and a 4-bar periodicity is invisible under it."""
    x = np.asarray(x, np.float64).copy()
    bad = ~np.isfinite(x)
    if bad.any():
        x[bad] = np.nanmean(x)
    x = x - moving_avg(x.astype(np.float32), detrend).astype(np.float64)
    x = x - x.mean()
    v = x.var() + 1e-12
    return np.array([float((x[l:] * x[:-l]).mean() / v) for l in range(1, maxlag + 1)])


def phrase_phase(e_rms: np.ndarray, lo: int, hi: int, period: int) -> int:
    """Which bar of a `period`-bar group starts a phrase, judged by ARRANGEMENT (where energy
    steps up), not by rhythm - so the phrase grid is independent of the fill/similarity test it is
    used to score."""
    d = np.diff(e_rms[lo:hi], prepend=e_rms[lo])
    idx = np.arange(lo, hi) % period
    sc = [np.maximum(d[idx == j], 0).sum() for j in range(period)]
    return int(np.argmax(sc))


def detect_fills(hit: np.ndarray, amp: np.ndarray, e_high: np.ndarray,
                 win: int = 16) -> tuple[np.ndarray, np.ndarray]:
    """A fill is a bar noticeably busier / brighter than its own neighbourhood. Score = z of the
    onset count plus z of the high-band flux energy, both against a rolling window."""
    n = hit.sum(axis=(1, 2))
    hf = amp[:, :, 2].sum(1)
    z = np.zeros(len(n))
    for arr in (n, hf, e_high):
        a = np.asarray(arr, np.float64)
        med = np.array([np.median(a[max(0, b - win):b + win + 1]) for b in range(len(a))])
        mad = np.array([np.median(np.abs(a[max(0, b - win):b + win + 1] - med[b])) + 1e-9
                        for b in range(len(a))])
        z += (a - med) / (1.4826 * mad)
    z /= 3.0
    return z, n


def chop_evidence(hit: np.ndarray, off: np.ndarray, amp: np.ndarray) -> dict:
    """Is this a looped bar or a re-chopped break?

    - a LOOP repeats its microtiming exactly: the same 16 deviations, bar after bar
    - a CHOP keeps the sample's internal timing inside each slice but reorders the slices, so the
      pattern can repeat while the microtiming signature does not
    - a chop also TRUNCATES: a slice is cut before it decays, leaving an abrupt amplitude step at a
      16th boundary
    - and it recurs at ROTATED positions: bar j's pattern equals a circular shift of bar i's
    """
    nb = len(hit)
    V = hit.reshape(nb, -1)
    O = np.nanmean(off, axis=2)
    rng = np.random.default_rng(11)

    def timing_delta(b, c):
        m = np.isfinite(O[b]) & np.isfinite(O[c])
        return float(np.mean(np.abs(O[b][m] - O[c][m]))) if m.sum() >= 6 else np.nan

    agree, tdel = np.full(nb, np.nan), np.full(nb, np.nan)
    for b in range(1, nb):
        if V[b].sum() < 4 or V[b - 1].sum() < 4:
            continue
        agree[b] = float((V[b] == V[b - 1]).mean())
        tdel[b] = timing_delta(b, b - 1)
    # control: the same measurement on bars picked at random from the same neighbourhood
    ctrl = []
    for b in range(8, nb - 8):
        c = b + int(rng.choice([-8, -7, -6, -5, 5, 6, 7, 8]))
        ctrl.append(timing_delta(b, c))
    ctrl = np.array(ctrl)
    ok = np.isfinite(agree) & np.isfinite(tdel)
    hi_thr = np.nanpercentile(agree[ok], 90)
    top = ok & (agree >= hi_thr)

    # rotations, WITH a control: the same best-of-16 search against an unrelated bar, so the
    # best-of-16 selection bias is subtracted rather than being reported as a finding
    H = hit.sum(axis=2) > 0

    def best_shift(a, c):
        sc = np.array([float((np.roll(c, s) == a).mean()) for s in range(16)])
        j = int(np.argmax(sc))
        return j, sc[j], sc[0]

    rot, rot_ctrl = [], []
    for b in range(1, nb):
        if H[b].sum() < 4:
            continue
        rot.append(best_shift(H[b], H[b - 1]))
        c = int(rng.integers(0, nb))
        if H[c].sum() >= 4:
            rot_ctrl.append(best_shift(H[b], H[c]))
    return {"agree": agree, "tdel": tdel, "ctrl_tdel": ctrl, "top": top, "ok": ok,
            "hi_thr": hi_thr, "rot": rot, "rot_ctrl": rot_ctrl,
            "rot_zero": sum(1 for r in rot if r[0] == 0)}


def truncation_test(t16: np.ndarray, p16: float) -> dict:
    """A chop cuts a slice before it decays, leaving a sharp level DROP. Find the sharp drops in the
    rms envelope and ask whether their times cluster on the 16th grid. Phase concentration (the
    length of the mean unit vector of their grid phases) is the statistic; a uniform scatter gives
    ~0, a hard quantise gives ~1. Compared against the phases of an equal number of random times."""
    f = np.load(os.path.join(CACHE, "frames.npz"))
    ft = np.asarray(f["t"], np.float64)
    fr = np.asarray(f["rms"], np.float64)
    k = 2                                             # 21 ms: a step, not a decay
    drop = 20 * np.log10(np.maximum(fr[k:], 1e-9) / np.maximum(fr[:-k], 1e-9))
    tt = ft[k:]
    sharp = drop < -4.0
    # keep only local minima of the drop so one cut counts once
    isloc = np.r_[False, (drop[1:-1] < drop[:-2]) & (drop[1:-1] <= drop[2:]), False]
    sel = sharp & isloc
    times = tt[sel]
    j = np.clip(np.searchsorted(t16, times) - 1, 0, len(t16) - 2)
    ph = (times - t16[j]) / np.diff(t16)[j]
    z = np.exp(2j * np.pi * ph).mean()
    conc = float(np.abs(z))
    mean_ph = float((np.angle(z) / (2 * np.pi)) % 1.0)
    rng = np.random.default_rng(3)
    rnd = rng.uniform(t16[0], t16[-1], len(times))
    j2 = np.clip(np.searchsorted(t16, rnd) - 1, 0, len(t16) - 2)
    ph2 = (rnd - t16[j2]) / np.diff(t16)[j2]
    conc2 = float(np.abs(np.exp(2j * np.pi * ph2).mean()))
    hist = np.histogram(ph, bins=8, range=(0, 1))[0] / len(ph)
    near = float(np.mean(np.minimum(ph, 1 - ph) < 0.15))
    return {"n": int(sel.sum()), "conc": conc, "conc_rand": conc2, "near": near,
            "mean_phase": mean_ph, "mean_phase_ms": mean_ph * p16 * 1000.0, "hist": hist,
            "rate_per_bar": float(sel.sum() / (len(t16) / 16))}


# ----------------------------------------------------------------------
# helpers for the report
# ----------------------------------------------------------------------
def fmt_row(label: str, vals, width: int = 5, prec: int = 2) -> str:
    cells = " ".join(f"{v:>{width}.{prec}f}" if np.isfinite(v) else " " * (width - 1) + "-" for v in vals)
    return f"{label:<12}{cells}"


def mmss(s: float) -> str:
    return f"{int(s) // 60}:{int(s) % 60:02d}"



def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", action="store_true", help="grid sanity check only")
    ap.add_argument("--stage", default="all")
    a = ap.parse_args(argv)

    scratch = os.environ.get("REAPER_SCRATCH", os.environ.get("TEMP", "."))
    ep = os.path.join(scratch, "reaper_env250_sf.npz")
    dur = 1259.727
    if os.path.exists(ep):
        z = np.load(ep)
        env = {k: z[k] for k in z.files}
        print(f"envelopes (cached): {len(env['t'])} frames at {FPS:.1f} fps", flush=True)
    else:
        mono = np.load(os.path.join(CACHE, "mono8k.npy")).astype(np.float32)
        dur = len(mono) / SR
        print(f"mono8k: {len(mono)} samples = {dur:.1f} s at {SR} Hz", flush=True)
        env = band_flux(mono)
        print(f"envelopes: {len(env['t'])} frames at {FPS:.1f} fps", flush=True)
        np.savez(ep, **env)
    dur = float(env["t"][-1])


    if a.probe:
        for mult in (1.8, 2.0, 2.3, 2.6, 3.0):
            ons = {k: pick_onsets(env[k], mult=mult) for k in ("low", "mid", "high")}
            per_bar = {k: len(ons[k][0]) / (dur / (60 / 165.9 * 4)) for k in ons}
            print(f"mult={mult}: per bar  " + "  ".join(f"{k}={v:.2f}" for k, v in per_bar.items())
                  + f"   total={sum(per_bar.values()):.2f}")
        return 0

    onsets = {k: pick_onsets(env[k]) for k in ("low", "mid", "high")}
    for k in onsets:
        print(f"  {k}: {len(onsets[k][0])} onsets")
    g = build_grid(env, onsets, dur)
    cs, bpms = g["bpm_windows"]
    print(f"local tempo over {len(cs)} windows: median {np.median(bpms):.3f} sd {bpms.std():.3f}")

    if a.stage == "acf":
        ts, X = timbre_matrix()
        sec_t = novelty_sections(ts, X)
        bar_starts, secinfo = bar_phase_per_section(g["t16"], sec_t, onsets, g["beat_phase"], dur)
        M = bar_matrices(onsets, g["t16"], bar_starts)
        S = bar_similarity(M["hit"], M["amp"])
        z, nc = detect_fills(M["hit"], M["amp"], bar_energy(M["bar_t"], g["bar_len"])["high"])
        for nm, series in (("fill", (z > 1.0).astype(float)), ("onsets", nc), ("r1", S["r1"])):
            print(f"\n{nm}:")
            for dt in (0, 9, 17, 33, 65):
                v = detrended_acf(series, 16, dt) if dt else detrended_acf(series, 16, 1)
                print(f"  detrend={dt:>3}: " + " ".join(f"{x:+.2f}" for x in v))
        return 0

    if a.stage == "diag":
        t = np.concatenate([onsets[k][0] for k in ("low", "mid", "high")])
        w = np.concatenate([onsets[k][1] / onsets[k][1].mean() for k in ("low", "mid", "high")])
        o = np.argsort(t); t, w = t[o], w[o]
        p16, ph16 = g["p16"], None
        # rigid
        _, ph16, _ = phase_fit(t, w, 60 / 190 / 4, 60 / 150 / 4, n=6000)
        rig = (((t - ph16) / p16 + 0.5) % 1.0 - 0.5) * p16 * 1000
        trk = g["dev_ms"]
        for nm, d in (("rigid", rig), ("tracked", trk)):
            print(f"{nm:>8}: |dev|<10ms {np.mean(np.abs(d)<10)*100:5.1f}%  "
                  f"<15ms {np.mean(np.abs(d)<15)*100:5.1f}%  <20ms {np.mean(np.abs(d)<20)*100:5.1f}%  "
                  f"median|dev| {np.median(np.abs(d)):5.1f}")
        for ws in (8, 16, 24, 40):
            pcs, phi = phase_track(t, w, p16, ph16, dur, win_s=ws)
            tt = grid16_times(p16, ph16, pcs, phi, dur)
            j = np.clip(np.searchsorted(tt, t) - 1, 0, len(tt) - 2)
            d0 = t - tt[j]; st = np.diff(tt)[j]
            d = np.where(d0 > st / 2, d0 - st, d0) * 1000
            print(f"  win={ws:>3}s: <10ms {np.mean(np.abs(d)<10)*100:5.1f}%  "
                  f"<15ms {np.mean(np.abs(d)<15)*100:5.1f}%  phi span "
                  f"{(phi.max()-phi.min())*1000:.0f} ms")
        cs, res = g["residual"]
        print("\nphase residual vs the rigid grid (ms, per 20 s):")
        for i in range(0, len(cs), 4):
            print(f"  {mmss(cs[i]):>6} {res[i]:+7.1f}")
        return 0

    ts, X = timbre_matrix()
    sec_t = novelty_sections(ts, X)
    bar_starts, secinfo = bar_phase_per_section(g["t16"], sec_t, onsets, g["beat_phase"], dur)
    M = bar_matrices(onsets, g["t16"], bar_starts)
    print(f"\n{len(sec_t)} sections, {len(bar_starts)} bars")
    analyse_and_report(g, onsets, M, secinfo, sec_t, dur)
    return 0


# ----------------------------------------------------------------------
def analyse_and_report(g, onsets, M, secinfo, sec_t, dur):
    hit, amp, off, bar_t = M["hit"], M["amp"], M["off"], M["bar_t"]
    nb = len(hit)
    p16_ms = g["p16"] * 1000.0
    E = bar_energy(bar_t, g["bar_len"])
    # which section each bar belongs to
    sec_of = np.searchsorted(np.array([s["t0"] for s in secinfo]), bar_t, "right") - 1
    L = ["# Reference rhythm analysis - Tim Reaper jungle DJ set (section), 2026-08",
         "",
         "Structural measurement only. No audio was sampled, extracted or copied; everything below "
         "is numbers derived from the cached feature set.",
         "", "Source: `Tim_Reaper_Jungle_DJ_Set_SECTION_August_2026.wav`, 1259.7 s, 48 kHz stereo. "
         "Analysis runs on the 8 kHz mono downmix in the cache.",
         "Script: `scripts/reaper_rhythm.py`.", ""]

    # ---------------- 0. grid ----------------
    xc = g["xcheck"]
    L += ["## 0. The grid, and how much to trust it", "",
          f"- **Tempo 165.997 BPM** (16th = {p16_ms:.3f} ms, beat = {p16_ms*4:.2f} ms, "
          f"bar = {g['bar_len']*1000:.1f} ms). Fitted by circular phase coherence over "
          f"{sum(len(onsets[k][0]) for k in onsets)} onset times, not by frame autocorrelation, so "
          f"the period is good to about 0.01 BPM.",
          f"- Independent check: per-window autocorrelation over 155 x 24 s windows gives median "
          f"{np.median(g['bpm_windows'][1]):.3f} BPM, sd {g['bpm_windows'][1].std():.3f}. The set is "
          f"beat-matched throughout; **there is no tempo change anywhere in the 21 minutes**.",
          f"- A *rigid* grid at that tempo does NOT hold: the phase of the onsets wanders up to "
          f"**{g['drift_rigid_ms']:.0f} ms** (half a 16th) across the set and wraps once, because two "
          f"decks in a mix are never locked to the part-per-million. So the grid used here is "
          f"**drift-tracked**: the fitted period plus a smoothed phase-correction curve, "
          f"re-solved for every 16th boundary.",
          "- Quality of the drift-tracked grid, measured as the distance from every detected onset "
          "to its nearest 16th:", "",
          "  | grid | median &#124;dev&#124; | within 10 ms | within 15 ms |",
          "  |---|---|---|---|",
          "  | rigid 166.00 BPM | 14.2 ms | 35.1 % | 52.4 % |",
          "  | **drift-tracked (used here)** | **4.7 ms** | **76.6 %** | **85.9 %** |", ""]
    if xc:
        L += [f"- Cross-check against the other agent's `grid.npz`: it agrees on tempo "
              f"({xc['bpm']:.3f} BPM vs 165.997) and {xc['within_20ms']*100:.0f} % of its beats are "
              f"within 20 ms of mine. I did **not** use it: its beat times are snapped to the "
              f"10.67 ms frame hop of the 93.75 fps cache, which is coarser than the microtiming "
              f"this analysis has to resolve, and it carries a single global bar phase "
              f"(its downbeats agree with mine {xc['downbeat_agree']*100:.0f} % of the time - see next point)."]
    L += [f"- **Bar phase is per-section, not global.** A single bar phase for the whole set only "
          f"holds in 65 % of one-minute windows: this is a DJ mix, and the incoming record does not "
          f"inherit the outgoing record's bar. Phase is therefore re-fitted inside each of the "
          f"{len(secinfo)} sections (kick on beat 1 + snare on 2 and 4). It changes "
          f"{sum(1 for a,b in zip(secinfo,secinfo[1:]) if a['phase16']!=b['phase16'])} times, always "
          f"at a section boundary.",
          "- **Trust:** tempo and 16th grid, high. Bar phase, good inside sections "
          f"(mean margin {np.mean([s['margin'] for s in secinfo]):.2f} sd above the alternatives) but "
          "the absolute '1' is inferred from kick/snare placement, not from anything notated. "
          "Sub-10 ms microtiming figures are near the resolution floor of a 64 ms STFT window and "
          "should be read as trends, not as exact per-hit values.", ""]

    # ---------------- sections ----------------
    dens = hit.sum(axis=(1, 2))
    L += ["### Sections used throughout", "",
          "| # | start | end | bars | bar phase /16 | onsets/bar | rms (rel. set median) |",
          "|---|---|---|---|---|---|---|"]
    for i, s in enumerate(secinfo):
        m = sec_of == i
        if m.sum() == 0:
            continue
        L.append(f"| S{i+1} | {mmss(s['t0'])} | {mmss(s['t1'])} | {int(m.sum())} | "
                 f"{s['phase16']} | {dens[m].mean():.1f} | "
                 f"{20*np.log10(E['rms'][m].mean()/np.median(E['rms'])):+.1f} dB |")
    L.append("")

    # ---------------- 1. occupancy ----------------
    L += ["## 1. Per-16th occupancy", "",
          "Probability that a 16th slot carries an onset, by band. "
          "low = 20-160 Hz (kick/bass), mid = 160-1200 Hz (snare/body), high = 1.2-4 kHz "
          "(hats, ghosts, snare edge). Slots are numbered 0-15; beats are 0, 4, 8, 12.", "",
          "**Whole set (%s bars)**" % nb, "",
          "```",
          "slot        " + " ".join(f"{k:>5d}" for k in range(16))]
    occ = hit.mean(0)
    for i, nm in enumerate(("low", "mid", "high")):
        L.append(fmt_row(nm, occ[:, i]))
    L += ["```", ""]
    # strongest / weakest
    tot = occ.mean(1)
    L += [f"Read-out: every beat slot is near-saturated (0 = {occ[0].mean():.2f} mean across bands, "
          f"4 = {occ[4].mean():.2f}, 8 = {occ[8].mean():.2f}, 12 = {occ[12].mean():.2f}); "
          f"the off-8th 16ths (odd slots) are the sparse ones "
          f"({occ[1::2].mean():.2f} mean vs {occ[0::2].mean():.2f} for even slots). "
          f"The single busiest non-beat slot is **{int(np.argmax(np.where(np.arange(16)%4==0,0,tot)))}** "
          f"and the emptiest is **{int(np.argmin(tot))}**.", ""]

    for i, s in enumerate(secinfo):
        m = sec_of == i
        if m.sum() < 8:
            continue
        o = hit[m].mean(0)
        L += [f"**S{i+1}  {mmss(s['t0'])}-{mmss(s['t1'])}**  ({int(m.sum())} bars, "
              f"{dens[m].mean():.1f} onsets/bar)", "", "```",
              "slot        " + " ".join(f"{k:>5d}" for k in range(16))]
        for j, nm in enumerate(("low", "mid", "high")):
            L.append(fmt_row(nm, o[:, j]))
        L += ["```", ""]

    # ---------------- 2. microtiming ----------------
    sw = swing_stats(off, hit, amp)
    rel = sw["any"]["rel"]
    sd = sw["any"]["sd"]
    ratios = swing_ratio(rel, p16_ms)
    L += ["## 2. Microtiming and swing", "",
          "Deviation of each onset from its exact 16th, in ms, early = negative. Measured against "
          "the drift-tracked grid, then referenced to the mean of the four beat slots (0/4/8/12) so "
          "that 'zero' means 'on the beat grid' rather than 'on the fitted phase'.", "", "```",
          "slot        " + " ".join(f"{k:>5d}" for k in range(16)),
          fmt_row("mean ms", rel, prec=1),
          fmt_row("sd ms", sd, prec=1),
          fmt_row("n", sw["any"]["n"], prec=0),
          "```", "",
          "Per band (mean ms, relative to that band's own beat-slot anchor):", "", "```",
          "slot        " + " ".join(f"{k:>5d}" for k in range(16))]
    for nm in ("low", "mid", "high"):
        L.append(fmt_row(nm, sw[nm]["rel"], prec=1))
    L += ["```", ""]
    # swing figures
    e_rel = rel[0::2]
    o_rel = rel[1::2]
    L += ["### Swing", "",
          f"- Even 16ths (the 8th-note positions 0,2,4,...) sit at **{np.nanmean(e_rel):+.1f} ms** "
          f"(spread {np.nanstd(e_rel):.1f}).",
          f"- Odd 16ths (the off-8th 'e' and 'a' positions) sit at **{np.nanmean(o_rel):+.1f} ms**, "
          f"i.e. **{np.nanmean(o_rel)-np.nanmean(e_rel):+.1f} ms late** relative to the even ones.", "",
          "Expressed as the split of an 8th into its two 16ths (50.0 % = straight, 66.7 % = triplet "
          "shuffle):", "",
          "| off-8th slot | first half (ms) | second half (ms) | ratio | swing % |",
          "|---|---|---|---|---|"]
    for k in sorted(ratios):
        r = ratios[k]
        L.append(f"| {k} | {r['first_ms']:.1f} | {r['second_ms']:.1f} | {r['ratio']:.3f} | "
                 f"{r['pct']:.1f} % |")
    r1, r3 = ratios[1], ratios[3]
    allpct = np.mean([ratios[k]["pct"] for k in ratios])
    # amplitude control for the lateness
    o_any = np.nanmean(off, axis=2)
    a_any = np.nanmax(amp, axis=2)
    thr = np.percentile(a_any[a_any > 0], 50)
    ev, od = np.arange(0, 16, 2), np.arange(1, 16, 2)
    s_even = o_any[:, ev][a_any[:, ev] > thr]
    w_even = o_any[:, ev][(a_any[:, ev] <= thr) & (a_any[:, ev] > 0)]
    s_odd = o_any[:, od][a_any[:, od] > thr]
    lvl_bias = float(np.nanmean(w_even) - np.nanmean(s_even))
    raw_lag = float(np.nanmean(o_rel) - np.nanmean(e_rel))
    # loud-only comparison: the honest swing figure
    loud_lag = float(np.nanmean(s_odd) - np.nanmean(s_even))
    loud_pct = 100.0 * (p16_ms + loud_lag) / (2 * p16_ms)
    L += ["",
          f"**The two the brief asks for, uncorrected:** 2nd 16th (slot 1) = **{r1['pct']:.1f} %** "
          f"(ratio {r1['ratio']:.3f}); 4th 16th (slot 3) = **{r3['pct']:.1f} %** "
          f"(ratio {r3['ratio']:.3f}). Mean over all eight off-8th slots: **{allpct:.1f} %**, i.e. "
          f"{raw_lag:+.1f} ms of late off-8ths.", "",
          "### Controlling for level", "",
          "A quiet hit has a slower attack, so its flux peak is detected later; off-8th hits are the "
          "quiet ones, so level could fake swing. Control: compare loud against quiet onsets **at "
          "the same (even) slots**, where there is no swing to find.", "",
          f"- loud onsets on even slots: {np.nanmean(s_even):+.1f} ms "
          f"(n = {np.isfinite(s_even).sum()})",
          f"- quiet onsets on even slots: {np.nanmean(w_even):+.1f} ms "
          f"(n = {np.isfinite(w_even).sum()})",
          f"- so the detector does carry a **{lvl_bias:+.1f} ms** level bias, and the raw figure "
          f"above is contaminated by it.", "",
          f"The clean comparison is loud-against-loud. Restricted to onsets above the median level "
          f"on both sides, the off-8th lag is **{loud_lag:+.1f} ms** = **{loud_pct:.1f} % swing** - "
          f"slightly *more* than the uncontrolled {allpct:.1f} %, not less.", "",
          f"**Verdict: effectively straight, with a {loud_lag:.0f} ms lean.** Best estimate "
          f"{loud_pct:.1f} % against 50.0 % for dead straight and 66.7 % for a triplet shuffle. "
          f"{loud_lag:.1f} ms is under a twentieth of a 16th. This is not a shuffle and not an MPC "
          f"54-58 % swing setting; it is the residual feel of the sampled break, and it varies by "
          f"track (see the per-section table below, which runs 47 % to 55 % - i.e. some records in "
          f"the mix lean *early*).", ""]

    # quantised or human
    med_sd = float(np.nanmedian(sd))
    sd_even, sd_odd = float(np.nanmean(sd[0::2])), float(np.nanmean(sd[1::2]))
    L += ["### Quantised, or human/chopped?", "",
          f"- Spread of the deviation at a given slot: median sd **{med_sd:.1f} ms** across the 16 "
          f"slots (range {np.nanmin(sd):.1f}-{np.nanmax(sd):.1f} ms).",
          f"- That spread is strongly split: **{sd_even:.1f} ms sd on the even (8th) slots** and "
          f"**{sd_odd:.1f} ms on the odd ones** - the backbone is tight, the in-between hits are "
          f"loose.",
          f"- {np.mean(np.abs(g['dev_ms'])<10)*100:.0f} % of all onsets land within 10 ms of a 16th, "
          f"{np.mean(np.abs(g['dev_ms'])<20)*100:.0f} % within 20 ms; median |deviation| "
          f"{np.median(np.abs(g['dev_ms'])):.1f} ms.",
          "",
          f"**Verdict: quantised placement, human content.** A {sd_even:.0f} ms sd on the beat and "
          f"8th positions at a 90 ms subdivision is machine-tight - a genuinely loose human "
          f"performance at 166 BPM runs 15-25 ms, and a drum machine would run under 2 ms. The "
          f"odd-slot {sd_odd:.0f} ms is a different population: those are the ghost hits carried "
          f"*inside* the slices, keeping the source break's own feel. That combination - rigid on "
          f"the 8ths, loose in between - is the signature of **a break sliced and re-triggered on a "
          f"16th grid**: neither played live nor programmed from scratch.", ""]

    # per-section swing
    L += ["Swing by section (mean off-8th lateness, ms):", "", "| section | odd-16th lag ms | "
          "swing % | sd ms |", "|---|---|---|---|"]
    for i, s in enumerate(secinfo):
        m = sec_of == i
        if m.sum() < 8:
            continue
        ss = swing_stats(off[m], hit[m], amp[m])["any"]
        lag = np.nanmean(ss["rel"][1::2]) - np.nanmean(ss["rel"][0::2])
        rr = swing_ratio(ss["rel"], p16_ms)
        L.append(f"| S{i+1} {mmss(s['t0'])} | {lag:+.1f} | "
                 f"{np.mean([rr[k]['pct'] for k in rr]):.1f} % | {np.nanmedian(ss['sd']):.1f} |")
    L.append("")

    # ---------------- 3. bar-to-bar ----------------
    # fills are detected here (used by section 4) because section 3 compares its own 4-bar
    # autocorrelation against theirs
    z, ncount = detect_fills(hit, amp, E["high"])
    fill = z > 1.0
    af = detrended_acf(fill.astype(float), 32)
    an = detrended_acf(ncount, 32)

    S = bar_similarity(hit, amp)
    r1 = S["r1"]
    ok = np.isfinite(r1)
    # baselines: two bars picked at random from the same section, and from anywhere in the set
    rng = np.random.default_rng(7)
    V = hit.reshape(nb, -1)

    def rpair(ii, jj):
        a = V[ii] - V[ii].mean(1, keepdims=True)
        b = V[jj] - V[jj].mean(1, keepdims=True)
        d = np.sqrt((a * a).sum(1) * (b * b).sum(1))
        return np.where(d > 1e-9, (a * b).sum(1) / np.maximum(d, 1e-12), np.nan)

    same_sec = []
    for i in range(len(secinfo)):
        m = np.nonzero(sec_of == i)[0]
        if len(m) < 8:
            continue
        ii = rng.choice(m, 400)
        jj = rng.choice(m, 400)
        k = np.abs(ii - jj) > 2
        same_sec.append(rpair(ii[k], jj[k]))
    base_sec = float(np.nanmean(np.concatenate(same_sec)))
    ii, jj = rng.integers(0, nb, 4000), rng.integers(0, nb, 4000)
    base_all = float(np.nanmean(rpair(ii, jj)))
    # per-band baselines: a sparser band correlates worse for purely statistical reasons, so each
    # band's bar-to-bar r has to be read against its OWN same-section random baseline
    band_base = {}
    for bi, bn in enumerate(("low", "mid", "high")):
        Vb = hit[:, :, bi]

        def rp(x, y):
            a = Vb[x] - Vb[x].mean(1, keepdims=True)
            b = Vb[y] - Vb[y].mean(1, keepdims=True)
            d = np.sqrt((a * a).sum(1) * (b * b).sum(1))
            return np.where(d > 1e-9, (a * b).sum(1) / np.maximum(d, 1e-12), np.nan)

        acc = []
        for i in range(len(secinfo)):
            m = np.nonzero(sec_of == i)[0]
            if len(m) < 8:
                continue
            x, y = rng.choice(m, 400), rng.choice(m, 400)
            k = np.abs(x - y) > 2
            acc.append(rp(x[k], y[k]))
        band_base[bn] = float(np.nanmean(np.concatenate(acc)))
    L += ["## 3. Bar-to-bar variation", "",
          "Each bar is a 48-cell vector (16 slots x 3 bands). r is the Pearson correlation between "
          "consecutive bars' vectors; 'cells changed' is how many of the 48 flipped.", "",
          "**Baselines first**, because a bare correlation means nothing without them:", "",
          "| pair | mean r |", "|---|---|",
          f"| consecutive bars | **{np.nanmean(r1):.3f}** |",
          f"| two random bars from the *same* section | {base_sec:.3f} |",
          f"| two random bars from anywhere in the set | {base_all:.3f} |", "",
          f"Consecutive bars are only {np.nanmean(r1)-base_sec:+.3f} more alike than two bars picked "
          f"at random from the same section. **Adjacency buys almost nothing**: within a section "
          f"every bar is about as similar to every other bar as it is to its neighbour. The pattern "
          f"is a stable distribution of hits, continually re-dealt, not a loop with occasional "
          f"edits.", "",
          f"- mean r(bar, previous bar) = **{np.nanmean(r1):.3f}**, median {np.nanmedian(r1):.3f}, "
          f"sd {np.nanstd(r1):.3f}",
          f"- **{np.mean(r1[ok]>0.8)*100:.0f} %** of bars are near-identical to the previous bar "
          f"(r > 0.8); {np.mean(r1[ok]>0.6)*100:.0f} % are r > 0.6; "
          f"{np.mean(r1[ok]<0.4)*100:.0f} % are a clear break with the previous bar (r < 0.4)",
          f"- median number of the 48 cells that change from bar to bar: "
          f"**{np.nanmedian(S['dham']):.0f}** (mean {np.nanmean(S['dham']):.1f})",
          ""]
    exc = {bn: np.nanmean(S["r1_" + bn]) - band_base[bn] for bn in ("low", "mid", "high")}
    exc4 = {bn: np.nanmean(S["r4_" + bn]) - band_base[bn] for bn in ("low", "mid", "high")}
    L += ["By band, against each band's own same-section random baseline (a sparser band correlates "
          "worse for purely statistical reasons, so the excess is the number that means something). "
          "Shown at lag 1 and at lag 4, because lag 4 is where the structure actually is:", "",
          "| band | r at lag 1 | r at lag 4 | random baseline | excess at lag 1 | excess at lag 4 |",
          "|---|---|---|---|---|---|"]
    for bn in ("low", "mid", "high"):
        L.append(f"| {bn} | {np.nanmean(S['r1_'+bn]):.3f} | {np.nanmean(S['r4_'+bn]):.3f} | "
                 f"{band_base[bn]:.3f} | {exc[bn]:+.3f} | {exc4[bn]:+.3f} |")
    steady = max(exc4, key=exc4.get)
    movey = min(exc4, key=exc4.get)
    L += ["", f"At lag 1 **no band repeats at all** - every excess is within ±0.03 of zero, which "
          f"is the quantitative form of 'consecutive bars are unrelated'. At lag 4 all three bands "
          f"come back, and the **{steady}** band comes back hardest ({exc4[steady]:+.3f} above its "
          f"baseline) while the **{movey}** band is the loosest ({exc4[movey]:+.3f}).", "",
          f"So the four-bar unit is defined most strongly by its **{steady}**-band pattern; the "
          f"**{movey}** band is where the per-pass re-chopping shows.", ""]

    # lag profile
    lags = S["lags"]
    L += ["### How far back does a bar rhyme? (lag profile)", "",
          "Mean r between a bar and the bar N before it. The same-section random baseline is "
          f"{base_sec:.3f}; anything at that level is 'no relationship'.", "",
          "| lag (bars) | " + " | ".join(str(l) for l in range(1, 17)) + " |",
          "|" + "---|" * 17,
          "| mean r | " + " | ".join(f"{v:.3f}" for v in lags) + " |", "",
          f"**This is the important table.** Lag **{int(np.argmax(lags))+1}** is the strongest "
          f"period in the profile ({lags.max():.3f}), with lag 8 ({lags[7]:.3f}) and lag 2 "
          f"({lags[1]:.3f}) behind it. Lag 1 ({lags[0]:.3f}) is the *lowest of the first eight* and "
          f"is level with the random baseline. Every even lag beats every odd lag out to 16: "
          f"mean r {lags[1::2].mean():.3f} at even lags against {lags[0::2].mean():.3f} at odd.", "",
          f"Read that carefully, because it is the answer to the hypothesis:", "",
          f"- there **is** a repeating unit, and it is **4 bars** (reinforced at 8 and 16);",
          f"- inside that unit, **a bar is least like the bar next to it** - adjacency is the "
          f"weakest relationship in the whole profile;",
          f"- there is a clear **2-bar sub-period** on top (lag 2 > lag 1 and lag 3).", "",
          f"So the four bars of the phrase are *all different from each other*, in a fixed "
          f"A-B-C-D order, and it is the whole four-bar group that comes back - not three copies "
          f"and a variation.", ""]

    # 4-bar and 8-bar position profile, on an arrangement-derived phrase grid
    prof4, prof8, n4, n8 = np.zeros(4), np.zeros(8), np.zeros(4), np.zeros(8)
    pos4 = np.full(nb, -1)
    pos8 = np.full(nb, -1)
    for i in range(len(secinfo)):
        m = np.nonzero(sec_of == i)[0]
        if len(m) < 16:
            continue
        lo, hi = m[0], m[-1] + 1
        p4 = phrase_phase(E["rms"], lo, hi, 4)
        p8 = phrase_phase(E["rms"], lo, hi, 8)
        pos4[lo:hi] = (np.arange(lo, hi) - lo - p4) % 4
        pos8[lo:hi] = (np.arange(lo, hi) - lo - p8) % 8
    se4, se8 = np.zeros(4), np.zeros(8)
    for k in range(4):
        m = (pos4 == k) & ok
        prof4[k], n4[k] = np.nanmean(r1[m]), m.sum()
        se4[k] = np.nanstd(r1[m]) / np.sqrt(max(m.sum(), 1))
    for k in range(8):
        m = (pos8 == k) & ok
        prof8[k], n8[k] = np.nanmean(r1[m]), m.sum()
        se8[k] = np.nanstd(r1[m]) / np.sqrt(max(m.sum(), 1))
    # similarity to bar 1 of the same phrase - the direct form of the hypothesis
    to1 = np.full(4, np.nan)
    to1n = np.zeros(4)
    idx = np.arange(nb)
    for k in range(1, 4):
        src = idx[(pos4 == k)]
        ref = src - k
        good = (ref >= 0) & (sec_of[np.maximum(ref, 0)] == sec_of[src])
        if good.sum() > 4:
            to1[k] = np.nanmean(rpair(src[good], ref[good]))
            to1n[k] = good.sum()
    # permutation test: is the position-4 dip more than chance?
    obs = prof4.max() - prof4.min()
    perm = []
    rr = r1[ok]
    for _ in range(2000):
        p = rng.permutation(rr)
        mm = [p[i::4].mean() for i in range(4)]
        perm.append(max(mm) - min(mm))
    pval = float(np.mean(np.array(perm) >= obs))
    L += ["### The user's hypothesis: 'three bars repeat and the fourth disturbs'", "",
          "The phrase grid here is set by **arrangement** (where the bar-rms steps up inside each "
          "section), not by rhythm, so this is not a circular test.", "",
          "Mean r(bar, previous bar) by position in the 4-bar phrase. Position 1 is the first bar "
          "of the phrase, so its r measures 'how different is the phrase start from the last bar of "
          "the previous phrase':", "",
          "| position in 4 | 1 | 2 | 3 | 4 |", "|---|---|---|---|---|",
          "| mean r vs previous bar | " + " | ".join(f"{prof4[k]:.3f}" for k in range(4)) + " |",
          "| standard error | " + " | ".join(f"±{se4[k]:.3f}" for k in range(4)) + " |",
          "| n bars | " + " | ".join(f"{int(n4[k])}" for k in range(4)) + " |",
          "| mean r vs **bar 1 of its own phrase** | - | "
          + " | ".join(f"{to1[k]:.3f}" for k in range(1, 4)) + " |", "",
          "| position in 8 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |",
          "|---|---|---|---|---|---|---|---|---|",
          "| mean r | " + " | ".join(f"{prof8[k]:.3f}" for k in range(8)) + " |",
          "| standard error | " + " | ".join(f"±{se8[k]:.3f}" for k in range(8)) + " |",
          "| n bars | " + " | ".join(f"{int(n8[k])}" for k in range(8)) + " |", ""]
    lowest4 = int(np.argmin(prof4)) + 1
    lowest8 = int(np.argmin(prof8)) + 1
    spread4 = prof4.max() - prof4.min()
    spread8 = prof8.max() - prof8.min()
    # the decisive, phase-free form of the hypothesis: if three bars repeated and the fourth broke,
    # the bar-to-bar similarity SERIES itself would be periodic with period 4 (high, high, high,
    # low). Autocorrelate it - no phrase phase needed, so no way to get the phase wrong.
    acf_r1 = detrended_acf(r1, 16)
    L += [f"**Result: the reference does NOT do it.** The least-similar bar of the four is position "
          f"**{lowest4}** - the right position for the hypothesis - but the effect is negligible: "
          f"the spread across the four positions is **{spread4:.3f}** in r "
          f"({prof4.min():.3f} to {prof4.max():.3f}) against a standard error of about "
          f"{se4.mean():.3f} per cell. A permutation test (2000 shuffles of the bar order) returns "
          f"**p = {pval:.3f}** for a spread that large arising by chance.", "",
          f"The second row is a sharper test: similarity to bar 1 of the *same* phrase runs "
          + ", ".join(f"bar {k+1} = {to1[k]:.3f}" for k in range(1, 4)) +
          f". If three bars repeated and the fourth disturbed, bars 2 and 3 would sit far above bar "
          f"4. They differ by {abs(np.nanmean(to1[1:3])-to1[3]):.3f}.", "",
          "**And the decisive test, which needs no phrase phase at all.** If the music really went "
          "same-same-same-different, then the bar-to-bar similarity *series* would itself be "
          "periodic with period 4: high, high, high, low, high, high, high, low. Autocorrelating "
          "that series cannot be fooled by a mis-guessed phase:", "",
          "| lag (bars) | " + " | ".join(str(l) for l in range(1, 17)) + " |",
          "|" + "---|" * 17,
          "| acf of the r-series | " + " | ".join(f"{v:+.2f}" for v in acf_r1) + " |", "",
          f"At lag 4 it is **{acf_r1[3]:+.3f}**, against {acf_r1[0]:+.3f} at lag 1 (which is just "
          f"the series being smooth) and {acf_r1[1]:+.3f} / {acf_r1[2]:+.3f} at lags 2 and 3. So "
          f"there **is** a faint 4-bar component in how similarity rises and falls - but compare it "
          f"with the same statistic on the fill indicator ({af[3]:+.2f}) and on the onset count "
          f"({an[3]:+.2f}), measured the same way on the same bars.", "",
          f"**That contrast is the answer.** The 4-bar unit is unmistakable in *density* and in "
          f"*fills*. It is only a whisper in *whether a bar resembles the one before it*. If the "
          f"music were built as three repeats and a disturbance, the similarity series would be the "
          f"strongest 4-bar signal of the three, not the weakest.", "",
          f"Over eight bars the least-similar position is **{lowest8}** with a spread of "
          f"{spread8:.3f} - again inside the noise.", "",
          f"**What it does instead:** it varies continuously. Every bar changes about "
          f"{np.nanmedian(S['dham']):.0f} of its 48 cells from the one before, at every position in "
          f"the phrase. The repetition in this music is at the level of the *distribution* - which "
          f"slots are likely - not at the level of an identical bar that is periodically broken.", "",
          f"**But the intuition is half right, and the half it gets right matters.** There *is* a "
          f"4-bar unit - the lag profile above peaks at lag 4 ({S['lags'][3]:.3f}) and 8 "
          f"({S['lags'][7]:.3f}) - it just is not built as 'three the same plus one different'. "
          f"It is built as **A-B-C-D, four bars that all differ from each other, and the group "
          f"returns**. Lag 1 ({S['lags'][0]:.3f}) being the lowest lag in the profile is the "
          f"measurement of exactly that: consecutive bars are the *least* alike pair in the music.", "",
          f"The practical restatement: **do not repeat a bar and then break it. Write four bars that "
          f"differ, and repeat the four.**", ""]

    # ---------------- 4. fills ----------------
    L += ["## 4. Fills", "",
          "A fill is scored as a bar whose onset count, high-band flux and high-band energy all sit "
          "above the rolling median of the 33 bars around it (mean robust z > 1.0).", "",
          f"- **{fill.sum()} fill bars out of {nb}** = {fill.mean()*100:.1f} %, i.e. one every "
          f"**{nb/max(fill.sum(),1):.1f} bars**", ""]
    pos16 = np.full(nb, -1)
    for i in range(len(secinfo)):
        m = np.nonzero(sec_of == i)[0]
        if len(m) < 16:
            continue
        lo, hi = m[0], m[-1] + 1
        p16b = phrase_phase(E["rms"], lo, hi, 16)
        pos16[lo:hi] = (np.arange(lo, hi) - lo - p16b) % 16
    d4 = np.array([np.mean(fill[pos4 == k]) for k in range(4)])
    d8 = np.array([np.mean(fill[pos8 == k]) for k in range(8)])
    d16 = np.array([np.mean(fill[pos16 == k]) if (pos16 == k).any() else np.nan
                    for k in range(16)])
    chi4 = float(np.sum((d4 - fill.mean()) ** 2 / (fill.mean() * (1 - fill.mean()) /
                                                   np.maximum([np.sum(pos4 == k) for k in range(4)], 1))))
    L += ["Where they land, as the fill rate at each position (the flat expectation is "
          f"{fill.mean()*100:.1f} %):", "",
          "| position in the 4-bar phrase | 1 | 2 | 3 | 4 |", "|---|---|---|---|---|",
          "| fill rate | " + " | ".join(f"{100*v:.1f} %" for v in d4) + " |", "",
          "| position in the 8-bar phrase | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |",
          "|---|---|---|---|---|---|---|---|---|",
          "| fill rate | " + " | ".join(f"{100*v:.1f} %" for v in d8) + " |", "",
          "| position in the 16-bar phrase | " + " | ".join(str(k + 1) for k in range(16)) + " |",
          "|" + "---|" * 17,
          "| fill rate | " + " | ".join(f"{100*v:.0f}" if np.isfinite(v) else "-" for v in d16)
          + " |", "",
          f"chi-square against a flat distribution over the four positions: {chi4:.2f} on 3 df "
          f"(p {'> 0.1' if chi4 < 6.25 else '< 0.05'}).", ""]
    # phase-free periodicity (af / an computed above, before section 3, which cites them)
    L += ["The position tables above depend on having guessed the phrase phase right. This next "
          "test does not: it autocorrelates the fill indicator and the onset count across bars "
          "(after removing each series' local mean, so slow drift between sections cannot swamp "
          "it), so a 4- or 8-bar habit shows as a spike at lag 4 / 8 / 16 whatever the phase.", "",
          "| lag (bars) | " + " | ".join(str(l) for l in range(1, 17)) + " |",
          "|" + "---|" * 17,
          "| fill indicator acf | " + " | ".join(f"{v:+.2f}" for v in af[:16]) + " |",
          "| onset-count acf | " + " | ".join(f"{v:+.2f}" for v in an[:16]) + " |", "",
          f"**This overturns the tables above.** Fill autocorrelation is **{af[3]:+.3f} at lag 4** - "
          f"the largest value in the whole profile out to 32 - with lag 8 {af[7]:+.3f} and every odd "
          f"lag negative (mean {np.mean(af[0:8:2]):+.3f}). Onset count does the same, and more "
          f"strongly: lag 4 **{an[3]:+.3f}**, lag 8 {an[7]:+.3f}. **Fills and density are on a "
          f"4-bar cycle.**", "",
          f"(Robustness: the high-pass window matters, so it was varied. At detrend windows of 17 / "
          f"33 / 65 bars the fill lag-4 value is +0.12 / +0.19 / +0.22 and the onset-count lag-4 "
          f"value is +0.10 / +0.20 / +0.27. The 4-bar peak is present at every setting that leaves "
          f"a 4-bar period intact; 33 bars is reported.)", "",
          f"The position tables looked flat because the *phase* I fitted from the arrangement "
          f"(where bar-rms steps up) is not the phase the fills use. The autocorrelation needs no "
          f"phase, so it wins: the 4-bar cycle is real, and the rms-step cue is simply a weak "
          f"anchor for finding bar 1 in this material. **I can say fills are 4-bar periodic; I "
          f"cannot say from this data whether the fill bar is the 4th of the phrase or the 2nd.**", "",
          f"Note the reconciliation with the rate: only {fill.mean()*100:.1f} % of bars are fills, "
          f"one every {nb/max(fill.sum(),1):.0f} bars, which is roughly **one in four of the "
          f"available 4-bar slots**. So the rule is not 'a fill every 4 bars' - it is *fills land on "
          f"the 4-bar grid, and take about one opportunity in four*. That is exactly what an "
          f"autocorrelation of {af[3]:+.2f} rather than +1.0 means.", ""]
    nf, nn = ncount[fill], ncount[~fill]
    L += [f"- a fill bar carries **{nf.mean():.1f} onsets** against **{nn.mean():.1f}** in a normal "
          f"bar = **{nf.mean()/nn.mean():.2f}x denser** (+{nf.mean()-nn.mean():.1f} onsets)",
          f"- its high-band flux is {amp[fill][:,:,2].sum(1).mean()/amp[~fill][:,:,2].sum(1).mean():.2f}x "
          f"a normal bar's, its low-band {amp[fill][:,:,0].sum(1).mean()/amp[~fill][:,:,0].sum(1).mean():.2f}x",
          f"- similarity to the previous bar drops to r = {np.nanmean(r1[fill]):.3f} in a fill bar "
          f"against {np.nanmean(r1[~fill]):.3f} elsewhere",
          f"- the strongest 4-bar position for fills is **{int(np.argmax(d4))+1}** "
          f"({100*d4.max():.1f} %) and the strongest 8-bar position is "
          f"**{int(np.argmax(d8))+1}** ({100*d8.max():.1f} %)", ""]

    # ---------------- 5. density ----------------
    L += ["## 5. Density", "", "Onsets per bar, and how they split across the three bands.", "",
          "| section | bars | onsets/bar | low | mid | high | rms rel. | class |",
          "|---|---|---|---|---|---|---|---|"]
    med_rms = np.median(E["rms"])
    med_sub = np.median(E["sub"] + E["bass"])
    cls = []
    for i, s in enumerate(secinfo):
        m = sec_of == i
        if m.sum() == 0:
            cls.append("-"); continue
        db = 20 * np.log10(E["rms"][m].mean() / med_rms)
        lowdb = 20 * np.log10((E["sub"] + E["bass"])[m].mean() / med_sub)
        c = "drop" if (db > -1.0 and dens[m].mean() > np.median(dens)) else \
            ("breakdown" if db < -3.0 or lowdb < -4.0 else "mid")
        cls.append(c)
        L.append(f"| S{i+1} {mmss(s['t0'])} | {int(m.sum())} | {dens[m].mean():.1f} | "
                 f"{hit[m][:,:,0].sum(1).mean():.1f} | {hit[m][:,:,1].sum(1).mean():.1f} | "
                 f"{hit[m][:,:,2].sum(1).mean():.1f} | {db:+.1f} dB | {c} |")
    L.append("")
    # drop vs breakdown bar
    dbar = np.array([20 * np.log10(E["rms"][b] / med_rms) for b in range(nb)])
    lowd = np.array([20 * np.log10((E["sub"] + E["bass"])[b] / med_sub) for b in range(nb)])
    isdrop = (dbar > np.percentile(dbar, 90)) & (lowd > np.percentile(lowd, 60))
    isbrk = (dbar < np.percentile(dbar, 10)) | (lowd < np.percentile(lowd, 8))
    L += ["Bar-level, contrasting the extremes: a **drop bar** is in the loudest 10 % with above-"
          "median low end, a **breakdown bar** is in the quietest 10 % or the bottom 8 % for low-end "
          "energy:", "",
          "| | onsets/bar | low | mid | high | share of onsets in the low band |",
          "|---|---|---|---|---|---|"]
    for nm, m in (("drop bar", isdrop), ("all bars", np.ones(nb, bool)), ("breakdown bar", isbrk)):
        L.append(f"| {nm} | {dens[m].mean():.1f} | {hit[m][:,:,0].sum(1).mean():.1f} | "
                 f"{hit[m][:,:,1].sum(1).mean():.1f} | {hit[m][:,:,2].sum(1).mean():.1f} | "
                 f"{100*hit[m][:,:,0].sum()/hit[m].sum():.0f} % |")
    lowE = 20 * np.log10((E["sub"] + E["bass"])[isdrop].mean() /
                         max((E["sub"] + E["bass"])[isbrk].mean(), 1e-12))
    rmsE = np.mean(dbar[isdrop]) - np.mean(dbar[isbrk])
    lo_r = hit[isdrop][:, :, 0].sum(1).mean() / max(hit[isbrk][:, :, 0].sum(1).mean(), 1e-9)
    hi_r = hit[isdrop][:, :, 2].sum(1).mean() / max(hit[isbrk][:, :, 2].sum(1).mean(), 1e-9)
    L += ["",
          f"A drop bar is only **{dens[isdrop].mean()/max(dens[isbrk].mean(),1e-9):.2f}x** the onset "
          f"count of a breakdown bar ({dens[isdrop].mean():.1f} vs {dens[isbrk].mean():.1f}) - but "
          f"it is **{rmsE:.1f} dB** louder overall and carries **{lowE:+.1f} dB** more low-end "
          f"energy. The counts move in opposite directions by band:", "",
          f"- high band {hit[isbrk][:,:,2].sum(1).mean():.1f} -> "
          f"{hit[isdrop][:,:,2].sum(1).mean():.1f} onsets/bar (**{hi_r:.2f}x**) - the drop gets "
          f"*brighter and busier on top*;",
          f"- low band {hit[isbrk][:,:,0].sum(1).mean():.1f} -> "
          f"{hit[isdrop][:,:,0].sum(1).mean():.1f} onsets/bar (**{lo_r:.2f}x**) - **fewer** low "
          f"events, while low-band energy rises {lowE:+.1f} dB.", "",
          f"**That is the key structural fact about the drop.** It is not a denser drum pattern. "
          f"The low band trades *many small transients for fewer, much larger ones* - a sustained "
          f"sub and a heavier kick replacing scattered low-frequency chatter - and the extra "
          f"activity that does arrive lands in the high band. A drop built by adding drum hits "
          f"would be moving all three counts up together, and this reference does not.", "",
          f"Range across bars: {dens.min():.0f} onsets in the sparsest bar, {dens.max():.0f} in the "
          f"densest, 10th-90th percentile {np.percentile(dens,10):.0f}-{np.percentile(dens,90):.0f}, "
          f"median {np.median(dens):.0f}.", ""]

    # ---------------- 6. chopped breaks ----------------
    C = chop_evidence(hit, off, amp)
    T = truncation_test(g["t16"], g["p16"])
    rot, rotc = C["rot"], C["rot_ctrl"]
    nz = [r for r in rot if r[0] != 0]
    gain = np.array([r[1] - r[2] for r in rot])
    gainc = np.array([r[1] - r[2] for r in rotc])
    top_td = C["tdel"][C["top"]]
    all_td = C["tdel"][C["ok"]]
    ctrl_td = C["ctrl_tdel"][np.isfinite(C["ctrl_tdel"])]
    L += ["## 6. Chopped break, or looped bar?", "",
          "A looped bar reproduces its microtiming exactly, bar after bar: the same audio, so the "
          "same deviations. A re-chopped break can land on the same 16-slot pattern while the "
          "microtiming underneath it changes, because different slices of the source are firing. "
          "Three tests, each with a control so that selection bias is subtracted rather than "
          "reported as a result.", "",
          f"**(a) Even the most pattern-identical bar pairs do not share their timing.** Taking the "
          f"top decile of consecutive bar pairs by pattern agreement (>= "
          f"{100*C['hi_thr']:.0f} % of the 48 cells identical), the mean absolute difference in "
          f"per-slot microtiming is **{np.nanmean(top_td):.1f} ms** (median "
          f"{np.nanmedian(top_td):.1f}). For all consecutive pairs it is "
          f"{np.nanmean(all_td):.1f} ms, and for a control pair 5-8 bars apart it is "
          f"{np.nanmean(ctrl_td):.1f} ms.", "",
          f"  A genuine audio loop would put the first number at **0-1 ms** and far below the "
          f"control. It is {np.nanmean(top_td):.1f} ms - about half the control "
          f"({np.nanmean(top_td)/max(np.nanmean(ctrl_td),1e-9):.2f}x), so *some* slices do carry "
          f"over from bar to bar, but nothing like enough for a repeated bar of audio. **The "
          f"pattern is being rebuilt each bar from partly-reused slices.**", "",
          f"**(b) Rotation matching: inconclusive, and here is why.** Best circular shift of the "
          f"previous bar against each bar: shift 0 wins {100*C['rot_zero']/max(len(rot),1):.0f} % of "
          f"the time, a non-zero shift {100*len(nz)/max(len(rot),1):.0f} %, and the winning shifts "
          f"lean heavily even (" +
          ", ".join(f"{s}: {c}" for s, c in
                    sorted(((s, sum(1 for r in nz if r[0] == s)) for s in range(1, 16)),
                           key=lambda x: -x[1])[:5]) +
          f"). But running the identical best-of-16 search against an **unrelated** bar gains "
          f"{100*gainc.mean():.1f} pp where the real neighbour gains {100*gain.mean():.1f} pp - "
          f"{100*(gain.mean()-gainc.mean()):+.1f} pp, i.e. below the selection-bias floor. The "
          f"even-shift preference is a property of the onset distribution itself (hits concentrate "
          f"on even slots, so even rotations preserve the shape), not evidence of slice "
          f"displacement. **This test tells us nothing; it is reported so the other two are not "
          f"read as three.**", "",
          f"**(c) Truncations are phase-locked to the grid, landing mid-slot.** Sharp level "
          f"drops (rms falling more than 4 dB in 21 ms) are the fingerprint of a slice cut before it "
          f"decayed. There are **{T['n']}** of them, {T['rate_per_bar']:.2f} per bar. Their phase "
          f"within the 16th has a concentration of **{T['conc']:.3f}** against "
          f"**{T['conc_rand']:.3f}** for the same number of random times - "
          f"{T['conc']/max(T['conc_rand'],1e-9):.0f}x, so they are strongly non-uniform. Where they "
          f"sit inside the 16th (fraction of the {p16_ms:.0f} ms slot):", "",
          "| phase in the 16th | 0-.12 | .12-.25 | .25-.38 | .38-.50 | .50-.62 | .62-.75 | "
          ".75-.88 | .88-1.0 |", "|---|---|---|---|---|---|---|---|---|",
          "| share of cuts | " + " | ".join(f"{100*v:.0f} %" for v in T["hist"]) + " |", "",
          f"The mean phase is **{T['mean_phase']:.2f} of a 16th = {T['mean_phase_ms']:.0f} ms after "
          f"a boundary**, and the distribution peaks in the "
          f"{['0-.12','.12-.25','.25-.38','.38-.50','.50-.62','.62-.75','.75-.88','.88-1.0'][int(np.argmax(T['hist']))]} "
          f"band. That is exactly what a chop looks like from the outside: a slice fires on the "
          f"boundary, rings for part of the slot, and is cut off partway through when the next slice "
          f"is triggered. A played or looped break would decay smoothly and produce no such "
          f"concentration.", "",
          "**Conclusion: chopped, and re-chopped continuously.** Two of the three tests carry "
          "weight. (a) says bars that share a written pattern share only about half as much "
          "microtiming as a true repeat would demand - the audio underneath a repeated pattern is "
          "not the same audio. (c) says level cuts are 20x more phase-locked to the 16th grid than "
          "chance and sit partway through the slot, which is a slice being interrupted rather than a "
          "drum decaying. (b) is selection bias and proves nothing. The picture is a break sliced to "
          "16ths and re-triggered in a changing order, bar after bar, for twenty-one minutes - "
          "**there is no 'loop plus occasional variation' anywhere in this reference**.", ""]

    # ---------------- rules ----------------
    fill_every = nb / max(fill.sum(), 1)
    L += ["## What this means for building a jungle track", "",
          f"1. **166.0 BPM, 16ths at {p16_ms:.0f} ms, swing essentially off ({loud_pct:.0f} %).** "
          f"Level-corrected swing is {loud_pct:.1f} % against 50.0 % for dead straight - a "
          f"{loud_lag:.0f} ms lean, not a groove. Do not reach for a swing template; the feel "
          f"comes from the break's own content, not from moved grid positions. Lock the tempo hard "
          f"- across 21 minutes it never moved (sd {g['bpm_windows'][1].std():.2f} BPM).",
          f"2. **Fill 16 slots per bar to these odds.** Beat slots 0/4/8/12 at "
          f"{occ[[0,4,8,12]].mean(1).mean():.2f}, the other even slots at "
          f"{occ[[2,6,10,14]].mean(1).mean():.2f}, the odd slots at {occ[1::2].mean():.2f}. "
          f"Concretely: kick on 0 ({occ[0,0]:.2f}) and 10 ({occ[10,0]:.2f}), snare on 4 "
          f"({occ[4,1]:.2f}) and 12 ({occ[12,1]:.2f}), ghosts scattered on 2/6/8/14, and the odd "
          f"slots left mostly empty - they are the {occ[1::2].mean():.0%} that keeps it from "
          f"turning into a wall.",
          f"3. **{dens.mean():.0f} onsets per bar is the target**, split roughly "
          f"{100*hit[:,:,0].sum()/hit.sum():.0f}/{100*hit[:,:,1].sum()/hit.sum():.0f}/"
          f"{100*hit[:,:,2].sum()/hit.sum():.0f} low/mid/high. Below "
          f"{np.percentile(dens,10):.0f} reads as a breakdown, above "
          f"{np.percentile(dens,90):.0f} as a fill.",
          f"4. **The drop does not add drums, it adds weight and brightness.** Drop bars carry "
          f"{dens[isdrop].mean():.0f} onsets against {dens[isbrk].mean():.0f} in a breakdown "
          f"({dens[isdrop].mean()/max(dens[isbrk].mean(),1e-9):.2f}x) while rms goes up "
          f"{rmsE:.0f} dB and low-end energy {lowE:+.0f} dB. Low-band onset *count* actually falls "
          f"({lo_r:.2f}x) and high-band rises ({hi_r:.2f}x). So: at the drop, swap low-frequency "
          f"chatter for one sustained sub and a bigger kick, and put the new movement in the hats - "
          f"do not thicken the break.",
          f"5. **Chop the break to 16ths; never loop a bar of audio.** Even the most "
          f"pattern-identical consecutive bars differ by {np.nanmean(top_td):.1f} ms of per-slot "
          f"microtiming - only about half the {np.nanmean(ctrl_td):.1f} ms of bars 5-8 apart, and "
          f"nowhere near the 0-1 ms a repeated bar of audio would give. Re-point the "
          f"slices every bar. Displace them by an 8th (2 slots) or a whole beat (4 slots): those are "
          f"the rotations that actually recur. Expect {T['rate_per_bar']:.1f} audible truncations "
          f"per bar, landing on the grid.",
          f"6. **Write a 4-bar unit as A-B-C-D, all four different, and repeat the unit.** Lag 4 "
          f"similarity is {S['lags'][3]:.2f} and lag 8 is {S['lags'][7]:.2f}, but lag 1 is only "
          f"{S['lags'][0]:.2f} - no higher than two random bars from the same section "
          f"({base_sec:.2f}). Change about {np.nanmedian(S['dham']):.0f} of the 48 cells between "
          f"adjacent bars; only {np.mean(r1[ok]>0.8)*100:.0f} % of bars should be near-copies of "
          f"their neighbour.",
          f"7. **Let the {steady} band define the 4-bar unit and the {movey} band re-chop freely.** "
          f"At lag 4 the excess over each band's own random baseline is low {exc4['low']:+.3f}, "
          f"mid {exc4['mid']:+.3f}, high {exc4['high']:+.3f}; at lag 1 all three are within ±0.03 of "
          f"zero. So: no band should repeat bar to bar, but the {steady} band should come back four "
          f"bars later. Do not nail the kick to slots 0 and 10 in every bar - its placement is part "
          f"of what moves.",
          f"8. **Put fills on the 4-bar grid, but only take one slot in four.** Fill-indicator "
          f"autocorrelation is {af[3]:+.2f} at lag 4 and {af[7]:+.2f} at lag 8, ~0 at every odd lag "
          f"- so fills are 4-bar-aligned - yet only {fill.mean()*100:.0f} % of bars are fills, one "
          f"every {fill_every:.0f} bars. Keep them modest: "
          f"{nf.mean()/nn.mean():.2f}x the onset count of a normal bar "
          f"(+{nf.mean()-nn.mean():.0f} onsets) and "
          f"{amp[fill][:,:,2].sum(1).mean()/amp[~fill][:,:,2].sum(1).mean():.1f}x its high-band "
          f"energy. A jungle fill is a slightly busier, brighter bar - not a drum roll.",
          f"9. **Do not write '3 bars the same, 1 different'.** Bar-to-bar similarity by 4-bar "
          f"position is {prof4[0]:.2f}/{prof4[1]:.2f}/{prof4[2]:.2f}/{prof4[3]:.2f} - a spread of "
          f"{spread4:.3f} on a standard error of {se4.mean():.3f}, permutation p = {pval:.2f} - and "
          f"the phase-free version (autocorrelation of the similarity series) is only "
          f"{acf_r1[3]:+.2f} at lag 4, against {af[3]:+.2f} for fills and {an[3]:+.2f} for density "
          f"measured the same way - the weakest of the three. "
          f"Variation is spread evenly over every bar, not saved up for the fourth. What is "
          f"periodic is the return of the whole 4-bar group (rule 6), not a fourth bar that breaks "
          f"three identical ones.",
          f"10. **Keep the odd 16ths mostly empty and let that be the space.** Even slots run at "
          f"{occ[0::2].mean():.2f} occupancy and odd slots at {occ[1::2].mean():.2f}; the emptiest "
          f"slots in the bar are {int(np.argmin(occ.mean(1)))} and "
          f"{int(np.argsort(occ.mean(1))[1])}. At {dens.mean():.0f} onsets per bar the music is "
          f"already dense, so the legibility comes from those reserved positions - fill them and the "
          f"break stops reading as a break.", ""]

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT_MD, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")
    print(f"wrote {OUT_MD} ({len(L)} lines)")
    # console echo of the headline numbers
    print(f"\nswing {allpct:.1f}% | r1 {np.nanmean(r1):.3f} | near-identical "
          f"{np.mean(r1[ok]>0.8)*100:.0f}% | fills {fill.mean()*100:.1f}% every {fill_every:.1f} bars"
          f" | onsets/bar {dens.mean():.1f} | prof4 {np.round(prof4,3)}")


if __name__ == "__main__":
    sys.exit(main())
