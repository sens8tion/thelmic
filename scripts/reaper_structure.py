"""REAPER STRUCTURE - macro shape of the reference jungle DJ set.

STRUCTURAL ANALYSIS ONLY. Nothing here reads, writes, sums or exports audio material from the
reference. It consumes the cached frame features (band energies, flux, centroid, width, crest) and
emits numbers: a self-similarity matrix, a novelty curve, section boundaries, a local tempo/beat
grid, DJ-seam evidence, phrase arithmetic and repetition indices.

Everything is computed in SECONDS. Bars are derived from a locally-tracked beat grid (the cached
single global tempo is not trusted) and are always reported as approximate.

    python scripts/reaper_structure.py all          # full pipeline, prints every table
    python scripts/reaper_structure.py grid         # just the tempo / beat tracking report
    python scripts/reaper_structure.py boundaries   # SSM + novelty + boundary picking
    python scripts/reaper_structure.py seams        # DJ-mix seam evidence
    python scripts/reaper_structure.py repeat       # repetition / recall indices
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

CACHE = r"C:\Users\eric\Downloads\reaper_cache"
WORK = os.environ.get("REAPER_WORK") or os.path.join(os.path.dirname(__file__), "..", "..",
                                                     "..", "AppData", "Local", "Temp")
SCRATCH = r"C:\Users\eric\AppData\Local\Temp\claude\C--Users-eric-github-sens8tion-thelmic\b784ee21-3fab-4996-98dd-32e4a4e5ac45\scratchpad"

BANDS = ["sub", "bass", "lowmid", "mid", "high", "air"]
R = 2.0                      # analysis rate for the SSM, frames per second
BPM_LO, BPM_HI = 140.0, 200.0


# ----------------------------------------------------------------------
# loading / resampling
# ----------------------------------------------------------------------
def load_frames() -> dict:
    f = np.load(os.path.join(CACHE, "frames.npz"))
    return {k: f[k].astype(np.float64) for k in f.files}


def block_mean(x: np.ndarray, edges: np.ndarray) -> np.ndarray:
    """Mean of x over [edges[i], edges[i+1]) - reduceat, safe for empty blocks."""
    c = np.concatenate([[0.0], np.cumsum(x)])
    lo, hi = edges[:-1], edges[1:]
    return (c[hi] - c[lo]) / np.maximum(hi - lo, 1)


def coarse_features(f: dict, rate: float = R) -> tuple[np.ndarray, np.ndarray, dict]:
    """Aggregate the ~93.75 fps frames to `rate` fps. Returns (t, X, raw) where X is the
    normalised feature matrix used for the SSM and raw holds the un-normalised columns."""
    fps = 1.0 / np.median(np.diff(f["t"]))
    n = len(f["t"])
    step = fps / rate
    edges = np.unique(np.round(np.arange(0, n + 1, step)).astype(int))
    edges = np.clip(edges, 0, n)
    t = f["t"][np.minimum(edges[:-1], n - 1)]

    raw = {}
    for b in BANDS:
        raw[b] = block_mean(f[b], edges)
    raw["rms"] = np.sqrt(block_mean(f["rms"] ** 2, edges))
    raw["crest"] = block_mean(f["crest"], edges)
    raw["centroid"] = block_mean(f["centroid"], edges)
    raw["width"] = block_mean(f["width"], edges)
    raw["flux"] = block_mean(f["flux"], edges)
    raw["t"] = t

    # timbre vector: log band energies with the overall level divided out (so a fader move does
    # not read as a new section), plus log centroid, width and crest.
    E = np.stack([np.log10(raw[b] + 1e-6) for b in BANDS], axis=1)
    E = E - E.mean(axis=1, keepdims=True)
    extra = np.stack([np.log10(raw["centroid"] + 1.0), raw["width"] * 10.0,
                      np.log10(raw["crest"] + 1e-6)], axis=1)
    X = np.concatenate([E, extra], axis=1)
    X = (X - X.mean(axis=0)) / (X.std(axis=0) + 1e-9)
    # weight: the six band ratios carry the identity of a track; the three extras are support
    X *= np.array([1.0] * 6 + [0.6, 0.6, 0.4])
    return t, X, raw


def smooth(x: np.ndarray, w: int) -> np.ndarray:
    if w <= 1:
        return x.copy()
    k = np.hanning(w + 2)[1:-1]
    k /= k.sum()
    return np.convolve(x, k, mode="same")


# ----------------------------------------------------------------------
# self-similarity + Foote novelty
# ----------------------------------------------------------------------
def ssm(X: np.ndarray, smooth_frames: int = 8) -> np.ndarray:
    """Cosine self-similarity after smoothing the feature stream (an 8-frame = 4 s box makes the
    matrix about texture, not about individual drum hits)."""
    Y = X.copy()
    if smooth_frames > 1:
        for j in range(Y.shape[1]):
            Y[:, j] = smooth(Y[:, j], smooth_frames)
    Y = Y / (np.linalg.norm(Y, axis=1, keepdims=True) + 1e-9)
    S = Y @ Y.T
    return S


def checkerboard(half: int) -> np.ndarray:
    """Gaussian-tapered checkerboard kernel, 2*half square."""
    g = np.arange(-half, half) + 0.5
    xx, yy = np.meshgrid(g, g)
    taper = np.exp(-0.5 * (xx ** 2 + yy ** 2) / (half / 2.0) ** 2)
    sign = np.sign(xx) * np.sign(yy)
    k = sign * taper
    return k / np.abs(k).sum()


def novelty(S: np.ndarray, half: int) -> np.ndarray:
    k = checkerboard(half)
    n = S.shape[0]
    nov = np.zeros(n)
    P = np.pad(S, half, mode="edge")
    for i in range(n):
        nov[i] = float((P[i:i + 2 * half, i:i + 2 * half] * k).sum())
    nov = np.maximum(nov, 0.0)
    return nov


def pick_peaks(nov: np.ndarray, t: np.ndarray, min_gap_s: float, k_mad: float) -> np.ndarray:
    """Local maxima above median + k_mad * MAD, thinned to one per min_gap_s."""
    med = np.median(nov)
    mad = np.median(np.abs(nov - med)) + 1e-12
    thr = med + k_mad * mad
    cand = [i for i in range(1, len(nov) - 1)
            if nov[i] >= nov[i - 1] and nov[i] >= nov[i + 1] and nov[i] > thr]
    cand.sort(key=lambda i: -nov[i])
    keep: list[int] = []
    for i in cand:
        if all(abs(t[i] - t[j]) >= min_gap_s for j in keep):
            keep.append(i)
    return np.array(sorted(keep), int), thr


# ----------------------------------------------------------------------
# local tempo + beat grid (the cached global grid is not trusted)
# ----------------------------------------------------------------------
def onset_env(f: dict) -> tuple[np.ndarray, float]:
    fps = 1.0 / np.median(np.diff(f["t"]))
    e = f["flux"].copy()
    # adaptive whitening: divide by a ~1 s moving average so quiet passages still contribute
    m = smooth(e, int(round(fps)))
    e = e / (m + np.percentile(m, 20) + 1e-9)
    e = np.log1p(e)
    e = e - smooth(e, int(round(fps * 1.5)))
    return np.maximum(e, 0.0), fps


def tempo_curve(env: np.ndarray, fps: float, win_s: float = 12.0, hop_s: float = 1.0):
    """Autocorrelation tempogram -> (times, bpm, confidence, ambiguity).

    ambiguity = second-best ACF peak / best, measured over distinct tempo candidates; it rises
    where two records with different tempos are both audible."""
    win = int(round(win_s * fps))
    hop = int(round(hop_s * fps))
    lo = int(np.floor(60.0 * fps / BPM_HI))
    hi = int(np.ceil(60.0 * fps / BPM_LO))
    ts, bpms, confs, ambig = [], [], [], []
    for a in range(0, len(env) - win, hop):
        seg = env[a:a + win]
        seg = seg - seg.mean()
        if seg.std() < 1e-9:
            ts.append((a + win / 2) / fps); bpms.append(np.nan); confs.append(0.0); ambig.append(1.0)
            continue
        ac = np.correlate(seg, seg, mode="full")[win - 1:]
        ac = ac / (ac[0] + 1e-12)
        # normalise for the shrinking overlap
        ac = ac * (win / np.maximum(win - np.arange(len(ac)), 1))
        band = ac[lo:hi + 1]
        # local maxima inside the band
        pk = [i for i in range(1, len(band) - 1) if band[i] > band[i - 1] and band[i] >= band[i + 1]]
        if not pk:
            pk = [int(np.argmax(band))]
        pk.sort(key=lambda i: -band[i])
        best = pk[0]
        # parabolic refinement
        j = best
        if 1 <= j < len(band) - 1:
            y0, y1, y2 = band[j - 1], band[j], band[j + 1]
            d = y0 - 2 * y1 + y2
            j = j + (0.5 * (y0 - y2) / d if d != 0 else 0.0)
        lag = lo + j
        bpm = 60.0 * fps / lag
        second = 0.0
        for i in pk[1:]:
            if abs(i - best) > 2:
                second = band[i]
                break
        ts.append((a + win / 2) / fps)
        bpms.append(bpm)
        confs.append(float(band[best]))
        ambig.append(float(second / (band[best] + 1e-9)))
    return np.array(ts), np.array(bpms), np.array(confs), np.array(ambig)


def track_beats(env: np.ndarray, fps: float, period: np.ndarray, alpha: float = 300.0):
    """Ellis-style dynamic-programming beat tracker with a time-varying period (frames)."""
    n = len(env)
    e = env / (env.max() + 1e-9)
    score = np.full(n, -1e18)
    back = np.zeros(n, int)
    score[0] = e[0]
    for t in range(1, n):
        p = period[t]
        lo = max(0, int(t - 2.0 * p))
        hi = max(lo + 1, int(t - 0.5 * p))
        if hi <= lo:
            score[t] = e[t]
            back[t] = max(t - 1, 0)
            continue
        idx = np.arange(lo, hi)
        pen = -alpha * (np.log((t - idx) / p) ** 2)
        cand = score[idx] + pen
        j = int(np.argmax(cand))
        score[t] = cand[j] + e[t]
        back[t] = idx[j]
    # backtrack from the best tail
    tail = int(np.argmax(score[-int(2 * period[-1]):]) + n - int(2 * period[-1]))
    beats = [tail]
    while back[beats[-1]] < beats[-1]:
        beats.append(back[beats[-1]])
    beats = np.array(sorted(beats)) / fps
    return beats


def downbeat_phase(beats: np.ndarray, t_low: np.ndarray, low: np.ndarray,
                   a: float, z: float) -> int:
    """Which of the four beat phases inside [a,z] carries the most low end."""
    sel = np.where((beats >= a) & (beats < z))[0]
    if len(sel) < 8:
        return 0
    w = np.interp(beats[sel], t_low, low)
    return int(np.argmax([w[k::4].mean() for k in range(4)]))


# ----------------------------------------------------------------------
# repetition: time-lag matrix
# ----------------------------------------------------------------------
def lag_repetition(S: np.ndarray, t: np.ndarray, min_lag_s: float, max_lag_s: float,
                   path_s: float = 8.0):
    """For every frame, the best similarity of a `path_s`-long diagonal path arriving at that
    frame from `lag` seconds earlier, over lags in [min_lag, max_lag]. Returns (best, arg_lag_s)."""
    n = S.shape[0]
    dt = float(np.median(np.diff(t)))
    lo = max(1, int(round(min_lag_s / dt)))
    hi = min(n - 1, int(round(max_lag_s / dt)))
    w = max(1, int(round(path_s / dt)))
    best = np.full(n, -1.0)
    arg = np.zeros(n)
    kern = np.ones(w) / w
    for L in range(lo, hi + 1):
        d = np.full(n, -1.0)
        d[L:] = S[np.arange(L, n), np.arange(0, n - L)]
        sm = np.convolve(d, kern, mode="same")
        upd = sm > best
        best[upd] = sm[upd]
        arg[upd] = L * dt
    return best, arg


# ----------------------------------------------------------------------
# labelling
# ----------------------------------------------------------------------
def db(x):
    return 20.0 * np.log10(np.maximum(x, 1e-9))


def section_stats(raw: dict, a: float, z: float) -> dict:
    t = raw["t"]
    m = (t >= a) & (t < z)
    if m.sum() == 0:
        m = np.zeros_like(t, bool); m[np.argmin(np.abs(t - a))] = True
    tot = sum(raw[b][m].mean() for b in BANDS)
    out = {"rms_db": float(db(np.sqrt((raw["rms"][m] ** 2).mean()))),
           "crest": float(raw["crest"][m].mean()),
           "centroid": float(raw["centroid"][m].mean()),
           "width": float(raw["width"][m].mean()),
           "flux": float(raw["flux"][m].mean())}
    for b in BANDS:
        out["f_" + b] = float(raw[b][m].mean() / (tot + 1e-9))
        out["e_" + b] = float(db(raw[b][m].mean()))
    return out


# ----------------------------------------------------------------------
def build(rate: float = R):
    f = load_frames()
    t, X, raw = coarse_features(f, rate)
    S = ssm(X, smooth_frames=int(round(4.0 * rate)))
    return f, t, X, raw, S


def fmt_time(s: float) -> str:
    return f"{int(s) // 60}:{s - 60 * (int(s) // 60):05.2f}"


# ----------------------------------------------------------------------
def cmd_grid():
    f = load_frames()
    env, fps = onset_env(f)
    tt, bpm, conf, amb = tempo_curve(env, fps)
    np.savez(os.path.join(SCRATCH, "tempo.npz"), t=tt, bpm=bpm, conf=conf, amb=amb)
    print(f"onset env: {len(env)} frames at {fps:.3f} fps")
    print(f"tempo windows: {len(tt)}  median bpm {np.nanmedian(bpm):.2f}  "
          f"p10 {np.nanpercentile(bpm, 10):.2f}  p90 {np.nanpercentile(bpm, 90):.2f}")
    print(f"conf median {np.median(conf):.3f}   ambiguity median {np.median(amb):.3f}")
    # coarse print
    for i in range(0, len(tt), 30):
        print(f"  {fmt_time(tt[i]):>8}  {bpm[i]:7.2f} bpm  conf {conf[i]:.3f}  amb {amb[i]:.3f}")
    return tt, bpm, conf, amb


def cmd_beats():
    """Refine the global tempo, then DP-track beats and look for drift / phase slips."""
    f = load_frames()
    env, fps = onset_env(f)
    d = np.load(os.path.join(SCRATCH, "tempo.npz"))

    # a long-window ACF for a precise global period: average the ACF of 60 s windows
    win = int(round(60 * fps))
    lo = int(np.floor(60.0 * fps / BPM_HI))
    hi = int(np.ceil(60.0 * fps / BPM_LO))
    acc = np.zeros(hi + 3)
    for a in range(0, len(env) - win, win // 2):
        seg = env[a:a + win] - env[a:a + win].mean()
        ac = np.correlate(seg, seg, mode="full")[win - 1:win - 1 + len(acc)]
        acc += ac / (ac[0] + 1e-12)
    j = lo + int(np.argmax(acc[lo:hi + 1]))
    y0, y1, y2 = acc[j - 1], acc[j], acc[j + 1]
    dd = y0 - 2 * y1 + y2
    lag = j + (0.5 * (y0 - y2) / dd if dd else 0.0)
    print(f"global ACF period {lag:.4f} frames = {lag / fps * 1000:.2f} ms -> "
          f"{60 * fps / lag:.3f} BPM;  bar {4 * lag / fps:.4f} s")
    for mult, name in ((0.5, "half"), (2.0, "double"), (4.0, "4-beat/bar"), (8.0, "2-bar")):
        L = lag * mult
        if L < len(acc) - 1:
            print(f"   ACF at {name:>10} lag {L:7.2f}: {acc[int(round(L))] / acc[int(round(lag))]:.3f}")

    per = np.interp(np.arange(len(env)) / fps, d["t"], d["bpm"])
    per = 60.0 * fps / np.clip(per, BPM_LO, BPM_HI)
    beats = track_beats(env, fps, per)
    np.savez(os.path.join(SCRATCH, "beats.npz"), beats=beats, global_bpm=60 * fps / lag)
    ibi = np.diff(beats)
    print(f"beats tracked: {len(beats)}  median IBI {np.median(ibi) * 1000:.2f} ms "
          f"({60 / np.median(ibi):.3f} BPM)  IQR {np.percentile(ibi, 75) * 1000 - np.percentile(ibi, 25) * 1000:.2f} ms")
    print(f"beats expected at a constant {60 * fps / lag:.3f} BPM over {beats[-1] - beats[0]:.1f} s: "
          f"{(beats[-1] - beats[0]) / (lag / fps):.2f}")
    # drift: cumulative phase against a constant grid anchored at the first beat
    ideal = beats[0] + np.arange(len(beats)) * lag / fps
    drift = beats - ideal
    for q in (0, 0.25, 0.5, 0.75, 1.0):
        i = int(q * (len(beats) - 1))
        print(f"   at {fmt_time(beats[i]):>8}  drift vs constant grid {drift[i] * 1000:+8.1f} ms "
              f"({drift[i] / (lag / fps):+.2f} beats)")
    return beats


def comb_score(env: np.ndarray, fps: float, period: float, phase: np.ndarray,
               a: float = 0.0, z: float | None = None) -> np.ndarray:
    """Sum of the onset envelope sampled at a beat comb whose beats sit at ABSOLUTE frame
    positions phase + m*period (phase measured from t=0), restricted to [a, z] seconds."""
    n = len(env)
    z = n / fps if z is None else z
    i0, i1 = max(0.0, a * fps), min(float(n - 2), z * fps)
    m0 = int(np.ceil(i0 / period))
    K = int(np.floor((i1 - i0) / period))
    if K < 2:
        return np.zeros_like(phase)
    m = m0 + np.arange(K)
    pos = phase[:, None] + m[None, :] * period
    pos = np.clip(pos, 0, n - 2)
    lo = np.floor(pos).astype(int)
    frac = pos - lo
    return (env[lo] * (1 - frac) + env[lo + 1] * frac).sum(axis=1) / K


def cmd_fitgrid():
    """Fit ONE global period + phase to the whole set at sub-frame precision, then check whether a
    single grid really holds by measuring the local best phase in 30 s chunks."""
    f = load_frames()
    env, fps = onset_env(f)
    n = len(env)
    base = 33.9207

    best = None
    for P in np.arange(base - 0.06, base + 0.06, 0.0005):
        ph = np.arange(0, P, 0.1)
        sc = comb_score(env, fps, P, ph)
        j = int(np.argmax(sc))
        if best is None or sc[j] > best[2]:
            best = (P, ph[j], sc[j])
    P, ph0, _ = best
    bpm = 60.0 * fps / P
    print(f"best global grid: period {P:.4f} frames ({P / fps * 1000:.3f} ms) = {bpm:.4f} BPM, "
          f"phase {ph0 / fps * 1000:.1f} ms, bar {4 * P / fps:.5f} s")

    # local phase drift check
    print("\nlocal beat phase against that grid (ms, wrapped to +-half a beat):")
    rows = []
    for a in range(0, int(n / fps) - 30, 30):
        ph = np.arange(0, P, 0.05)
        sc = comb_score(env, fps, P, ph, a=a, z=a + 30)
        j = int(np.argmax(sc))
        # express relative to the global phase, wrapped
        rel = (ph[j] - (ph0 + a * fps) % P) % P
        if rel > P / 2:
            rel -= P
        rows.append((a, rel / fps * 1000, sc[j] / max(sc.mean(), 1e-9)))
    for a, rel, sharp in rows:
        print(f"  {fmt_time(a):>8}  {rel:+7.1f} ms   comb sharpness {sharp:.3f}")
    off = np.array([r[1] for r in rows])
    print(f"phase spread: sd {off.std():.1f} ms, max |offset| {np.abs(off).max():.1f} ms "
          f"(one beat = {P / fps * 1000:.1f} ms, one 16th = {P / fps * 250:.1f} ms)")
    np.savez(os.path.join(SCRATCH, "fitgrid.npz"), period_frames=P, phase_frames=ph0, fps=fps,
             bpm=bpm, bar_s=4 * P / fps, local_offset_ms=off,
             local_t=np.array([r[0] for r in rows]))
    return P, ph0, fps


def phase_track(env, fps, P, win_s=12.0, hop_s=3.0):
    """Best beat phase in short windows, unwrapped into a continuous ms curve."""
    n = len(env)
    ts, phs, sharp = [], [], []
    ph = np.arange(0, P, 0.02)
    for a in np.arange(0, n / fps - win_s, hop_s):
        sc = comb_score(env, fps, P, ph, a=a, z=a + win_s)
        j = int(np.argmax(sc))
        ts.append(a + win_s / 2)
        phs.append(ph[j])
        sharp.append(sc[j] / max(sc.mean(), 1e-9))
    ts = np.array(ts); phs = np.array(phs); sharp = np.array(sharp)
    # unwrap in units of P
    u = phs.copy()
    for i in range(1, len(u)):
        while u[i] - u[i - 1] > P / 2:
            u[i] -= P
        while u[i] - u[i - 1] < -P / 2:
            u[i] += P
    return ts, u / fps * 1000.0, sharp, phs


def cmd_phase():
    f = load_frames()
    env, fps = onset_env(f)
    P0 = 33.8867
    ts, u, sharp, raw_ph = phase_track(env, fps, P0)
    # robust slope (Theil-Sen on a subsample) -> corrected period
    idx = np.arange(len(ts))
    sl = []
    for i in range(0, len(ts), 7):
        for j in range(i + 20, len(ts), 23):
            sl.append((u[j] - u[i]) / (ts[j] - ts[i]))
    slope = float(np.median(sl))                      # ms of phase per second
    beat_ms = P0 / fps * 1000.0
    P_corr = (beat_ms + slope * beat_ms / 1000.0)
    print(f"phase slope {slope:+.4f} ms/s -> corrected beat {P_corr:.4f} ms = "
          f"{60000 / P_corr:.4f} BPM, bar {4 * P_corr / 1000:.5f} s")
    resid = u - slope * (ts - ts[0])
    resid -= np.median(resid)
    np.savez(os.path.join(SCRATCH, "phase.npz"), t=ts, unwrapped=u, resid=resid, sharp=sharp,
             slope=slope, bpm=60000 / P_corr, bar_s=4 * P_corr / 1000)
    # step detection on the residual
    print("\nphase residual (ms) after removing the constant-tempo slope; "
          f"one 16th = {P_corr / 4:.1f} ms")
    steps = []
    w = 8                                             # 24 s either side
    for i in range(w, len(resid) - w):
        a, b = np.median(resid[i - w:i]), np.median(resid[i:i + w])
        steps.append(abs(b - a))
    steps = np.array([0.0] * w + steps + [0.0] * w)
    ordr = np.argsort(-steps)
    keep = []
    for i in ordr:
        if steps[i] < 12:
            break
        if all(abs(ts[i] - ts[j]) > 20 for j in keep):
            keep.append(i)
    for i in sorted(keep):
        print(f"  step at {fmt_time(ts[i]):>8}  {steps[i]:6.1f} ms  "
              f"({steps[i] / P_corr * 4:.2f} of a 16th)  sharpness {sharp[i]:.2f}")
    lows = np.argsort(sharp)[:14]
    print("\nlowest comb sharpness (grid least legible - typically a blend or a breakdown):")
    for i in sorted(lows):
        print(f"  {fmt_time(ts[i]):>8}  sharpness {sharp[i]:.2f}")
    return ts, resid, sharp


def cmd_acf():
    """Long-lag autocorrelation of the onset envelope: the period measured over hundreds of beats,
    which is the only way to get a grid that survives 21 minutes."""
    f = load_frames()
    env, fps = onset_env(f)
    n = len(env)
    x = env - env.mean()
    N = 1 << int(np.ceil(np.log2(2 * n)))
    F = np.fft.rfft(x, N)
    ac = np.fft.irfft(F * np.conj(F), N)[:n]
    ac = ac / (ac[0] + 1e-12)
    norm = n / np.maximum(n - np.arange(n), 1)
    ac = ac * norm
    print("period from the ACF peak nearest k beats (k beats ~ k*33.89 frames):")
    ests = []
    for k in (1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024, 2048):
        centre = k * 33.8867
        if centre + 20 >= n:
            break
        w = max(3, int(0.012 * centre))
        lo, hi = int(centre - w), int(centre + w)
        seg = ac[lo:hi + 1]
        j = lo + int(np.argmax(seg))
        y0, y1, y2 = ac[j - 1], ac[j], ac[j + 1]
        d = y0 - 2 * y1 + y2
        jf = j + (0.5 * (y0 - y2) / d if d else 0.0)
        P = jf / k
        ests.append((k, P, ac[j]))
        print(f"  k={k:5d}  lag {jf:10.3f} fr  -> beat {P / fps * 1000:8.4f} ms "
              f"= {60 * fps / P:9.5f} BPM   acf {ac[j]:.4f}")
    return ests


def cmd_phasecurve():
    f = load_frames()
    env, fps = onset_env(f)
    P0 = float(sys.argv[2]) if len(sys.argv) > 2 else 33.8867
    ts, u, sharp, raw_ph = phase_track(env, fps, P0, win_s=12.0, hop_s=6.0)
    beat_ms = P0 / fps * 1000
    print(f"grid period {beat_ms:.4f} ms; 16th = {beat_ms / 4:.1f} ms; "
          f"unwrapped phase (ms) every 6 s")
    for i in range(len(ts)):
        bar = int(round(u[i] / (beat_ms / 8)))
        print(f"  {fmt_time(ts[i]):>8} {u[i]:+9.1f}  sharp {sharp[i]:.2f}  "
              f"{'|' * max(0, min(60, bar + 30))}")
    return ts, u, sharp


# the grid this analysis uses, measured in cmd_acf / cmd_phasecurve (not the cached one)
BEAT_MS = 361.561
BAR_S = 4 * BEAT_MS / 1000.0
DOWNBEAT_S = 0.0            # filled in by cmd_downbeat


def cmd_boundaries(verbose=True):
    f, t, X, raw, S = build()
    np.save(os.path.join(SCRATCH, "ssm.npy"), S.astype(np.float32))
    np.savez(os.path.join(SCRATCH, "coarse.npz"), X=X, **{k: v for k, v in raw.items()})
    dt = float(np.median(np.diff(t)))
    out = {}
    for half_s in (24.0, 12.0, 6.0):
        h = int(round(half_s / dt))
        nv = novelty(S, h)
        nv = smooth(nv, 3)
        nv = nv / (nv.max() + 1e-12)
        out[half_s] = nv
    np.savez(os.path.join(SCRATCH, "novelty.npz"), t=t, **{f"n{int(k)}": v for k, v in out.items()})
    if verbose:
        for half_s, nv in out.items():
            pk, thr = pick_peaks(nv, t, min_gap_s=16.0, k_mad=2.0)
            print(f"\nkernel +-{half_s:.0f} s : {len(pk)} boundaries (thr {thr:.3f})")
            print("  " + "  ".join(f"{fmt_time(t[i])}({nv[i]:.2f})" for i in pk))
    return t, S, out, raw


def cmd_downbeat():
    """Lock the bar phase: which beat of four carries the low end, checked in 60 s chunks."""
    f = load_frames()
    env, fps = onset_env(f)
    low = f["sub"] + f["bass"]
    P = BEAT_MS / 1000.0 * fps
    ph = np.arange(0, P, 0.05)
    sc = comb_score(env, fps, P, ph)
    base = ph[int(np.argmax(sc))]
    lowsm = smooth(low, 9)
    votes = []
    for a in range(0, 1200, 60):
        beats = np.arange(base, len(env) - 2, P)
        beats = beats[(beats / fps >= a) & (beats / fps < a + 60)]
        w = np.interp(beats, np.arange(len(low)), lowsm)
        m = [w[k::4].mean() for k in range(4)]
        votes.append((a, int(np.argmax(m)), max(m) / (np.mean(m) + 1e-9)))
    from collections import Counter
    c = Counter(v[1] for v in votes)
    print("downbeat vote per 60 s chunk (beat index of four, and how much low end it wins by):")
    for a, k, r in votes:
        print(f"  {fmt_time(a):>8}  beat {k}  ratio {r:.3f}")
    print("counts:", dict(c))
    k = c.most_common(1)[0][0]
    db0 = (base + k * P) / fps
    print(f"beat-1 anchor {db0:.4f} s; bar {BAR_S:.5f} s; "
          f"{(1259.72 - db0) / BAR_S:.2f} bars in the file")
    np.savez(os.path.join(SCRATCH, "downbeat.npz"), db0=db0, bar_s=BAR_S, beat_ms=BEAT_MS)
    return db0


def cmd_map(tile_s: float = 15.0):
    """ASCII self-similarity map: each cell is the mean cosine similarity of two `tile_s` tiles.
    Blocks on the diagonal are tracks; off-diagonal blocks are recalls."""
    t = np.load(os.path.join(SCRATCH, "coarse.npz"))["t"]
    S = np.load(os.path.join(SCRATCH, "ssm.npy")).astype(np.float64)
    dt = float(np.median(np.diff(t)))
    k = int(round(tile_s / dt))
    n = S.shape[0] // k
    B = S[:n * k, :n * k].reshape(n, k, n, k).mean(axis=(1, 3))
    lo, hi = np.percentile(B, 20), np.percentile(B, 97)
    chars = " .:-=+*#%@"
    print(f"tile = {tile_s:.0f} s ({tile_s / BAR_S:.1f} bars), {n} tiles, "
          f"scale {lo:.2f}..{hi:.2f}")
    hdr = "".join(str((i // 4) % 10) if i % 4 == 0 else " " for i in range(n))
    print("        " + hdr)
    for i in range(n):
        row = "".join(chars[int(np.clip((B[i, j] - lo) / (hi - lo), 0, 1) * (len(chars) - 1))]
                      for j in range(n))
        print(f"{fmt_time(i * tile_s):>7} {row}")
    np.save(os.path.join(SCRATCH, "blockssm.npy"), B)
    return B


# ----------------------------------------------------------------------
# sections
# ----------------------------------------------------------------------
def bars_of(s: float, db0: float = 0.0421) -> float:
    return (s - db0) / BAR_S


def onset_peaks(flux: np.ndarray, pre: int = 3, post: int = 3, delta_mult: float = 1.3,
                avg_frames: int = 43) -> np.ndarray:
    """Frame indices where flux is a local max over +-pre/post AND above a moving average * mult.
    Vectorised restatement of the detector used to build the cache, so the two agree."""
    n = len(flux)
    avg = np.convolve(flux, np.ones(avg_frames) / avg_frames, mode="same")
    ok = (flux > avg * delta_mult) & (flux > 0)
    win = np.lib.stride_tricks.sliding_window_view(flux, pre + post + 1)
    ismax = flux[pre:n - post] >= win.max(axis=1)
    idx = np.arange(pre, n - post)
    return idx[ismax & ok[pre:n - post]].astype(np.float64)


def onsets_per_bar(f: dict, edges_s: np.ndarray) -> dict:
    """Onset counts inside each bar, overall and for a low / high split."""
    fps = 1.0 / np.median(np.diff(f["t"]))
    res = {}
    for name, fl in (("all", f["flux"]),
                     ("low", f["flux_sub"] + f["flux_bass"]),
                     ("high", f["flux_high"] + f["flux_air"])):
        pk = onset_peaks(fl) / fps
        res[name] = np.histogram(pk, bins=edges_s)[0].astype(float)
        res[name + "_times"] = pk
    return res


def pick_sections(t, novs, db0):
    """Combine the kernels, force in every long-kernel peak, snap to the bar grid."""
    n12, n6, n24 = novs[12.0], novs[6.0], novs[24.0]
    comb = 0.55 * n12 + 0.45 * n6
    comb = comb / comb.max()
    p_main, thr = pick_peaks(comb, t, min_gap_s=10.0, k_mad=1.6)
    p_maj, _ = pick_peaks(n24, t, min_gap_s=16.0, k_mad=2.0)
    idx = sorted(set(p_main.tolist()) | set(p_maj.tolist()))
    times = [t[i] for i in idx]
    # snap to the nearest bar line, then drop anything closer than 8 bars to its neighbour
    snapped = [db0 + round(bars_of(x, db0)) * BAR_S for x in times]
    keep = [0.0]
    for x in snapped:
        if x - keep[-1] >= 8 * BAR_S - 0.1:
            keep.append(x)
    if 1259.727 - keep[-1] < 8 * BAR_S:
        keep.pop()
    keep.append(1259.727)
    majs = set(round(db0 + round(bars_of(t[i], db0)) * BAR_S, 3) for i in p_maj)
    return np.array(keep), majs, comb, thr


def cluster_tiles(S, t, tile_s=6.0, thresh=0.80):
    """Greedy medoid clustering of short tiles by timbre - a crude 'which record is this'."""
    dt = float(np.median(np.diff(t)))
    k = max(1, int(round(tile_s / dt)))
    n = S.shape[0] // k
    B = S[:n * k, :n * k].reshape(n, k, n, k).mean(axis=(1, 3))
    lab = np.full(n, -1)
    cid = 0
    order = []
    while (lab < 0).any():
        free = np.where(lab < 0)[0]
        cnt = [(int(((B[i, free] > thresh)).sum()), i) for i in free]
        cnt.sort(reverse=True)
        if cnt[0][0] <= 1:
            for i in free:
                lab[i] = cid; cid += 1
            break
        c, medoid = cnt[0]
        members = free[B[medoid, free] > thresh]
        lab[members] = cid
        order.append((cid, medoid, len(members)))
        cid += 1
    return lab, k, B, order


def cmd_sections():
    f = load_frames()
    d = np.load(os.path.join(SCRATCH, "coarse.npz"))
    t = d["t"]
    raw = {kk: d[kk] for kk in d.files if kk != "X"}
    S = np.load(os.path.join(SCRATCH, "ssm.npy")).astype(np.float64)
    nv = np.load(os.path.join(SCRATCH, "novelty.npz"))
    novs = {24.0: nv["n24"], 12.0: nv["n12"], 6.0: nv["n6"]}
    db0 = float(np.load(os.path.join(SCRATCH, "downbeat.npz"))["db0"])

    bnds, majs, comb, thr = pick_sections(t, novs, db0)
    print(f"{len(bnds) - 1} sections (threshold {thr:.3f}); bar {BAR_S:.5f} s, "
          f"anchor {db0:.3f} s")

    # bar-level onset densities on OUR grid
    nbar = int((1259.727 - db0) / BAR_S)
    edges = db0 + np.arange(nbar + 1) * BAR_S
    ons = onsets_per_bar(f, edges)

    # repetition
    loop_rep, loop_lag = lag_repetition(S, t, 1.2, 24.0, path_s=8.0)
    recall, recall_lag = lag_repetition(S, t, 30.0, 900.0, path_s=12.0)

    lab, k, B, order = cluster_tiles(S, t, tile_s=6.0, thresh=0.80)
    tile_s = 6.0

    rows = []
    for i in range(len(bnds) - 1):
        a, z = float(bnds[i]), float(bnds[i + 1])
        st = section_stats(raw, a, z)
        m = (t >= a) & (t < z)
        ba, bz = int(round(bars_of(a, db0))), int(round(bars_of(z, db0)))
        bmask = slice(max(0, ba), min(nbar, bz))
        cl = lab[max(0, int(a / tile_s)):max(1, int(z / tile_s))]
        cl_main = int(np.bincount(cl).argmax()) if len(cl) else -1
        rows.append(dict(
            i=i, a=a, z=z, dur=z - a, bars=bz - ba, bar_a=ba, bar_z=bz,
            major=round(a, 3) in majs,
            rms=st["rms_db"], crest=st["crest"], centroid=st["centroid"],
            width=st["width"],
            f_sub=st["f_sub"], f_bass=st["f_bass"], f_lowmid=st["f_lowmid"],
            f_mid=st["f_mid"], f_high=st["f_high"], f_air=st["f_air"],
            low=st["f_sub"] + st["f_bass"], hi=st["f_high"] + st["f_air"],
            ons=float(ons["all"][bmask].mean()) if bz > ba else 0.0,
            ons_lo=float(ons["low"][bmask].mean()) if bz > ba else 0.0,
            ons_hi=float(ons["high"][bmask].mean()) if bz > ba else 0.0,
            loop=float(loop_rep[m].mean()), loop_lag=float(np.median(loop_lag[m])),
            recall=float(recall[m].mean()), recall_lag=float(np.median(recall_lag[m])),
            recall_hi=float((recall[m] > 0.72).mean()),
            cluster=cl_main,
            rms_slope=float(np.polyfit(t[m], db(raw["rms"][m]), 1)[0]) if m.sum() > 3 else 0.0,
        ))
    np.save(os.path.join(SCRATCH, "sections.npy"), np.array([(r["a"], r["z"]) for r in rows]))
    with open(os.path.join(SCRATCH, "sections.json"), "w") as fh:
        json.dump(rows, fh, indent=1)

    hdr = (f"{'#':>3} {'start':>8} {'end':>8} {'s':>6} {'bars':>5} {'bar#':>5} "
           f"{'rms':>6} {'slope':>6} {'low%':>5} {'hi%':>5} {'cent':>6} {'wid':>5} "
           f"{'crest':>5} {'on/bar':>6} {'lo/bar':>6} {'loop':>5} {'lag':>5} "
           f"{'rcl':>5} {'rlag':>7} {'cl':>3} M")
    print(hdr)
    for r in rows:
        print(f"{r['i']:>3} {fmt_time(r['a']):>8} {fmt_time(r['z']):>8} {r['dur']:6.1f} "
              f"{r['bars']:5d} {r['bar_a']:5d} {r['rms']:6.1f} {r['rms_slope']:+6.2f} "
              f"{100 * r['low']:5.1f} {100 * r['hi']:5.1f} {r['centroid']:6.0f} "
              f"{r['width']:5.3f} {r['crest']:5.2f} {r['ons']:6.2f} {r['ons_lo']:6.2f} "
              f"{r['loop']:5.2f} {r['loop_lag']:5.1f} {r['recall']:5.2f} "
              f"{r['recall_lag']:7.1f} {r['cluster']:3d} {'*' if r['major'] else ''}")
    print("\ncluster sizes (tile = 6 s):", {c: int((lab == c).sum()) for c in sorted(set(lab.tolist())) if (lab == c).sum() > 2})
    return rows, lab, tile_s


def cmd_phrase():
    """Do the novelty peaks land on a phrase grid? Histogram the RAW (unsnapped) peak times
    modulo 4, 8, 16 and 32 bars, and test the best phase against a uniform null."""
    d = np.load(os.path.join(SCRATCH, "coarse.npz"))
    t = d["t"]
    nv = np.load(os.path.join(SCRATCH, "novelty.npz"))
    db0 = float(np.load(os.path.join(SCRATCH, "downbeat.npz"))["db0"])
    n12, n6, n24 = nv["n12"], nv["n6"], nv["n24"]
    comb = 0.55 * n12 + 0.45 * n6
    comb /= comb.max()
    p, thr = pick_peaks(comb, t, min_gap_s=10.0, k_mad=1.6)
    p24, _ = pick_peaks(n24, t, min_gap_s=16.0, k_mad=2.0)
    for name, idx in (("all boundaries", sorted(set(p.tolist()) | set(p24.tolist()))),
                      ("major (+-24 s kernel)", sorted(p24.tolist()))):
        times = np.array([t[i] for i in idx])
        bars = bars_of(times, db0)
        print(f"\n{name}: n={len(bars)}")
        for m in (4, 8, 16, 32):
            ph = bars % m
            # circular concentration
            ang = 2 * np.pi * ph / m
            Rv = np.hypot(np.cos(ang).mean(), np.sin(ang).mean())
            best = (np.arctan2(np.sin(ang).mean(), np.cos(ang).mean()) % (2 * np.pi)) * m / (2 * np.pi)
            dev = np.minimum((ph - best) % m, (best - ph) % m)
            within1 = float((dev <= 1.0).mean())
            hist = np.bincount(np.round(ph).astype(int) % m, minlength=m)
            print(f"  mod {m:2d} bars: R={Rv:.3f} (uniform ~{1 / np.sqrt(len(bars)):.3f}), "
                  f"best phase {best:5.2f}, {100 * within1:4.0f}% within 1 bar, "
                  f"median |dev| {np.median(dev):.2f} bars")
            print(f"            hist {list(hist)}")
    # section lengths against 8-bar units, using the snapped boundaries
    bnds, majs, _, _ = pick_sections(t, {24.0: n24, 12.0: n12, 6.0: n6}, db0)
    lens = np.diff(bnds) / BAR_S
    print("\nsection lengths in bars (snapped):", [round(x) for x in lens])
    for unit in (4, 8, 16):
        r = np.abs(((lens + unit / 2) % unit) - unit / 2)
        print(f"  distance to a multiple of {unit:2d}: median {np.median(r):.2f} bars, "
              f"{100 * float((r <= 1).mean()):3.0f}% within 1 bar, "
              f"{100 * float((r <= 2).mean()):3.0f}% within 2")
    return bnds


# ----------------------------------------------------------------------
# BAR-RATE analysis (the grid is verified, so work in bars directly)
# ----------------------------------------------------------------------
def bar_matrix(f: dict, db0: float, n_bars: int | None = None):
    """Per-bar features on the verified grid. Returns (bar_start_s, X_normalised, raw)."""
    fps = 1.0 / np.median(np.diff(f["t"]))
    n = len(f["t"])
    total = int((n / fps - db0) / BAR_S)
    n_bars = total if n_bars is None else min(n_bars, total)
    starts = db0 + np.arange(n_bars + 1) * BAR_S
    edges = np.clip(np.round(starts * fps).astype(int), 0, n)
    raw = {}
    for b in BANDS:
        raw[b] = block_mean(f[b], edges)
    raw["rms"] = np.sqrt(block_mean(f["rms"] ** 2, edges))
    raw["peak"] = block_mean(f["peak"], edges)
    for c in ("crest", "centroid", "width", "flux"):
        raw[c] = block_mean(f[c], edges)
    raw["t"] = starts[:-1]

    E = np.stack([np.log10(raw[b] + 1e-6) for b in BANDS], axis=1)
    E = E - E.mean(axis=1, keepdims=True)
    extra = np.stack([np.log10(raw["centroid"] + 1.0), raw["width"] * 10.0,
                      np.log10(raw["crest"] + 1e-6)], axis=1)
    X = np.concatenate([E, extra], axis=1)
    X = (X - X.mean(axis=0)) / (X.std(axis=0) + 1e-9)
    X *= np.array([1.0] * 6 + [0.6, 0.6, 0.4])
    return starts, X, raw


def bar_ssm(X, smooth_bars=4):
    Y = X.copy()
    for j in range(Y.shape[1]):
        Y[:, j] = smooth(Y[:, j], smooth_bars)
    Y = Y / (np.linalg.norm(Y, axis=1, keepdims=True) + 1e-9)
    return Y @ Y.T


def cmd_anchor():
    """Pick the bar phase (which beat is beat 1) that makes the structure line up best: the one
    whose novelty peaks concentrate hardest on 4-bar lines."""
    f = load_frames()
    beat = BEAT_MS / 1000.0
    base = 0.0421
    print("phase  n_peaks  meanNov  R(mod4)  medDev(mod4)  R(mod8)")
    best = None
    for k in range(4):
        db0 = base + k * beat
        starts, X, raw = bar_matrix(f, db0)
        S = bar_ssm(X)
        nv = smooth(novelty(S, 16), 3)
        nv /= nv.max() + 1e-12
        pk, thr = pick_peaks(nv, starts[:-1], min_gap_s=8 * BAR_S, k_mad=1.6)
        ph4 = pk % 4
        a4 = 2 * np.pi * ph4 / 4
        R4 = np.hypot(np.cos(a4).mean(), np.sin(a4).mean())
        b4 = (np.arctan2(np.sin(a4).mean(), np.cos(a4).mean()) % (2 * np.pi)) * 4 / (2 * np.pi)
        dev = np.minimum((ph4 - b4) % 4, (b4 - ph4) % 4)
        a8 = 2 * np.pi * (pk % 8) / 8
        R8 = np.hypot(np.cos(a8).mean(), np.sin(a8).mean())
        print(f"  +{k}b  {len(pk):5d}  {nv[pk].mean():7.3f}  {R4:7.3f}  {np.median(dev):12.2f}"
              f"  {R8:7.3f}")
        score = R4 * nv[pk].mean()
        if best is None or score > best[0]:
            best = (score, k, db0)
    print(f"-> beat-1 anchor = base + {best[1]} beats = {best[2]:.4f} s")
    np.savez(os.path.join(SCRATCH, "anchor.npz"), db0=best[2], k=best[1])
    return best[2]


def bar_pack(db0=0.0421):
    """Everything downstream needs, computed once on the bar grid."""
    cache = os.path.join(SCRATCH, "barpack.npz")
    if os.path.exists(cache):
        z = np.load(cache, allow_pickle=True)
        return {k: z[k] for k in z.files}
    f = load_frames()
    starts, X, raw = bar_matrix(f, db0)
    n = len(X)
    S = bar_ssm(X, smooth_bars=4)
    Sf = bar_ssm(X, smooth_bars=1)                 # unsmoothed: for literal-repeat tests
    ons = onsets_per_bar(f, np.append(starts, starts[-1] + BAR_S)[:n + 1])
    out = {"t": starts[:n], "X": X, "S": S, "Sf": Sf, "db0": np.array(db0)}
    for k, v in raw.items():
        out["raw_" + k] = v[:n]
    for k in ("all", "low", "high"):
        out["ons_" + k] = ons[k][:n]
    np.savez_compressed(cache, **out)
    return out


def bar_novelty(S, halves=(8, 16, 32)):
    out = {}
    for h in halves:
        nv = smooth(novelty(S, h), 3)
        out[h] = nv / (nv.max() + 1e-12)
    return out


def cmd_phrasegrid():
    """Periodicity of the structure itself: autocorrelation of the bar-rate novelty curve and of
    the per-bar low-band energy. Peaks at 4/8/16/32 bars = phrase discipline."""
    p = bar_pack()
    S = p["S"]
    nvs = bar_novelty(S)
    series = {"novelty +-8b": nvs[8], "novelty +-16b": nvs[16],
              "low-band energy/bar": db(p["raw_sub"] + p["raw_bass"]),
              "onsets/bar": p["ons_all"].astype(float),
              "high-band energy/bar": db(p["raw_high"] + p["raw_air"]),
              "rms/bar": db(p["raw_rms"])}
    print("autocorrelation of bar-rate series (lag in BARS); "
          "a jungle record phrased in 8s should spike at 8/16/32")
    print(f"{'series':>22} " + " ".join(f"{l:>6}" for l in (1, 2, 4, 8, 12, 16, 24, 32, 64)))
    for name, v in series.items():
        x = v - v.mean()
        A = np.correlate(x, x, "full")[len(x) - 1:]
        A = A / (A[0] + 1e-12) * (len(x) / np.maximum(len(x) - np.arange(len(A)), 1))
        print(f"{name:>22} " + " ".join(f"{A[l]:6.3f}" for l in (1, 2, 4, 8, 12, 16, 24, 32, 64)))
    # where is the best structural lag, bar by bar?
    best, arg = lag_repetition(S, p["t"], 4 * BAR_S, 64 * BAR_S, path_s=8 * BAR_S)
    lagb = np.round(arg / BAR_S).astype(int)
    hist = np.bincount(lagb, minlength=70)[:70]
    print("\nbest repeat lag per bar (4..64 bars), histogram:")
    for l in range(4, 70):
        if hist[l] > 4:
            print(f"   lag {l:2d} bars: {hist[l]:4d} bars of the set ({100 * hist[l] / len(lagb):4.1f}%)  "
                  f"mean sim {best[lagb == l].mean():.3f}")
    return nvs


def cmd_lagprofile():
    """Mean diagonal similarity as a function of lag, 1..128 bars. Local maxima at 4/8/16/32
    are the phrase grid showing up without any boundary detection in the loop."""
    p = bar_pack()
    for name, S in (("4-bar-smoothed", p["S"]), ("per-bar (literal)", p["Sf"])):
        n = S.shape[0]
        prof = np.array([S[np.arange(L, n), np.arange(0, n - L)].mean() for L in range(1, 129)])
        print(f"\nlag profile, {name} SSM:")
        for row in range(0, 128, 16):
            print("  " + " ".join(f"{L + 1:3d}:{prof[L]:+.3f}" for L in range(row, row + 16)))
        loc = [L + 1 for L in range(1, 127) if prof[L] > prof[L - 1] and prof[L] >= prof[L + 1]]
        print("  local maxima at lags:", loc)
    return prof


def rolling_med(x, w):
    n = len(x)
    out = np.empty(n)
    for i in range(n):
        a, z = max(0, i - w), min(n, i + w + 1)
        out[i] = np.median(x[a:z])
    return out


def cmd_seams():
    """DJ-mix seam evidence, per bar, and a blend-length estimate for each seam."""
    p = bar_pack()
    S, X, t = p["S"], p["X"], p["t"]
    n = len(t)
    nvs = bar_novelty(S, halves=(16, 32))
    lowf = (p["raw_sub"] + p["raw_bass"]) / (sum(p["raw_" + b] for b in BANDS) + 1e-9)
    ons = p["ons_all"].astype(float)
    Xn = X / (np.linalg.norm(X, axis=1, keepdims=True) + 1e-9)

    W = 16
    cross = np.full(n, 1.0)          # similarity of the 16 bars before to the 16 after
    for i in range(W, n - W):
        a = Xn[i - W:i].mean(axis=0); b = Xn[i:i + W].mean(axis=0)
        cross[i] = float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))
    lowdip = rolling_med(lowf, 24) - lowf
    onsjump = ons / (rolling_med(ons, 24) + 1e-9)
    # grid legibility from the phase tracker, resampled to bars
    ph = np.load(os.path.join(SCRATCH, "phase.npz")) if os.path.exists(
        os.path.join(SCRATCH, "phase.npz")) else None
    sharp = np.interp(t, ph["t"], ph["sharp"]) if ph is not None else np.ones(n)
    sharpdip = rolling_med(sharp, 40) - sharp

    def z(v):
        return (v - np.median(v)) / (np.median(np.abs(v - np.median(v))) * 1.4826 + 1e-9)

    score = (1.2 * z(nvs[32]) + 0.8 * z(nvs[16]) + 1.0 * z(-cross) + 0.7 * z(lowdip)
             + 0.6 * z(onsjump) + 0.6 * z(sharpdip))
    score = smooth(score, 5)
    np.savez(os.path.join(SCRATCH, "seams.npz"), t=t, score=score, cross=cross, lowf=lowf,
             lowdip=lowdip, onsjump=onsjump, sharp=sharp, n32=nvs[32], n16=nvs[16])

    cand = [i for i in range(8, n - 8) if score[i] == max(score[max(0, i - 8):i + 9])
            and score[i] > 1.5]
    keep = []
    for i in sorted(cand, key=lambda i: -score[i]):
        if all(abs(i - j) >= 16 for j in keep):
            keep.append(i)
    keep.sort()
    print(f"{'bar':>5} {'time':>8} {'score':>6} {'cross':>6} {'lowdip':>7} {'ons x':>6} "
          f"{'sharpdip':>8} {'nov32':>6} {'blend(bars)':>12} {'blend(s)':>9}")
    rows = []
    for i in keep:
        # blend length: how long the texture takes to go from "before" to "after"
        A = Xn[max(0, i - 40):max(1, i - 16)].mean(axis=0)
        B = Xn[min(n - 1, i + 16):min(n, i + 40)].mean(axis=0)
        A /= np.linalg.norm(A) + 1e-9
        B /= np.linalg.norm(B) + 1e-9
        u0, u1 = max(0, i - 40), min(n, i + 40)
        dcurve = Xn[u0:u1] @ (B - A)
        dcurve = smooth(dcurve, 5)
        lo, hi = np.percentile(dcurve, 10), np.percentile(dcurve, 90)
        if hi - lo < 1e-6:
            bl = np.nan
        else:
            nrm = (dcurve - lo) / (hi - lo)
            up = np.where(nrm >= 0.8)[0]
            dn = np.where(nrm <= 0.2)[0]
            if len(up) and len(dn) and up[-1] > dn[0]:
                first_up = up[up > dn[0]][0] if (up > dn[0]).any() else up[-1]
                last_dn = dn[dn < first_up][-1]
                bl = first_up - last_dn
            else:
                bl = np.nan
        rows.append((i, bl))
        print(f"{i:5d} {fmt_time(t[i]):>8} {score[i]:6.2f} {cross[i]:6.3f} {lowdip[i]:+7.3f} "
              f"{onsjump[i]:6.2f} {sharpdip[i]:+8.2f} {nvs[32][i]:6.3f} "
              f"{bl if bl == bl else -1:12.0f} {(bl * BAR_S) if bl == bl else -1:9.1f}")
    with open(os.path.join(SCRATCH, "seamrows.json"), "w") as fh:
        json.dump([[int(i), (None if r != r else int(r))] for i, r in rows], fh)
    return keep, score


def dp_segment(S: np.ndarray, lam: float, min_len: int = 8, max_len: int = 400):
    """Partition 0..n into blocks maximising sum_blocks (within-block similarity mass / length)
    minus lam per block. Integral image -> O(n^2). This is the same objective as Foote novelty
    but global and with an explicit boundary cost, so the number of blocks is controlled by lam
    instead of by a peak-picking threshold."""
    n = S.shape[0]
    I = np.zeros((n + 1, n + 1))
    I[1:, 1:] = S.cumsum(0).cumsum(1)

    def blocksum(a, z):
        return I[z, z] - I[a, z] - I[z, a] + I[a, a]

    best = np.full(n + 1, -1e18)
    prev = np.zeros(n + 1, int)
    best[0] = 0.0
    for z in range(min_len, n + 1):
        a_lo = max(0, z - max_len)
        a_hi = z - min_len
        av = np.arange(a_lo, a_hi + 1)
        bs = I[z, z] - I[av, z] - I[z, av] + I[av, av]
        sc = best[av] + bs / (z - av) - lam
        j = int(np.argmax(sc))
        best[z] = sc[j]
        prev[z] = av[j]
    cuts = [n]
    while cuts[-1] > 0:
        cuts.append(prev[cuts[-1]])
    return np.array(sorted(set(cuts)))


def cmd_segment():
    p = bar_pack()
    S, t = p["S"], p["t"]
    n = len(t)
    print("lambda sweep (blocks, mean length in bars):")
    table = {}
    for lam in (0.5, 1, 2, 3, 4, 5, 6, 8, 10, 12, 15, 20, 25, 30, 40, 55, 70, 90):
        c = dp_segment(S, lam)
        table[lam] = c
        print(f"  lam {lam:5.1f} -> {len(c) - 1:3d} blocks, mean {n / (len(c) - 1):6.1f} bars "
              f"({n / (len(c) - 1) * BAR_S:5.1f} s)")
    # a track-level and a section-level cut
    trk = min(table.values(), key=lambda c: abs((len(c) - 1) - 9))
    sec = min(table.values(), key=lambda c: abs((len(c) - 1) - 38))
    for name, c in (("TRACK level", trk), ("SECTION level", sec)):
        print(f"\n{name}: {len(c) - 1} blocks")
        for i in range(len(c) - 1):
            a, z = int(c[i]), int(c[i + 1])
            print(f"   bar {a:4d}-{z:4d}  {fmt_time(t[a]):>8}-{fmt_time(t[min(z, n - 1)]):>8}  "
                  f"{z - a:4d} bars  {(z - a) * BAR_S:6.1f} s  "
                  f"within-sim {S[a:z, a:z].mean():.3f}")
    np.savez(os.path.join(SCRATCH, "seg.npz"), track=trk, section=sec)
    return trk, sec


def refine_cuts(Sf, cuts, radius=4, h=8):
    """Move each DP cut to the nearby bar line with the sharpest local contrast, measured on the
    UNSMOOTHED per-bar SSM (the 4-bar smoothing used for the DP blurs a cut by +-2 bars)."""
    n = Sf.shape[0]
    out = [0]
    for c in cuts[1:-1]:
        bestv, bestc = -1e18, c
        for cand in range(max(h, c - radius), min(n - h, c + radius) + 1):
            a = Sf[cand - h:cand, cand - h:cand].mean()
            b = Sf[cand:cand + h, cand:cand + h].mean()
            x = Sf[cand - h:cand, cand:cand + h].mean()
            v = a + b - 2 * x
            if v > bestv:
                bestv, bestc = v, cand
        if bestc - out[-1] >= 8:
            out.append(bestc)
    out.append(n)
    return np.array(out)


LABEL_HELP = """intro/outro  = at the edges of the file
breakdown    = low-band fraction far below the local norm AND onsets down
build        = rms or high-band rising monotonically into a higher-energy block
drop         = low fraction at/above the track norm, onsets high, follows a build/breakdown
groove       = the steady state
transition   = two records audible: seam evidence inside the block"""


def cmd_final():
    p = bar_pack()
    S, Sf, t, X = p["S"], p["Sf"], p["t"], p["X"]
    n = len(t)
    seg = np.load(os.path.join(SCRATCH, "seg.npz"))
    cuts = refine_cuts(Sf, seg["section"])
    tcuts = refine_cuts(Sf, seg["track"])
    print("refined section cuts:", cuts.tolist())
    lens = np.diff(cuts)
    print("lengths in bars:", lens.tolist())
    for unit in (4, 8, 16):
        r = np.abs(((lens + unit / 2) % unit) - unit / 2)
        print(f"  |len| to a multiple of {unit:2d}: median {np.median(r):.1f}, "
              f"{100 * (r == 0).mean():3.0f}% exact, {100 * (r <= 1).mean():3.0f}% within 1, "
              f"{100 * (r <= 2).mean():3.0f}% within 2")
    ph = cuts[1:-1] % 8
    print("  cut positions mod 8 bars:", np.bincount(ph, minlength=8).tolist())
    ph4 = cuts[1:-1] % 4
    print("  cut positions mod 4 bars:", np.bincount(ph4, minlength=4).tolist())

    # repetition measures
    rec8, reclag8 = lag_repetition(S, t, 16 * BAR_S, 700.0, path_s=8 * BAR_S)
    loop, looplag = lag_repetition(S, t, 2 * BAR_S, 16 * BAR_S, path_s=8 * BAR_S)
    print(f"\nrecall(>=16 bars back, 8-bar path) distribution: "
          f"p10 {np.percentile(rec8, 10):.2f} p50 {np.percentile(rec8, 50):.2f} "
          f"p90 {np.percentile(rec8, 90):.2f}")
    print(f"loop(2..16 bars back): p10 {np.percentile(loop, 10):.2f} "
          f"p50 {np.percentile(loop, 50):.2f} p90 {np.percentile(loop, 90):.2f}")

    lowf = (p["raw_sub"] + p["raw_bass"]) / (sum(p["raw_" + b] for b in BANDS) + 1e-9)
    hif = (p["raw_high"] + p["raw_air"]) / (sum(p["raw_" + b] for b in BANDS) + 1e-9)
    rmsdb = db(p["raw_rms"])
    ons = p["ons_all"].astype(float)
    onslo = p["ons_low"].astype(float)
    sm = np.load(os.path.join(SCRATCH, "seams.npz"))
    seamscore = np.interp(t, sm["t"], sm["score"])

    rows = []
    for i in range(len(cuts) - 1):
        a, z = int(cuts[i]), int(cuts[i + 1])
        sl = slice(a, z)
        trk = int(np.searchsorted(tcuts, a, "right") - 1)
        prev = rows[-1] if rows else None
        r = dict(i=i, a=a, z=z, bars=z - a, t0=float(t[a]),
                 t1=float(t[z]) if z < n else 1259.727,
                 rms=float(rmsdb[sl].mean()),
                 rms_in=float(rmsdb[a:a + 4].mean()), rms_out=float(rmsdb[max(a, z - 4):z].mean()),
                 slope=float(np.polyfit(np.arange(z - a), rmsdb[sl], 1)[0]) if z - a > 3 else 0.0,
                 low=float(lowf[sl].mean()), hi=float(hif[sl].mean()),
                 cent=float(p["raw_centroid"][sl].mean()),
                 width=float(p["raw_width"][sl].mean()),
                 crest=float(p["raw_crest"][sl].mean()),
                 ons=float(ons[sl].mean()), onslo=float(onslo[sl].mean()),
                 rec=float(rec8[sl].mean()), rec_hi=float((rec8[sl] > 0.85).mean()),
                 reclag=float(np.median(reclag8[sl]) / BAR_S),
                 loop=float(loop[sl].mean()), looplag=float(np.median(looplag[sl]) / BAR_S),
                 seam=float(seamscore[sl].max()), track=trk,
                 dsim=float(S[max(0, a - 12):a, a:a + 12].mean()) if a >= 12 else 0.0)
        rows.append(r)

    hdr = (f"{'#':>2} {'bar':>4} {'start':>8} {'end':>8} {'bars':>4} {'s':>6} {'trk':>3} "
           f"{'rms':>6} {'slp':>6} {'low%':>5} {'hi%':>5} {'cent':>5} {'wid':>5} {'crst':>5} "
           f"{'on/b':>5} {'lo/b':>5} {'rec':>5} {'rec%':>5} {'rlag':>5} {'loop':>5} "
           f"{'llag':>5} {'seam':>5} {'join':>5}")
    print("\n" + hdr)
    for r in rows:
        print(f"{r['i']:2d} {r['a']:4d} {fmt_time(r['t0']):>8} {fmt_time(r['t1']):>8} "
              f"{r['bars']:4d} {r['t1'] - r['t0']:6.1f} {r['track']:3d} {r['rms']:6.1f} "
              f"{r['slope']:+6.3f} {100 * r['low']:5.1f} {100 * r['hi']:5.1f} "
              f"{r['cent']:5.0f} {r['width']:5.3f} {r['crest']:5.2f} {r['ons']:5.2f} "
              f"{r['onslo']:5.2f} {r['rec']:5.2f} {100 * r['rec_hi']:5.0f} {r['reclag']:5.0f} "
              f"{r['loop']:5.2f} {r['looplag']:5.0f} {r['seam']:5.1f} {r['dsim']:+5.2f}")
    with open(os.path.join(SCRATCH, "final.json"), "w") as fh:
        json.dump({"rows": rows, "cuts": cuts.tolist(), "tcuts": tcuts.tolist(),
                   "bar_s": BAR_S, "bpm": 60000 / BEAT_MS}, fh, indent=1)
    print("\nTRACK-level blocks (refined):")
    for i in range(len(tcuts) - 1):
        a, z = int(tcuts[i]), int(tcuts[i + 1])
        print(f"  T{i}  bar {a:4d}-{z:4d}  {fmt_time(t[a]):>8}-"
              f"{fmt_time(t[z] if z < n else 1259.7):>8}  {z - a:4d} bars "
              f"{(z - a) * BAR_S:6.1f} s  within {S[a:z, a:z].mean():.3f}  "
              f"cross-to-prev {S[max(0, a - 24):a, a:a + 24].mean():+.3f}")
    return rows, cuts, tcuts


def cmd_blend():
    """Bar-by-bar profile around every track-level cut: is there a window where BOTH records are
    audible? Evidence = onset density above both sides, low-band fraction dipping (the classic EQ
    bass handover), beat-comb sharpness dipping, and the texture crossfading from A to B."""
    p = bar_pack()
    S, X, t = p["S"], p["X"], p["t"]
    n = len(t)
    fin = json.load(open(os.path.join(SCRATCH, "final.json")))
    tcuts = fin["tcuts"]
    lowf = (p["raw_sub"] + p["raw_bass"]) / (sum(p["raw_" + b] for b in BANDS) + 1e-9)
    ons = p["ons_all"].astype(float)
    Xn = X / (np.linalg.norm(X, axis=1, keepdims=True) + 1e-9)
    ph = np.load(os.path.join(SCRATCH, "phase.npz"))
    sharp = np.interp(t, ph["t"], ph["sharp"])
    rmsdb = db(p["raw_rms"])

    print("bar-by-bar around each track cut.  A/B = cosine to the 24 bars well before / after.")
    for c in tcuts[1:-1]:
        c = int(c)
        A = Xn[max(0, c - 48):c - 24].mean(axis=0); A /= np.linalg.norm(A) + 1e-9
        B = Xn[c + 24:min(n, c + 48)].mean(axis=0); B /= np.linalg.norm(B) + 1e-9
        loA = np.median(lowf[max(0, c - 48):c - 24]); loB = np.median(lowf[c + 24:min(n, c + 48)])
        onA = np.median(ons[max(0, c - 48):c - 24]); onB = np.median(ons[c + 24:min(n, c + 48)])
        shA = np.median(sharp[max(0, c - 48):c - 24]); shB = np.median(sharp[c + 24:min(n, c + 48)])
        print(f"\n=== cut at bar {c} ({fmt_time(t[c])}) ===  low% {100 * loA:.1f}->{100 * loB:.1f}"
              f"  ons/bar {onA:.1f}->{onB:.1f}  sharp {shA:.2f}->{shB:.2f}")
        print(f"{'bar':>5} {'time':>8} {'A':>6} {'B':>6} {'B-A':>6} {'low%':>6} {'ons':>5} "
              f"{'sharp':>6} {'rms':>6}")
        for b in range(max(0, c - 20), min(n, c + 21)):
            sa = float(Xn[b] @ A); sb = float(Xn[b] @ B)
            mark = " <<<" if b == c else ""
            over = " both" if (ons[b] > max(onA, onB) * 1.12 and
                               sharp[b] < min(shA, shB) * 0.98) else ""
            print(f"{b:5d} {fmt_time(t[b]):>8} {sa:+6.2f} {sb:+6.2f} {sb - sa:+6.2f} "
                  f"{100 * lowf[b]:6.1f} {ons[b]:5.0f} {sharp[b]:6.2f} {rmsdb[b]:6.1f}"
                  f"{mark}{over}")


def label_sections(rows, tcuts):
    """Numeric labelling rules, all relative to the parent track block's own norm."""
    import statistics as st
    by_track = {}
    for r in rows:
        by_track.setdefault(r["track"], []).append(r)
    norm = {k: {"rms": st.median([x["rms"] for x in v])} for k, v in by_track.items()}
    setlow = st.median([r["low"] for r in rows])          # 0.125 - the set-wide low-band norm
    setons = st.median([r["ons"] for r in rows])
    n = len(rows)
    for r in rows:
        r["lowrel"] = r["low"] / setlow                   # bass presence vs the whole set
        r["rmsrel"] = r["rms"] - norm[r["track"]]["rms"]  # level vs this record's own norm
        r["onsrel"] = r["ons"] / setons
    for i, r in enumerate(rows):
        nx = rows[i + 1] if i + 1 < n else None
        pv = rows[i - 1] if i else None
        at_cut = min(abs(r["a"] - c) for c in tcuts) <= 4
        lab = "groove"
        if r["lowrel"] > 1.45 and r["rmsrel"] > -1.0 and (pv is None or pv["lowrel"] < 1.1):
            lab = "drop"
        if r["lowrel"] > 1.30 and pv is not None and pv["lowrel"] < 0.60:
            lab = "drop"
        if r["lowrel"] < 0.45:
            lab = "breakdown"
        if r["slope"] > 0.15 and nx and (nx["rms"] > r["rms"] + 0.8 or nx["low"] > r["low"] * 1.4):
            lab = "build"
        if at_cut and r["seam"] > 8.0 and 0.45 <= r["lowrel"] <= 1.45:
            lab = "transition"
        if i == 0:
            lab = "intro/mix-in"
        if i == n - 1:
            lab = "outro/mix-out"
        r["label"] = lab
        r["at_cut"] = bool(at_cut)
    return rows


