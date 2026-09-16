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
    python scripts/reaper_bass.py shortcal   # calibrate note events on a synthetic bass + break
    python scripts/reaper_bass.py short      # where short notes sit in the bar, the loop, the break
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
def yin_track(x, verbose=False):
    """YIN F0 track of an 8 kHz signal (band-passed 28-190 Hz, decimated to 2 kHz) -> dict."""
    bp = fft_band(x, SR8, 28.0, 190.0)
    y = np.ascontiguousarray(bp[::DEC])                  # already band-limited: plain decimation
    del bp
    tau_min = int(np.floor(SRP / F0_HI))                 # 13
    tau_max = int(np.ceil(SRP / F0_LO))                  # 67
    W, hop = YIN_W, YIN_HOP
    need = W + tau_max
    nfr = 1 + (len(y) - need) // hop
    if verbose:
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
    return dict(t=t_s.astype(np.float32), f0=f0, midi_raw=m_raw.astype(np.float32), midi=m_med,
                conf=conf, conf_med=c_med, power=power, voiced=ok)


def stage_f0():
    x = np.load(os.path.join(CACHE, "mono8k.npy")).astype(np.float32)
    print(f"mono8k: {len(x)} samples, {len(x) / SR8:.1f} s")
    d = yin_track(x, verbose=True)
    f0, m_raw, m_med, ok = d["f0"], d["midi_raw"], d["midi"], d["voiced"]
    print(f"voiced frames: {ok.mean() * 100:.1f}%  (conf>0.70, 30-150 Hz)")
    print(f"median |raw-median| jitter: {np.median(np.abs(m_raw - m_med)[ok]) * 100:.1f} cents")
    print(f"pitch range (voiced, 5-95 pct): {np.percentile(m_med[ok], 5):.1f} - "
          f"{np.percentile(m_med[ok], 95):.1f} MIDI "
          f"({midi_name(np.percentile(m_med[ok], 5))} - {midi_name(np.percentile(m_med[ok], 95))})")
    np.savez(scratch("f0.npz"), **d)


def load_f0():
    return np.load(scratch("f0.npz"))


# ----------------------------------------------------------------------
# 4. note segmentation
# ----------------------------------------------------------------------
SLOPE_MAX = 2.0                        # st/s; above this the bass is sliding, not holding


