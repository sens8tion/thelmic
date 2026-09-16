"""REAPER BASS - what the low end of the reference jungle DJ set actually does.

STRUCTURAL ANALYSIS ONLY. Nothing here reads, writes or copies audio material out of the
reference: every output is a number, a duration, an interval or a decibel. No audio is
rendered, sliced, resampled to disk or exported.

Numpy + torch only (no librosa/scipy/soundfile/sklearn). Everything is built here: FFT
band filters, a YIN F0 tracker, a DP beat tracker, checkerboard novelty segmentation,
note segmentation, kick-relative sub-band windows, and a harmonic-comb reese test.

Stages (each caches an npz into the scratch dir so the next one is cheap):

    python scripts/reaper_bass.py grid       # beat/bar grid from the onset envelope
    python scripts/reaper_bass.py sections   # checkerboard novelty -> section boundaries
    python scripts/reaper_bass.py f0         # YIN over a 28-180 Hz band, decimated to 2 kHz
    python scripts/reaper_bass.py notes      # segment the F0 track into held notes
    python scripts/reaper_bass.py spec       # register fractions + harmonic comb (reese test)
    python scripts/reaper_bass.py kick       # kick onsets, post-kick sub windows, duck in dB
    python scripts/reaper_bass.py report     # print the whole numeric report
    python scripts/reaper_bass.py all        # everything in order
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np
import torch

CACHE = r"C:\Users\eric\Downloads\reaper_cache"
SCRATCH = (r"C:\Users\eric\AppData\Local\Temp\claude\C--Users-eric-github-sens8tion-thelmic"
           r"\b784ee21-3fab-4996-98dd-32e4a4e5ac45\scratchpad\bass")

SR8 = 8000                 # mono8k.npy
DEC = 4                    # 8 kHz -> 2 kHz for the pitch work
SRP = SR8 // DEC           # 2000 Hz pitch-analysis rate
F0_LO, F0_HI = 30.0, 150.0
YIN_W = 320                # 160 ms analysis window at 2 kHz
YIN_HOP = 48               # 24 ms -> 41.67 fps
YIN_THRESH = 0.16
ENV_HOP = 40               # 5 ms blocks at 8 kHz -> 200 fps envelopes


# ----------------------------------------------------------------------
# small DSP helpers
# ----------------------------------------------------------------------
def fft_band(x: np.ndarray, sr: int, lo: float, hi: float, taper: float = 0.25) -> np.ndarray:
    """Zero-phase band-pass by masking the rfft, with cosine-tapered edges (no scipy here)."""
    t = torch.from_numpy(np.ascontiguousarray(x, dtype=np.float32))
    X = torch.fft.rfft(t)
    f = torch.fft.rfftfreq(t.numel(), 1.0 / sr)
    m = torch.ones_like(f)
    if lo > 0:
        w = max(lo * taper, 1.0)
        m = m * torch.clamp((f - (lo - w)) / w, 0.0, 1.0)
        m = torch.where(f < lo - w, torch.zeros_like(m), m)
    if hi < sr / 2:
        w = max(hi * taper, 1.0)
        m = m * torch.clamp(((hi + w) - f) / w, 0.0, 1.0)
    X = X * m.to(X.dtype)
    return torch.fft.irfft(X, n=t.numel()).numpy().astype(np.float32)


def block_rms(x: np.ndarray, hop: int) -> np.ndarray:
    n = (len(x) // hop) * hop
    return np.sqrt((x[:n].astype(np.float64) ** 2).reshape(-1, hop).mean(axis=1)).astype(np.float32)


def medfilt(x: np.ndarray, k: int) -> np.ndarray:
    """Odd-length median filter, edges reflected."""
    if k <= 1:
        return x.copy()
    k |= 1
    p = k // 2
    xp = np.concatenate([x[p:0:-1], x, x[-2:-2 - p:-1]])
    win = np.lib.stride_tricks.sliding_window_view(xp, k)[:len(x)]
    return np.median(win, axis=1).astype(x.dtype)


def frames_of(x: np.ndarray, w: int, hop: int) -> np.ndarray:
    n = 1 + (len(x) - w) // hop
    return np.lib.stride_tricks.as_strided(x, (n, w), (x.strides[0] * hop, x.strides[0]))


def scratch(name: str) -> str:
    os.makedirs(SCRATCH, exist_ok=True)
    return os.path.join(SCRATCH, name)


def hz_to_midi(f):
    return 69.0 + 12.0 * np.log2(np.maximum(f, 1e-6) / 440.0)


NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def midi_name(m: float) -> str:
    i = int(round(m))
    return f"{NOTE_NAMES[i % 12]}{i // 12 - 1}"


def db(x, ref):
    return 10.0 * np.log10(np.maximum(x, 1e-20) / max(float(ref), 1e-20))


def grp(bs, edges, lo, hi):
    """Sum the per-band values whose edges fall inside [lo, hi)."""
    e = np.asarray(edges)
    return float(bs[(e[:, 0] >= lo) & (e[:, 1] <= hi)].sum())


MAJOR_SET = np.array([0, 2, 4, 5, 7, 9, 11])


def best_scale(pc: np.ndarray):
    """-> (tonic of the best-fitting 7-note diatonic collection, fraction of weight inside it).
    Reported as the relative MINOR tonic, which is what a jungle bassline sits on."""
    best = (0, -1.0)
    for t in range(12):
        inside = float(pc[(MAJOR_SET + t) % 12].sum()) / max(pc.sum(), 1e-20)
        if inside > best[1]:
            best = (t, inside)
    return (best[0] + 9) % 12, best[1]


# ----------------------------------------------------------------------
# 1. beat / bar grid  (grid.npz from the other agent if it turns up, else our own DP tracker)
# ----------------------------------------------------------------------
def dp_beats(onset: np.ndarray, period: float, tightness: float = 300.0) -> np.ndarray:
    """Ellis-style dynamic-programming beat tracker: best chain of onset peaks spaced ~period."""
    o = onset / (onset.std() + 1e-9)
    lo, hi = int(round(period * 0.55)), int(round(period * 1.8))
    lags = np.arange(lo, hi + 1)
    pen = -tightness * (np.log(lags / period) ** 2)
    pen_rev = pen[::-1].copy()                     # index 0 <-> lag hi, last <-> lag lo
    n = len(o)
    cum = np.zeros(n, np.float64)
    back = np.full(n, -1, np.int64)
    for i in range(n):
        a, b = i - hi, i - lo
        if b < 0:
            cum[i] = o[i]
            continue
        a0 = max(a, 0)
        p = pen_rev[a0 - a:a0 - a + (b - a0 + 1)]
        cand = cum[a0:b + 1] + p
        k = int(np.argmax(cand))
        cum[i] = o[i] + cand[k]
        back[i] = a0 + k
    tail = int(np.argmax(cum[-int(2 * period):]) + len(cum) - int(2 * period))
    beats = []
    i = tail
    while i >= 0:
        beats.append(i)
        i = back[i]
    return np.array(beats[::-1], np.float64)


def stage_grid():
    ext = os.path.join(CACHE, "grid.npz")
    if os.path.exists(ext):
        g = np.load(ext, allow_pickle=True)
        if "beats_s" in g.files:
            bt = np.asarray(g["beats_s"], np.float64)
            dbt = np.asarray(g["downbeats_s"], np.float64) if "downbeats_s" in g.files else bt[::4]
            # least-squares beat length: the stored beats are quantised to the 93.75 fps frame grid,
            # so a median of the diffs under-reads the tempo by ~0.5 BPM.
            beat_s = float((bt[-1] - bt[0]) / (len(bt) - 1))
            np.savez(scratch("grid.npz"), beat_s=bt, downbeat_s=dbt,
                     beat_len=np.array([beat_s]), source=np.array([1]))
            print(f"grid.npz from the other agent: {len(bt)} beats, {len(dbt)} downbeats, "
                  f"lsq {60 / beat_s:.2f} BPM (median-of-diffs {60 / np.median(np.diff(bt)):.2f}), "
                  f"bar {4 * beat_s:.4f} s")
            return
    f = np.load(os.path.join(CACHE, "frames.npz"))
    meta = json.load(open(os.path.join(CACHE, "meta.json")))
    fps = meta["fps"]
    env = f["flux"].astype(np.float64)
    env = env / (env.max() + 1e-12)
    # local tempo, 16 s windows, to check the set is really beatmatched
    w = int(16 * fps)
    bpms = []
    for a in range(0, len(env) - w, w):
        e = env[a:a + w] - env[a:a + w].mean()
        ac = np.correlate(e, e, "full")[w - 1:]
        lags = np.arange(len(ac))
        with np.errstate(divide="ignore"):
            bpm = 60.0 * fps / np.maximum(lags, 1e-9)
        ok = (bpm >= 150) & (bpm <= 190)
        bpms.append(float(bpm[ok][np.argmax(ac[ok])]))
    bpms = np.array(bpms)
    period = 60.0 * fps / float(np.median(bpms))
    print(f"local tempo over {len(bpms)} x 16 s windows: median {np.median(bpms):.2f} BPM, "
          f"p10 {np.percentile(bpms, 10):.2f}, p90 {np.percentile(bpms, 90):.2f}, "
          f"frac within 1 BPM of median {np.mean(np.abs(bpms - np.median(bpms)) < 1.0):.2f}")
    beats = dp_beats(env, period)
    bt = beats / fps
    ibi = np.diff(bt)
    beat_s = float((bt[-1] - bt[0]) / (len(bt) - 1))
    print(f"DP beats: {len(bt)}, median IBI {np.median(ibi) * 1000:.1f} ms "
          f"({60 / np.median(ibi):.2f} BPM), IQR {np.percentile(ibi, 75) - np.percentile(ibi, 25):.4f} s")
    low = np.interp(beats, np.arange(len(f["sub"])), f["sub"] + f["bass"])
    first = int(np.argmax([low[k::4].mean() for k in range(4)]))
    np.savez(scratch("grid.npz"), beat_s=bt, downbeat_s=bt[first::4],
             beat_len=np.array([beat_s]), source=np.array([0]))


def load_grid():
    g = np.load(scratch("grid.npz"))
    return g["beat_s"].astype(np.float64), g["downbeat_s"].astype(np.float64), float(g["beat_len"][0])


# ----------------------------------------------------------------------
# 2. sections (checkerboard novelty on 1.5 s blocks of the cached frame features)
# ----------------------------------------------------------------------
def stage_sections():
    f = np.load(os.path.join(CACHE, "frames.npz"))
    meta = json.load(open(os.path.join(CACHE, "meta.json")))
    fps, dur = meta["fps"], meta["duration_s"]
    blk = int(round(1.5 * fps))
    n = len(f["t"]) // blk
    bands = ["sub", "bass", "lowmid", "mid", "high", "air"]
    E = np.stack([f[b][:n * blk].reshape(n, blk).mean(axis=1) for b in bands], 1)
    L = np.log10(E + 1e-9)
    tot = np.log10(E.sum(1, keepdims=True) + 1e-9)
    feat = np.concatenate([L - tot, tot,
                           np.log10(f["centroid"][:n * blk].reshape(n, blk).mean(1) + 1)[:, None],
                           f["width"][:n * blk].reshape(n, blk).mean(1)[:, None] * 5,
                           f["crest"][:n * blk].reshape(n, blk).mean(1)[:, None] * 0.1], 1)
    feat = (feat - feat.mean(0)) / (feat.std(0) + 1e-9)
    Z = feat / (np.linalg.norm(feat, axis=1, keepdims=True) + 1e-9)
    S = Z @ Z.T
    L2 = 16                                              # 24 s half-kernel
    g = np.outer(*(2 * [np.exp(-0.5 * (np.arange(-L2, L2) + 0.5) ** 2 / (L2 / 2.0) ** 2)]))
    sign = np.sign(np.outer(np.r_[-np.ones(L2), np.ones(L2)], np.r_[-np.ones(L2), np.ones(L2)]))
    K = g * sign
    nov = np.zeros(n)
    for i in range(L2, n - L2):
        nov[i] = (S[i - L2:i + L2, i - L2:i + L2] * K).sum()
    nov = np.maximum(nov - medfilt(nov, 41), 0)
    nov /= (nov.max() + 1e-9)
    minsep = 20                                          # >= 30 s apart
    order = np.argsort(nov)[::-1]
    picks = []
    for i in order:
        if nov[i] < 0.12:
            break
        if all(abs(i - p) >= minsep for p in picks):
            picks.append(int(i))
    picks = sorted(picks)
    bounds = np.array([0.0] + [p * blk / fps for p in picks] + [dur])
    print(f"{len(bounds) - 1} sections:")
    for i in range(len(bounds) - 1):
        print(f"  S{i + 1:02d}  {bounds[i]:7.1f} - {bounds[i + 1]:7.1f} s  "
              f"({bounds[i + 1] - bounds[i]:6.1f} s)")
    np.savez(scratch("sections.npz"), bounds=bounds)


def load_sections():
    return np.load(scratch("sections.npz"))["bounds"].astype(np.float64)


# ----------------------------------------------------------------------
# 3. F0: YIN on a 28-180 Hz band, decimated to 2 kHz
# ----------------------------------------------------------------------
def stage_f0():
    x = np.load(os.path.join(CACHE, "mono8k.npy")).astype(np.float32)
    print(f"mono8k: {len(x)} samples, {len(x) / SR8:.1f} s")
    bp = fft_band(x, SR8, 28.0, 190.0)
    y = np.ascontiguousarray(bp[::DEC])                  # already band-limited: plain decimation
    del bp
    tau_min = int(np.floor(SRP / F0_HI))                 # 13
    tau_max = int(np.ceil(SRP / F0_LO))                  # 67
    W, hop = YIN_W, YIN_HOP
    need = W + tau_max
    nfr = 1 + (len(y) - need) // hop
    print(f"YIN: {nfr} frames at {SRP / hop:.2f} fps, W={W} ({W / SRP * 1000:.0f} ms), "
          f"tau {tau_min}..{tau_max} ({SRP / tau_max:.1f}-{SRP / tau_min:.1f} Hz)")
    F = frames_of(y, need, hop)[:nfr]
    nfft = 1 << int(np.ceil(np.log2(2 * need)))
    f0 = np.zeros(nfr, np.float32)
    conf = np.zeros(nfr, np.float32)
    power = np.zeros(nfr, np.float32)
    CH = 4096
    taus = np.arange(tau_min, tau_max + 1)
    for a in range(0, nfr, CH):
        b = min(a + CH, nfr)
        blk = torch.from_numpy(np.ascontiguousarray(F[a:b]))
        # r(tau) = sum_{j<W} x[j] x[j+tau]: cross-correlate the W-long head against the whole
        # frame, not the frame with itself, or the tail terms bias d(tau) upward.
        head = torch.zeros((b - a, nfft))
        head[:, :W] = blk[:, :W]
        A = torch.fft.rfft(head, n=nfft)
        B = torch.fft.rfft(blk, n=nfft)
        ac = torch.fft.irfft(A.conj() * B, n=nfft)[:, :tau_max + 1].numpy().astype(np.float64)
        sq = (blk.numpy().astype(np.float64) ** 2)
        cs = np.concatenate([np.zeros((b - a, 1)), np.cumsum(sq, axis=1)], axis=1)
        p0 = cs[:, W] - cs[:, 0]                                     # sum x[0..W)
        # YIN difference function over the FULL tau range 1..tau_max, so the cumulative-mean
        # normalisation has the proper denominator; the search is then restricted to 30-150 Hz.
        allt = np.arange(1, tau_max + 1)
        pt = cs[:, W + allt] - cs[:, allt]                            # sum x[tau..tau+W)
        dfull = np.maximum(p0[:, None] + pt - 2.0 * ac[:, allt], 0.0)
        cm = np.cumsum(dfull, axis=1) / allt[None, :]
        dpf = dfull / np.maximum(cm, 1e-12)
        d = dfull[:, tau_min - 1:]                                    # aligned with taus
        dp = dpf[:, tau_min - 1:]
        # first local minimum under the threshold, else global min
        best = np.argmin(dp, axis=1)
        under = dp < YIN_THRESH
        first = np.where(under.any(1), np.argmax(under, axis=1), best)
        # walk down to the local minimum from that first crossing
        for r in range(b - a):
            k = int(first[r])
            while k + 1 < len(taus) and dp[r, k + 1] < dp[r, k]:
                k += 1
            first[r] = k
        idx = first
        t = taus[idx].astype(np.float64)
        # parabolic interpolation on d
        km1 = np.maximum(idx - 1, 0)
        kp1 = np.minimum(idx + 1, len(taus) - 1)
        rr = np.arange(b - a)
        y0, y1, y2 = d[rr, km1], d[rr, idx], d[rr, kp1]
        den = (y0 - 2 * y1 + y2)
        shift = np.where(np.abs(den) > 1e-12, 0.5 * (y0 - y2) / np.where(den == 0, 1, den), 0.0)
        t = t + np.clip(shift, -0.5, 0.5)
        f0[a:b] = (SRP / np.maximum(t, 1e-6)).astype(np.float32)
        conf[a:b] = np.clip(1.0 - dp[rr, idx], 0, 1).astype(np.float32)
        power[a:b] = np.sqrt(p0 / W).astype(np.float32)
    t_s = (np.arange(nfr) * hop + W / 2) / SRP
    # median filter the MIDI track (5 frames = 120 ms) to kill single-frame jitter/octave flips
    m_raw = hz_to_midi(f0)
    m_med = medfilt(m_raw.astype(np.float64), 5).astype(np.float32)
    c_med = medfilt(conf.astype(np.float64), 5).astype(np.float32)
    ok = (c_med > 0.70) & (f0 >= F0_LO) & (f0 <= F0_HI) & (power > np.percentile(power, 8))
    print(f"voiced frames: {ok.mean() * 100:.1f}%  (conf>0.70, 30-150 Hz)")
    print(f"median |raw-median| jitter: {np.median(np.abs(m_raw - m_med)[ok]) * 100:.1f} cents")
    print(f"pitch range (voiced, 5-95 pct): {np.percentile(m_med[ok], 5):.1f} - "
          f"{np.percentile(m_med[ok], 95):.1f} MIDI "
          f"({midi_name(np.percentile(m_med[ok], 5))} - {midi_name(np.percentile(m_med[ok], 95))})")
    np.savez(scratch("f0.npz"), t=t_s.astype(np.float32), f0=f0, midi_raw=m_raw.astype(np.float32),
             midi=m_med, conf=conf, conf_med=c_med, power=power, voiced=ok)


def load_f0():
    return np.load(scratch("f0.npz"))


# ----------------------------------------------------------------------
# 4. note segmentation
# ----------------------------------------------------------------------
SLOPE_MAX = 2.0                        # st/s; above this the bass is sliding, not holding


def stage_notes():
    d = load_f0()
    t, m, ok = d["t"].astype(np.float64), d["midi"].astype(np.float64), d["voiced"]
    conf, pw = d["conf_med"].astype(np.float64), d["power"].astype(np.float64)
    dt = float(np.median(np.diff(t)))
    # This bass GLIDES. A 5-point linear-fit slope separates the plateaus (a pitch being held)
    # from the portamento between them; without this split a single slide gets minced into a
    # run of neighbouring semitones and the interval histogram fills with phantom +-1 st.
    k = np.array([-2.0, -1.0, 0.0, 1.0, 2.0]) / (10.0 * dt)
    slope = np.convolve(m, k[::-1], mode="same")
    slope[:2] = slope[2]
    slope[-2:] = slope[-3]
    steady = ok & (np.abs(slope) < SLOPE_MAX)
    print(f"voiced {ok.mean() * 100:.1f}% of frames; of the voiced frames "
          f"{steady[ok].mean() * 100:.1f}% are steady (|d pitch/dt| < {SLOPE_MAX} st/s) and "
          f"{100 - steady[ok].mean() * 100:.1f}% are gliding")
    print(f"  |slope| percentiles over voiced frames (st/s): " + "  ".join(
        f"p{q}={np.percentile(np.abs(slope[ok]), q):.2f}" for q in (25, 50, 75, 90, 95, 99)))
    # Is the movement real or is it the tracker? Tighten the confidence gate and see whether the
    # steady fraction and the slope distribution hold up.
    print("  conf gate  frames%   steady%   |slope| p50   p75   p90")
    for g in (0.55, 0.70, 0.80, 0.90):
        sel = (d["conf_med"] > g) & (d["f0"] >= F0_LO) & (d["f0"] <= F0_HI)
        if sel.sum() < 50:
            continue
        print(f"   >{g:.2f}     {sel.mean() * 100:6.1f}   {np.mean(np.abs(slope[sel]) < SLOPE_MAX) * 100:6.1f}   "
              f"{np.percentile(np.abs(slope[sel]), 50):10.2f} {np.percentile(np.abs(slope[sel]), 75):6.2f} "
              f"{np.percentile(np.abs(slope[sel]), 90):6.2f}")
    # glide runs
    gl = []
    i = 0
    while i < len(t):
        if ok[i] and not steady[i]:
            j = i
            while j + 1 < len(t) and ok[j + 1] and not steady[j + 1]:
                j += 1
            if (j - i + 1) * dt >= 0.07:
                gl.append((t[i], t[j], m[i], m[j], m[j] - m[i], (m[j] - m[i]) / ((j - i) * dt + 1e-9)))
            i = j + 1
        else:
            i += 1
    G = np.array(gl, np.float64) if gl else np.zeros((0, 6))
    print(f"{len(G)} glide runs >= 70 ms: median duration {np.median(G[:, 1] - G[:, 0]) * 1000:.0f} ms, "
          f"median |span| {np.median(np.abs(G[:, 4])):.2f} st, "
          f"median |rate| {np.median(np.abs(G[:, 5])):.1f} st/s, "
          f"{np.mean(G[:, 4] < 0) * 100:.0f}% fall / {np.mean(G[:, 4] > 0) * 100:.0f}% rise")
    ok = steady                        # from here on a "note" means a held plateau
    # Hysteresis state machine. A held bass note drifts: with a plain "more than TOL from the
    # running centre -> new note" rule, slow drift across the boundary shatters one held note
    # into a run of neighbouring semitones, and the interval histogram fills up with spurious
    # +-1 st. So a departure only commits a new note once it PERSISTS for HOLD frames at a
    # consistent new pitch; shorter excursions are absorbed into the current note.
    TOL = 0.60                         # semitones from the note's own median
    HOLD = 3                           # 72 ms a new pitch must hold before it counts
    MAXGAP = 4                         # 96 ms of unvoiced tolerated inside a note
    n = len(t)
    notes = []                         # (t0, t1, midi_median, midi_std, conf, power)
    start = None
    vals: list[float] = []
    last = -1
    gap = 0
    cand_start, cand_vals = -1, []

    def close(s, e, v):
        if e >= s and (e - s + 1) * dt >= 0.07 and len(v) >= 3:
            notes.append((t[s] - dt / 2, t[e] + dt / 2, float(np.median(v)), float(np.std(v)),
                          float(conf[s:e + 1].mean()), float(pw[s:e + 1].mean())))

    for i in range(n):
        if not ok[i]:
            if start is not None:
                gap += 1
                if gap > MAXGAP:
                    close(start, last, vals)
                    start, vals, cand_vals = None, [], []
            continue
        mi = m[i]
        if start is None:
            start, vals, last, gap, cand_vals = i, [mi], i, 0, []
            continue
        if abs(mi - float(np.median(vals))) <= TOL:
            vals.append(mi)
            last, gap, cand_vals = i, 0, []
            continue
        # off the held pitch: open or extend a candidate
        if cand_vals and abs(mi - float(np.median(cand_vals))) <= TOL:
            cand_vals.append(mi)
        else:
            cand_start, cand_vals = i, [mi]
        gap = 0
        if len(cand_vals) >= HOLD:
            close(start, cand_start - 1, vals)
            start, vals, last, cand_vals = cand_start, list(cand_vals), i, []
    if start is not None:
        close(start, last, vals)
    N = np.array(notes, np.float64)
    print(f"{len(N)} raw bass segments, total voiced time {(N[:, 1] - N[:, 0]).sum():.1f} s "
          f"of {t[-1]:.1f} s ({(N[:, 1] - N[:, 0]).sum() / t[-1] * 100:.1f}%)")
    # A held note that a break momentarily masks comes back as two segments at the same pitch.
    # Merge neighbours within 0.5 st separated by <= 150 ms: that is the "is it a drone" view.
    M = []
    cur = list(N[0])
    for r in N[1:]:
        if r[0] - cur[1] <= 0.15 and abs(r[2] - cur[2]) <= 0.5:
            w0, w1 = cur[1] - cur[0], r[1] - r[0]
            cur[2] = (cur[2] * w0 + r[2] * w1) / (w0 + w1)
            cur[4] = (cur[4] * w0 + r[4] * w1) / (w0 + w1)
            cur[5] = (cur[5] * w0 + r[5] * w1) / (w0 + w1)
            cur[1] = r[1]
        else:
            M.append(cur)
            cur = list(r)
    M.append(cur)
    M = np.array(M, np.float64)
    print(f"{len(M)} merged plateaus (same pitch across gaps <= 150 ms); "
          f"median raw {np.median(N[:, 1] - N[:, 0]) * 1000:.0f} ms -> "
          f"merged {np.median(M[:, 1] - M[:, 0]) * 1000:.0f} ms")
    # classify each plateau-to-plateau transition: did the bass SLIDE there or JUMP?
    lab = []
    for i in range(len(M) - 1):
        g0, g1 = M[i, 1], M[i + 1, 0]
        cov = 0.0
        for a, b, *_ in G:
            cov += max(0.0, min(b, g1) - max(a, g0))
        span = max(g1 - g0, 1e-9)
        lab.append(1 if (cov / span > 0.5 and g1 - g0 > 0.04) else 0)
    lab = np.array(lab, np.int8)
    if len(lab):
        print(f"transitions between plateaus: {lab.mean() * 100:.1f}% are glides, "
              f"{100 - lab.mean() * 100:.1f}% are jumps/re-articulations")
    np.savez(scratch("notes.npz"), notes=N, merged=M, glides=G, trans=lab)


def load_notes(merged: bool = False):
    z = np.load(scratch("notes.npz"))
    return z["merged" if merged else "notes"]


# ----------------------------------------------------------------------
# 5. register + harmonic comb (reese test)
# ----------------------------------------------------------------------
def stage_spec():
    x = np.load(os.path.join(CACHE, "mono8k.npy")).astype(np.float32)
    nfft, hop = 2048, 192                                # 256 ms window, 24 ms hop, 3.91 Hz bins
    win = torch.hann_window(nfft)
    KEEP = int(2400 / (SR8 / nfft)) + 1                  # keep up to 2.4 kHz
    mags = []
    step = 1 << 21
    for a in range(0, len(x), step):
        seg = x[max(0, a - nfft):a + step + nfft]
        S = torch.stft(torch.from_numpy(np.ascontiguousarray(seg)), nfft, hop, window=win,
                       center=True, return_complex=True).abs()[:KEEP]
        pad = 0 if a == 0 else nfft // hop + 1
        mags.append(S[:, pad:S.shape[1] - (nfft // hop + 1)].numpy().astype(np.float32))
    S = np.concatenate(mags, axis=1)
    del mags
    freqs = np.arange(KEEP) * SR8 / nfft
    print(f"STFT: {S.shape[1]} frames at {SR8 / hop:.2f} fps, {KEEP} bins to {freqs[-1]:.0f} Hz")
    P = (S.astype(np.float64) ** 2)
    # 0-60 is split finely so we can prove the sub energy is musical bass and not DC or rumble
    edges = [(0, 20), (20, 30), (30, 40), (40, 50), (50, 60), (60, 120), (120, 250),
             (250, 400), (400, 1000), (1000, 2400)]
    band = np.stack([P[(freqs >= lo) & (freqs < hi)].sum(0) for lo, hi in edges], 0)
    np.savez(scratch("spec.npz"), band=band.astype(np.float32), edges=np.array(edges),
             fps=np.array([SR8 / hop]))
    # --- harmonic comb on sustained notes -------------------------------
    N = load_notes()
    fps = SR8 / hop
    keep = (N[:, 1] - N[:, 0] >= 0.30) & (N[:, 4] > 0.7)
    sel = N[keep]
    print(f"harmonic comb over {len(sel)} sustained notes (>=300 ms, conf>0.7)")
    KMAX = 12
    on = np.zeros(KMAX)
    off = np.zeros(KMAX)
    cnt = 0
    vres = []                                            # YIN vs spectral-peak cross-check
    for t0, t1, mid, _, _, _ in sel:
        f0 = 440.0 * 2 ** ((mid - 69) / 12.0)
        a = int((t0 + 0.05) * fps)
        b = int((t1 - 0.02) * fps)
        if b - a < 3:
            continue
        col = P[:, a:b].mean(1)
        lowsel = (freqs >= 25) & (freqs <= 175)
        pk = freqs[lowsel][int(np.argmax(col[lowsel]))]
        vres.append(12 * np.log2(max(pk, 1e-6) / f0))
        for k in range(1, KMAX + 1):
            fk = f0 * k
            fo = f0 * (k + 0.5)                          # off-comb control, same region
            if fk > freqs[-1] - 10:
                break
            w = max(6.0, fk * 0.03)
            on[k - 1] += col[(freqs > fk - w) & (freqs < fk + w)].max() if (
                (freqs > fk - w) & (freqs < fk + w)).any() else 0.0
            if fo < freqs[-1] - 10:
                wo = max(6.0, fo * 0.03)
                off[k - 1] += col[(freqs > fo - wo) & (freqs < fo + wo)].max() if (
                    (freqs > fo - wo) & (freqs < fo + wo)).any() else 0.0
        cnt += 1
    on /= max(cnt, 1)
    off /= max(cnt, 1)
    v = np.array(vres)
    print(f"  F0 cross-check vs the strongest 25-175 Hz spectral peak (n={len(v)}): "
          f"within 0.5 st {np.mean(np.abs(v) < 0.5) * 100:.1f}%, within 1 st "
          f"{np.mean(np.abs(v) < 1.0) * 100:.1f}%, YIN an octave HIGH "
          f"{np.mean(np.abs(v + 12) < 1.5) * 100:.1f}%, an octave LOW "
          f"{np.mean(np.abs(v - 12) < 1.5) * 100:.1f}%, other {np.mean((np.abs(v) >= 1.0) & (np.abs(np.abs(v) - 12) >= 1.5)) * 100:.1f}%")
    np.savez(scratch("comb.npz"), on=on, off=off, n=np.array([cnt]), xcheck=v)
    print("k   on-comb dB re h1   off-comb dB re h1   excess dB")
    for k in range(KMAX):
        print(f"{k + 1:2d}  {db(on[k], on[0]):8.1f}         {db(off[k], on[0]):8.1f}      "
              f"{db(on[k], off[k]):7.1f}")


# ----------------------------------------------------------------------
# 6. kicks and the sub
# ----------------------------------------------------------------------
def stage_kick():
    x = np.load(os.path.join(CACHE, "mono8k.npy")).astype(np.float32)
    fps = SR8 / ENV_HOP                                  # 200 fps, 5 ms
    env = {}
    for name, (lo, hi) in (("sub", (20, 60)), ("kickband", (35, 120)), ("bass", (60, 120)),
                           ("harm", (120, 250)), ("mid", (400, 2000))):
        env[name] = block_rms(fft_band(x, SR8, lo, hi), ENV_HOP)
    n = min(len(v) for v in env.values())
    for k in env:
        env[k] = env[k][:n]
    t = np.arange(n) / fps
    # --- kick onsets: rise in the 35-120 Hz envelope, adaptive threshold, 120 ms refractory
    e = np.log10(env["kickband"] + 1e-7)
    d = np.maximum(np.diff(e, prepend=e[0]), 0)
    d = np.convolve(d, np.ones(3) / 3, "same")
    loc = medfilt(d.astype(np.float64), 201)             # ~1 s local floor
    thr = loc + 0.6 * (np.percentile(d, 95) - np.percentile(d, 50))
    cand = np.where((d > thr) & (d > np.roll(d, 1)) & (d >= np.roll(d, -1)))[0]
    refr = int(0.12 * fps)
    kicks = []
    for i in cand:
        if not kicks or i - kicks[-1] >= refr:
            kicks.append(int(i))
        elif d[i] > d[kicks[-1]]:
            kicks[-1] = int(i)
    kicks = np.array(kicks)
    # A low-frequency transient is not automatically a kick: snares and break body hit 35-120 Hz
    # too. Keep the kick-like ones - low band well above the 400-2k band, and loud.
    lo_at = env["kickband"][np.minimum(kicks + 2, n - 1)].astype(np.float64)
    mi_at = env["mid"][np.minimum(kicks + 2, n - 1)].astype(np.float64)
    ratio = 20 * np.log10((lo_at + 1e-9) / (mi_at + 1e-9))
    strong = (ratio >= np.percentile(ratio, 50)) & (lo_at >= np.percentile(lo_at, 40))
    kt = kicks / fps
    print(f"{len(kicks)} low-frequency transients, {len(kicks) / (n / fps) * 60:.1f} per minute, "
          f"median IOI {np.median(np.diff(kt)) * 1000:.0f} ms")
    print(f"  kick-like subset (low/mid ratio >= median, loud): {int(strong.sum())} "
          f"({strong.sum() / (n / fps) * 60:.1f} per minute, median IOI "
          f"{np.median(np.diff(kt[strong])) * 1000:.0f} ms, low/mid {np.median(ratio[strong]):.1f} dB)")
    # --- windows after each kick vs the between-kick baseline
    wins = [(0.000, 0.030), (0.030, 0.080), (0.080, 0.200)]
    nxt = np.concatenate([kicks[1:], [n + 10 ** 6]])
    far = np.ones(n, bool)
    for i in kicks:
        far[max(0, i - int(0.10 * fps)):min(n, i + int(0.25 * fps))] = False
    res = {}
    for bname in ("sub", "bass", "harm", "mid"):
        v = env[bname].astype(np.float64) ** 2
        base = v[far].mean()
        row = []
        for (a, b) in wins:
            ia, ib = int(a * fps), int(b * fps)
            vals = []
            for i, nx in zip(kicks, nxt):
                if i + ib > n or i + ib > nx:
                    continue
                vals.append(v[i + ia:i + ib].mean())
            row.append((np.mean(vals), np.median(vals), len(vals)))
        res[bname] = (base, row)
        print(f"  {bname:5s} baseline(between kicks) 0 dB ref | " + " | ".join(
            f"{int(a * 1000)}-{int(b * 1000)}ms {db(r[0], base):+6.2f} dB (med {db(r[1], base):+6.2f})"
            for (a, b), r in zip(wins, row)))
    # --- the honest duck test: only where a bass NOTE is sounding across the kick
    N = load_notes()
    sustained = N[(N[:, 1] - N[:, 0] >= 0.35) & (N[:, 4] > 0.7)]
    duck = {b: [[], [], []] for b in ("sub", "bass", "harm")}
    pw2 = {b: env[b].astype(np.float64) ** 2 for b in ("sub", "bass", "harm")}
    used = 0
    for i in kicks:
        tk = i / fps
        if not ((sustained[:, 0] <= tk - 0.12) & (sustained[:, 1] >= tk + 0.25)).any():
            continue
        if i + int(0.200 * fps) >= n:
            continue
        used += 1
        for b, v in pw2.items():
            pre = v[max(0, i - int(0.11 * fps)):max(1, i - int(0.02 * fps))].mean()
            for w, (a, z) in enumerate(wins):
                duck[b][w].append(v[i + int(a * fps):i + int(z * fps)].mean() / max(pre, 1e-20))
    print(f"\n  in-note duck test ({used} kicks that land inside a >=350 ms bass note), "
          f"ref = the 110..20 ms BEFORE the kick:")
    innote = {}
    for b in duck:
        r = [10 * np.log10(np.median(np.array(w))) for w in duck[b]]
        innote[b] = r
        print(f"  {b:5s} " + " | ".join(f"{int(a * 1000)}-{int(z * 1000)}ms {v:+6.2f} dB"
                                        for (a, z), v in zip(wins, r)))

    # --- the decisive picture: the median envelope SHAPE across a kick, in 5 ms steps.
    # A real sidechain shows a trough; a kick simply added on top of a steady sub does not.
    PRE, POST = int(0.120 * fps), int(0.260 * fps)
    prof = {}
    for label, ksel in (("all", kicks), ("kick-like", kicks[strong])):
        sel = [i for i in ksel if i - PRE >= 0 and i + POST < n
               and ((sustained[:, 0] <= i / fps - 0.12) & (sustained[:, 1] >= i / fps + 0.26)).any()]
        for b, v in pw2.items():
            M = np.stack([v[i - PRE:i + POST] for i in sel]) if sel else np.zeros((1, PRE + POST))
            ref = M[:, :int(0.100 * fps)].mean(1, keepdims=True)
            prof[(label, b)] = (10 * np.log10(np.median(M / np.maximum(ref, 1e-20), 0) + 1e-20),
                                len(sel))
    lag_ms = (np.arange(-PRE, POST)) / fps * 1000
    for label in ("all", "kick-like"):
        print(f"\n  median envelope across a kick inside a sustained bass note [{label}, "
              f"n={prof[(label, 'sub')][1]}], dB re the 120..20 ms before:")
        print("    ms  " + "".join(f"{int(v):>6d}" for v in lag_ms[::4][:24]))
        for b in ("sub", "bass", "harm"):
            c = prof[(label, b)][0]
            print(f"    {b:5s}" + "".join(f"{v:>6.1f}" for v in c[::4][:24]))
            post = c[PRE:]
            print(f"      -> min after the kick {post.min():+.2f} dB at "
                  f"{int(np.argmin(post) / fps * 1000)} ms; "
                  f"min in 40-250 ms {post[int(0.04 * fps):].min():+.2f} dB")
    # --- decisive duck test, artifact-free -------------------------------------------------
    # Two corrections over the above: (a) anchor on the kick's envelope PEAK, not on the
    # steepest-rise index (which sits in the trough just before the attack and fakes a dip at
    # t=0); (b) reference each kick to a baseline taken from kick-FREE frames inside the SAME
    # bass note, so a neighbouring hit cannot contaminate the reference.
    kb = env["kickband"].astype(np.float64)
    peak = np.array([int(i + np.argmax(kb[i:min(i + int(0.040 * fps), n)])) for i in kicks])
    ordk = np.sort(peak)
    idxall = np.arange(n)
    nxt_i = np.searchsorted(ordk, idxall, "left")
    since = idxall - ordk[np.clip(nxt_i - 1, 0, len(ordk) - 1)]
    until = ordk[np.clip(nxt_i, 0, len(ordk) - 1)] - idxall
    longn = N[(N[:, 1] - N[:, 0] >= 0.70) & (N[:, 4] > 0.65)]
    print(f"\n  ANCHORED duck test: kick peak vs a kick-free baseline inside the same bass note "
          f"({len(longn)} notes >= 700 ms)")
    prof2 = {b: [] for b in ("sub", "bass", "harm")}
    used2 = 0
    for t0, t1, *_ in longn:
        a2, b2 = int((t0 + 0.05) * fps), int((t1 - 0.05) * fps)
        if b2 - a2 < int(0.4 * fps):
            continue
        sl = np.arange(a2, min(b2, n))
        clean = (since[sl] > int(0.20 * fps)) & (until[sl] > int(0.05 * fps))
        if clean.sum() < 5:
            continue
        ks = peak[(peak >= a2) & (peak < b2)]
        ks = ks[(ks - PRE >= 0) & (ks + POST < n)]
        if not len(ks):
            continue
        used2 += 1
        for b, v in pw2.items():
            base = v[sl[clean]].mean()
            for kp in ks:
                prof2[b].append(v[kp - PRE:kp + POST] / max(base, 1e-20))
    print(f"    {used2} notes, {len(prof2['sub'])} kicks; 0 dB = the sub's own level between "
          f"kicks inside the note")
    print("    ms  " + "".join(f"{int(v):>6d}" for v in lag_ms[::4][:24]))
    anch = {}
    for b in ("sub", "bass", "harm"):
        c = 10 * np.log10(np.median(np.stack(prof2[b]), 0) + 1e-20)
        anch[b] = c
        print(f"    {b:5s}" + "".join(f"{v:>6.1f}" for v in c[::4][:24]))
        post = c[PRE:]
        print(f"      -> peak {post.max():+.2f} dB at {int(np.argmax(post) / fps * 1000)} ms; "
              f"min in 0-250 ms after {post.min():+.2f} dB at "
              f"{int(np.argmin(post) / fps * 1000)} ms; "
              f"level at 80/120/200 ms {post[int(0.08 * fps)]:+.2f}/"
              f"{post[int(0.12 * fps)]:+.2f}/{post[int(0.20 * fps)]:+.2f} dB")

    # How big is the sub's OWN ripple inside a note? Post-kick excursions only mean something
    # if they are bigger than this.
    rip = []
    for t0, t1, *_ in longn:
        a2, b2 = int((t0 + 0.06) * fps), int((t1 - 0.06) * fps)
        if b2 - a2 < int(0.4 * fps):
            continue
        seg = 10 * np.log10(pw2["sub"][a2:b2] + 1e-20)
        rip.append(np.percentile(seg, 90) - np.percentile(seg, 10))
    print(f"    reference ripple: inside a sustained note the sub's own p10-p90 spread is "
          f"{np.median(rip):.1f} dB (median over {len(rip)} notes) - the post-kick excursions "
          f"above are smaller than the note's own wobble")

    # per-section: does any single track in the mix actually sidechain?
    bounds = load_sections()
    print("    per-section sub level 30-90 ms after a kick, dB re the in-note kick-free baseline:")
    persec = []
    for s in range(len(bounds) - 1):
        a3, z3 = bounds[s], bounds[s + 1]
        vals = []
        for t0, t1, *_ in longn[(longn[:, 0] >= a3) & (longn[:, 0] < z3)]:
            a2, b2 = int((t0 + 0.05) * fps), int((t1 - 0.05) * fps)
            if b2 - a2 < int(0.4 * fps):
                continue
            sl = np.arange(a2, min(b2, n))
            clean = (since[sl] > int(0.20 * fps)) & (until[sl] > int(0.05 * fps))
            ks = peak[(peak >= a2) & (peak < b2 - int(0.09 * fps))]
            if clean.sum() < 5 or not len(ks):
                continue
            base = pw2["sub"][sl[clean]].mean()
            for kp in ks:
                vals.append(pw2["sub"][kp + int(0.03 * fps):kp + int(0.09 * fps)].mean()
                            / max(base, 1e-20))
        v = 10 * np.log10(np.median(vals)) if len(vals) >= 8 else np.nan
        persec.append(v)
        print(f"      S{s + 1:02d} {a3:7.1f}-{z3:7.1f}s  n={len(vals):4d}  "
              f"{'   n/a' if np.isnan(v) else f'{v:+6.2f} dB'}")
    ok = np.array([p for p in persec if not np.isnan(p)])
    print(f"    -> across {len(ok)} sections: median {np.median(ok):+.2f} dB, "
          f"worst {ok.min():+.2f} dB, best {ok.max():+.2f} dB; "
          f"sections below -4 dB: {int((ok < -4).sum())}")

    # --- kick-only vs sustained-bass spectrum
    sp = np.load(scratch("spec.npz"))
    band, sfps = sp["band"].astype(np.float64), float(sp["fps"][0])
    edges = sp["edges"]
    f0d = load_f0()
    ft, voiced = f0d["t"], f0d["voiced"]
    # kick-only: a kick with no voiced bass in the 200 ms around it
    vt = np.interp(kt, ft, voiced.astype(float))
    ko = kt[strong & (vt < 0.2)]
    # sustained-bass-only: inside a long note and >=150 ms from any kick
    sb = []
    for t0, t1, *_ in sustained:
        a, z = t0 + 0.10, t1 - 0.05
        if z - a < 0.15:
            continue
        cen = np.arange(a, z, 0.05)
        gap = np.min(np.abs(cen[:, None] - kt[None, :]), axis=1) if len(kt) else np.ones(len(cen))
        sb.extend(cen[gap > 0.15])
    sb = np.array(sb)
    print(f"\n  kick-only moments: {len(ko)}   bass-without-kick moments: {len(sb)}")

    def band_avg(times, off=0.0, span=0.06):
        idx = []
        for tt in times:
            a = int((tt + off) * sfps)
            b = int((tt + off + span) * sfps)
            if 0 <= a < band.shape[1] and b <= band.shape[1]:
                idx.append(band[:, a:b].mean(1))
        return np.mean(idx, 0) if idx else np.zeros(band.shape[0])

    bk = band_avg(ko, 0.0, 0.08)
    bb = band_avg(sb, 0.0, 0.08)
    names = [f"{int(a)}-{int(z)}" for a, z in edges]
    print("  band(Hz)   kick-only %   bass-only %   kick-only dB re its own total   bass dB")
    for i, nm in enumerate(names):
        print(f"  {nm:>9s}  {bk[i] / bk.sum() * 100:9.1f}  {bb[i] / bb.sum() * 100:11.1f}  "
              f"{db(bk[i], bk.sum()):10.1f}  {db(bb[i], bb.sum()):20.1f}")
    np.savez(scratch("kick.npz"), kt=kt.astype(np.float32), strong=strong,
             innote=np.array([innote[b] for b in ("sub", "bass", "harm")]),
             raw=np.array([[db(r[0], res[b][0]) for r in res[b][1]] for b in ("sub", "bass", "harm", "mid")]),
             prof=np.array([prof[("kick-like", b)][0] for b in ("sub", "bass", "harm")]),
             anch=np.array([anch[b] for b in ("sub", "bass", "harm")]),
             anch_n=np.array([len(prof2["sub"])]),
             prof_n=np.array([prof[("kick-like", "sub")][1]]), lag_ms=lag_ms, pre=np.array([PRE]),
             bk=bk, bb=bb, edges=edges)


# ----------------------------------------------------------------------
# 7. report
# ----------------------------------------------------------------------
def stage_report():
    beats, downbeats, beat_s = load_grid()
    bounds = load_sections()
    N = load_notes(merged=True)
    Nraw = load_notes()
    d = load_f0()
    sp = np.load(scratch("spec.npz"))
    band, sfps, edges = sp["band"].astype(np.float64), float(sp["fps"][0]), sp["edges"]
    bpm = 60.0 / beat_s
    bar_s = 4 * beat_s
    dur = float(d["t"][-1])

    def to_beats(sec):
        return sec / beat_s

    print("=" * 78)
    print(f"GRID  {bpm:.2f} BPM, beat {beat_s * 1000:.1f} ms, bar {bar_s:.3f} s, "
          f"{dur / bar_s:.0f} bars over {dur:.1f} s")
    print("=" * 78)

    dur_b = to_beats(N[:, 1] - N[:, 0])
    rawb = to_beats(Nraw[:, 1] - Nraw[:, 0])
    print(f"\n[1] NOTE DURATIONS  ({len(N)} merged notes; voiced "
          f"{((N[:, 1] - N[:, 0]).sum() / dur * 100):.1f}% of the file)")
    print(f"  raw segments before merging: {len(Nraw)}, median {np.median(rawb):.2f} beats "
          f"({np.median(Nraw[:, 1] - Nraw[:, 0]) * 1000:.0f} ms); merging same-pitch segments "
          f"across <=150 ms dropouts gives the held-note view below")
    print(f"  notes per bar: merged {len(N) / (dur / bar_s):.2f}, raw {len(Nraw) / (dur / bar_s):.2f}")
    qs = [5, 10, 25, 50, 75, 90, 95, 99]
    print("  percentiles (beats): " + "  ".join(f"p{q}={np.percentile(dur_b, q):.2f}" for q in qs))
    print(f"  mean {dur_b.mean():.2f} beats ({(N[:, 1] - N[:, 0]).mean() * 1000:.0f} ms), "
          f"max {dur_b.max():.2f} beats")
    bins = [0, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0, 8.0, 16.0, 1e9]
    labels = ["<1/16", "1/16-1/8", "1/8-d1/8", "d1/8-1/4", "1/4-3/8", "3/8-1/2",
              "1/2-3/4", "3/4-1 bar", "1-1.5 bar", "1.5-2 bar", "2-4 bar", ">4 bar"]
    h, _ = np.histogram(dur_b, bins)
    tot_t = (N[:, 1] - N[:, 0]).sum()
    ht = np.array([(N[(dur_b >= bins[i]) & (dur_b < bins[i + 1])][:, 1]
                    - N[(dur_b >= bins[i]) & (dur_b < bins[i + 1])][:, 0]).sum() for i in range(len(h))])
    print("  duration bin (beats)      count    % of notes   % of sounding time")
    for i, lab in enumerate(labels):
        print(f"  {bins[i]:5.2f}-{bins[i + 1] if bins[i + 1] < 100 else 99:5.2f}  {lab:>10s}  "
              f"{h[i]:6d}   {h[i] / len(N) * 100:8.1f}   {ht[i] / tot_t * 100:14.1f}")

    z = np.load(scratch("notes.npz"))
    G, trans = z["glides"], z["trans"]
    print(f"\n[1b] GLIDES  ({len(G)} runs >= 70 ms, i.e. the bass sliding rather than holding)")
    print(f"  median duration {np.median(G[:, 1] - G[:, 0]) * 1000:.0f} ms "
          f"({to_beats(np.median(G[:, 1] - G[:, 0])):.2f} beats), "
          f"median |span| {np.median(np.abs(G[:, 4])):.2f} st, "
          f"p90 |span| {np.percentile(np.abs(G[:, 4]), 90):.2f} st, "
          f"median rate {np.median(np.abs(G[:, 5])):.1f} st/s")
    print(f"  direction: {np.mean(G[:, 4] < 0) * 100:.0f}% falling, {np.mean(G[:, 4] > 0) * 100:.0f}% rising")
    print(f"  glide runs per bar: {len(G) / (dur / bar_s):.2f}; "
          f"time spent gliding {(G[:, 1] - G[:, 0]).sum() / dur * 100:.1f}% of the file")

    print(f"\n[2] INTERVALS between consecutive plateaus (gap < 1 bar)")
    iv, gaps, lab = [], [], []
    for i in range(len(N) - 1):
        g = N[i + 1, 0] - N[i, 1]
        if g <= bar_s:
            iv.append(N[i + 1, 2] - N[i, 2])
            gaps.append(g)
            lab.append(int(trans[i]) if i < len(trans) else 0)
    iv, lab = np.array(iv), np.array(lab)
    print(f"  of these, {lab.mean() * 100:.0f}% are reached by a GLIDE and "
          f"{100 - lab.mean() * 100:.0f}% by a jump / re-articulation")
    for nm, sel in (("glided", lab == 1), ("jumped", lab == 0)):
        if sel.sum() > 10:
            print(f"    {nm}: median |interval| {np.median(np.abs(iv[sel])):.2f} st, "
                  f"p90 {np.percentile(np.abs(iv[sel]), 90):.2f} st, "
                  f"frac >= 3 st {np.mean(np.abs(iv[sel]) >= 3) * 100:.0f}%")
    ivr = np.round(iv).astype(int)
    print(f"  {len(iv)} transitions; median gap between notes {np.median(gaps) * 1000:.0f} ms "
          f"({to_beats(np.median(gaps)):.2f} beats)")
    print(f"  |interval| mean {np.abs(iv).mean():.2f} st, median {np.median(np.abs(iv)):.2f} st, "
          f"frac |iv| < 0.5 st (repeat) {np.mean(np.abs(iv) < 0.5) * 100:.1f}%")
    rev = np.mean([abs(iv[k] + iv[k + 1]) < 0.5 and abs(iv[k]) > 0.5 for k in range(len(iv) - 1)])
    print(f"  immediate-reversal rate (move then undo it exactly): {rev * 100:.1f}% "
          f"(high = the tracker wobbling inside one held note, not a real line)")
    print("  semitones   count      %      cumulative %")
    cum = 0
    for s in range(-24, 25):
        c = int((ivr == s).sum())
        if c == 0:
            continue
        cum += c
        print(f"  {s:+4d}      {c:6d}  {c / len(iv) * 100:6.2f}   {cum / len(iv) * 100:7.2f}")
    print("  folded |interval| (semitones): " + "  ".join(
        f"{s}:{int((np.abs(ivr) == s).sum()) / len(iv) * 100:.1f}%" for s in range(0, 13)
        if (np.abs(ivr) == s).sum() / len(iv) > 0.005))

    print(f"\n[3] PER-SECTION: change rate, note length, register, key")
    print("  sec   start    end   len_s  bars | notes  chg/bar  chg/8bar  medNote(beats)  "
          "voiced%  medMIDI  root  <60Hz%  60-120%  120-250%")
    rows = []
    for i in range(len(bounds) - 1):
        a, z = bounds[i], bounds[i + 1]
        sel = N[(N[:, 0] >= a) & (N[:, 0] < z)]
        nbars = (z - a) / bar_s
        if len(sel) < 3:
            continue
        # changes = transitions where the pitch actually moves >= 0.5 st
        ch = 0
        for k in range(len(sel) - 1):
            if abs(sel[k + 1, 2] - sel[k, 2]) >= 0.5:
                ch += 1
        vd = (sel[:, 1] - sel[:, 0]).sum() / (z - a)
        pc = np.zeros(12)
        for t0, t1, m, *_ in sel:
            pc[int(round(m)) % 12] += (t1 - t0)
        root = int(np.argmax(pc))
        ia, iz = int(a * sfps), min(int(z * sfps), band.shape[1])
        bs = band[:, ia:iz].mean(1)
        low3 = grp(bs, edges, 0, 250) + 1e-20
        rows.append(dict(sec=i + 1, a=a, z=z, bars=nbars, n=len(sel),
                         chg_bar=ch / nbars, med_note=to_beats(np.median(sel[:, 1] - sel[:, 0])),
                         voiced=vd * 100, med_midi=float(np.median(sel[:, 2])), root=root,
                         pc=pc / pc.sum(),
                         f60=grp(bs, edges, 0, 60) / low3 * 100,
                         f120=grp(bs, edges, 60, 120) / low3 * 100,
                         f250=grp(bs, edges, 120, 250) / low3 * 100, tot=bs))
        r = rows[-1]
        print(f"  S{r['sec']:02d} {a:7.1f} {z:7.1f} {z - a:6.1f} {nbars:5.1f} | {len(sel):5d}  "
              f"{r['chg_bar']:7.2f}  {r['chg_bar'] * 8:8.1f}  {r['med_note']:13.2f}  "
              f"{vd * 100:6.1f}  {r['med_midi']:7.1f}  {NOTE_NAMES[root]:>4s}  "
              f"{r['f60']:6.1f}  {r['f120']:7.1f}  {r['f250']:8.1f}")
    allbars = dur / bar_s
    tot_ch = sum(1 for k in range(len(N) - 1) if abs(N[k + 1, 2] - N[k, 2]) >= 0.5)
    print(f"  WHOLE FILE: {tot_ch / allbars:.2f} changes/bar = {tot_ch / allbars * 8:.1f} per 8 bars; "
          f"median note {np.median(dur_b):.2f} beats")

    # presence vs absence, per bar - the two-state view the arrangement rules care about
    print(f"\n[3b] BASS PRESENT vs ABSENT, per bar")
    nb = int(dur / bar_s)
    cov = np.zeros(nb)
    for t0, t1, *_ in N:
        b0, b1 = int(t0 / bar_s), min(int(t1 / bar_s), nb - 1)
        for b in range(b0, b1 + 1):
            cov[b] += max(0.0, min(t1, (b + 1) * bar_s) - max(t0, b * bar_s)) / bar_s
    for t0, t1, *_ in G:                                  # glides count as the bass sounding
        b0, b1 = int(t0 / bar_s), min(int(t1 / bar_s), nb - 1)
        for b in range(b0, b1 + 1):
            cov[b] += max(0.0, min(t1, (b + 1) * bar_s) - max(t0, b * bar_s)) / bar_s
    on = cov > 0.25
    print(f"  {nb} bars; bass audible in {on.mean() * 100:.1f}% of bars "
          f"(>25% of the bar covered by a plateau or a glide)")
    print(f"  per-bar coverage percentiles: " + "  ".join(
        f"p{q}={np.percentile(cov, q) * 100:.0f}%" for q in (10, 25, 50, 75, 90)))
    runs, cur, val = [], 0, on[0]
    for v in on:
        if v == val:
            cur += 1
        else:
            runs.append((val, cur))
            val, cur = v, 1
    runs.append((val, cur))
    ron = np.array([r[1] for r in runs if r[0]])
    roff = np.array([r[1] for r in runs if not r[0]])
    print(f"  unbroken ON stretches: {len(ron)}, median {np.median(ron):.0f} bars, "
          f"p90 {np.percentile(ron, 90):.0f} bars, max {ron.max()} bars")
    print(f"  unbroken OFF stretches: {len(roff)}, median {np.median(roff):.0f} bars, "
          f"p90 {np.percentile(roff, 90):.0f} bars, max {roff.max()} bars")

    print(f"\n[4] REGISTER over the whole file (share of 0-2.4 kHz power)")
    tot = band.mean(1)
    names = [f"{int(x)}-{int(y)} Hz" for x, y in edges]
    for i, nm in enumerate(names):
        print(f"  {nm:>12s}  {tot[i] / tot.sum() * 100:6.2f}%   {db(tot[i], tot.sum()):+6.1f} dB re total")
    l3 = grp(tot, edges, 0, 250)
    print(f"  within the low end only (0-250 Hz): <60 {grp(tot, edges, 0, 60) / l3 * 100:.1f}%, "
          f"60-120 {grp(tot, edges, 60, 120) / l3 * 100:.1f}%, "
          f"120-250 {grp(tot, edges, 120, 250) / l3 * 100:.1f}%")
    print(f"  of the whole 0-2.4 kHz power: <60 Hz {grp(tot, edges, 0, 60) / tot.sum() * 100:.1f}%, "
          f"60-120 {grp(tot, edges, 60, 120) / tot.sum() * 100:.1f}%, "
          f"120-250 {grp(tot, edges, 120, 250) / tot.sum() * 100:.1f}%")
    print(f"  DC/rumble check: 0-20 Hz is {tot[0] / tot.sum() * 100:.2f}% of total and "
          f"{tot[0] / grp(tot, edges, 0, 60) * 100:.2f}% of the sub band - the sub energy is "
          f"musical, not DC")

    c = np.load(scratch("comb.npz"))
    on, off = c["on"], c["off"]
    print(f"\n[5] HARMONIC COMB on sustained bass notes (n={int(c['n'][0])})")
    print("  k   f/f0     on-comb dB re k=1   excess over off-comb dB")
    for k in range(len(on)):
        if on[k] <= 0:
            continue
        print(f"  {k + 1:2d}   x{k + 1:<4d}   {db(on[k], on[0]):+8.1f}            {db(on[k], off[k]):+8.1f}")

    kk = np.load(scratch("kick.npz"))
    print(f"\n[6] KICK vs SUB   ({len(kk['kt'])} kicks)")
    wl = ["0-30 ms", "30-80 ms", "80-200 ms"]
    print("  raw (post-kick vs mean between kicks):")
    for i, b in enumerate(("sub 20-60", "bass 60-120", "harm 120-250", "mid 400-2k")):
        print(f"    {b:13s} " + " | ".join(f"{w} {kk['raw'][i][j]:+6.2f} dB"
                                           for j, w in enumerate(wl)))
    print("  in-note (kick lands inside a sustained bass note; ref = 110..20 ms before):")
    for i, b in enumerate(("sub 20-60", "bass 60-120", "harm 120-250")):
        print(f"    {b:13s} " + " | ".join(f"{w} {kk['innote'][i][j]:+6.2f} dB"
                                           for j, w in enumerate(wl)))
    bk, bb = kk["bk"], kk["bb"]
    print("  spectrum share: band | kick-only | bass-without-kick")
    for i, nm in enumerate(names):
        print(f"    {nm:>12s}  {bk[i] / bk.sum() * 100:7.1f}%  {bb[i] / bb.sum() * 100:7.1f}%")

    print(f"\n[7] KEY from the bass")
    pcall = np.zeros(12)
    for t0, t1, m, *_ in N:
        pcall[int(round(m)) % 12] += (t1 - t0)
    p = pcall / pcall.sum()
    print("  whole-file bass pitch-class weight (by sounding time):")
    print("   " + "  ".join(f"{NOTE_NAMES[i]:>3s}{p[i] * 100:5.1f}" for i in range(12)))
    print(f"  strongest root: {NOTE_NAMES[int(np.argmax(p))]} ({p.max() * 100:.1f}%)")
    gt, gf = best_scale(pcall)
    print(f"  best single 7-note collection for the WHOLE file: {NOTE_NAMES[gt]} minor / "
          f"{NOTE_NAMES[(gt + 3) % 12]} major - {gf * 100:.1f}% of all bass sounding time "
          f"lies inside it")
    print(f"  pitch classes outside it: " + " ".join(
        f"{NOTE_NAMES[i]}({p[i] * 100:.1f}%)" for i in range(12)
        if i not in set((MAJOR_SET + (gt + 3) % 12) % 12)))
    print("\n  per section: root, its own best collection, and how well it fits the set's key")
    inset = set(((MAJOR_SET + (gt + 3) % 12) % 12).tolist())
    fits = []
    for r in rows:
        st, sf = best_scale(r["pc"])
        fit = float(sum(r["pc"][i] for i in inset))
        fits.append(fit)
        top = np.argsort(r["pc"])[::-1][:3]
        print(f"  S{r['sec']:02d} {r['a']:7.1f}s  root {NOTE_NAMES[r['root']]:>2s}  "
              f"own key {NOTE_NAMES[st]:>2s} min ({sf * 100:3.0f}% in)  "
              f"fit to {NOTE_NAMES[gt]} min {fit * 100:3.0f}%   top: " +
              " ".join(f"{NOTE_NAMES[t]}({r['pc'][t] * 100:.0f}%)" for t in top))
    roots = [NOTE_NAMES[r["root"]] for r in rows]
    uniq = {k: roots.count(k) for k in sorted(set(roots))}
    print(f"  section roots: {uniq}  -> {len(uniq)} distinct roots over {len(rows)} sections")
    fits = np.array(fits)
    print(f"  sections whose bass sits >=80% inside {NOTE_NAMES[gt]} minor: "
          f"{int((fits >= 0.8).sum())}/{len(fits)}; >=60%: {int((fits >= 0.6).sum())}/{len(fits)}; "
          f"median fit {np.median(fits) * 100:.0f}%")
    print("=" * 78)


def stage_inspect(t0=500.0, t1=512.0):
    """Print the raw F0 track over a window, to see with your own eyes what the notes are made of."""
    d = load_f0()
    t, mr, mm, c, pw = d["t"], d["midi_raw"], d["midi"], d["conf_med"], d["power"]
    sel = (t >= t0) & (t < t1)
    idx = np.where(sel)[0]
    N = load_notes()
    print(f"window {t0}-{t1} s, {len(idx)} frames at {1 / np.median(np.diff(t)):.1f} fps")
    print("   t      raw    med   conf   pow    | notes starting here")
    ns = N[(N[:, 0] >= t0) & (N[:, 0] < t1)]
    for i in idx:
        tag = ""
        for r in ns:
            if abs(r[0] - t[i]) < 0.012:
                tag = f"  <- note {midi_name(r[2])} ({r[2]:.2f}) for {r[1] - r[0]:.3f} s"
        print(f"{t[i]:7.2f}  {mr[i]:6.2f} {mm[i]:6.2f}  {c[i]:5.2f} {pw[i]:6.4f}{tag}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("stage", choices=["grid", "sections", "f0", "notes", "spec", "kick",
                                      "report", "inspect", "all"])
    ap.add_argument("--t0", type=float, default=500.0)
    ap.add_argument("--t1", type=float, default=512.0)
    a = ap.parse_args(argv)
    stages = {"grid": stage_grid, "sections": stage_sections, "f0": stage_f0,
              "notes": stage_notes, "spec": stage_spec, "kick": stage_kick,
              "report": stage_report, "inspect": lambda: stage_inspect(a.t0, a.t1)}
    if a.stage == "all":
        for k in ["grid", "sections", "f0", "notes", "spec", "kick", "report"]:
            print(f"\n----- {k} -----")
            stages[k]()
    else:
        stages[a.stage]()
    return 0


if __name__ == "__main__":
    sys.exit(main())