def cmd_label():
    fin = json.load(open(os.path.join(SCRATCH, "final.json")))
    rows = label_sections(fin["rows"], fin["tcuts"])
    for r in rows:
        print(f"{r['i']:2d} {fmt_time(r['t0']):>8}-{fmt_time(r['t1']):>8} {r['bars']:3d}b "
              f"T{r['track']} {r['label']:>14}  lowrel {r['lowrel']:5.2f} rmsrel "
              f"{r['rmsrel']:+5.1f} onsrel {r['onsrel']:4.2f} slope {r['slope']:+.3f} "
              f"seam {r['seam']:4.1f} rec% {100 * r['rec_hi']:3.0f}")
    with open(os.path.join(SCRATCH, "labelled.json"), "w") as fh:
        json.dump(fin | {"rows": rows}, fh, indent=1)
    from collections import Counter
    print(Counter(r["label"] for r in rows))
    return rows


def cmd_tracksim():
    """Do records come back? Mean similarity between every pair of track-level blocks, plus a
    finer sweep for a 10th/11th candidate record."""
    p = bar_pack()
    S, t = p["S"], p["t"]
    n = len(t)
    fin = json.load(open(os.path.join(SCRATCH, "final.json")))
    tc = [int(x) for x in fin["tcuts"]]
    k = len(tc) - 1
    M = np.zeros((k, k))
    for i in range(k):
        for j in range(k):
            M[i, j] = S[tc[i]:tc[i + 1], tc[j]:tc[j + 1]].mean()
    print("track-block similarity (diagonal = internal cohesion):")
    print("     " + " ".join(f"T{j:<5d}" for j in range(k)))
    for i in range(k):
        print(f"T{i:<3d} " + " ".join(f"{M[i, j]:+6.3f}" for j in range(k)))
    print("\noff-diagonal pairs above +0.15 (a record, or its family, coming back):")
    for i in range(k):
        for j in range(i + 1, k):
            if M[i, j] > 0.15:
                print(f"  T{i} ({fmt_time(t[tc[i]])}) vs T{j} ({fmt_time(t[tc[j]])}): {M[i, j]:+.3f}")
    for lam in (12, 15):
        c = dp_segment(S, lam)
        print(f"\nlam {lam}: {len(c) - 1} blocks -> " +
              ", ".join(f"{fmt_time(t[int(x)])}" for x in c[:-1]))
    return M


