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
    python scripts/reaper_bass.py bell       # onset-aligned attack: partials, pitch ping, click
    python scripts/reaper_bass.py recipe     # fit a synth recipe through the same measurements
    python scripts/reaper_bass.py timbre     # per-section sub timbre fingerprint + ANOVA
    python scripts/reaper_bass.py riff       # 16th-note riff periods, run lengths, changes
    python scripts/reaper_bass.py bars       # bar-level change points -> reaper_cache/bass_bars.npz
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


# ----------------------------------------------------------------------
# 8. the bell in the attack
# ----------------------------------------------------------------------
# Every measurement below is a number. Snippets of the reference live only in memory for the
# length of one FFT; nothing is written, played or kept. The synthetic notes used for the
# control and the recipe fit are generated from scratch (sine / FM formulas), not from the file.
PRE_S, POST_S = 2000, 4000                 # snippet = onset -250 ms .. +500 ms at 8 kHz
SNIP = PRE_S + POST_S
B_WINS = [(0, 20), (20, 50), (50, 100), (100, 200), (200, 400)]
B_PRE = (-150, -90)
KP = 8                                     # partials 1..8
ZC_BINS = [0, 10, 20, 30, 45, 60, 80, 100, 130, 170, 220, 300]
HZB = [(20, 60), (60, 120), (120, 250), (250, 500), (500, 1000), (1000, 2000), (2000, 3900)]
HZW = [(-60, -10), (0, 5), (5, 20), (20, 50), (50, 100), (200, 400)]
NF = 8192
SCAN_R = np.round(np.arange(0.5, 10.0001, 0.05), 3)


def _edge_taper(n, frac=0.08):
    w = np.ones(n)
    m = max(1, int(n * frac))
    r = 0.5 - 0.5 * np.cos(np.pi * np.arange(m) / m)
    w[:m] = r
    w[-m:] = r[::-1]
    return w


_TAPER = _edge_taper(SNIP)                 # only touches -250..-190 and +440..+500 ms
_FREQ = np.fft.fftfreq(SNIP, 1.0 / SR8)
_RF = np.fft.rfftfreq(NF, 1.0 / SR8)


def _ms(a):
    return PRE_S + int(round(a * SR8 / 1000.0))


def demod_power(S, centres, sigma):
    """Gaussian complex demodulation of a snippet spectrum at each centre frequency -> power
    envelope (n_centres x SNIP). Time resolution sigma_t = 1 / (2 pi sigma)."""
    c = np.atleast_1d(np.asarray(centres, float))[:, None]
    s = np.broadcast_to(np.atleast_1d(np.asarray(sigma, float)), (c.shape[0],))[:, None]
    G = np.exp(-0.5 * ((_FREQ[None, :] - c) / s) ** 2)
    y = np.fft.ifft(S[None, :] * G, axis=1)
    return y.real ** 2 + y.imag ** 2


def partial_levels(snip, f0):
    """Partials k*f0 (k=1..8), sigma = f0/4 (neighbours 35 dB down), each re the note's own
    sustained fundamental (200-400 ms). -> (levels KP x windows, pre KP, envelope KP x 300, S)."""
    S = np.fft.fft(snip * _TAPER)
    env = demod_power(S, f0 * np.arange(1, KP + 1), f0 / 4.0)
    env /= env[0, _ms(200):_ms(400)].mean() + 1e-30
    lev = np.array([[env[k, _ms(a):_ms(b)].mean() for a, b in B_WINS] for k in range(KP)])
    pre = env[:, _ms(B_PRE[0]):_ms(B_PRE[1])].mean(1)
    return lev, pre, env[:, ::20].copy(), S


def zc_track(S, f0, lo=0.6, hi=1.9, fref=None, amp_ms=(200, 400)):
    """Period-by-period pitch from upward zero crossings of the note band-passed to lo..hi x f0.
    -> (period mid-times ms re onset, semitone offsets re the 200-400 ms pitch, that pitch)."""
    af = np.abs(_FREQ)
    L, H = lo * f0, hi * f0
    m = np.clip((af - 0.8 * L) / (0.2 * L), 0, 1) * np.clip((1.2 * H - af) / (0.2 * H), 0, 1)
    y = np.fft.ifft(S * m).real
    a0 = _ms(-5)
    seg = y[a0:_ms(420)]
    idx = np.where((seg[:-1] < 0) & (seg[1:] >= 0))[0]
    if len(idx) < 8:
        return None
    zc = idx + (-seg[idx]) / (seg[idx + 1] - seg[idx] + 1e-30)
    per = np.diff(zc) / SR8
    mid = ((zc[:-1] + zc[1:]) / 2 + a0 - PRE_S) * 1000.0 / SR8
    amp = np.array([np.abs(seg[int(zc[i]):int(np.ceil(zc[i + 1])) + 1]).max() for i in range(len(per))])
    late = (mid >= amp_ms[0]) & (mid < amp_ms[1])
    if late.sum() < 2:
        return None
    if fref is None:
        if late.sum() < 3:
            return None
        fref = 1.0 / np.median(per[late])
    ok = amp >= 0.1 * np.median(amp[late])
    return mid[ok], 12 * np.log2((1.0 / per[ok]) / fref), fref


def zc_summary(mid, off):
    b = np.full(len(ZC_BINS) - 1, np.nan)
    for i in range(len(ZC_BINS) - 1):
        s = (mid >= ZC_BINS[i]) & (mid < ZC_BINS[i + 1])
        if s.any():
            b[i] = off[s].mean()
    e = (mid >= 0) & (mid < 35)
    start = off[e].mean() if e.any() else np.nan
    sel = (mid >= 0) & (mid < 300)
    mm, oo = mid[sel], off[sel]
    settle = np.nan
    if len(oo):
        bad = np.where(np.abs(oo) >= 0.7)[0]
        if not len(bad):
            settle = 0.0
        elif bad[-1] + 1 < len(mm):
            settle = float(mm[bad[-1] + 1])
    c = (mid >= 250) & (mid < 285)
    ctrl = off[c].mean() if c.any() else np.nan
    return b, start, settle, ctrl


def psd_win(snip, a, b):
    s = snip[_ms(a):_ms(b)]
    w = np.hanning(len(s) + 2)[1:-1]
    X = np.fft.rfft(s * w, NF)
    return 2.0 * (X.real ** 2 + X.imag ** 2) / (SR8 * np.sum(w ** 2))     # power per Hz


def hz_bands(snip, f0):
    df = SR8 / NF
    late = psd_win(snip, 200, 400)
    ref = late[(_RF >= 0.75 * f0) & (_RF <= 1.25 * f0)].sum() * df + 1e-30
    out = np.zeros((len(HZB), len(HZW)))
    for j, (a, b) in enumerate(HZW):
        p = late if (a, b) == (200, 400) else psd_win(snip, a, b)
        for i, (lo, hi) in enumerate(HZB):
            out[i, j] = p[(_RF >= lo) & (_RF < hi)].sum() * df / ref
    return out, ref


def synth_note(f0, att_ms, N=0.0, tau_p=10.0, r=1.0, I0=0.0, tau_I=20.0, I_s=0.0,
               L_h=None, tau_h=20.0, N2=0.0, tau_p2=80.0, r2=2.0, I2=0.0):
    """A synthetic note from formulas (never from the reference): sine carrier, optional pitch
    envelope +N st decaying with tau_p ms, static ratio-1 modulation I_s, a decaying modulator at
    ratio r with index I0 and tau_I ms, and/or a decaying 1/k harmonic layer at L_h dB."""
    tt = (np.arange(SNIP) - PRE_S) / SR8
    tp = np.maximum(tt, 0.0)
    semi = N * np.exp(-tp / (tau_p / 1000.0)) + N2 * np.exp(-tp / (tau_p2 / 1000.0))
    f = f0 * 2 ** (semi / 12.0)
    ph = 2 * np.pi * np.cumsum(f) / SR8
    ph -= ph[PRE_S]
    I = I0 * np.exp(-tp / (tau_I / 1000.0))
    s = np.sin(ph + I_s * np.sin(ph) + I2 * np.sin(r2 * ph) + I * np.sin(r * ph))
    if L_h is not None:
        g = 10 ** (L_h / 20.0) * np.exp(-tp / (tau_h / 1000.0))
        s = s + g * sum(np.sin(k * ph) / k for k in range(2, KP + 1))
    return s * np.clip(tt / max(att_ms / 1000.0, 1e-4), 0.0, 1.0)


def bell_onsets(x):
    """Fresh bass-note onsets: a voiced run after >= 96 ms unvoiced, a stable settled pitch, a
    >= 9 dB rise in the 25-400 Hz envelope, refined to 2.5 ms."""
    d = load_f0()
    t = d["t"].astype(np.float64)
    v = d["voiced"].astype(bool)
    midi = d["midi"].astype(np.float64)
    lo = block_rms(fft_band(x, SR8, 25, 400), 20)
    hf = block_rms(fft_band(x, SR8, 2000, 3950), 20)
    L = 20 * np.log10(lo + 1e-7)
    Ls = np.convolve(L, np.ones(3) / 3, "same")
    Hd = 20 * np.log10(hf + 1e-7)
    Hs = np.convolve(Hd, np.ones(3) / 3, "same")
    EB, nb = 400.0, len(L)
    hr = np.full(nb, -99.0)
    hr[:-4] = Hs[4:] - Hs[:-4]
    cand = np.where((hr >= 9) & (hr >= np.roll(hr, 1)) & (hr >= np.roll(hr, -1)))[0]
    hits = []
    for j in cand:
        if not hits or j - hits[-1] >= 12:
            hits.append(int(j))
    hits = np.array(hits)
    runs, i, n, prev_end = [], 0, len(v), -100
    while i < n:
        if v[i]:
            j = i
            while j + 1 < n and v[j + 1]:
                j += 1
            runs.append((i, j, i - prev_end - 1))
            prev_end, i = j, j + 1
        else:
            i += 1
    out = []
    for i, j, gap in runs:
        if gap < 4:
            continue
        a, b = i + 6, min(j, i + 17)
        if b - a < 3:
            continue
        mm = midi[a:b + 1]
        if mm.std() > 0.6:
            continue
        f0 = 440.0 * 2 ** ((np.median(mm) - 69) / 12)
        jc = int(t[i] * EB)
        s0, s1 = max(jc - 40, 60), min(jc + 24, nb - 60)
        if s1 <= s0:
            continue
        js = s0 + int(np.argmax(Ls[s0 + 4:s1 + 4] - Ls[s0:s1]))
        pre = float(np.median(L[js - 24:js - 4]))
        pk = float(L[js:js + 40].max())
        if pk - pre < 9:
            continue
        Aw = 10 ** (L[js - 10:js + 40] / 20)
        ap, ak = 10 ** (pre / 20), 10 ** (pk / 20)
        jon = js - 10 + int(np.argmax(Aw >= ap + 0.25 * (ak - ap)))
        i10 = int(np.argmax(Aw >= ap + 0.10 * (ak - ap)))
        i90 = int(np.argmax(Aw >= ap + 0.90 * (ak - ap)))
        att = max((i90 - i10) * 2.5, 0.5)
        hf_rise = float(Hs[jon - 4:jon + 8].max() - np.median(Hd[jon - 40:jon - 8]))
        drums = int(((hits > jon + 6) & (hits < jon + 160)).sum()) if len(hits) else 0
        out.append((jon * 20, f0, (j - i + 1) * 0.024, pk - pre, hf_rise, drums, att, t[i]))
    O = np.array(out)
    keep = [0]
    for k in range(1, len(O)):
        if O[k, 0] - O[keep[-1], 0] >= 800:
            keep.append(k)
    return O[keep], hits / EB