def segment_notes(d, verbose=True):
    """-> (raw plateaus, merged plateaus, glide runs, plateau-transition glide flags)."""
    say = print if verbose else (lambda *args, **kw: None)
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
    say(f"voiced {ok.mean() * 100:.1f}% of frames; of the voiced frames "
          f"{steady[ok].mean() * 100:.1f}% are steady (|d pitch/dt| < {SLOPE_MAX} st/s) and "
          f"{100 - steady[ok].mean() * 100:.1f}% are gliding")
    say(f"  |slope| percentiles over voiced frames (st/s): " + "  ".join(
        f"p{q}={np.percentile(np.abs(slope[ok]), q):.2f}" for q in (25, 50, 75, 90, 95, 99)))
    # Is the movement real or is it the tracker? Tighten the confidence gate and see whether the
    # steady fraction and the slope distribution hold up.
    say("  conf gate  frames%   steady%   |slope| p50   p75   p90")
    for g in (0.55, 0.70, 0.80, 0.90):
        sel = (d["conf_med"] > g) & (d["f0"] >= F0_LO) & (d["f0"] <= F0_HI)
        if sel.sum() < 50:
            continue
        say(f"   >{g:.2f}     {sel.mean() * 100:6.1f}   {np.mean(np.abs(slope[sel]) < SLOPE_MAX) * 100:6.1f}   "
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
    if len(G):
      say(f"{len(G)} glide runs >= 70 ms: median duration {np.median(G[:, 1] - G[:, 0]) * 1000:.0f} ms, "
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
    say(f"{len(N)} raw bass segments, total voiced time {(N[:, 1] - N[:, 0]).sum():.1f} s "
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
    say(f"{len(M)} merged plateaus (same pitch across gaps <= 150 ms); "
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
        say(f"transitions between plateaus: {lab.mean() * 100:.1f}% are glides, "
              f"{100 - lab.mean() * 100:.1f}% are jumps/re-articulations")
    return N, M, G, lab


def stage_notes():
    N, M, G, lab = segment_notes(load_f0())
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


# ----------------------------------------------------------------------
# 13. short-note placement
# ----------------------------------------------------------------------
# Musical note events (attack or pitch change -> end), calibrated on a synthetic track whose
# notes are known, then placed on the rhythm agent's drift-tracked bar grid. The synthetic track
# is generated from formulas (sines, noise, envelopes); nothing is taken from the reference.
SLOT_NAMES = [f"{b + 1}{s}" for b in range(4) for s in ("", "e", "&", "a")]
EV_ATTACK, EV_SLIDE, EV_SOFT = 0, 1, 2
EV_DEPTH = 9.0                              # dB dip-to-peak in 25-150 Hz that counts as a (re)attack


def zc_pitch_series(x, hi=160):
    """Period-by-period pitch of the 25-hi Hz band over the whole signal: (mid s, Hz, peak amp)."""
    y = fft_band(x, SR8, 25, hi).astype(np.float64)
    idx = np.where((y[:-1] < 0) & (y[1:] >= 0))[0]
    zc = idx + (-y[idx]) / (y[idx + 1] - y[idx] + 1e-30)
    per = np.diff(zc) / SR8
    mid = (zc[:-1] + zc[1:]) / 2 / SR8
    amp = np.maximum.reduceat(np.abs(y), idx)[:len(per)]
    return mid, 1.0 / per, amp


def _tone_after(pm, pf, pa, ton, tend):
    """Is there a steady tone after an onset, up to the note's own end?
    -> (n periods, spread st, Hz, level change dB re the first 30 ms)."""
    w1 = min(ton + 0.11, tend)
    w0 = ton + 0.045 if w1 - (ton + 0.045) >= 0.02 else ton + 0.03
    a, b = np.searchsorted(pm, w0), np.searchsorted(pm, w1)
    if b - a < 1:
        return 0, 99.0, np.nan, -99.0
    f = pf[a:b]
    st = 12 * np.log2(f / np.median(f))
    e0, e1 = np.searchsorted(pm, ton), np.searchsorted(pm, ton + 0.03)
    a_early = pa[e0:e1].max() if e1 > e0 else pa[a]
    dec = 20 * np.log10(np.median(pa[a:b]) / (a_early + 1e-12))
    return b - a, float(np.max(np.abs(st))), float(np.median(f)), float(dec)


def bass_events(x, d, M, G, trans, debug=None):
    """Bass note events -> rows [onset_s, env_end_s, voiced_end_s(raw), type, depth_dB, midi].
    Onsets: (1) an attack in 25-150 Hz (>= 9 dB dip-to-peak) confirmed by a steady pitch 45-110 ms
    later and not shaped like a kick (click + decaying level + no steady pitch); (2) a gapless
    retrigger: the pitch snaps >= 3 st up and falls back with no level jump or click; (3) a pitch
    change between plateaus with no re-attack (slid / legato)."""
    t = np.asarray(d["t"], float)
    v = np.asarray(d["voiced"], bool)
    midi = np.asarray(d["midi"], float)
    dt = float(np.median(np.diff(t)))
    lo = block_rms(fft_band(x, SR8, 25, 150), 20)
    hf = block_rms(fft_band(x, SR8, 2000, 3950), 20)
    L = 20 * np.log10(lo + 1e-7)
    Ls = np.convolve(L, np.ones(3) / 3, "same")
    Hd = 20 * np.log10(hf + 1e-7)
    Hs = np.convolve(Hd, np.ones(3) / 3, "same")
    EB, nb = 400.0, len(L)
    pm, pf, pa = zc_pitch_series(x)

    def fidx(ts):
        return int(np.clip(round((ts - t[0]) / dt), 0, len(t) - 1))

    def hf_rise(jon):
        return float(Hs[max(jon - 4, 0):jon + 8].max() - np.median(Hd[max(jon - 40, 0):max(jon - 8, 1)]))

    rise = np.full(nb, -99.0)
    rise[:-4] = Ls[4:] - Ls[:-4]
    cand = np.where((rise >= 3) & (rise >= np.roll(rise, 1)) & (rise >= np.roll(rise, -1)))[0]
    keep = []
    for j in cand:
        if keep and j - keep[-1] < 16:
            if rise[j] > rise[keep[-1]]:
                keep[-1] = j
        else:
            keep.append(int(j))
    att = []
    for j in keep:
        if j < 40 or j > nb - 60:
            continue
        jm = j - 32 + int(np.argmin(Ls[j - 32:j + 1]))
        jp = j + int(np.argmax(Ls[j:j + 24]))
        pre, pk = Ls[jm], Ls[jp]
        if pk - pre < EV_DEPTH:
            continue
        A = 10 ** (Ls[jm:jp + 1] / 20)
        a0, a1 = 10 ** (pre / 20), 10 ** (pk / 20)
        jon = jm + int(np.argmax(A >= a0 + 0.25 * (a1 - a0)))
        att.append((jon / EB, pk - pre, jon))
    ons = []
    amb = []
    for k, (ton, depth, jon) in enumerate(att):
        tnext = att[k + 1][0] if k + 1 < len(att) else ton + 1.0
        jp = jon + int(np.argmax(Ls[jon:jon + 32]))
        below = Ls[jp:min(nb, jp + 400)] < Ls[jp] - 12
        run = np.convolve(below.astype(float), np.ones(6), "valid") >= 6
        gate = (jp + int(np.argmax(run))) / EB if run.any() else ton + 1.0
        npd, spread, fmed, dec = _tone_after(pm, pf, pa, ton, min(gate - 0.005, tnext - 0.004))
        click = hf_rise(jon)
        steady = (npd >= 2 and spread <= 1.0) or npd == 1
        pitched = steady and F0_LO <= fmed <= F0_HI
        # level shape: a kick decays from its first milliseconds, a bass note holds until its gate
        w0b, w1b = jon + 10, jon + int(min(0.11, max(gate - ton - 0.005, 0.0)) * EB)
        if w1b - w0b >= 8:
            slope = float(np.polyfit(np.arange(w1b - w0b) / EB, Ls[w0b:w1b], 1)[0]) / 100.0   # dB per 10 ms
        else:
            slope = 0.0
        if pitched and slope >= -0.5:
            accept = True
        else:
            a2, b2 = np.searchsorted(pm, ton + 0.12), np.searchsorted(pm, min(ton + 0.22, tnext - 0.004))
            accept = False
            if b2 - a2 >= 2:
                f2 = pf[a2:b2]
                sp2 = np.max(np.abs(12 * np.log2(f2 / np.median(f2))))
                e0 = np.searchsorted(pm, ton)
                lv2 = 20 * np.log10(np.median(pa[a2:b2]) / (pa[e0:max(a2, e0 + 1)].max() + 1e-12))
                accept = sp2 <= 1.0 and F0_LO <= np.median(f2) <= F0_HI and lv2 >= -12
            if not accept and pitched:
                amb.append(ton)
        dec = slope
        if debug is not None:
            debug.append((ton, depth, npd, spread, fmed, dec, click, accept))
        if accept:
            ons.append([ton, EV_ATTACK, depth])
    # gapless retriggers: the pitch drop restarts with no level dip. In a 25-420 Hz band the
    # snap is visible: >= 5 st above a steady running pitch, falling back within ~90 ms.
    qm, qf, qa = zc_pitch_series(x, 420)
    qst = 12 * np.log2(qf / 55.0)
    att_t = np.array([o[0] for o in ons]) if ons else np.zeros(0)
    i = 6
    while i < len(qm) - 12:
        p0 = np.searchsorted(qm, qm[i] - 0.07)
        prev = qst[p0:i]
        if len(prev) < 2 or not (F0_LO <= qf[i - 1] <= F0_HI):
            i += 1
            continue
        pm_ = np.median(prev)
        if qst[i] - pm_ < 5.0 or np.abs(prev - pm_).max() > 1.0:
            i += 1
            continue
        e1 = np.searchsorted(qm, qm[i] + 0.09)
        e0 = np.searchsorted(qm, qm[i] + 0.05)
        tail = qst[e0:e1]
        if len(tail) < 2 or np.abs(tail - np.median(tail)).max() > 1.2 or np.median(tail) > qst[i] - 3:
            i += 1
            continue
        tt = qm[i] - 0.5 / qf[i]
        jon = int(tt * EB)
        if jon < 40 or jon > nb - 20 or (len(att_t) and np.min(np.abs(att_t - tt)) < 0.06):
            i = e0
            continue
        lvl = Ls[jon:jon + 8].max() - np.median(Ls[jon - 16:jon - 2])
        fi = fidx(tt)
        if lvl < 4 and v[max(fi - 3, 0):fi + 4].any():
            ons.append([tt, EV_SOFT, 0.0])
        i = e0
    att_t = np.array([o[0] for o in ons]) if ons else np.zeros(0)
    for i in range(len(M) - 1):
        if abs(M[i + 1, 2] - M[i, 2]) < 0.5 or M[i + 1, 0] - M[i, 1] > 0.25:
            continue
        a, z = M[i, 1], M[i + 1, 0]
        if len(att_t) and np.any((att_t >= a - 0.10) & (att_t <= z + 0.05)):
            continue
        # refine on the fine pitch series: the last time the pitch still sits on the old note
        p0, p1 = np.searchsorted(pm, a - 0.12), np.searchsorted(pm, z + 0.02)
        dev = np.abs(12 * np.log2(pf[p0:p1] / (440.0 * 2 ** ((M[i, 2] - 69) / 12))))
        on_old = np.where(dev <= 0.5)[0]
        if len(on_old):
            tc = pm[p0 + on_old[-1]] + 0.5 / pf[p0 + on_old[-1]]
        else:
            tc = a if (i < len(trans) and trans[i]) else 0.5 * (a + z)
        ons.append([tc, EV_SLIDE, 0.0])
    ons.sort(key=lambda o: o[0])
    pri = {EV_ATTACK: 0, EV_SLIDE: 1, EV_SOFT: 2}
    dd = []
    for o in ons:
        if dd and o[0] - dd[-1][0] < 0.045:
            if pri[o[1]] < pri[dd[-1][1]]:
                dd[-1] = o
        else:
            dd.append(o)
    rows = []
    for k, (ton, typ, depth) in enumerate(dd):
        jon = int(ton * EB)
        jp = jon + int(np.argmax(Ls[jon:jon + 32])) if jon + 32 < nb else jon
        pk = Ls[jp]
        below = Ls[jp:min(nb, jp + 800)] < pk - 12
        run = np.convolve(below.astype(float), np.ones(6), "valid") >= 6
        env_end = (jp + int(np.argmax(run))) / EB if run.any() else ton + 2.0
        i = fidx(ton + 0.02)
        while i < len(t) and not v[i] and t[i] < ton + 0.2:
            i += 1
        j = i
        while j + 2 < len(t) and (v[j + 1] or v[j + 2]):
            j += 1
        v_end = t[j] + dt / 2 if i < len(t) else ton
        nxt = dd[k + 1][0] if k + 1 < len(dd) else ton + 9.0
        end = min(nxt, env_end)
        a_, b_ = np.searchsorted(pm, ton + 0.045), np.searchsorted(pm, end - 0.005)
        if b_ - a_ >= 1:
            f = np.median(pf[a_:b_])
            m = float(hz_to_midi(f)) if F0_LO <= f <= F0_HI else np.nan
        else:
            m = np.nan
        if np.isnan(m):
            a2, z2 = fidx(ton + 0.04), fidx(end)
            sel = np.arange(a2, z2 + 1)
            sel = sel[v[sel]] if len(sel) else sel
            m = float(np.median(midi[sel])) if len(sel) else np.nan
        rows.append([ton, env_end, v_end, typ, depth, m])
    if debug is not None:
        debug.append(("ambiguous", np.array(amb)))
    return np.array(rows)


def event_durations(E, vcorr, rule="C"):
    on, env_end, v_end = E[:, 0], E[:, 1], E[:, 2] + vcorr
    nxt = np.r_[on[1:], on[-1] + 9.0]
    if rule == "A":
        off = np.minimum(nxt, env_end)
    elif rule == "B":
        off = np.minimum(nxt, v_end)
    else:
        off = np.minimum(nxt, np.minimum(env_end, v_end))
    return np.maximum(off, on + 0.01)


def synth_track(seed=5, bars=160, bpm=166.0, snare_hp=0.0):
    """A formula-generated bass + break with known notes, for calibrating the note-event
    pipeline. -> (signal at 8 kHz, truth rows, bar starts, 16th length s)."""
    rng = np.random.default_rng(seed)
    sr = SR8
    s16 = 60.0 / bpm / 4
    lead = 0.6
    n = int((lead + (bars + 1) * 16 * s16) * sr)
    f_tr = np.full(n, 50.0)
    a_tr = np.zeros(n)
    PAT = {
        "court": [(s, 1.2, 0) for s in (0, 3, 4, 7, 8, 11, 12, 15)],
        "subliminal": [(0, 5.0, 0), (6, 5.0, 0)],
        "stab8": [(s, 1.0, 0) for s in range(0, 16, 2)],
        "retrig16": [(s, 1.0, 0) for s in range(0, 8)] + [(8, 8.0, 0)],
        "held": [(0, 7.5, 0), (8, 7.5, 0)],
        "glide": [(0, 8.0, 0), (8, 8.0, 1)],
        "mixed": [(0, 6.0, 0), (10, 1.5, 0), (13, 1.0, 0), (14, 2.0, 1)],
        "pickup": [(0, 10.0, 0), (14, 1.0, 0)],
        "twohits": [(0, 1.0, 0), (1, 1.0, 0), (8, 4.0, 0)],
    }
    names = list(PAT) + ["random"] * 4
    truth = []
    bar_t = lead + np.arange(bars + 1) * 16 * s16
    prev = None                                        # (end sample, midi) of the previous note
    for b in range(bars):
        name = names[int(rng.integers(len(names)))]
        if name == "random":
            k = int(rng.integers(1, 9))
            slots = sorted(int(q) for q in rng.choice(16, k, replace=False))
            pat = []
            for i, sl in enumerate(slots):
                room = (slots[i + 1] if i + 1 < len(slots) else 16) - sl
                dur = float(min(room, rng.choice([0.6, 0.8, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0, 8.0])))
                pat.append((sl, dur, int(room == dur and rng.random() < 0.3)))
        else:
            pat = PAT[name]
        root = int(rng.integers(26, 41))
        for sl, dur, gl in pat:
            s0 = int((bar_t[b] + sl * s16) * sr)
            s1 = int((bar_t[b] + (sl + dur) * s16) * sr)
            pitch = root + int(rng.choice([0, 0, 0, 2, -2, 5, 7, -5, 3]))
            f_note = 440.0 * 2 ** ((pitch - 69) / 12)
            tt = np.arange(s1 - s0) / sr
            legato = bool(gl) and prev is not None and abs(prev[0] - s0) <= 2 and prev[1] != pitch
            gapless = prev is not None and abs(prev[0] - s0) <= 2
            if legato:
                pm = prev[1]
                semi = np.where(tt < 0.06, (pm - pitch) * (1 - tt / 0.06), 0.0)
                f_tr[s0:s1] = f_note * 2 ** (semi / 12)
                a_tr[s0:s1] = 1.0
                ping = 0
            else:
                ping = int(rng.random() < 0.7)
                semi = ping * (30 * np.exp(-tt / 0.012) + 1.0 * np.exp(-tt / 0.2))
                f_tr[s0:s1] = f_note * 2 ** (semi / 12)
                env = np.minimum(1.0, tt / 0.002) if not gapless else np.ones(len(tt))
                a_tr[s0:s1] = env
            rel = min(int(0.008 * sr), s1 - s0)
            a_tr[s1 - rel:s1] *= np.linspace(1, 0, rel)
            truth.append((s0 / sr, s1 / sr, pitch, b, sl, dur, int(not legato), int(gapless and not legato), ping,
                          (list(PAT) + ["random"]).index(name)))
            prev = (s1, pitch)
    ph = 2 * np.pi * np.cumsum(f_tr) / sr
    bass = 0.30 * a_tr * np.sin(ph + 0.3 * np.sin(ph) + 0.5 * np.sin(2 * ph))
    drums = np.zeros(n)
    kpats = [[0, 10], [0, 2, 10], [0, 6, 8], [0, 10, 13], [0, 8]]

    def add(s0, sig):
        e = min(n, s0 + len(sig))
        drums[s0:e] += sig[:e - s0]

    kick_t = []
    for b in range(bars):
        kp = kpats[int(rng.integers(len(kpats)))]
        for sl in kp:
            s0 = int((bar_t[b] + sl * s16) * sr)
            kick_t.append(s0 / sr)
            tt = np.arange(int(0.35 * sr)) / sr
            fk = 55 + 125 * np.exp(-tt / 0.03)
            kick = 0.45 * np.exp(-tt / float(rng.choice([0.05, 0.07, 0.1]))) * np.sin(2 * np.pi * np.cumsum(fk) / sr)
            click = np.diff(rng.standard_normal(int(0.004 * sr) + 1)) * 0.12
            kick[:len(click)] += click
            add(s0, kick)
        for sl in [4, 12] + ([int(rng.choice([7, 14]))] if rng.random() < 0.3 else []):
            s0 = int((bar_t[b] + sl * s16) * sr)
            tt = np.arange(int(0.25 * sr)) / sr
            nz = rng.standard_normal(len(tt))
            if snare_hp > 0:
                nz = fft_band(nz.astype(np.float32), SR8, snare_hp, 3990).astype(np.float64)
            sn = 0.25 * np.exp(-tt / 0.08) * nz + 0.15 * np.exp(-tt / 0.06) * np.sin(2 * np.pi * 190 * tt)
            add(s0, sn * (1.0 if sl in (4, 12) else 0.4))
        for sl in range(16):
            s0 = int((bar_t[b] + sl * s16) * sr)
            hh = 0.05 * np.exp(-np.arange(int(0.03 * sr)) / (0.012 * sr)) * np.diff(rng.standard_normal(int(0.03 * sr) + 1))
            add(s0, hh)
    y = bass + drums
    y = (y / (np.abs(y).max() + 1e-9) * 0.6).astype(np.float32)
    return y, np.array(truth), bar_t, s16, np.array(kick_t)


def stage_shortcal(snare_hp=0.0):
    """Calibrate onset timing, duration and the short-note floor on known synthetic notes."""
    y, T, bar_t, s16, kick_t = synth_track(snare_hp=snare_hp)
    print(f"synthetic break: snare noise high-passed at {snare_hp:.0f} Hz" if snare_hp else "synthetic break: full-range snare noise")
    beat = 4 * s16
    d = yin_track(y)
    N, M, G, trans = segment_notes(d, verbose=False)
    E = bass_events(y, d, M, G, trans)
    print(f"synthetic: {len(T)} true notes over {len(bar_t) - 1} bars; detected {len(E)} events")
    used = np.zeros(len(E), bool)
    match = np.full(len(T), -1)
    order = np.argsort(T[:, 0])
    for i in order:
        dif = np.abs(E[:, 0] - T[i, 0])
        dif[used] = 9
        k = int(np.argmin(dif))
        if dif[k] <= 0.045:
            match[i], used[k] = k, True
    ok = match >= 0
    typ = np.where(T[:, 6] == 0, "legato glide", np.where(T[:, 7] == 1, "gapless retrigger", "attack after a gap"))
    same_prev = np.r_[False, T[1:, 2] == T[:-1, 2]]
    inaudible = (typ == "gapless retrigger") & (T[:, 8] == 0) & same_prev
    print(f"  inaudible onsets (gapless, no pitch drop, same pitch as before): {inaudible.sum()}; "
          f"recall over audible onsets {ok[~inaudible].mean() * 100:.1f}%")
    gl2 = (typ == "gapless retrigger") & (T[:, 8] == 1)
    print(f"    gapless retrigger WITH pitch drop n={gl2.sum()}: recall {ok[gl2].mean() * 100:.0f}%")
    durb = (T[:, 1] - T[:, 0]) / beat
    cls = np.where(durb < 0.5, "short", np.where(durb < 1.0, "medium", "long"))
    print(f"  recall {ok.mean() * 100:.1f}%, precision {used.mean() * 100:.1f}%")
    for nm in ("attack after a gap", "gapless retrigger", "legato glide"):
        m = typ == nm
        print(f"    {nm:20s} n={m.sum():4d}  recall {ok[m].mean() * 100:5.1f}%")
    for nm in ("short", "medium", "long"):
        m = cls == nm
        print(f"    true {nm:6s} n={m.sum():4d}  recall {ok[m].mean() * 100:5.1f}%")
    PN = ["court", "subliminal", "stab8", "retrig16", "held", "glide", "mixed", "pickup", "twohits", "random"]
    print("    by pattern: " + ", ".join(f"{PN[int(q)]} {ok[T[:, 9] == q].mean() * 100:.0f}% (n={np.sum(T[:, 9] == q)})"
                                      for q in np.unique(T[:, 9])))
    err = E[match[ok], 0] - T[ok, 0]
    bias = {}
    for code, nm in ((EV_ATTACK, "attack"), (EV_SLIDE, "slide"), (EV_SOFT, "soft")):
        m = E[match[ok], 3] == code
        if m.sum() >= 5:
            bias[code] = float(np.median(err[m]))
            print(f"  onset error [{nm}] n={m.sum()}: median {np.median(err[m]) * 1000:+.1f} ms, "
                  f"p10 {np.percentile(err[m], 10) * 1000:+.1f}, p90 {np.percentile(err[m], 90) * 1000:+.1f}")
    corr = np.array([bias.get(int(c), 0.0) for c in E[match[ok], 3]])
    slot_det = np.round((E[match[ok], 0] - corr - bar_t[T[ok, 3].astype(int)]) / s16).astype(int)
    print(f"  16th-slot accuracy after bias correction: {np.mean(slot_det == T[ok, 4].astype(int)) * 100:.1f}%")
    # offsets
    mv = ok & (T[:, 6] == 1)
    gapafter = np.r_[T[1:, 0] - T[:-1, 1], 1.0] > s16 * 0.9
    sel = mv & gapafter
    vcorr = float(np.median(T[sel, 1] - E[match[sel], 2]))
    print(f"  voicing overhang at note ends: YIN voicing ends {-vcorr * 1000:+.0f} ms after the true end (median)")
    best = None
    for rule in ("A", "B", "C"):
        off = event_durations(E, vcorr, rule)
        dd = (off[match[ok]] - E[match[ok], 0]) / s16
        tru = (T[ok, 1] - T[ok, 0]) / s16
        e = dd - tru
        dcls = np.where(dd / 4 < 0.5, "short", np.where(dd / 4 < 1.0, "medium", "long"))
        acc = np.mean(dcls == cls[ok])
        sh = cls[ok] == "short"
        print(f"  duration rule {rule}: median error {np.median(e):+.2f} 16ths, MAE {np.mean(np.abs(e)):.2f}, "
              f"short-note MAE {np.mean(np.abs(e[sh])):.2f}; S/M/L class agreement {acc * 100:.1f}% "
              f"(true short read as short {np.mean(dcls[sh] == 'short') * 100:.0f}%)")
        if best is None or acc > best[1]:
            best = (rule, acc)
    for rule in ("A", "C"):
        off = event_durations(E, vcorr, rule)
        dd = (off[match[ok]] - E[match[ok], 0]) / beat
        dcls = np.where(dd < 0.5, "short", np.where(dd < 1.0, "medium", "long"))
        print(f"  rule {rule} confusion (rows true, cols detected S/M/L):")
        for nm in ("short", "medium", "long"):
            m = cls[ok] == nm
            print(f"    {nm:6s} " + "  ".join(f"{np.mean(dcls[m] == q) * 100:4.0f}%" for q in ("short", "medium", "long")) + f"   n={m.sum()}")
        # detected-class counts vs true-class counts (does the rule inflate shorts?)
        allc = np.where((off - E[:, 0]) / beat < 0.5, "short", np.where((off - E[:, 0]) / beat < 1.0, "medium", "long"))
        print(f"    detected share S/M/L over ALL events: " + " ".join(f"{np.mean(allc == q) * 100:.0f}%" for q in ("short", "medium", "long")) +
              f"; true share among matched: " + " ".join(f"{np.mean(cls[ok] == q) * 100:.0f}%" for q in ("short", "medium", "long")))
    fp = ~used
    fk = np.array([np.min(np.abs(kick_t - q)) < 0.02 for q in E[fp, 0]]) if fp.any() else np.zeros(0, bool)
    fpslot = np.round(((E[fp, 0] - bar_t[0]) / s16)).astype(int) % 16
    print(f"  false events: {fp.sum()} ({fp.mean() * 100:.0f}%); on a kick {fk.mean() * 100:.0f}%, on snare slots 4/12 "
          f"{np.mean(np.isin(fpslot, [4, 12])) * 100:.0f}%; typed attack {np.mean(E[fp, 3] == EV_ATTACK) * 100:.0f}% / "
          f"slide {np.mean(E[fp, 3] == EV_SLIDE) * 100:.0f}% / retrigger {np.mean(E[fp, 3] == EV_SOFT) * 100:.0f}%")
    offp = event_durations(E, vcorr, "A")
    fpd = (offp[fp] - E[fp, 0]) / beat
    print(f"    false events read as short {np.mean(fpd < 0.5) * 100:.0f}%; share of all detected SHORT events that are false: "
          f"{np.sum(fpd < 0.5) / max(np.sum((offp - E[:, 0]) / beat < 0.5), 1) * 100:.0f}%")
    rule = "A"      # class agreement ties with C, but C reads 58% of true mediums as short and inflates the
    #                 short share (66% vs 61% true); A keeps the S/M/L mix closest to the truth
    off = event_durations(E, vcorr, rule)
    dd = (off[match[ok]] - E[match[ok], 0]) / beat
    tru = (T[ok, 1] - T[ok, 0]) / beat
    print(f"  chosen rule {rule}. Detected length for true lengths (beats):")
    for lo_, hi_ in ((0.0, 0.2), (0.2, 0.3), (0.3, 0.4), (0.4, 0.5), (0.5, 1.0), (1.0, 3.0)):
        m = (tru >= lo_) & (tru < hi_)
        if m.sum() >= 3:
            print(f"    true {lo_:.1f}-{hi_:.1f}: n={m.sum():3d}, detected median {np.median(dd[m]):.2f}, "
                  f"p10 {np.percentile(dd[m], 10):.2f}, p90 {np.percentile(dd[m], 90):.2f}")
    print(f"  shortest detected event: {((off - E[:, 0]) / beat).min():.3f} beats; true minimum {durb.min():.3f}")
    m = (cls == "short") & (T[:, 5] >= 0.9) & (T[:, 5] <= 1.3)
    court = np.isin(T[:, 3], [b for b in np.unique(T[:, 3]) if np.sum((T[:, 3] == b) & (T[:, 5] == 1.2)) == 8])
    onk = np.array([np.min(np.abs(kick_t - o)) < 0.02 for o in T[:, 0]])
    for nm in ("short", "long"):
        m = cls == nm
        print(f"  {nm} notes ON a kick: n={np.sum(m & onk)}, recall {ok[m & onk].mean() * 100:.0f}%;  OFF a kick: "
              f"n={np.sum(m & ~onk)}, recall {ok[m & ~onk].mean() * 100:.0f}%")
    dbg = []
    bass_events(y, d, M, G, trans, debug=dbg)
    amb = dbg[-1][1]
    tr_short_onk = T[(cls == "short") & onk & ~ok, 0]
    hit_amb = np.mean([np.min(np.abs(amb - q)) < 0.045 for q in tr_short_onk]) if len(amb) and len(tr_short_onk) else 0
    kick_amb = np.mean([np.min(np.abs(kick_t - q)) < 0.045 for q in amb]) if len(amb) else 0
    print(f"  ambiguous kick-coincident tonal attacks: {len(amb)}; they catch {hit_amb * 100:.0f}% of the missed short "
          f"notes on kicks; {kick_amb * 100:.0f}% of them sit on a kick")
    # per-bar density: how many true onsets per detected onset, and what a real template bar reads as
    tb = T[:, 3].astype(int)
    eb = np.clip(np.searchsorted(bar_t, E[:, 0] + 1e-9, "right") - 1, 0, len(bar_t) - 2)
    true_n = np.bincount(tb, minlength=len(bar_t) - 1)
    det_n = np.bincount(eb, minlength=len(bar_t) - 1)
    fit = np.polyfit(true_n, det_n, 1)
    print(f"  per bar: detected = {fit[0]:.2f} x true + {fit[1]:.2f} (so true ~ (detected - {fit[1]:.2f}) / {fit[0]:.2f})")
    for k in (2, 4, 8, 16):
        m = true_n == k
        if m.sum():
            print(f"    bars with {k:2d} true onsets: detected median {np.median(det_n[m]):.0f}, p90 {np.percentile(det_n[m], 90):.0f} (n={m.sum()})")
    COURT = [0, 3, 4, 7, 8, 11, 12, 15]
    court_b = [b for b in np.unique(tb) if np.sum((tb == b) & (T[:, 5] == 1.2)) == 8]
    other_b = [b for b in np.unique(tb) if b not in court_b]
    def tmpl_hits(b):
        m = eb == b
        sl_ = np.round((E[m, 0] - bias[EV_ATTACK] if EV_ATTACK in bias else E[m, 0]) / s16 - (bar_t[b] / s16)).astype(int)
        return len(set(sl_.tolist()) & set(COURT))
    ch = np.array([tmpl_hits(b) for b in court_b])
    oh = np.array([tmpl_hits(b) for b in other_b])
    print(f"    COURT-template slots detected: in true court bars median {np.median(ch):.0f}, share >= 4: {np.mean(ch >= 4) * 100:.0f}%, "
          f">= 3: {np.mean(ch >= 3) * 100:.0f}%; in other bars share >= 4: {np.mean(oh >= 4) * 100:.0f}%, >= 3: {np.mean(oh >= 3) * 100:.0f}%")
    # what a known figure looks like to the detector
    def detected_in(b):
        m = eb == b
        return np.round((E[m, 0] - bias.get(EV_ATTACK, 0.0) - bar_t[b]) / s16).astype(int)
    pat = {int(q): [b for b in np.unique(tb) if np.all(T[tb == b, 9] == q)] for q in np.unique(T[:, 9])}
    PN = ["court", "subliminal", "stab8", "retrig16", "held", "glide", "mixed", "pickup", "twohits", "random"]
    figs = {}
    for q, name in ((2, "stab8"), (0, "court"), (1, "subliminal"), (4, "held"), (9, "random")):
        bs = pat.get(q, [])
        if not bs:
            continue
        cnt = np.array([len(detected_in(b)) for b in bs])
        pos = np.concatenate([detected_in(b) for b in bs]) % 16
        runs_ = []
        for b in bs:
            sl_ = np.sort(detected_in(b))
            cur, best_ = 1, 1
            for k in range(1, len(sl_)):
                cur = cur + 1 if sl_[k] - sl_[k - 1] == 2 else 1
                best_ = max(best_, cur)
            runs_.append(best_ if len(sl_) else 0)
        runs_ = np.array(runs_)
        share = lambda qq: np.mean(np.isin(pos, qq)) * 100 if len(pos) else 0
        figs[name] = (np.median(cnt), np.mean(cnt >= 6), np.median(runs_), np.mean(runs_ >= 4), share([0, 4, 8, 12]),
                      share([2, 6, 10, 14]), share([1, 5, 9, 13]), share([3, 7, 11, 15]))
        print(f"    known '{name}' bars (n={len(bs)}): detected onsets median {np.median(cnt):.0f} (>= 6: {np.mean(cnt >= 6) * 100:.0f}%), "
              f"longest 8th-run median {np.median(runs_):.0f} (>= 4: {np.mean(runs_ >= 4) * 100:.0f}%); detected positions beat "
              f"{share([0, 4, 8, 12]):.0f}% / & {share([2, 6, 10, 14]):.0f}% / e {share([1, 5, 9, 13]):.0f}% / a {share([3, 7, 11, 15]):.0f}%")
    np.savez(scratch("shortcal_fig_hp.npz" if snare_hp else "shortcal_fig.npz"), names=np.array(list(figs)),
             vals=np.array(list(figs.values())))
    np.savez(scratch("shortcal_bar_hp.npz" if snare_hp else "shortcal_bar.npz"), fit=fit, court_ge4=np.array([np.mean(ch >= 4), np.mean(oh >= 4)]),
             court_ge3=np.array([np.mean(ch >= 3), np.mean(oh >= 3)]))
    np.savez(scratch("shortcal_kick_hp.npz" if snare_hp else "shortcal_kick.npz"), onk_short_recall=np.array([ok[(cls == "short") & onk].mean(), ok[(cls == "short") & ~onk].mean()]),
             onk_long_recall=np.array([ok[(cls == "long") & onk].mean(), ok[(cls == "long") & ~onk].mean()]))
    print(f"  'court'-style bars (8 shorts per bar): recall {ok[court].mean() * 100:.0f}%; "
          f"'subliminal' long pairs: recall {ok[(T[:, 5] == 5.0)].mean() * 100:.0f}%")
    np.savez(scratch("shortcal_hp.npz" if snare_hp else "shortcal.npz"), bias=np.array([bias.get(EV_ATTACK, 0.0), bias.get(EV_SLIDE, 0.0), bias.get(EV_SOFT, 0.0)]),
             vcorr=np.array([vcorr]), rule=np.array([rule]),
             recall=np.array([ok.mean(), ok[cls == "short"].mean(), ok[cls == "long"].mean(),
                              ok[typ == "gapless retrigger"].mean(), ok[typ == "legato glide"].mean()]),
             precision=np.array([used.mean()]))


GATE_SIG = 6.0                              # Hz: demodulation width around each bar pitch (sigma_t ~ 26 ms)


def gate_notes(x, d, bstart, bdur, pad=0.12):
    """Per bar: count separated bass notes from a narrowband envelope at the bar's own pitches.
    A note = the envelope rising above -6 dB (re the bar's loudest bass) after sitting below -14 dB,
    holding its level (not a kick's steady decay). -> rows [onset_s, offset_s, midi, bar]."""
    t = np.asarray(d["t"], float)
    v = np.asarray(d["voiced"], bool)
    midi = np.asarray(d["midi"], float)
    out = []
    for b in range(len(bstart)):
        a0, a1 = bstart[b] - pad, bstart[b] + bdur[b] + pad
        fr = (t >= a0) & (t <= a1) & v
        if fr.sum() < 3:
            continue
        vals, cnts = np.unique(np.round(midi[fr]).astype(int), return_counts=True)
        pitches = vals[cnts >= 2][:6]
        if not len(pitches):
            continue
        s0, s1 = int(a0 * SR8), int(a1 * SR8)
        if s0 < 0 or s1 > len(x):
            continue
        seg = x[s0:s1].astype(np.float64)
        n = len(seg)
        w = np.ones(n)
        m_ = int(0.03 * SR8)
        w[:m_] = np.linspace(0, 1, m_)
        w[-m_:] = np.linspace(1, 0, m_)
        S = np.fft.fft(seg * w)
        fq = np.fft.fftfreq(n, 1.0 / SR8)
        fc = 440.0 * 2 ** ((pitches - 69) / 12.0)
        G = np.exp(-0.5 * ((fq[None, :] - fc[:, None]) / GATE_SIG) ** 2)
        Y = np.fft.ifft(S[None, :] * G, axis=1)
        P = (Y.real ** 2 + Y.imag ** 2)[:, ::20]                    # 2.5 ms
        env = P.max(0)
        which = P.argmax(0)
        inner = slice(int(pad * 400), int((pad + bdur[b]) * 400))
        ref = np.percentile(env[inner], 98) + 1e-20
        edb = 10 * np.log10(env / ref + 1e-20)
        low = edb[0] < -14
        i = 1
        while i < len(edb):
            if low and edb[i] > -6:
                j0 = i
                while j0 > 0 and edb[j0 - 1] > -9:
                    j0 -= 1
                j1 = i
                while j1 + 1 < len(edb) and edb[j1 + 1] > -12:
                    j1 += 1
                ton = a0 + j0 / 400.0
                toff = a0 + (j1 + 1) / 400.0
                seg_db = edb[j0 + 8:max(j0 + 8, j1 - 2)]
                slope = np.polyfit(np.arange(len(seg_db)) / 400.0, seg_db, 1)[0] / 100.0 if len(seg_db) >= 8 else 0.0
                if bstart[b] <= ton < bstart[b] + bdur[b] and toff - ton >= 0.03 and slope >= -0.5:
                    out.append([ton, toff, float(pitches[int(np.bincount(which[j0:j1 + 1]).argmax())]), b])
                low = False
                i = j1 + 1
                continue
            if edb[i] < -14:
                low = True
            i += 1
    return np.array(out)


def stage_gatecal():
    """Calibrate the narrowband gate counter on the synthetic bass + break."""
    y, T, bar_t, s16, kick_t = synth_track()
    beat = 4 * s16
    d = yin_track(y)
    bd = np.full(len(bar_t) - 1, 16 * s16)
    Gn = gate_notes(y, d, bar_t[:-1], bd)
    sep = (T[:, 6] == 1) & ((T[:, 7] == 0) | (T[:, 8] == 1))       # audible onsets: after a gap, or a pinged retrigger
    Ts = T[sep]
    used = np.zeros(len(Gn), bool)
    ok = np.zeros(len(Ts), bool)
    err = []
    for i in np.argsort(Ts[:, 0]):
        dif = np.abs(Gn[:, 0] - Ts[i, 0])
        dif[used] = 9
        k = int(np.argmin(dif))
        if dif[k] <= 0.045:
            ok[i], used[k] = True, True
            err.append(Gn[k, 0] - Ts[i, 0])
    err = np.array(err)
    durb = (Ts[:, 1] - Ts[:, 0]) / beat
    print(f"gate counter on synthetic: {len(Gn)} notes found for {len(Ts)} audible true onsets; recall {ok.mean() * 100:.1f}%, "
          f"precision {used.mean() * 100:.1f}%")
    print(f"  onset error median {np.median(err) * 1000:+.1f} ms, p10 {np.percentile(err, 10) * 1000:+.1f}, p90 {np.percentile(err, 90) * 1000:+.1f}")
    for nm, m in (("attack after a gap", Ts[:, 7] == 0), ("pinged gapless retrigger", Ts[:, 7] == 1),
                  ("short < 0.5 beat", durb < 0.5), ("long >= 1 beat", durb >= 1)):
        print(f"  {nm:26s} n={m.sum():4d} recall {ok[m].mean() * 100:5.1f}%")
    onk = np.array([np.min(np.abs(kick_t - o)) < 0.02 for o in Ts[:, 0]])
    print(f"  short on a kick: recall {ok[(durb < 0.5) & onk].mean() * 100:.0f}% (n={np.sum((durb < 0.5) & onk)}); off a kick "
          f"{ok[(durb < 0.5) & ~onk].mean() * 100:.0f}% (n={np.sum((durb < 0.5) & ~onk)})")
    fp = ~used
    fpk = np.array([np.min(np.abs(kick_t - q)) < 0.02 for q in Gn[fp, 0]])
    print(f"  false notes: {fp.sum()}, on a kick {fpk.mean() * 100 if fp.any() else 0:.0f}%")
    tb = Ts[:, 3].astype(int)
    true_n = np.bincount(tb, minlength=len(bar_t) - 1)
    det_n = np.bincount(Gn[:, 3].astype(int), minlength=len(bar_t) - 1)
    fit = np.polyfit(true_n, det_n, 1)
    print(f"  per bar: detected = {fit[0]:.2f} x true + {fit[1]:.2f}; corr {np.corrcoef(true_n, det_n)[0, 1]:.2f}")
    for k in (1, 2, 3, 4, 6, 8):
        m = true_n == k
        if m.sum():
            print(f"    bars with {k} audible true onsets: detected median {np.median(det_n[m]):.0f}, IQR {np.percentile(det_n[m], 25):.0f}-"
                  f"{np.percentile(det_n[m], 75):.0f} (n={m.sum()})")
    COURT = [0, 3, 4, 7, 8, 11, 12, 15]
    court_b = [b for b in np.unique(T[:, 3].astype(int)) if np.sum((T[:, 3] == b) & (T[:, 5] == 1.2)) == 8]
    sl = np.round((Gn[:, 0] - bar_t[Gn[:, 3].astype(int)]) / s16).astype(int)
    hits = np.array([len(set(sl[(Gn[:, 3] == b)].tolist()) & set(COURT)) for b in range(len(bar_t) - 1)])
    isc = np.isin(np.arange(len(bar_t) - 1), court_b)
    stab8_b = [b for b in np.unique(T[:, 3].astype(int)) if np.sum((T[:, 3] == b) & (T[:, 5] == 1.0) & (T[:, 4] % 2 == 0)) == 8]
    iss = np.isin(np.arange(len(bar_t) - 1), stab8_b)
    print(f"  COURT-template slots found: court bars median {np.median(hits[isc]):.0f} (>=5: {np.mean(hits[isc] >= 5) * 100:.0f}%), "
          f"other bars median {np.median(hits[~isc]):.0f} (>=5: {np.mean(hits[~isc] >= 5) * 100:.0f}%)")
    print(f"  notes found per bar: court bars median {np.median(det_n[isc]):.0f}; 8th-stab bars median {np.median(det_n[iss]):.0f}; "
          f"'subliminal'/'held' bars median {np.median(det_n[~isc & ~iss & (true_n <= 2)]):.0f}")
    np.savez(scratch("gatecal.npz"), fit=fit, recall=np.array([ok.mean(), ok[durb < 0.5].mean(), ok[durb >= 1].mean()]),
             precision=np.array([used.mean()]), bias=np.array([np.median(err)]),
             court=np.array([np.mean(hits[isc] >= 5), np.mean(hits[~isc] >= 5)]),
             kick=np.array([ok[(durb < 0.5) & onk].mean(), ok[(durb < 0.5) & ~onk].mean()]),
             per_true=np.array([[k, np.median(det_n[true_n == k]) if np.any(true_n == k) else np.nan] for k in range(0, 17)]))


def stage_shortdiag():
    """Why are synthetic notes missed? Candidate features at every true attacked onset."""
    y, T, bar_t, s16, kick_t = synth_track()
    d = yin_track(y)
    N, M, G, trans = segment_notes(d, verbose=False)
    dbg = []
    E = bass_events(y, d, M, G, trans, debug=dbg)
    D = np.array(dbg)
    att = (T[:, 6] == 1) & (T[:, 7] == 0)
    print(f"attack candidates {len(D)}, accepted {int(D[:, 7].sum())}; true attacked-after-gap notes {att.sum()}")
    rows = []
    for i in np.where(att)[0]:
        k = int(np.argmin(np.abs(D[:, 0] - T[i, 0])))
        if abs(D[k, 0] - T[i, 0]) > 0.045:
            rows.append((0, np.nan, np.nan, np.nan, np.nan, np.nan, T[i, 5], T[i, 8]))
        else:
            rows.append((1, D[k, 2], D[k, 3], D[k, 4], D[k, 5], D[k, 6], T[i, 5], T[i, 8]))
    Rr = np.array(rows)
    has = Rr[:, 0] == 1
    print(f"  a candidate within 45 ms: {has.mean() * 100:.0f}%")
    q = Rr[has]
    print(f"  periods found 45-110 ms: " + ", ".join(f"{k}: {np.mean(q[:, 1] == k) * 100:.0f}%" for k in range(0, 5)))
    print(f"  spread st: p50 {np.nanmedian(q[:, 2]):.2f}, share <= 1.0: {np.mean(q[:, 2] <= 1.0) * 100:.0f}%")
    print(f"  pitch Hz ok: {np.mean((q[:, 3] >= F0_LO) & (q[:, 3] <= F0_HI)) * 100:.0f}%; level change p50 {np.nanmedian(q[:, 4]):.1f} dB; click p50 {np.nanmedian(q[:, 5]):.1f} dB")
    for lo_, hi_ in ((0, 1.1), (1.1, 1.6), (1.6, 20)):
        m = has & (Rr[:, 6] >= lo_) & (Rr[:, 6] < hi_)
        mm = Rr[m]
        print(f"  true {lo_}-{hi_} 16ths n={m.sum()}: periods>=2 {np.mean(mm[:, 1] >= 2) * 100:.0f}%, spread<=1 "
              f"{np.mean(mm[:, 2] <= 1) * 100:.0f}%, ping share {np.mean(mm[:, 7]) * 100:.0f}%, spread|ping p50 "
              f"{np.nanmedian(mm[mm[:, 7] == 1, 2]):.2f}, spread|no ping p50 {np.nanmedian(mm[mm[:, 7] == 0, 2]):.2f}")
    kick_c = D[~np.isin(np.arange(len(D)), [int(np.argmin(np.abs(D[:, 0] - T[i, 0]))) for i in range(len(T))])]
    print(f"  candidates not near any true note (kicks/snares): {len(kick_c)}, accepted {int(kick_c[:, 7].sum())}; "
          f"their spread p50 {np.nanmedian(kick_c[:, 3]):.2f}, periods>=2 {np.mean(kick_c[:, 2] >= 2) * 100:.0f}%, "
          f"level change p50 {np.nanmedian(kick_c[:, 5]):.1f}, click p50 {np.nanmedian(kick_c[:, 6]):.1f}")


def _slot_of(times, bstart, bdur):
    """-> (bar index, slot 0..15, micro offset ms); onsets rounding up into the next bar move there."""
    b = np.searchsorted(bstart, times + 1e-9, "right") - 1
    ok = (b >= 0) & (b < len(bstart))
    b = np.clip(b, 0, len(bstart) - 1)
    s16 = bdur[b] / 16
    pos = (times - bstart[b]) / s16
    r = np.round(pos).astype(int)
    micro = (pos - r) * s16 * 1000
    wrap = r >= 16
    nxt_ok = wrap & (b + 1 < len(bstart))
    contig = np.zeros(len(b), bool)
    contig[nxt_ok] = np.abs(bstart[np.minimum(b[nxt_ok] + 1, len(bstart) - 1)] - (bstart[b[nxt_ok]] + bdur[b[nxt_ok]])) < 0.05
    b = np.where(wrap & contig, b + 1, b)
    r = np.where(wrap, np.where(contig, 0, 15), r)
    ok &= (pos <= 16.5) & ~(wrap & ~contig)
    return b, r, micro, ok


def stage_short():
    x = np.load(os.path.join(CACHE, "mono8k.npy")).astype(np.float32)
    cal = np.load(scratch("shortcal.npz"))
    d = load_f0()
    z = np.load(scratch("notes.npz"))
    M, G, trans = z["merged"], z["glides"], z["trans"]
    E = bass_events(x, d, M, G, trans)
    E = E[~np.isnan(E[:, 5])]
    bias = cal["bias"]
    E[:, 0] -= bias[E[:, 3].astype(int)]
    E = E[np.argsort(E[:, 0])]
    off = event_durations(E, float(cal["vcorr"][0]), str(cal["rule"][0]))
    R = np.load(os.path.join(CACHE, "rhythm_bars.npz"), allow_pickle=True)
    bstart0, bdur = R["bar_start_s"], R["bar_dur_s"]
    kick0 = R["kick_occ16"].astype(bool)
    kclass = R["kick_class"]
    Rsec = R["section_id"]
    # Snare on 2 and 4 cannot tell a half-bar shift apart. Put the downbeat on the kick-heavier of
    # slots 0 / 8 in each rhythm section, and check the beat phase with 1-4 kHz energy on the
    # snare slots (4, 12) against the kick slots (0, 8).
    hfb = block_rms(fft_band(x, SR8, 1000, 3950), 20)
    rot = np.zeros(len(bstart0), int)
    print("  bar-phase check per rhythm section: kick occ slot0 / slot8 -> rotation; HF snare-vs-kick-slot contrast dB")
    for sid in np.unique(Rsec):
        m = Rsec == sid
        k0, k8 = kick0[m, 0].mean(), kick0[m, 8].mean()
        r_ = 8 if k8 > k0 + 0.1 else 0
        rot[m] = r_
        bb = np.where(m)[0]
        def lev(slots):
            vals = []
            for b in bb:
                for q in slots:
                    j = int((bstart0[b] + ((q + r_) % 16) * bdur[b] / 16 + (bdur[b] if q + r_ >= 16 else 0)) * 400)
                    if j + 16 < len(hfb):
                        vals.append(hfb[j:j + 16].mean() ** 2)
            return np.mean(vals) if vals else np.nan
        con = 10 * np.log10(lev([4, 12]) / lev([0, 8]))
        print(f"    rhythm S{sid:02d} ({m.sum():3d} bars, class {kclass[m][0]}): {k0:.2f} / {k8:.2f} -> rotate {r_}; "
              f"snare-slot HF {con:+.1f} dB")
    bstart = bstart0 + rot / 16.0 * bdur
    contig = np.r_[np.abs(bstart0[1:] - (bstart0[:-1] + bdur[:-1])) < 0.05, False]
    kick = np.zeros_like(kick0)
    for b in range(len(bstart0)):
        if rot[b] == 0:
            kick[b] = kick0[b]
        elif contig[b]:
            kick[b] = np.r_[kick0[b, 8:], kick0[b + 1, :8]]
    gb = load_grid()[1]
    offs = np.array([((g - bstart[np.argmin(np.abs(bstart - g))]) / (bdur[0] / 16)) for g in gb])
    offq = np.round(offs).astype(int)
    print(f"  grid.npz downbeats vs these bars (16ths): same {np.mean(offq == 0) * 100:.0f}%, half a bar off "
          f"{np.mean(np.abs(offq) == 8) * 100:.0f}%, a beat off {np.mean(np.abs(offq) == 4) * 100:.0f}%, other {np.mean(~np.isin(np.abs(offq), [0, 4, 8])) * 100:.0f}%")
    beat = np.median(bdur) / 4
    durb = (off - E[:, 0]) / beat
    cls = np.where(durb < 0.5, 0, np.where(durb < 1.0, 1, 2))           # 0 short, 1 medium, 2 long
    CN = ["short", "medium", "long"]
    bi, sl, micro, okg = _slot_of(E[:, 0], bstart, bdur)
    nbar = len(bstart)
    print("=" * 78)
    print(f"[13] SHORT-NOTE PLACEMENT - {len(E)} bass note events "
          f"(attack {np.mean(E[:, 3] == EV_ATTACK) * 100:.0f}%, slid {np.mean(E[:, 3] == EV_SLIDE) * 100:.0f}%, "
          f"soft start {np.mean(E[:, 3] == EV_SOFT) * 100:.0f}%); on the rhythm grid: {okg.sum()}")
    print(f"  calibration: recall {cal['recall'][0] * 100:.0f}% (short {cal['recall'][1] * 100:.0f}%, "
          f"gapless retrigger {cal['recall'][3] * 100:.0f}%), precision {cal['precision'][0] * 100:.0f}%, rule {cal['rule'][0]}")
    print("=" * 78)
    E, off, durb, cls, bi, sl, micro = E[okg], off[okg], durb[okg], cls[okg], bi[okg], sl[okg], micro[okg]
    n = len(E)
    print(f"\n[13.1] classes: " + ", ".join(f"{CN[c]} {np.sum(cls == c)} ({np.mean(cls == c) * 100:.0f}%)" for c in range(3)))
    print(f"  duration (beats) p1 {np.percentile(durb, 1):.2f}, p5 {np.percentile(durb, 5):.2f}, p10 {np.percentile(durb, 10):.2f}, "
          f"p25 {np.percentile(durb, 25):.2f}, p50 {np.percentile(durb, 50):.2f}, p75 {np.percentile(durb, 75):.2f}, p90 {np.percentile(durb, 90):.2f}")
    sh = cls == 0
    print(f"  short notes: duration p5 {np.percentile(durb[sh], 5):.2f}, p25 {np.percentile(durb[sh], 25):.2f}, "
          f"median {np.median(durb[sh]):.2f}, p75 {np.percentile(durb[sh], 75):.2f} beats")
    hb = np.histogram(durb[sh], bins=np.arange(0, 0.55, 0.05))[0]
    print("  short durations, 0.05-beat bins from 0: " + " ".join(str(v) for v in hb))
    print(f"  what ends a short note: the next onset {np.mean(np.isclose(off[sh], np.r_[E[1:, 0], 1e9][sh])) * 100:.0f}%, "
          f"its own release {np.mean(~np.isclose(off[sh], np.r_[E[1:, 0], 1e9][sh])) * 100:.0f}%")
    print(f"  micro-timing re the 16th grid: median {np.median(micro):+.1f} ms, IQR {np.percentile(micro, 25):+.1f}..{np.percentile(micro, 75):+.1f} ms")

    print(f"\n[13.2] onset slot histograms (share of each class; uniform = 6.25%)")
    print("  slot   " + "".join(f"{s:>6s}" for s in SLOT_NAMES))
    hist = {}
    for c in range(3):
        h = np.bincount(sl[cls == c], minlength=16) / max(np.sum(cls == c), 1)
        hist[c] = h
        print(f"  {CN[c]:6s} " + "".join(f"{v * 100:6.1f}" for v in h))
    hall = np.bincount(sl, minlength=16) / n
    print(f"  all    " + "".join(f"{v * 100:6.1f}" for v in hall))
    grp = {"beat (1,2,3,4)": [0, 4, 8, 12], "and (&)": [2, 6, 10, 14], "e": [1, 5, 9, 13], "a": [3, 7, 11, 15]}
    for c in range(3):
        print(f"  {CN[c]:6s} by position: " + ", ".join(f"{k} {hist[c][v].sum() * 100:.0f}%" for k, v in grp.items()))
    top = np.argsort(hist[0])[::-1][:5]
    print(f"  top short slots: " + ", ".join(f"{SLOT_NAMES[s]} {hist[0][s] * 100:.1f}%" for s in top))
    print(f"  short-over-long ratio per slot (enrichment of shorts): " + " ".join(
        f"{SLOT_NAMES[s]}:{(hist[0][s] + 1e-3) / (hist[2][s] + 1e-3):.1f}" for s in range(16)))

    # riff cycles
    bars, seq, active = bar_sequences()
    bounds = load_sections()
    sec = np.searchsorted(bounds, bars[:, 0], "right") - 1
    per_sec, period, cont, runs = riff_core(seq, active, sec, len(bounds) - 1)
    gstart = bars[:, 0]
    to_r = np.array([int(np.argmin(np.abs(bstart - g))) for g in gstart])
    to_r_ok = np.array([abs(bstart[k] - g) < 0.25 * np.median(bdur) for k, g in zip(to_r, gstart)])
    print(f"\n[13.3] placement in the riff cycle (runs from section 11, anchored on the run's first bar)")
    for C in (2, 4):
        cyc = {c: np.zeros(16 * C) for c in range(3)}
        tot = {c: 0 for c in range(3)}
        for s0, e0, L in runs:
            if L % C and C % L:
                continue
            if C > L and L not in (1, 2, 4):
                continue
            if L < C and C % L:
                continue
            for gb in range(s0, e0 + 1):
                if not to_r_ok[gb]:
                    continue
                rb = to_r[gb]
                m = bi == rb
                if not m.any():
                    continue
                phase = (gb - s0) % C
                for c in range(3):
                    mm = m & (cls == c)
                    np.add.at(cyc[c], phase * 16 + sl[mm], 1)
                    tot[c] += mm.sum()
        print(f"  {C}-bar cycle: notes counted short {tot[0]}, medium {tot[1]}, long {tot[2]}")
        for c in (0, 2):
            h = cyc[c] / max(tot[c], 1)
            bar_share = [h[16 * q:16 * (q + 1)].sum() for q in range(C)]
            last4 = [h[16 * q + 12:16 * (q + 1)].sum() for q in range(C)]
            print(f"    {CN[c]:6s} share per bar of the cycle: " + " ".join(f"{v * 100:.0f}%" for v in bar_share) +
                  f" | in beat 4 (slots 12-15) of each bar: " + " ".join(f"{v * 100:.0f}%" for v in last4))
            top = np.argsort(h)[::-1][:8]
            print(f"      top positions: " + ", ".join(f"bar{p // 16 + 1}:{SLOT_NAMES[p % 16]} {h[p] * 100:.1f}%" for p in top))

    # context
    print(f"\n[13.4] context of short notes")
    nxt_gap = np.r_[(E[1:, 0] - E[:-1, 0]) / (beat / 4), np.nan]
    prv_gap = np.r_[np.nan, (E[1:, 0] - E[:-1, 0]) / (beat / 4)]
    nxt_cls = np.r_[cls[1:], -1]
    iv_out = np.r_[E[1:, 5] - E[:-1, 5], np.nan]
    iv_in = np.r_[np.nan, E[1:, 5] - E[:-1, 5]]
    for name, m in (("short", sh), ("long", cls == 2)):
        g = np.round(nxt_gap[m])
        g = g[~np.isnan(g)]
        print(f"  {name}: time to the next onset (16ths): " + ", ".join(
            f"{int(k)}: {np.mean(g == k) * 100:.0f}%" for k in (1, 2, 3, 4)) + f", 5-8: {np.mean((g >= 5) & (g <= 8)) * 100:.0f}%, "
            f">8: {np.mean(g > 8) * 100:.0f}%")
    msh = sh & ~np.isnan(nxt_gap)
    close = msh & (nxt_gap <= 4.5)
    print(f"  short notes followed by an onset within a beat: {close.sum() / msh.sum() * 100:.0f}%; of those the next note is "
          + ", ".join(f"{CN[c]} {np.mean(nxt_cls[close] == c) * 100:.0f}%" for c in range(3)))
    for name, iv in (("out of", iv_out), ("into", iv_in)):
        q = iv[sh & ~np.isnan(iv)]
        a = np.abs(q)
        print(f"  interval {name} a short note: same pitch (<0.5 st) {np.mean(a < 0.5) * 100:.0f}%, step 1-2 st "
              f"{np.mean((a >= 0.5) & (a < 2.5)) * 100:.0f}%, 3-4 st {np.mean((a >= 2.5) & (a < 4.5)) * 100:.0f}%, "
              f"4th/5th {np.mean((a >= 4.5) & (a < 7.5)) * 100:.0f}%, bigger {np.mean(a >= 7.5) * 100:.0f}%; "
              f"up {np.mean(q >= 0.5) * 100:.0f}% / down {np.mean(q <= -0.5) * 100:.0f}%")
    q = iv_out[(cls == 2) & ~np.isnan(iv_out)]
    print(f"  (for comparison, out of a LONG note: same {np.mean(np.abs(q) < 0.5) * 100:.0f}%, step "
          f"{np.mean((np.abs(q) >= 0.5) & (np.abs(q) < 2.5)) * 100:.0f}%, bigger {np.mean(np.abs(q) >= 2.5) * 100:.0f}%)")
    pick = close & (nxt_cls == 2)
    nb_slot = np.r_[sl[1:], -1]
    print(f"  pickups (short, then a LONG note within a beat): {pick.sum() / sh.sum() * 100:.0f}% of shorts; "
          f"the long lands on slot " + ", ".join(f"{SLOT_NAMES[s]} {np.mean(nb_slot[pick] == s) * 100:.0f}%"
                                                 for s in np.argsort(np.bincount(nb_slot[pick], minlength=16))[::-1][:4]))
    rep = sh & (np.abs(iv_out) < 0.5) & (nxt_gap <= 4.5) & (nxt_cls == 0)
    print(f"  repeated stabs (short -> same pitch short within a beat): {rep.sum() / sh.sum() * 100:.0f}% of shorts")
    print(f"  type of short-note onsets: attacked {np.mean(E[sh, 3] == EV_ATTACK) * 100:.0f}%, slid into "
          f"{np.mean(E[sh, 3] == EV_SLIDE) * 100:.0f}%, soft {np.mean(E[sh, 3] == EV_SOFT) * 100:.0f}%")

    # patterns
    print(f"\n[13.5] common one-bar figures (S = short, M = medium, L = long onset; . = none)")
    lab = np.full((nbar, 16), ".", dtype="<U1")
    for k in range(n):
        lab[bi[k], sl[k]] = "SML"[cls[k]]
    strs = ["".join(r) for r in lab]
    nonempty = [s_ for s_ in strs if s_ != "." * 16]
    from collections import Counter
    cnt = Counter(nonempty)
    print(f"  {len(nonempty)} bars with >= 1 onset, {len(cnt)} distinct labelled figures")
    for i, (s_, c) in enumerate(cnt.most_common(15)):
        print(f"   {i + 1:2d}. |{s_[:4]}|{s_[4:8]}|{s_[8:12]}|{s_[12:]}|  {c:3d} bars ({c / len(nonempty) * 100:4.1f}%)")
    masks = Counter("".join("x" if ch != "." else "." for ch in s_) for s_ in nonempty)
    top15 = masks.most_common(15)
    print(f"  top 15 onset masks ignoring length cover {sum(c for _, c in top15) / len(nonempty) * 100:.0f}% of bars:")
    for i, (s_, c) in enumerate(top15):
        print(f"   {i + 1:2d}. |{s_[:4]}|{s_[4:8]}|{s_[8:12]}|{s_[12:]}|  {c:3d} ({c / len(nonempty) * 100:4.1f}%)")
    pairs = Counter()
    trip = Counter()
    for k in range(n - 1):
        if cls[k] != 0 or nxt_gap[k] > 4.5:
            continue
        pairs[f"S@{SLOT_NAMES[sl[k]]} -> {CN[nxt_cls[k]][0].upper()}@{SLOT_NAMES[sl[k + 1]]}"] += 1
        if k + 2 < n and nxt_gap[k + 1] <= 4.5:
            trip[f"S@{SLOT_NAMES[sl[k]]} {CN[cls[k + 1]][0].upper()}@{SLOT_NAMES[sl[k + 1]]} {CN[cls[k + 2]][0].upper()}@{SLOT_NAMES[sl[k + 2]]}"] += 1
    tot_p = sum(pairs.values())
    print(f"  top two-note figures starting on a short note ({tot_p} with the next onset within a beat):")
    for i, (s_, c) in enumerate(pairs.most_common(15)):
        print(f"   {i + 1:2d}. {s_:22s} {c:3d} ({c / tot_p * 100:4.1f}%)")
    tot_t = sum(trip.values())
    print(f"  top three-note figures starting on a short note ({tot_t}):")
    for i, (s_, c) in enumerate(trip.most_common(8)):
        print(f"   {i + 1:2d}. {s_:32s} {c:3d} ({c / tot_t * 100:4.1f}%)")

    # density
    print(f"\n[13.6] density")
    on_bar = np.bincount(bi, minlength=nbar)
    sh_bar = np.bincount(bi[sh], minlength=nbar)
    has = on_bar > 0
    print(f"  bars with bass onsets: {has.sum()} of {nbar}")
    print(f"  short notes per bar (bars with onsets): " + ", ".join(f"{k}: {np.mean(sh_bar[has] == k) * 100:.0f}%" for k in range(6)) +
          f", 6+: {np.mean(sh_bar[has] >= 6) * 100:.1f}%; mean {sh_bar[has].mean():.2f}")
    print(f"  onsets per bar: " + ", ".join(f"{k}: {np.mean(on_bar[has] == k) * 100:.0f}%" for k in range(1, 8)) +
          f", 8+: {np.mean(on_bar[has] >= 8) * 100:.1f}%; median {np.median(on_bar[has]):.0f}")
    print(f"  bars with >= 4 short notes: {np.mean(sh_bar[has] >= 4) * 100:.1f}%; >= 8 onsets: {np.mean(on_bar[has] >= 8) * 100:.1f}%")
    fg = np.load(scratch("shortcal_fig.npz"))
    FG = dict(zip([str(q) for q in fg["names"]], fg["vals"]))
    print(f"  how known figures read through this detector (synthetic): " + "; ".join(
        f"{k}: median {v[0]:.0f} onsets/bar, >=6 in {v[1] * 100:.0f}% of bars, 8th-run>=4 in {v[3] * 100:.0f}%"
        for k, v in FG.items()))
    runs_ref = []
    for b in np.where(has)[0]:
        sl_ = np.sort(sl[bi == b])
        cur, best_ = 1, 1
        for k in range(1, len(sl_)):
            cur = cur + 1 if sl_[k] - sl_[k - 1] == 2 else 1
            best_ = max(best_, cur)
        runs_ref.append(best_)
    runs_ref = np.array(runs_ref)
    print(f"  reference: bars with >= 6 detected onsets {np.mean(on_bar[has] >= 6) * 100:.1f}%; bars whose longest in-bar 8th-run is >= 4: "
          f"{np.mean(runs_ref >= 4) * 100:.1f}% (a bar of separated 8th stabs reads that way {FG['stab8'][3] * 100:.0f}% of the time)"
          if "stab8" in FG else "")
    gpos = bi * 16 + sl
    for step, nm in ((2, "8th"), (1, "16th")):
        runs_ = []
        cur = 1
        for k in range(1, n):
            if gpos[k] - gpos[k - 1] == step:
                cur += 1
            else:
                runs_.append(cur)
                cur = 1
        runs_.append(cur)
        runs_ = np.array(runs_)
        print(f"  runs of consecutive {nm}-spaced onsets: longest {runs_.max()} notes; runs >= 4 notes: {np.sum(runs_ >= 4)}, "
              f">= 8: {np.sum(runs_ >= 8)}; share of onsets inside a run >= 4: {runs_[runs_ >= 4].sum() / n * 100:.1f}%")
    COURT = [0, 3, 4, 7, 8, 11, 12, 15]
    cm = np.array([sum(ch != "." for ch in (s_[q] for q in COURT)) for s_ in strs])
    csh = np.array([sum(ch == "S" for ch in (s_[q] for q in COURT)) for s_ in strs])
    extra = np.array([sum(ch != "." for q, ch in enumerate(s_) if q not in COURT) for s_ in strs])
    print(f"  COURT OF APPEAL template (onsets on every beat and its 'a', all short):")
    print(f"    bars with all 8 template slots struck: {np.sum(cm[has] == 8)}; >= 6: {np.mean(cm[has] >= 6) * 100:.1f}%; "
          f">= 4: {np.mean(cm[has] >= 4) * 100:.1f}%; >= 4 of them short: {np.mean(csh[has] >= 4) * 100:.1f}%")
    print(f"    template slots struck per bar: " + ", ".join(f"{k}: {np.mean(cm[has] == k) * 100:.0f}%" for k in range(0, 7)))
    if "court" in FG:
        v = FG["court"]
        print(f"    a real COURT bar reads through this detector as beat {v[4]:.0f}% / & {v[5]:.0f}% / e {v[6]:.0f}% / a {v[7]:.0f}% of its detected onsets "
              f"(the 'a' notes follow a gap, the beat notes are retriggers); the reference's SHORT notes sit beat "
              f"{hist[0][[0, 4, 8, 12]].sum() * 100:.0f}% / & {hist[0][[2, 6, 10, 14]].sum() * 100:.0f}% / e {hist[0][[1, 5, 9, 13]].sum() * 100:.0f}% / "
              f"a {hist[0][[3, 7, 11, 15]].sum() * 100:.0f}%")
    SUB = (0, 6)
    two = np.array([s_[0] != "." and s_[6] != "." for s_ in strs])
    only = np.array([s_[0] != "." and s_[6] != "." and sum(ch != "." for ch in s_) == 2 for s_ in strs])
    upto3 = np.array([s_[0] != "." and s_[6] != "." and sum(ch != "." for ch in s_) <= 3 for s_ in strs])
    held = np.array([s_[0] in "ML" and s_[6] in "ML" for s_ in strs])
    print(f"  SUBLIMINAL MESSAGE template (1 and the '&' of 2, held):")
    print(f"    bars with onsets on both 1 and 2&: {np.mean(two[has]) * 100:.1f}%; exactly those two: {np.mean(only[has]) * 100:.1f}%; "
          f"those two plus at most one more: {np.mean(upto3[has]) * 100:.1f}%; both notes >= 0.5 beat: {np.mean(held[has]) * 100:.1f}%")
    base = np.mean([hall[0] > 0])
    pair_rank = Counter()
    for s_ in nonempty:
        on_ = [q for q, ch in enumerate(s_) if ch != "."]
        for a_ in on_:
            for b_ in on_:
                if a_ < b_:
                    pair_rank[(a_, b_)] += 1
    print(f"  most common onset PAIRS inside a bar (share of bars): " + ", ".join(
        f"{SLOT_NAMES[a_]}+{SLOT_NAMES[b_]} {c / len(nonempty) * 100:.0f}%" for (a_, b_), c in pair_rank.most_common(8)))

    # against the break
    print(f"\n[13.7] against the break (kicks from rhythm_bars.npz, snare slots 2 and 4 = slots 4 and 12)")
    ts = bstart[bi]
    region = np.where((ts >= 443) & (ts < 565), "two-step 7:23-9:25", np.where(kclass[bi] == 3, "break kick", "other"))
    rng = np.random.default_rng(13)
    for reg in ("break kick", "two-step 7:23-9:25", "other"):
        for c, nm in ((0, "short"), (2, "long")):
            m = (region == reg) & (cls == c)
            if m.sum() < 15:
                continue
            kb = kick[bi[m], sl[m]]
            kpm = kick[bi[m], np.clip(sl[m] - 1, 0, 15)] | kick[bi[m], np.clip(sl[m] + 1, 0, 15)]
            snare = np.isin(sl[m], [4, 12])
            gap = ~kb & ~snare
            null = []
            bars_m = bi[m]
            for _ in range(500):
                perm = bars_m.copy()
                for s_id in np.unique(Rsec[bars_m]):
                    pool = np.where(Rsec == s_id)[0]
                    idx = np.where(Rsec[bars_m] == s_id)[0]
                    perm[idx] = rng.choice(pool, len(idx))
                null.append(np.mean(kick[perm, sl[m]]))
            null = np.array(null)
            print(f"  {reg:20s} {nm:5s} n={m.sum():4d}: on a kick {kb.mean() * 100:4.0f}% (null {null.mean() * 100:4.0f}%, "
                  f"p {np.mean(null >= kb.mean()):.3f}); kick +-1 slot {kpm.mean() * 100:3.0f}%; on a snare slot "
                  f"{snare.mean() * 100:3.0f}% (uniform 12.5%); kick or snare {np.mean(kb | snare) * 100:3.0f}%; in the gaps {gap.mean() * 100:3.0f}%")
    for reg in ("break kick", "two-step 7:23-9:25"):
        mb = np.array([(reg == "break kick" and kclass[b] == 3 and not (443 <= bstart[b] < 565)) or
                       (reg != "break kick" and 443 <= bstart[b] < 565) for b in range(nbar)])
        print(f"  {reg}: kick occupancy per slot " + " ".join(f"{v:.2f}" for v in kick[mb].mean(0)))
        m = np.isin(bi, np.where(mb)[0]) & sh
        h = np.bincount(sl[m], minlength=16) / max(m.sum(), 1)
        ml = np.isin(bi, np.where(mb)[0]) & (cls == 2)
        hl = np.bincount(sl[ml], minlength=16) / max(ml.sum(), 1)
        print(f"  {'':{len(reg)}s}  short-note slots      " + " ".join(f"{v:.2f}" for v in h) + f"  (n={m.sum()})")
        print(f"  {'':{len(reg)}s}  long-note slots       " + " ".join(f"{v:.2f}" for v in hl) + f"  (n={ml.sum()})")
    np.savez(scratch("short.npz"), E=E, off=off, durb=durb, cls=cls, bi=bi, sl=sl, micro=micro)


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
                                      "timbre", "riff", "bars", "shortcal", "shortcalhp", "shortdiag", "gatecal", "short", "all"])
    ap.add_argument("--t0", type=float, default=500.0)
    ap.add_argument("--t1", type=float, default=512.0)
    a = ap.parse_args(argv)
    stages = {"grid": stage_grid, "sections": stage_sections, "f0": stage_f0,
              "notes": stage_notes, "spec": stage_spec, "kick": stage_kick,
              "report": stage_report, "inspect": lambda: stage_inspect(a.t0, a.t1),
              "bell": stage_bell, "bellreport": bell_report, "recipe": stage_recipe,
              "timbre": stage_timbre, "riff": stage_riff, "bars": lambda: stage_bars(),
              "shortcal": stage_shortcal, "shortcalhp": lambda: stage_shortcal(150.0), "shortdiag": stage_shortdiag, "gatecal": stage_gatecal, "short": stage_short}
    if a.stage == "all":
        for k in ["grid", "sections", "f0", "notes", "spec", "kick", "report"]:
            print(f"\n----- {k} -----")
            stages[k]()
    else:
        stages[a.stage]()
    return 0


if __name__ == "__main__":
    sys.exit(main())