def cmd_repeat():
    """Literal repetition per section: internal 4/8/16-bar self-repeat (unsmoothed SSM) and how
    much of the section matches material >=16 bars earlier."""
    p = bar_pack()
    S, Sf, t = p["S"], p["Sf"], p["t"]
    n = len(t)
    fin = json.load(open(os.path.join(SCRATCH, "labelled.json")))
    rows = fin["rows"]
    rec, reclag = lag_repetition(S, t, 16 * BAR_S, 700.0, path_s=8 * BAR_S)
    print(f"{'#':>2} {'start':>8} {'bars':>4} {'label':>14} {'rep4':>5} {'rep8':>5} "
          f"{'rep16':>5} {'rep32':>5} {'newmat%':>7} {'recall%':>7} {'rlag(b)':>7} {'from':>8}")
    for r in rows:
        a, z = r["a"], r["z"]
        def selfrep(L):
            i = np.arange(max(a, L), z)
            return float(Sf[i, i - L].mean()) if len(i) else float("nan")
        sl = slice(a, z)
        rc = rec[sl]
        lg = reclag[sl]
        hi = rc > 0.85
        r["rep4"], r["rep8"] = selfrep(4), selfrep(8)
        r["rep16"], r["rep32"] = selfrep(16), selfrep(32)
        r["recall_pct"] = float(hi.mean())
        r["new_pct"] = float((rc < 0.70).mean())
        src = float(np.median(t[sl][hi] - lg[hi])) if hi.any() else float("nan")
        r["recall_from"] = src
        print(f"{r['i']:2d} {fmt_time(r['t0']):>8} {r['bars']:4d} {r['label']:>14} "
              f"{r['rep4']:5.2f} {r['rep8']:5.2f} {r['rep16']:5.2f} {r['rep32']:5.2f} "
              f"{100 * r['new_pct']:7.0f} {100 * r['recall_pct']:7.0f} "
              f"{np.median(lg) / BAR_S:7.0f} {fmt_time(src) if src == src else '     -':>8}")
    a4 = np.array([r["rep4"] for r in rows]); a8 = np.array([r["rep8"] for r in rows])
    a16 = np.array([r["rep16"] for r in rows]); a32 = np.array([r["rep32"] for r in rows])
    print(f"\nmedian literal self-similarity: lag4 {np.nanmedian(a4):.2f}  lag8 "
          f"{np.nanmedian(a8):.2f}  lag16 {np.nanmedian(a16):.2f}  lag32 {np.nanmedian(a32):.2f}")
    print(f"median 'recalls earlier material' {100 * np.median([r['recall_pct'] for r in rows]):.0f}%"
          f", median 'new material' {100 * np.median([r['new_pct'] for r in rows]):.0f}%")
    with open(os.path.join(SCRATCH, "repeat.json"), "w") as fh:
        json.dump(fin | {"rows": rows}, fh, indent=1)
    return rows