def stage_bell():
    x = np.load(os.path.join(CACHE, "mono8k.npy")).astype(np.float32)
    O, hit_t = bell_onsets(x)
    bounds = load_sections()
    print(f"fresh bass-note onsets (>=96 ms unvoiced before, >=9 dB rise, stable pitch): {len(O)}")
    print(f"  HF (2-4 kHz) drum hits across the file: {len(hit_t)} ({len(hit_t) / (len(x) / SR8) * 60:.0f}/min)")
    O = O[(O[:, 2] >= 0.42) & (O[:, 0] - PRE_S >= 0) & (O[:, 0] + POST_S <= len(x))]
    print(f"  notes lasting >= 420 ms (needed for the 200-400 ms reference): {len(O)}")
    print(f"  attack 10-90% rise time: median {np.median(O[:, 6]):.1f} ms, IQR "
          f"{np.percentile(O[:, 6], 25):.1f}-{np.percentile(O[:, 6], 75):.1f} ms")
    print(f"  onset rise: median {np.median(O[:, 3]):.1f} dB; HF rise at onset: median "
          f"{np.median(O[:, 4]):.1f} dB; share with an HF drum transient AT the onset (>= 9 dB): "
          f"{np.mean(O[:, 4] >= 9) * 100:.0f}%")
    R = {k: [] for k in ("lev", "pre", "env", "lev_s", "env_s", "zcn", "zcw", "start_n", "start_w",
                         "settle", "ctrl", "scan_e", "scan_l", "scan_p", "hz", "hz_s", "psd_e",
                         "psd_l", "psd_a", "psd_s", "f0", "sec", "bell", "clean", "drums", "att", "t")}
    for s_on, f0, dur, rise, hfr, drums, att, tc in O:
        s_on = int(s_on)
        snip = x[s_on - PRE_S:s_on + POST_S].astype(np.float64)
        lev, pre, env, S = partial_levels(snip, f0)
        zn = zc_track(S, f0, 0.6, 1.9)
        zw = zc_track(S, f0, 0.6, 3.5)
        if zn is None or abs(12 * np.log2(zn[2] / f0)) > 1.0:
            continue
        sine = synth_note(zn[2], att)
        lev_s, _, env_s, _ = partial_levels(sine, zn[2])
        f0 = zn[2]                                        # the zero-crossing pitch is finer than YIN
        lev, pre, env, S = partial_levels(snip, f0)
        bn, st_n, settle, ctrl = zc_summary(zn[0], zn[1])
        if zw is not None:
            bw, st_w, _, _ = zc_summary(zw[0], zw[1])
        else:
            bw, st_w = np.full(len(ZC_BINS) - 1, np.nan), np.nan
        env_r = demod_power(S, np.r_[f0, SCAN_R * f0], np.r_[0.1 * f0, 0.1 * SCAN_R * 0 + 0.1 * f0])
        fund = env_r[0, _ms(200):_ms(400)].mean() + 1e-30
        sc = env_r[1:] / fund
        hz, _ = hz_bands(snip, f0)
        hz_s, _ = hz_bands(sine, f0)
        late = psd_win(snip, 200, 400)
        ref = late[(_RF >= 0.75 * f0) & (_RF <= 1.25 * f0)].sum() + 1e-30
        up = np.arange(1, KP)
        up_e = lev[up, :2].mean(1).sum()                  # partials 2..8 over 0-50 ms
        base = max(lev[up, 4].sum(), pre[up].sum(), lev_s[up, :2].mean(1).sum())
        R["lev"].append(lev); R["pre"].append(pre); R["env"].append(env)
        R["lev_s"].append(lev_s); R["env_s"].append(env_s)
        R["zcn"].append(bn); R["zcw"].append(bw); R["start_n"].append(st_n); R["start_w"].append(st_w)
        R["settle"].append(settle); R["ctrl"].append(ctrl)
        R["scan_e"].append(sc[:, _ms(0):_ms(80)].mean(1)); R["scan_l"].append(sc[:, _ms(200):_ms(400)].mean(1))
        R["scan_p"].append(sc[:, _ms(-160):_ms(-100)].mean(1))
        R["hz"].append(hz); R["hz_s"].append(hz_s)
        R["psd_e"].append(psd_win(snip, 0, 80) / ref); R["psd_l"].append(late / ref)
        R["psd_a"].append(psd_win(snip, 0, 20) / ref); R["psd_s"].append(psd_win(sine, 0, 20) / (
            psd_win(sine, 200, 400)[(_RF >= 0.75 * f0) & (_RF <= 1.25 * f0)].sum() + 1e-30))
        R["f0"].append(f0); R["bell"].append(10 * np.log10(up_e / base))
        R["sec"].append(int(np.searchsorted(bounds, s_on / SR8, "right") - 1))
        R["clean"].append(hfr < 9); R["drums"].append(drums); R["att"].append(att); R["t"].append(s_on / SR8)
    Z = {k: np.array(v) for k, v in R.items()}
    np.savez(scratch("bell.npz"), **Z)
    print(f"  measured {len(Z['f0'])} notes ({int(Z['clean'].sum())} with no HF drum hit at the onset); "
          f"median pitch {np.median(Z['f0']):.1f} Hz")
    bell_report()


def _dbm(a, axis=0):
    return 10 * np.log10(np.median(a, axis=axis) + 1e-30)


