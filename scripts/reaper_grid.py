"""REAPER GRID - a trustworthy tempo / beat / bar grid for the reference DJ set.

The reference wav is STRUCTURAL SOURCE MATERIAL ONLY (the user's rule): nothing here reads or writes
audio samples out of it, nothing is lifted or resampled. Everything below runs on the cached feature
frames from scripts/reaper_features.py and emits numbers.

Why this exists: reaper_features.py fits ONE global tempo (165.83 BPM) to the whole 21-minute file and
its beat-phase confidence came out ~1.04, i.e. every phase scored the same, i.e. the grid is noise. A
DJ set is several tracks with different tempi and beatmatched transitions, so the grid has to be local.

Method, in order:
  1. onset envelopes   log-compressed spectral flux, local-mean removed, broadband + low + high
  2. tempogram         8 s windows / 1 s hop, FFT autocorrelation, comb over lag multiples 1..4.
                       The AC is tapered and sinc-upsampled first - see tempogram() for why a naive
                       version reports the same BPM in every window and calls it confidence
  3. tempo Viterbi     piecewise-constant BPM path (L1 penalty on BPM change), used only to hand the
                       beat tracker a per-frame period
  4. beat DP           Ellis-style dynamic programming with that per-frame period, so phase is
                       continuous by construction and a real tempo change would be followed
  5. stable stretches  bottom-up piecewise-LINEAR fit of beat time vs beat index: a constant tempo is
                       a straight line there, so each piece is a stable stretch and its slope gives
                       the period far more precisely than any 8 s window can. Second DP pass with the
                       refined periods, then snap the beats onto the line and polish sub-frame
  6. downbeats         beat-synchronous low-band onset, 4-state Viterbi over bar position with a
                       switch penalty (so the bar phase can legally move at a mix), cross-checked
                       against broadband onset and per-beat spectral change
  7. confidence        two measures, because they answer different questions: salience (is there a
                       pulse here at all) and beat-vs-off-beat-8th (is the pulse on the beat)

    python scripts/reaper_grid.py                 # build + save grid.npz, print the report tables
    python scripts/reaper_grid.py --report        # re-print tables from a saved grid.npz
    python scripts/reaper_grid.py --diag          # tempo / phase / beat-phase-profile diagnostics

Result for this file: one tempo, 165.99 BPM, the whole 21 minutes; one beat-phase step at 15:13.9.
Output: C:\\Users\\eric\\Downloads\\reaper_cache\\grid.npz - format in save_grid() and in
tracks/2026-09-16_reaper/grid.md.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np

CACHE = r"C:\Users\eric\Downloads\reaper_cache"
OUT = os.path.join(CACHE, "grid.npz")

BPM_LO, BPM_HI, BPM_STEP = 140.0, 200.0, 0.05
WIN_S, HOP_S = 8.0, 1.0
TEMPO_LAMBDA = 0.02          # cost per BPM of change in the tempo Viterbi
COMB_WEIGHTS = ((1, 1.0), (2, 0.6), (3, 0.4), (4, 0.3))
TIGHTNESS = 80.0             # beat-DP penalty on log(inter-beat / period) ** 2
BAR_SWITCH_PEN = 8.0         # cost of the bar phase jumping at a mix
SEG_BLOCK = 16               # bottom-up piecewise-linear segmentation of the beat times
SEG_RESID_MS = 12.0
SEG_MIN_BEATS = 48


# ----------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------
def moving_average(x: np.ndarray, k: int) -> np.ndarray:
    k = max(1, int(k) | 1)
    c = np.concatenate([[0.0], np.cumsum(x, dtype=np.float64)])
    half = k // 2
    lo = np.clip(np.arange(len(x)) - half, 0, len(x))
    hi = np.clip(np.arange(len(x)) + half + 1, 0, len(x))
    return (c[hi] - c[lo]) / np.maximum(hi - lo, 1)


def gauss_smooth(x: np.ndarray, sigma: float) -> np.ndarray:
    if sigma <= 0:
        return x
    r = int(np.ceil(3 * sigma))
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma) ** 2)
    k /= k.sum()
    return np.convolve(x, k, mode="same")


def onset_envelope(raw: np.ndarray, fps: float, detrend_s: float = 1.5) -> np.ndarray:
    """log-compress, remove a running mean, half-wave rectify, unit std."""
    raw = np.asarray(raw, np.float64)
    scale = np.median(raw[raw > 0]) if np.any(raw > 0) else 1.0
    e = np.log1p(raw / (scale + 1e-12))
    e = np.maximum(e - moving_average(e, int(round(detrend_s * fps))), 0.0)
    s = e.std()
    return e / (s if s > 1e-12 else 1.0)


def load_envelopes() -> dict:
    meta = json.load(open(os.path.join(CACHE, "meta.json")))
    fps = float(meta["fps"])
    f = np.load(os.path.join(CACHE, "frames.npz"))
    env = {
        "full": onset_envelope(f["flux"], fps),
        "low": onset_envelope(f["flux_sub"].astype(np.float64) + f["flux_bass"], fps),
        "high": onset_envelope(f["flux_high"].astype(np.float64) + f["flux_air"], fps),
        # raw band ENERGY, for the independent downbeat check (what changes, not what attacks)
        "bands": np.stack([f["sub"].astype(np.float64) + f["bass"], f["lowmid"], f["mid"],
                           f["high"].astype(np.float64) + f["air"]]),
    }
    env["fps"] = fps
    env["dur"] = float(meta["duration_s"])
    env["old_bpm"] = float(meta["bpm"])
    env["rms"] = f["rms"].astype(np.float64)
    return env


# ----------------------------------------------------------------------
# 2. tempogram
# ----------------------------------------------------------------------
def tempogram(env: np.ndarray, fps: float):
    W, H = int(round(WIN_S * fps)), int(round(HOP_S * fps))
    n = len(env)
    starts = np.arange(0, max(1, n - W + 1), H)
    bpms = np.arange(BPM_LO, BPM_HI + 1e-9, BPM_STEP)
    lags = 60.0 * fps / bpms
    maxlag = W // 2
    idx = np.arange(maxlag, dtype=np.float64)
    unbias = W / np.maximum(W - idx, 1.0)
    # The autocorrelation only exists at integer lags. Interpolating it linearly makes the comb score
    # piecewise linear, so its maximum snaps to whichever BPM puts every tooth on an integer lag -
    # the same BPM in every window, a resolution the 8 s window does not actually have. Taper the AC
    # and sinc-upsample it x8 so the comb is a genuinely smooth function of BPM.
    U = 8
    taper = 0.5 * (1.0 + np.cos(np.pi * idx / maxlag))
    idxu = np.arange(maxlag * U, dtype=np.float64) / U
    nfft = 1 << int(np.ceil(np.log2(2 * W)))
    scores = np.zeros((len(starts), len(bpms)))
    for i, s in enumerate(starts):
        x = env[s:s + W]
        x = x - x.mean()
        if x.std() < 1e-9:
            continue
        X = np.fft.rfft(x, nfft)
        ac = np.fft.irfft(X * np.conj(X), nfft)[:maxlag]
        ac = ac / (ac[0] + 1e-12) * unbias * taper
        acu = np.fft.irfft(np.fft.rfft(ac), maxlag * U) * U
        sc = np.zeros(len(bpms))
        for k, w in COMB_WEIGHTS:
            L = k * lags
            ok = L < maxlag - 1
            sc += w * np.where(ok, np.interp(L, idxu, acu), 0.0)
        scores[i] = sc
    t = (starts + W / 2.0) / fps
    return t, bpms, scores


def tempo_viterbi(bpms: np.ndarray, scores: np.ndarray, lam: float = TEMPO_LAMBDA,
                  pad: float = 4.0) -> np.ndarray:
    """piecewise-constant BPM path: maximise sum(score) - lam * sum|dBPM|.

    Narrowed to the band the raw per-window peaks actually occupy (+/- pad BPM) so the state space
    stays small enough for a fine BPM step.
    """
    peak = bpms[np.argmax(scores, axis=1)]
    keep = (bpms >= np.percentile(peak, 1) - pad) & (bpms <= np.percentile(peak, 99) + pad)
    bpms, scores = bpms[keep], scores[:, keep]
    pen = lam * np.abs(bpms[:, None] - bpms[None, :])
    n_w, n_b = scores.shape
    dp = scores[0].copy()
    back = np.zeros((n_w, n_b), np.int32)
    for i in range(1, n_w):
        cand = dp[:, None] - pen                 # from j (rows) to k (cols)
        back[i] = np.argmax(cand, axis=0)
        dp = cand[back[i], np.arange(n_b)] + scores[i]
    path = np.zeros(n_w, np.int32)
    path[-1] = int(np.argmax(dp))
    for i in range(n_w - 1, 0, -1):
        path[i - 1] = back[i, path[i]]
    return bpms[path]


# ----------------------------------------------------------------------
# 4. beat dynamic programming with a time-varying period
# ----------------------------------------------------------------------
def beat_dp(env: np.ndarray, period: np.ndarray, tightness: float = TIGHTNESS) -> np.ndarray:
    """Ellis-style DP. period[t] = frames per beat at frame t. Returns beat frame indices."""
    n = len(env)
    local = gauss_smooth(env, 1.4)
    local = local / (local.std() + 1e-12)
    cum = np.zeros(n)
    back = np.full(n, -1, np.int32)
    cache: dict[int, np.ndarray] = {}
    for t in range(n):
        P = period[t]
        lo = t - int(round(2.0 * P))
        hi = t - int(round(0.5 * P))
        if hi < 1:
            cum[t] = local[t]
            continue
        lo = max(lo, 0)
        key = (hi - lo) * 4096 + int(round(P * 20))
        F = cache.get(key)
        if F is None:
            tau = (t - np.arange(lo, hi + 1)).astype(np.float64)
            F = -tightness * np.log(np.maximum(tau, 1e-9) / P) ** 2
            cache[key] = F
        cand = cum[lo:hi + 1] + F
        j = int(np.argmax(cand))
        cum[t] = local[t] + cand[j]
        back[t] = lo + j
    tail = max(0, n - int(round(4 * period[-1])))
    t = tail + int(np.argmax(cum[tail:]))
    beats = []
    while t >= 0:
        beats.append(t)
        t = back[t]
    return np.array(beats[::-1], np.int64)


# ----------------------------------------------------------------------
# 5. segments + per-segment least-squares refit
# ----------------------------------------------------------------------
def _linfit(y: np.ndarray, a: int, b: int):
    """least-squares beat time ~ c0 + c1 * beat_index over [a, b). Returns (c0, c1, sse)."""
    x = np.arange(a, b, dtype=np.float64)
    yy = y[a:b]
    n = len(x)
    sx, sy = x.sum(), yy.sum()
    sxx, sxy = (x * x).sum(), (x * yy).sum()
    den = n * sxx - sx * sx
    if den <= 0:
        return float(yy.mean()), 0.0, 0.0
    c1 = (n * sxy - sx * sy) / den
    c0 = (sy - c1 * sx) / n
    r = yy - (c0 + c1 * x)
    return c0, c1, float((r * r).sum())


def piecewise_tempo(beats_s: np.ndarray, block: int = SEG_BLOCK,
                    resid_ms: float = SEG_RESID_MS, min_beats: int = SEG_MIN_BEATS):
    """Bottom-up piecewise-LINEAR fit of beat time vs beat index.

    A constant tempo is a straight line here, so each surviving piece is a stable-tempo stretch and
    its slope is the period to sub-0.01 BPM. Merging stops when a merged piece can no longer be
    explained by one line to within `resid_ms` RMS - which is what a real tempo change looks like.
    """
    n = len(beats_s)
    bounds = list(range(0, n, block))
    if bounds[-1] != n:
        bounds.append(n)
    if bounds[-1] - bounds[-2] < block // 2 and len(bounds) > 2:
        bounds.pop(-2)
    segs = [[bounds[i], bounds[i + 1]] for i in range(len(bounds) - 1)]

    def merged_rms(i):
        a, b = segs[i][0], segs[i + 1][1]
        _, _, sse = _linfit(beats_s, a, b)
        return np.sqrt(sse / max(b - a - 2, 1)) * 1000.0

    costs = [merged_rms(i) for i in range(len(segs) - 1)]
    while costs and min(costs) < resid_ms:
        i = int(np.argmin(costs))
        segs[i] = [segs[i][0], segs[i + 1][1]]
        del segs[i + 1]
        del costs[i]
        if i < len(segs) - 1:
            costs[i] = merged_rms(i)
        if i > 0:
            costs[i - 1] = merged_rms(i - 1)

    # absorb stretches too short to be a track into whichever neighbour fits them better
    changed = True
    while changed and len(segs) > 1:
        changed = False
        for i, (a, b) in enumerate(segs):
            if b - a >= min_beats:
                continue
            left = merged_rms(i - 1) if i > 0 else np.inf
            right = merged_rms(i) if i < len(segs) - 1 else np.inf
            j = i - 1 if left <= right else i
            segs[j] = [segs[j][0], segs[j + 1][1]]
            del segs[j + 1]
            changed = True
            break
    out = []
    for a, b in segs:
        c0, c1, sse = _linfit(beats_s, a, b)
        out.append({"i0": a, "i1": b, "t0": float(beats_s[a]),
                    "t1": float(beats_s[b - 1] + c1), "phase": c0, "period": c1,
                    "bpm": 60.0 / c1 if c1 > 0 else float("nan"),
                    "resid_ms": float(np.sqrt(sse / max(b - a - 2, 1)) * 1000.0),
                    "beats": b - a})
    return out


def refit_segment(beat_s: np.ndarray):
    """least-squares beat_s ~ a + b*n over a stretch; returns (phase, period_s, resid_ms)."""
    if len(beat_s) < 4:
        return None
    n = np.arange(len(beat_s), dtype=np.float64)
    A = np.stack([np.ones_like(n), n], axis=1)
    coef, *_ = np.linalg.lstsq(A, beat_s, rcond=None)
    resid = beat_s - A @ coef
    return float(coef[0]), float(coef[1]), float(np.sqrt((resid ** 2).mean()) * 1000.0)


# ----------------------------------------------------------------------
# 6. downbeats
# ----------------------------------------------------------------------
def beat_feature(env: np.ndarray, beats_f: np.ndarray, fps: float,
                 pre_s: float = 0.045, post_s: float = 0.065) -> np.ndarray:
    a = np.maximum(0, (beats_f - pre_s * fps).astype(int))
    b = np.minimum(len(env) - 1, (beats_f + post_s * fps).astype(int)) + 1
    return np.array([env[i:j].max() if j > i else 0.0 for i, j in zip(a, b)])


def downbeat_viterbi(low_b: np.ndarray, win: int = 33, pen: float = BAR_SWITCH_PEN):
    """4-state Viterbi over bar position. Emission = locally z-scored low-band onset when state==0."""
    z = low_b - moving_average(low_b, win)
    z = z / (moving_average(np.abs(z), 4 * win) + 1e-9)
    n = len(z)
    dp = np.where(np.arange(4) == 0, z[0], 0.0)
    back = np.zeros((n, 4), np.int8)
    for i in range(1, n):
        keep = np.array([dp[(s - 1) % 4] for s in range(4)])          # legal 0->1->2->3->0
        jump = dp.max() - pen
        src = np.array([(s - 1) % 4 for s in range(4)], np.int8)
        take = keep >= jump
        back[i] = np.where(take, src, np.int8(np.argmax(dp)))
        dp = np.where(take, keep, jump) + np.where(np.arange(4) == 0, z[i], 0.0)
    path = np.zeros(n, np.int8)
    path[-1] = int(np.argmax(dp))
    for i in range(n - 1, 0, -1):
        path[i - 1] = back[i, path[i]]
    return path, z


def beat_novelty(bands: np.ndarray, beats_s: np.ndarray, fps: float) -> np.ndarray:
    """Independent downbeat cue: how much the spectrum CHANGES from one beat to the next.

    New elements - a bass note, a pad, the break coming back - land on bar one, so the 4-phase
    profile of this should agree with the kick-onset profile. It is a different measurement from the
    onset flux (energy level, not attack), so agreement is real corroboration.
    """
    e = np.zeros((bands.shape[0], len(beats_s)))
    edges = np.clip((beats_s * fps).astype(int), 0, bands.shape[1] - 1)
    for i in range(len(beats_s)):
        a = edges[i]
        b = edges[i + 1] if i + 1 < len(edges) else bands.shape[1]
        e[:, i] = bands[:, a:max(a + 1, b)].mean(axis=1)
    L = np.log10(np.maximum(e, 1e-9))
    nov = np.zeros(len(beats_s))
    nov[1:] = np.abs(np.diff(L, axis=1)).sum(axis=0)
    return nov


def bar_phase_margin(z: np.ndarray, path: np.ndarray, lo: int, hi: int) -> float:
    """How much better the chosen bar phase scores than the best rival, per bar, in z units."""
    sl = slice(lo, hi)
    zz, pp = z[sl], path[sl]
    if len(zz) < 8:
        return float("nan")
    means = [zz[pp == k].mean() if np.any(pp == k) else -9.0 for k in range(4)]
    best = means[0]
    rival = max(means[1:])
    return float(best - rival)


# ----------------------------------------------------------------------
# 7. confidence
# ----------------------------------------------------------------------
BASE_OFFSETS = np.linspace(0.18, 0.85, 12)


def beat_scores(mix: np.ndarray, low: np.ndarray, beats_s: np.ndarray, period_s: np.ndarray,
                fps: float):
    """Per-beat raw numbers the two confidence measures are built from.

    e_grid    broadband onset ON the beat
    e_base    the same at 12 offsets spread over the beat - the "any old position" baseline
    l_grid    kick-band onset ON the beat
    l_half    kick-band onset on the off-beat 8th (beat + P/2)

    The two questions these answer are different and both need asking. e_grid/e_base says IS THERE A
    PULSE HERE AT ALL - a guessed grid scores ~1. l_grid/l_half says IS THE PULSE ON THE BEAT rather
    than an 8th off, which in jungle is the only realistic rival: 16th offsets are rejected outright
    (they score ~0.2x) but the off-beat 8th is heavily populated, so this margin is the honest one.
    """
    fr = beats_s * fps
    im, il = np.arange(len(mix)), np.arange(len(low))
    return {
        "e_grid": np.interp(fr, im, mix),
        "e_base": np.stack([np.interp(fr + d * period_s * fps, im, mix) for d in BASE_OFFSETS]),
        "l_grid": np.interp(fr, il, low),
        "l_half": np.interp(fr + 0.5 * period_s * fps, il, low),
        "e_half": np.interp(fr + 0.5 * period_s * fps, im, mix),
    }


def windowed_confidence(sc: dict, beat_t: np.ndarray, win_s: float = 8.0, hop_s: float = 1.0):
    out = {k: [] for k in ("t", "grid", "z", "phase")}
    t0 = beat_t[0]
    while t0 < beat_t[-1]:
        m = (beat_t >= t0) & (beat_t < t0 + win_s)
        if m.sum() >= 6:
            b = sc["e_base"][:, m].mean(axis=1)
            out["t"].append(t0 + win_s / 2)
            out["grid"].append(sc["e_grid"][m].mean() / (b.mean() + 1e-9))
            out["z"].append((sc["e_grid"][m].mean() - b.mean()) / (b.std() + 1e-9))
            out["phase"].append((sc["l_grid"][m].mean() + sc["e_grid"][m].mean())
                                / (sc["l_half"][m].mean() + sc["e_half"][m].mean() + 1e-9))
        t0 += hop_s
    return {k: np.array(v) for k, v in out.items()}


def phase_residual(env: np.ndarray, beats_s: np.ndarray, fps: float, period_s: np.ndarray,
                   win_s: float = 8.0, hop_s: float = 1.0, span: float = 0.25):
    """Local phase offset of the onsets relative to our grid, in ms.

    Searched over +/- `span` of a beat only. Searching the whole beat is useless here: the off-beat
    8th is strong enough in jungle that an ambiguous window flips to it and reports half a beat of
    "error" that is not an error of the grid at all.
    """
    idx = np.arange(len(env))
    shifts = np.linspace(-span, span, 41)
    out_t, out_d = [], []
    t0 = beats_s[0]
    while t0 < beats_s[-1]:
        m = (beats_s >= t0) & (beats_s < t0 + win_s)
        if m.sum() >= 6:
            fr, P = beats_s[m] * fps, period_s[m] * fps
            sc = [np.interp(fr + s * P, idx, env).mean() for s in shifts]
            out_t.append(t0 + win_s / 2)
            out_d.append(shifts[int(np.argmax(sc))] * float(np.median(period_s[m])) * 1000.0)
        t0 += hop_s
    return np.array(out_t), np.array(out_d)


def best_shift(mix: np.ndarray, beats_s: np.ndarray, period_s: np.ndarray, fps: float,
               span: float = 0.15) -> float:
    """Sub-frame phase polish for one stretch: the shift that maximises broadband onset on the beat."""
    idx = np.arange(len(mix))
    shifts = np.linspace(-span, span, 121)
    sc = [np.interp(beats_s * fps + s * period_s * fps, idx, mix).mean() for s in shifts]
    return float(shifts[int(np.argmax(sc))] * np.median(period_s))


# ----------------------------------------------------------------------
# build
# ----------------------------------------------------------------------
import tempfile

# intermediate cache for the slow half - deliberately NOT in the repo, other agents work here too
SCRATCH = os.environ.get("REAPER_GRID_SCRATCH",
                         os.path.join(tempfile.gettempdir(), "reaper_grid_stage.npz"))


def stage1(force: bool = False):
    """envelopes -> tempogram -> tempo path -> beat DP. Cached, because it is the slow half."""
    if not force and os.path.exists(SCRATCH):
        d = np.load(SCRATCH)
        return {k: d[k] for k in d.files}
    env = load_envelopes()
    fps, dur = env["fps"], env["dur"]
    print(f"frames {len(env['full'])} @ {fps} fps, {dur:.1f} s; cached global bpm {env['old_bpm']:.2f}")
    mix = 1.0 * env["full"] + 0.7 * env["low"] + 0.5 * env["high"]
    mix /= mix.std()

    t_win, bpms, scores = tempogram(mix, fps)
    peak = bpms[np.argmax(scores, axis=1)]
    bpm_path = tempo_viterbi(bpms, scores)
    print(f"tempogram {scores.shape}; raw peak bpm p1/p50/p99 = "
          f"{np.percentile(peak,1):.2f}/{np.median(peak):.2f}/{np.percentile(peak,99):.2f}; "
          f"viterbi runs {1 + int((np.diff(bpm_path) != 0).sum())}")

    ft = np.arange(len(mix)) / fps
    period_frames = 60.0 * fps / np.interp(ft, t_win, bpm_path)
    beats_f = beat_dp(mix, period_frames)
    print(f"beat DP pass 1: {len(beats_f)} beats")

    d = {"mix": mix, "low": env["low"], "bands": env["bands"].astype(np.float32),
         "fps": np.array([fps]), "dur": np.array([dur]),
         "t_win": t_win, "bpm_path": bpm_path, "peak": peak, "beats_f": beats_f.astype(np.float64)}
    np.savez_compressed(SCRATCH, **d)
    return d


def build(force: bool = False, second_pass: bool = True):
    d = stage1(force)
    mix, low_env = d["mix"], d["low"]
    fps, dur = float(d["fps"][0]), float(d["dur"][0])
    t_win, bpm_path, peak = d["t_win"], d["bpm_path"], d["peak"]
    beats_s = d["beats_f"] / fps

    ibi = np.diff(beats_s)
    print(f"pass 1 beats {len(beats_s)}: ibi median {np.median(ibi)*1000:.2f} ms "
          f"({60/np.median(ibi):.3f} BPM), ibi std {np.std(ibi)*1000:.2f} ms")
    _, per_g, res_g = refit_segment(beats_s)
    print(f"single global line: {60/per_g:.3f} BPM, residual RMS {res_g:.1f} ms  "
          f"<- large residual = the set is NOT one tempo")

    pieces = piecewise_tempo(beats_s)
    print(f"piecewise-linear on the beat times: {len(pieces)} stable stretches")

    if second_pass:
        # rebuild the per-frame period from the refined stretches and re-run the DP, so the phase is
        # tracked with the right period inside every stretch instead of one global guess
        ft = np.arange(len(mix)) / fps
        bpm_f = np.full(len(mix), 60.0 / per_g)
        for p in pieces:
            m = (ft >= p["t0"] - 1.0) & (ft < p["t1"] + 1.0)
            bpm_f[m] = p["bpm"]
        bpm_f = gauss_smooth(bpm_f, 0.25 * fps)
        beats_s = beat_dp(mix, 60.0 * fps / bpm_f) / fps
        ibi = np.diff(beats_s)
        print(f"pass 2 beats {len(beats_s)}: ibi std {np.std(ibi)*1000:.2f} ms")
        pieces = piecewise_tempo(beats_s)
        print(f"piecewise-linear after pass 2: {len(pieces)} stable stretches")

    # inside a stretch a straight line IS the grid: snap to it, which kills the +/-10 ms frame jitter
    # the DP's integer-frame resolution leaves behind, then polish the stretch's phase sub-frame
    beats_s = beats_s.astype(np.float64)
    snapped = 0
    for p in pieces:
        if p["resid_ms"] >= SEG_RESID_MS * 1.5:
            continue
        n = np.arange(p["i0"], p["i1"], dtype=np.float64)
        b = p["phase"] + p["period"] * n
        shift = best_shift(mix, b, np.full(len(b), p["period"]), fps)
        beats_s[p["i0"]:p["i1"]] = b + shift
        p["phase"] += shift
        p["t0"], p["t1"] = float(beats_s[p["i0"]]), float(beats_s[p["i1"] - 1] + p["period"])
        snapped += p["beats"]
        print(f"  stretch {mmss(p['t0'])}-{mmss(p['t1'])}: {p['bpm']:.3f} BPM, "
              f"line residual {p['resid_ms']:.1f} ms, sub-frame phase polish {shift*1000:+.1f} ms")
    print(f"snapped {snapped}/{len(beats_s)} beats onto their stretch's straight line")
    seg_fit = [(p["t0"], p["t1"], p["bpm"], p["resid_ms"], float(p["beats"])) for p in pieces]

    # a split between two stretches at the same BPM is a PHASE step, not a tempo change: measure it
    steps = []
    for p, q in zip(pieces[:-1], pieces[1:]):
        i = q["i0"]
        expect = p["phase"] + p["period"] * i             # where stretch 1 would have put that beat
        off = (beats_s[i] - expect + 0.5 * p["period"]) % p["period"] - 0.5 * p["period"]
        steps.append((float(beats_s[i]), float(off)))
        print(f"  boundary {mmss(beats_s[i])}: dBPM {q['bpm']-p['bpm']:+.3f} "
              f"({abs(q['bpm']-p['bpm'])/p['bpm']*100:.3f}%), beat-phase step {off*1000:+.0f} ms "
              f"= {off/p['period']:+.2f} of a beat")

    old = json.load(open(os.path.join(CACHE, "meta.json")))
    ob, n_common = np.array(old["beats_s"]), min(len(beats_s), len(old["beats_s"]))
    err = (ob[:n_common] - beats_s[:n_common]) * 1000.0
    print(f"  vs the old single-tempo grid ({old['bpm']:.2f} BPM, period "
          f"{60/old['bpm']*1000:.3f} ms vs {pieces[0]['period']*1000:.3f} ms here): its beats run "
          f"{err[0]:+.0f} ms out at the start and {err[-1]:+.0f} ms "
          f"({err[-1]/1000/pieces[0]['period']:+.1f} beats) out by the end")

    # the published BPM timeline is the piecewise fit (precise to ~0.01 BPM), not the tempogram path
    bpm_win = np.full(len(t_win), np.nan)
    for p in pieces:
        bpm_win[(t_win >= p["t0"]) & (t_win <= p["t1"])] = p["bpm"]
    bad = np.isnan(bpm_win)
    if bad.any():
        bpm_win[bad] = np.interp(t_win[bad], t_win[~bad], bpm_win[~bad])
    bpm_tempogram, bpm_path = bpm_path, bpm_win
    period_s = np.empty(len(beats_s))
    period_s[:-1] = np.diff(beats_s)
    period_s[-1] = period_s[-2]
    period_s = np.clip(period_s, 60 / BPM_HI, 60 / BPM_LO)

    # downbeats
    low_b = beat_feature(low_env, beats_s * fps, fps)
    bar_pos, zlow = downbeat_viterbi(low_b)
    downbeats_s = beats_s[bar_pos == 0]
    resets = [i for i in range(1, len(bar_pos))
              if (int(bar_pos[i]) - int(bar_pos[i - 1])) % 4 != 1]
    print(f"downbeats: {len(downbeats_s)} ({len(beats_s)/4:.0f} expected), "
          f"{len(resets)} bar-phase resets")

    # how much of the bar phase survives if the switch penalty changes? A reset that only exists at
    # one setting is the tracker chasing a fill, not a mix.
    print("  reset robustness vs BAR_SWITCH_PEN:")
    robust = set()
    for pen in (4.0, 8.0, 16.0, 32.0, 1e9):
        bp, _ = downbeat_viterbi(low_b, pen=pen)
        rs = [i for i in range(1, len(bp)) if (int(bp[i]) - int(bp[i - 1])) % 4 != 1]
        if pen == 16.0:
            robust = {min(resets, key=lambda j: abs(j - i)) for i in rs} if resets else set()
        agree = float((bp == bar_pos).mean())
        print(f"    pen {pen:>7.0f}: {len(rs):2d} resets at " +
              ", ".join(mmss(beats_s[i]) for i in rs) +
              f" | agrees with the published phase on {100*agree:5.1f}% of beats")
    print(f"  resets that survive pen=16: {', '.join(mmss(beats_s[i]) for i in sorted(robust))}")

    # independent check: does spectral CHANGE per beat pick the same bar position as the kick?
    nov = beat_novelty(d["bands"].astype(np.float64), beats_s, fps)
    fb = beat_feature(mix, beats_s * fps, fps)
    print("  bar-position profiles (published phase):")
    for lbl, v in (("kick onset", low_b), ("broadband onset", fb), ("spectral change", nov)):
        vals = [v[bar_pos == k].mean() for k in range(4)]
        win = int(np.argmax(vals))
        print(f"    {lbl:>16}: " + "  ".join(f"pos{k} {x:7.3f}" for k, x in enumerate(vals)) +
              f"   argmax=pos{win}  pos0/pos2 {vals[0]/max(vals[2],1e-9):.3f}")

    # confidence
    sc = beat_scores(mix, low_env, beats_s, period_s, fps)
    cw = windowed_confidence(sc, beats_s)
    pt, pd = phase_residual(mix, beats_s, fps, period_s)
    print(f"grid salience: median {np.median(cw['grid']):.2f}, p10 {np.percentile(cw['grid'],10):.2f}")
    print(f"beat-vs-8th  : median {np.median(cw['phase']):.2f}, "
          f"{100*np.mean(cw['phase'] < 1.0):.1f}% of windows below 1.0")
    print(f"phase residual |ms|: median {np.median(np.abs(pd)):.1f}, "
          f"p90 {np.percentile(np.abs(pd),90):.1f}")

    g = dict(beats_s=beats_s, downbeats_s=downbeats_s, bar_pos=bar_pos, t_win=t_win,
             bpm_path=bpm_path, bpm_tempogram=bpm_tempogram, cw=cw, pt=pt, pd=pd,
             seg_fit=seg_fit, zlow=zlow, fps=fps, dur=dur, resets=resets)
    save_grid(g)
    report(g)
    return 0


def seg_stats(g, a, b):
    cw, beats_s = g["cw"], g["beats_s"]
    m = (cw["t"] >= a) & (cw["t"] < b)
    mp = (g["pt"] >= a) & (g["pt"] < b)
    lo, hi = int(np.searchsorted(beats_s, a)), int(np.searchsorted(beats_s, b))
    return (float(np.median(cw["grid"][m])) if m.any() else np.nan,
            float(np.median(cw["z"][m])) if m.any() else np.nan,
            float(np.median(cw["phase"][m])) if m.any() else np.nan,
            float(np.median(np.abs(g["pd"][mp]))) if mp.any() else np.nan,
            bar_phase_margin(g["zlow"], g["bar_pos"], lo, hi))


def save_grid(g):
    seg = g["seg_fit"]
    stats = np.array([seg_stats(g, a, b) for a, b, *_ in seg], np.float64)
    np.savez_compressed(
        OUT,
        beats_s=g["beats_s"].astype(np.float64),
        downbeats_s=g["downbeats_s"].astype(np.float64),
        beat_bar_pos=g["bar_pos"].astype(np.int8),
        bpm_timeline=np.stack([g["t_win"], g["bpm_path"]], 1).astype(np.float64),
        bpm_tempogram=np.stack([g["t_win"], g["bpm_tempogram"]], 1).astype(np.float64),
        confidence=np.stack([g["cw"]["t"], g["cw"]["grid"]], 1).astype(np.float64),
        confidence_z=np.stack([g["cw"]["t"], g["cw"]["z"]], 1).astype(np.float64),
        confidence_phase=np.stack([g["cw"]["t"], g["cw"]["phase"]], 1).astype(np.float64),
        phase_residual_ms=np.stack([g["pt"], g["pd"]], 1).astype(np.float64),
        segments=np.array([[a, b, bpm] for a, b, bpm, _, _ in seg], np.float64),
        segment_fit=np.array([[r, n] for _, _, _, r, n in seg], np.float64),
        segment_stats=stats,
        bar_phase_resets_s=np.array([g["beats_s"][i] for i in g["resets"]], np.float64),
        meta=np.array([g["fps"], g["dur"], len(g["beats_s"]), len(g["downbeats_s"])], np.float64),
    )
    print(f"saved -> {OUT}")


# ----------------------------------------------------------------------
# report tables
# ----------------------------------------------------------------------
def mmss(s: float) -> str:
    return f"{int(s)//60}:{s - 60*(int(s)//60):05.2f}"


def report(g):
    beats_s, bar_pos, dur = g["beats_s"], g["bar_pos"], g["dur"]
    print("\n--- stable stretches ---")
    print(f"{'start':>9} {'end':>9} {'len_s':>7} {'bpm':>8} {'resid':>6} {'beats':>6} "
          f"{'salience':>9} {'z':>6} {'beat/8th':>9} {'|res|ms':>8} {'bar_marg':>9}")
    for a, b, bpm, res, n in g["seg_fit"]:
        s = seg_stats(g, a, b)
        print(f"{mmss(a):>9} {mmss(b):>9} {b-a:7.1f} {bpm:8.3f} {res:6.1f} {int(n):6d} "
              f"{s[0]:9.2f} {s[1]:6.2f} {s[2]:9.2f} {s[3]:8.1f} {s[4]:9.2f}")

    print("\n--- per minute ---")
    print(f"{'min':>4} {'bpm':>8} {'salience':>9} {'z':>6} {'beat/8th':>9} {'|res|ms':>8} "
          f"{'resets':>7} {'verdict':>9}")
    for k in range(int(np.ceil(dur / 60))):
        a, b = 60 * k, 60 * (k + 1)
        bw = (g["t_win"] >= a) & (g["t_win"] < b)
        mb = (beats_s >= a) & (beats_s < b)
        bp = bar_pos[mb].astype(int)
        nres = int((np.diff(bp) % 4 != 1).sum()) if len(bp) > 1 else 0
        s = seg_stats(g, a, b)
        v = "solid" if (s[0] > 3.0 and s[2] > 1.05 and nres == 0) else (
            "ok" if s[0] > 2.0 and s[2] > 1.0 else "soft")
        print(f"{k:4d} {np.median(g['bpm_path'][bw]) if bw.any() else np.nan:8.2f} "
              f"{s[0]:9.2f} {s[1]:6.2f} {s[2]:9.2f} {s[3]:8.1f} {nres:7d} {v:>9}")

    print("\n--- bar-phase resets (candidate mix markers) ---")
    for i in g["resets"]:
        t = beats_s[i]
        s = seg_stats(g, t - 8, t + 8)
        print(f"  {mmss(t):>9}  bar pos {bar_pos[i-1]} -> {bar_pos[i]}   "
              f"salience {s[0]:.2f}  beat/8th {s[2]:.2f}")


def diag(force: bool = False):
    """Everything I need to decide whether the single-tempo answer is real or a modelling artifact."""
    d = stage1(force)
    mix, fps = d["mix"], float(d["fps"][0])
    beats = d["beats_f"] / fps
    n = len(beats)

    print("\n--- local BPM from sliding linear fits of the RAW DP beats ---")
    for W in (64, 128, 256):
        loc = []
        for c in range(0, n - W, 8):
            _, c1, _ = _linfit(beats, c, c + W)
            loc.append(60.0 / c1)
        loc = np.array(loc)
        print(f"  W={W:4d} beats: min {loc.min():.3f} p5 {np.percentile(loc,5):.3f} "
              f"med {np.median(loc):.3f} p95 {np.percentile(loc,95):.3f} max {loc.max():.3f} "
              f"(spread {loc.max()-loc.min():.3f} BPM)")
    W = 128
    loc_t, loc_b = [], []
    for c in range(0, n - W, 8):
        _, c1, _ = _linfit(beats, c, c + W)
        loc_t.append(beats[c + W // 2])
        loc_b.append(60.0 / c1)
    loc_t, loc_b = np.array(loc_t), np.array(loc_b)
    print("  every 30 s:", " ".join(f"{mmss(t)}={b:.2f}" for t, b in
                                    zip(loc_t[::4], loc_b[::4]) if int(t) % 30 < 3))

    print("\n--- residual of the DP beats against ONE global straight line (ms) ---")
    c0, c1, _ = _linfit(beats, 0, n)
    r = (beats - (c0 + c1 * np.arange(n))) * 1000.0
    for k in range(0, n, 128):
        seg = r[k:k + 128]
        print(f"  {mmss(beats[k]):>8}  mean {seg.mean():8.1f}  min {seg.min():8.1f} "
              f"max {seg.max():8.1f}   (one beat = {c1*1000:.1f} ms)")

    print("\n--- localising the phase step (residual per 32 beats, 13:30-16:00) ---")
    for k in range(0, n - 32, 32):
        if not (810 <= beats[k] <= 960):
            continue
        print(f"  {mmss(beats[k]):>8}  mean {r[k:k+32].mean():8.1f} ms")

    # profiles must be measured against the ACTUAL beats: the DP beats wander +/-70 ms from any one
    # straight line, so a profile taken against the global line is smeared by that wander
    print("\n--- beat-phase profile against the ACTUAL DP beats (32 bins per beat) ---")
    P_s = np.empty(n)
    P_s[:-1] = np.diff(beats)
    P_s[-1] = P_s[-2]
    envs = {"mix": mix, "low(kick)": d["low"]}
    prof = {}
    for name, e in envs.items():
        idx = np.arange(len(e))
        p = []
        for b in range(32):
            fr = (beats + (b / 32.0) * P_s) * fps
            p.append(float(np.interp(fr[fr < len(e) - 1], idx, e).mean()))
        prof[name] = np.array(p)
    mx = {k: v.max() for k, v in prof.items()}
    print("  bin  ms      mix                         low(kick)")
    for b in range(32):
        a, c = prof["mix"][b], prof["low(kick)"][b]
        print(f"  {b:3d} {b/32*361.5:5.1f}  {a:.3f} {'#'*int(26*a/mx['mix']):<26} "
              f"{c:.3f} {'#'*int(26*c/mx['low(kick)'])}")
    for k, v in prof.items():
        pk = int(np.argmax(v))
        print(f"  {k}: peak bin {pk} = {pk/32*361.5:.1f} ms after the grid; "
              f"bin0/mean {v[0]/v.mean():.2f}, peak/mean {v.max()/v.mean():.2f}, "
              f"bin0 vs half-beat(bin16) {v[0]/v[16]:.2f}")

    print("\n--- beat level: grid vs half / double (actual beats) ---")
    for name, e in envs.items():
        idx = np.arange(len(e))
        g = float(np.interp(beats * fps, idx, e).mean())
        mid = float(np.interp((beats[:-1] + 0.5 * P_s[:-1]) * fps, idx, e).mean())
        print(f"  {name:>10}: on beats {g:.4f}   on the off-beat 8ths {mid:.4f}   "
              f"ratio {g/mid:.2f}")

    print("\n--- bar-phase profile: low-band onset by beat-in-bar, for each of the 4 phases ---")
    lb = beat_feature(d["low"], beats * fps, fps)
    fb = beat_feature(mix, beats * fps, fps)
    for k in range(4):
        print(f"  phase {k}: beat1 low {lb[k::4].mean():.3f}  broadband {fb[k::4].mean():.3f}")
    return 0


def report_only():
    z = np.load(OUT)
    print({k: z[k].shape for k in z.files})
    print("\n--- stable stretches ---")
    for (a, b, bpm), (res, n), s in zip(z["segments"], z["segment_fit"], z["segment_stats"]):
        print(f"{mmss(a):>9} {mmss(b):>9} {b-a:7.1f} {bpm:8.3f} {res:6.1f} {int(n):6d} "
              f"{s[0]:9.2f} {s[1]:6.2f} {s[2]:9.2f} {s[3]:8.1f} {s[4]:9.2f}")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Corrected tempo/beat/bar grid for the reference set.")
    ap.add_argument("--report", action="store_true", help="print tables from a saved grid.npz")
    ap.add_argument("--force", action="store_true", help="redo the cached slow stage")
    ap.add_argument("--one-pass", action="store_true", help="skip the refined second beat DP")
    ap.add_argument("--diag", action="store_true", help="tempo / phase / beat-level diagnostics")
    a = ap.parse_args(argv)
    if a.report:
        return report_only()
    if a.diag:
        return diag(a.force)
    return build(a.force, not a.one_pass)


if __name__ == "__main__":
    sys.exit(main())
