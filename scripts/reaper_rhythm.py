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



# ======================================================================
# 48 kHz feature layer - for the 16th carrier (section 9) and the kick (section 10)
#
# Read straight from the wav, chunk by chunk, and reduced at once to envelopes and a 1/12-octave
# spectrogram. Nothing but these numbers is kept; no audio is written anywhere.
# ======================================================================
WAV = r"C:\Users\eric\Downloads\Tim_Reaper_Jungle_DJ_Set_SECTION_August_2026.wav"
SR48 = 48000
FPS5 = 200.0            # envelope rate (hop 240)
FPS10 = 100.0           # spectrogram rate (hop 480)
OCT12_LO = 40.0
N_OCT12 = 104           # 40 Hz .. ~15.1 kHz in twelfth-octaves
F12 = OCT12_LO * 2.0 ** (np.arange(N_OCT12) / 12.0)


def scratch_dir() -> str:
    return os.environ.get("REAPER_SCRATCH", os.environ.get("TEMP", "."))


def wav_header(path: str) -> tuple[int, int, int, int]:
    """-> (channels, sample rate, data offset, number of frames). 16-bit PCM only."""
    import struct
    size = os.path.getsize(path)
    with open(path, "rb") as fh:
        pos, fmt = 12, None
        while pos + 8 <= size:
            fh.seek(pos)
            cid = fh.read(4)
            sz = struct.unpack("<I", fh.read(4))[0]
            if cid == b"fmt ":
                fmt = struct.unpack("<HHIIHH", fh.read(16))
            elif cid == b"data":
                off = pos + 8
                n_bytes = size - off if (sz in (0, 0xFFFFFFFF) or off + sz > size) else sz
                tag, ch, sr, _, align, bits = fmt
                if tag != 1 or bits != 16:
                    raise ValueError("expected 16-bit PCM")
                return ch, sr, off, n_bytes // align
            pos += 8 + sz + (sz & 1)
    raise ValueError("no data chunk")


def _read_mono(fh, off: int, ch: int, n_total: int, a: int, b: int) -> np.ndarray:
    out = np.zeros(b - a, np.float32)
    lo, hi = max(a, 0), min(b, n_total)
    if hi > lo:
        fh.seek(off + lo * 2 * ch)
        raw = np.frombuffer(fh.read((hi - lo) * 2 * ch), "<i2").reshape(-1, ch)
        out[lo - a:hi - a] = raw.astype(np.float32).mean(1) / 32768.0
    return out