def cmd_summary():
    """Aggregate numbers for the write-up."""
    p = bar_pack()
    t = p["t"]
    n = len(t)
    lowf = (p["raw_sub"] + p["raw_bass"]) / (sum(p["raw_" + b] for b in BANDS) + 1e-9)
    rmsdb = db(p["raw_rms"])
    ons = p["ons_all"].astype(float)
    fin = json.load(open(os.path.join(SCRATCH, "repeat.json")))
    rows, tcuts = fin["rows"], [int(x) for x in fin["tcuts"]]
    print(f"duration {1259.727:.1f} s | beat {BEAT_MS:.3f} ms = {60000 / BEAT_MS:.3f} BPM | "
          f"bar {BAR_S:.5f} s | {n} bars | {n / 8:.2f} eight-bar phrases")
    bare = lowf < 0.05
    runs, cur = [], 0
    for b in bare:
        cur = cur + 1 if b else 0
        if not b and cur:
            runs.append(cur)
        if b:
            pass
    runs = []
    i = 0
    while i < n:
        if bare[i]:
            j = i
            while j < n and bare[j]:
                j += 1
            runs.append((i, j - i))
            i = j
        else:
            i += 1
    long = [r for r in runs if r[1] >= 4]
    print(f"bass-stripped bars (low band <5% of the spectrum): {bare.sum()} / {n} "
          f"({100 * bare.mean():.1f}%); runs >=4 bars: {len(long)}")
    for a, L in long:
        print(f"   bars {a:4d}-{a + L:4d} {fmt_time(t[a]):>8} {L:3d} bars ({L * BAR_S:5.1f} s) "
              f"rms {rmsdb[a:a + L].mean():6.1f} dB  ons/bar {ons[a:a + L].mean():4.1f}"
              f"{'   <- at a track cut' if min(abs(a - c) for c in tcuts) <= 2 or min(abs(a + L - c) for c in tcuts) <= 2 else ''}")
    lens = np.array([r["bars"] for r in rows])
    print(f"\nsection lengths: n={len(lens)} min {lens.min()} max {lens.max()} "
          f"median {int(np.median(lens))} mean {lens.mean():.1f} bars "
          f"({np.median(lens) * BAR_S:.1f} s median)")
    print("  histogram by 8-bar band:",
          {f"{8 * k}-{8 * k + 7}": int(((lens >= 8 * k) & (lens < 8 * k + 8)).sum())
           for k in range(0, 7)})
    tl = np.diff(tcuts)
    print(f"\ntrack blocks: n={len(tl)} lengths(bars) {tl.tolist()} "
          f"= {(tl * BAR_S).round(0).tolist()} s")
    print(f"  median {np.median(tl):.0f} bars ({np.median(tl) * BAR_S:.0f} s), "
          f"mean {tl.mean():.0f} bars ({tl.mean() * BAR_S:.0f} s)")
    print(f"  distance of each track length to the nearest multiple of 8: "
          f"{[int(min(abs(x - 8 * round(x / 8)), 8)) for x in tl]}")
    # loudness arc
    print("\nper-minute rms (dB) and low-band fraction:")
    for m in range(0, 21):
        sl = (t >= m * 60) & (t < (m + 1) * 60)
        if sl.sum():
            print(f"  {m:02d}:00  rms {rmsdb[sl].mean():6.2f}  low {100 * lowf[sl].mean():5.1f}%  "
                  f"ons/bar {ons[sl].mean():5.1f}")
    lab = {}
    for r in rows:
        lab.setdefault(r["label"], []).append(r["bars"])
    print("\nlabel -> count, total bars, median bars")
    for k, v in sorted(lab.items(), key=lambda kv: -sum(kv[1])):
        print(f"  {k:>14}: {len(v):2d} sections, {sum(v):4d} bars "
              f"({100 * sum(v) / n:4.1f}%), median {int(np.median(v))}")