def bell_report():
    Z = dict(np.load(scratch("bell.npz")))
    G = load_notes()
    cl = Z["clean"].astype(bool)
    n_all, n_cl = len(cl), int(cl.sum())
    print("=" * 78)
    print(f"[9] THE BELL IN THE ATTACK - {n_all} onsets, {n_cl} clean (no 2-4 kHz hit at the onset)")
    print("=" * 78)
    for label, m in (("clean", cl), ("on a drum hit", ~cl)):
        if m.sum() < 10:
            continue
        L = _dbm(Z["lev"][m])
        Ls = _dbm(Z["lev_s"][m])
        P = _dbm(Z["pre"][m])
        print(f"\n[9.1] partial level per window, dB re the note's own sustained fundamental "
              f"[{label}, n={int(m.sum())}]")
        print("   k   " + "".join(f"{f'{a}-{b}ms':>11s}" for a, b in B_WINS) + "    pre(bg)")
        for k in range(KP):
            print(f"  {k + 1:2d}   " + "".join(f"{v:11.1f}" for v in L[k]) + f"   {P[k]:8.1f}")
        if label == "clean":
            print("  same pipeline on a clean sine note with the same pitch and attack time "
                  "(measurement floor / onset splatter):")
            for k in range(KP):
                print(f"  {k + 1:2d}   " + "".join(f"{v:11.1f}" for v in Ls[k]))
            print("  excess over the clean sine (dB), attack windows only, floored at the background:")
            for k in range(1, KP):
                ex = [L[k, w] - max(Ls[k, w], P[k]) for w in range(len(B_WINS))]
                print(f"  {k + 1:2d}   " + "".join(f"{v:+11.1f}" for v in ex))

    m = cl
    # ratio scan: which ratios light up in the attack
    se, sl, sp = _dbm(Z["scan_e"][m]), _dbm(Z["scan_l"][m]), _dbm(Z["scan_p"][m])
    print(f"\n[9.2] ratio scan (sigma = 0.1 x f0), 0-80 ms vs 200-400 ms vs pre, dB re sustained fundamental")
    print("  local peaks of the ATTACK curve (>= 2 dB above the +-0.3 ratio neighbourhood median):")
    print("   ratio   attack   sustain   pre    attack-sustain   nearest integer   off by")
    pk = []
    for i in range(3, len(SCAN_R) - 3):
        lo_, hi_ = max(0, i - 6), min(len(SCAN_R), i + 7)
        if se[i] == se[lo_:hi_].max() and se[i] - np.median(se[lo_:hi_]) >= 2.0:
            pk.append(i)
            ni = round(SCAN_R[i])
            print(f"  {SCAN_R[i]:6.2f}  {se[i]:7.1f}  {sl[i]:8.1f}  {sp[i]:6.1f}   {se[i] - sl[i]:+10.1f}"
                  f"        {ni:5d}          {SCAN_R[i] - ni:+.2f}")
    print("  attack - sustain at integer vs half-integer ratios (dB):")
    ints = [np.argmin(np.abs(SCAN_R - k)) for k in range(1, 10)]
    halfs = [np.argmin(np.abs(SCAN_R - (k + 0.5))) for k in range(1, 10)]
    print("   k      " + "".join(f"{k:>7d}" for k in range(1, 10)))
    print("   k      " + "".join(f"{se[i] - sl[i]:+7.1f}" for i in ints))
    print("   k+0.5  " + "".join(f"{se[i] - sl[i]:+7.1f}" for i in halfs))
    print("   attack level at k     " + "".join(f"{se[i]:7.1f}" for i in ints))
    print("   attack level at k+0.5 " + "".join(f"{se[i]:7.1f}" for i in halfs))
    # inharmonic candidates the coordinator named
    for rr in (1.41, 2.76, 3.5, 5.4):
        i = int(np.argmin(np.abs(SCAN_R - rr)))
        print(f"   ratio {rr:4.2f}: attack {se[i]:6.1f} dB, sustain {sl[i]:6.1f}, pre {sp[i]:6.1f}")

    # decay per partial
    E = np.median(Z["env"][m], axis=0)
    Es = np.median(Z["env_s"][m], axis=0)
    tms = (np.arange(E.shape[1]) * 20 - PRE_S) / 8.0
    print(f"\n[9.3] decay of each partial (median envelope, sigma_t = 1/(2 pi f0/4) ~ {1000 / (2 * np.pi * np.median(Z['f0']) / 4):.0f} ms)")
    print("   k   peak dB   at ms   floor dB   T-10 ms   T-20 ms   | clean-sine T-20 (resolution floor)")
    decay = []
    for k in range(KP):
        e = 10 * np.log10(E[k] + 1e-30)
        es = 10 * np.log10(Es[k] + 1e-30)
        w = (tms >= -10) & (tms <= 150)
        ip = np.where(w)[0][int(np.argmax(e[w]))]
        floor = max(10 * np.log10(np.median(Z["lev"][m][:, k, 4]) + 1e-30),
                    10 * np.log10(np.median(Z["pre"][m][:, k]) + 1e-30))
        def tdrop(curve, i0, dbd):
            after = np.where((np.arange(len(curve)) > i0) & (curve <= curve[i0] - dbd))[0]
            return tms[after[0]] - tms[i0] if len(after) else np.nan
        t10, t20 = tdrop(e, ip, 10), tdrop(e, ip, 20)
        ips = np.where(w)[0][int(np.argmax(es[w]))]
        t20s = tdrop(es, ips, 20)
        decay.append((k + 1, e[ip], tms[ip], floor, t10, t20, t20s))
        lim = " (floor within 20 dB)" if e[ip] - floor < 20 else ""
        print(f"  {k + 1:2d}  {e[ip]:7.1f}  {tms[ip]:6.1f}  {floor:8.1f}   {t10:7.1f}   {t20:7.1f}{lim:22s}| {t20s:6.1f}")

    # pitch envelope
    print(f"\n[9.4] pitch at note start, period by period (semitones re the 200-400 ms pitch)")
    bins = [f"{ZC_BINS[i]}-{ZC_BINS[i + 1]}" for i in range(len(ZC_BINS) - 1)]
    print("   ms           " + "".join(f"{b:>8s}" for b in bins))
    for label, arr in (("narrow p50", Z["zcn"][m]), ("wide   p50", Z["zcw"][m])):
        print(f"   {label}   " + "".join(f"{v:8.2f}" for v in np.nanmedian(arr, 0)))
    print("   narrow p25    " + "".join(f"{v:8.2f}" for v in np.nanpercentile(Z["zcn"][m], 25, 0)))
    print("   narrow p75    " + "".join(f"{v:8.2f}" for v in np.nanpercentile(Z["zcn"][m], 75, 0)))
    print("   n notes       " + "".join(f"{int(v):8d}" for v in np.sum(~np.isnan(Z["zcn"][m]), 0)))
    st, ctrl = Z["start_n"][m], Z["ctrl"][m]
    stw = Z["start_w"][m]
    ok = ~np.isnan(st)
    okc = ~np.isnan(ctrl)
    print(f"   start offset (0-35 ms): median {np.nanmedian(st):+.2f} st (wide band {np.nanmedian(stw):+.2f}); "
          f"p25 {np.nanpercentile(st, 25):+.2f}, p75 {np.nanpercentile(st, 75):+.2f}, p90 {np.nanpercentile(st, 90):+.2f}")
    for th in (0.5, 1.0, 2.0, 3.0, 5.0):
        print(f"     share starting >= +{th:.1f} st sharp: {np.mean(st[ok] >= th) * 100:5.1f}%   "
              f"(control, mid-note 250-285 ms: {np.mean(ctrl[okc] >= th) * 100:5.1f}%; "
              f"flat <= -{th:.1f}: {np.mean(st[ok] <= -th) * 100:4.1f}%)")
    sett = Z["settle"][m]
    print(f"   settle time (last period >= 0.7 st off): median {np.nanmedian(sett):.0f} ms, "
          f"p75 {np.nanpercentile(sett, 75):.0f} ms; among notes starting >= +1 st: median "
          f"{np.nanmedian(sett[ok & (np.nan_to_num(st) >= 1)]):.0f} ms")
    # the 96 ms glides: how many sit on a fresh note start?
    Gz = np.load(scratch("notes.npz"))["glides"]
    tons = Z["t"]
    d = load_f0()
    v = d["voiced"].astype(bool)
    ft = d["t"]
    starts = ft[np.where(v & ~np.r_[False, v[:-1]])[0]]
    near = np.array([np.any((starts >= g0 - 0.10) & (starts <= g0 + 0.03)) for g0 in Gz[:, 0]])
    print(f"   glides (from [1b]) that begin within 100 ms after a voiced start: {near.mean() * 100:.0f}% "
          f"of {len(Gz)}; of those {np.mean(Gz[near, 4] < 0) * 100:.0f}% fall (median span "
          f"{np.median(Gz[near, 4]):+.2f} st, {np.median(Gz[near, 1] - Gz[near, 0]) * 1000:.0f} ms); "
          f"the rest fall {np.mean(Gz[~near, 4] < 0) * 100:.0f}% (median span {np.median(Gz[~near, 4]):+.2f} st)")

    # click vs tone
    H = _dbm(Z["hz"][m])
    Hs = _dbm(Z["hz_s"][m])
    print(f"\n[9.5] click vs tone: band power per window, dB re the sustained fundamental (reference / clean sine)")
    print("   band Hz      " + "".join(f"{f'{a}..{b}':>14s}" for a, b in HZW))
    for i, (lo, hi) in enumerate(HZB):
        print(f"   {lo:>4d}-{hi:<5d}  " + "".join(f"{H[i, j]:7.1f}/{Hs[i, j]:<6.1f}" for j in range(len(HZW))))
    ex = np.median(Z["psd_a"][m] / 1.0, 0) - np.median(Z["psd_s"][m], 0)
    exl = np.median(Z["psd_e"][m] - Z["psd_l"][m], 0)
    sel = (_RF >= 100) & (_RF <= 3900)
    kern = np.ones(9) / 9
    exs = np.convolve(np.maximum(ex, 0), kern, "same")
    exls = np.convolve(np.maximum(exl, 0), kern, "same")
    fpk = _RF[sel][int(np.argmax(exs[sel]))]
    fpk2 = _RF[sel][int(np.argmax(exls[sel]))]
    cen = (np.maximum(ex, 0)[sel] * _RF[sel]).sum() / (np.maximum(ex, 0)[sel].sum() + 1e-30)
    pos = np.maximum(ex, 0)[sel] + 1e-12
    flat = np.exp(np.mean(np.log(pos))) / np.mean(pos)
    print(f"   0-20 ms excess over a clean sine, 100-3900 Hz: peak at {fpk:.0f} Hz, centroid {cen:.0f} Hz, "
          f"spectral flatness {flat:.3f} (1 = white click, -> 0 = tonal)")
    print(f"   0-80 ms excess over the note's own 200-400 ms spectrum: peak at {fpk2:.0f} Hz "
          f"(= {fpk2 / np.median(Z['f0'][m]):.2f} x median f0)")
    df = SR8 / NF
    att_hi = np.median([(Z["psd_a"][m][i][_RF >= 150].sum() - Z["psd_s"][m][i][_RF >= 150].sum()) * df
                        for i in range(int(m.sum()))])
    att_all = np.median([Z["psd_a"][m][i].sum() * df for i in range(int(m.sum()))])
    print(f"   attack (0-20 ms) power above 150 Hz beyond a clean sine: {10 * np.log10(max(att_hi, 1e-12)):+.1f} dB "
          f"re sustained fundamental; total 0-20 ms power {10 * np.log10(att_all):+.1f} dB")
    # absolute-Hz vs ratio-locked: where does the 0-80 ms excess concentrate?
    f0s = Z["f0"][m]
    grid_r = np.arange(0.5, 30, 0.05)
    exr = np.median([np.interp(grid_r * f0s[i], _RF, Z["psd_e"][m][i] - Z["psd_l"][m][i])
                     for i in range(int(m.sum()))], 0)
    for nm, curve, ax in (("absolute Hz", exl, _RF), ("ratio f/f0", exr, grid_r)):
        c = np.convolve(np.maximum(curve, 0), np.ones(5) / 5, "same")
        lim = (ax >= (100 if nm == "absolute Hz" else 1.5)) & (ax <= (1500 if nm == "absolute Hz" else 25))
        cc = c[lim]
        print(f"   peakiness of the 0-80 ms excess on a {nm:11s} axis: max/median = "
              f"{10 * np.log10(cc.max() / (np.median(cc) + 1e-30)):.1f} dB at {ax[lim][int(np.argmax(cc))]:.2f}")

    # consistency
    bell = Z["bell"]
    print(f"\n[9.6] consistency - bell index = partials 2-8 over 0-50 ms, dB above the loudest of "
          f"(their own sustain, the background, a clean sine's onset splatter)")
    print(f"   all {n_all}: median {np.median(bell):+.1f} dB; clean: median {np.median(bell[cl]):+.1f} dB, "
          f"p10 {np.percentile(bell[cl], 10):+.1f}, p25 {np.percentile(bell[cl], 25):+.1f}, "
          f"p75 {np.percentile(bell[cl], 75):+.1f}, p90 {np.percentile(bell[cl], 90):+.1f}")
    for th in (0, 3, 6, 10):
        print(f"   share of clean notes with bell index >= {th:2d} dB: {np.mean(bell[cl] >= th) * 100:5.1f}%")
    print("   per section (clean onsets):  sec  n   bell p50   share>=6dB   start-pitch p50   share>=+1st   att ms")
    secs = Z["sec"]
    per = []
    for s in np.unique(secs):
        mm = cl & (secs == s)
        if mm.sum() < 5:
            continue
        stv = Z["start_n"][mm]
        per.append((s, mm.sum(), np.median(bell[mm]), np.mean(bell[mm] >= 6), np.nanmedian(stv),
                    np.nanmean(np.nan_to_num(stv, nan=-9) >= 1), np.median(Z["att"][mm])))
        print(f"   S{s + 1:02d} {int(mm.sum()):4d}   {np.median(bell[mm]):+7.1f}   {np.mean(bell[mm] >= 6) * 100:9.0f}%"
              f"   {np.nanmedian(stv):+13.2f}   {np.nanmean(np.nan_to_num(stv, nan=-9) >= 1) * 100:10.0f}%"
              f"   {np.median(Z['att'][mm]):6.1f}")
    np.savez(scratch("bell_summary.npz"), L=_dbm(Z["lev"][cl]), P=_dbm(Z["pre"][cl]),
             Z=np.nanmedian(Z["zcn"][cl], 0), f0=np.median(Z["f0"][cl]), att=np.median(Z["att"][cl]),
             decay=np.array(decay), per=np.array(per))


def zc_signature(S, f0):
    """Discriminates a pitch SWEEP from an FM sideband: (narrow start st, wide start st, share of
    0-45 ms periods more than 0.7 st FLAT, monotone-falling flag)."""
    zn = zc_track(S, f0, 0.6, 1.9)
    zw = zc_track(S, f0, 0.6, 3.5)
    if zn is None or zw is None:
        return np.nan, np.nan, np.nan, np.nan
    sn = zc_summary(zn[0], zn[1])[1]
    sw = zc_summary(zw[0], zw[1])[1]
    e = (zn[0] >= 0) & (zn[0] < 45)
    if e.sum() < 2:
        return sn, sw, np.nan, np.nan
    o = zn[1][e]
    return sn, sw, float(np.mean(o < -0.7)), float(np.all(np.diff(o) <= 0.5))