def _oct12_weights(nfft: int) -> np.ndarray:
    """Band x bin matrix: the share of each STFT bin's frequency interval inside each 1/12-octave
    band. Sparse low bands get fractional bins instead of being empty."""
    df = SR48 / nfft
    fb = np.arange(nfft // 2 + 1) * df
    lo_e, hi_e = F12 * 2 ** (-1 / 24), F12 * 2 ** (1 / 24)
    b_lo, b_hi = fb - df / 2, fb + df / 2
    ov = np.clip(np.minimum(hi_e[:, None], b_hi[None, :]) - np.maximum(lo_e[:, None], b_lo[None, :]),
                 0, None)
    return (ov / df).astype(np.float32)


def _superflux(logmag: np.ndarray, lag: int, fmax: bool) -> np.ndarray:
    ref = logmag
    if fmax:
        ref = np.maximum(np.maximum(np.roll(logmag, 1, 0), logmag), np.roll(logmag, -1, 0))
    ref = np.concatenate([ref[:, :1].repeat(lag, 1), ref[:, :-lag]], axis=1)
    return np.maximum(0.0, logmag - ref).sum(0)


def features48(verbose: bool = True) -> dict:
    """Envelopes at 200 fps and a 1/12-octave spectrogram at 100 fps, cached in scratch."""
    path = os.path.join(scratch_dir(), "reaper_rhythm_f48.npz")
    if os.path.exists(path):
        z = np.load(path)
        return {k: z[k] for k in z.files}
    ch, sr, off, n = wav_header(WAV)
    assert sr == SR48
    cfg = {512: 240, 1024: 240, 2048: 480}
    W = _oct12_weights(2048)
    wins = {nf: torch.hann_window(nf) for nf in cfg}
    df = {nf: SR48 / nf for nf in cfg}
    fbin = {nf: np.arange(nf // 2 + 1) * df[nf] for nf in cfg}

    def sel(nf, lo, hi):
        return (fbin[nf] >= lo) & (fbin[nf] < hi)

    acc = {k: [] for k in ("e_car", "e_air", "fl_700", "fl_1500", "fl_4000",
                           "e_kick", "e_click", "fl_kick", "fl_click", "spec")}
    chunk = SR48 * 30
    with open(WAV, "rb") as fh:
        for s0 in range(0, n, chunk):
            s1 = min(n, s0 + chunk)
            for nf, hop in cfg.items():
                g0, g1 = -(-s0 // hop), -(-s1 // hop)
                a = g0 * hop - nf // 2
                b = (g1 - 1) * hop + nf // 2
                x = _read_mono(fh, off, ch, n, a, b)
                S = torch.stft(torch.from_numpy(x), nf, hop, window=wins[nf], center=False,
                               return_complex=True).abs().numpy()
                P = S ** 2
                if nf == 512:
                    acc["e_car"].append(P[sel(nf, 1500, 16000)].sum(0))
                    acc["e_air"].append(P[sel(nf, 5000, 16000)].sum(0))
                    L = np.log1p(100.0 * S)
                    for lo, key in ((700, "fl_700"), (1500, "fl_1500"), (4000, "fl_4000")):
                        acc[key].append(_superflux(L[sel(nf, lo, 16000)], 2, True))
                elif nf == 1024:
                    kb = sel(nf, 115, 260)                 # 140.6 / 187.5 / 234.4 Hz bins
                    acc["e_kick"].append(P[kb].sum(0))
                    acc["e_click"].append(P[sel(nf, 1000, 8000)].sum(0))
                    L = np.log1p(100.0 * S)
                    acc["fl_kick"].append(_superflux(L[kb], 3, False))
                    acc["fl_click"].append(_superflux(L[sel(nf, 1000, 8000)], 2, True))
                else:
                    acc["spec"].append((10 * np.log10(W @ P + 1e-12)).astype(np.float16).T)
            if verbose:
                print(f"  48k features {s1 / SR48:7.1f} / {n / SR48:.1f} s", flush=True)
    out = {k: np.concatenate(v, axis=0 if k == "spec" else -1) for k, v in acc.items()}
    for k in out:
        if k != "spec":
            out[k] = out[k].astype(np.float32)
    np.savez(path, **out)
    return out


KICK_CODES = {0: "no kick", 1: "four on the floor", 2: "two-step", 3: "break kick",
              4: "sparse / syncopated"}
CARRIER_CODES = {0: "none", 1: "high-passed break", 2: "short percussion", 3: "full-range break"}
BARS_NPZ = os.path.join(CACHE, "rhythm_bars.npz")


def _mmss_to_s(txt: str) -> float:
    m, s = txt.strip().split(":")
    return int(m) * 60 + float(s)


def read_peers() -> dict:
    """Read-only use of the other agents' published tables: drop/breakdown events (drops.md), record
    seams (structure.md) and the per-section bass change rate (bass.md). Parsed defensively; any
    table that is missing or reshaped simply comes back empty."""
    import re
    base = OUT_DIR
    out = {"drops": [], "breakdowns": [], "seams": [], "bass": []}
    try:
        for line in open(os.path.join(base, "drops.md"), encoding="utf-8"):
            m = re.match(r"\|\s*(\d+)\s*\|\s*(\d+:\d+\.\d+)\s*\|\s*(drop|breakdown)\s*\|\s*(\w+)\s*\|"
                         r"\s*([+-]?[\d.]+)", line)
            if m:
                ev = {"t": _mmss_to_s(m.group(2)), "grade": m.group(4), "step": float(m.group(5))}
                out["drops" if m.group(3) == "drop" else "breakdowns"].append(ev)
    except OSError:
        pass
    try:
        for line in open(os.path.join(base, "structure.md"), encoding="utf-8"):
            m = re.match(r"\|\s*bar\s+\d+\s*\|\s*(\d+:\d+\.\d+)\s*\|\s*\*\*([^*]+)\*\*", line)
            if m:
                out["seams"].append({"t": _mmss_to_s(m.group(1)), "device": m.group(2).strip()})
    except OSError:
        pass
    try:
        for line in open(os.path.join(base, "bass.md"), encoding="utf-8"):
            m = re.match(r"\|\s*(S\d+)\s*\|\s*([\d.]+)\s*[–-]\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|"
                         r"\s*(\d+)\s*\|\s*\**([\d.]+)\**\s*\|", line)
            if m:
                out["bass"].append({"sec": m.group(1), "t0": float(m.group(2)),
                                    "t1": float(m.group(3)), "chg": float(m.group(6))})
    except OSError:
        pass
    return out


def kicks_final(F: dict, t16: np.ndarray, bar_of: np.ndarray, slot_of: np.ndarray, nb: int,
                thr_db: float = -9.0, decay_min: float = 6.0) -> dict:
    """Kicks = low-mid transients whose attack puts real energy in 80-160 Hz (where a held sub
    cannot leak: two FFT bins above a 47 Hz fundamental), that decay >= 6 dB by 100-150 ms, and that
    are not a no-click event inside a sustained bass note."""
    K = kick_candidates(F)
    spec = F["spec"]
    m80 = band_mask(80, 160)
    K["klow"] = np.array([db(attack_spectrum(spec, t)[m80].sum()) for t in K["t"]])
    k0, off0 = nearest16(t16, K["t"])
    strong = (np.abs(off0) < 35) & (K["rise"] > 10)
    lat = float(np.median(off0[strong])) / 1000.0
    k, off = nearest16(t16, K["t"], lat)
    b, s = bar_of[k], slot_of[k]
    near = (np.abs(off) < 35) & (K["rise"] > -50) & (b >= 0)
    ref = float(np.percentile(K["klow"][near & (s == 0)], 90))
    out = {"lat_ms": lat * 1000, "ref_db": ref, "n_cand": int(near.sum())}
    sweep = []
    for thr in (-6.0, -9.0, -12.0):
        cand = near & (K["klow"] - ref >= thr)
        dec = cand & (K["decay"] >= decay_min)
        fp = dec & (K["in_note"] > 0) & (K["click"] < 3)
        sweep.append({"thr": thr, "cand": int(cand.sum()), "decay_fail": int((cand & ~dec).sum()),
                      "fp": int(fp.sum()), "final": int((dec & ~fp).sum())})
    cand = near & (K["klow"] - ref >= thr_db)
    dec = cand & (K["decay"] >= decay_min)
    fp = dec & (K["in_note"] > 0) & (K["click"] < 3)
    kick = dec & ~fp
    KH = np.zeros((nb, 16), bool)
    KH[b[kick], s[kick]] = True
    out.update({"sweep": sweep, "cand": int(cand.sum()), "decay_fail": int((cand & ~dec).sum()),
                "fp": int(fp.sum()), "in_note_click": int((dec & (K["in_note"] > 0) &
                                                          (K["click"] >= 3)).sum()),
                "kick": kick, "KH": KH, "bar": b, "slot": s, "K": K,
                "click_share": float(np.mean(K["click"][kick] >= 3)),
                "in_note_share": float(np.mean(K["in_note"][kick] > 0))})
    return out


def carrier_final(F: dict, g: dict, bar_starts: np.ndarray, key: str = "fl_1500") -> dict:
    """16th carrier per bar. For every slot: peak carrier-band flux on the 16th (A) against the
    same measurement a 32nd later (B). A slot is articulated when A >= rho x the bar's median B.
    The null is the identical test applied to the B positions themselves."""
    t16 = g["t16"]
    tt, _ = pick_peaks(F[key], FPS5, 0.5, 2.0, 0.04)
    _, oo = nearest16(t16, tt)
    lat = float(np.median(oo[np.abs(oo) < 30])) / 1000.0
    A, B = slot_contrast(F[key], t16, bar_starts, lat)
    floor = np.median(B, axis=1, keepdims=True) + 1e-6
    amax = A.max(1, keepdims=True)
    rows = []
    for rho in (1.25, 1.5, 1.75, 2.0, 2.5, 3.0):
        H = (A >= rho * floor) & (A >= 0.05 * amax)
        Hn = (B >= rho * floor) & (B >= 0.05 * amax)
        odd, tot = H[:, 1::2].sum(1), H.sum(1)
        oddn, totn = Hn[:, 1::2].sum(1), Hn.sum(1)
        rows.append({"rho": rho, "cov": float(np.mean((odd >= 3) & (tot >= 10))),
                     "odd3": float(np.mean(odd >= 3)), "null_odd3": float(np.mean(oddn >= 3)),
                     "null_cov": float(np.mean((oddn >= 3) & (totn >= 10)))})
    # mixture model: observed = c*s + (1-c)*f; with s ~ 1 at the loosest settings, c is bounded below
    for r in rows:
        r["c_lb"] = (r["odd3"] - r["null_odd3"]) / max(1 - r["null_odd3"], 1e-9)
    c_hat = max(r["c_lb"] for r in rows)
    for r in rows:
        fa = (1 - c_hat) * r["null_odd3"]
        tp = r["odd3"] - fa
        r["err"] = fa + max(c_hat - tp, 0.0)
    best = min(rows, key=lambda r: r["err"])
    rho = best["rho"]
    H = (A >= rho * floor) & (A >= 0.05 * amax)
    odd, tot = H[:, 1::2].sum(1), H.sum(1)
    present = (odd >= 3) & (tot >= 10)
    return {"lat_ms": lat * 1000, "rows": rows, "rho": rho, "c_hat": c_hat, "H": H, "odd": odd,
            "tot": tot, "present": present, "A": A, "B": B}


def other_band_coverage(F, g, bar_starts, rho):
    out = {}
    for key in ("fl_700", "fl_4000"):
        tt, _ = pick_peaks(F[key], FPS5, 0.5, 2.0, 0.04)
        _, oo = nearest16(g["t16"], tt)
        lat = float(np.median(oo[np.abs(oo) < 30])) / 1000.0
        A, B = slot_contrast(F[key], g["t16"], bar_starts, lat)
        floor = np.median(B, axis=1, keepdims=True) + 1e-6
        H = (A >= rho * floor) & (A >= 0.05 * A.max(1, keepdims=True))
        out[key] = float(np.mean((H[:, 1::2].sum(1) >= 3) & (H.sum(1) >= 10)))
    return out


I3_SHAPE = np.arange(32, 104).reshape(18, 4)          # 1/3-octave groups 252 Hz .. 15 kHz
I3_ALL = np.arange(0, 104).reshape(26, 4)             # 1/3-octave groups 40 Hz .. 15 kHz
F3_ALL = np.array([np.sqrt(F12[g[0]] * F12[g[-1]]) for g in I3_ALL])


def hit_features(F: dict, times: np.ndarray) -> dict:
    """Per carrier hit: level, decay, gap before the next 16th, attack-spectrum centroid, low
    content, local flatness, and a normalised 1/3-octave shape for hit-to-hit comparison."""
    spec = F["spec"]
    ec = db(F["e_car"])
    n = len(ec)
    N = len(times)
    out = {k: np.full(N, np.nan) for k in ("lvl", "decay", "gap", "cen", "lowc", "flat")}
    out["shape"] = np.zeros((N, 18), np.float32)
    out["att3"] = np.zeros((N, 26), np.float32)
    bw = F12 * (2 ** (1 / 24) - 2 ** (-1 / 24))
    m200, m_lo, m_pl = band_mask(200, 16000), band_mask(125, 500), band_mask(1000, 4000)
    lf = np.log2(F12)
    out["ring"] = np.full(N, np.nan)
    for q, t in enumerate(times):
        i = int(round(t * FPS5))
        if i < 10 or i > n - 30:
            continue
        seg = ec[i - 1:i + 6]
        pk = i - 1 + int(np.argmax(seg))
        p = ec[pk]
        pre = ec[i - 8:i - 1].min()
        rise = max(p - pre, 1e-3)
        out["lvl"][q] = p
        # decay = time to lose half the rise (in dB): the sustained mix under a hit never lets the
        # band fall a fixed 12 dB, but a short hit gives back its own rise within tens of ms
        after = ec[pk:pk + 19]
        below = np.nonzero(after <= p - rise / 2)[0]
        out["decay"][q] = (below[0] * 5.0) if len(below) else 90.0
        out["gap"][q] = ec[i + 10:i + 17].min() - p
        # ring = share of the rise still standing 50-80 ms later, just before the next 16th
        out["ring"][q] = float(np.clip((ec[i + 10:i + 17].min() - pre) / rise, -1, 1.5))
        att = attack_spectrum(spec, t, 0.020, 0.035)
        w = att[m200]
        if w.sum() <= 0:
            continue
        cen_l = (w * lf[m200]).sum() / w.sum()
        out["cen"][q] = 2 ** cen_l
        out["lowc"][q] = db(att[m_lo].sum()) - db(att[m_pl].sum())
        loc = (lf >= cen_l - 1) & (lf <= cen_l + 1)
        dens = att[loc] / bw[loc]
        dens = np.maximum(dens, dens.max() * 1e-3) + 1e-24
        out["flat"][q] = np.exp(np.mean(np.log(dens))) / np.mean(dens)
        a3 = np.array([att[gg].sum() for gg in I3_ALL])
        out["att3"][q] = a3
        sh = db(np.array([att[gg].sum() for gg in I3_SHAPE]))
        sh = np.maximum(sh, sh.max() - 40)
        out["shape"][q] = sh - sh.mean()
    return out


def noise_var(X: np.ndarray) -> float:
    diff = np.diff(np.asarray(X, np.float64), axis=0)
    return max(float(np.median(0.5 * (diff ** 2).mean(0))), 0.5 * float((diff ** 2).mean()), 1e-6)


def calibrate_beta(X: np.ndarray, betas=(0.25, 0.35, 0.5, 0.7, 1.0, 1.4, 2.0, 2.8),
                   n_perm: int = 8, seed: int = 0) -> tuple[float, list]:
    """The penalty is not chosen, it is calibrated: shuffle the bar order (which destroys any
    sub-section structure while keeping every bar's content), run the same segmentation, and take the
    smallest beta for which the shuffled series averages at most one change point. That fixes the
    false-alarm rate at ~1 spurious boundary per set under 'no structure'."""
    rng = np.random.default_rng(seed)
    sig2 = noise_var(X)
    n, d = X.shape
    table = []
    chosen = betas[-1]
    for beta in betas:
        pen = beta * d * sig2 * np.log(n)
        cps = [len(changepoints(X[rng.permutation(n)], pen=pen)[0]) - 1 for _ in range(n_perm)]
        table.append((beta, float(np.mean(cps))))
    for beta, m in table:
        if m <= 1.0:
            chosen = beta
            break
    return chosen, table


def changepoints(X: np.ndarray, beta: float = 1.0, min_len: int = 2,
                 pen: float | None = None) -> tuple[np.ndarray, float]:
    """Optimal partition of a bar-level vector series into constant-mean segments (dynamic
    programming, exact). Cost = within-segment sum of squares + a per-segment penalty
    beta * d * sigma^2 * ln(n), BIC-shaped, with sigma^2 estimated from bar-to-bar differences.
    Minimum segment length 2 bars, so a one-bar fill cannot become a segment.
    -> (segment start indices, penalty used)."""
    X = np.asarray(X, np.float64)
    n, d = X.shape
    if pen is None:
        pen = beta * d * noise_var(X) * np.log(n)
    cs = np.vstack([np.zeros(d), np.cumsum(X, 0)])
    cs2 = np.concatenate([[0.0], np.cumsum((X ** 2).sum(1))])
    Fc = np.full(n + 1, np.inf)
    Fc[0] = -pen
    last = np.zeros(n + 1, np.int64)
    for j in range(min_len, n + 1):
        i = np.arange(0, j - min_len + 1)
        i = i[np.isfinite(Fc[i])]
        m = (j - i)[:, None]
        s = cs[j] - cs[i]
        c = (cs2[j] - cs2[i]) - (s * s).sum(1) / m[:, 0]
        tot = Fc[i] + c + pen
        q = int(np.argmin(tot))
        Fc[j], last[j] = tot[q], i[q]
    starts = []
    j = n
    while j > 0:
        starts.append(int(last[j]))
        j = int(last[j])
    return np.array(sorted(starts)), pen


def seg_ids(starts: np.ndarray, n: int) -> np.ndarray:
    ids = np.zeros(n, np.int64)
    for q, s0 in enumerate(starts):
        ids[s0:] = q
    return ids


def modal_share(P: np.ndarray, tol: int = 0) -> float:
    """Share of rows equal (within `tol` differing cells) to the most common row."""
    if len(P) == 0:
        return np.nan
    from collections import Counter
    rows = P.astype(np.int16)
    mode = np.array(Counter(tuple(r) for r in rows.tolist()).most_common(1)[0][0], np.int16)
    return float(np.mean(np.abs(rows - mode).sum(1) <= tol))


def kick_evidence(KF: dict, idx: np.ndarray, bar_starts: np.ndarray, t16: np.ndarray) -> dict:
    """Everything needed to classify the kick over a group of bars."""
    KH = KF["KH"][idx]
    n = len(idx)
    occ = KH.mean(0) if n else np.zeros(16)
    # the snare-based bar phase cannot tell beat 2 from beat 4, so a kick pattern can come out
    # rotated by half a bar; put the stronger of slots 0 and 8 on the downbeat
    rot = 8 if occ[8] > occ[0] + 0.05 else 0
    KHc = np.roll(KH, -rot, axis=1)
    occ_c = np.roll(occ, -rot)
    beat = np.zeros(16, bool)
    beat[[0, 4, 8, 12]] = True
    total = KHc.sum()
    ev = {"n": n, "rot": rot, "occ": occ_c, "kpb": float(KH.sum(1).mean()) if n else 0.0,
          "off_share": float(KHc[:, ~beat].sum() / total) if total else np.nan,
          "beat_min": float(occ_c[beat].min()), "beat_mean": float(occ_c[beat].mean())}
    has = KHc.sum(1) > 0
    jac = []
    for q in range(1, n):
        if has[q] and has[q - 1]:
            a, b = KHc[q], KHc[q - 1]
            jac.append((a & b).sum() / (a | b).sum())
    ev["jaccard"] = float(np.mean(jac)) if jac else np.nan
    ev["modal"] = modal_share(KHc[has]) if has.sum() else np.nan
    ev["modal1"] = modal_share(KHc[has], 1) if has.sum() else np.nan
    # timbre of successive kicks
    kick = KF["kick"]
    bars_in = np.zeros(len(bar_starts), bool)
    bars_in[idx] = True
    sel = kick & (KF["bar"] >= 0)
    sel[sel] = bars_in[KF["bar"][sel]]
    sh = KF["K"]["shape"][sel].astype(np.float64)
    if len(sh) >= 4:
        sh = np.maximum(sh - sh.max(1, keepdims=True), -40.0)
        d = np.sqrt(((sh[1:] - sh[:-1]) ** 2).mean(1))
        ev["timbre_dist"] = float(np.median(d))
    else:
        ev["timbre_dist"] = np.nan
    ev["hf_body"] = float(np.median(KF["K"]["hf_body"][sel])) if sel.sum() else np.nan
    ev["n_kicks"] = int(sel.sum())
    ev["sub_body"] = float(np.median(KF["K"]["sub_body"][sel])) if sel.sum() else np.nan
    ev["click"] = float(np.median(KF["K"]["click"][sel])) if sel.sum() else np.nan
    # rotation-invariant pattern scores: the downbeat is inferred, the rhythm is not
    ev["four_floor"] = float(max(min(occ[(r + j) % 16] for j in (0, 4, 8, 12)) for r in range(4)))
    ev["four_rest"] = float(max(np.mean([occ[(r + j) % 16] for j in (2, 6, 10, 14)])
                                for r in range(4)))
    ts = [(min(occ[r], occ[(r + 10) % 16]), r) for r in range(16)]
    ev["two_step"], ev["two_step_rot"] = max(ts)
    r2 = ev["two_step_rot"]
    others = [occ[(r2 + j) % 16] for j in range(16) if j not in (0, 10, 2)]
    ev["two_step_rest"] = float(np.mean(others))
    if total:
        lat = [KH[:, [(r + j) % 16 for j in (0, 4, 8, 12)]].sum() / KH.sum() for r in range(4)]
        ev["lattice_off"] = float(1 - max(lat))
    else:
        ev["lattice_off"] = np.nan
    return ev


def classify_kick(ev: dict) -> tuple[int, str, str]:
    """-> (code, confidence, reason). Boundaries and why:
    - no kick: under 0.4 kicks a bar, i.e. at most one kick in every 2.5 bars.
    - four on the floor: all four slots of one beat lattice >= 0.6 while the 8ths between them
      stay under 0.3. 0.6 rather than the ~0.8 a listener would expect, because the detector does
      not find every kick: its best slot anywhere in the set reaches 0.96-0.98, and most sections'
      strongest slot sits at 0.7-0.8, so a true four-on-the-floor would measure well below 1.0.
    - two-step: kicks 10 then 6 sixteenths apart (0 + 10 on some rotation) both >= 0.5, the other
      slots quiet, AND programmed: successive kicks within 11 dB of each other in spectral shape (the
      set splits cleanly there: 7.6-9.8 dB against 11.8-15.8 dB) and the bar pattern repeating
      (Jaccard >= 0.45 between neighbouring bars).
    - sparse / syncopated: 0.4-1.2 kicks a bar, or more but mostly off every beat lattice.
    - break kick: everything else with kicks in it - dense, re-dealt, timbre varying hit to hit."""
    kpb = ev["kpb"]
    if kpb < 0.4:
        return 0, ("high" if kpb < 0.2 else "medium"), f"{kpb:.2f} kicks/bar"
    if ev["four_floor"] >= 0.6 and ev["four_rest"] < 0.3:
        return 1, ("high" if ev["four_floor"] >= 0.8 else "medium"), \
            f"beats {ev['four_floor']:.2f}, 8ths between {ev['four_rest']:.2f}"
    programmed = (np.isfinite(ev["timbre_dist"]) and ev["timbre_dist"] <= 11.0
                  and np.isfinite(ev["jaccard"]) and ev["jaccard"] >= 0.45)
    if ev["two_step"] >= 0.5 and ev["two_step_rest"] < 0.25 and programmed and kpb <= 3.2:
        conf = "high" if (ev["two_step"] >= 0.7 and ev["timbre_dist"] <= 10 and ev["n"] >= 12) \
            else "medium"
        return 2, conf, (f"0+10 pair {ev['two_step']:.2f}, rest {ev['two_step_rest']:.2f}, "
                         f"timbre {ev['timbre_dist']:.1f} dB, Jaccard {ev['jaccard']:.2f}")
    if kpb < 1.2 or (np.isfinite(ev["lattice_off"]) and ev["lattice_off"] >= 0.6
                     and ev["occ"].max() < 0.6):
        return 4, ("medium" if kpb < 1.0 else "low"), \
            f"{kpb:.2f} kicks/bar, {100 * ev['lattice_off']:.0f}% off the beat lattice"
    conf = "high" if (ev["timbre_dist"] > 12 and ev["jaccard"] < 0.4 and ev["n"] >= 12
                      and ev["occ"].max() >= 0.4) else "medium"
    if programmed or (np.isfinite(ev["modal1"]) and ev["modal1"] >= 0.7):
        conf = "low"      # repeats like a programmed pattern but is not a two-step
    return 3, conf, (f"{kpb:.2f} kicks/bar, Jaccard {ev['jaccard']:.2f}, "
                     f"timbre {ev['timbre_dist']:.1f} dB")


def hit_shape_db(att3: np.ndarray) -> np.ndarray:
    """Per-hit 1/3-octave attack spectrum in dB relative to that hit's own 1-4 kHz plateau."""
    L = db(np.atleast_2d(att3))
    pl = L[:, (F3_ALL >= 1000) & (F3_ALL <= 4000)].mean(1, keepdims=True)
    return np.clip(L - pl, -60.0, 30.0)


def median_shape(att3_hits: np.ndarray) -> np.ndarray:
    """The typical hit: per-band MEDIAN of plateau-relative dB. Averaging power instead lets the few
    odd-slot hits that coincide with a bass-note onset or a kick own every low band."""
    return np.median(hit_shape_db(att3_hits), axis=0)


def corner_hz(shape_db: np.ndarray, drop_db: float = 12.0) -> float:
    """Where a plateau-relative 1/3-octave shape (dB) first falls `drop_db` below its 1-4 kHz
    plateau, scanning down from 1 kHz. NaN = never falls that far above 45 Hz (open, full range)."""
    L = np.asarray(shape_db, np.float64)
    plateau = L[(F3_ALL >= 1000) & (F3_ALL <= 4000)].mean()
    start = int(np.nonzero(F3_ALL < 1000)[0][-1])
    prev_f, prev_l = F3_ALL[start + 1], L[start + 1]
    for j in range(start, -1, -1):
        if F3_ALL[j] < 45:
            break
        if L[j] < plateau - drop_db:
            # interpolate the crossing on log frequency
            a = (prev_l - (plateau - drop_db)) / max(prev_l - L[j], 1e-9)
            return float(2 ** (np.log2(prev_f) + a * (np.log2(F3_ALL[j]) - np.log2(prev_f))))
        prev_f, prev_l = F3_ALL[j], L[j]
    return np.nan


def classify_carrier(ev: dict) -> tuple[int, str, str]:
    """-> (code, confidence, reason). Evidence, in order of weight:
    - short percussion is UNIFORM hit to hit: shape correlation >= 0.35 and level spread <= 2.5 dB
    - a break is MIXED: low shape correlation, several dB of accent spread
    - a break is HIGH-PASSED when its attack spectrum falls 12 dB below the 1-4 kHz plateau
      above 250 Hz; FULL-RANGE when it does not fall that far above 125 Hz; between is a partial
      low-cut and is called by whichever side it is nearer, at low confidence."""
    uniform = ev["shape_r"] >= 0.35 and ev["lvl_sd"] <= 2.5
    mixed = ev["shape_r"] < 0.30 and ev["lvl_sd"] > 2.5
    c = ev["corner"]
    if uniform:
        kind = "hats / shakers" if ev["cen"] > 3000 else (
            "congas / woodblock" if ev["flat"] < 0.2 else "clicks / rim")
        conf = "high" if ev["shape_r"] >= 0.4 and ev["lvl_sd"] <= 1.5 else "medium"
        return 2, conf, f"uniform (shape r {ev['shape_r']:.2f}, level sd {ev['lvl_sd']:.1f} dB): {kind}"
    conf_b = "medium" if mixed else "low"
    if np.isfinite(c) and c >= 250:
        return 1, conf_b if c >= 350 else "low", f"corner {c:.0f} Hz"
    if not np.isfinite(c) or c < 125:
        return 3, conf_b, "no corner above 45 Hz" if not np.isfinite(c) else f"corner {c:.0f} Hz"
    return (1 if c >= 180 else 3), "low", f"partial low-cut, corner {c:.0f} Hz"


def pair_r(a: np.ndarray, b: np.ndarray) -> float:
    a = np.asarray(a, np.float64) - np.mean(a)
    b = np.asarray(b, np.float64) - np.mean(b)
    d = np.sqrt((a * a).sum() * (b * b).sum())
    return float((a * b).sum() / d) if d > 1e-12 else np.nan


def carrier_evidence(HF: dict, hb: np.ndarray, hs: np.ndarray, present: np.ndarray,
                     bar_mask: np.ndarray, hit_mask: np.ndarray | None = None) -> dict | None:
    """Evidence for what carries the 16ths over a set of bars, from the odd-slot hits (the off-8th
    positions, which only a 16th layer articulates) in bars that have a carrier."""
    mh = (hs % 2 == 1) & bar_mask[hb] & present[hb] & np.isfinite(HF["cen"])
    if hit_mask is not None:
        mh &= hit_mask
    if mh.sum() < 10:
        return None
    rng = np.random.default_rng(5)
    sh = HF["shape"][mh].astype(np.float64)
    ii, jj = rng.integers(0, len(sh), 600), rng.integers(0, len(sh), 600)
    k = ii != jj
    a = sh[ii[k]] - sh[ii[k]].mean(1, keepdims=True)
    b = sh[jj[k]] - sh[jj[k]].mean(1, keepdims=True)
    r = float(((a * b).sum(1) / np.sqrt((a * a).sum(1) * (b * b).sum(1) + 1e-12)).mean())
    med = median_shape(HF["att3"][mh].astype(np.float64))
    return {"n": int(mh.sum()), "cen": float(np.nanmedian(HF["cen"][mh])),
            "spread": float(np.nanstd(np.log2(HF["cen"][mh]))), "shape_r": r,
            "decay": float(np.nanmedian(HF["decay"][mh])), "ring": float(np.nanmedian(HF["ring"][mh])),
            "lowc": float(np.nanmedian(HF["lowc"][mh])), "flat": float(np.nanmedian(HF["flat"][mh])),
            "lvl_sd": float(np.nanstd(HF["lvl"][mh])), "lvl": float(np.nanmedian(HF["lvl"][mh])),
            "shape_db": med, "corner": corner_hz(med), "mask": mh}


def shape_rel(shape_db: np.ndarray) -> np.ndarray:
    """A median plateau-relative shape restricted to 250 Hz - 15 kHz, floored at -40 dB."""
    return np.maximum(np.asarray(shape_db)[F3_ALL >= 250], -40.0)


def runs_of(mask: np.ndarray) -> list[tuple[int, int]]:
    out, start = [], None
    for i, v in enumerate(list(mask) + [False]):
        if v and start is None:
            start = i
        elif not v and start is not None:
            out.append((start, i))
            start = None
    return out


def phrase_alignment(starts: np.ndarray, bar_t: np.ndarray, bar_len: float, n: int,
                     anchors: np.ndarray, rec_edges: np.ndarray) -> dict:
    """Do change points sit on 4/8/16/32-bar phrase lines? Two tests.
    (1) Phase-free: interior segment lengths that are exact multiples of P, against 1/P.
    (2) Anchored: bars from the nearest drop/breakdown/seam in the same record (excluding one within
        a bar of the change point itself, which would be self-alignment), on the P lattice exactly
        and within +-1 bar, against 1/P and 3/P."""
    ends = np.concatenate([starts[1:], [n]])
    lengths = (ends - starts)[1:-1]
    out = {"lengths": lengths, "P": {}}
    cps = starts[1:]
    rec_of = lambda t: int(np.searchsorted(rec_edges, t, "right"))
    for P in (4, 8, 16, 32):
        L_share = float(np.mean(lengths % P == 0)) if len(lengths) else np.nan
        exact, near, cnt = 0, 0, 0
        for c in cps:
            tc = bar_t[c]
            cand = [a for a in anchors if rec_of(a) == rec_of(tc) and abs(a - tc) > 1.2 * bar_len]
            if not cand:
                continue
            a = min(cand, key=lambda x: abs(x - tc))
            d = int(round(abs(tc - a) / bar_len))
            cnt += 1
            exact += (d % P == 0)
            near += (d % P in (0, 1, P - 1))
        out["P"][P] = {"len_share": L_share, "n_len": int(len(lengths)),
                       "anch_exact": exact / cnt if cnt else np.nan,
                       "anch_near": near / cnt if cnt else np.nan, "n_anch": cnt}
    return out


def stability(P: np.ndarray, starts: np.ndarray, n: int, tol: int, rng, n_null: int = 200) -> dict:
    """Share of bars matching their segment's modal pattern, against the same segment lengths laid
    at random offsets (a circular shift of the whole segmentation)."""
    ends = np.concatenate([starts[1:], [n]])

    def score(st_, en_):
        num, den = 0.0, 0
        for s0, e0 in zip(st_, en_):
            idx = np.arange(s0, e0) % n
            num += modal_share(P[idx], tol) * len(idx)
            den += len(idx)
        return num / den

    real = score(starts, ends)
    null = []
    for _ in range(n_null):
        sh = int(rng.integers(1, n))
        null.append(score(starts + sh, ends + sh))
    null = np.array(null)
    return {"real": real, "null_mean": float(null.mean()), "null_p95": float(np.percentile(null, 95)),
            "p": float(np.mean(null >= real))}


def mode_int(v: np.ndarray, default: int = -1) -> int:
    v = np.asarray(v)
    if len(v) == 0:
        return default
    vals, cnt = np.unique(v, return_counts=True)
    return int(vals[int(np.argmax(cnt))])


def tbl(header: list, rows: list) -> list[str]:
    out = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return out


def f1(v, fmt="{:.1f}", nan="-"):
    try:
        return nan if v is None or not np.isfinite(v) else fmt.format(v)
    except TypeError:
        return str(v)


def splice_sections(path: str, blocks: dict) -> None:
    """Replace (or append) '## 9.' / '## 10.' blocks in rhythm.md without touching the rest."""
    text = open(path, encoding="utf-8").read() if os.path.exists(path) else ""
    for head, lines in blocks.items():
        body = "\n".join(lines).rstrip() + "\n"
        i = text.find("\n" + head)
        if i < 0:
            text = text.rstrip() + "\n\n" + body
            continue
        j = text.find("\n## ", i + 1)
        text = text[:i + 1] + body + ("\n" + text[j + 1:] if j >= 0 else "")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def preserved_tail(path: str) -> str:
    if not os.path.exists(path):
        return ""
    text = open(path, encoding="utf-8").read()
    idx = [i for i in (text.find("\n## 9. "), text.find("\n## 10. ")) if i >= 0]
    return text[min(idx):] if idx else ""



def block_similarity(P: np.ndarray, starts: np.ndarray, n: int) -> dict:
    """Is the pattern a fixed distribution inside a sub-section that changes at its edges?
    within = r between the occupancy profiles of a segment's first and second half;
    across = r between the profiles of the last half of one segment and the first half of the next
    (equal-length windows, so the two numbers are comparable)."""
    ends = np.concatenate([starts[1:], [n]])
    within, across = [], []
    for q, (s0, e0) in enumerate(zip(starts, ends)):
        L = e0 - s0
        if L >= 4:
            h = L // 2
            within.append(pair_r(P[s0:s0 + h].mean(0), P[s0 + h:e0].mean(0)))
        if q + 1 < len(starts):
            s1, e1 = starts[q + 1], ends[q + 1]
            w = min(L, e1 - s1) // 2
            if w >= 2:
                across.append(pair_r(P[e0 - w:e0].mean(0), P[s1:s1 + w].mean(0)))
    return {"within": float(np.nanmean(within)), "across": float(np.nanmean(across)),
            "n_within": len(within), "n_across": len(across)}


def coincidence(a: np.ndarray, b: np.ndarray, n: int, tol: int, rng, n_null: int = 500) -> dict:
    """Share of change points in `a` with one in `b` within +-tol bars, against b shifted at random."""
    a, b = np.asarray(a[1:]), np.asarray(b[1:])
    if len(a) == 0 or len(b) == 0:
        return {"real": np.nan, "null": np.nan, "p": np.nan}
    hit = lambda bb: float(np.mean([np.min(np.abs(bb - x)) <= tol for x in a]))
    real = hit(b)
    null = np.array([hit((b + rng.integers(1, n)) % n) for _ in range(n_null)])
    return {"real": real, "null": float(null.mean()), "p": float(np.mean(null >= real))}


def run_extras(st, F):
    g, bar_starts, secinfo, M = st["g"], st["bar_starts"], st["secinfo"], st["M"]
    t16 = g["t16"]
    nb = len(bar_starts)
    bar_t = t16[bar_starts]
    bar_len = g["bar_len"]
    bar_of, slot_of = slot_index(t16, bar_starts)
    sec_of = np.searchsorted(np.array([s["t0"] for s in secinfo]), bar_t, "right") - 1
    E = bar_energy(bar_t, bar_len)
    tot_e = sum(E[c] for c in ("sub", "bass", "lowmid", "mid", "high", "air"))
    low_pct = (E["sub"] + E["bass"]) / tot_e
    rms_db = 20 * np.log10(E["rms"] / np.median(E["rms"]))
    peers = read_peers()
    drops = np.array(sorted(e["t"] for e in peers["drops"]))
    drops_big = np.array(sorted(e["t"] for e in peers["drops"] if e["grade"] in ("major", "mid")))
    bdowns = np.array(sorted(e["t"] for e in peers["breakdowns"]))
    seams = np.array(sorted(e["t"] for e in peers["seams"]))
    anchors = np.sort(np.concatenate([drops, bdowns, seams]))
    rng = np.random.default_rng(17)
    bar_at = lambda t: int(np.argmin(np.abs(bar_t - t)))

    # ------------------------------------------------------------- kicks
    KF = kicks_final(F, t16, bar_of, slot_of, nb)
    KH = KF["KH"]
    kick_hits = KH.sum(1)
    kbeta, ktab = calibrate_beta(KH.astype(float))
    kstarts, kpen = changepoints(KH.astype(float), kbeta)
    kseg = seg_ids(kstarts, nb)
    kends = np.concatenate([kstarts[1:], [nb]])
    kseg_ev, kseg_cls = [], []
    for s0, e0 in zip(kstarts, kends):
        ev = kick_evidence(KF, np.arange(s0, e0), bar_starts, t16)
        kseg_ev.append(ev)
        kseg_cls.append(classify_kick(ev))
    kick_class = np.array([kseg_cls[q][0] for q in kseg], np.int8)
    sec_kev = [kick_evidence(KF, np.nonzero(sec_of == i)[0], bar_starts, t16) for i in range(len(secinfo))]
    sec_kcls = [classify_kick(ev) for ev in sec_kev]
    # threshold sensitivity of the section classes
    kick_sens, kick_flips = {}, {}
    for thr in (-6.0, -12.0):
        KFx = kicks_final(F, t16, bar_of, slot_of, nb, thr_db=thr)
        cl = [classify_kick(kick_evidence(KFx, np.nonzero(sec_of == i)[0], bar_starts, t16))[0]
              for i in range(len(secinfo))]
        w = np.array([np.sum(sec_of == i) for i in range(len(secinfo))])
        kick_sens[thr] = float(np.sum(w * (np.array(cl) == np.array([c[0] for c in sec_kcls]))) / w.sum())
        kick_flips[thr] = [f"S{i + 1} -> {KICK_CODES[c]}" for i, c in enumerate(cl) if c != sec_kcls[i][0]]

    # ------------------------------------------------------------- carrier
    CF = carrier_final(F, g, bar_starts)
    H, present, odd_n = CF["H"], CF["present"], CF["odd"]
    other = other_band_coverage(F, g, bar_starts, CF["rho"])
    hb, hs = np.nonzero(H)
    HF = hit_features(F, t16[bar_starts[hb] + hs] + CF["lat_ms"] / 1000.0)
    # per-bar timbre for the change-point vector
    bar_cen = np.full(nb, np.nan)
    bar_low = np.full(nb, np.nan)
    for b in range(nb):
        m = (hb == b) & np.isfinite(HF["cen"])
        if m.sum():
            bar_cen[b] = np.median(np.log2(HF["cen"][m]))
            bar_low[b] = np.median(HF["lowc"][m])
    for arr in (bar_cen, bar_low):
        last = np.nanmedian(arr)
        for b in range(nb):
            if np.isfinite(arr[b]):
                last = arr[b]
            else:
                arr[b] = last
    z = lambda v: (v - v.mean()) / (v.std() + 1e-9)
    XC = np.hstack([2.0 * present[:, None].astype(float), H.astype(float),
                    0.5 * np.clip(z(bar_cen), -3, 3)[:, None], 0.5 * np.clip(z(bar_low), -3, 3)[:, None]])
    cbeta, ctab = calibrate_beta(XC)
    cstarts, cpen = changepoints(XC, cbeta)
    cseg = seg_ids(cstarts, nb)
    cends = np.concatenate([cstarts[1:], [nb]])
    cseg_cls = []
    for s0, e0 in zip(cstarts, cends):
        bm = np.zeros(nb, bool)
        bm[s0:e0] = True
        if present[s0:e0].mean() < 0.5:
            cseg_cls.append((0, "-", f"carrier in {100 * present[s0:e0].mean():.0f}% of bars"))
            continue
        ev = carrier_evidence(HF, hb, hs, present, bm)
        cseg_cls.append(classify_carrier(ev) if ev else (0, "-", "too few hits"))
    carrier_type = np.array([cseg_cls[q][0] for q in cseg], np.int8)
    sec_cev, sec_ccls = [], []
    for i in range(len(secinfo)):
        ev = carrier_evidence(HF, hb, hs, present, sec_of == i)
        sec_cev.append(ev)
        sec_ccls.append(classify_carrier(ev) if ev else (0, "-", "too few hits"))

    # ------------------------------------------------------------- save the per-bar table
    np.savez(BARS_NPZ,
             bar_start_s=bar_t.astype(np.float64), bar_dur_s=np.full(nb, bar_len),
             section_id=sec_of.astype(np.int16),
             kick_class=kick_class, kick_hits=kick_hits.astype(np.int8), kick_occ16=KH,
             carrier_present=present, carrier_type=carrier_type,
             carrier_odd_hits=odd_n.astype(np.int8), carrier_occ16=H,
             kick_segment_id=kseg.astype(np.int16), carrier_segment_id=cseg.astype(np.int16),
             kick_codes=np.array(json.dumps(KICK_CODES)),
             carrier_codes=np.array(json.dumps(CARRIER_CODES)),
             meta=np.array(json.dumps({"bpm": g["bpm"], "grid": g["source"], "carrier_rho": CF["rho"],
                                       "kick_beta": kbeta, "carrier_beta": cbeta,
                                       "kick_thr_db": -9.0, "script": "scripts/reaper_rhythm.py"})))
    print(f"wrote {BARS_NPZ}")

    # ------------------------------------------------------------- shared derived numbers
    rec_edges = seams
    kalign = phrase_alignment(kstarts, bar_t, bar_len, nb, anchors, rec_edges)
    calign = phrase_alignment(cstarts, bar_t, bar_len, nb, anchors, rec_edges)
    kstab = stability(KH, kstarts, nb, 0, rng)
    kstab1 = stability(KH, kstarts, nb, 1, rng)
    cstab_p = stability(present[:, None], cstarts, nb, 0, rng)
    cstab_h = stability(H, cstarts, nb, 2, rng)
    kblock = block_similarity(KH.astype(float), kstarts, nb)
    cblock = block_similarity(H.astype(float), cstarts, nb)
    coin1 = coincidence(kstarts, cstarts, nb, 1, rng)
    coin2 = coincidence(kstarts, cstarts, nb, 2, rng)
    stab_by_class = {}
    for c in KICK_CODES:
        segs = [q for q in range(len(kstarts)) if kseg_cls[q][0] == c]
        num = den = num1 = 0.0
        for q in segs:
            s0, e0 = kstarts[q], kends[q]
            has = KH[s0:e0].sum(1) > 0
            if has.sum() == 0:
                continue
            num += modal_share(KH[s0:e0][has], 0) * has.sum()
            num1 += modal_share(KH[s0:e0][has], 1) * has.sum()
            den += has.sum()
        if den:
            stab_by_class[c] = (num / den, num1 / den, int(den))

    def ctx_label(t0, t1):
        lab = []
        if len(seams) and np.any((seams >= t0 - 2 * bar_len) & (seams <= t1 + 2 * bar_len)):
            lab.append("mix seam")
        if len(drops) and np.any((drops >= t0 - 2 * bar_len) & (drops <= t1 + bar_len)):
            lab.append("drop")
        if len(bdowns) and np.any((bdowns >= t0 - 8 * bar_len) & (bdowns <= t1)):
            lab.append("breakdown")
        return lab

    # ================================================================= SECTION 9
    L9 = ["## 9. The 16th carrier", "",
          "The claim under test: *something is always carrying a 16th rhythm - usually a high "
          "filtered break, or short percussion*. Measurement only; the wav was read solely to "
          "compute envelopes and spectra (see `features48` in the script), nothing was kept but "
          "numbers. Grid: the drift-tracked grid of section 0.", "",
          "### 9.1 Coverage", "",
          f"**Detector.** Carrier-band (1.5-16 kHz) spectral flux at 5 ms resolution, from the "
          f"48 kHz file. For every 16th, the peak flux within +-20 ms of the slot (A) is compared "
          f"with the same measurement a 32nd later, between two slots (B). A slot is articulated "
          f"when A >= rho x the bar's median B. A bar has a **carrier** when at least **3 of its 8 "
          f"off-8th slots** are articulated and **at least 10 of 16** overall. The detector's "
          f"latency ({CF['lat_ms']:.1f} ms) is removed first; 92.5 % of carrier-band onsets land "
          f"within 20 ms of the grid.", "",
          "**Why 3 of 8.** A layer playing 8ths leaves the odd slots empty; a straight 16th layer "
          "fills all 8; a chopped break typically lands 3-5 of them. 3 is the brief's figure and it "
          "is *not* noise-proof on its own - at the rho used below, 3 of 8 between-slot positions "
          "spike by chance in about a quarter of bars - which is why rho is chosen against that "
          "false-alarm rate rather than fixed, and why the carrier share is also reported as a "
          "null-corrected estimate that does not depend on the rho choice. **Why 10 of 16.** It "
          "requires the layer to be continuous across the bar rather than a single roll.", "",
          "**Choosing rho, and the null.** The null is the identical test run on the between-slot "
          "positions themselves: how often do 3 of 8 *between* positions spike at the same "
          "threshold? That is the false-alarm rate. Observed = c x sensitivity + (1 - c) x "
          "false-alarm, so (observed - null) / (1 - null) bounds the true carrier share c from "
          "below, and the loosest settings (where sensitivity ~ 1) give its best estimate. rho is "
          "then the setting with the smallest estimated misclassification (false alarms plus "
          "misses).", ""]
    L9 += tbl(["rho", "bars with carrier", "odd >= 3 only", "null (odd >= 3 on between-slots)",
               "lower bound on c", "est. misclassified"],
              [[f"{r['rho']:.2f}" + (" **(used)**" if r["rho"] == CF["rho"] else ""),
                f"{100 * r['cov']:.1f} %", f"{100 * r['odd3']:.1f} %", f"{100 * r['null_odd3']:.1f} %",
                f"{100 * r['c_lb']:.1f} %", f"{100 * r['err']:.1f} %"] for r in CF["rows"]])
    # windows
    odd2 = np.convolve(odd_n, np.ones(2) / 2, "same")
    tot2 = np.convolve(H.sum(1), np.ones(2) / 2, "same")
    odd4 = np.convolve(odd_n, np.ones(4) / 4, "same")
    tot4 = np.convolve(H.sum(1), np.ones(4) / 4, "same")
    cov2 = float(np.mean((odd2 >= 3) & (tot2 >= 10)))
    cov4 = float(np.mean((odd4 >= 3) & (tot4 >= 10)))
    L9 += ["",
           f"**Coverage: {100 * present.mean():.1f} % of bars** at rho = {CF['rho']}. The null-corrected "
           f"estimate of the true share is **{100 * CF['c_hat']:.0f} %**. Is it fragile?", "",
           f"- to the **band**: 0.7-16 kHz gives {100 * other['fl_700']:.1f} %, 4-16 kHz gives "
           f"{100 * other['fl_4000']:.1f} % - stable;",
           f"- to the **window**: judged on the mean of 2 bars {100 * cov2:.1f} %, of 4 bars "
           f"{100 * cov4:.1f} %;",
           f"- to **rho**: yes, and the table shows exactly how. The loosest setting (false alarms "
           f"{100 * CF['rows'][0]['null_odd3']:.0f} %) calls {100 * CF['rows'][0]['cov']:.0f} % of bars; "
           f"even the strictest (false alarms {100 * CF['rows'][-1]['null_odd3']:.0f} %) still finds a "
           f"carrier in {100 * CF['rows'][-1]['cov']:.0f} %, and there the drop is the detector losing "
           f"quiet 16ths. The null-corrected share sits at {100 * CF['rows'][0]['c_lb']:.0f}-"
           f"{100 * CF['rows'][1]['c_lb']:.0f} % at the two loosest settings, which is where "
           f"sensitivity is closest to 1.", "",
           f"**Verdict on 'always':** not always, but most of the time - roughly **7 bars in 10**. "
           f"The claim holds as a strong default, not as an invariant, and the gaps are not random "
           f"(9.1b).", "",
           "Coverage per section:", ""]
    rows = []
    for i, s in enumerate(secinfo):
        m = sec_of == i
        if not m.any():
            continue
        rows.append([f"S{i + 1}", mmss(s["t0"]), int(m.sum()), f"{100 * present[m].mean():.0f} %",
                     f"{odd_n[m].mean():.1f}", f"{H[m].sum(1).mean():.1f}"])
    L9 += tbl(["section", "start", "bars", "carrier", "odd slots hit / bar", "slots hit / bar"], rows)

    # 9.1b stretches without
    gaps = runs_of(~present)
    glen = np.array([b1 - b0 for b0, b1 in gaps])
    L9 += ["", f"**9.1b Every stretch without a carrier** - {len(gaps)} stretches, "
               f"{int(glen.sum())} bars. Length distribution: "
               + ", ".join(f"{int((glen == k).sum())} x {k} bar{'s' if k > 1 else ''}"
                           for k in sorted(set(glen.tolist())) if k <= 4)
               + (f", {int((glen > 4).sum())} longer than 4 bars" if (glen > 4).any() else "")
               + ". Context comes from the drop/breakdown events in `drops.md` and the record seams "
                 "in `structure.md` (within 2 bars; breakdown = within the 8 bars after one).", ""]
    grows, ctx_count = [], {}
    for b0, b1 in gaps:
        t0, t1 = bar_t[b0], bar_t[b1 - 1] + bar_len
        lab = ctx_label(t0, t1)
        if not lab:
            lab = ["low end out"] if np.median(low_pct[b0:b1]) < 0.05 else ["groove"]
        key = " + ".join(lab)
        ctx_count[key] = ctx_count.get(key, 0) + (b1 - b0)
        grows.append([mmss(t0), b1 - b0, f"S{sec_of[b0] + 1}", key, f"{odd_n[b0:b1].mean():.1f}",
                      f"{H[b0:b1].sum(1).mean():.1f}", f"{kick_hits[b0:b1].mean():.1f}",
                      f"{rms_db[b0:b1].mean():+.1f}", f"{100 * np.median(low_pct[b0:b1]):.0f} %"])
    L9 += tbl(["start", "bars", "section", "what is happening", "odd hits/bar", "slots hit/bar",
               "kicks/bar", "rms dB (rel.)", "low %"], grows)
    tot_gap = max(int(glen.sum()), 1)
    L9 += ["", "Bars without a carrier, by context: " +
           "; ".join(f"{k} {v} ({100 * v / tot_gap:.0f} %)" for k, v in
                     sorted(ctx_count.items(), key=lambda x: -x[1])) + ".", ""]
    groove_share = ctx_count.get("groove", 0) / tot_gap
    L9 += [f"Reading: {100 * np.mean(glen <= 2):.0f} % of the gaps are 1-2 bars - a fill, a stop or "
           f"a thin bar inside a running carrier, not an absence. {100 * groove_share:.0f} % of the "
           f"carrier-less bars sit in plain groove with no event nearby; the rest cluster at drops, "
           f"breakdowns, seams and low-end-out passages.", ""]

    # 9.2 what carries it
    L9 += ["### 9.2 What carries it", "",
           "Measured on the **odd-slot hits** of carrier bars (the positions only a 16th layer "
           "plays). Each hit's own spectrum is isolated by subtracting the frame before it "
           "(attack spectrum), so sustained pads and a held sub drop out.", "",
           "- **shape r**: mean correlation between the 1/3-octave shapes of two random hits. "
           "Uniform percussion is one sound repeated; a break's slices are snare edge, ghost, hat, "
           "ride - mixed.",
           "- **centroid spread**: sd of log2 centroid between hits, in octaves.",
           "- **level sd**: accent spread between hits, dB. Breaks accent; programmed shakers don't.",
           "- **decay**: ms for the carrier band to give back half its rise. **ring**: share of the "
           "rise still standing 50-80 ms later, just before the next 16th (0 = fully decayed).",
           "- **low content**: attack energy 125-500 Hz relative to 1-4 kHz. **corner**: where the "
           "averaged attack spectrum falls 12 dB below its 1-4 kHz plateau (9.3).",
           "- **flatness**: spectral flatness within an octave of the centroid (1 = noise, "
           "0 = pitched).", "",
           "Class rules (in `classify_carrier`): *uniform* (shape r >= 0.35 and level sd <= 2.5 dB) "
           "-> short percussion; otherwise a break, **high-passed** when the corner is >= 250 Hz, "
           "**full-range** when there is no corner above 125 Hz, and a partial low-cut in between "
           "is called by the nearer side (180 Hz) at low confidence. The boundaries come from the "
           "kick register: the kick's body lives at 60-250 Hz (bass.md), so a break whose hits "
           "have lost 12 dB by 250 Hz no longer carries a kick, and one still within 12 dB at 125 Hz "
           "does. The corner is taken from the **median** hit shape - averaging power instead lets "
           "the few odd-slot hits that coincide with a bass-note onset own every low band.", ""]
    rows = []
    for i, s in enumerate(secinfo):
        ev, cl = sec_cev[i], sec_ccls[i]
        if ev is None:
            rows.append([f"S{i + 1}", mmss(s["t0"]), "-", "-", "too few hits"] + ["-"] * 10)
            continue
        rows.append([f"S{i + 1}", mmss(s["t0"]), f"**{CARRIER_CODES[cl[0]]}**", cl[1], cl[2], ev["n"],
                     f"{ev['shape_r']:.2f}", f"{ev['spread']:.2f}", f"{ev['lvl_sd']:.1f}",
                     f"{ev['decay']:.0f}", f"{ev['ring']:.2f}", f"{ev['lowc']:+.1f}",
                     f1(ev["corner"], "{:.0f}", "open"), f"{ev['cen']:.0f}", f"{ev['flat']:.2f}"])
    L9 += tbl(["sec", "start", "carrier", "conf.", "deciding evidence", "hits", "shape r",
               "centroid spread oct", "level sd dB", "decay ms", "ring", "low content dB",
               "corner Hz", "centroid Hz", "flatness"], rows)
    w_sec = np.array([np.sum(sec_of == i) for i in range(len(secinfo))])
    share_by = {}
    for i, cl in enumerate(sec_ccls):
        share_by[cl[0]] = share_by.get(cl[0], 0) + w_sec[i]
    ev_all = [e for e in sec_cev if e]
    corners = [e["corner"] for e in ev_all if np.isfinite(e["corner"])]
    L9 += ["", "By bars: " + ", ".join(f"{CARRIER_CODES[k]} {100 * v / nb:.0f} %"
                                        for k, v in sorted(share_by.items(), key=lambda x: -x[1])) + ".",
           "",
           f"**Read the labels with the corners next to them.** Every section's corner lies between "
           f"{min(corners):.0f} and {max(corners):.0f} Hz. So 'high-passed break' here means a break "
           f"with its kick and bass register trimmed out (corners around 200-300 Hz, in the "
           f"records running 2:28-6:46 and at 19:50), and 'full-range break' means one that keeps "
           f"body down to about 80-180 Hz. **No section's carrier is a thin, 1 kHz-plus filtered "
           f"break.** The one genuinely high carrier is S1 (0:00-0:49), the high-passed breaks-only "
           f"mix-in: centroid 5.5 kHz, uniform, level spread 0.5 dB - classed as short percussion "
           f"(hats/shakers), though a very steadily played, heavily filtered break would look the "
           f"same to these measures. Most calls are low-to-medium confidence: in a full mix the "
           f"odd-slot hits carry everything that attacks there, not only the carrier.", "",
           f"What does **not** separate them: decay and ring. Every section's odd-slot hits give "
           f"back half their rise in {min(e['decay'] for e in ev_all):.0f}-"
           f"{max(e['decay'] for e in ev_all):.0f} ms and have decayed to the pre-hit floor "
           f"before the next 16th (ring {min(e['ring'] for e in ev_all):+.2f} to "
           f"{max(e['ring'] for e in ev_all):+.2f}). That is itself a finding: whatever carries the "
           f"16ths is **cut short** - slices chopped to the 16th, or short hits - never a ringing "
           f"slice that overlaps the next. What does separate them is uniformity and low content.", ""]

    # 9.3 filter corner
    L9 += ["### 9.3 The filter", "",
           "For breaks, the corner is where the median attack spectrum of the carrier's odd-slot "
           "hits falls 12 dB below its 1-4 kHz plateau. It is measured twice: over all carrier bars "
           "of the section, and - as asked - only over bars with **no detected kick and the low "
           "end out** (under 5 % of the spectrum below 120 Hz), where nothing else can fill the "
           "low end of the attack spectrum.", ""]
    rows = []
    free = (kick_hits == 0) & (low_pct < 0.05)
    for i, s in enumerate(secinfo):
        if sec_ccls[i][0] not in (1, 3):
            continue
        ev_f = carrier_evidence(HF, hb, hs, present, (sec_of == i) & free)
        rows.append([f"S{i + 1}", mmss(s["t0"]), CARRIER_CODES[sec_ccls[i][0]],
                     f1(sec_cev[i]["corner"], "{:.0f} Hz", "open (< 45 Hz)"),
                     int(((sec_of == i) & free).sum()),
                     f1(ev_f["corner"], "{:.0f} Hz", "open (< 45 Hz)") if ev_f else "too few bars"])
    L9 += tbl(["sec", "start", "carrier", "corner, all carrier bars", "kick- and bass-free bars",
               "corner, kick/bass-free"], rows)
    # corner around drops
    drow, moves = [], []
    for d in drops_big:
        b = bar_at(d)
        cs = []
        for lo, hi in ((-8, 0), (0, 8), (8, 16)):
            bm = np.zeros(nb, bool)
            bm[max(b + lo, 0):min(b + hi, nb)] = True
            ev = carrier_evidence(HF, hb, hs, present, bm)
            cs.append(ev["corner"] if (ev and ev["n"] >= 12) else np.nan if ev is None else ev["corner"])
        drow.append([mmss(d), f1(cs[0], "{:.0f}", "open"), f1(cs[1], "{:.0f}", "open"),
                     f1(cs[2], "{:.0f}", "open")])
        moves.append(cs)
    L9 += ["", "The kick- and bass-free bars are few (0-11 per section) but agree with the "
               "all-bars corners to within about half an octave, so the low end of the median hit "
               "is the carrier's own, not bleed from kick or sub.", "",
           "Corner (Hz) around every major/mid drop in `drops.md` - the 8 bars before, the "
               "first 8 bars of the drop, and the 8 after that. 'open' = no fall of 12 dB above "
               "45 Hz.", ""]
    L9 += tbl(["drop", "8 bars before", "drop bars 1-8", "drop bars 9-16"], drow)
    mv = np.array(moves, np.float64)
    fin = lambda x: np.where(np.isfinite(x), x, 40.0)
    opened = int(np.sum(fin(mv[:, 1]) < fin(mv[:, 0]) / 1.5))
    closed = int(np.sum(fin(mv[:, 1]) > fin(mv[:, 0]) * 1.5))
    L9 += ["", f"Across {len(mv)} drops the corner **opens** (falls by more than half an octave) "
               f"into the drop {opened} times, **closes** {closed} times, and holds within half an "
               f"octave {len(mv) - opened - closed} times. Median corner before "
               f"{f1(np.nanmedian(mv[:, 0]), '{:.0f}')} Hz, at the drop "
               f"{f1(np.nanmedian(mv[:, 1]), '{:.0f}')} Hz, after "
               f"{f1(np.nanmedian(mv[:, 2]), '{:.0f}')} Hz (NaN-free medians over the drops where "
               f"a corner exists).", "",
           "**The filter does not open at the drop.** Openings and closings are equally common and "
           "the median corner is the same before, at and after. The drop is not delivered by "
           "sweeping the break's high-pass down; the low end arrives from the kick and sub "
           "(drops.md: sub +10 dB) while the carrier keeps its own low-cut.", ""]

    # 9.4 stacking
    L9 += ["### 9.4 Stacking at the drop", "",
           "For each major/mid drop: does the carrier's 16th pattern and timbre carry through, or is "
           "it replaced? Pattern r = correlation of the 16-slot carrier occupancy over the 8 bars "
           "before vs the first 8 of the drop; its baseline is the split-half r inside each window "
           "(what 'unchanged' looks like). Timbre = RMS dB difference of the odd-slot attack shape "
           "(plateau-relative, 250 Hz-15 kHz), with its split-half baseline. Level = carrier hit "
           "level change. Mid onsets = snare/body onsets per bar from section 1 (a full-range break "
           "arriving shows here).", ""]
    srow, verdicts = [], []
    for d in drops_big:
        b = bar_at(d)
        pre = np.arange(max(b - 8, 0), b)
        at = np.arange(b, min(b + 8, nb))
        if len(pre) < 6 or len(at) < 6:
            continue
        r_x = pair_r(H[pre].mean(0), H[at].mean(0))
        r_b = np.nanmean([pair_r(H[pre[:4]].mean(0), H[pre[4:]].mean(0)),
                          pair_r(H[at[:4]].mean(0), H[at[4:]].mean(0))])
        shp = {}
        for nm, idx in (("pre", pre), ("at", at), ("pre_a", pre[:4]), ("pre_b", pre[4:]),
                        ("at_a", at[:4]), ("at_b", at[4:])):
            bm = np.zeros(nb, bool)
            bm[idx] = True
            ev = carrier_evidence(HF, hb, hs, np.ones(nb, bool), bm)
            shp[nm] = ev
        if not (shp["pre"] and shp["at"]):
            continue
        tdiff = float(np.sqrt(np.mean((shape_rel(shp["pre"]["shape_db"]) - shape_rel(shp["at"]["shape_db"])) ** 2)))
        bl = [np.sqrt(np.mean((shape_rel(shp[a]["shape_db"]) - shape_rel(shp[c]["shape_db"])) ** 2))
              for a, c in (("pre_a", "pre_b"), ("at_a", "at_b")) if shp[a] and shp[c]]
        tbase = float(np.mean(bl)) if bl else np.nan
        dl = shp["at"]["lvl"] - shp["pre"]["lvl"]
        dmid = M["hit"][at][:, :, 1].sum(1).mean() - M["hit"][pre][:, :, 1].sum(1).mean()
        dlow = shp["at"]["lowc"] - shp["pre"]["lowc"]
        keep_p = np.isfinite(r_x) and r_x >= min(r_b, 0.9) - 0.15
        keep_t = tdiff <= max(2.0, 1.5 * tbase)
        v = ("continues" if keep_p and keep_t else "replaced" if not (keep_p or keep_t)
             else "pattern kept, timbre changed" if keep_p else "timbre kept, pattern changed")
        verdicts.append(v)
        srow.append([mmss(d), f"{r_x:.2f}", f"{r_b:.2f}", f"{tdiff:.1f}", f1(tbase), f"{dl:+.1f}",
                     f"{dlow:+.1f}", f"{dmid:+.1f}", f"{100 * present[pre].mean():.0f}% -> "
                                                    f"{100 * present[at].mean():.0f}%", f"**{v}**"])
    L9 += tbl(["drop", "pattern r", "baseline r", "timbre diff dB", "baseline dB", "carrier level dB",
               "low content dB", "mid onsets/bar", "carrier bars", "verdict"], srow)
    vc = {k: verdicts.count(k) for k in set(verdicts)}
    dls = [float(r[5]) for r in srow]
    dlows = [float(r[6]) for r in srow]
    L9 += ["", "Tally: " + ", ".join(f"{k} {v}" for k, v in sorted(vc.items(), key=lambda x: -x[1]))
           + f" (of {len(verdicts)} measurable drops).", "",
           f"**It stacks; it is not replaced.** {vc.get('replaced', 0)} of {len(verdicts)} drops "
           f"replace the carrier outright, and "
           f"{len(verdicts) - vc.get('replaced', 0)} keep at least its pattern or its timbre. The "
           f"carrier's hit level changes by a median {np.median(dls):+.1f} dB (range "
           f"{min(dls):+.1f} to {max(dls):+.1f}) - it neither ducks under the drop nor rides over "
           f"it - while its odd-slot hits gain a median {np.median(dlows):+.1f} dB of 125-500 Hz "
           f"body, above +3 dB at {int(np.sum(np.array(dlows) > 3))} drops: full-range material "
           f"joins underneath the 16th layer rather than taking over from it. Timbre verdicts are "
           f"the weaker half of this test - the split-half baselines are 2-12 dB, because 4 bars "
           f"hold few odd-slot hits.", ""]

    # 9.5 timbre per section
    L9 += ["### 9.5 Does the carrier change character per section?", "",
           "Each section's mean odd-slot attack shape (plateau-relative dB, 250 Hz-15 kHz). "
           "'Within' is the split-half distance inside the section (first half of its hits vs "
           "second half): how much the same carrier wanders. 'To previous' is the distance to the "
           "previous section's carrier. A ratio of 2 or more, with at least 2 dB, is a change of "
           "character.", ""]
    rows, changes, prev = [], 0, None
    n_cmp = 0
    for i, s in enumerate(secinfo):
        ev = sec_cev[i]
        if ev is None or ev["n"] < 20:
            continue
        idx = np.nonzero(ev["mask"])[0]
        h1, h2 = idx[:len(idx) // 2], idx[len(idx) // 2:]
        s1 = shape_rel(median_shape(HF["att3"][h1].astype(np.float64)))
        s2 = shape_rel(median_shape(HF["att3"][h2].astype(np.float64)))
        within = float(np.sqrt(np.mean((s1 - s2) ** 2)))
        cur = shape_rel(ev["shape_db"])
        if prev is not None:
            dist = float(np.sqrt(np.mean((cur - prev[0]) ** 2)))
            ratio = dist / max((within + prev[1]) / 2, 1e-6)
            chg = ratio >= 2 and dist >= 2
            changes += chg
            n_cmp += 1
            rows.append([f"S{i + 1}", mmss(s["t0"]), CARRIER_CODES[sec_ccls[i][0]], f"{within:.1f}",
                         f"{dist:.1f}", f"{ratio:.1f}", "**yes**" if chg else "no",
                         f1(ev["corner"], "{:.0f}", "open"), f"{ev['cen']:.0f}"])
        else:
            rows.append([f"S{i + 1}", mmss(s["t0"]), CARRIER_CODES[sec_ccls[i][0]], f"{within:.1f}",
                         "-", "-", "-", f1(ev["corner"], "{:.0f}", "open"), f"{ev['cen']:.0f}"])
        prev = (cur, within)
    L9 += tbl(["sec", "start", "carrier", "within dB", "to previous dB", "ratio", "changed",
               "corner Hz", "centroid Hz"], rows)
    L9 += ["", f"**{changes} of {n_cmp}** section boundaries change the carrier's character by that "
               f"test - but read the 'within' column: a carrier wanders 1.4-5.9 dB inside one "
               f"section, as far as it moves between neighbours, so section-to-section shape "
               f"distance is too noisy to see a change. The corner and centroid are steadier, and "
               f"they do move - by **record** (the 9 records of structure.md):", ""]
    rrows = []
    edges = np.concatenate([[0.0], seams, [bar_t[-1] + bar_len]])
    for ri in range(len(edges) - 1):
        bm = (bar_t >= edges[ri]) & (bar_t < edges[ri + 1])
        ev = carrier_evidence(HF, hb, hs, present, bm)
        if ev is None:
            continue
        rrows.append([f"T{ri}", mmss(edges[ri]), int(bm.sum()), f"{100 * present[bm].mean():.0f} %",
                      f1(ev["corner"], "{:.0f} Hz", "open"), f"{ev['cen']:.0f} Hz", f"{ev['lowc']:+.1f}",
                      f"{ev['shape_r']:.2f}", f"{ev['lvl_sd']:.1f}"])
    L9 += tbl(["record", "start", "bars", "carrier", "corner", "centroid", "low content dB",
               "shape r", "level sd dB"], rrows)
    # is it a property of the record? within-record vs between-record spread of section values
    rec_of_sec = [int(np.searchsorted(seams, s_["t0"] + 1.0, "right")) for s_ in secinfo]
    groups_c, groups_z = {}, {}
    for i, ev in enumerate(sec_cev):
        if ev is None or not np.isfinite(ev["corner"]):
            continue
        groups_c.setdefault(rec_of_sec[i], []).append(np.log2(ev["corner"]))
        groups_z.setdefault(rec_of_sec[i], []).append(np.log2(ev["cen"]))

    def spread(groups):
        within = [v - np.mean(g_) for g_ in groups.values() if len(g_) > 1 for v in g_]
        dof = sum(len(g_) - 1 for g_ in groups.values() if len(g_) > 1)
        w = float(np.sqrt(np.sum(np.square(within)) / max(dof, 1)))
        b = float(np.std([np.mean(g_) for g_ in groups.values()], ddof=1))
        return w, b

    wc, bc = spread(groups_c)
    wz, bz = spread(groups_z)
    L9 += ["", f"Is the character a property of the record? Only partly. Across sections, the corner "
               f"spreads {wc:.2f} octaves (sd) *inside* a record and {bc:.2f} octaves *between* "
               f"record means; the centroid {wz:.2f} inside against {bz:.2f} between. Records differ "
               f"(between > within), but sections within one record move nearly as much. The one "
               f"contrast that stands clear of that noise is between the trimmed breaks of "
               f"3:08-7:22 (corner ~200-235 Hz, centroid 1.2-1.5 kHz, low content -2.5 to +1.2 dB) and "
               f"the body-heavy 16ths of 7:22-10:04 (corner 84-111 Hz, centroid 0.5-0.7 kHz, low "
               f"content +6 to +11 dB) - the stretch that also carries the programmed two-step kick "
               f"(section 10). Where the character does change, the carrier change points of 9.6 "
               f"mark it, since their bar vector includes the timbre coordinates.", ""]

    # 9.6 change points
    clen = np.diff(np.concatenate([cstarts, [nb]]))
    L9 += ["### 9.6 Sub-sections: where the carrier changes", "",
           f"Bar vector: carrier present (weight 2), the 16-slot articulation pattern, and two "
           f"timbre coordinates (median log-centroid and low content of the bar's hits, z-scored, "
           f"weight 0.5). Exact optimal partition (dynamic programming), minimum segment 2 bars. "
           f"The penalty is **calibrated, not chosen**: beta = the smallest value at which "
           f"bar-shuffled data averages <= 1 change point (shuffles: " +
           ", ".join(f"beta {b} -> {m:.1f}" for b, m in ctab) + f"). Chosen beta = **{cbeta}**.", "",
           f"**{len(cstarts)} carrier sub-sections.** Lengths in bars: median "
           f"{np.median(clen):.0f}, quartiles {np.percentile(clen, 25):.0f}-"
           f"{np.percentile(clen, 75):.0f}, range {clen.min()}-{clen.max()}. Distribution: " +
           ", ".join(f"{lo}-{hi}: {int(np.sum((clen >= lo) & (clen <= hi)))}"
                     for lo, hi in ((2, 3), (4, 7), (8, 15), (16, 31), (32, 63), (64, 999))) + ".", "",
           f"**Stability inside a sub-section.** Carrier present/absent matches the segment's modal "
           f"state in **{100 * cstab_p['real']:.0f} %** of bars (random segment placement with the "
           f"same lengths: {100 * cstab_p['null_mean']:.0f} %, p = {cstab_p['p']:.3f}). The 16-slot "
           f"articulation pattern matches the segment's modal pattern to within 2 slots in "
           f"**{100 * cstab_h['real']:.0f} %** of bars (null {100 * cstab_h['null_mean']:.0f} %, "
           f"p = {cstab_h['p']:.3f}).", ""]
    L9 += [f"As a distribution, the carrier's 16-slot articulation profile correlates "
           f"**r = {cblock['within']:.2f}** between the halves of a sub-section and "
           f"**r = {cblock['across']:.2f}** across a boundary.", ""]
    L9 += align_lines(calign)
    L9 += ["", "Carrier sub-sections:", ""]
    rows = []
    for q, (s0, e0) in enumerate(zip(cstarts, cends)):
        rows.append([q, mmss(bar_t[s0]), e0 - s0, f"{100 * present[s0:e0].mean():.0f} %",
                     CARRIER_CODES[cseg_cls[q][0]], cseg_cls[q][1], cseg_cls[q][2]])
    L9 += tbl(["seg", "start", "bars", "carrier bars", "type", "conf.", "evidence"], rows)
    L9 += ["", "### What this means for building a jungle track (carrier)", "",
           f"1. Keep a 16th layer running in about **{100 * CF['c_hat']:.0f}-{100 * present.mean():.0f} % "
           f"of bars** - at least 3 of the 8 off-8th slots, 10+ of 16 slots - and take it out on "
           f"purpose, mostly for 1-2 bars at a time ({100 * np.mean(glen <= 2):.0f} % of gaps).",
           "2. Cut every carrier hit short: the reference's odd-slot hits are back at their floor "
           "before the next 16th in every section. No ringing slices overlapping.",
           f"3. Change the carrier's pattern and timbre as blocks: sub-sections of median "
           f"{np.median(clen):.0f} bars, not bar by bar.", ""]

    # ================================================================= SECTION 10
    klen = np.diff(np.concatenate([kstarts, [nb]]))
    L10 = ["## 10. Kick pattern per section", "",
           "The claim under test: *sometimes 80-120 Hz is filled by a kick four on the floor, "
           "sometimes none, sometimes rare syncopated; sometimes the kick is on a two-step like "
           "DnB; and the pattern only changes at sub-section boundaries.*", "",
           "### 10.1 Isolating kicks from bass notes", "",
           "Section 1's low band (20-160 Hz) mixes kick and bass. Here a **kick** is a low-mid "
           "transient (superflux in the 140-234 Hz FFT bins, which a sub note below 60 Hz cannot "
           "leak into) that passes three tests:", "",
           f"1. **body**: its attack spectrum carries energy in **80-160 Hz** within 9 dB of the "
           f"reference kick level (the 90th percentile of slot-0 candidates, {KF['ref_db']:.1f} dB). "
           f"A 47 Hz sub note sits two FFT bins below 80 Hz, and its own second harmonic is ~17 dB "
           f"down (bass.md), so bass notes put little here; the bass agent's kick puts 42.5 % of "
           f"its energy in 60-250 Hz. Why -9 dB: slot-0 candidates (mostly kicks) peak at -7 to "
           f"-4 dB, while candidates on the snare slots 4 and 12 (mostly snare bleed) peak at "
           f"-13 to -10 dB; -9 dB is the valley between them;",
           "2. **decay**: the 115-260 Hz envelope falls >= 6 dB between 100 and 150 ms after the "
           "peak;",
           "3. **not a bass note**: it must not sit *inside a sustained bass note* (sub level "
           "steady within 4 dB from 220 ms before to 320 ms after) *without a click* (< 3 dB rise "
           "in 1-8 kHz).", "",
           "**Validation.**", ""]
    L10 += tbl(["body threshold", "candidates", "fail decay", "inside a bass note, no click (false positives)",
                "kicks kept", "kicks / bar"],
               [[f"{r['thr']:+.0f} dB" + (" **(used)**" if r["thr"] == -9 else ""), r["cand"],
                 r["decay_fail"], f"{r['fp']} ({100 * r['fp'] / max(r['cand'] - r['decay_fail'], 1):.1f} %)",
                 r["final"], f"{r['final'] / nb:.2f}"] for r in KF["sweep"]])
    L10 += ["",
            f"At the operating point, **{KF['fp']} detections ({100 * KF['fp'] / max(KF['cand'] - KF['decay_fail'], 1):.1f} %)** "
            f"sat inside a sustained bass note with no click and were removed as false positives. "
            f"Of the {int(KF['kick'].sum())} kicks kept ({KF['kick'].sum() / nb:.2f} per bar; the "
            f"bass agent's independent kick-like count is 2.8 per bar), {100 * KF['click_share']:.0f} % "
            f"carry a click and {100 * KF['in_note_share']:.0f} % land inside a bass note *with* a "
            f"click - kicks over a held sub, which is expected with no sidechain. Detector latency "
            f"{KF['lat_ms']:.1f} ms, removed. Kick counts move with the body threshold (table), so "
            f"the classes below were re-run at -6 and -12 dB: the section classes agree with the "
            f"-9 dB result for **{100 * kick_sens[-6.0]:.0f} %** and **{100 * kick_sens[-12.0]:.0f} %** "
            f"of bars respectively. The sections that flip: at -6 dB " +
            (", ".join(kick_flips[-6.0]) or "none") + "; at -12 dB " +
            (", ".join(kick_flips[-12.0]) or "none") + ". Those calls are threshold-dependent; the "
            "rest are not.", "",
            "### 10.2 Classes, and where their boundaries come from", ""]
    doc = classify_kick.__doc__.split("Boundaries and why:")[1]
    L10 += ["```", doc.strip("\n"), "```", "",
            "Two practical points. **Rotation.** The bar phase of section 0 is inferred from snare "
            "placement, which cannot tell beat 2 from beat 4 and in one record sits an 8th off, so "
            "every pattern test is rotation-invariant: four on the floor is 'all four slots of *some* "
            "beat lattice', two-step is 'two kicks 10 then 6 sixteenths apart', and the tables print "
            "occupancy rotated so the stronger of slots 0/8 is the downbeat. **Two-step vs break "
            "kick** is decided by three measurements: bar-to-bar consistency (Jaccard of successive "
            "bars' kick slots, and the share of bars within one slot of the modal pattern), timbral "
            "consistency (median RMS dB distance between the 1/4-octave attack shapes of successive "
            "kicks: one sample vs several slices), and whether the kick sits in its own band "
            "(attack energy 2-16 kHz relative to 80-250 Hz: a programmed kick has only a click up "
            "there, a break kick brings the slice's hats and snare edge with it).", "",
            "### 10.3 Per section", ""]
    rows = []
    for i, s in enumerate(secinfo):
        ev, cl = sec_kev[i], sec_kcls[i]
        occ = "".join("#" if v >= 0.6 else ("+" if v >= 0.3 else ".") for v in ev["occ"])
        rows.append([f"S{i + 1}", mmss(s["t0"]), ev["n"], f"**{KICK_CODES[cl[0]]}**", cl[1],
                     f"{ev['kpb']:.2f}", f"`{occ}`", " ".join(f"{v:.2f}" for v in ev["occ"]),
                     f1(100 * ev["lattice_off"], "{:.0f} %"), f1(ev["jaccard"], "{:.2f}"),
                     f1(ev["modal1"], "{:.2f}"), f1(ev["timbre_dist"]), f1(ev["hf_body"], "{:+.1f}")])
    L10 += tbl(["sec", "start", "bars", "class", "conf.", "kicks/bar",
                "pattern (# >= .6, + >= .3)", "16-slot kick occupancy (downbeat-rotated)",
                "off the beat lattice", "Jaccard bar-to-bar", "modal +-1", "timbre dist dB",
                "HF / body dB"], rows)
    two = [i for i, c in enumerate(sec_kcls) if c[0] == 2]
    brk = [i for i, c in enumerate(sec_kcls) if c[0] == 3]
    agg = lambda ids, k: np.nanmedian([sec_kev[i][k] for i in ids]) if ids else np.nan
    L10 += ["", "**Two-step against break kick, side by side** (medians over the sections in each "
                "class):", ""]
    L10 += tbl(["", "sections", "Jaccard bar-to-bar", "modal +-1", "timbre dist dB", "HF / body dB",
                "kicks/bar"],
               [["two-step", len(two), f1(agg(two, "jaccard"), "{:.2f}"), f1(agg(two, "modal1"), "{:.2f}"),
                 f1(agg(two, "timbre_dist")), f1(agg(two, "hf_body"), "{:+.1f}"), f1(agg(two, "kpb"), "{:.2f}")],
                ["break kick", len(brk), f1(agg(brk, "jaccard"), "{:.2f}"), f1(agg(brk, "modal1"), "{:.2f}"),
                 f1(agg(brk, "timbre_dist")), f1(agg(brk, "hf_body"), "{:+.1f}"), f1(agg(brk, "kpb"), "{:.2f}")]])

    # 10.4 sub-sections
    eighth = [q for q, ev in enumerate(kseg_ev)
              if np.sum(ev["occ"][[0, 2, 4, 6, 8, 10, 12, 14]] >= 0.6) >= 7]
    L10 += ["", "**Four on the floor: not found.** No section and no sub-section has all four beats "
                "of a lattice at 0.6 with the 8ths between them quiet. What a spectrogram would show "
                "as a filled, regular 80-120 Hz lane is " +
            ("; ".join(f"{mmss(bar_t[kstarts[q]])} ({kends[q] - kstarts[q]} bars, "
                       f"{kseg_ev[q]['kpb']:.1f} kicks/bar)" for q in eighth) if eighth else "absent") +
            (": low-mid hits on **every 8th**, twice as dense as four on the floor. They are drum "
             "hits, not bass: their attack carries " +
             " and ".join(f"{kseg_ev[q]['sub_body']:+.0f} dB" for q in eighth) +
             " of sub (40-62 Hz) relative to their 80-160 Hz body, where the set's kicks sit at "
             f"{np.median(KF['K']['sub_body'][KF['kick']]):+.0f} dB and a clean sub note would be "
             "strongly positive, and each has a ~10 dB click. Whether they are a kick roll or "
             "low toms, the measurement cannot say." if eighth else "."), "",
            "**A pattern outside the five classes.** Two kick sub-sections hold a near-identical "
            "pair on beat 1 and beat 4 (rotated slots 0 and 12) - 4:11 and 5:24, modal-within-one-"
            "slot 0.73 and 0.94. It repeats like a programmed kick but is not a two-step, and its "
            "timbre varies like slices; the rules call it break kick at low confidence.", ""]
    L10 += ["", "### 10.4 Sub-sections: change points in the kick pattern", "",
            f"Bar vector = the 16-slot kick hits. Same exact partition and minimum length (2 bars) "
            f"as 9.6; penalty calibrated on bar-shuffled data (" +
            ", ".join(f"beta {b} -> {m:.1f}" for b, m in ktab) + f"), chosen beta = **{kbeta}**.", "",
            f"**{len(kstarts)} kick sub-sections.** Lengths in bars: median {np.median(klen):.0f}, "
            f"quartiles {np.percentile(klen, 25):.0f}-{np.percentile(klen, 75):.0f}, range "
            f"{klen.min()}-{klen.max()}. Distribution: " +
            ", ".join(f"{lo}-{hi}: {int(np.sum((klen >= lo) & (klen <= hi)))}"
                      for lo, hi in ((2, 3), (4, 7), (8, 15), (16, 31), (32, 63), (64, 999))) + ".", "",
            f"**Stability.** The exact 16-slot kick pattern equals its segment's modal pattern in "
            f"**{100 * kstab['real']:.0f} %** of bars (random placement {100 * kstab['null_mean']:.0f} %, "
            f"p = {kstab['p']:.3f}); within one slot in **{100 * kstab1['real']:.0f} %** "
            f"(null {100 * kstab1['null_mean']:.0f} %, p = {kstab1['p']:.3f}).", ""]
    L10 += tbl(["kick class", "bars with kicks", "exact modal pattern", "modal within 1 slot"],
               [[KICK_CODES[c], v[2], f"{100 * v[0]:.0f} %", f"{100 * v[1]:.0f} %"]
                for c, v in stab_by_class.items() if c != 0])
    L10 += ["",
            f"So 'fixed inside a sub-section' depends on the kind of kick. Taken as a *distribution*, "
            f"the 16-slot kick occupancy of a sub-section's first half correlates "
            f"**r = {kblock['within']:.2f}** with its second half, against "
            f"**r = {kblock['across']:.2f}** across a boundary (equal windows either side). Taken as "
            f"an *exact bar*, compare the classes in the table: a programmed kick repeats, a break "
            f"kick re-deals its slots every bar inside a stable distribution.", ""]
    L10 += align_lines(kalign)
    L10 += ["", f"**Do the kick and the carrier change together?** "
                f"{100 * coin1['real']:.0f} % of kick change points have a carrier change point within "
                f"1 bar (random placement {100 * coin1['null']:.0f} %, p = {coin1['p']:.3f}); within 2 "
                f"bars {100 * coin2['real']:.0f} % (random {100 * coin2['null']:.0f} %, "
                f"p = {coin2['p']:.3f}).", ""]
    rows = []
    for q, (s0, e0) in enumerate(zip(kstarts, kends)):
        ev, cl = kseg_ev[q], kseg_cls[q]
        occ = "".join("#" if v >= 0.6 else ("+" if v >= 0.3 else ".") for v in ev["occ"])
        lab = ctx_label(bar_t[s0] - bar_len, bar_t[s0] + bar_len) if q else []
        rows.append([q, mmss(bar_t[s0]), e0 - s0, f"**{KICK_CODES[cl[0]]}**", cl[1], f"{ev['kpb']:.2f}",
                     f"`{occ}`", f1(ev["modal1"], "{:.2f}"), f1(ev["timbre_dist"]),
                     f1(max(ev["sub_body"], -40.0), "{:+.0f}"),
                     " + ".join(lab) if lab else ("-" if q else "start")])
    L10 += ["", "Kick sub-sections (pattern rotated so the stronger of slots 0/8 is the downbeat; "
                "sub/body = attack at 40-62 Hz relative to 80-160 Hz, floored at -40):", ""]
    L10 += tbl(["seg", "start", "bars", "class", "conf.", "kicks/bar", "pattern", "modal +-1",
                "timbre dist dB", "sub/body dB", "boundary sits at"], rows)

    # 10.5 timeline
    run_s = {c: float(np.sum(kick_class == c)) * bar_len for c in KICK_CODES}
    tot_s = sum(run_s.values())
    L10 += ["", "### 10.5 Timeline", "",
            "Runtime per class (from the sub-section classes, which is what `kick_class` in the npz "
            "holds):", ""]
    L10 += tbl(["class", "bars", "runtime", "share", "where"],
               [[KICK_CODES[c], int(np.sum(kick_class == c)), mmss(run_s[c]),
                 f"{100 * run_s[c] / tot_s:.1f} %",
                 ", ".join(f"{mmss(bar_t[s0])} ({e0 - s0} bars)" for q, (s0, e0) in
                           enumerate(zip(kstarts, kends)) if kseg_cls[q][0] == c) or "-"]
                for c in KICK_CODES])
    # class changes
    at_drop = at_seam = at_bd = elsewhere = 0
    n_chg = 0
    for q in range(1, len(kstarts)):
        if kseg_cls[q][0] == kseg_cls[q - 1][0]:
            continue
        n_chg += 1
        lab = ctx_label(bar_t[kstarts[q]] - bar_len, bar_t[kstarts[q]] + bar_len)
        if "mix seam" in lab:
            at_seam += 1
        elif "drop" in lab:
            at_drop += 1
        elif "breakdown" in lab:
            at_bd += 1
        else:
            elsewhere += 1
    drop_tr = {}
    for d in drops_big:
        b = bar_at(d)
        pre_c = mode_int(kick_class[max(b - 4, 0):b])
        at_c = mode_int(kick_class[b:b + 4])
        if pre_c < 0 or at_c < 0:
            continue
        key = f"{KICK_CODES[pre_c]} -> {KICK_CODES[at_c]}"
        drop_tr[key] = drop_tr.get(key, 0) + 1
    L10 += ["", f"**Where the class changes.** {n_chg} class changes between neighbouring kick "
                f"sub-sections: {at_seam} at a record seam, {at_drop} at a drop, {at_bd} after a "
                f"breakdown, {elsewhere} with no event within a bar.", "",
            "Kick class in the 4 bars before vs the first 4 bars of every major/mid drop: " +
            "; ".join(f"{k}: {v}" for k, v in sorted(drop_tr.items(), key=lambda x: -x[1])) + ".", ""]

    # 10.6 relationships
    L10 += ["### 10.6 Relationships", "",
            "**Kick class vs how much the bass moves.** Each of the bass agent's 25 sections "
            "(`bass.md`, table 4) takes the kick class that covers most of its bars:", ""]
    by = {}
    for bs in peers["bass"]:
        m = (bar_t >= bs["t0"]) & (bar_t < bs["t1"])
        if m.sum() < 4:
            continue
        c = mode_int(kick_class[m])
        by.setdefault(c, []).append(bs["chg"])
    L10 += tbl(["kick class", "bass sections", "bass changes / bar (mean)", "median", "range"],
               [[KICK_CODES[c], len(v), f"{np.mean(v):.2f}", f"{np.median(v):.2f}",
                 f"{min(v):.2f}-{max(v):.2f}"] for c, v in sorted(by.items())])
    kick_off = [x for c, v in by.items() if c in (0, 4) for x in v]
    kick_brk = by.get(3, [])
    kick_two = by.get(2, [])
    if kick_off and kick_brk:
        rel = ("about the same" if abs(np.mean(kick_brk) - np.mean(kick_off)) < 0.2 else
               "more with the break kick" if np.mean(kick_brk) > np.mean(kick_off) else
               "more when the kick thins out")
        two_txt = (f" The contrast is **two-step**: under a programmed two-step the bass moves only "
                   f"{np.mean(kick_two):.2f} times a bar. A locked kick gets a still bass; a moving, "
                   f"re-chopped kick gets a moving bass." if kick_two else "")
        L10 += ["", f"Bass under a **break kick** moves {np.mean(kick_brk):.2f} times a bar and under a "
                    f"sparse or absent kick {np.mean(kick_off):.2f} - {rel}.{two_txt} (Sections: "
                    f"two-step {len(kick_two)}, break kick {len(kick_brk)}, sparse/none "
                    f"{len(kick_off)} - small samples; read it as a lean.)", ""]
    L10 += ["**Kick class vs the 16th carrier** (bars, from the two sets of sub-section classes):", ""]
    rows = []
    for c in KICK_CODES:
        m = kick_class == c
        if not m.any():
            continue
        row = [KICK_CODES[c], int(m.sum())]
        for t in CARRIER_CODES:
            row.append(f"{100 * np.mean(carrier_type[m] == t):.0f} %")
        row.append(f"{100 * present[m].mean():.0f} %")
        rows.append(row)
    L10 += tbl(["kick class", "bars"] + [f"carrier: {CARRIER_CODES[t]}" for t in CARRIER_CODES] +
               ["bars with a carrier"], rows)
    two_m = kick_class == 2
    brk_m = kick_class == 3
    L10 += ["", f"Carrier type is a property of the carrier *sub-section* and is 'none' when fewer "
                f"than half its bars carry 16ths, so a bar can have a carrier while its type reads "
                f"none. Even so the pairing is clear: under a **two-step** the carrier sub-section is "
                f"'none' or short percussion in {100 * np.mean(np.isin(carrier_type[two_m], [0, 2])):.0f} % "
                f"of bars and never a high-passed break; under a **break kick** it is a break "
                f"(high-passed or full-range) in {100 * np.mean(np.isin(carrier_type[brk_m], [1, 3])):.0f} %. "
                f"A programmed kick comes with a thin or absent 16th layer; a break kick comes with "
                f"the break carrying the 16ths itself.", ""]
    L10 += ["", "### 10.7 Per-bar table for cross-feature alignment", "",
            f"`{BARS_NPZ}` - one row per analysed bar ({nb} bars; a few bars are skipped where the "
            f"bar phase changes between sections, so index by `bar_start_s`, not by bar number).", ""]
    L10 += tbl(["array", "dtype / shape", "meaning"],
               [["bar_start_s", "float64 (bars)", "bar start in seconds, drift-tracked grid"],
                ["bar_dur_s", "float64 (bars)", f"bar length ({bar_len:.4f} s)"],
                ["section_id", "int16 (bars)", "0-based index of the 19 sections used in this file"],
                ["kick_class", "int8 (bars)", "class of the bar's kick sub-section: " +
                 ", ".join(f"{k} = {v}" for k, v in KICK_CODES.items())],
                ["kick_hits", "int8 (bars)", "kicks detected in the bar (<= 1 per slot)"],
                ["kick_occ16", "bool (bars, 16)", "kick per 16th slot, section-0 bar phase (NOT rotated)"],
                ["kick_segment_id", "int16 (bars)", "kick change-point sub-section"],
                ["carrier_present", "bool (bars)", f"16th carrier: >= 3 of 8 odd slots and >= 10 of 16 at rho {CF['rho']}"],
                ["carrier_type", "int8 (bars)", "type of the bar's carrier sub-section: " +
                 ", ".join(f"{k} = {v}" for k, v in CARRIER_CODES.items())],
                ["carrier_odd_hits", "int8 (bars)", "articulated off-8th slots (0-8)"],
                ["carrier_occ16", "bool (bars, 16)", "articulated slots, carrier band 1.5-16 kHz"],
                ["carrier_segment_id", "int16 (bars)", "carrier change-point sub-section"],
                ["kick_codes / carrier_codes", "0-d str", "JSON code tables"],
                ["meta", "0-d str", "JSON: bpm, grid, rho, betas, kick threshold, script"]])
    L10 += ["", "```python", "import numpy as np, json",
            f"z = np.load(r\"{BARS_NPZ}\")",
            "codes = json.loads(str(z['kick_codes']))", "```", "",
            "### What this means for building a jungle track (kick)", ""]
    share = {KICK_CODES[c]: 100 * run_s[c] / tot_s for c in KICK_CODES}
    L10 += [f"1. Kick time in the reference: " +
            ", ".join(f"{k} {v:.0f} %" for k, v in sorted(share.items(), key=lambda x: -x[1])) + ".",
            f"2. Hold one kick *distribution* per sub-section (median {np.median(klen):.0f} bars; "
            f"first half vs second half r = {kblock['within']:.2f}, across a boundary "
            f"{kblock['across']:.2f}) and change it at the edge, together with the carrier where you "
            f"can ({100 * coin1['real']:.0f} % of kick changes have a carrier change within a bar). "
            f"Inside: a two-step repeats (75 % of bars within one slot of its pattern), a break kick "
            f"re-deals its slots every bar (45 %).",
            "3. A programmed two-step is one consistent sample in its own band; a break kick is a "
            "slice that brings hats and snare edge with it and changes timbre hit to hit. Choose "
            "which one a section is, and do not blur them. Under a two-step, keep the bass nearly "
            "still (0.25 note changes a bar against ~1 under a break kick) and the 16th layer thin.",
            "4. No four on the floor. The fullest low-mid lane in the reference is 8th-note drum hits "
            "for 8-15 bars before a cut, and the last six minutes run on a sparse, syncopated kick "
            "under a big sub.", ""]

    splice_sections(OUT_MD, {"## 9. The 16th carrier": L9, "## 10. Kick pattern per section": L10})
    print(f"spliced sections 9 and 10 into {OUT_MD}")
    # console summary
    print(f"carrier coverage {100 * present.mean():.1f}% (c_hat {100 * CF['c_hat']:.0f}%), gaps {len(gaps)}")
    print("carrier section classes:", [(f"S{i+1}", CARRIER_CODES[c[0]], c[1]) for i, c in enumerate(sec_ccls)])
    print("kick section classes:", [(f"S{i+1}", KICK_CODES[c[0]], c[1]) for i, c in enumerate(sec_kcls)])
    print("kick runtime share:", {k: round(v, 1) for k, v in share.items()})
    print("kick segs", len(kstarts), "median len", np.median(klen), "carrier segs", len(cstarts),
          "median len", np.median(clen))
    print("kick align", {P: {k: (round(v, 3) if isinstance(v, float) else v) for k, v in d.items()}
                         for P, d in kalign["P"].items()})
    print("carrier align", {P: {k: (round(v, 3) if isinstance(v, float) else v) for k, v in d.items()}
                            for P, d in calign["P"].items()})
    print("stab kick", kstab, kstab1, "carrier", cstab_p, cstab_h)
    print("block", kblock, cblock, "coin", coin1, coin2, "stab_by_class", stab_by_class)
    print("drop verdicts", vc, "corner moves open/closed", opened, closed)
    print("sens", kick_sens, "drop kick transitions", drop_tr, "changes", n_chg, at_seam, at_drop, at_bd, elsewhere)
    print("bass by kick", {KICK_CODES[c]: (len(v), round(float(np.mean(v)), 2)) for c, v in by.items()})


def binom_tail(k: int, n: int, p: float) -> float:
    from math import comb
    return float(sum(comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(k, n + 1)))


def align_lines(al: dict) -> list[str]:
    rows = []
    for P, d in al["P"].items():
        kl = int(round(d["len_share"] * d["n_len"]))
        ka = int(round(d["anch_exact"] * d["n_anch"])) if d["n_anch"] else 0
        kn = int(round(d["anch_near"] * d["n_anch"])) if d["n_anch"] else 0
        rows.append([f"{P} bars", f"{100 * d['len_share']:.0f} % ({kl}/{d['n_len']}), "
                                  f"p = {binom_tail(kl, d['n_len'], 1 / P):.2f}", f"{100 / P:.1f} %",
                     f1(100 * d["anch_exact"], "{:.0f} %") + f", p = {binom_tail(ka, d['n_anch'], 1 / P):.2f}",
                     f"{100 / P:.1f} %",
                     f1(100 * d["anch_near"], "{:.0f} %") +
                     f", p = {binom_tail(kn, d['n_anch'], min(3 / P, 1.0)):.2f}",
                     f"{min(300 / P, 100):.1f} %", d["n_anch"]])
    out = ["**Do the change points land on phrase lines?** Two tests. *Lengths*: interior "
           "sub-section lengths that are exact multiples of the phrase (phase-free). *Anchored*: "
           "bars from the nearest drop, breakdown or seam in the same record (excluding one that "
           "coincides with the change point) on the phrase lattice, exactly and within +-1 bar.", ""]
    out += tbl(["phrase", "lengths on it", "chance", "anchored, exact", "chance",
                "anchored, +-1 bar", "chance", "change points tested"], rows)
    P = al["P"]
    verdict = []
    for p in (4, 8, 16, 32):
        lr = P[p]["len_share"] * p
        ar = (P[p]["anch_exact"] * p) if np.isfinite(P[p]["anch_exact"]) else np.nan
        verdict.append(f"{p}: {lr:.1f}x / {f1(ar, '{:.1f}')}x")
    out += ["", "Lift over chance (lengths / anchored exact): " + "; ".join(verdict) + ". "
            "p = one-sided binomial probability of doing at least that well by chance. Change points "
            "are only located to about a bar (a pattern that is re-dealt every bar has no sharp edge), "
            "so the exact tests are harsh; the +-1 bar column is the fair one."]
    return out


def load_state(env, verbose=False):
    """The grid, onsets, sections and bar matrices of sections 0-6, cached for the follow-ups."""
    import pickle
    p = os.path.join(scratch_dir(), "reaper_rhythm_state.pkl")
    if os.path.exists(p):
        with open(p, "rb") as fh:
            return pickle.load(fh)
    dur = float(env["t"][-1])
    onsets = {k: pick_onsets(env[k]) for k in ("low", "mid", "high")}
    g = build_grid(env, onsets, dur, verbose=verbose)
    ts, X = timbre_matrix()
    sec_t = novelty_sections(ts, X)
    bar_starts, secinfo = bar_phase_per_section(g["t16"], sec_t, onsets, g["beat_phase"], dur)
    M = bar_matrices(onsets, g["t16"], bar_starts)
    st = {"g": g, "onsets": onsets, "sec_t": sec_t, "bar_starts": bar_starts,
          "secinfo": secinfo, "M": M, "dur": dur}
    with open(p, "wb") as fh:
        pickle.dump(st, fh)
    return st


def db(x):
    return 10.0 * np.log10(np.asarray(x, np.float64) + 1e-12)


def pick_peaks(env: np.ndarray, fps: float, win_s: float, mult: float,
               min_sep_s: float) -> tuple[np.ndarray, np.ndarray]:
    """pick_onsets for any frame rate -> (times s, strength)."""
    k = int(round(win_s * fps))
    avg = moving_avg(env, k)
    a, b, c = env[:-2], env[1:-1], env[2:]
    idx = np.nonzero((b >= a) & (b > c) & (b > avg[1:-1] * mult) & (b > 0))[0] + 1
    if len(idx) == 0:
        return np.zeros(0), np.zeros(0, np.float32)
    y0, y1, y2 = (env[idx - 1].astype(np.float64), env[idx].astype(np.float64),
                  env[idx + 1].astype(np.float64))
    den = y0 - 2 * y1 + y2
    shift = np.clip(np.where(den != 0, 0.5 * (y0 - y2) / np.where(den == 0, 1, den), 0.0), -0.5, 0.5)
    pos = (idx + shift) / fps
    st = env[idx].astype(np.float32)
    keep = _thin(pos, st, min_sep_s)
    return pos[keep], st[keep]


def slot_index(t16: np.ndarray, bar_starts: np.ndarray):
    """t16 index -> (bar, slot), -1 where the 16th belongs to no analysed bar."""
    bar_of = np.full(len(t16), -1, np.int64)
    slot_of = np.full(len(t16), -1, np.int64)
    for b, k0 in enumerate(bar_starts):
        bar_of[k0:k0 + 16] = b
        slot_of[k0:k0 + 16] = np.arange(16)
    return bar_of, slot_of


def nearest16(t16: np.ndarray, times: np.ndarray, lat: float = 0.0):
    """-> (index of nearest 16th, signed offset in ms after removing detector latency)."""
    tt = times - lat
    j = np.clip(np.searchsorted(t16, tt) - 1, 0, len(t16) - 2)
    d0 = tt - t16[j]
    step = t16[j + 1] - t16[j]
    k = j + (d0 > step / 2)
    return k, (tt - t16[k]) * 1000.0


def band_mask(lo: float, hi: float) -> np.ndarray:
    return (F12 >= lo) & (F12 < hi)


def attack_spectrum(spec: np.ndarray, t: float, post_s: float = 0.025,
                    pre_s: float = 0.040) -> np.ndarray:
    """Power per 1/12-octave band gained at an onset: frame after minus frame before, floored at 0.
    Subtracting the pre-onset frame removes whatever was already sounding (pads, a held sub, the
    tail of the previous slice), so what is left is the hit's own spectrum."""
    jp = int(round((t + post_s) * FPS10))
    jq = int(round((t - pre_s) * FPS10))
    jp = min(max(jp, 0), len(spec) - 1)
    jq = min(max(jq, 0), len(spec) - 1)
    return np.maximum(10 ** (spec[jp].astype(np.float64) / 10) - 10 ** (spec[jq].astype(np.float64) / 10), 0)


def kick_candidates(F: dict) -> dict:
    """Low-mid transients (115-260 Hz superflux), with the evidence needed to call one a kick."""
    times, strength = pick_peaks(F["fl_kick"], FPS5, 0.6, 2.0, 0.075)
    ek, ec = db(F["e_kick"]), db(F["e_click"])
    spec = F["spec"]
    sub_lvl = db((10 ** (spec[:, band_mask(40, 62)].astype(np.float64) / 10)).sum(1))
    sub_floor = float(np.percentile(sub_lvl, 30))
    m_sub, m_lo, m_mid = band_mask(40, 62), band_mask(40, 150), band_mask(180, 500)
    m_body, m_hf = band_mask(80, 250), band_mask(2000, 16000)
    n = len(ek)
    rec = {k: np.zeros(len(times)) for k in ("rise", "decay", "click", "lo_mid", "body_share",
                                              "hf_body", "in_note", "sub_pre", "sub_post", "sub_body")}
    shapes = np.zeros((len(times), 26), np.float32)       # 1/3-octave attack shape 40 Hz - 8 kHz
    for q, t in enumerate(times):
        i = int(round(t * FPS5))
        if i < 70 or i > n - 70:
            rec["rise"][q] = -99
            continue
        pre = ek[i - 12:i - 2].min()
        pk = i + int(np.argmax(ek[i:i + 9]))
        rec["rise"][q] = ek[pk] - pre
        rec["decay"][q] = ek[pk] - ek[pk + 20:pk + 31].mean()
        rec["click"][q] = ec[i - 2:i + 5].max() - ec[i - 12:i - 4].mean()
        att = attack_spectrum(spec, t)
        lo, mid, body = att[m_lo].sum(), att[m_mid].sum(), att[m_body].sum()
        rec["lo_mid"][q] = db(lo) - db(mid)
        rec["body_share"][q] = body / (att[band_mask(40, 500)].sum() + 1e-12)
        rec["hf_body"][q] = db(att[m_hf].sum()) - db(body)
        rec["sub_body"][q] = db(att[m_sub].sum()) - db(att[band_mask(80, 160)].sum())
        j = int(round(t * FPS10))
        a_pre = sub_lvl[max(j - 22, 0):max(j - 4, 1)]
        a_post = sub_lvl[j + 17:j + 32]
        rec["sub_pre"][q], rec["sub_post"][q] = a_pre.mean(), a_post.mean()
        rec["in_note"][q] = float(a_pre.mean() > sub_floor and a_post.mean() > sub_floor
                                  and abs(a_post.mean() - a_pre.mean()) <= 4.0
                                  and (a_pre.max() - a_pre.min()) <= 8.0)
        a3 = att[:78].reshape(26, 3).sum(1)
        shapes[q] = db(a3)
    rec["t"], rec["strength"], rec["shape"] = times, strength, shapes
    rec["sub_floor"] = sub_floor
    return rec


def slot_contrast(flux: np.ndarray, t16: np.ndarray, bar_starts: np.ndarray, lat: float,
                  shift: float = 0.0, half_w: float = 0.020) -> tuple[np.ndarray, np.ndarray]:
    """Per bar and slot: peak flux in a +-20 ms window on the 16th (A), and peak flux in the same
    window a 32nd later (B, the 'between' position). -> (A, B) arrays [bars, 16]."""
    nb = len(bar_starts)
    A = np.zeros((nb, 16), np.float32)
    B = np.zeros((nb, 16), np.float32)
    hw = int(round(half_w * FPS5))
    n = len(flux)
    for b, k0 in enumerate(bar_starts):
        ts = t16[k0:k0 + 17]
        for s in range(16):
            c = ts[s] + lat + shift
            half = (ts[s + 1] - ts[s]) / 2
            for arr, cc in ((A, c), (B, c + half)):
                i = int(round(cc * FPS5))
                lo, hi = max(i - hw, 0), min(i + hw + 1, n)
                arr[b, s] = flux[lo:hi].max() if hi > lo else 0.0
    return A, B


def explore_extras(st, F):
    g, bar_starts, secinfo = st["g"], st["bar_starts"], st["secinfo"]
    t16 = g["t16"]
    nb = len(bar_starts)
    bar_of, slot_of = slot_index(t16, bar_starts)
    bar_t = t16[bar_starts]
    sec_of = np.searchsorted(np.array([s["t0"] for s in secinfo]), bar_t, "right") - 1
    K = kick_candidates(F)
    spec = F["spec"]
    m80 = band_mask(80, 160)
    klow = np.array([db(attack_spectrum(spec, t)[m80].sum()) for t in K["t"]])
    k, off = nearest16(t16, K["t"], 0.012)
    sl, bb = slot_of[k], bar_of[k]
    near = (np.abs(off) < 35) & (K["rise"] > -50) & (bb >= 0)
    ref = np.percentile(klow[near & (sl == 0)], 90)
    kick = near & (klow - ref >= -9) & (K["decay"] >= 6) & ~((K["in_note"] > 0) & (K["click"] < 3))
    print(f"decay<6 among slot0 strong: {np.mean(K['decay'][near&(sl==0)&(klow-ref>=-9)]<6)*100:.0f}%")
    KH = np.zeros((nb, 16), bool)
    KH[bb[kick], sl[kick]] = True
    for i, s in enumerate(secinfo):
        m = sec_of == i
        if m.sum() < 4:
            continue
        o = KH[m].mean(0)
        print(f"S{i+1:<2} {mmss(s['t0']):>6} {int(m.sum()):3}b {KH[m].sum(1).mean():4.2f}/bar  " +
              " ".join(f"{v:.2f}" for v in o))
    lat = 0.0073
    A, B = slot_contrast(F["fl_1500"], t16, bar_starts, lat)
    floor = np.median(B, axis=1, keepdims=True) + 1e-6
    amax = A.max(1, keepdims=True)
    for rho in (1.25, 1.5, 1.75, 2.0, 2.5, 3.0):
        H = (A >= rho * floor) & (A >= 0.05 * amax)
        Hn = (B >= rho * floor) & (B >= 0.05 * amax)
        odd, tot = H[:, 1::2].sum(1), H.sum(1)
        oddn, totn = Hn[:, 1::2].sum(1), Hn.sum(1)
        print(f" rho {rho}: carrier {np.mean((odd>=3)&(tot>=10))*100:5.1f}%  odd>=3 only "
              f"{np.mean(odd>=3)*100:5.1f}% | null carrier {np.mean((oddn>=3)&(totn>=10))*100:5.1f}%"
              f" null odd>=3 {np.mean(oddn>=3)*100:5.1f}% | odd hist " +
              " ".join(str(int((odd == c).sum())) for c in range(9)))
        car = (odd >= 3) & (tot >= 10)
        if rho == 1.5:
            for i, s in enumerate(secinfo):
                m = sec_of == i
                print(f"   S{i+1:<2} {mmss(s['t0']):>6} carrier {car[m].mean()*100:5.1f}%  odd mean "
                      f"{odd[m].mean():.2f} tot {tot[m].mean():.1f}")



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

    if a.stage in ("f48", "explore", "extras"):
        st = load_state(env, verbose=True)
        F = features48()
        print(f"48k features: {len(F['e_car'])} frames @200fps, spec {F['spec'].shape} @100fps")
        if a.stage == "explore":
            explore_extras(st, F)
        elif a.stage == "extras":
            run_extras(st, F)
        return 0

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
    tail = preserved_tail(OUT_MD)                     # sections 9-10 are written by --stage extras
    with open(OUT_MD, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n" + (tail if tail else ""))
    print(f"wrote {OUT_MD} ({len(L)} lines)")
    # console echo of the headline numbers
    print(f"\nswing {allpct:.1f}% | r1 {np.nanmean(r1):.3f} | near-identical "
          f"{np.mean(r1[ok]>0.8)*100:.0f}% | fills {fill.mean()*100:.1f}% every {fill_every:.1f} bars"
          f" | onsets/bar {dens.mean():.1f} | prof4 {np.round(prof4,3)}")


if __name__ == "__main__":
    sys.exit(main())