def cmd_seamtable():
    """One row per track cut: handover length, bass-swap depth, doubled-drum bars, grid dip."""
    p = bar_pack()
    S, X, t = p["S"], p["X"], p["t"]
    n = len(t)
    fin = json.load(open(os.path.join(SCRATCH, "repeat.json")))
    tc = [int(x) for x in fin["tcuts"]]
    lowf = (p["raw_sub"] + p["raw_bass"]) / (sum(p["raw_" + b] for b in BANDS) + 1e-9)
    ons = p["ons_all"].astype(float)
    rmsdb = db(p["raw_rms"])
    Xn = X / (np.linalg.norm(X, axis=1, keepdims=True) + 1e-9)
    ph = np.load(os.path.join(SCRATCH, "phase.npz"))
    sharp = np.interp(t, ph["t"], ph["sharp"])
    print(f"{'cut':>5} {'time':>8} {'handover':>9} {'s':>6} {'bassout':>8} {'minlow%':>8} "
          f"{'dbl-drum':>9} {'maxons':>7} {'sharp':>13} {'rmsdip':>7}")
    for c in tc[1:-1]:
        A = Xn[max(0, c - 48):c - 24].mean(axis=0); A /= np.linalg.norm(A) + 1e-9
        B = Xn[c + 24:min(n, c + 48)].mean(axis=0); B /= np.linalg.norm(B) + 1e-9
        w = np.arange(max(0, c - 24), min(n, c + 25))
        dd = smooth(Xn[w] @ (B - A), 3)
        lo, hi = np.percentile(dd, 8), np.percentile(dd, 92)
        nrm = (dd - lo) / (hi - lo + 1e-9)
        mid = np.where((nrm > 0.2) & (nrm < 0.8))[0]
        # contiguous run of "neither side dominates" that contains the cut
        ci = int(np.argmin(np.abs(w - c)))
        run = 0
        if len(mid):
            grp, cur = [], [mid[0]]
            for x in mid[1:]:
                if x == cur[-1] + 1:
                    cur.append(x)
                else:
                    grp.append(cur); cur = [x]
            grp.append(cur)
            near = [g for g in grp if g[0] - 2 <= ci <= g[-1] + 2]
            run = len(max(near, key=len)) if near else 0
        pre = slice(max(0, c - 16), c)
        loA = np.median(lowf[max(0, c - 48):c - 24])
        bassout = int((lowf[pre] < 0.5 * loA).sum())
        onA = np.median(ons[max(0, c - 48):c - 24]); onB = np.median(ons[c + 24:min(n, c + 48)])
        nearw = slice(max(0, c - 8), min(n, c + 9))
        dbl = int((ons[nearw] > 1.35 * max(onA, onB)).sum())
        shA = np.median(sharp[max(0, c - 48):c - 24]); shB = np.median(sharp[c + 24:min(n, c + 48)])
        shmin = sharp[max(0, c - 24):min(n, c + 25)].min()
        rmsA = np.median(rmsdb[max(0, c - 48):c - 24])
        # alternation: bar-to-bar flips of "which record is on top" in a +-24 bar window
        raw_d = Xn[w] @ (B - A)
        flips = int((np.diff(np.sign(raw_d)) != 0).sum())
        print(f"{c:5d} {fmt_time(t[c]):>8} {run:9d} {run * BAR_S:6.1f} {bassout:8d} "
              f"{100 * lowf[pre].min():8.1f} {dbl:9d} {ons[nearw].max():7.0f} "
              f"{shA:5.2f}/{shmin:4.2f}/{shB:4.2f} "
              f"{rmsdb[max(0, c - 8):c].min() - rmsA:+7.1f} {flips:6d}")