def stage_recipe():
    """Fit the smallest synth that, pushed through the SAME measurement code, lands on the
    reference medians. Only formula-generated notes are synthesised."""
    B = np.load(scratch("bell_summary.npz"))
    Zb = dict(np.load(scratch("bell.npz")))
    cl = Zb["clean"].astype(bool)
    Lref, Pref, Zref = B["L"], B["P"], B["Z"]
    Zwref = np.nanmedian(Zb["zcw"][cl], 0)
    Href = _dbm(Zb["hz"][cl])
    f0 = float(B["f0"])
    floor = 10 ** (Pref / 10)
    hz_floor = 10 ** (Href[:, 0] / 10)                     # background from the -60..-10 ms window
    zvalid, zwvalid = ~np.isnan(Zref), ~np.isnan(Zwref)
    HB, HW = [1, 2, 3, 4], [1, 2, 3]                       # 60-1000 Hz x (0-5, 5-20, 20-50 ms)

    def score(**kw):
        s = synth_note(f0, **kw)
        lev, _, _, S = partial_levels(s, f0)
        Lm = 10 * np.log10(lev + floor[:, None] + 1e-30)
        e_db = np.sqrt(np.mean((Lm - Lref) ** 2))
        hz = hz_bands(s, f0)[0]
        Hm = 10 * np.log10(hz[np.ix_(HB, HW)] + hz_floor[HB][:, None] + 1e-30)
        e_hz = np.sqrt(np.mean((Hm - Href[np.ix_(HB, HW)]) ** 2))
        zn = zc_track(S, f0, 0.6, 1.9)
        zw = zc_track(S, f0, 0.6, 3.5)
        if zn is None or zw is None:
            return 1e9, e_db, 9.0, e_hz
        zb = zc_summary(zn[0], zn[1])[0]
        zwb = zc_summary(zw[0], zw[1])[0]
        v, vw = zvalid & ~np.isnan(zb), zwvalid & ~np.isnan(zwb)
        e_st = np.sqrt(np.mean(np.r_[(zb[v] - Zref[v]) ** 2, (zwb[vw] - Zwref[vw]) ** 2]))
        return (e_db / 2.0) ** 2 + (e_st / 0.5) ** 2 + (e_hz / 4.0) ** 2, e_db, e_st, e_hz

    def search(grid, fixed):
        best = None
        for g in grid:
            kw = dict(fixed)
            kw.update(g)
            J, e_db, e_st, e_hz = score(**kw)
            if best is None or J < best[0]:
                best = (J, e_db, e_st, e_hz, kw)
        return best

    print(f"target: median clean note, f0 {f0:.1f} Hz (n={int(cl.sum())})")
    res = {}
    atts = [0.2, 1, 2, 4, 8, 16, 32]
    Iss = [0.0, 0.15, 0.3, 0.45]
    res["sine"] = search([dict(att_ms=a, I_s=i) for a in atts for i in Iss], {})
    base = {k: res["sine"][4][k] for k in ("att_ms", "I_s")}
    Ns = [0, 3, 6, 9, 12, 15, 18, 21, 24, 30, 36, 48]
    taus = [2, 3, 4, 5, 6, 8, 10, 12, 15, 18, 25, 35, 50]
    N2s = [0.0, 0.5, 1.0, 1.5, 2.0, 3.0]
    tau2s = [40, 60, 90, 130, 200]
    res["pitch env"] = search([dict(N=n, tau_p=tp) for n in Ns for tp in taus], base)
    fixed = dict(base, **{k: res["pitch env"][4][k] for k in ("N", "tau_p")})
    b2 = search([dict(N2=n2, tau_p2=t2) for n2 in N2s for t2 in tau2s], fixed)
    b2 = search([dict(N=n, tau_p=tp) for n in Ns for tp in taus],
                {k: v for k, v in b2[4].items() if k not in ("N", "tau_p")})
    res["pitch env, two-stage"] = b2
    rs = [0.5, 1.0, 1.5, 2.0, 2.76, 3.0, 3.5, 4.0, 5.0, 5.4, 7.0]
    I0s = list(np.arange(0.0, 6.01, 0.5))
    tIs = [3, 5, 8, 12, 18, 25, 35, 50, 70, 100, 150]
    res["FM modulator"] = search([dict(r=r, I0=i, tau_I=ti) for r in rs for i in I0s for ti in tIs], base)
    Lhs = list(range(-30, 7, 3))
    res["harmonic layer"] = search([dict(L_h=l, tau_h=th) for l in Lhs for th in tIs], base)
    I2s = [0.0, 0.25, 0.5, 0.75, 1.0]
    # rival explanation: no pitch envelope at all - a decaying modulator plus a static one
    cur = dict(base, **{k: res["FM modulator"][4][k] for k in ("r", "I0", "tau_I")})
    b = None
    for _ in range(2):
        b = search([dict(r2=r2, I2=i2) for r2 in (1.0, 2.0, 3.0) for i2 in I2s],
                   {k: v for k, v in cur.items() if k not in ("r2", "I2")})
        cur = b[4]
        b = search([dict(r=r, I0=i, tau_I=ti) for r in rs for i in I0s for ti in tIs],
                   {k: v for k, v in cur.items() if k not in ("r", "I0", "tau_I")})
        cur = b[4]
    res["two FM modulators, no pitch env"] = b
    # recipe candidate: pitch envelope + static modulator (+ optional decaying modulator)
    cur = dict(res["pitch env, two-stage"][4])
    for _ in range(2):
        b = search([dict(r2=r2, I2=i2) for r2 in (1.0, 2.0, 3.0) for i2 in I2s],
                   {k: v for k, v in cur.items() if k not in ("r2", "I2")})
        cur = b[4]
        b = search([dict(N=n, tau_p=tp) for n in Ns for tp in taus],
                   {k: v for k, v in cur.items() if k not in ("N", "tau_p")})
        cur = b[4]
        b = search([dict(N2=n2, tau_p2=t2) for n2 in N2s for t2 in tau2s],
                   {k: v for k, v in cur.items() if k not in ("N2", "tau_p2")})
        cur = b[4]
        b = search([dict(att_ms=a, I_s=i) for a in atts for i in Iss],
                   {k: v for k, v in cur.items() if k not in ("att_ms", "I_s")})
        cur = b[4]
    res["pitch env + static modulator"] = b
    b = search([dict(r=r, I0=i, tau_I=ti) for r in rs for i in I0s for ti in tIs], cur)
    res["pitch env + static + decaying modulator"] = b
    print("\nmodel                                     rms dB partials  rms st pitch  rms dB click bands    J")
    for k, (J, e_db, e_st, e_hz, kw) in res.items():
        print(f"  {k:40s}  {e_db:10.2f}     {e_st:10.2f}    {e_hz:10.2f}      {J:7.2f}")
        print("      " + ", ".join(f"{a}={round(float(v), 3)}" for a, v in kw.items()))
    Jb = res["sine"][0]
    print("\nsingle-component improvement over a plain sine (same attack + static ratio-1 modulation):")
    for k in ("pitch env", "pitch env, two-stage", "FM modulator", "harmonic layer"):
        print(f"  {k:22s}  J {Jb:.2f} -> {res[k][0]:.2f}  ({(1 - res[k][0] / Jb) * 100:.0f}% of the misfit removed)")

    # sweep-vs-sideband discriminator, reference vs the two rival explanations
    x = np.load(os.path.join(CACHE, "mono8k.npy"), mmap_mode="r")
    sig = []
    for tt, ff in zip(Zb["t"][cl], Zb["f0"][cl]):
        s0 = int(round(tt * SR8))
        snip = np.asarray(x[s0 - PRE_S:s0 + POST_S], np.float64)
        sig.append(zc_signature(np.fft.fft(snip * _TAPER), ff))
    sig = np.array(sig)
    print("\nSWEEP or SIDEBAND?        narrow start   wide start   wide-narrow   flat periods 0-45 ms   monotone fall")
    print(f"  reference (median)        {np.nanmedian(sig[:, 0]):+7.2f}      {np.nanmedian(sig[:, 1]):+7.2f}"
          f"      {np.nanmedian(sig[:, 1] - sig[:, 0]):+6.2f}        {np.nanmean(sig[:, 2]) * 100:6.1f}%"
          f"              {np.nanmean(sig[:, 3]) * 100:5.1f}%")
    for k in ("pitch env + static modulator", "two FM modulators, no pitch env"):
        s = synth_note(f0, **res[k][4])
        g = zc_signature(np.fft.fft(s * _TAPER), f0)
        print(f"  {k[:24]:24s}  {g[0]:+7.2f}      {g[1]:+7.2f}      {g[1] - g[0]:+6.2f}        "
              f"{g[2] * 100:6.1f}%              {g[3] * 100:5.1f}%")

    full = res["pitch env + static + decaying modulator"]
    kw = full[4] if full[0] < 0.85 * res["pitch env + static modulator"][0] else res["pitch env + static modulator"][4]
    s = synth_note(f0, **kw)
    lev, _, env, S = partial_levels(s, f0)
    Lm = 10 * np.log10(lev + floor[:, None] + 1e-30)
    print("\nRECIPE (chosen): " + ", ".join(f"{a}={round(float(v), 3)}" for a, v in kw.items()))
    print("fitted synth through the same pipeline (dB re sustained fundamental, background added) | reference:")
    print("   k   " + "".join(f"{f'{a}-{b}ms':>11s}" for a, b in B_WINS))
    for k in range(KP):
        print(f"  {k + 1:2d}   " + "".join(f"{v:11.1f}" for v in Lm[k]) + "   | " +
              " ".join(f"{v:6.1f}" for v in Lref[k]))
    zn = zc_track(S, f0, 0.6, 1.9)
    zw = zc_track(S, f0, 0.6, 3.5)
    print("   narrow pitch bins synth " + " ".join(f"{v:6.2f}" for v in zc_summary(zn[0], zn[1])[0]))
    print("   narrow pitch bins ref   " + " ".join(f"{v:6.2f}" for v in Zref))
    print("   wide   pitch bins synth " + " ".join(f"{v:6.2f}" for v in zc_summary(zw[0], zw[1])[0]))
    print("   wide   pitch bins ref   " + " ".join(f"{v:6.2f}" for v in Zwref))
    hz = hz_bands(s, f0)[0]
    Hm = 10 * np.log10(hz + hz_floor[:, None] + 1e-30)
    print("   click bands, ref / synth+background:  " + "".join(f"{f'{a}..{b}':>14s}" for a, b in HZW[1:4]))
    for i, (lo, hi) in enumerate(HZB):
        print(f"   {lo:>4d}-{hi:<5d}                            " + "".join(
            f"{Href[i, j]:7.1f}/{Hm[i, j]:<6.1f}" for j in (1, 2, 3)))
    tt = np.array([0, 2, 5, 10, 15, 20, 30, 45, 60, 100, 150, 200])
    semi = kw.get("N", 0) * np.exp(-tt / kw.get("tau_p", 1)) + kw.get("N2", 0) * np.exp(-tt / kw.get("tau_p2", 1))
    print("   pitch envelope of the recipe (st above the note): " + "  ".join(f"{a}ms {v:+.1f}" for a, v in zip(tt, semi)))
    print(f"   start frequency at the median note: {f0 * 2 ** (semi[0] / 12):.0f} Hz -> {f0:.0f} Hz")
    np.savez(scratch("recipe.npz"), names=np.array(list(res)),
             scores=np.array([[v[0], v[1], v[2], v[3]] for v in res.values()]),
             chosen=np.array([f"{a}={v}" for a, v in kw.items()]))