def main(argv):
    cmd = argv[0] if argv else "all"
    if cmd == "seamtable":
        cmd_seamtable()
    elif cmd == "summary":
        cmd_summary()
    elif cmd == "tracksim":
        cmd_tracksim()
    elif cmd == "repeat":
        cmd_repeat()
    elif cmd == "blend":
        cmd_blend()
    elif cmd == "label":
        cmd_label()
    elif cmd == "final":
        cmd_final()
    elif cmd == "segment":
        cmd_segment()
    elif cmd == "lagprofile":
        cmd_lagprofile()
    elif cmd == "seams":
        cmd_seams()
    elif cmd == "phrasegrid":
        cmd_phrasegrid()
    elif cmd == "anchor":
        cmd_anchor()
    elif cmd == "phrase":
        cmd_phrase()
    elif cmd == "sections":
        cmd_sections()
    elif cmd == "map":
        cmd_map(float(argv[1]) if len(argv) > 1 else 15.0)
    elif cmd == "boundaries":
        cmd_boundaries()
    elif cmd == "downbeat":
        cmd_downbeat()
    elif cmd == "acf":
        cmd_acf()
    elif cmd == "phasecurve":
        cmd_phasecurve()
    elif cmd == "phase":
        cmd_phase()
    elif cmd == "grid":
        cmd_grid()
    elif cmd == "beats":
        cmd_beats()
    elif cmd == "fitgrid":
        cmd_fitgrid()
    elif cmd == "all":
        os.makedirs(SCRATCH, exist_ok=True)
        for f in ("barpack.npz",):                      # force a rebuild of the bar cache
            q = os.path.join(SCRATCH, f)
            if os.path.exists(q):
                os.remove(q)
        for step in (cmd_acf, cmd_grid, cmd_phase, cmd_downbeat, cmd_boundaries, cmd_segment,
                     cmd_lagprofile, cmd_phrasegrid, cmd_final, cmd_seams, cmd_label,
                     cmd_repeat, cmd_seamtable, cmd_summary, cmd_map, cmd_tracksim, cmd_blend):
            print(f"\n{'=' * 78}\n== {step.__name__}\n{'=' * 78}")
            step()
    else:
        print(__doc__)
        print("\ncommands: all acf grid phase fitgrid phasecurve downbeat anchor boundaries "
              "segment lagprofile phrasegrid final seams label repeat seamtable summary map "
              "tracksim blend")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