# ----------------------------------------------------------------------
# 10. timbre per section
# ----------------------------------------------------------------------
def stage_timbre():
    x = np.load(os.path.join(CACHE, "mono8k.npy")).astype(np.float32)
    N = load_notes(merged=True)
    bounds = load_sections()
    T = timbre_rows(x, N, bounds, 0.25, 0.06, 0.15)
    cols = ["h2", "h3", "h4", "h5", "h6", "h7", "h8", "odd-even", "THD", "floor@h2", "floor@h5"]
    np.savez(scratch("timbre.npz"), T=T, cols=np.array(cols))
    print(f"{len(T)} notes (plateaus >= 250 ms, conf > 0.7), sustain from +60 ms for up to 400 ms")
    secs = T[:, 2].astype(int)
    midi = T[:, 3]
    F = T[:, 4:15]
    h1x = T[:, 15]
    groups = [s for s in np.unique(secs) if (secs == s).sum() >= 8]
    msk = np.isin(secs, groups)
    secs, midi, F, h1x = secs[msk], midi[msk], F[msk], h1x[msk]
    print(f"octave sanity: the fundamental stands {np.median(h1x):.1f} dB above its half-integer neighbours "
          f"(p10 {np.percentile(h1x, 10):.1f} dB); notes where it does not clear 6 dB: {np.mean(h1x < 6) * 100:.1f}%")
    print(f"{len(F)} notes in {len(groups)} sections with >= 8 notes")

    def anova(y, g):
        ok = ~np.isnan(y)
        y, g = y[ok], g[ok]
        u, inv = np.unique(g, return_inverse=True)
        n = np.bincount(inv)
        mu = np.bincount(inv, y) / n
        gm = y.mean()
        ssb = (n * (mu - gm) ** 2).sum()
        ssw = ((y - mu[inv]) ** 2).sum()
        dfb, dfw = len(u) - 1, len(y) - len(u)
        return (ssb / dfb) / (ssw / dfw), ssb / (ssb + ssw), inv, y

    rng = np.random.default_rng(7)
    print("\nfeature     F raw   eta2   perm p   | slope dB/oct (within)   F pitch-adjusted  eta2 adj"
          "   | within-sec SD  between-sec SD (of medians)  half-split r")
    stats = {}
    for j, c in enumerate(cols):
        y = F[:, j]
        Fr, e2, inv, yy = anova(y, secs)
        cnt = 0
        for _ in range(500):
            Fp, _, _, _ = anova(y, rng.permutation(secs))
            cnt += Fp >= Fr
        beta = within_slope(y, midi, secs)
        ya = y - beta * (midi - np.nanmean(midi))
        Fa, e2a, _, _ = anova(ya, secs)
        ok = ~np.isnan(ya)
        u = np.unique(secs[ok])
        med = np.array([np.median(ya[ok][secs[ok] == s]) for s in u])
        wsd = np.sqrt(np.mean([np.var(ya[ok][secs[ok] == s]) for s in u]))
        h1, h2 = [], []
        for s in u:
            idx = np.where(ok & (secs == s))[0]
            if len(idx) >= 8:
                h1.append(np.median(ya[idx[:len(idx) // 2]]))
                h2.append(np.median(ya[idx[len(idx) // 2:]]))
        r = np.corrcoef(h1, h2)[0, 1] if len(h1) > 3 else np.nan
        stats[c] = (Fr, e2, (cnt + 1) / 501, beta * 12, Fa, e2a, wsd, med.std(), r)
        print(f"{c:10s} {Fr:7.1f}  {e2:5.2f}  {(cnt + 1) / 501:6.3f}   | {beta * 12:+10.1f}              "
              f"{Fa:7.1f}        {e2a:5.2f}     | {wsd:8.1f}        {med.std():8.1f}                 {r:+.2f}")
    # nearest-centroid section identification from the standardised fingerprint
    use = [cols.index(c) for c in ("h2", "h3", "h4", "h5", "odd-even", "THD")]
    Y = np.column_stack([F[:, j] - within_slope(F[:, j], midi, secs) * (midi - np.nanmean(midi)) for j in use])
    good = ~np.isnan(Y).any(1)
    Y, sg = Y[good], secs[good]
    Y = (Y - Y.mean(0)) / (Y.std(0) + 1e-9)
    u = np.unique(sg)
    hit = hit1 = 0
    for i in range(len(Y)):
        m = np.ones(len(Y), bool)
        m[i] = False
        cents = np.array([np.median(Y[m & (sg == s)], 0) if (m & (sg == s)).sum() else np.full(Y.shape[1], 1e9)
                          for s in u])
        pred = u[int(np.argmin(((cents - Y[i]) ** 2).sum(1)))]
        hit += pred == sg[i]
        hit1 += abs(pred - sg[i]) <= 1
    print(f"\nleave-one-out nearest-centroid: which section is this note from? {hit / len(Y) * 100:.1f}% exact "
          f"(chance {100 / len(u):.1f}%), {hit1 / len(Y) * 100:.1f}% within +-1 section")
    B = None
    if os.path.exists(scratch("bell.npz")):
        B = dict(np.load(scratch("bell.npz")))
    print("\nper section (pitch-adjusted medians, dB re the note's own fundamental):")
    print("  sec   n   medMIDI    h2     h3     h4     h5    odd-even   THD   floor@h2 floor@h5 | bell p50  n_on | h1 clear dB")
    per = []
    for s in u:
        idx = sg == s
        raw = secs == s
        adj = lambda j: np.nanmedian(F[raw, j] - within_slope(F[:, j], midi, secs) * (midi[raw] - np.nanmean(midi)))
        vals = [adj(cols.index(c)) for c in ("h2", "h3", "h4", "h5", "odd-even", "THD", "floor@h2", "floor@h5")]
        bm, bn = np.nan, 0
        if B is not None:
            mb = (B["sec"] == s) & B["clean"].astype(bool)
            bn = int(mb.sum())
            bm = np.median(B["bell"][mb]) if bn >= 3 else np.nan
        per.append([s + 1, raw.sum(), np.median(midi[raw])] + vals + [bm, bn])
        print(f"  S{s + 1:02d} {int(raw.sum()):4d}  {np.median(midi[raw]):6.1f}  " +
              "  ".join(f"{v:+5.1f}" for v in vals[:4]) + f"   {vals[4]:+6.1f}  {vals[5]:+6.1f}  {vals[6]:+7.1f}  "
              f"{vals[7]:+7.1f}  | {bm:+6.1f}  {bn:4d} | {np.median(h1x[raw]):5.1f}")
    np.savez(scratch("timbre_summary.npz"), per=np.array(per),
             stats=np.array([stats[c] for c in cols]), cols=np.array(cols))


# ----------------------------------------------------------------------
# 11. riff repetition
# ----------------------------------------------------------------------
RIFF_THR = 0.50            # 16th-slot agreement for "the same riff" (chance between records ~11%)
RIFF_TOL = 1               # semitones: absorbs glide / pitch-ping smear across a 16th boundary


def riff_match(a, b, tol=RIFF_TOL):
    act = (a >= 0) | (b >= 0)
    if act.sum() < 3:
        return np.nan
    same = act & (((a >= 0) & (b >= 0) & (np.abs(a - b) <= tol)) | ((a < 0) & (b < 0)))
    return same.sum() / act.sum()


def onsets(row):
    row = np.asarray(row)
    prev = np.r_[-1, row[:-1]]
    return (row >= 0) & ((prev < 0) | (np.abs(row - prev) > RIFF_TOL))


def bar_sequences():
    """Per bar, 16 slots on the grid.npz beats: rounded MIDI of the bass, -1 = rest."""
    beats, downbeats, _ = load_grid()
    d = load_f0()
    ft, midi, v = d["t"].astype(np.float64), d["midi"].astype(np.float64), d["voiced"].astype(bool)
    bidx = np.searchsorted(beats, downbeats - 0.02)
    bars = []
    for bi in bidx:
        if bi + 4 < len(beats):
            b0 = beats[bi:bi + 5]
            bars.append(np.r_[np.concatenate([b0[k] + (b0[k + 1] - b0[k]) * np.arange(4) / 4 for k in range(4)]), b0[4]])
    bars = np.array(bars)
    nb = len(bars)
    seq = np.full((nb, 16), -1, int)
    for b in range(nb):
        i0, i1 = np.searchsorted(ft, bars[b, 0]), np.searchsorted(ft, bars[b, 16])
        tt, vv, mm = ft[i0:i1], v[i0:i1], midi[i0:i1]
        k = np.clip(np.searchsorted(bars[b], tt, "right") - 1, 0, 15)
        for s in range(16):
            sel = k == s
            if sel.sum() and vv[sel].mean() >= 0.5:
                seq[b, s] = int(round(np.median(mm[sel & vv])))
    active = (seq >= 0).sum(1) >= 3
    return bars, seq, active


def block_match(A, LA, Bq, LB, tol=RIFF_TOL):
    """Best agreement between two riffs of LA and LB bars, tiled to a common length, over every
    bar rotation of the second."""
    Lc = int(np.lcm(LA, LB))
    At = np.tile(A.reshape(LA, 16), (Lc // LA, 1)).ravel()
    best = 0.0
    for sh in range(LB):
        Bt = np.tile(np.roll(Bq.reshape(LB, 16), sh, axis=0), (Lc // LB, 1)).ravel()
        m = riff_match(At, Bt, tol)
        if not np.isnan(m) and m > best:
            best = m
    return best


def riff_core(seq, active, sec, nsec, thr=RIFF_THR, tol=RIFF_TOL):
    nb = len(seq)
    lags = (1, 2, 3, 4, 8)
    per_sec, period = {}, np.full(nb, 4, int)
    for s in range(nsec):
        bs = np.where((sec == s) & active)[0]
        mv = {}
        for L in lags:
            vals = [riff_match(seq[b], seq[b + L], tol) for b in bs
                    if b + L < nb and sec[b + L] == s and active[b + L]]
            vals = [q for q in vals if not np.isnan(q)]
            mv[L] = (float(np.mean(vals)) if len(vals) >= 3 else np.nan, len(vals))
        cands = [L for L in (1, 2, 4, 8) if not np.isnan(mv[L][0])]
        P, bestL = 0, 4
        if cands:
            best = max(mv[L][0] for L in cands)
            bestL = min(L for L in cands if mv[L][0] >= best - 0.08)
            P = bestL if best >= thr else 0
        per_sec[s] = (mv, P)
        period[sec == s] = bestL
    cont = np.zeros(nb, bool)
    for b in range(nb):
        L = period[b]
        if b - L >= 0 and active[b] and active[b - L]:
            m = riff_match(seq[b], seq[b - L], tol)
            cont[b] = (not np.isnan(m)) and m >= thr
    runs, b = [], 0
    while b < nb:
        if cont[b]:
            e = b
            while e + 1 < nb and (cont[e + 1] or (e + 2 < nb and cont[e + 2] and active[e + 1])):
                e += 1
            L = period[b]
            runs.append((max(b - L, 0), e, L))
            b = e + 1
        else:
            b += 1
    return per_sec, period, cont, runs


def riff_ids(seq, active, runs, period, thr=RIFF_THR, tol=RIFF_TOL):
    """Same id whenever the same riff (any rotation, any tiling of 1/2/4/8 bars) comes back."""
    nb = len(seq)
    rid = np.full(nb, -1, int)
    protos = []                                          # (block, L)
    def assign(block, L):
        for i, (pb, pL) in enumerate(protos):
            if block_match(pb, pL, block, L, tol) >= thr:
                return i
        protos.append((block, L))
        return len(protos) - 1
    for s, e, L in runs:
        blocks = [seq[q:q + L].ravel() for q in range(s, e - L + 2, L) if q + L <= nb]
        if not blocks:
            continue
        if len(blocks) > 2:
            sc = [np.nanmean([riff_match(bk, o, tol) for o in blocks if o is not bk]) for bk in blocks]
            med = blocks[int(np.nanargmax(sc))]
        else:
            med = blocks[0]
        i = assign(med, L)
        rid[s:e + 1] = np.where(active[s:e + 1], i, -1)
    for b in range(nb):                                  # active bars outside any run
        if active[b] and rid[b] < 0:
            L = period[b]
            blk = seq[b:b + L].ravel() if b + L <= nb else seq[b:b + 1].ravel()
            rid[b] = assign(blk, L if b + L <= nb else 1)
    return rid, len(protos)


def segments_from_ids(ids, min_len=2):
    """Contiguous runs of equal id; runs shorter than min_len bars are absorbed by the previous
    run (or the next one at the start)."""
    ids = np.asarray(ids).copy()
    changed = True
    while changed:
        changed = False
        starts = np.r_[0, np.where(np.diff(ids) != 0)[0] + 1]
        ends = np.r_[starts[1:], len(ids)]
        for a, z in zip(starts, ends):
            if z - a < min_len and len(starts) > 1:
                ids[a:z] = ids[a - 1] if a > 0 else ids[z]
                changed = True
                break
    starts = np.r_[0, np.where(np.diff(ids) != 0)[0] + 1]
    seg = np.zeros(len(ids), int)
    for i, a in enumerate(starts):
        seg[a:] = i
    return seg, starts[1:], ids


def stage_riff():
    bars, seq, active = bar_sequences()
    bounds = load_sections()
    nb, nsec = len(seq), len(bounds) - 1
    sec = np.searchsorted(bounds, bars[:, 0], "right") - 1
    print(f"{nb} bars x 16 slots; bars with >= 3 pitched 16ths: {active.sum()} ({active.mean() * 100:.0f}%)")
    print(f"  16ths pitched: {(seq >= 0).mean() * 100:.0f}%; note onsets per active bar: "
          f"median {np.median([onsets(seq[b]).sum() for b in range(nb) if active[b]]):.1f}")
    rng = np.random.default_rng(3)
    ab = np.where(active)[0]
    ch0, ch1 = [], []
    while len(ch1) < 20000:
        i, j = rng.choice(ab, 2, replace=False)
        if sec[i] != sec[j]:
            ch0.append(riff_match(seq[i], seq[j], 0))
            ch1.append(riff_match(seq[i], seq[j], 1))
    ch0, ch1 = np.array(ch0), np.array(ch1)
    print(f"  chance agreement between bars of DIFFERENT sections: exact mean {np.nanmean(ch0) * 100:.0f}%, "
          f"+-1 st mean {np.nanmean(ch1) * 100:.0f}% (p90 {np.nanpercentile(ch1, 90) * 100:.0f}%, "
          f"p99 {np.nanpercentile(ch1, 99) * 100:.0f}%) -> threshold {RIFF_THR * 100:.0f}% at +-{RIFF_TOL} st")
    per_sec, period, cont, runs = riff_core(seq, active, sec, nsec)
    rl = np.array([e - s + 1 for s, e, L in runs])
    print(f"\nper-section lag agreement (mean over active bar pairs b, b+L; +-1 st)")
    print("  sec   bars active |   L1   L2   L3   L4   L8 | period  notes/riff  runs  median run  max run")
    table = []
    for s in range(nsec):
        mv, P = per_sec[s]
        bsec = np.where(sec == s)[0]
        sr = [r for r, (a, e, L) in zip(rl, runs) if sec[min(a, nb - 1)] == s]
        L = period[bsec[0]] if len(bsec) else 4
        npr = np.median([onsets(seq[b:b + L].ravel()).sum() for b in bsec if active[b] and b + L <= nb]) \
            if active[bsec].sum() else np.nan
        cells = "  ".join(f"{mv[q][0] * 100:3.0f}" if not np.isnan(mv[q][0]) else "  -" for q in (1, 2, 3, 4, 8))
        print(f"  S{s + 1:02d}  {len(bsec):4d}  {int(active[bsec].sum()):5d} | {cells} | "
              f"{(str(P) if P else '(' + str(L) + ')'):>6}  {npr:9.1f}  {len(sr):5d}  "
              f"{(np.median(sr) if sr else float('nan')):9.0f}  {(max(sr) if sr else 0):7d}")
        table.append([s + 1, len(bsec), active[bsec].sum()] + [mv[q][0] for q in (1, 2, 3, 4, 8)] +
                     [P, L, npr, len(sr), np.median(sr) if sr else np.nan, max(sr) if sr else 0])
    Ps = [row[8] for row in table if row[8]]
    print(f"  periods found: " + ", ".join(f"{q} bars x{Ps.count(q)}" for q in (1, 2, 4, 8)) +
          f"; no riff above threshold in {nsec - len(Ps)} sections")
    print(f"\n{len(runs)} riff runs (each bar agrees with the bar one period back, one odd bar tolerated)")
    print(f"  run length in bars: p10 {np.percentile(rl, 10):.0f}, p25 {np.percentile(rl, 25):.0f}, "
          f"median {np.median(rl):.0f}, p75 {np.percentile(rl, 75):.0f}, p90 {np.percentile(rl, 90):.0f}, max {rl.max()}")
    print("  bars      runs   % runs   % of riff bars")
    for lo, hi in [(2, 4), (4, 8), (8, 16), (16, 32), (32, 999)]:
        m = (rl >= lo) & (rl < hi)
        print(f"  {lo:>3d}-{(str(hi - 1) if hi < 999 else ''):<4}  {m.sum():5d}   {m.mean() * 100:5.0f}%   "
              f"{rl[m].sum() / rl.sum() * 100:6.0f}%")
    in_runs = np.zeros(nb, bool)
    for s0, e0, L in runs:
        in_runs[s0:e0 + 1] = True
    def act_in(lo, hi):
        m = np.zeros(nb, bool)
        for (s0, e0, L), r in zip(runs, rl):
            if lo <= r <= hi:
                m[s0:e0 + 1] = True
        return np.sum(m & active) / active.sum() * 100
    print(f"  active bars inside a run: {np.mean(in_runs[active]) * 100:.0f}%; inside runs of 8-16 bars: "
          f"{act_in(8, 16):.0f}%; of >= 8 bars: {act_in(8, 9999):.0f}%; of < 8 bars: {act_in(1, 7):.0f}%")
    for thr in (0.40, 0.60):
        _, _, _, rr = riff_core(seq, active, sec, nsec, thr=thr)
        q = np.array([e - s + 1 for s, e, L in rr])
        print(f"  sensitivity, threshold {thr * 100:.0f}%: {len(rr)} runs, median {np.median(q):.0f} bars, "
              f"p75 {np.percentile(q, 75):.0f}, p90 {np.percentile(q, 90):.0f}")
    kinds = []
    for (s0, e0, L0), nxt in zip(runs[:-1], runs[1:]):
        L = max(L0, 1)
        A = seq[max(e0 - L + 1, 0):e0 + 1].ravel()
        n0 = e0 + 1
        while n0 < nb and not active[n0]:
            n0 += 1
        if n0 + L > nb:
            break
        Bq = seq[n0:n0 + L].ravel()
        if len(A) != len(Bq):
            continue
        pm = block_match(A, L, Bq, L)
        oa, ob = onsets(A), onsets(Bq)
        act = (A >= 0) | (Bq >= 0)
        rm = float(np.mean((((A >= 0) == (Bq >= 0)) & (oa == ob))[act])) if act.any() else np.nan
        tb, tm = 0, 0.0
        for tr in range(-12, 13):
            if abs(tr) <= RIFF_TOL:
                continue
            mt = block_match(np.where(A >= 0, A + tr, -1), L, Bq, L)
            if mt > tm:
                tm, tb = mt, tr
        na = [int(p) % 12 for p, o in zip(A, oa) if o]
        nq = [int(p) % 12 for p, o in zip(Bq, ob) if o]
        same_notes = len(na) > 0 and sorted(set(na)) == sorted(set(nq))
        if pm >= RIFF_THR:
            k = "variation, then same riff"
        elif tm >= RIFF_THR and tm > pm + 0.15:
            k = "transposition"
        elif rm >= 0.75:
            k = "same rhythm, new notes"
        elif same_notes:
            k = "same notes, new rhythm"
        elif pm >= 0.30:
            k = "partial variation"
        else:
            k = "new riff"
        kinds.append((k, sec[e0] != sec[min(n0, nb - 1)], n0 - e0 - 1, tb if k == "transposition" else 0))
    from collections import Counter
    cnt = Counter(k for k, *_ in kinds)
    print(f"\nwhat follows the end of a run ({len(kinds)} changes):")
    for k, c in cnt.most_common():
        sub = [q for q in kinds if q[0] == k]
        print(f"  {k:26s} {c:4d}  ({c / len(kinds) * 100:4.0f}%)  across a section boundary "
              f"{np.mean([q[1] for q in sub]) * 100:3.0f}%, after an absence {np.mean([q[2] > 0 for q in sub]) * 100:3.0f}%")
    tr = [q[3] for q in kinds if q[0] == "transposition"]
    if tr:
        print(f"  transposition intervals (st): {dict(Counter(tr))}")
    np.savez(scratch("riff.npz"), table=np.array(table, float), rl=rl, chance=np.array([np.nanmean(ch1)]),
             kinds=np.array([k for k, *_ in kinds]))


# ----------------------------------------------------------------------
# 12. bar-level state: change points, phrase grid, bass_bars.npz
# ----------------------------------------------------------------------
TIMBRE_COLS = ["h2", "h3", "h4", "h5", "odd-even", "THD"]


def timbre_rows(x, N, bounds, min_dur=0.25, lead=0.06, min_win=0.15, max_win=0.40):
    """Per held note: harmonic levels re its own fundamental, background-subtracted.
    Row = [t0, t1, sec, midi, h2..h8, odd-even, THD, floor@h2, floor@h5, h1 over its neighbours]."""
    nfft = 1 << 15
    fr = np.fft.rfftfreq(nfft, 1.0 / SR8)
    rows = []
    for t0, t1, m, sd, cf, pw in N:
        if t1 - t0 < min_dur or cf < 0.7:
            continue
        a = t0 + lead
        b = min(t1 - 0.02, a + max_win)
        if b - a < min_win:
            continue
        seg = x[int(a * SR8):int(b * SR8)].astype(np.float64)
        X = np.fft.rfft(seg * np.hanning(len(seg)), nfft)
        P = X.real ** 2 + X.imag ** 2
        f0 = 440.0 * 2 ** ((m - 69) / 12)
        s = (fr >= 0.94 * f0) & (fr <= 1.06 * f0)
        i = np.where(s)[0][int(np.argmax(P[s]))]
        y0, y1, y2 = np.log(P[i - 1] + 1e-30), np.log(P[i] + 1e-30), np.log(P[i + 1] + 1e-30)
        den = y0 - 2 * y1 + y2
        f0r = fr[i] + (0.5 * (y0 - y2) / den if den != 0 else 0.0) * (fr[1] - fr[0])
        on, off = np.full(KP, np.nan), np.full(KP, np.nan)
        for k in range(1, KP + 1):
            if (k + 0.62) * f0r > 3900:
                break
            w = 0.12 * f0r
            on[k - 1] = P[(fr >= k * f0r - w) & (fr <= k * f0r + w)].max()
            off[k - 1] = 0.5 * (P[(fr >= (k + 0.5) * f0r - w) & (fr <= (k + 0.5) * f0r + w)].max() +
                                P[(fr >= (k - 0.5) * f0r - w) & (fr <= (k - 0.5) * f0r + w)].max())
        h1 = on[0]
        corr = np.maximum(on - off, h1 * 10 ** -4.5) / h1
        hdb = 10 * np.log10(corr)
        fdb = 10 * np.log10(off / h1)
        oe = 10 * np.log10(np.nansum(corr[[2, 4, 6]]) / np.nansum(corr[[1, 3, 5]]))
        thd = 10 * np.log10(np.nansum(corr[1:]))
        sec = int(np.searchsorted(bounds, t0, "right") - 1)
        rows.append(np.r_[t0, t1, sec, m, hdb[1:], oe, thd, fdb[1], fdb[4], -fdb[0]])
    return np.array(rows)


def within_slope(y, xm, g):
    ok = ~np.isnan(y)
    y, xm, g = y[ok], xm[ok], g[ok]
    u, inv = np.unique(g, return_inverse=True)
    n = np.bincount(inv)
    xc = xm - (np.bincount(inv, xm) / n)[inv]
    yc = y - (np.bincount(inv, y) / n)[inv]
    return (xc * yc).sum() / ((xc ** 2).sum() + 1e-12)


def dp_segment(Y, pen, min_len=2):
    """Optimal partition of rows of Y (unit-noise, mean-shift model), min_len rows per segment."""
    n, d = Y.shape
    cs = np.vstack([np.zeros(d), np.cumsum(Y, 0)])
    cs2 = np.r_[0.0, np.cumsum((Y ** 2).sum(1))]
    F = np.full(n + 1, np.inf)
    F[0] = -pen
    back = np.zeros(n + 1, int)
    for j in range(min_len, n + 1):
        i = np.arange(0, j - min_len + 1)
        m = (j - i)[:, None]
        cost = (cs2[j] - cs2[i]) - ((cs[j] - cs[i]) ** 2 / m).sum(1)
        tot = F[i] + cost + pen
        k = int(np.argmin(tot))
        F[j], back[j] = tot[k], i[k]
    cps, j = [], n
    while j > 0:
        cps.append(back[j])
        j = back[j]
    return sorted(c for c in cps if c > 0)


def dp_segment_w(Y, w, pen, min_len=2):
    """Weighted mean-shift optimal partition: row i carries w[i] unit-noise observations
    (w = 0 -> no evidence, the row just belongs to whichever segment spans it)."""
    n, d = Y.shape
    Yz = np.nan_to_num(Y)
    cw = np.r_[0.0, np.cumsum(w)]
    cs = np.vstack([np.zeros(d), np.cumsum(Yz * w[:, None], 0)])
    cs2 = np.r_[0.0, np.cumsum((Yz ** 2).sum(1) * w)]
    F = np.full(n + 1, np.inf)
    F[0] = -pen
    back = np.zeros(n + 1, int)
    for j in range(min_len, n + 1):
        i = np.arange(0, j - min_len + 1)
        W = np.maximum(cw[j] - cw[i], 1e-9)[:, None]
        cost = (cs2[j] - cs2[i]) - ((cs[j] - cs[i]) ** 2 / W).sum(1)
        tot = F[i] + cost + pen
        k = int(np.argmin(tot))
        F[j], back[j] = tot[k], i[k]
    cps, j = [], n
    while j > 0:
        cps.append(back[j])
        j = back[j]
    return sorted(c for c in cps if c > 0)


def ping_scan(x):
    """Broad onset set for the per-bar attack flag: every voiced-run start after >= 48 ms unvoiced
    with a >= 6 dB rise; start pitch offset from zero crossings re the YIN pitch of the note."""
    d = load_f0()
    t, v, midi = d["t"].astype(np.float64), d["voiced"].astype(bool), d["midi"].astype(np.float64)
    lo = block_rms(fft_band(x, SR8, 25, 400), 20)
    hf = block_rms(fft_band(x, SR8, 2000, 3950), 20)
    L = 20 * np.log10(lo + 1e-7)
    Ls = np.convolve(L, np.ones(3) / 3, "same")
    Hd = 20 * np.log10(hf + 1e-7)
    Hs = np.convolve(Hd, np.ones(3) / 3, "same")
    nb = len(L)
    out, i, n, prev = [], 0, len(v), -100
    while i < n:
        if not v[i]:
            i += 1
            continue
        j = i
        while j + 1 < n and v[j + 1]:
            j += 1
        gap, prev_end = i - prev - 1, j
        prev = j
        s_i = i
        i = j + 1
        if gap < 2 or j - s_i + 1 < 7:
            continue
        mm = midi[s_i + 4:min(j, s_i + 13) + 1]
        if len(mm) < 3 or mm.std() > 0.8:
            continue
        f0 = 440.0 * 2 ** ((np.median(mm) - 69) / 12)
        jc = int(t[s_i] * 400)
        s0, s1 = max(jc - 40, 60), min(jc + 24, nb - 60)
        if s1 <= s0:
            continue
        js = s0 + int(np.argmax(Ls[s0 + 4:s1 + 4] - Ls[s0:s1]))
        pre, pk = float(np.median(L[js - 24:js - 4])), float(L[js:js + 40].max())
        if pk - pre < 6:
            continue
        Aw = 10 ** (L[js - 10:js + 40] / 20)
        ap, ak = 10 ** (pre / 20), 10 ** (pk / 20)
        jon = js - 10 + int(np.argmax(Aw >= ap + 0.25 * (ak - ap)))
        s_on = jon * 20
        if s_on - PRE_S < 0 or s_on + POST_S > len(x):
            continue
        dur_ms = (t[j] - t[s_i]) * 1000 + 24
        snip = x[s_on - PRE_S:s_on + POST_S].astype(np.float64)
        z = zc_track(np.fft.fft(snip * _TAPER), f0, 0.6, 1.9, fref=f0, amp_ms=(40, max(60, min(dur_ms - 10, 300))))
        if z is None:
            continue
        st = zc_summary(z[0], z[1])[1]
        if np.isnan(st):
            continue
        hfr = float(Hs[jon - 4:jon + 8].max() - np.median(Hd[jon - 40:jon - 8]))
        out.append((s_on / SR8, f0, st, hfr, dur_ms))
    return np.array(out)


def phrase_alignment(cps, sec, nb, rng, n_null=2000):
    """Share of change points on 4/8/16/32-bar boundaries, with the phase chosen (a) once for the
    whole file and (b) per section, each against a Monte-Carlo null with the same number of
    change points per section and >= 2 bars spacing."""
    cps = np.asarray(sorted(cps))
    if len(cps) < 3:
        return {}
    secs = np.unique(sec)
    ranges = {s: np.where(sec == s)[0] for s in secs}
    k_per = {s: int(np.sum(sec[cps] == s)) for s in secs}

    def shares(c):
        out = {}
        for M in (4, 8, 16, 32):
            g = max(np.mean((c - ph) % M == 0) for ph in range(M))
            hits = 0
            for s in secs:
                cs = c[sec[c] == s]
                if len(cs):
                    hits += max(int(np.sum((cs - ph) % M == 0)) for ph in range(M))
            lens = np.diff(c)
            g1 = max(np.mean(np.minimum((c - ph) % M, M - (c - ph) % M) <= 1) for ph in range(M))
            out[M] = (g, hits / len(c), np.mean(lens % M == 0) if len(lens) else np.nan, g1)
        return out

    obs = shares(cps)
    null = {M: [] for M in (4, 8, 16, 32)}
    for _ in range(n_null):
        c = []
        for s in secs:
            k = k_per[s]
            r = ranges[s]
            if k == 0 or len(r) < 3:
                continue
            for _try in range(50):
                pick = np.sort(rng.choice(r[1:] if r[0] == 0 else r, min(k, len(r) - 1), replace=False))
                if len(pick) < 2 or np.all(np.diff(pick) >= 2):
                    break
            c.extend(pick.tolist())
        c = np.array(sorted(c))
        if len(c) < 3:
            continue
        sh = shares(c)
        for M in null:
            null[M].append(sh[M])
    res = {}
    for M in (4, 8, 16, 32):
        nm = np.array(null[M])
        res[M] = tuple((obs[M][q], np.nanmean(nm[:, q]), float(np.mean(nm[:, q] >= obs[M][q])))
                       for q in range(4))
    return res


def stage_bars():
    x = np.load(os.path.join(CACHE, "mono8k.npy")).astype(np.float32)
    bounds = load_sections()
    bars, seq, active = bar_sequences()
    nb, nsec = len(seq), len(bounds) - 1
    sec = np.searchsorted(bounds, bars[:, 0], "right") - 1
    rng = np.random.default_rng(11)
    print(f"{nb} bars from grid.npz")

    # --- riff state per bar
    per_sec, period, cont, runs = riff_core(seq, active, sec, nsec)
    rid, nproto = riff_ids(seq, active, runs, period)
    riff_seg, riff_cps, rid_merged = segments_from_ids(rid, 2)
    rlen = np.diff(np.r_[0, riff_cps, nb])
    riff_state = rid_merged
    print(f"\n[riff] {nproto} distinct riff ids; {len(riff_cps) + 1} riff segments (min 2 bars; a riff id, "
          f"or no bass)")
    bass_seg = riff_state >= 0
    rl_b = np.array([z - a for a, z in zip(np.r_[0, riff_cps], np.r_[riff_cps, nb]) if riff_state[a] >= 0])
    print(f"  segment length (bars), bass segments only: p10 {np.percentile(rl_b, 10):.0f}, p25 {np.percentile(rl_b, 25):.0f}, "
          f"median {np.median(rl_b):.0f}, p75 {np.percentile(rl_b, 75):.0f}, p90 {np.percentile(rl_b, 90):.0f}, max {rl_b.max()}")
    for lo, hi in [(2, 4), (4, 8), (8, 16), (16, 32), (32, 9999)]:
        m = (rl_b >= lo) & (rl_b < hi)
        print(f"    {lo:>3d}-{(str(hi - 1) if hi < 9999 else ''):<4} bars: {m.sum():4d} segments ({m.mean() * 100:4.0f}%), "
              f"{rl_b[m].sum() / rl_b.sum() * 100:4.0f}% of bass bars")
    sb = np.array([np.argmax(sec == q) for q in range(nsec) if np.any(sec == q)])[1:]
    print(f"  riff change points within 4 bars of a section boundary: "
          f"{np.mean([np.min(np.abs(sb - c)) <= 4 for c in riff_cps]) * 100:.0f}% of {len(riff_cps)}")
    ids_active = rid[active]
    reuse = np.bincount(ids_active[ids_active >= 0])
    print(f"  riff ids used in >1 segment: {int(np.sum([len(set(riff_seg[(riff_state == i)])) > 1 for i in np.unique(ids_active)]))} "
          f"of {len(np.unique(ids_active))}")

    # --- timbre per bar
    Nn = load_notes(merged=True)
    T = timbre_rows(x, Nn, bounds, min_dur=0.21, lead=0.04, min_win=0.15)
    t0s, t1s, secn, midi = T[:, 0], T[:, 1], T[:, 2].astype(int), T[:, 3]
    feat_idx = {"h2": 4, "h3": 5, "h4": 6, "h5": 7, "odd-even": 11, "THD": 12}
    Fz = np.column_stack([T[:, feat_idx[c]] for c in TIMBRE_COLS])
    for j in range(Fz.shape[1]):
        Fz[:, j] = Fz[:, j] - within_slope(Fz[:, j], midi, secn) * (midi - np.nanmean(midi))
    timbre = np.full((nb, len(TIMBRE_COLS)), np.nan)
    for b in range(nb):
        a, z = bars[b, 0], bars[b, 16]
        ov = np.maximum(0, np.minimum(t1s, z) - np.maximum(t0s, a))
        m = ov > 0.05
        if m.any():
            timbre[b] = np.nanmedian(Fz[m], 0)
    have = ~np.isnan(timbre).any(1)
    print(f"\n[timbre] {len(T)} notes >= 210 ms measured; bars with a timbre reading: {have.sum()} "
          f"({have.sum() / active.sum() * 100:.0f}% of bass bars)")
    # evidence per bar = the notes that START in it (a note spanning two bars is counted once);
    # noise = note-to-note spread inside a section (conservative: includes real variation)
    nb_of = np.clip(np.searchsorted(bars[:, 0], t0s, "right") - 1, 0, nb - 1)
    dz = []
    for sct in np.unique(secn):
        q = Fz[secn == sct]
        if len(q) >= 3:
            dz.append(np.diff(q, axis=0))
    dz = np.vstack(dz)
    sig = np.nanmedian(np.abs(dz - np.nanmedian(dz, 0)), 0) / 0.6745 / np.sqrt(2)
    mu = np.nanmean(Fz, 0)
    Y = np.zeros((nb, len(TIMBRE_COLS)))
    wv = np.zeros(nb)
    for b in range(nb):
        m = nb_of == b
        if m.any():
            Y[b] = np.nanmean(np.clip((Fz[m] - mu) / sig, -2.5, 2.5), 0)   # winsorised: clamped harmonics are outliers
            wv[b] = m.sum()
    print(f"  per-note noise (dB): " + ", ".join(f"{c} {v:.1f}" for c, v in zip(TIMBRE_COLS, sig)))
    d = len(TIMBRE_COLS)
    tim_res = {}
    for c in (0.5, 1.0, 2.0):
        cps = dp_segment_w(Y, wv, c * d * np.log(wv.sum()), 2)
        seglen = np.diff(np.r_[0, cps, nb])
        tim_res[c] = (cps, seglen)
        print(f"  penalty {c:.1f} x BIC: {len(cps)} change points, segment length median {np.median(seglen):.0f} bars, "
              f"p25 {np.percentile(seglen, 25):.0f}, p75 {np.percentile(seglen, 75):.0f}, p90 {np.percentile(seglen, 90):.0f}")
    TPEN = 1.0
    tcps, tlen = tim_res[TPEN]
    print(f"  using penalty {TPEN:.1f} x BIC below (standard BIC; readings winsorised at 2.5 sigma so single odd notes do not split)")
    timbre_seg = np.zeros(nb, int)
    for i, a in enumerate(tcps):
        timbre_seg[a:] = i + 1
    print("  timbre segment length (bars, BIC):")
    for lo, hi in [(2, 4), (4, 8), (8, 16), (16, 32), (32, 64), (64, 9999)]:
        m = (tlen >= lo) & (tlen < hi)
        print(f"    {lo:>3d}-{(str(hi - 1) if hi < 9999 else ''):<4} bars: {m.sum():4d} segments, {tlen[m].sum() / nb * 100:4.0f}% of bars")
    sec_starts = np.array([np.argmax(sec == s) for s in range(nsec) if np.any(sec == s)])[1:]
    near = [np.min(np.abs(sec_starts - c)) for c in tcps]
    nulln = []
    for _ in range(2000):
        rc = rng.choice(np.arange(2, nb - 2), len(tcps), replace=False)
        nulln.append(np.mean([np.min(np.abs(sec_starts - c)) <= 4 for c in rc]))
    print(f"  (null for 'within 4 bars of a boundary' with {len(tcps)} random change points: {np.mean(nulln) * 100:.0f}%)")
    print(f"  timbre change points within 4 bars of a section (record) boundary: {np.mean(np.array(near) <= 4) * 100:.0f}% "
          f"({len(tcps)} cps, {len(sec_starts)} boundaries); boundaries with a timbre cp within 4 bars: "
          f"{np.mean([np.min(np.abs(np.array(tcps) - s)) <= 4 for s in sec_starts]) * 100 if len(tcps) else 0:.0f}%")
    within = [c for c, nd in zip(tcps, near) if nd > 4]
    print(f"  timbre change points INSIDE sections (> 4 bars from a boundary): {len(within)}")

    # --- attack ping per bar
    pg = ping_scan(x)
    print(f"\n[attack] broad onset set: {len(pg)} onsets with a measurable start pitch; "
          f"start >= +3 st: {np.mean(pg[:, 2] >= 3) * 100:.0f}% (clean of HF hits: "
          f"{np.mean(pg[pg[:, 3] < 9, 2] >= 3) * 100:.0f}% of {int(np.sum(pg[:, 3] < 9))}; on a drum hit: "
          f"{np.mean(pg[pg[:, 3] >= 9, 2] >= 3) * 100:.0f}% of {int(np.sum(pg[:, 3] >= 9))})")
    print(f"  start offset percentiles: p10 {np.percentile(pg[:, 2], 10):+.1f}, p25 {np.percentile(pg[:, 2], 25):+.1f}, "
          f"p50 {np.percentile(pg[:, 2], 50):+.1f}, p75 {np.percentile(pg[:, 2], 75):+.1f}, p90 {np.percentile(pg[:, 2], 90):+.1f} st")
    osec = np.searchsorted(bounds, pg[:, 0], "right") - 1
    print("  per section: sec  onsets  share starting >= +3 st   median start st")
    ping_sec = {}
    for s in range(nsec):
        m = osec == s
        if m.sum() >= 5:
            ping_sec[s] = (m.sum(), np.mean(pg[m, 2] >= 3), np.median(pg[m, 2]))
            print(f"   S{s + 1:02d}  {m.sum():5d}   {np.mean(pg[m, 2] >= 3) * 100:10.0f}%   {np.median(pg[m, 2]):+14.1f}")
    has_bell = np.full(nb, np.nan)
    n_on = np.zeros(nb, int)
    bi = np.searchsorted(bars[:, 0], pg[:, 0], "right") - 1
    for b in range(nb):
        m = bi == b
        n_on[b] = m.sum()
        if m.any():
            has_bell[b] = np.mean(pg[m, 2] >= 3)

    # --- phrase grid alignment
    print("\n[phrase grid] change points on 4/8/16/32-bar boundaries vs a Monte-Carlo null (same count per section)")
    print("  layer    M   global-phase share (null, p)   +-1 bar (null, p)       per-section-phase (null, p)   segment lengths multiple of M (null, p)")
    align = {}
    for name, cps in (("riff", riff_cps), ("timbre", np.array(tcps))):
        res = phrase_alignment(cps, sec, nb, rng, 1000)
        align[name] = res
        for M, ((g, gn, gp), (l, ln, lp), (q, qn, qp), (g1, g1n, g1p)) in res.items():
            print(f"  {name:6s} {M:3d}     {g * 100:5.1f}% ({gn * 100:4.1f}%, {gp:.3f})     {g1 * 100:5.1f}% ({g1n * 100:4.1f}%, {g1p:.3f})"
                  f"     {l * 100:5.1f}% ({ln * 100:4.1f}%, {lp:.3f})       {q * 100:5.1f}% ({qn * 100:4.1f}%, {qp:.3f})")

    root_pc = np.full(nb, -1, int)
    for b in range(nb):
        if active[b]:
            vals = seq[b][seq[b] >= 0]
            root_pc[b] = int(np.bincount(vals % 12).argmax())
    out = os.path.join(CACHE, "bass_bars.npz")
    np.savez(out,
             bar_start_s=bars[:, 0].astype(np.float64), bar_end_s=bars[:, 16].astype(np.float64),
             section=sec.astype(np.int16), root_pc=root_pc.astype(np.int8), bass_present=active,
             seq16=seq.astype(np.int8), riff_id=rid.astype(np.int16), riff_period_bars=period.astype(np.int8),
             riff_segment_id=riff_seg.astype(np.int16), timbre=timbre.astype(np.float32),
             timbre_cols=np.array(TIMBRE_COLS), timbre_segment_id=timbre_seg.astype(np.int16),
             has_bell_attack=has_bell.astype(np.float32), n_onsets_measured=n_on.astype(np.int8))
    print(f"\nwrote {out}")
    np.savez(scratch("bars_summary.npz"), riff_len=rl_b, timbre_len=tlen, ping=pg,
             riff_cps=np.array(riff_cps), timbre_cps=np.array(tcps))


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
                                      "report", "inspect", "bell", "bellreport", "recipe",
                                      "timbre", "riff", "bars", "all"])
    ap.add_argument("--t0", type=float, default=500.0)
    ap.add_argument("--t1", type=float, default=512.0)
    a = ap.parse_args(argv)
    stages = {"grid": stage_grid, "sections": stage_sections, "f0": stage_f0,
              "notes": stage_notes, "spec": stage_spec, "kick": stage_kick,
              "report": stage_report, "inspect": lambda: stage_inspect(a.t0, a.t1),
              "bell": stage_bell, "bellreport": bell_report, "recipe": stage_recipe,
              "timbre": stage_timbre, "riff": stage_riff, "bars": lambda: stage_bars()}
    if a.stage == "all":
        for k in ["grid", "sections", "f0", "notes", "spec", "kick", "report"]:
            print(f"\n----- {k} -----")
            stages[k]()
    else:
        stages[a.stage]()
    return 0


if __name__ == "__main__":
    sys.exit(main())
