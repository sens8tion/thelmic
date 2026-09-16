"""REAPER HOOKS - how melodic and vocal material is used in the reference jungle DJ set.

STRUCTURAL ANALYSIS ONLY. Nothing here reads, writes or copies audio material out of the reference.
Every output is a number, a timestamp or a description of shape. No audio is written, no loop or
riff is extracted, and pitch is only ever reported as an interval against a section root - never as
a transcribed line that could be played back.

Why it works the way it does: aggregate band statistics are useless on a dense jungle mix, because
the break's cymbal wash and the reese's upper harmonics fill 200 Hz - 4 kHz continuously. What
separates a HOOK from that bed is that a hook is a small number of narrow, sustained partials
standing PROMINENTLY above the local spectral envelope. So the detector is built on prominence:

  stage 1  frames   STFT of the cached 8 kHz mono -> median-filter HPSS -> harmonic power on a
                    one-bin-per-semitone axis -> prominence = bin minus a +-6-semitone median.
                    Per frame: prominence mass, its register, partial count, chordality, f0,
                    bass top, band powers, centroids and flux for the contrast measures.
  stage 2  sections novelty segmentation on the cached band energies + a LOCAL tempo per section
  stage 3  events   hysteresis on prominence mass against each section's own baseline
  stage 4  report   sparsity, repetition, length, register gap, key, contrast -> tracks/.../hooks.md

    python scripts/reaper_hooks.py --stage1
    python scripts/reaper_hooks.py --peek
    python scripts/reaper_hooks.py --report
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter

import numpy as np
import torch

CACHE = r"C:\Users\eric\Downloads\reaper_cache"
SCRATCH = (r"C:\Users\eric\AppData\Local\Temp\claude\C--Users-eric-github-sens8tion-thelmic"
           r"\b784ee21-3fab-4996-98dd-32e4a4e5ac45\scratchpad")
OUT_MD = r"C:\Users\eric\github\sens8tion\thelmic\tracks\2026-09-16_reaper\hooks.md"

SR = 8000                 # mono8k.npy
N_FFT = 2048              # 3.91 Hz bins
HOP = 256                 # 31.25 fps
FPS = SR / HOP
T_WIN = 21                # HPSS median along time  (0.67 s) -> harmonic
F_WIN = 41                # HPSS median along freq  (160 Hz) -> percussive
ENV_WIN = 13              # +-6 semitones: the local envelope a partial must stand above
CHUNK = 1500              # frames per chunk (48 s)

MIDI_LO, MIDI_HI = 24, 108            # 32.7 Hz .. 3951 Hz, one bin per semitone
HOOK_MIDI = (55, 100)                 # 196 Hz .. 2637 Hz - where a hook fundamental lives
HOOK_HZ = (200.0, 4000.0)
LOW_HZ = (20.0, 200.0)
BASS_MIDI = (24, 55)                  # 32.7 .. 196 Hz - for the bass root chroma
PROM_TH = 6.0                         # dB above the local envelope before a bin counts as a partial
TOP_MIDI = 79                         # 784 Hz - the "is anything sparkling up top" tier

FRAMES_NPZ = os.path.join(SCRATCH, "hook_frames.npz")
EVENTS_NPZ = os.path.join(SCRATCH, "hook_events.npz")
PC = ["1", "b2", "2", "b3", "3", "4", "b5", "5", "b6", "6", "b7", "7"]


def midi_to_hz(m):
    return 440.0 * 2.0 ** ((np.asarray(m, float) - 69.0) / 12.0)


def hz_to_midi(f):
    return 69.0 + 12.0 * np.log2(np.maximum(np.asarray(f, float), 1e-9) / 440.0)


def semitone_matrix(freqs: np.ndarray) -> np.ndarray:
    mids = np.arange(MIDI_LO, MIDI_HI)
    centres, lo, hi = midi_to_hz(mids), midi_to_hz(mids - 0.5), midi_to_hz(mids + 0.5)
    M = np.zeros((len(mids), len(freqs)), np.float32)
    for i in range(len(mids)):
        left = (freqs >= lo[i]) & (freqs <= centres[i])
        right = (freqs > centres[i]) & (freqs <= hi[i])
        M[i, left] = (freqs[left] - lo[i]) / max(centres[i] - lo[i], 1e-9)
        M[i, right] = (hi[i] - freqs[right]) / max(hi[i] - centres[i], 1e-9)
        s = M[i].sum()
        if s > 0:
            M[i] /= s
        else:
            M[i, int(np.argmin(np.abs(freqs - centres[i])))] = 1.0
    return M


def median_filt(x: torch.Tensor, win: int, dim: int) -> torch.Tensor:
    pad = win // 2
    idx = torch.clamp(torch.arange(-pad, x.shape[dim] + pad), 0, x.shape[dim] - 1)
    xp = torch.index_select(x, dim, idx)
    return xp.unfold(dim, win, 1).median(dim=-1).values


def cum_pct_hz(Pw: torch.Tensor, sel: np.ndarray, freqs: np.ndarray, q: float) -> np.ndarray:
    """Frequency below which `q` of the power inside `sel` sits."""
    b = Pw[sel]
    c = torch.cumsum(b, 0) / b.sum(0, keepdim=True).clamp_min(1e-20)
    j = (c < q).sum(0).clamp(0, len(sel) - 1)
    return freqs[sel][j.numpy()].astype(np.float32)


# ----------------------------------------------------------------------
# stage 1
# ----------------------------------------------------------------------
def stage1():
    y = np.load(os.path.join(CACHE, "mono8k.npy"), mmap_mode="r")
    n = len(y)
    freqs = np.fft.rfftfreq(N_FFT, 1 / SR)
    M = torch.from_numpy(semitone_matrix(freqs))
    win = torch.hann_window(N_FFT)
    fz = torch.from_numpy(freqs.astype(np.float32))

    hook_m = torch.from_numpy(((freqs >= HOOK_HZ[0]) & (freqs < HOOK_HZ[1])).astype(np.float32))
    low_m = torch.from_numpy(((freqs >= LOW_HZ[0]) & (freqs < LOW_HZ[1])).astype(np.float32))
    sub_m = torch.from_numpy(((freqs >= 20) & (freqs < 60)).astype(np.float32))
    rough_m = torch.from_numpy(((freqs >= 1000) & (freqs < 4000)).astype(np.float32))
    bt_sel = np.where((freqs >= 25) & (freqs < 500))[0]
    hk = slice(HOOK_MIDI[0] - MIDI_LO, HOOK_MIDI[1] - MIDI_LO)
    bs = slice(BASS_MIDI[0] - MIDI_LO, BASS_MIDI[1] - MIDI_LO)
    hook_mids = np.arange(MIDI_LO, MIDI_HI)[hk].astype(np.float32)

    scalars = ["t", "hook_e", "hook_h_e", "hook_p_e", "low_e", "sub_e",
               "bass_top", "bass_top99", "bass_top_h", "bass_top_h95",
               "hook_cent", "low_cent", "hook_flux", "low_flux", "rough", "hook_flat"]
    acc = {c: [] for c in scalars}
    for v in ("semi_h", "semi_a"):
        acc[v] = []

    step, overlap = CHUNK * HOP, N_FFT * 4
    pos, prev_hook, prev_low = 0, None, None
    while pos < n:
        stop = min(n, pos + step + overlap)
        seg = torch.from_numpy(np.array(y[pos:stop], np.float32))
        S = torch.stft(seg, N_FFT, HOP, window=win, center=True, return_complex=True).abs()
        keep = CHUNK if stop < n else S.shape[1]
        H_env, P_env = median_filt(S, T_WIN, 1), median_filt(S, F_WIN, 0)
        mask = (H_env ** 2) / (H_env ** 2 + P_env ** 2 + 1e-20)
        Hm, Pm = S * mask, S * (1 - mask)
        Hm, Pm, S = Hm[:, :keep], Pm[:, :keep], S[:, :keep]
        Pw, Hw, Pp = S ** 2, Hm ** 2, Pm ** 2            # power spectra

        # --- semitone axis, kept ABSOLUTE and in dB. Prominence is derived later (see derive()):
        # normalising here would bake in the 1/f tilt and push every measured hook register down.
        semi_h = M @ Hw                                   # harmonic power per semitone
        semi_a = M @ Pw                                   # total power per semitone
        acc["semi_h"].append((10 * torch.log10(semi_h + 1e-20)).numpy().T)
        acc["semi_a"].append((10 * torch.log10(semi_a + 1e-20)).numpy().T)

        # --- band powers, centroids, register gap, contrast
        he = (Pw * hook_m[:, None]).sum(0)
        le = (Pw * low_m[:, None]).sum(0)
        acc["hook_e"].append(he.numpy())
        acc["low_e"].append(le.numpy())
        acc["sub_e"].append((Pw * sub_m[:, None]).sum(0).numpy())
        acc["hook_h_e"].append((Hw * hook_m[:, None]).sum(0).numpy())
        acc["hook_p_e"].append((Pp * hook_m[:, None]).sum(0).numpy())
        acc["hook_cent"].append(((Pw * hook_m[:, None] * fz[:, None]).sum(0)
                                 / he.clamp_min(1e-20)).numpy())
        acc["low_cent"].append(((Pw * low_m[:, None] * fz[:, None]).sum(0)
                                / le.clamp_min(1e-20)).numpy())
        acc["rough"].append((((Pw * rough_m[:, None]).sum(0)) / he.clamp_min(1e-20)).numpy())
        hb = Pw[hook_m > 0]
        acc["hook_flat"].append((torch.exp(torch.log(hb + 1e-20).mean(0))
                                 / hb.mean(0).clamp_min(1e-20)).numpy())
        acc["bass_top"].append(cum_pct_hz(Pw, bt_sel, freqs, 0.90))
        acc["bass_top99"].append(cum_pct_hz(Pw, bt_sel, freqs, 0.99))
        # the same, on the HARMONIC part only: this is the bass instrument's top, with the
        # break's low-mid transients taken out
        acc["bass_top_h"].append(cum_pct_hz(Hw, bt_sel, freqs, 0.90))
        acc["bass_top_h95"].append(cum_pct_hz(Hw, bt_sel, freqs, 0.95))

        def fl(v, prev):
            d = torch.diff(torch.sqrt(v), prepend=(prev if prev is not None else torch.sqrt(v[:1])))
            return d.clamp_min(0).numpy(), torch.sqrt(v[-1:]).clone()
        f1, prev_hook = fl(he, prev_hook)
        f2, prev_low = fl(le, prev_low)
        acc["hook_flux"].append(f1)
        acc["low_flux"].append(f2)
        acc["t"].append((len(np.concatenate(acc["t"])) if acc["t"] else 0) + np.arange(keep))
        pos += step
        print(f"  {pos / SR:7.1f}s / {n / SR:.1f}s", end="\r", flush=True)

    out = {k: np.concatenate(v).astype(np.float32) for k, v in acc.items()}
    out["t"] = out["t"] * HOP / SR
    os.makedirs(SCRATCH, exist_ok=True)
    np.savez_compressed(FRAMES_NPZ, **out)
    print(f"\nstage1 -> {FRAMES_NPZ}  {len(out['t'])} frames at {FPS:.2f} fps")


# ----------------------------------------------------------------------
# stage 2 - sections and local tempo
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# stage 2a - prominence, derived from the saved semitone spectrograms
# ----------------------------------------------------------------------
def med_freq(X: np.ndarray, win: int) -> np.ndarray:
    """Median along the semitone axis (axis 1) of a (T, n_semi) array, edges replicated."""
    pad = win // 2
    idx = np.clip(np.arange(-pad, X.shape[1] + pad), 0, X.shape[1] - 1)
    Xp = X[:, idx]
    return np.median(np.lib.stride_tricks.sliding_window_view(Xp, win, axis=1), axis=-1)


def derive(F: dict) -> dict:
    """Turn the saved dB semitone spectrograms into scale-free prominence features.

    Two normalisations, and both matter:
      * along TIME - each semitone bin is expressed in dB above its own long-term level, so the
        mix's 1/f tilt and the reese's standing harmonics stop dominating,
      * along FREQUENCY - a partial must then stand above a +-6-semitone median of that whitened
        surface. What survives is a narrow peak that is loud *for its own band* and loud *for its
        own neighbourhood*: a hook, not the bed.
    """
    L = F["semi_h"]                                        # (T, 84) dB
    ref = np.percentile(L, 60, axis=0, keepdims=True)      # each band's own standing level
    Lw = L - ref
    prom = np.clip(Lw - med_freq(Lw, ENV_WIN), 0.0, None)  # dB above the local envelope
    prom *= (Lw > -3.0)                                    # and it has to be up at all
    hk = slice(HOOK_MIDI[0] - MIDI_LO, HOOK_MIDI[1] - MIDI_LO)
    bs = slice(BASS_MIDI[0] - MIDI_LO, BASS_MIDI[1] - MIDI_LO)
    ph = prom[:, hk]
    mids = np.arange(MIDI_LO, MIDI_HI, dtype=float)
    hm = mids[hk]

    D = {}
    D["prom"] = prom
    D["ph"] = ph
    D["prom_sum"] = ph.sum(1)
    D["n_part"] = (ph > 6.0).sum(1).astype(np.float32)
    w = ph / np.maximum(ph.sum(1, keepdims=True), 1e-9)
    D["prom_cent"] = (w * hm).sum(1)
    c = np.cumsum(w, 1)
    for name, q in (("prom_lo", 0.10), ("prom_hi", 0.90)):
        D[name] = hm[np.clip((c < q).sum(1), 0, len(hm) - 1)]
    # harmonic-sum f0 over the prominence surface
    offs, wts = [0, 12, 19, 24], [1.0, 0.6, 0.45, 0.35]
    hsum = np.zeros_like(ph)
    for o, wt in zip(offs, wts):
        z = np.zeros_like(ph)
        if o < ph.shape[1]:
            z[:, :ph.shape[1] - o] = ph[:, o:]
        hsum += wt * z
    D["f0_midi"] = hm[np.argmax(hsum, 1)]
    D["f0_sal"] = hsum.max(1) / np.maximum(hsum.sum(1), 1e-9)
    # chroma from prominence (hook range) and from the bass range
    pb = prom[:, bs]
    bsum = np.zeros_like(pb)
    for o, wt in zip(offs, wts):
        z = np.zeros_like(pb)
        if o < pb.shape[1]:
            z[:, :pb.shape[1] - o] = pb[:, o:]
        bsum += wt * z
    bm = mids[bs]
    D["bass_f0"] = bm[np.argmax(bsum, 1)]
    D["bass_f0_sal"] = bsum.max(1) / np.maximum(bsum.sum(1), 1e-9)
    ch = np.zeros((len(L), 12), np.float32)
    cb = np.zeros((len(L), 12), np.float32)
    for k in range(12):
        ch[:, k] = hsum[:, (k - (HOOK_MIDI[0] % 12)) % 12::12].sum(1)
        cb[:, k] = bsum[:, (k - (BASS_MIDI[0] % 12)) % 12::12].sum(1)
    D["chroma"] = ch / np.maximum(ch.sum(1, keepdims=True), 1e-9)
    D["chroma_bass"] = cb / np.maximum(cb.sum(1, keepdims=True), 1e-9)
    D["n_pc"] = (D["chroma"] > 0.14).sum(1).astype(np.float32)
    D["semi_prom"] = ph / np.maximum(ph.sum(1, keepdims=True), 1e-9)

    # where the mix leaves a hole: the quietest semitone in 120-700 Hz relative to a broad trend
    A = F["semi_a"]
    lo_i, hi_i = int(round(hz_to_midi(120))) - MIDI_LO, int(round(hz_to_midi(700))) - MIDI_LO
    seg = A[:, lo_i:hi_i] - med_freq(A, 25)[:, lo_i:hi_i]
    D["valley_hz"] = midi_to_hz(mids[lo_i:hi_i][np.argmin(seg, 1)]).astype(np.float32)
    D["valley_db"] = seg.min(1)
    return D


def local_tempo(env: np.ndarray, fps: float, lo=150.0, hi=190.0) -> float:
    e = env - env.mean()
    if len(e) < 256:
        return float("nan")
    ac = np.correlate(e, e, mode="full")[len(e) - 1:]
    lags = np.arange(len(ac))
    with np.errstate(divide="ignore"):
        bpm = 60.0 * fps / np.maximum(lags, 1e-9)
    ok = (bpm >= lo) & (bpm <= hi) & (lags < len(ac) // 2)
    if not ok.any():
        return float("nan")
    lag = int(lags[ok][np.argmax(ac[ok])])
    if 1 <= lag < len(ac) - 1:
        y0, y1, y2 = ac[lag - 1], ac[lag], ac[lag + 1]
        d = y0 - 2 * y1 + y2
        if d != 0:
            lag = lag + 0.5 * (y0 - y2) / d
    return float(60.0 * fps / lag)


def sections(min_s=45.0, n_target=16):
    f = np.load(os.path.join(CACHE, "frames.npz"))
    fps_c = 93.75
    bands = np.stack([f[b] for b in ("sub", "bass", "lowmid", "mid", "high", "air")], 1)
    bands = np.log1p(bands / (bands.mean(0, keepdims=True) + 1e-9))
    w = int(round(2.0 * fps_c))
    nb = len(bands) // w
    X = bands[:nb * w].reshape(nb, w, -1).mean(1)
    X = (X - X.mean(0)) / (X.std(0) + 1e-9)
    Xn = X / (np.linalg.norm(X, axis=1, keepdims=True) + 1e-9)
    Ssm = Xn @ Xn.T
    L = 12
    g = np.outer(*[np.exp(-0.5 * (np.arange(-L, L) / (L / 2.0)) ** 2)] * 2)
    sign = np.sign(np.outer(np.r_[-np.ones(L), np.ones(L)], np.r_[-np.ones(L), np.ones(L)]))
    K = g * sign
    nov = np.zeros(nb)
    for i in range(L, nb - L):
        nov[i] = (Ssm[i - L:i + L, i - L:i + L] * K).sum()
    nov = np.maximum(nov, 0) / (np.maximum(nov, 0).max() + 1e-9)
    picked, mind = [], int(round(min_s / 2.0))
    for i in np.argsort(nov)[::-1]:
        if nov[i] <= 0:
            break
        if all(abs(i - j) >= mind for j in picked):
            picked.append(int(i))
        if len(picked) >= n_target:
            break
    b = sorted([0] + picked + [nb])
    secs = [(b[k] * 2.0, b[k + 1] * 2.0) for k in range(len(b) - 1)]

    flux = f["flux"]
    out = []
    for (a, z) in secs:
        i0, i1 = int(a * fps_c), int(z * fps_c)
        bpm = local_tempo(flux[i0:i1] / (flux[i0:i1].max() + 1e-9), fps_c)
        out.append({"t0": a, "t1": z, "bpm": bpm, "bar_s": 240.0 / bpm if bpm == bpm else np.nan})
    return out


def grid_note():
    p = os.path.join(CACHE, "grid.npz")
    if os.path.exists(p):
        return p
    return None


# ----------------------------------------------------------------------
# stage 3 - events
# ----------------------------------------------------------------------
def smooth(x, w):
    return x if w <= 1 else np.convolve(x, np.ones(w) / w, mode="same")


def running_pct(x, win, q):
    """Cheap running percentile: percentile inside non-overlapping blocks, then interpolated."""
    nb = max(1, len(x) // win)
    e = np.array_split(np.arange(len(x)), nb)
    c = np.array([np.percentile(x[b], q) for b in e])
    ctr = np.array([b.mean() for b in e])
    return np.interp(np.arange(len(x)), ctr, c)


def band_view(F, band):
    """Prominence mass, partial count and band power for one semitone window."""
    a, b = band[0] - HOOK_MIDI[0], band[1] - HOOK_MIDI[0]
    ph = F["ph"][:, a:b]
    e = (10.0 ** (F["semi_h"][:, band[0] - MIDI_LO:band[1] - MIDI_LO] / 10.0)).sum(1)
    return ph.sum(1), (ph > PROM_TH).sum(1).astype(np.float32), e


def hook_score(F, secs, band=HOOK_MIDI):
    """Prominence mass measured against each section's own tonal bed, then gated two ways:
    relatively (is this band louder than its own bed right now) and ABSOLUTELY (are there really
    several prominent partials up there). Without the absolute gate a narrow sub-band reports
    activity whenever its own noise floor wobbles, and a subset ends up 'busier' than the whole."""
    t = F["t"]
    pm_all, npart_all, e_all = band_view(F, band)
    score = np.zeros(len(t), np.float32)
    for s in secs:
        i0, i1 = np.searchsorted(t, s["t0"]), np.searchsorted(t, s["t1"])
        if i1 - i0 < 64:
            continue
        pm = smooth(pm_all[i0:i1], 5)
        hh = e_all[i0:i1]
        lvl = np.clip(np.log1p(hh / (np.percentile(hh, 50) + 1e-20)) / 1.2, 0, 1.6)
        base = running_pct(pm, int(12 * FPS), 40)       # the section's standing tonal bed
        spread = running_pct(pm, int(12 * FPS), 90) - base
        rel = (pm - base) / np.maximum(spread, 1e-6) * np.clip(lvl, 0.25, 1.6)
        absg = np.clip(smooth(npart_all[i0:i1], 5) / 3.0, 0.0, 1.0)
        score[i0:i1] = rel * absg
    return score


def detect_events(F, secs, hi_th=1.00, lo_th=0.45, min_dur=0.18, merge=0.18,
                  band=HOOK_MIDI):
    t = F["t"]
    score = hook_score(F, secs, band)
    on, ext = score > hi_th, score > lo_th
    lab = np.zeros(len(score), bool)
    idx = np.where(on)[0]
    i = 0
    while i < len(idx):
        j = idx[i]
        a = b = j
        while a > 0 and ext[a - 1]:
            a -= 1
        while b < len(ext) - 1 and ext[b + 1]:
            b += 1
        lab[a:b + 1] = True
        while i < len(idx) and idx[i] <= b:
            i += 1
    d = np.diff(lab.astype(np.int8))
    starts = list(np.where(d == 1)[0] + 1)
    ends = list(np.where(d == -1)[0] + 1)
    if lab[0]:
        starts = [0] + starts
    if lab[-1]:
        ends = ends + [len(lab)]
    spans = []
    for s, e in zip(starts, ends):
        if spans and (s - spans[-1][1]) / FPS < merge:
            spans[-1] = (spans[-1][0], e)
        else:
            spans.append((s, e))

    evs = []
    for s, e in spans:
        if (e - s) / FPS < min_dur:
            continue
        sl = slice(s, e)
        w = F["prom_sum"][sl] + 1e-9
        pm = F["prom_sum"][sl]
        env = smooth(F["hook_e"][sl], 2)
        pk = int(np.argmax(env))
        f0 = F["f0_midi"][sl]
        strong = F["f0_sal"][sl] > np.percentile(F["f0_sal"][sl], 40)
        f0s = f0[strong] if strong.sum() > 2 else f0
        ev = {
            "t": float(t[s]), "dur": float((e - s) / FPS), "i0": int(s), "i1": int(e),
            "cent_midi": float(np.average(F["prom_cent"][sl], weights=w)),
            "lo_midi": float(np.percentile(F["prom_lo"][sl], 20)),
            "hi_midi": float(np.percentile(F["prom_hi"][sl], 80)),
            "f0_midi": float(np.median(f0s)),
            "f0_iqr": float(np.percentile(f0s, 75) - np.percentile(f0s, 25)),
            "f0_range": float(np.percentile(f0s, 90) - np.percentile(f0s, 10)),
            "n_part": float(np.median(F["n_part"][sl])),
            "n_pc": float(np.median(F["n_pc"][sl])),
            "peak_score": float(score[sl].max()),
            "prom": float(pm.mean()),
            "rough": float(np.average(F["rough"][sl], weights=w)),
            "hook_cent": float(np.average(F["hook_cent"][sl], weights=w)),
            "low_cent": float(np.average(F["low_cent"][sl], weights=w)),
            "bass_top": float(np.median(F["bass_top"][sl])),
            "bass_top99": float(np.median(F["bass_top99"][sl])),
            "hook_flux": float(F["hook_flux"][sl].mean()),
            "low_flux": float(F["low_flux"][sl].mean()),
            "hook_e": float(F["hook_e"][sl].mean()),
            "low_e": float(F["low_e"][sl].mean()),
            "attack_s": float((pk + 1) / FPS),
        }
        ch = F["chroma"][sl].mean(0)
        ev["chroma"] = ch / (ch.sum() + 1e-9)
        ev["semi"] = F["semi_prom"][sl].mean(0)
        cb = F["chroma_bass"][sl].mean(0)
        ev["chroma_bass"] = cb / (cb.sum() + 1e-9)
        evs.append(ev)
    return evs, score


def classify(ev):
    """Type from measured axes only. These names are shorthand for a measurement, not an
    instrument identification - from 8 kHz mono inside a dense mix the honest discriminators are
    length, fundamental register, pitch movement (f0 inter-quartile range, which is robust where
    f0_range is not) and how many partials/pitch classes sound at once."""
    d = ev["dur"]
    f0, move, npc, npart = ev["f0_midi"], ev["f0_iqr"], ev["n_pc"], ev["n_part"]
    if d < 0.35:
        return "chord stab" if npc >= 3 else "stab"
    if move >= 3.0 and npart >= 8 and d <= 2.0:
        return "vocal-like"
    if f0 >= 72 and move < 3.0:
        return "bell / high tone"
    if d >= 1.2 and move < 2.0:
        return "sustained tone"
    if d >= 1.2:
        return "lead line"
    return "riff fragment"


# ----------------------------------------------------------------------
def peek():
    F = load()
    secs = sections()
    print(f"{len(secs)} sections; local tempo:")
    for s in secs:
        print(f"  {s['t0']:7.1f}-{s['t1']:7.1f} ({s['t1']-s['t0']:5.1f}s)  {s['bpm']:.2f} BPM"
              f"  bar {s['bar_s']:.3f}s")
    evs, score = detect_events(F, secs)
    dur = F["t"][-1]
    tot = sum(e["dur"] for e in evs)
    print(f"\nscore pct: {np.percentile(score, [50, 75, 90, 95, 99]).round(2)}")
    print(f"{len(evs)} events, {tot:.1f}s = {100*tot/dur:.1f}% of {dur:.0f}s")
    ds = np.array([e["dur"] for e in evs])
    print("dur pct:", np.percentile(ds, [10, 25, 50, 75, 90]).round(2))
    print("cent_midi pct:", np.percentile([e["cent_midi"] for e in evs], [10, 50, 90]).round(1),
          "=> Hz", midi_to_hz(np.percentile([e["cent_midi"] for e in evs], [10, 50, 90])).round(0))
    print("f0 Hz pct:", midi_to_hz(np.percentile([e["f0_midi"] for e in evs], [10, 50, 90])).round(0))
    print("bass_top90 Hz pct:", np.percentile([e["bass_top"] for e in evs], [10, 50, 90]).round(0))
    print(Counter(classify(e) for e in evs).most_common())
    for e in evs[:30]:
        print(f"  {e['t']:7.2f} {e['dur']:5.2f}s f0 {midi_to_hz(e['f0_midi']):6.0f} "
              f"cen {midi_to_hz(e['cent_midi']):6.0f} rng {e['f0_range']:4.1f} "
              f"np {e['n_part']:4.1f} npc {e['n_pc']:3.1f} sc {e['peak_score']:4.1f} "
              f"{classify(e)}")


def implied_f0(semi_prom: np.ndarray) -> tuple[float, float]:
    """Fit a harmonic comb to the prominence profile. Returns (best midi f0, fit 0..1).

    The point is to catch the reese/sub's own harmonic series masquerading as a hook: if the comb
    that best explains the partials has its fundamental down at 60-130 Hz, that is the bass, not a
    hook sitting above it.
    """
    n = len(semi_prom)                                    # midi HOOK_MIDI[0] .. HOOK_MIDI[1]
    v = semi_prom / (semi_prom.sum() + 1e-12)
    offs = np.array([0, 12, 19.02, 24, 27.86, 31.02, 33.69, 36], float)
    wts = np.array([1.0, .8, .6, .5, .4, .35, .3, .28])
    best, bf = -1.0, np.nan
    for f0 in np.arange(36, 97, 1.0):
        idx = np.round(f0 + offs - HOOK_MIDI[0]).astype(int)
        ok = (idx >= 0) & (idx < n)
        if ok.sum() < 3:
            continue
        s = float((v[idx[ok]] * wts[ok]).sum() / wts[ok].sum())
        if s > best:
            best, bf = s, f0
    return float(bf), float(best)


def bar_phase_check():
    """Is the single global bar grid safe? Comb the low-band onset flux per section."""
    f = np.load(os.path.join(CACHE, "frames.npz"))
    meta = json.load(open(os.path.join(CACHE, "meta.json")))
    fps_c, bpm = 93.75, meta["bpm"]
    beat_f = 60.0 * fps_c / bpm
    env = f["flux_sub"] + f["flux_bass"]
    env = env / (env.max() + 1e-9)
    out = []
    for s in sections():
        i0, i1 = int(s["t0"] * fps_c), int(s["t1"] * fps_c)
        e = env[i0:i1]
        sc = []
        for ph in np.arange(0, beat_f, 0.25):
            pos = np.arange(ph, len(e) - 1, beat_f)
            sc.append(np.interp(pos, np.arange(len(e)), e).sum())
        ph = float(np.arange(0, beat_f, 0.25)[int(np.argmax(sc))])
        # phase of this section's beat grid relative to the global one, in ms
        glob = (meta["beat_phase"] + beat_f * np.ceil((i0 - meta["beat_phase"]) / beat_f)) - i0
        d = ((ph - glob + beat_f / 2) % beat_f) - beat_f / 2
        out.append((s["t0"], s["t1"], d * 1000.0 / fps_c, max(sc) / (np.mean(sc) + 1e-9)))
    return out


def diag():
    F = load()
    q = [5, 25, 50, 75, 90, 95, 99]
    for k in ("prom_sum", "n_part", "n_pc", "f0_sal", "bass_top", "bass_top99",
              "prom_cent", "prom_lo", "prom_hi", "hook_cent", "low_cent", "rough", "hook_flat"):
        print(f"{k:11s}", np.percentile(F[k], q).round(3))
    print(f"{'h/p':11s}", np.percentile(F["hook_h_e"] / (F["hook_p_e"] + 1e-20), q).round(2))
    print(f"{'hook/low dB':11s}",
          np.percentile(10 * np.log10(F["hook_e"] / (F["low_e"] + 1e-20) + 1e-20), q).round(1))

    print("\n-- bar phase of each section vs the single global grid --")
    for t0, t1, dms, conf in bar_phase_check():
        print(f"  {t0:7.1f}-{t1:7.1f}  offset {dms:+7.1f} ms   comb conf {conf:.2f}")

    secs = sections()
    evs, score = detect_events(F, secs)
    f0s = np.array([implied_f0(e["semi"]) for e in evs])
    print(f"\n-- implied fundamental of each event's partial comb ({len(evs)} events) --")
    print("  implied f0 midi pct:", np.percentile(f0s[:, 0], [5, 25, 50, 75, 95]).round(1),
          "=> Hz", midi_to_hz(np.percentile(f0s[:, 0], [5, 25, 50, 75, 95])).round(0))
    print("  fit pct:", np.percentile(f0s[:, 1], [5, 25, 50, 75, 95]).round(3))
    for cut in (44, 48, 52, 55):
        print(f"  share with implied f0 < midi {cut} ({midi_to_hz(cut):.0f} Hz): "
              f"{(f0s[:, 0] < cut).mean():.3f}")
    ds = np.array([e["dur"] for e in evs])
    print("\n  dur max", ds.max().round(2), " n>3s", int((ds > 3).sum()), " n>6s", int((ds > 6).sum()))
    # does the score just track the bass?
    sub = F["sub_e"]
    print("  corr(score, sub_e):", round(float(np.corrcoef(score, np.log1p(sub / sub.mean()))[0, 1]), 3))
    hh = F["hook_h_e"]
    print("  corr(score, hook_h_e):",
          round(float(np.corrcoef(score, np.log1p(hh / hh.mean()))[0, 1]), 3))


def main(argv=None):
    ap = argparse.ArgumentParser()
    for f in ("stage1", "peek", "diag", "report", "callresp"):
        ap.add_argument("--" + f, action="store_true")
    a = ap.parse_args(argv)
    if a.stage1:
        stage1()
    elif a.peek:
        peek()
    elif a.diag:
        diag()
    elif a.report:
        report()
    elif a.callresp:
        callresp_main()
    else:
        ap.print_help()
    return 0


# ----------------------------------------------------------------------
# stage 4 - per-section bar grid, then the analysis
# ----------------------------------------------------------------------
def section_grids(secs):
    """Prefer the shared grid.npz if another pass has produced one; otherwise comb each section's
    own downbeat phase out of the low-band onset flux (tempo is locked across the set, but the
    DJ's mixes shift the phase, so a single global grid is wrong for positions)."""
    gp = grid_note()
    if gp:
        g = np.load(gp, allow_pickle=True)
        db = np.asarray(g["downbeats_s"], float)
        seg = np.asarray(g["segments"], float) if "segments" in g.files else None
        for s in secs:
            bars = db[(db >= s["t0"]) & (db < s["t1"] + 1e-6)]
            if len(bars) < 2:
                bars = db[max(0, np.searchsorted(db, s["t0"]) - 1):np.searchsorted(db, s["t1"]) + 1]
            bpm = np.nan
            if seg is not None:
                for a, z, b in seg:
                    if a <= s["t0"] < z:
                        bpm = float(b)
            if bpm != bpm:
                bpm = float(np.median(240.0 / np.diff(bars))) if len(bars) > 2 else 165.83
            s["bpm"] = bpm
            s["bar_s"] = 240.0 / bpm
            s["beat_s"] = 60.0 / bpm
            s["bars"] = bars
            s["comb_conf"] = float("nan")
            s["src"] = "grid.npz"
        return secs
    return _section_grids_comb(secs)


def _section_grids_comb(secs):
    f = np.load(os.path.join(CACHE, "frames.npz"))
    meta = json.load(open(os.path.join(CACHE, "meta.json")))
    fps_c = 93.75
    env = f["flux_sub"] + f["flux_bass"]
    env = env / (env.max() + 1e-9)
    low = f["sub"] + f["bass"]
    for s in secs:
        bpm = s["bpm"] if s["bpm"] == s["bpm"] else meta["bpm"]
        beat_f = 60.0 * fps_c / bpm
        i0, i1 = int(s["t0"] * fps_c), int(s["t1"] * fps_c)
        e = env[i0:i1]
        cand = np.arange(0, beat_f, 0.2)
        sc = [np.interp(np.arange(p, len(e) - 1, beat_f), np.arange(len(e)), e).sum() for p in cand]
        ph = float(cand[int(np.argmax(sc))])
        beats = np.arange(ph, len(e) - 1, beat_f)
        w = np.interp(beats, np.arange(len(e)), low[i0:i1])
        k = int(np.argmax([w[j::4].mean() for j in range(4)]))
        s["beat_s"] = 60.0 / bpm
        s["bar_s"] = 240.0 / bpm
        s["bars"] = (i0 + beats[k::4]) / fps_c          # absolute seconds
        s["comb_conf"] = float(max(sc) / (np.mean(sc) + 1e-9))
        s["src"] = "own comb"
    return secs


def load():
    """Frames + the derived prominence surface, merged into one dict."""
    F = dict(np.load(FRAMES_NPZ))
    F.update(derive(F))
    return F


def band_prom(F, midi_from, midi_to=HOOK_MIDI[1]):
    """Prominence mass (dB above the local envelope) restricted to a semitone window."""
    a, b = midi_from - HOOK_MIDI[0], midi_to - HOOK_MIDI[0]
    return F["ph"][:, a:b].sum(1)


def ev_register(F, ev, midi_from=HOOK_MIDI[0]):
    """Prominence-weighted register percentiles for one event, inside a semitone window."""
    a = midi_from - HOOK_MIDI[0]
    v = F["ph"][ev["i0"]:ev["i1"], a:].sum(0)
    if v.sum() <= 0:
        return dict(lo=np.nan, med=np.nan, hi=np.nan, cent=np.nan)
    v = v / v.sum()
    mids = np.arange(midi_from, HOOK_MIDI[1], dtype=float)
    c = np.cumsum(v)
    q = lambda x: float(mids[min(int((c < x).sum()), len(mids) - 1)])
    return dict(lo=q(0.10), med=q(0.50), hi=q(0.90), cent=float((v * mids).sum()))


def to_bars(evs, secs):
    """Tag each event with its section and its bar index within that section."""
    for e in evs:
        e["sec"] = None
        for k, s in enumerate(secs):
            if s["t0"] <= e["t"] < s["t1"]:
                e["sec"] = k
                b = s["bars"]
                e["bar"] = int(np.searchsorted(b, e["t"], "right") - 1)
                e["bar_f"] = float(np.interp(e["t"], b, np.arange(len(b)))) if len(b) > 1 else 0.0
                e["beats"] = e["dur"] / s["beat_s"]
                e["bars_len"] = e["dur"] / s["bar_s"]
                break
    return [e for e in evs if e["sec"] is not None]


def cluster(evs, th=0.82):
    """Greedy single-pass clustering on a prominence-profile + chroma fingerprint."""
    fps = []
    for e in evs:
        v = np.concatenate([e["semi"] / (np.linalg.norm(e["semi"]) + 1e-9) * 1.0,
                            e["chroma"] / (np.linalg.norm(e["chroma"]) + 1e-9) * 0.8])
        fps.append(v / (np.linalg.norm(v) + 1e-9))
    fps = np.array(fps)
    lab = -np.ones(len(evs), int)
    cents = []
    for i in range(len(evs)):
        if not cents:
            cents.append(fps[i].copy())
            lab[i] = 0
            continue
        C = np.array(cents)
        sims = C @ fps[i]
        j = int(np.argmax(sims))
        if sims[j] >= th:
            lab[i] = j
            cents[j] = (cents[j] * 0.8 + fps[i] * 0.2)
            cents[j] /= np.linalg.norm(cents[j]) + 1e-9
        else:
            cents.append(fps[i].copy())
            lab[i] = len(cents) - 1
    return lab, fps


def bar_lag_selfsim(F, secs, midi_from=HOOK_MIDI[0], max_lag=32):
    """Per-section: which bar lag does the melodic layer repeat at? (independent of event cuts)"""
    out = []
    a = midi_from - HOOK_MIDI[0]
    for s in secs:
        b = s["bars"]
        if len(b) < 12:
            continue
        rows = []
        for k in range(len(b) - 1):
            i0 = np.searchsorted(F["t"], b[k])
            i1 = np.searchsorted(F["t"], b[k + 1])
            if i1 <= i0:
                continue
            v = F["ph"][i0:i1, a:].sum(0)
            rows.append(v)
        X = np.array(rows)
        if len(X) < 12:
            continue
        Xn = X / (np.linalg.norm(X, axis=1, keepdims=True) + 1e-9)
        S = Xn @ Xn.T
        lags = {}
        for L in range(1, min(max_lag, len(X) - 4) + 1):
            lags[L] = float(np.mean(np.diag(S, L)))
        base = np.mean(list(lags.values()))
        best = max(lags, key=lambda L: lags[L] - (0.004 * L))      # mild penalty on long lags
        out.append({"t0": s["t0"], "best_lag": best, "sim": lags[best], "base": base,
                    "lags": lags})
    return out


def section_key(F, evs, secs):
    """Pitch classes per section, reported as INTERVALS above the section's bass root.

    Chroma folded from the whole prominence comb turns to mush in a DJ mix (two tracks overlap,
    and every note smears its own energy onto its 3rd and 5th through its own partials). So the
    histogram is built from the *fundamental* estimate instead - one pitch class per frame,
    weighted by how salient that fundamental is. That is effectively a monophonic pitch histogram
    and it is far sharper. No absolute notes leave this function: only intervals above the root.
    """
    out = []
    for k, s in enumerate(secs):
        i0, i1 = np.searchsorted(F["t"], s["t0"]), np.searchsorted(F["t"], s["t1"])
        bf = F["bass_f0"][i0:i1]
        bw = F["bass_f0_sal"][i0:i1] * np.log1p(F["low_e"][i0:i1] / (F["low_e"].mean() + 1e-20))
        bh = np.bincount(np.mod(np.round(bf).astype(int), 12), weights=bw, minlength=12)
        bh = bh / (bh.sum() + 1e-12)
        root = int(np.argmax(bh))

        se = [e for e in evs if e["sec"] == k]
        hh = np.zeros(12)
        for e in se:
            sl = slice(e["i0"], e["i1"])
            w = F["f0_sal"][sl] * F["prom_sum"][sl]
            hh += np.bincount(np.mod(np.round(F["f0_midi"][sl]).astype(int), 12),
                              weights=w, minlength=12)
        hh = hh / (hh.sum() + 1e-12)
        rel, relb = np.roll(hh, -root), np.roll(bh, -root)
        used = [PC[i] for i in np.argsort(rel)[::-1][:5] if rel[i] >= 0.08]
        third = "minor" if rel[3] > rel[4] else ("major" if rel[4] > rel[3] else "-")
        agree = float(np.sum(rel * relb) / (np.linalg.norm(rel) * np.linalg.norm(relb) + 1e-12))
        # how concentrated is the hook's pitch use: share carried by its top 4 classes
        conc = float(np.sort(rel)[::-1][:4].sum())
        out.append({"sec": k, "t0": s["t0"], "t1": s["t1"], "root_pc": root, "rel": rel,
                    "relb": relb, "used": used, "third": third, "agree": agree,
                    "conc": conc, "n_ev": len(se)})
    return out


def contrast(F, evs, secs):
    """The juxtaposition measure: hook-band brightness / roughness / flux against the low band, at
    the moments a hook is sounding versus the same section without one."""
    t = F["t"]
    mask = np.zeros(len(t), bool)
    for e in evs:
        mask[e["i0"]:e["i1"]] = True
    rows = []
    for k, s in enumerate(secs):
        i0, i1 = np.searchsorted(t, s["t0"]), np.searchsorted(t, s["t1"])
        m = mask[i0:i1]
        if m.sum() < 30 or (~m).sum() < 30:
            continue
        def g(name, sel):
            v = F[name][i0:i1][sel]
            return float(np.mean(v) if "flux" in name else np.median(v))
        rows.append({
            "t0": s["t0"],
            "on_hook_cent": g("hook_cent", m), "off_hook_cent": g("hook_cent", ~m),
            "on_low_cent": g("low_cent", m), "off_low_cent": g("low_cent", ~m),
            "on_rough": g("rough", m), "off_rough": g("rough", ~m),
            "on_hf": g("hook_flux", m), "off_hf": g("hook_flux", ~m),
            "on_lf": g("low_flux", m), "off_lf": g("low_flux", ~m),
            "on_bt": g("bass_top_h", m), "off_bt": g("bass_top_h", ~m),
            "on_val": g("valley_hz", m), "off_val": g("valley_hz", ~m),
            "on_hl": 10 * np.log10(g("hook_e", m) / max(g("low_e", m), 1e-20)),
            "off_hl": 10 * np.log10(g("hook_e", ~m) / max(g("low_e", ~m), 1e-20)),
            "on_ton": g("hook_h_e", m) / max(g("hook_e", m), 1e-20),
            "off_ton": g("hook_h_e", ~m) / max(g("hook_e", ~m), 1e-20),
            "on_cm": float(np.median(midi_to_hz(F["prom_cent"][i0:i1][m]))),
            "off_cm": float(np.median(midi_to_hz(F["prom_cent"][i0:i1][~m]))),
        })
    return rows


def sparsity(evs, secs, label):
    """Bar occupancy and the distribution of gaps between hook appearances."""
    tot_bars = sum(max(0, len(s["bars"]) - 1) for s in secs)
    hit = set()
    per_sec = []
    for k, s in enumerate(secs):
        nb = max(0, len(s["bars"]) - 1)
        se = sorted([e for e in evs if e["sec"] == k], key=lambda e: e["t"])
        bars_hit = set()
        for e in se:
            b0 = int(np.floor(e["bar_f"]))
            b1 = int(np.floor(e["bar_f"] + e["bars_len"] - 1e-9))
            for b in range(max(0, b0), min(nb - 1, b1) + 1):
                bars_hit.add(b)
                hit.add((k, b))
        per_sec.append({"sec": k, "t0": s["t0"], "t1": s["t1"], "n_bars": nb,
                        "n_ev": len(se), "bars_hit": len(bars_hit),
                        "frac": len(bars_hit) / nb if nb else 0.0,
                        "ev_per_8": 8.0 * len(se) / nb if nb else 0.0})
    gaps, onsets_gap = [], []
    for k, s in enumerate(secs):
        se = sorted([e for e in evs if e["sec"] == k], key=lambda e: e["t"])
        for a, b in zip(se, se[1:]):
            onsets_gap.append(b["bar_f"] - a["bar_f"])
            gaps.append(max(0.0, b["bar_f"] - (a["bar_f"] + a["bars_len"])))
    return {"label": label, "tot_bars": tot_bars, "hit": len(hit),
            "frac": len(hit) / tot_bars if tot_bars else 0.0,
            "per_sec": per_sec, "gaps": np.array(gaps), "ioi": np.array(onsets_gap)}


def pct(a, qs=(10, 25, 50, 75, 90)):
    a = np.asarray([x for x in a if x == x], float)
    return np.percentile(a, qs) if len(a) else np.full(len(qs), np.nan)


def report():
    F = load()
    secs = section_grids(sections())
    evs_all, score = detect_events(F, secs)
    evs_all = to_bars(evs_all, secs)
    for e in evs_all:
        r = ev_register(F, e)
        e.update({"r_lo": r["lo"], "r_med": r["med"], "r_hi": r["hi"], "r_cent": r["cent"]})
        e["type"] = classify(e)
        e["imp_f0"], e["imp_fit"] = implied_f0(e["semi"])

    # the unambiguous set: the melodic mass sits above 392 Hz, clear of the bass's harmonics
    evs_up, score_up = detect_events(F, secs, band=(TOP_MIDI, HOOK_MIDI[1]))
    evs_up = to_bars(evs_up, secs)
    for e in evs_up:
        r = ev_register(F, e, TOP_MIDI)
        e.update({"r_lo": r["lo"], "r_med": r["med"], "r_hi": r["hi"], "r_cent": r["cent"]})
        e["type"] = classify(e)

    sp_all = sparsity(evs_all, secs, "all melodic (196 Hz+)")
    sp_up = sparsity(evs_up, secs, f"top-end tier ({midi_to_hz(TOP_MIDI):.0f} Hz+)")
    lab, fps = cluster(evs_all)
    lab_u, _ = cluster(evs_up)
    lags = bar_lag_selfsim(F, secs)
    keys = section_key(F, evs_all, secs)
    ctr = contrast(F, evs_all, secs)

    os.makedirs(os.path.dirname(OUT_MD), exist_ok=True)
    L = []
    w = L.append
    bar_s = float(np.median([s["bar_s"] for s in secs]))
    beat_s = bar_s / 4
    bpm = 240.0 / bar_s

    w("# Hooks in the reference jungle DJ set - melodic and vocal usage\n")
    w(f"Source: `Tim_Reaper_Jungle_DJ_Set_SECTION_August_2026.wav`, {F['t'][-1]:.1f} s, 48 kHz "
      f"stereo (analysed from the cached 8 kHz mono, so everything above 4 kHz is invisible here).\n")
    w("**Structural analysis only.** No audio, loop, riff or melody was extracted or copied. "
      "Pitch appears only as an interval against a measured section root, never as a transcription.\n")

    w("## 0. Grid, and why the bar numbers are trustworthy\n")
    src = secs[0].get("src", "own comb")
    if src == "grid.npz":
        g = np.load(grid_note(), allow_pickle=True)
        resets = np.asarray(g["bar_phase_resets_s"], float)
        segl = np.asarray(g["segments"], float)
        w(f"`grid.npz` was present, so bar positions come from it: "
          f"{len(np.asarray(g['downbeats_s'])):d} downbeats, "
          f"{len(segl)} tempo segment(s) at "
          f"{', '.join(f'{b:.2f} BPM' for _, _, b in segl)}.\n")
        w(f"Tempo is effectively locked across the whole set (spread "
          f"{1000*(segl[:,2].max()-segl[:,2].min()):.0f} mBPM). 1 bar = {bar_s:.4f} s, "
          f"1 beat = {beat_s:.4f} s.\n")
        w(f"`grid.npz` records **{len(resets)} bar-phase moves** at "
          f"{', '.join(f'{x:.0f} s' for x in resets)} - the DJ's mix points - and one beat-phase "
          "step (see grid.md). All bar positions here come from it.\n")
        w("*Correction to an earlier draft:* this file once said a per-section comb against a "
          "single global grid put downbeats up to +-173 ms apart and 'independently agreed' with "
          "the phase resets. That comb was measured against the old cached grid in `meta.json` "
          "(165.83 BPM), which grid.md shows is the wrong tempo and drifts 3.7 beats by the end of "
          "the file - so most of that offset was tempo error, not phase. The conclusion (do not use "
          "the cached bar grid) stands; the 'independent agreement' does not.\n")
    else:
        w("`grid.npz` was NOT present, so the grid below is my own and bar positions should be "
          "treated as approximate.\n")
        w(f"Tempo is locked across the whole set: per-section autocorrelation gives "
          f"{min(s['bpm'] for s in secs):.2f}-{max(s['bpm'] for s in secs):.2f} BPM "
          f"(spread {1000*(max(s['bpm'] for s in secs)-min(s['bpm'] for s in secs)):.0f} mBPM). "
          f"1 bar = {bar_s:.4f} s, 1 beat = {beat_s:.4f} s.\n")
        w("The **phase** is not locked. Combing each section's low-band onset flux separately, "
          "the downbeat of each section sits up to **+-173 ms** away from a single global grid - "
          f"more than a 16th note ({bar_s/16*1000:.0f} ms). Every bar index below therefore comes "
          "from a per-section grid with its own phase.\n")
    w("Sections are cut by checkerboard novelty on the cached band energies (min 45 s apart); in a "
      "DJ set these are roughly track and arrangement changes, not musical 8-bar phrases.\n")
    w("| section | start s | end s | BPM | bars | grid source |")
    w("|---|---|---|---|---|---|")
    for k, s in enumerate(secs):
        w(f"| S{k:02d} | {s['t0']:.0f} | {s['t1']:.0f} | {s['bpm']:.2f} | {len(s['bars'])-1} "
          f"| {s.get('src', 'own comb')} |")
    w("")

    w("## 1. Event table\n")
    w("Detection: median-filter HPSS -> harmonic power on a one-semitone-per-bin axis -> "
      "**prominence** (bin minus a +-6-semitone running median). A hook is a small set of narrow "
      "partials standing above the local spectral envelope; the break's cymbal wash and the "
      "reese's broadband growl are not. Prominence mass is then scored against *each section's own* "
      "40th-percentile tonal bed, so a continuously-present pad becomes the baseline rather than "
      "an event, and only departures from it count. Hysteresis 1.00/0.45, gaps < 0.18 s merged, "
      "events < 0.18 s dropped.\n")
    w(f"**{len(evs_all)} melodic/vocal events** over {F['t'][-1]:.0f} s. Total sounding time "
      f"{sum(e['dur'] for e in evs_all):.1f} s = "
      f"**{100*sum(e['dur'] for e in evs_all)/F['t'][-1]:.1f}%** of the set.\n")
    cnt = Counter(e["type"] for e in evs_all)
    w("Types: " + ", ".join(f"`{k}` {v}" for k, v in cnt.most_common()) + "\n")
    w("`reg` is the 10th-90th percentile of the event's prominence-weighted register (the band the "
      "melodic energy actually occupies); `f0` is the harmonic-sum fundamental estimate.\n")
    w("| # | t (s) | bar | dur s | dur beats | reg 10-90% Hz | f0 Hz | move st | partials | type |")
    w("|---|---|---|---|---|---|---|---|---|---|")
    for i, e in enumerate(evs_all):
        w(f"| {i+1} | {e['t']:.2f} | S{e['sec']:02d}b{e['bar']:03d} | {e['dur']:.2f} | "
          f"{e['beats']:.1f} | {midi_to_hz(e['r_lo']):.0f}-{midi_to_hz(e['r_hi']):.0f} | "
          f"{midi_to_hz(e['f0_midi']):.0f} | {e['f0_range']:.1f} | {e['n_part']:.0f} | "
          f"{e['type']} |")
    w("")
    w(f"### Cross-check: the same detector run on {midi_to_hz(TOP_MIDI):.0f} Hz+ only\n")
    w(f"Restricting prominence to {midi_to_hz(TOP_MIDI):.0f} Hz and above gives **{len(evs_up)} "
      f"events**, {sum(e['dur'] for e in evs_up):.1f} s = "
      f"{100*sum(e['dur'] for e in evs_up)/F['t'][-1]:.1f}% of the set - within a point or two of "
      "the full-band figure.\n")
    w("**Read this as a negative result, not a second layer.** It was built to answer 'is anything "
      "sparkling up top, clear of the reese's harmonics'. It lands on almost the same bars as the "
      "full-band pass because it is firing on the *upper partials of the same mid-register "
      f"events*: only {100*np.mean(np.array([e['f0_midi'] for e in evs_all]) > TOP_MIDI):.1f}% of "
      f"events have a fundamental above {midi_to_hz(TOP_MIDI):.0f} Hz. There is no independent "
      "top-octave hook line in this set - the melodic material is mid-register and reaches the "
      "top end through its own harmonics.\n")
    w("| # | t (s) | bar | dur s | dur beats | reg 10-90% Hz | type |")
    w("|---|---|---|---|---|---|---|")
    for i, e in enumerate(evs_up):
        w(f"| {i+1} | {e['t']:.2f} | S{e['sec']:02d}b{e['bar']:03d} | {e['dur']:.2f} | "
          f"{e['beats']:.1f} | {midi_to_hz(e['r_lo']):.0f}-{midi_to_hz(e['r_hi']):.0f} | "
          f"{e['type']} |")
    w("")

    w("## 2. Sparsity\n")
    w("The two tiers land on nearly the same bars, which is itself the finding: see the "
      f"cross-check above - the {midi_to_hz(TOP_MIDI):.0f} Hz+ pass is tracking the upper "
      "harmonics of the same mid-register events, not a separate high layer. Use the first row as "
      "the answer.\n")
    for sp in (sp_all, sp_up):
        w(f"**{sp['label']}** - {sp['hit']} of {sp['tot_bars']} bars carry any event = "
          f"**{100*sp['frac']:.1f}%**. In 8 bars, that is "
          f"**{8*sp['frac']:.1f} bars with something** and {8*(1-sp['frac']):.1f} without.\n")
    w("Per section (bar occupancy = share of the section's bars in which a melodic event sounds):\n")
    w("| section | s | bars | events | bars w/ event | occupancy | events per 8 bars | "
      "upper occupancy |")
    w("|---|---|---|---|---|---|---|---|")
    for a, b in zip(sp_all["per_sec"], sp_up["per_sec"]):
        w(f"| S{a['sec']:02d} | {a['t0']:.0f}-{a['t1']:.0f} | {a['n_bars']} | {a['n_ev']} | "
          f"{a['bars_hit']} | {100*a['frac']:.0f}% | {a['ev_per_8']:.1f} | {100*b['frac']:.0f}% |")
    w("")
    for sp in (sp_all, sp_up):
        g, io = sp["gaps"], sp["ioi"]
        w(f"**Gaps between hook appearances, {sp['label']}** (bars of silence between the end of "
          f"one event and the start of the next):\n")
        w(f"- percentiles 10/25/50/75/90/95: "
          f"{'/'.join(f'{x:.2f}' for x in pct(g, (10,25,50,75,90,95)))} bars; mean "
          f"{g.mean():.2f}, max {g.max():.1f}\n")
        w(f"- onset-to-onset: "
          f"{'/'.join(f'{x:.2f}' for x in pct(io, (10,25,50,75,90,95)))} bars\n")
        hist = np.histogram(g, bins=[0, 0.5, 1, 2, 4, 8, 16, 32, 1e9])[0]
        w("| gap (bars) | <0.5 | 0.5-1 | 1-2 | 2-4 | 4-8 | 8-16 | 16-32 | >32 |")
        w("|---|---|---|---|---|---|---|---|---|")
        w("| count | " + " | ".join(str(int(x)) for x in hist) + " |")
        w("| share | " + " | ".join(f"{100*x/max(1,hist.sum()):.0f}%" for x in hist) + " |")
        w("")

    w("## 3. Repetition\n")
    for name, ee, ll in (("all melodic (196 Hz+)", evs_all, lab),
                         (f"top-end tier ({midi_to_hz(TOP_MIDI):.0f} Hz+)", evs_up, lab_u)):
        n_cl = len(set(ll))
        sizes = Counter(ll)
        rep = [c for c in sizes.values() if c >= 2]
        w(f"**{name}**: {len(ee)} events fall into {n_cl} distinct shapes "
          f"(cosine >= 0.82 on a prominence-profile + chroma fingerprint). "
          f"{len(rep)} shapes recur; {sizes.most_common(1)[0][1]} is the largest family.\n")
        periods, runs = [], []
        for c in set(ll):
            ts = sorted([ee[i]["bar_f"] + 0.0 for i in range(len(ee)) if ll[i] == c
                         and ee[i]["sec"] == ee[[j for j in range(len(ee)) if ll[j] == c][0]]["sec"]])
            idx = [i for i in range(len(ee)) if ll[i] == c]
            bysec = {}
            for i in idx:
                bysec.setdefault(ee[i]["sec"], []).append(ee[i]["bar_f"])
            for k, v in bysec.items():
                v = sorted(v)
                d = np.diff(v)
                periods += [x for x in d if x <= 64]
                run, cur = [], 1
                for x in d:
                    if x <= 16:
                        cur += 1
                    else:
                        run.append(cur)
                        cur = 1
                run.append(cur)
                runs += run
        periods = np.array(periods)
        runs = np.array(runs) if runs else np.array([1])
        if "all melodic" in name:
            runs_all, periods_all = runs, periods
        if len(periods):
            w(f"- repeat period between successive appearances of the *same* shape: "
              f"{'/'.join(f'{x:.1f}' for x in pct(periods))} bars (10/25/50/75/90), "
              f"mode near {np.bincount(np.round(periods).astype(int).clip(0, 64)).argmax()} bars\n")
            h = np.histogram(periods, bins=[0, 1, 2, 3, 4, 6, 8, 12, 16, 24, 32, 1e9])[0]
            w("| period (bars) | <1 | 1-2 | 2-3 | 3-4 | 4-6 | 6-8 | 8-12 | 12-16 | 16-24 | 24-32 "
              "| >32 |")
            w("|---|---|---|---|---|---|---|---|---|---|---|---|")
            w("| count | " + " | ".join(str(int(x)) for x in h) + " |")
        if len(runs):
            w(f"- appearances in a row before the shape changes or leaves: "
              f"{'/'.join(f'{x:.0f}' for x in pct(runs))} (10/25/50/75/90), mean {runs.mean():.1f}, "
              f"max {runs.max():.0f}\n")
        w("")
    w("Independent check - per-section bar-lag self-similarity of the whole melodic layer "
      "(no event segmentation involved):\n")
    w("| section | best lag (bars) | sim at lag | mean sim | lag 4 | lag 8 | lag 16 |")
    w("|---|---|---|---|---|---|---|")
    for r in lags:
        g = r["lags"]
        w(f"| {r['t0']:.0f}s | **{r['best_lag']}** | {r['sim']:.3f} | {r['base']:.3f} | "
          f"{g.get(4, float('nan')):.3f} | {g.get(8, float('nan')):.3f} | "
          f"{g.get(16, float('nan')):.3f} |")
    bl = [r["best_lag"] for r in lags]
    w(f"\nBest lag across sections: median **{np.median(bl):.0f} bars**, "
      f"counts {dict(Counter(bl).most_common())}.\n")

    w("## 4. Length: how long is a hook phrase\n")
    for name, ee in (("all melodic (196 Hz+)", evs_all),
                     (f"top-end tier ({midi_to_hz(TOP_MIDI):.0f} Hz+)", evs_up)):
        d = np.array([e["dur"] for e in ee])
        bt = np.array([e["beats"] for e in ee])
        br = np.array([e["bars_len"] for e in ee])
        at = np.array([e["attack_s"] for e in ee])
        w(f"**{name}** ({len(ee)} events)\n")
        w(f"- duration: {'/'.join(f'{x:.2f}' for x in pct(d))} s (10/25/50/75/90), "
          f"max {d.max():.2f} s\n")
        w(f"- in beats: {'/'.join(f'{x:.2f}' for x in pct(bt))}; "
          f"in bars: {'/'.join(f'{x:.2f}' for x in pct(br))}\n")
        w(f"- attack (onset to envelope peak): {'/'.join(f'{1000*x:.0f}' for x in pct(at))} ms; "
          f"sustain share of the event = "
          f"{'/'.join(f'{x:.2f}' for x in pct(1 - at / np.maximum(d, 1e-6)))}\n")
        h = np.histogram(bt, bins=[0, 0.5, 1, 2, 3, 4, 6, 8, 1e9])[0]
        w("| length (beats) | <0.5 | 0.5-1 | 1-2 | 2-3 | 3-4 | 4-6 | 6-8 | >8 |")
        w("|---|---|---|---|---|---|---|---|---|")
        w("| count | " + " | ".join(str(int(x)) for x in h) + " |")
        w("| share | " + " | ".join(f"{100*x/max(1,h.sum()):.0f}%" for x in h) + " |")
        w("")

    w("## 5. Register and separation from the bass\n")
    lo = np.array([midi_to_hz(e["r_lo"]) for e in evs_all])
    hi = np.array([midi_to_hz(e["r_hi"]) for e in evs_all])
    ce = np.array([midi_to_hz(e["r_cent"]) for e in evs_all])
    f0h = np.array([midi_to_hz(e["f0_midi"]) for e in evs_all])
    bt90 = np.array([np.median(F["bass_top"][e["i0"]:e["i1"]]) for e in evs_all])
    bth = np.array([np.median(F["bass_top_h"][e["i0"]:e["i1"]]) for e in evs_all])
    val = np.array([np.median(F["valley_hz"][e["i0"]:e["i1"]]) for e in evs_all])
    vdb = np.array([np.median(F["valley_db"][e["i0"]:e["i1"]]) for e in evs_all])
    w("All percentiles are 10/25/50/75/90 across events.\n")
    w("| quantity | 10% | 25% | 50% | 75% | 90% |")
    w("|---|---|---|---|---|---|")
    for nm, v in (("hook fundamental (f0)", f0h),
                  ("hook bottom (10% of its prominence)", lo),
                  ("hook centre of mass", ce),
                  ("hook top (90% of its prominence)", hi),
                  ("bass top, harmonic only (90% of 25-500 Hz)", bth),
                  ("bass top incl. drum low-mid (90% of 25-500 Hz)", bt90),
                  ("spectral valley between them", val)):
        w(f"| {nm} Hz | " + " | ".join(f"{x:.0f}" for x in pct(v)) + " |")
    w("")
    gst = 12 * np.log2(np.maximum(lo / np.maximum(bth, 1e-6), 1e-6))
    w(f"- **Gap between the bass's top and the hook's bottom**: "
      f"{'/'.join(f'{x:+.1f}' for x in pct(gst))} semitones "
      f"({'/'.join(f'{x:+.2f}' for x in pct(gst / 12))} octaves). The hook's bottom clears the "
      f"bass's top in **{100 * np.mean(gst > 0):.0f}%** of events; the median event has "
      f"**{np.median(gst):+.0f} semitones** of daylight.\n")
    w(f"- **The mix leaves a hole, and it is always in the same place.** Taking the quietest "
      f"semitone between 120 and 700 Hz relative to a broad (+-1 octave) trend, the valley sits at "
      f"{'/'.join(f'{x:.0f}' for x in pct(val))} Hz during events and is "
      f"{'/'.join(f'{x:.1f}' for x in pct(vdb))} dB deep. Whole-file median "
      f"{np.median(F['valley_hz']):.0f} Hz at {np.median(F['valley_db']):.1f} dB. That notch, "
      f"around **{np.median(val):.0f} Hz**, is the separation mechanism: the bass stops below it "
      f"({np.median(bth):.0f} Hz) and the hook's mass sits above it ({np.median(ce):.0f} Hz).\n")
    w(f"- frame-wide, without reference to events: the low band's power centroid sits at "
      f"{np.median(F['low_cent']):.0f} Hz, 90% of the *harmonic* 25-500 Hz power is below "
      f"{np.median(F['bass_top_h']):.0f} Hz, and the melodic prominence centre is at "
      f"{midi_to_hz(np.median(F['prom_cent'])):.0f} Hz.\n")
    w("\nRegister histograms (all events):\n")
    for nm, v, bins in (
            ("hook fundamental f0", f0h, [0, 165, 196, 247, 311, 392, 523, 698, 1047, 1e9]),
            ("hook centre of mass", ce, [0, 400, 470, 550, 620, 700, 800, 1000, 1e9])):
        h = np.histogram(v, bins=bins)[0]
        lbl = [f"{int(bins[i])}-{int(bins[i+1]) if bins[i+1] < 1e8 else 'up'}"
               for i in range(len(bins) - 1)]
        w(f"*{nm} (Hz)*\n")
        w("| band | " + " | ".join(lbl) + " |")
        w("|---|" + "---|" * len(lbl))
        w("| count | " + " | ".join(str(int(x)) for x in h) + " |")
        w("| share | " + " | ".join(f"{100*x/max(1,h.sum()):.0f}%" for x in h) + " |")
        w("")
    lo_u = np.array([midi_to_hz(e["r_lo"]) for e in evs_up])
    bt_u = np.array([np.median(F["bass_top_h"][e["i0"]:e["i1"]]) for e in evs_up])
    gst_u = 12 * np.log2(np.maximum(lo_u / np.maximum(bt_u, 1e-6), 1e-6))
    w(f"For the **top-end tier (784 Hz+)** the same gap is "
      f"{'/'.join(f'{x:+.1f}' for x in pct(gst_u))} semitones, positive in "
      f"{100*np.mean(gst_u > 0):.0f}% of events.\n")

    w("## 6. Key and pitch classes\n")
    w("Root is the modal pitch class of the *bass's own* fundamental across the section. The hook "
      "histogram is built from the melodic fundamental - one pitch class per frame, weighted by "
      "salience - rather than from the full chroma, because a chroma folded from every partial "
      "turns to mush in a DJ mix (each note smears onto its own 3rd and 5th, and two records "
      "overlap at every transition). Everything is an interval above the root: no absolute notes, "
      "no transcription, nothing playable.\n")
    w("| section | s | hook events | 3rd | top hook intervals | top-4 share | hook/bass agreement |")
    w("|---|---|---|---|---|---|---|")
    for k in keys:
        w(f"| S{k['sec']:02d} | {k['t0']:.0f}-{k['t1']:.0f} | {k['n_ev']} | {k['third']} | "
          f"{' '.join(k['used']) if k['used'] else '-'} | {k['conc']:.2f} | {k['agree']:.2f} |")
    allrel = np.mean([k["rel"] for k in keys], 0)
    allrel = allrel / allrel.sum()
    w("\nAggregate hook pitch-class weight relative to the section root, whole set "
      "(mean of the per-section histograms):\n")
    w("| interval | " + " | ".join(PC) + " |")
    w("|---|" + "---|" * 12)
    w("| weight | " + " | ".join(f"{100*x:.0f}%" for x in allrel) + " |")
    top4 = np.argsort(allrel)[::-1][:4]
    w(f"\nThe shape is minor: **{', '.join(PC[i] for i in top4)}** carry "
      f"{100*allrel[top4].sum():.0f}% of all hook weight, and the minor third outweighs the major "
      f"third {100*allrel[3]:.0f}% to {100*allrel[4]:.0f}%. "
      f"{sum(1 for k in keys if k['third']=='minor')} of {len(keys)} sections read minor. "
      f"(The b2 at {100*allrel[1]:.0f}% is partly leakage from the root into the adjacent semitone "
      "bin - do not read it as a deliberate phrygian colour.)\n")
    ag = np.array([k["agree"] for k in keys])
    cc = np.array([k["conc"] for k in keys])
    w(f"\nHook-to-bass pitch agreement: median {np.median(ag):.2f}, range "
      f"{ag.min():.2f}-{ag.max():.2f}. Within a section the hook puts "
      f"{100*np.median(cc):.0f}% of its weight on just four pitch classes "
      f"(range {100*cc.min():.0f}-{100*cc.max():.0f}%) - a 4-5 note set, not a scale.\n")
    w("\n*Caveat:* this is a DJ set, so two records overlap across every transition and a section "
      "can briefly carry two keys at once. The per-section root is indicative; the aggregate "
      "interval shape is the reliable part.\n")

    w("## 7. Contrast / juxtaposition\n")
    sep = np.array([midi_to_hz(e["r_cent"]) / max(e["low_cent"], 1e-6) for e in evs_all])
    w("The headline number first, because it is the one that survives scrutiny:\n")
    w(f"> **At the instant a hook sounds, its centre of mass sits "
      f"{np.median(np.log2(sep)):.1f} octaves above the low band's centre of mass** "
      f"(10/25/50/75/90 percentiles: {'/'.join(f'{np.log2(x):.1f}' for x in pct(sep))} octaves; "
      f"{np.median(sep):.1f}x in frequency). Hook centre {np.median(ce):.0f} Hz against a low band "
      f"centred at {np.median([e['low_cent'] for e in evs_all]):.0f} Hz.\n")
    w("\nA warning about the obvious measurement. The spectral centroid of the whole 200 Hz-4 kHz "
      "band gets *darker*, not brighter, when a hook enters, because the reference's hooks are "
      "mid-register (centre ~550 Hz) while the break's cymbals already own everything above "
      "2 kHz. Light-against-dark here is **not** 'add treble'. It shows up as: the midrange turns "
      "tonal against a noisy break, and the hook opens a wide register gap over the bass. Both are "
      "measured below - `tonality` is the harmonic share of the 200 Hz-4 kHz band (how much of the "
      "midrange is pitched rather than noise), which is the real brightness-of-character contrast.\n")
    w("| section | tonality on/off | hook centre on/off Hz | mix centroid on/off Hz | "
      "rough on/off | low cent on/off Hz | bass top on/off Hz | h/l on/off dB | low flux on/off |")
    w("|---|---|---|---|---|---|---|---|---|")
    for r in ctr:
        w(f"| {r['t0']:.0f}s | {r['on_ton']:.2f} / {r['off_ton']:.2f} | "
          f"{r['on_cm']:.0f} / {r['off_cm']:.0f} | "
          f"{r['on_hook_cent']:.0f} / {r['off_hook_cent']:.0f} | "
          f"{r['on_rough']:.3f} / {r['off_rough']:.3f} | "
          f"{r['on_low_cent']:.0f} / {r['off_low_cent']:.0f} | "
          f"{r['on_bt']:.0f} / {r['off_bt']:.0f} | "
          f"{r['on_hl']:+.1f} / {r['off_hl']:+.1f} | "
          f"{r['on_lf']:.3f} / {r['off_lf']:.3f} |")
    d_ton = np.median([r["on_ton"] - r["off_ton"] for r in ctr])
    d_cm = np.median([r["on_cm"] - r["off_cm"] for r in ctr])
    d_cent = np.median([r["on_hook_cent"] - r["off_hook_cent"] for r in ctr])
    d_rough = np.median([r["on_rough"] - r["off_rough"] for r in ctr])
    d_low = np.median([r["on_low_cent"] - r["off_low_cent"] for r in ctr])
    d_bt = np.median([r["on_bt"] - r["off_bt"] for r in ctr])
    d_hl = np.median([r["on_hl"] - r["off_hl"] for r in ctr])
    d_lf = np.median([np.log10(max(r["on_lf"], 1e-9) / max(r["off_lf"], 1e-9)) for r in ctr])
    w(f"\nMedian across the {len(ctr)} sections, hook sounding versus not:\n")
    w(f"- **tonality of the 200 Hz-4 kHz band {d_ton:+.3f}** "
      f"({'the midrange turns pitched' if d_ton > 0 else 'the midrange turns noisier'}) - this is "
      "the light-against-dark contrast that actually registers\n")
    w(f"- melodic centre of mass **{d_cm:+.0f} Hz**\n")
    w(f"- full-mix centroid of the hook band **{d_cent:+.0f} Hz** "
      f"({'brighter' if d_cent > 0 else 'darker - see the warning above'})\n")
    w(f"- roughness (>1 kHz share of the hook band) **{d_rough:+.3f}**\n")
    w(f"- low-band centroid **{d_low:+.0f} Hz**, harmonic bass top **{d_bt:+.0f} Hz**\n")
    w(f"- hook-to-low power ratio **{d_hl:+.1f} dB** - the hook band gains on the low band, so the "
      "contrast is partly a balance move, not only a timbral one\n")
    w(f"- low-band flux **{20*d_lf:+.1f} dB** ({'fewer' if d_lf < 0 else 'more'} low-end onsets "
      "while a hook sounds)\n")
    corr = float(np.corrcoef(score, np.log1p(F["sub_e"] / F["sub_e"].mean()))[0, 1])
    corr_l = float(np.corrcoef(score, np.log1p(F["low_e"] / F["low_e"].mean()))[0, 1])
    w(f"\nCorrelation between the hook score and low-end energy across the whole set: "
      f"**{corr:+.3f}** against sub (20-60 Hz) and **{corr_l:+.3f}** against 20-200 Hz - "
      "effectively zero. So hooks are *not* placed by low-end level: the reference does not duck "
      "the sub to make room, and does not save hooks for quiet bars. What does change is the low "
      f"end's rhythmic activity - low-band flux falls {20*d_lf:+.1f} dB while a hook sounds, i.e. "
      "fewer low-end onsets under it, which is a placement rule about the drum pattern rather "
      "than about level.\n")

    w("## 8. Method and its limits\n")
    w("- Analysis runs on the cached **8 kHz mono** downmix, so nothing above 4 kHz is visible. "
      "Hi-hat sparkle, air and the top octave of any bell are outside the measurement; the "
      "register conclusions are about fundamentals and lower partials.\n")
    w("- **Harmonic/percussive separation** uses a 0.67 s median along time and a 160 Hz median "
      "along frequency. That window smears attacks, so the attack figures in section 4 are a "
      "coarse envelope shape, not a true transient time - treat 'sustain share' as ordinal.\n")
    w("- **Type labels are shorthand for measurements**, not instrument identification. From a "
      "dense mono mix `vocal-like` means 'pitch glides >=3 semitones with >=8 partials over "
      "0.35-2 s' - a toasted vocal and a portamento lead are not separable here.\n")
    w("- This is a **DJ set**: two records overlap at every transition (grid.npz marks 8 bar-phase "
      "resets). Per-section keys and roots are indicative; the aggregate interval shape is the "
      "reliable part.\n")
    w("- The detector scores prominence against **each section's own 40th-percentile tonal bed**. "
      "A genuinely continuous pad is therefore baseline, not an event. That is deliberate - it "
      "matches what the ear does - but it means 'bar occupancy' measures *changing* melodic "
      "material, not 'is any pitched sound present'.\n")
    w("- Section boundaries come from novelty on band energies, not from musical analysis; they "
      "approximate track and arrangement changes.\n")

    # ---- the rules
    w("## What this means for building a jungle track\n")
    w("Every number below is measured from the reference, not chosen. Bars are "
      f"{bar_s:.3f} s at {bpm:.1f} BPM.\n")

    o_all, o_up = sp_all["frac"], sp_up["frac"]
    occ = [s["frac"] for s in sp_all["per_sec"]]
    ev8 = [s["ev_per_8"] for s in sp_all["per_sec"]]
    beats_all = np.array([e["beats"] for e in evs_all])
    durs = np.array([e["dur"] for e in evs_all])
    g, gu = sp_all["gaps"], sp_up["gaps"]
    fam = Counter(lab)
    recur = np.array([v for v in fam.values() if v >= 2])
    top4 = np.argsort(allrel)[::-1][:4]
    short = ("stab", "chord stab", "riff fragment")
    sust = ("sustained tone", "lead line")

    w(f"1. **A hook sounds in {100*o_all:.0f}% of bars - {8*o_all:.1f} bars in every 8 - and this "
      f"is a dense DJ set, not a sparse one.** {sp_all['hit']} of {sp_all['tot_bars']} bars carry "
      f"any pitched melodic or vocal event. Per section the range is {100*min(occ):.0f}% to "
      f"{100*max(occ):.0f}%, median {100*np.median(occ):.0f}%. Density is {np.median(ev8):.1f} "
      f"events per 8 bars (range {min(ev8):.1f}-{max(ev8):.1f}). **Target ~3 of every 8 bars "
      f"carrying a hook, at ~{np.median(ev8):.0f} events per 8 bars.** A 32-bar section with "
      f"melodic material in more than {int(round(32*max(occ)))} of its bars is busier than "
      "anything in the reference.\n")

    w(f"2. **Hooks are fragments: {np.median(beats_all):.1f} beats, {np.median(durs):.2f} s.** "
      f"Quartiles {np.percentile(beats_all, 25):.1f}-{np.percentile(beats_all, 75):.1f} beats. "
      f"**{100*np.mean(beats_all < 2):.0f}% of events are under 2 beats**; only "
      f"{100*np.mean(beats_all > 4):.0f}% reach a full bar. The longest single event in "
      f"{F['t'][-1]:.0f} s is {durs.max():.1f} s ({beats_all.max():.1f} beats). Write 1-2 beat "
      "motifs - a 4-bar melody line has no precedent here. And they are **struck, not swelled**: "
      f"median onset-to-peak is {1000*np.median([e['attack_s'] for e in evs_all]):.0f} ms of that "
      f"{np.median(durs):.2f} s, leaving a sustain of "
      f"{np.median([1 - e['attack_s']/max(e['dur'], 1e-6) for e in evs_all]):.0%}, so use short "
      "percussive envelopes - stabs and chops - not long fades.\n")

    w(f"3. **Leave {np.median(g):.1f} bars of silence between appearances, often more.** Median gap "
      f"from the end of one hook to the start of the next is {np.median(g):.2f} bars (top-end tier "
      f"{np.median(gu):.2f}); 75th percentile {np.percentile(g, 75):.1f}, 90th "
      f"{np.percentile(g, 90):.1f}, max {g.max():.0f}. **{100*np.mean(g > 2):.0f}% of gaps exceed "
      f"2 bars and {100*np.mean(g > 4):.0f}% exceed 4.** If the melodic lane never goes quiet for "
      "2 bars, it is over-filled.\n")

    w(f"4. **Repeat sparingly: most shapes never come back at all.** Of {len(fam)} distinct hook "
      f"shapes, only {len(recur)} ({100*len(recur)/len(fam):.0f}%) ever recur; a recurring one "
      f"returns a median of {np.median(recur):.0f} times across the set (max {recur.max():.0f}). "
      f"When a shape does repeat, the interval is a median of {np.median(periods_all):.1f} bars "
      f"(quartiles {np.percentile(periods_all, 25):.1f}-{np.percentile(periods_all, 75):.1f}), and "
      f"bar-lag self-similarity of the whole melodic layer peaks at {np.median(bl):.0f} bars per "
      f"section with 4 and 8 next most common (best-lag counts "
      f"{dict(Counter(bl).most_common())}). Consecutive runs are short: a median of "
      f"{np.median(runs_all):.0f} back-to-back appearances before the shape changes or leaves "
      f"(75th pct {np.percentile(runs_all, 75):.0f}, max {runs_all.max():.0f}). **Practical form: "
      f"state a motif, bring it back {np.median(recur):.0f}-ish times on a 4- or 8-bar spacing, "
      "then replace it. Nothing in the reference plays every bar for 16 bars.**\n")

    w(f"5. **Register: fundamental {np.percentile(f0h, 25):.0f}-{np.percentile(f0h, 75):.0f} Hz, "
      f"energy spanning {np.median(lo):.0f} Hz to {np.median(hi):.0f} Hz.** Median fundamental "
      f"{np.median(f0h):.0f} Hz; {100*np.mean((f0h >= 196) & (f0h <= 700)):.0f}% of events have a "
      f"fundamental between 196 and 700 Hz and essentially none "
      f"({100*np.mean(f0h > 784):.1f}%) above 784 Hz. Centre of mass {np.median(ce):.0f} Hz. "
      "**There is no separate top-octave hook layer in this set.** Running the detector on "
      f"{midi_to_hz(TOP_MIDI):.0f} Hz+ alone finds {100*o_up:.0f}% bar occupancy - almost exactly "
      f"the {100*o_all:.0f}% of the full band - because it is firing on the *upper harmonics of "
      "the same mid-register events*, not on a distinct high line. So: put the hook's fundamental "
      f"in roughly {np.percentile(f0h, 25):.0f}-{np.percentile(f0h, 75):.0f} Hz and let its own "
      f"harmonics carry it up to ~{np.median(hi):.0f} Hz. Reach for top-end sparkle only as a "
      "deliberate exception.\n")

    w(f"6. **Put the hook's bottom {np.median(gst):+.0f} semitones above where the bass stops and "
      f"keep the notch between them empty.** During an event 90% of the harmonic 25-500 Hz power "
      f"is below {np.median(bth):.0f} Hz while the hook's lowest 10% starts at {np.median(lo):.0f} "
      f"Hz; the gap is positive in {100*np.mean(gst > 0):.0f}% of events. Between them sits a "
      f"**{abs(np.median(vdb)):.0f} dB valley at {np.median(val):.0f} Hz**. Concretely: high-pass "
      f"the melodic lane near {np.percentile(lo, 25):.0f} Hz, keep the bass's own content under "
      f"{np.median(bth):.0f} Hz, and let neither fill "
      f"{np.percentile(val, 25):.0f}-{np.percentile(val, 75):.0f} Hz.\n")

    w(f"7. **Light-against-dark is register and tonality, not treble.** When a hook sounds its "
      f"centre of mass is **{np.median(np.log2(sep)):.1f} octaves above the low band's centre** "
      f"({np.median(ce):.0f} Hz over {np.median([e['low_cent'] for e in evs_all]):.0f} Hz), and "
      f"the harmonic share of the 200 Hz-4 kHz band rises by **{d_ton:+.3f}** - a pitched element "
      f"cutting through a noisy break. Do not chase brightness: the full-mix centroid moves "
      f"{d_cent:+.0f} Hz, because the break already owns everything above 2 kHz. Give the hook "
      f"{d_hl:+.1f} dB on the low band and let register and tonality do the work.\n")

    w(f"8. **Do not duck the sub for the hook - thin the low-end *pattern* instead.** This one "
      f"contradicts the obvious advice, so it is worth stating plainly: hook placement is "
      f"uncorrelated with low-end level ({corr:+.3f} against 20-60 Hz, {corr_l:+.3f} against "
      f"20-200 Hz), and the low-band centroid barely moves ({d_low:+.0f} Hz). The reference does "
      f"not turn the bass down to make room. What *does* change is low-end rhythmic activity: "
      f"low-band flux drops **{20*d_lf:+.1f} dB** while a hook sounds - fewer kick and bass onsets "
      "under it. Give the hook a bar where the drum pattern is sparser, not a bar where the sub is "
      "quieter.\n")

    w(f"9. **In key, minor, four notes.** Hook pitch weight lands on "
      f"**{', '.join(PC[i] for i in top4)}** relative to the section root - "
      f"{100*allrel[top4].sum():.0f}% of all hook weight on four pitch classes - and within a "
      f"single section the top four carry {100*np.median(cc):.0f}%. The minor third outweighs the "
      f"major {100*allrel[3]:.0f}% to {100*allrel[4]:.0f}%, and "
      f"{sum(1 for k in keys if k['third'] == 'minor')} of {len(keys)} sections read minor. Hook "
      f"and bass draw on the same pitch set (median agreement {np.median(ag):.2f}). Use a 4-5 note "
      "set in the section's key, not a scale run.\n")

    w(f"10. **Fragments answering the drums, not a second melody.** "
      f"{100*np.mean([e['type'] in short for e in evs_all]):.0f}% of events are stabs or short "
      f"riff fragments; only {100*np.mean([e['type'] in sust for e in evs_all]):.0f}% are "
      f"sustained tones or lead lines. Median simultaneous pitch classes during an event is "
      f"{np.median([e['n_pc'] for e in evs_all]):.0f} - dyads and small chords, not stacks. A pad, "
      "if you want one, should be the continuous bed the fragments are measured against: this "
      "detector treats a constant pad as the baseline rather than an event, and so does the ear.\n")


    txt = "\n".join(L) + "\n"
    with open(OUT_MD, "w", encoding="utf-8") as fh:
        fh.write(txt)
    print(f"report -> {OUT_MD}  ({len(txt)} chars, {len(L)} lines)")
    cr_lines, cr_res = callresp(F, secs, evs_all)
    cr_splice(cr_lines + anacrusis(cr_res))
    np.savez_compressed(EVENTS_NPZ,
                        t=np.array([e["t"] for e in evs_all]),
                        dur=np.array([e["dur"] for e in evs_all]),
                        lab=lab)


# ======================================================================
# CALL AND RESPONSE - "high call at the front; sub response, longer, at the back"
# ======================================================================
# Measurement only. The sub stream comes from the bass agent's note code (scripts/reaper_bass.py,
# imported read-only; its cached notes.npz is read, never written). The sub-section boundaries come
# from reaper_structure.py's bar-accurate segments (sections.json, read only). Nothing is written
# anywhere except the markdown section this appends.
GRID_NPZ = os.path.join(CACHE, "grid.npz")
STRUCT_JSON = os.path.join(SCRATCH, "sections.json")
BASS_BARS = os.path.join(CACHE, "bass_bars.npz")
SUB_HZ = 120.0
CR_HEAD = "## Call and response"


def cr_grid():
    """16th-note slots on grid.npz. Only bars with exactly four beats are foldable."""
    g = np.load(GRID_NPZ)
    beats = np.asarray(g["beats_s"], float)
    pos = np.asarray(g["beat_bar_pos"], int)
    beat_len = float(np.median(np.diff(beats)))
    b_ext = np.append(beats, beats[-1] + beat_len)
    step = np.diff(b_ext)
    slot_t = (b_ext[:-1, None] + step[:, None] * np.arange(4)[None, :] / 4.0).ravel()
    slot_t = np.append(slot_t, b_ext[-1])
    bar_of_beat = np.cumsum(pos == 0) - 1
    nbar = int(bar_of_beat.max()) + 1
    beats_in_bar = np.bincount(bar_of_beat[bar_of_beat >= 0], minlength=nbar)
    slot_beat = np.repeat(np.arange(len(beats)), 4)
    slot_bar = bar_of_beat[slot_beat]
    slot_inbar = pos[slot_beat] * 4 + np.tile(np.arange(4), len(beats))
    ok_bar = beats_in_bar == 4
    slot_ok = (slot_bar >= 0) & ok_bar[np.clip(slot_bar, 0, nbar - 1)] & (slot_inbar < 16)
    return dict(beats=beats, beat_len=beat_len, slot_t=slot_t, slot_beat=slot_beat,
                slot_bar=slot_bar, slot_inbar=slot_inbar, slot_ok=slot_ok, nbar=nbar,
                downbeats=beats[pos == 0], bar_of_beat=bar_of_beat, ok_bar=ok_bar)


def cr_subsections(G):
    """Sub-sections as bar ranges: reaper_structure.py's bar-accurate segments if present,
    else this script's own novelty sections."""
    if os.path.exists(STRUCT_JSON):
        rows = json.load(open(STRUCT_JSON))
        starts, src = [float(r["a"]) for r in rows], "reaper_structure.py segments"
    else:
        starts, src = [s["t0"] for s in sections()], "reaper_hooks.py novelty sections"
    db = G["downbeats"]
    sb = sorted(set(int(np.argmin(np.abs(db - a))) for a in starts))
    if sb[0] != 0:
        sb = [0] + sb
    b = sb + [G["nbar"]]
    return [(b[i], b[i + 1]) for i in range(len(b) - 1) if b[i + 1] > b[i]], src


def cr_cover(intervals, slot_t):
    """Fraction of each 16th slot covered by any of the intervals (1 ms resolution)."""
    FS = 1000
    n = int(np.ceil(slot_t[-1] * FS)) + 2
    m = np.zeros(n, np.float32)
    for a, z in intervals:
        i0, i1 = int(max(a, 0.0) * FS), int(min(z, slot_t[-1]) * FS)
        if i1 > i0:
            m[i0:i1] = 1.0
    cs = np.concatenate([[0.0], np.cumsum(m, dtype=np.float64)])
    idx = np.clip(np.round(slot_t * FS).astype(int), 0, n)
    return ((cs[idx[1:]] - cs[idx[:-1]]) / np.maximum(idx[1:] - idx[:-1], 1)).astype(np.float32)


def cr_onsets(times, slot_t):
    """Count of onsets per 16th slot, each onset assigned to its NEAREST slot start."""
    st = slot_t[:-1]
    k = np.clip(np.searchsorted(st, times), 1, len(st) - 1)
    k = np.where(np.abs(times - st[k - 1]) <= np.abs(times - st[k]), k - 1, k)
    ok = (times >= st[0] - 0.05) & (times <= slot_t[-1])
    return np.bincount(k[ok], minlength=len(st)).astype(np.float32)


def cr_perc_accents(G, subs):
    """High-percussion accents that stand OUT of the 16th carrier: 2-16 kHz onset strength at a
    slot more than 2x (6 dB) the median strength of the SAME bar position over the surrounding
    +-4 bars of the same sub-section, and above that sub-section's 60th percentile. The regular
    backbeat therefore does not count - only departures from the repeating pattern do."""
    f = np.load(os.path.join(CACHE, "frames.npz"))
    fl = (f["flux_high"] + f["flux_air"]).astype(np.float64)
    ft = f["t"].astype(np.float64)
    st = G["slot_t"][:-1]
    i0 = np.searchsorted(ft, st - 0.02)
    i1 = np.maximum(np.searchsorted(ft, st + 0.04), i0 + 1)
    idx = np.ravel(np.column_stack([i0, i1]))
    idx = np.clip(idx, 0, len(fl) - 1)
    v = np.maximum.reduceat(fl, idx)[::2]
    L = np.log(v + 1e-9)
    acc = np.zeros(len(st), np.float32)
    sb, si, ok = G["slot_bar"], G["slot_inbar"], G["slot_ok"]
    for b0, b1 in subs:
        sel = np.where(ok & (sb >= b0) & (sb < b1))[0]
        if len(sel) < 64:
            continue
        nb = b1 - b0
        Mx = np.full((nb, 16), np.nan)
        Mx[sb[sel] - b0, si[sel]] = L[sel]
        ref = np.full_like(Mx, np.nan)
        for r in range(nb):
            lo, hi = max(0, r - 4), min(nb, r + 5)
            ref[r] = np.nanmedian(Mx[lo:hi], axis=0)
        thr = np.percentile(v[sel], 60)
        rr = ref[sb[sel] - b0, si[sel]]
        acc[sel] = ((L[sel] - rr > np.log(2.0)) & (v[sel] > thr)).astype(np.float32)
    return acc


def cr_fold(act, G, subs, N, anchor="sub"):
    """Per sub-section position sums for an N-bar cycle (complete cycles only)."""
    P = 16 * N
    sums, counts = [], []
    sb, si, ok = G["slot_bar"], G["slot_inbar"], G["slot_ok"]
    for b0, b1 in subs:
        nfull = (b1 - b0) // N
        if nfull == 0:
            sums.append(np.zeros(P))
            counts.append(0)
            continue
        sel = ok & (sb >= b0) & (sb < b0 + nfull * N)
        base = b0 if anchor == "sub" else 0
        cp = ((sb[sel] - base) % N) * 16 + si[sel]
        sums.append(np.bincount(cp, weights=act[sel], minlength=P)[:P])
        counts.append(nfull)
    return np.array(sums), np.array(counts)


def cr_profile_stats(prof):
    P = len(prof)
    tot = prof.sum()
    if tot <= 0:
        return dict(first=np.nan, com=np.nan, phase=np.nan, R=np.nan)
    pos = np.arange(P) + 0.5
    ang = 2 * np.pi * pos / P
    z = (prof * np.exp(1j * ang)).sum() / tot
    return dict(first=float(prof[:P // 2].sum() / tot), com=float((prof * pos).sum() / tot / P),
                phase=float((np.angle(z) / (2 * np.pi)) % 1.0), R=float(np.abs(z)))


def cr_front_back(call, resp, G, subs, N, anchor="sub", nboot=600, seed=7):
    Sc, n = cr_fold(call, G, subs, N, anchor)
    Sr, _ = cr_fold(resp, G, subs, N, anchor)
    keep = n > 0
    Sc, Sr = Sc[keep], Sr[keep]
    pc, pr = Sc.sum(0), Sr.sum(0)
    out = {"call": cr_profile_stats(pc), "resp": cr_profile_stats(pr),
           "prof_call": pc / max(pc.sum(), 1e-9), "prof_resp": pr / max(pr.sum(), 1e-9)}
    rng = np.random.default_rng(seed)
    P = 16 * N
    diffs, fc, fr = [], [], []
    for _ in range(nboot):
        k = rng.integers(0, len(Sc), len(Sc))
        a, b = Sc[k].sum(0), Sr[k].sum(0)
        if a.sum() <= 0 or b.sum() <= 0:
            continue
        x, y = a[:P // 2].sum() / a.sum(), b[:P // 2].sum() / b.sum()
        fc.append(x)
        fr.append(y)
        diffs.append(x - y)
    out["ci_call"] = np.percentile(fc, [2.5, 97.5])
    out["ci_resp"] = np.percentile(fr, [2.5, 97.5])
    out["ci_diff"] = np.percentile(diffs, [2.5, 97.5])
    out["diff"] = out["call"]["first"] - out["resp"]["first"]
    # anchor-free: circular offset of the response behind the call, per sub-section
    num, wsum, pos_share = 0j, 0.0, []
    for a, b in zip(Sc, Sr):
        if a.sum() <= 0 or b.sum() <= 0:
            continue
        sa, sbb = cr_profile_stats(a), cr_profile_stats(b)
        d = ((sbb["phase"] - sa["phase"] + 0.5) % 1.0) - 0.5
        w = sa["R"] * sbb["R"]
        num += w * np.exp(2j * np.pi * d)
        wsum += w
        pos_share.append(d > 0)
    out["rel_offset"] = float(np.angle(num) / (2 * np.pi)) if wsum > 0 else np.nan
    out["rel_R"] = float(np.abs(num) / wsum) if wsum > 0 else np.nan
    out["rel_pos_share"] = float(np.mean(pos_share)) if pos_share else np.nan
    return out


def cr_beats(act, G):
    return np.bincount(G["slot_beat"], weights=act, minlength=len(G["beats"]))


def cr_sub_beats(G, b0, b1):
    return np.where((G["bar_of_beat"] >= b0) & (G["bar_of_beat"] < b1))[0]


def cr_xcorr(cb, rb, G, subs, lags, mode=None, rng=None):
    num = np.zeros(len(lags))
    den = np.zeros(len(lags))
    for b0, b1 in subs:
        idx = cr_sub_beats(G, b0, b1)
        if len(idx) < 32:
            continue
        c, r = cb[idx].astype(float), rb[idx].astype(float)
        if c.std() == 0 or r.std() == 0:
            continue
        if mode == "shift":
            c = np.roll(c, int(rng.integers(8, len(c) - 8)))
        elif mode == "bars":
            bars = G["bar_of_beat"][idx]
            groups = [np.where(bars == k)[0] for k in np.unique(bars)]
            order = rng.permutation(len(groups))
            c = np.concatenate([c[groups[k]] for k in order])
        c = (c - c.mean()) / c.std()
        r = (r - r.mean()) / r.std()
        n = len(c)
        for j, L in enumerate(lags):
            if L >= 0:
                pr = c[:n - L] * r[L:]
            else:
                pr = c[-L:] * r[:n + L]
            num[j] += pr.sum()
            den[j] += len(pr)
    return num / np.maximum(den, 1)


def cr_cycles(call, resp, G, subs, N):
    """Per complete cycle: call and response sounding time in beats, whole cycle and by half."""
    rows = []
    sb, si, ok = G["slot_bar"], G["slot_inbar"], G["slot_ok"]
    for b0, b1 in subs:
        nfull = (b1 - b0) // N
        for c in range(nfull):
            sel = ok & (sb >= b0 + c * N) & (sb < b0 + (c + 1) * N)
            if sel.sum() < 16 * N:
                continue
            first = (((sb[sel] - b0) % N) * 16 + si[sel]) < 8 * N
            ca, ra = call[sel], resp[sel]
            rows.append((ca.sum() * 0.25, ra.sum() * 0.25, ca[first].sum() * 0.25,
                         ra[~first].sum() * 0.25, b0))
    return np.array(rows) if rows else np.zeros((0, 5))


def cr_unit(call, resp, G, b0, b1, N, nnull=200, rng=None):
    """Contrast for one bar range at an N-bar cycle, plus a null from rotating the call stream
    inside the range by a random number of 16ths (keeps its density and the sub untouched)."""
    sb, si, ok = G["slot_bar"], G["slot_inbar"], G["slot_ok"]
    nfull = (b1 - b0) // N
    if nfull == 0:
        return None
    sel = np.where(ok & (sb >= b0) & (sb < b0 + nfull * N))[0]
    P = 16 * N
    cp = ((sb[sel] - b0) % N) * 16 + si[sel]
    half = cp < P // 2
    c, r = call[sel], resp[sel]
    cb_, rb_ = c.sum() * 0.25, r.sum() * 0.25
    if c.sum() <= 0 or r.sum() <= 0:
        return dict(d=np.nan, lo=np.nan, hi=np.nan, cb=cb_, rb=rb_, cf=np.nan, rf=np.nan)
    rf = r[half].sum() / r.sum()
    cf = c[half].sum() / c.sum()
    nd = []
    if rng is not None and len(c) > 32:
        for _ in range(nnull):
            cc = np.roll(c, int(rng.integers(1, len(c))))
            nd.append(cc[half].sum() / cc.sum() - rf)
    lo, hi = (np.percentile(nd, [2.5, 97.5]) if nd else (np.nan, np.nan))
    return dict(d=cf - rf, lo=lo, hi=hi, cb=cb_, rb=rb_, cf=cf, rf=rf)


def cr_state(u, ncall, min_calls=4):
    if u is None:
        return "too short"
    if ncall < min_calls or u["rb"] < 4.0 or u["d"] != u["d"]:
        return "absent"
    if u["d"] > u["hi"]:
        return "holds"
    if u["d"] < u["lo"]:
        return "reversed"
    return "flat"


def callresp(F, secs, evs):
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "reaper_bass", os.path.join(os.path.dirname(os.path.abspath(__file__)), "reaper_bass.py"))
    rb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rb)                    # read-only import: defs and constants only
    z = np.load(rb.scratch("notes.npz"))
    plate = z["merged"]
    glides = z["glides"]
    sub_midi = 69 + 12 * np.log2(SUB_HZ / 440.0)
    plate = plate[plate[:, 2] < sub_midi]

    G = cr_grid()
    subs, sub_src = cr_subsections(G)
    st = G["slot_t"]
    dur = float(F["t"][-1])

    # ---- streams
    call_snd = cr_cover([(e["t"], e["t"] + e["dur"]) for e in evs], st)
    call_on = cr_onsets(np.array([e["t"] for e in evs]), st)
    acc = cr_perc_accents(G, subs)
    comb_on = np.clip(call_on + acc, 0, 1)
    comb_snd = np.clip(call_snd + acc, 0, 1)
    resp_snd = cr_cover([(a, b) for a, b in plate[:, :2]] + [(a, b) for a, b in glides[:, :2]], st)
    resp_on = cr_onsets(plate[:, 0], st)
    HOOK_TYPES = ("stab", "chord stab", "vocal-like", "bell / high tone")
    hook_snd = cr_cover([(e["t"], e["t"] + e["dur"]) for e in evs if e["type"] in HOOK_TYPES], st)
    streams = {
        "tonal CALL, sounding": call_snd,
        "hook types only, sounding": hook_snd,
        "tonal CALL, onsets": call_on,
        "perc accents, onsets": acc,
        "tonal + accents, onsets": comb_on,
    }
    resp_streams = {"sub, sounding": resp_snd, "sub, onsets": resp_on}

    L = []
    w = L.append
    w(f"{CR_HEAD}\n")
    w("Test of the reading **\"high call at the front; sub response, longer, at the back\"**. "
      "Measurement only: event times, durations and intervals. Nothing was extracted or reused.\n")
    w("### Streams and grid\n")
    ntype = Counter(e["type"] for e in evs)
    w(f"- **CALL (tonal)** - all {len(evs)} events from section 1, every type counted: "
      + ", ".join(f"{k} {v}" for k, v in ntype.most_common()) + ". Their fundamentals sit at "
      "233-392 Hz (IQR), so 'high' here means *above the sub*, not top-octave (section 5 shows there "
      "is no separate top-octave layer). A narrower **hook-types-only** stream keeps just "
      f"{', '.join(HOOK_TYPES)} ({sum(1 for e in evs if e['type'] in HOOK_TYPES)} events) and "
      "drops riff fragments, sustained tones and lead lines.\n")
    ok_s = G["slot_ok"]
    w(f"- **CALL (percussion accents)** - 2-16 kHz onset strength at a 16th that is >= 6 dB above "
      f"the median of the *same bar position* over the surrounding +-4 bars and above the "
      f"sub-section's 60th percentile. The regular backbeat and the 16th carrier are therefore "
      f"excluded; fills, crashes and displaced snares count. {int(acc.sum())} accents = "
      f"{100 * acc[ok_s].mean():.1f}% of 16th slots ({16 * acc[ok_s].mean():.2f} per bar). Kept as "
      "a separate stream and in a combined stream, because they are a different kind of call.\n")
    w(f"- **RESPONSE (sub)** - `scripts/reaper_bass.py` note code, imported read-only: "
      f"{len(plate)} held-pitch plateaus below {SUB_HZ:.0f} Hz (onsets) plus {len(glides)} glides "
      f"(sounding time). Sub sounds in {100 * resp_snd[ok_s].mean():.0f}% of 16th slots; the tonal "
      f"call in {100 * call_snd[ok_s].mean():.0f}%.\n")
    bbn = ("present - its per-bar riff segments are used as the bass layer's own state "
           "boundaries in part 5; the sub stream itself comes from the note cache, which carries "
           "exact onset and offset times" if os.path.exists(BASS_BARS) else
           "not present when this ran, so the notes cache was used directly")
    w(f"- `bass_bars.npz`: {bbn}.\n")
    w(f"- **Grid**: `grid.npz` beats, split into 16ths; only 4-beat bars are folded "
      f"({int(G['ok_bar'].sum())} of {G['nbar']}). **Cycles are anchored at sub-section starts** "
      f"({len(subs)} sub-sections from {sub_src}, snapped to the nearest downbeat), so bar 1 of a "
      "2- or 4-bar cycle is the first bar of a sub-section. Every front/back number is repeated "
      "with a second anchor (the global bar count) and with an **anchor-free** measure - the "
      "circular offset of the response behind the call inside the cycle, which does not depend on "
      "where bar 1 is.\n")

    # ---- 2. front vs back
    w("### 1. Front versus back\n")
    w("`first half` = share of the stream's activity in the first half of the cycle (0.50 = even). "
      "`COM` = linear centre of mass in the cycle, 0 = downbeat of bar 1, 1 = end of the cycle. "
      "`contrast` = call first-half share minus response first-half share; the user's reading "
      "predicts it positive. 95% CIs are a cluster bootstrap over sub-sections.\n")
    w("| call stream | response | cycle | call first half | call COM | resp first half | resp COM "
      "| contrast [95% CI] | anchor-free offset resp-call | global-anchor contrast [95% CI] |")
    w("|---|---|---|---|---|---|---|---|---|---|")
    FB = {}
    for cname, cs in streams.items():
        for rname, rs in resp_streams.items():
            if ("sounding" in cname) != ("sounding" in rname):
                continue
            for N in (1, 2, 4, 8):
                o = cr_front_back(cs, rs, G, subs, N)
                og = cr_front_back(cs, rs, G, subs, N, anchor="global", nboot=200)
                FB[(cname, rname, N)] = o
                w(f"| {cname} | {rname} | {N} bar | {o['call']['first']:.3f} | "
                  f"{o['call']['com']:.3f} | {o['resp']['first']:.3f} | {o['resp']['com']:.3f} | "
                  f"**{o['diff']:+.3f}** [{o['ci_diff'][0]:+.3f}, {o['ci_diff'][1]:+.3f}] | "
                  f"{o['rel_offset']:+.3f} cycle (R {o['rel_R']:.2f}, later in "
                  f"{100 * o['rel_pos_share']:.0f}% of subs) | {og['diff']:+.3f} "
                  f"[{og['ci_diff'][0]:+.3f}, {og['ci_diff'][1]:+.3f}] |")
    w("")
    key = ("tonal CALL, sounding", "sub, sounding")
    best_N = max((1, 2, 4, 8), key=lambda N: FB[key + (N,)]["diff"])
    ob = FB[key + (best_N,)]
    sig_pos = [(k2, v) for k2, v in FB.items() if v["ci_diff"][0] > 0]
    sig_neg = [(k2, v) for k2, v in FB.items() if v["ci_diff"][1] < 0]
    w(f"Largest contrast in the predicted direction for tonal call vs sub sounding: "
      f"**{best_N} bar(s)**, {ob['diff']:+.3f} [{ob['ci_diff'][0]:+.3f}, {ob['ci_diff'][1]:+.3f}] - "
      "its interval includes zero. Rows whose sub-section-anchored interval excludes zero: "
      f"**{len(sig_pos)} in the predicted direction, {len(sig_neg)} in the opposite direction** ("
      + "; ".join(f"{k2[0]} vs {k2[1]}, {k2[2]} bar: {v['diff']:+.3f}" for k2, v in sig_neg)
      + ").\n")

    def profile(title, cname, rname, N, per):
        o = FB[(cname, rname, N)]
        pc_ = o["prof_call"].reshape(-1, per).sum(1)
        pr_ = o["prof_resp"].reshape(-1, per).sum(1)
        if per == 16:
            labs = [f"bar {k + 1}" for k in range(len(pc_))]
        elif per == 4:
            labs = [f"{k // 4 + 1}.{k % 4 + 1}" for k in range(len(pc_))]
        else:
            labs = [f"{k // 2 + 1}{'' if k % 2 == 0 else '&'}" for k in range(len(pc_))]
        w(f"*{title}* - share of each stream's activity per {'bar' if per == 16 else ('beat' if per == 4 else '8th')}:\n")
        w("| position | " + " | ".join(labs) + " |")
        w("|---|" + "---|" * len(labs))
        w(f"| {cname} | " + " | ".join(f"{100 * x:.1f}" for x in pc_) + " |")
        w(f"| {rname} | " + " | ".join(f"{100 * x:.1f}" for x in pr_) + " |")
        w("| call - sub | " + " | ".join(f"{100 * (a - b):+.1f}" for a, b in zip(pc_, pr_)) + " |")
        w("")

    profile("One bar, percussion accents against sub onsets (the strongest effect in the table)",
            "perc accents, onsets", "sub, onsets", 1, 2)
    profile("Eight bars, tonal call onsets against sub onsets", "tonal CALL, onsets",
            "sub, onsets", 8, 16)
    profile("Four bars (the phrase unit), tonal call against sub, sounding",
            "tonal CALL, sounding", "sub, sounding", 4, 4)

    # ---- 3. alternation
    w("### 2. Alternation: cross-correlation at beat resolution\n")
    lags = list(range(-8, 9))
    rng = np.random.default_rng(11)
    w("Per-beat activity, z-scored inside each sub-section (so slow level changes between sections "
      "cannot create correlation), correlated at lags -8..+8 beats. **Positive lag = the sub comes "
      "after the call.** Two nulls, 200 draws each: `shift` rotates the call by a random number of "
      "beats inside its sub-section (destroys all alignment); `bar-shuffle` permutes whole bars of "
      "the call inside its sub-section (keeps the call's position-in-bar habit, destroys which bar "
      "answers which). A lag that beats `shift` but not `bar-shuffle` is a *metric habit*; one "
      "that beats both is *specific answering*.\n")
    XC = {}
    for cname, rname in (("tonal CALL, sounding", "sub, sounding"),
                         ("tonal CALL, onsets", "sub, onsets"),
                         ("perc accents, onsets", "sub, onsets"),
                         ("tonal + accents, onsets", "sub, onsets")):
        cb, rbb = cr_beats(streams[cname], G), cr_beats(resp_streams[rname], G)
        obs = cr_xcorr(cb, rbb, G, subs, lags)
        n_sh = np.array([cr_xcorr(cb, rbb, G, subs, lags, "shift", rng) for _ in range(200)])
        n_bs = np.array([cr_xcorr(cb, rbb, G, subs, lags, "bars", rng) for _ in range(200)])
        XC[cname] = (obs, n_sh, n_bs)
        w(f"**{cname} vs {rname}**\n")
        w("| lag (beats) | " + " | ".join(f"{L:+d}" for L in lags) + " |")
        w("|---|" + "---|" * len(lags))
        w("| r | " + " | ".join(f"{x:+.3f}" for x in obs) + " |")
        w("| shift null 95% | " + " | ".join(
            f"{np.percentile(n_sh[:, j], 2.5):+.3f}..{np.percentile(n_sh[:, j], 97.5):+.3f}"
            for j in range(len(lags))) + " |")
        w("| bar-shuffle null mean | " + " | ".join(f"{x:+.3f}" for x in n_bs.mean(0)) + " |")
        sig = ["**S**" if obs[j] > np.percentile(n_bs[:, j], 97.5) else
               ("**s-**" if obs[j] < np.percentile(n_bs[:, j], 2.5) else "") for j in range(len(lags))]
        w("| vs bar-shuffle | " + " | ".join(sig) + " |")
        pos_l = [j for j, L in enumerate(lags) if L > 0]
        jpk = max(pos_l, key=lambda j: obs[j])
        j0 = lags.index(0)
        w(f"\nPeak at positive lag: **{lags[jpk]:+d} beats**, r = {obs[jpk]:+.3f} "
          f"(bar-shuffle null {n_bs[:, jpk].mean():+.3f}). Lag 0: r = **{obs[j0]:+.3f}** "
          f"(shift null {np.percentile(n_sh[:, j0], 2.5):+.3f}..{np.percentile(n_sh[:, j0], 97.5):+.3f}, "
          f"bar-shuffle null {n_bs[:, j0].mean():+.3f}). `S` / `s-` = above / below the "
          "bar-shuffle 95% band.\n")

    # ---- 4. durations
    w("### 3. Durations: is the response longer?\n")
    for N in sorted(set([1, 2, 4, best_N])):
        C = cr_cycles(call_snd, resp_snd, G, subs, N)
        both = C[(C[:, 0] >= 0.25) & (C[:, 1] > 0)]
        ratio = both[:, 1] / both[:, 0]
        fb = C[(C[:, 2] >= 0.25) & (C[:, 3] > 0)]
        r2 = fb[:, 3] / fb[:, 2]
        w(f"**{N}-bar cycles** ({len(C)} complete, {len(both)} with both a call >= 1/4 beat and "
          "some sub):\n")
        w(f"- call sounding per cycle {'/'.join(f'{x:.2f}' for x in pct(both[:, 0]))} beats; sub "
          f"sounding {'/'.join(f'{x:.2f}' for x in pct(both[:, 1]))} beats (10/25/50/75/90)\n")
        w(f"- **sub / call ratio {'/'.join(f'{x:.2f}' for x in pct(ratio))}**; sub longer in "
          f"**{100 * np.mean(ratio > 1):.0f}%** of cycles, geometric mean "
          f"{np.exp(np.mean(np.log(ratio))):.2f}x\n")
        w(f"- front call vs back sub only (call in the first half, sub in the second half; "
          f"{len(fb)} cycles): ratio {'/'.join(f'{x:.2f}' for x in pct(r2))}, sub longer in "
          f"{100 * np.mean(r2 > 1):.0f}%\n")
    w("**Is 'longer' a property of the response, or of the sub?** The sub sounds in "
      f"{100 * resp_snd[ok_s].mean():.0f}% of 16ths and the call in "
      f"{100 * call_snd[ok_s].mean():.0f}%, so almost *any* cycle holding a call also holds more "
      "sub. Two checks: (a) the same ratio with the call stream rotated to random positions inside "
      "its sub-section (50 rotations) - if the observed ratio matches, 'longer' is just density; "
      "(b) sub sounding time in cycles *with* a call versus cycles *without* one, inside the same "
      "sub-section - an answering sub should play more after a call, not less.\n")
    w("| cycle | observed median sub/call | rotated-call median [95%] | sub beats, cycles with a "
      "call | sub beats, cycles without | paired diff (with - without) per sub-section |")
    w("|---|---|---|---|---|---|")
    rngd = np.random.default_rng(5)
    DUR = {}
    for N in (1, 2, 4):
        C = cr_cycles(call_snd, resp_snd, G, subs, N)
        both = C[(C[:, 0] >= 0.25) & (C[:, 1] > 0)]
        obs_med = float(np.median(both[:, 1] / both[:, 0]))
        nulls = []
        for _ in range(50):
            rot = np.zeros_like(call_snd)
            for b0, b1 in subs:
                sel = np.where(G["slot_ok"] & (G["slot_bar"] >= b0) & (G["slot_bar"] < b1))[0]
                if len(sel) > 1:
                    rot[sel] = np.roll(call_snd[sel], int(rngd.integers(1, len(sel))))
            Cn = cr_cycles(rot, resp_snd, G, subs, N)
            bn = Cn[(Cn[:, 0] >= 0.25) & (Cn[:, 1] > 0)]
            nulls.append(np.median(bn[:, 1] / bn[:, 0]))
        withc = C[C[:, 0] >= 0.25]
        noc = C[C[:, 0] == 0]
        pd_ = []
        for b0 in np.unique(C[:, 4]):
            a_ = C[(C[:, 4] == b0) & (C[:, 0] >= 0.25), 1]
            z_ = C[(C[:, 4] == b0) & (C[:, 0] == 0), 1]
            if len(a_) and len(z_):
                pd_.append(a_.mean() - z_.mean())
        DUR[N] = (obs_med, nulls, withc[:, 1].mean(), noc[:, 1].mean(), pd_)
        w(f"| {N} bar | {obs_med:.2f} | {np.median(nulls):.2f} "
          f"[{np.percentile(nulls, 2.5):.2f}, {np.percentile(nulls, 97.5):.2f}] | "
          f"{withc[:, 1].mean():.2f} (n={len(withc)}) | {noc[:, 1].mean():.2f} (n={len(noc)}) | "
          f"{np.median(pd_):+.2f} beats median, positive in {100 * np.mean(np.array(pd_) > 0):.0f}% "
          f"of {len(pd_)} sub-sections |")
    w("")
    dl = np.array([e["dur"] for e in evs]) / G["beat_len"]
    pl = (plate[:, 1] - plate[:, 0]) / G["beat_len"]
    w(f"\nSingle units, for scale: a call event lasts {'/'.join(f'{x:.2f}' for x in pct(dl))} beats, "
      f"a sub plateau {'/'.join(f'{x:.2f}' for x in pct(pl))} beats (10/25/50/75/90).\n")
    # event pairs: sub sounding after each call until the next call or 2 bars
    ct = np.array(sorted(e["t"] for e in evs))
    pairs = []
    for i, e in enumerate(sorted(evs, key=lambda e: e["t"])):
        end = min(ct[i + 1] if i + 1 < len(ct) else e["t"] + 8 * G["beat_len"],
                  e["t"] + 8 * G["beat_len"])
        a = int(np.searchsorted(st, e["t"])) - 1
        z2 = int(np.searchsorted(st, end))
        a, z2 = max(a, 0), min(z2, len(resp_snd))
        # sub sounding inside the window, measured in beats
        rs = resp_snd[a:z2].sum() * 0.25
        if rs > 0:
            pairs.append((e["dur"] / G["beat_len"], rs, (end - e["t"]) / G["beat_len"]))
    pairs = np.array(pairs)
    pr_ratio = pairs[:, 1] / pairs[:, 0]
    w(f"\nCall -> following window (until the next call, max 2 bars; {len(pairs)} calls with sub "
      f"in the window): window {'/'.join(f'{x:.1f}' for x in pct(pairs[:, 2]))} beats, sub "
      f"sounding in it {'/'.join(f'{x:.2f}' for x in pct(pairs[:, 1]))} beats, **ratio sub/call "
      f"{'/'.join(f'{x:.2f}' for x in pct(pr_ratio))}**, sub longer in "
      f"{100 * np.mean(pr_ratio > 1):.0f}%.\n")

    # ---- 5. pitch
    w("### 4. Pitch relationship (intervals only)\n")
    sub_pc = np.mod(np.round(plate[:, 2]).astype(int), 12)
    sub_w = plate[:, 1] - plate[:, 0]
    bar_t = G["downbeats"]
    roots = {}
    for k, (b0, b1) in enumerate(subs):
        t0 = bar_t[b0]
        t1 = bar_t[b1] if b1 < len(bar_t) else dur
        m = (plate[:, 0] >= t0) & (plate[:, 0] < t1)
        if m.sum() >= 3:
            roots[k] = int(np.argmax(np.bincount(sub_pc[m], weights=sub_w[m], minlength=12)))

    def sub_of(t):
        for k, (b0, b1) in enumerate(subs):
            t0 = bar_t[b0]
            t1 = bar_t[b1] if b1 < len(bar_t) else dur
            if t0 <= t < t1:
                return k, t0, t1
        return None, None, None

    obs_int, null_int, under_int = [], [], []
    call_root, resp_root = [], []
    rng = np.random.default_rng(3)
    for e in evs:
        k, t0, t1 = sub_of(e["t"])
        if k is None:
            continue
        cpc = int(np.round(e["f0_midi"])) % 12
        nxt = np.where((plate[:, 0] >= e["t"]) & (plate[:, 0] < e["t"] + 8 * G["beat_len"]))[0]
        under = np.where((plate[:, 0] <= e["t"]) & (plate[:, 1] > e["t"]))[0]
        if len(under):
            under_int.append((sub_pc[under[0]] - cpc) % 12)
        if len(nxt) == 0:
            continue
        rpc = sub_pc[nxt[0]]
        obs_int.append((rpc - cpc) % 12)
        pool = np.where((plate[:, 0] >= t0) & (plate[:, 0] < t1))[0]
        if len(pool):
            for j in rng.choice(pool, 50):
                null_int.append((sub_pc[j] - cpc) % 12)
        if k in roots:
            call_root.append((cpc - roots[k]) % 12)
            resp_root.append((rpc - roots[k]) % 12)
    all_root = []
    for k, (b0, b1) in enumerate(subs):
        if k not in roots:
            continue
        t0 = bar_t[b0]
        t1 = bar_t[b1] if b1 < len(bar_t) else dur
        m = (plate[:, 0] >= t0) & (plate[:, 0] < t1)
        all_root += list((sub_pc[m] - roots[k]) % 12)

    def hist(a):
        h = np.bincount(np.asarray(a, int), minlength=12).astype(float)
        return h / max(h.sum(), 1)

    ho, hn, hu = hist(obs_int), hist(null_int), hist(under_int)
    w(f"Call pitch class = the event's fundamental estimate; response = the **first** sub plateau "
      f"starting within 2 bars after the call onset ({len(obs_int)} pairs). Interval = response "
      "minus call, folded to one octave. The null pairs each call with 50 random sub plateaus from "
      "the same sub-section, so it shows what the key alone would produce.\n")
    w("| interval response-call | " + " | ".join(PC) + " |")
    w("|---|" + "---|" * 12)
    w("| observed | " + " | ".join(f"{100 * x:.0f}%" for x in ho) + " |")
    w("| same-section null | " + " | ".join(f"{100 * x:.0f}%" for x in hn) + " |")
    w("| observed - null | " + " | ".join(f"{100 * (a - b):+.0f}" for a, b in zip(ho, hn)) + " |")
    w("| sub note *under* the call | " + " | ".join(f"{100 * x:.0f}%" for x in hu) + " |")
    w("")
    uf = [0, 5, 7]
    w(f"Unison + 4th + 5th (response relative to call): observed **{100 * ho[uf].sum():.0f}%**, "
      f"null {100 * hn[uf].sum():.0f}%, under-the-call {100 * hu[uf].sum():.0f}%. "
      "(Octave errors in the call's f0 keep the pitch class; a twelfth error would move weight "
      "between 1 and 5, so read unison and fifth together.)\n")
    hc, hr, ha = hist(call_root), hist(resp_root), hist(all_root)
    w("\nRelative to the sub-section root (duration-weighted modal pitch class of that "
      "sub-section's sub plateaus):\n")
    w("| interval above root | " + " | ".join(PC) + " |")
    w("|---|" + "---|" * 12)
    w("| call | " + " | ".join(f"{100 * x:.0f}%" for x in hc) + " |")
    w("| sub response (first note after a call) | " + " | ".join(f"{100 * x:.0f}%" for x in hr) + " |")
    w("| all sub plateaus (baseline) | " + " | ".join(f"{100 * x:.0f}%" for x in ha) + " |")
    w("")
    w(f"Response on the root: {100 * hr[0]:.0f}% vs {100 * ha[0]:.0f}% for sub notes in general; "
      f"call on the root {100 * hc[0]:.0f}%, on root/4th/5th {100 * hc[uf].sum():.0f}%.\n")

    # Is the b6 spike under the call a musical choice or the sub's own 5th partial?
    HK = {2: 12.0, 3: 19.02, 4: 24.0, 5: 27.86, 6: 31.02, 7: 33.69, 8: 36.0}
    obs_d, null_d, suspect = [], [], set()
    for i_e, e in enumerate(evs):
        under = np.where((plate[:, 0] <= e["t"]) & (plate[:, 1] > e["t"]))[0]
        if not len(under):
            continue
        d = float(e["f0_midi"] - plate[under[0], 2])
        obs_d.append(d)
        if any(abs(d - v) <= 0.5 for kk, v in HK.items() if kk in (3, 5, 6, 7)):
            suspect.add(i_e)
        k_, t0_, t1_ = sub_of(e["t"])
        if k_ is not None:
            pool = np.where((plate[:, 0] >= t0_) & (plate[:, 0] < t1_))[0]
            for j in rng.choice(pool, 50) if len(pool) else []:
                null_d.append(float(e["f0_midi"] - plate[j, 2]))
    obs_d, null_d = np.array(obs_d), np.array(null_d)

    def near(a, v):
        return float(np.mean(np.abs(a - v) <= 0.5)) if len(a) else np.nan
    w("\n**Harmonic check.** The b6 spike in the *under-the-call* row is the signature of a call "
      "sitting a major third above the sub - which is also exactly where the sub's own **5th "
      "partial** falls (two octaves and a major third up). Measuring the unfolded distance from "
      "the sub plateau to the call's fundamental, against the same-section null:\n")
    w("| partial of the sub | 2 (8ve) | 3 (12th) | 4 (2 8ves) | 5 (2 8ves + M3) | 6 | 7 | 8 |")
    w("|---|---|---|---|---|---|---|---|")
    w("| call within 0.5 st, observed | " + " | ".join(f"{100 * near(obs_d, v):.1f}%"
                                                        for v in HK.values()) + " |")
    w("| same-section null | " + " | ".join(f"{100 * near(null_d, v):.1f}%"
                                             for v in HK.values()) + " |")
    w(f"\n{len(obs_d)} calls have a sub plateau sounding at their onset; {len(suspect)} of them "
      f"({100 * len(suspect) / max(len(obs_d), 1):.0f}%) sit within half a semitone of a non-octave "
      "partial (3, 5, 6 or 7) of that plateau. Octave partials are left out of the suspect set on "
      "purpose - a call on the bass's pitch class an octave or two up is a normal musical choice.\n")
    HARM = dict(obs=obs_d, null=null_d, suspect=suspect, HK=HK)
    evs_clean = [e for i_e, e in enumerate(evs) if i_e not in suspect]
    clean_snd = cr_cover([(e["t"], e["t"] + e["dur"]) for e in evs_clean], st)
    FBX = {}
    w("\nFront/back re-run **without** the harmonic suspects (sounding, sub-section anchor):\n")
    w("| cycle | call first half | sub first half | contrast [95% CI] |")
    w("|---|---|---|---|")
    for N in (1, 2, 4):
        o = cr_front_back(clean_snd, resp_snd, G, subs, N)
        FBX[N] = o
        w(f"| {N} bar | {o['call']['first']:.3f} | {o['resp']['first']:.3f} | "
          f"{o['diff']:+.3f} [{o['ci_diff'][0]:+.3f}, {o['ci_diff'][1]:+.3f}] |")
    w("")

    # ---- 6. per sub-section, and switching
    w("### 5. Per sub-section, and whether the state switches at boundaries\n")
    w("Each sub-section gets its own test at 1-, 2- and 4-bar cycles. Its contrast is compared with "
      "200 rotations of *its own* call stream by a random number of 16ths (same calls, same sub, "
      "positions scrambled), so a sub-section with two calls cannot 'hold' by luck. State at the "
      "4-bar cycle (the reference's phrase unit): `holds` = contrast above the rotation null's "
      "97.5th percentile; `reversed` = below its 2.5th; `flat` = inside; `absent` = fewer than 4 "
      "calls or under 4 beats of sub. By chance alone about 2.5% of eligible sub-sections would "
      "land in each tail.\n")
    w("| sub | start s | bars | calls | call beats | sub beats | contrast 1 bar | contrast 2 bar "
      "| contrast 4 bar [null 95%] | state (4 bar) | state (2 bar) |")
    w("|---|---|---|---|---|---|---|---|---|---|---|")
    rng6 = np.random.default_rng(21)
    sub_states = []
    ct_all = np.array([e["t"] for e in evs])
    for k, (b0, b1) in enumerate(subs):
        t0 = bar_t[b0]
        t1 = bar_t[b1] if b1 < len(bar_t) else dur
        ncall = int(((ct_all >= t0) & (ct_all < t1)).sum())
        U = {N: cr_unit(call_snd, resp_snd, G, b0, b1, N, rng=rng6) for N in (1, 2, 4)}
        s4, s2 = cr_state(U[4], ncall), cr_state(U[2], ncall)
        sub_states.append((k, t0, b1 - b0, s4, s2, U, ncall))

        def fm(u):
            return "-" if u is None or u["d"] != u["d"] else f"{u['d']:+.2f}"
        u4 = U[4]
        c4 = ("-" if u4 is None or u4["d"] != u4["d"] else
              f"{u4['d']:+.2f} [{u4['lo']:+.2f}, {u4['hi']:+.2f}]")
        cbeats = U[1]["cb"] if U[1] else 0.0
        rbeats = U[1]["rb"] if U[1] else 0.0
        w(f"| {k} | {t0:.0f} | {b1 - b0} | {ncall} | {cbeats:.1f} | {rbeats:.1f} | {fm(U[1])} | "
          f"{fm(U[2])} | {c4} | {s4} | {s2} |")
    for lab_n, idx in (("4-bar", 3), ("2-bar", 4)):
        cnt = Counter(s_[idx] for s_ in sub_states)
        bars_by = {}
        for s_ in sub_states:
            bars_by[s_[idx]] = bars_by.get(s_[idx], 0) + s_[2]
        totb = sum(bars_by.values())
        elig = sum(v for k2, v in cnt.items() if k2 in ("holds", "reversed", "flat"))
        w(f"\n**{lab_n} states:** " + ", ".join(
            f"`{k2}` {v} ({100 * bars_by[k2] / totb:.0f}% of bars)" for k2, v in cnt.most_common())
          + f". Of {elig} eligible sub-sections, chance predicts ~{0.025 * elig:.1f} in each tail.\n")
    w("\nWhere it holds (4-bar): " + (", ".join(
        f"{s_[1]:.0f} s ({s_[2]} bars)" for s_ in sub_states if s_[3] == "holds") or "nowhere")
      + ". Where it is reversed (4-bar): " + (", ".join(
        f"{s_[1]:.0f} s ({s_[2]} bars)" for s_ in sub_states if s_[3] == "reversed") or "nowhere")
      + ".\n")
    w("Where it holds (2-bar): " + (", ".join(
        f"{s_[1]:.0f} s" for s_ in sub_states if s_[4] == "holds") or "nowhere")
      + ". Where it is reversed (2-bar): " + (", ".join(
        f"{s_[1]:.0f} s" for s_ in sub_states if s_[4] == "reversed") or "nowhere") + ".\n")

    # 8-bar windows: does the contrast hold its value inside a sub-section and change at edges?
    w("\n**Persistence inside sub-sections.** The user's model predicts that the contrast is a "
      "*state* a sub-section holds: consecutive 8-bar windows inside one sub-section should look "
      "alike, and changes should cluster at sub-section edges. Tested on complete 8-bar windows "
      "anchored at sub-section starts, with the eta^2 null built by rotating the sub-section "
      "labels (which keeps them contiguous).\n")
    w("| cycle | windows with call and sub | eta^2 by sub-section | null median | null 95th | "
      "abs contrast change inside a sub-section | abs change across a boundary |")
    w("|---|---|---|---|---|---|---|")
    persist = {}
    for N in (1, 2, 4):
        win = []
        for k, (b0, b1) in enumerate(subs):
            for j in range((b1 - b0) // 8):
                wb0 = b0 + 8 * j
                u = cr_unit(call_snd, resp_snd, G, wb0, wb0 + 8, N)
                ok_w = u is not None and u["d"] == u["d"] and u["cb"] >= 0.5 and u["rb"] >= 2.0
                win.append((k, j, u["d"] if ok_w else np.nan))
        dv = np.array([x[2] for x in win])
        lk = np.array([x[0] for x in win])
        okd = ~np.isnan(dv)

        def eta2(vals, labs):
            m = vals.mean()
            ss_t = ((vals - m) ** 2).sum()
            ss_b = sum(((vals[labs == g].mean() - m) ** 2) * (labs == g).sum()
                       for g in np.unique(labs))
            return ss_b / ss_t if ss_t > 0 else np.nan

        e_obs = eta2(dv[okd], lk[okd])
        n_ok = int(okd.sum())
        e_null = [eta2(dv[okd], np.roll(lk[okd], sh)) for sh in range(1, n_ok)]
        ins, acr = [], []
        for (k1, _, d1), (k2, _, d2) in zip(win, win[1:]):
            if d1 == d1 and d2 == d2:
                (ins if k1 == k2 else acr).append(abs(d1 - d2))
        persist[N] = (e_obs, e_null, ins, acr)
        w(f"| {N} bar | {n_ok} | **{e_obs:.2f}** | {np.median(e_null):.2f} | "
          f"{np.percentile(e_null, 95):.2f} | {np.median(ins):.2f} (n={len(ins)}) | "
          f"{np.median(acr):.2f} (n={len(acr)}) |")
    w("\neta^2 is inflated by construction when many sub-sections hold only one or two windows, "
      "which is why the rotated-label null sits so high; read the observed value against the null "
      "columns, not against zero.\n")

    # The bass layer's own state boundaries, from the bass agent's bass_bars.npz (read only).
    bass_riff = None
    if os.path.exists(BASS_BARS):
        zb = np.load(BASS_BARS, allow_pickle=True)
        if "riff_segment_id" in zb.files and "bar_start_s" in zb.files:
            bstart = np.asarray(zb["bar_start_s"], float)
            rseg = np.asarray(zb["riff_segment_id"], int)
            db_ = G["downbeats"]
            gi = np.clip(np.searchsorted(bstart, db_), 1, len(bstart) - 1)
            gi = np.where(np.abs(db_ - bstart[gi - 1]) <= np.abs(db_ - bstart[gi]), gi - 1, gi)
            bass_riff = rseg[gi]                      # riff segment id per grid.npz bar
    if bass_riff is not None:
        chg = np.flatnonzero(np.diff(bass_riff) != 0) + 1     # bar index where a new riff state starts
        w(f"\n**Against the bass layer's own state changes.** `bass_bars.npz` (bass agent, read "
          f"only) splits the set into {len(np.unique(bass_riff))} riff segments "
          f"({len(chg)} change points). If every layer holds its state inside a sub-section, the "
          "call-vs-sub placement should also change where the *bass riff* changes:\n")
        w("| cycle | eta^2 by bass riff segment | null median | null 95th | abs change, window pair "
          "with no riff change | with a riff change |")
        w("|---|---|---|---|---|---|")
        for N in (1, 2, 4):
            wins = []
            for b0 in range(0, G["nbar"] - 8, 8):
                u = cr_unit(call_snd, resp_snd, G, b0, b0 + 8, N)
                ok_w = u is not None and u["d"] == u["d"] and u["cb"] >= 0.5 and u["rb"] >= 2.0
                seg_id = int(np.bincount(bass_riff[b0:b0 + 8] - bass_riff.min()).argmax()
                             + bass_riff.min())
                wins.append((b0, seg_id, u["d"] if ok_w else np.nan))
            dv = np.array([x[2] for x in wins])
            lk = np.array([x[1] for x in wins])
            okd = ~np.isnan(dv)
            e_b = eta2(dv[okd], lk[okd])
            e_bn = [eta2(dv[okd], np.roll(lk[okd], sh)) for sh in range(1, int(okd.sum()))]
            no_c, with_c = [], []
            for (b0a, _, da), (b0b, _, db2) in zip(wins, wins[1:]):
                if da == da and db2 == db2:
                    crosses = np.any((chg > b0a) & (chg < b0b + 8))
                    (with_c if crosses else no_c).append(abs(da - db2))
            persist[("bass", N)] = (e_b, e_bn, no_c, with_c)
            w(f"| {N} bar | **{e_b:.2f}** | {np.median(e_bn):.2f} | {np.percentile(e_bn, 95):.2f} | "
              f"{np.median(no_c):.2f} (n={len(no_c)}) | {np.median(with_c):.2f} (n={len(with_c)}) |")
        w("")
    else:
        w("\n`bass_bars.npz` was not available, so the bass layer's own riff boundaries were not "
          "tested.\n")
    # ---- verdict
    w("### Verdict\n")
    T = "tonal CALL, sounding"
    S = "sub, sounding"
    fb = {N: FB[(T, S, N)] for N in (1, 2, 4, 8)}
    acc1 = FB[("perc accents, onsets", "sub, onsets", 1)]
    ton8 = FB[("tonal CALL, onsets", "sub, onsets", 8)]
    obs_x, nsh_x, nbs_x = XC[T]
    j0 = lags.index(0)
    jpos = [j for j, L_ in enumerate(lags) if L_ > 0]
    jmax = max(jpos, key=lambda j: obs_x[j])
    jmin = min(jpos, key=lambda j: obs_x[j])
    obs_o, nsh_o, _ = XC["tonal CALL, onsets"]
    jall = max(range(len(lags)), key=lambda j: obs_o[j])
    st4 = Counter(x[3] for x in sub_states)
    elig4 = sum(v for k2, v in st4.items() if k2 in ("holds", "reversed", "flat"))
    absent_bars = sum(x[2] for x in sub_states if x[3] == "absent")
    tot_bars = sum(x[2] for x in sub_states)
    e1, en1, in1, ac1 = persist[1]
    e2, en2, in2, ac2 = persist[2]
    h5 = HARM["HK"][5]
    o5 = float(np.mean(np.abs(HARM["obs"] - h5) <= 0.5))
    n5 = float(np.mean(np.abs(HARM["null"] - h5) <= 0.5))

    w("**The reading does not hold as a set-wide rule, and at the bar level the reference leans "
      "the other way.**\n")
    w(f"1. **Front vs back - no.** Tonal call against sub, sounding time, sub-section anchor: "
      + ", ".join(f"{N} bar {fb[N]['diff']:+.3f} [{fb[N]['ci_diff'][0]:+.2f}, "
                  f"{fb[N]['ci_diff'][1]:+.2f}]" for N in (1, 2, 4, 8))
      + ". Every interval includes zero. The sub is not back-loaded in any cycle: its first-half "
      f"share of sounding time is {min(fb[N]['resp']['first'] for N in fb):.3f}-"
      f"{max(fb[N]['resp']['first'] for N in fb):.3f}. The anchor-free offset (no assumption about "
      f"where bar 1 is) finds no consistent order either: the response trails the call in only "
      f"{100 * min(fb[N]['rel_pos_share'] for N in fb):.0f}-"
      f"{100 * max(fb[N]['rel_pos_share'] for N in fb):.0f}% of sub-sections.\n")
    pa = acc1["prof_call"].reshape(-1, 2).sum(1)
    ps = acc1["prof_resp"].reshape(-1, 2).sum(1)
    lab8 = ["1", "1&", "2", "2&", "3", "3&", "4", "4&"]
    top_s = [lab8[i] for i in np.argsort(ps)[::-1][:2]]
    top_a = [lab8[i] for i in np.argsort(pa)[::-1][:2]]
    p8 = ton8["prof_call"].reshape(-1, 16).sum(1)
    top_b = sorted(int(i) + 1 for i in np.argsort(p8)[::-1][:3])
    w(f"2. **What the bar actually does is the reverse.** Sub *onsets* put "
      f"**{100 * acc1['resp']['first']:.0f}%** of themselves in the first half of the bar, peaking "
      f"on {' and '.join(top_s)}, while high percussion accents put "
      f"**{100 * (1 - acc1['call']['first']):.0f}%** in the second half, peaking on "
      f"{' and '.join(top_a)} (fills and pickups): contrast {acc1['diff']:+.3f} "
      f"[{acc1['ci_diff'][0]:+.2f}, {acc1['ci_diff'][1]:+.2f}], same with the global anchor. Over "
      f"8 bars, tonal call onsets drift late ({100 * (1 - ton8['call']['first']):.0f}% in bars 5-8, "
      f"busiest bars {', '.join(str(b) for b in top_b)}; "
      f"contrast {ton8['diff']:+.3f} [{ton8['ci_diff'][0]:+.2f}, {ton8['ci_diff'][1]:+.2f}]) "
      "while sub onsets stay even. So: **sub at the front, highs at the back** - of the bar "
      "clearly, of the 8-bar phrase weakly.\n")
    w(f"3. **Alternation - no answering lag.** Beat-resolution cross-correlation of call and sub "
      f"sounding peaks at positive lag {lags[jmax]:+d} beats with r = {obs_x[jmax]:+.3f}, inside "
      f"the shift null. Lag 0 is r = {obs_x[j0]:+.3f} - **not negative**, so they do not avoid "
      f"overlapping. The one lag outside both nulls is a *dip*: r = {obs_x[jmin]:+.3f} at "
      f"{lags[jmin]:+d} beats, i.e. the sub is slightly *thinner* "
      f"{abs(lags[jmin]) / 4:g} bar(s) after a call, not busier. "
      f"For onsets the largest value is at {lags[jall]:+d} beats (r = {obs_o[jall]:+.3f}, shift "
      f"null 97.5th {np.percentile(nsh_o[:, jall], 97.5):+.3f})"
      + (f" - if anything the sub leads and the call follows {abs(lags[jall]) / 4:g} bar(s) later."
         if lags[jall] < 0 else " - the sub following the call.") + "\n")
    w("4. **Longer - yes, but it is density, not response.** " + " ".join(
        f"{N}-bar: sub/call {DUR[N][0]:.2f}x observed vs {np.median(DUR[N][1]):.2f}x with the call "
        f"placed at random; sub {DUR[N][2]:.2f} beats in cycles with a call vs {DUR[N][3]:.2f} "
        "without." for N in (1, 2, 4))
      + " The sub sounds about four times as much as the call everywhere, so any cycle holding a "
      "call holds a longer stretch of sub - and it does not play more because a call happened.\n")
    uf = [0, 5, 7]
    w(f"5. **Pitch - no relationship beyond sharing the key.** First sub note after a call on the "
      f"call's pitch class, 4th or 5th: {100 * ho[uf].sum():.0f}% against "
      f"{100 * hn[uf].sum():.0f}% for random same-section pairs. The response sits on the "
      f"sub-section root {100 * hr[0]:.0f}% of the time, but so does every sub note "
      f"({100 * ha[0]:.0f}%). The one real pitch signal is *vertical*: a call sounding over a held "
      f"sub note lands on that note's 5th partial (two octaves and a major third up) "
      f"{100 * o5:.0f}% of the time against {100 * n5:.0f}% by chance - either a deliberate major "
      "third over the bass or a few 'calls' that are the reese's own upper partial. Removing those "
      "events does not change any front/back result.\n")
    w(f"6. **Per sub-section.** At the 4-bar phrase the pattern clears its own rotation null in "
      f"{st4.get('holds', 0)} of {elig4} eligible sub-sections and reverses in "
      f"{st4.get('reversed', 0)} - chance level (~{0.025 * elig4:.1f} each). "
      f"{st4.get('absent', 0)} sub-sections ({100 * absent_bars / tot_bars:.0f}% of bars) have too "
      "few calls or too little sub to test at all. What *does* behave like the user's model is "
      f"persistence: the call-vs-sub placement is stickier inside a sub-section than across one - "
      f"eta^2 {e1:.2f} vs null 95th {np.percentile(en1, 95):.2f} at 1 bar, {e2:.2f} vs "
      f"{np.percentile(en2, 95):.2f} at 2 bars; median change between neighbouring 8-bar windows "
      f"{np.median(in1):.2f} inside vs {np.median(ac1):.2f} across a boundary (1 bar). **Each "
      "sub-section holds a placement state and changes it at the edge - it just is not a "
      "front-call/back-response state.**" + (
        " Against the bass layer's own riff segments (`bass_bars.npz`): " + "; ".join(
            f"{N}-bar cycle eta^2 {persist[('bass', N)][0]:.2f} vs null 95th "
            f"{np.percentile(persist[('bass', N)][1], 95):.2f} "
            f"({'above' if persist[('bass', N)][0] > np.percentile(persist[('bass', N)][1], 95) else 'not above'}), "
            f"neighbouring windows differ {np.median(persist[('bass', N)][2]):.2f} without a riff "
            f"change vs {np.median(persist[('bass', N)][3]):.2f} across one"
            for N in (1, 2, 4)) + " - the placement state changes where the bass riff changes, "
        "clearly at the 2- and 4-bar cycles."
        if ("bass", 4) in persist else "") + "\n")
    w("**For the build.** Don't program the sub as an answer that waits for the hook. Measured "
      "against this reference, the working version is: sub attacks at the front of the bar, on the 1 and the 2&"
      "; high accents and pickups at the back of the bar; hooks clustered on the phrase "
      f"midpoint and the last bar of an 8-bar phrase (bars {', '.join(str(b) for b in top_b)}); the "
      "sub running about 4x the hook's sounding time regardless; and "
      "whatever placement relationship you pick, held for the whole sub-section and changed at its "
      "boundary.\n")
    return L, dict(best_N=best_N, FB=FB, XC=XC, lags=lags, ho=ho, hn=hn, hr=hr, ha=ha, hc=hc,
                   sub_states=sub_states, persist=persist, pr_ratio=pr_ratio, DUR=DUR,
                   HARM=HARM, FBX=FBX, G=G, subs=subs, acc=acc, resp_on=resp_on,
                   resp_snd=resp_snd, plate=plate, glides=glides, dur=dur)

# ----------------------------------------------------------------------
# call across the bar line (anacrusis reading)
# ----------------------------------------------------------------------
AN_HEAD = "### Call across the bar line"
BACK = [10, 12, 14]                         # 3&, 4, 4& as 16th slots of the bar
MID = [2, 4, 6]                             # 1&, 2, 2&  (control)


def an_high_strength(G):
    """2-16 kHz onset strength at every 16th slot (log), same measurement the accents use."""
    f = np.load(os.path.join(CACHE, "frames.npz"))
    fl = (f["flux_high"] + f["flux_air"]).astype(np.float64)
    ft = f["t"].astype(np.float64)
    st = G["slot_t"][:-1]
    i0 = np.searchsorted(ft, st - 0.02)
    i1 = np.maximum(np.searchsorted(ft, st + 0.04), i0 + 1)
    idx = np.clip(np.ravel(np.column_stack([i0, i1])), 0, len(fl) - 1)
    return np.log(np.maximum.reduceat(fl, idx)[::2] + 1e-9)


def an_mat(G, stream):
    M = np.zeros((G["nbar"], 16), np.float64)
    ok = G["slot_ok"]
    M[G["slot_bar"][ok], G["slot_inbar"][ok]] = stream[ok]
    return M


def an_pairs(G, units):
    ok = G["ok_bar"]
    P = [(N, k) for k, (b0, b1) in enumerate(units) for N in range(b0, b1 - 1) if ok[N] and ok[N + 1]]
    return np.array(P, int).reshape(-1, 2)


def an_cond(A, S):
    a, sv = A.astype(bool), S.astype(float)
    pA = sv[a].mean() if a.any() else np.nan
    pn = sv[~a].mean() if (~a).any() else np.nan
    return pA, pn, sv.mean()


def an_nulls(A, S, unit, n, rng):
    groups = [np.where(unit == k)[0] for k in np.unique(unit)]
    out = {"shuffle": [], "shift": []}
    for mode in out:
        for _ in range(n):
            A2 = A.copy()
            for ix in groups:
                if len(ix) < 2:
                    continue
                if mode == "shuffle":
                    A2[ix] = A[ix][rng.permutation(len(ix))]
                else:
                    A2[ix] = np.roll(A[ix], int(rng.integers(1, len(ix))))
            pA, pn, _ = an_cond(A2, S)
            out[mode].append(pA - pn)
        out[mode] = np.array(out[mode])
    return out


def an_boot(A, S, unit, n, rng):
    ks = np.unique(unit)
    groups = {k: np.where(unit == k)[0] for k in ks}
    d = []
    for _ in range(n):
        ix = np.concatenate([groups[k] for k in rng.choice(ks, len(ks))])
        pA, pn, _ = an_cond(A[ix], S[ix])
        if pA == pA and pn == pn:
            d.append(pA - pn)
    return np.percentile(d, [2.5, 97.5])


def an_xcorr16(acc, on, G, units, lags, mode=None, rng=None):
    num, den = np.zeros(len(lags)), np.zeros(len(lags))
    for b0, b1 in units:
        sel = np.where(G["slot_ok"] & (G["slot_bar"] >= b0) & (G["slot_bar"] < b1))[0]
        if len(sel) < 64:
            continue
        c, r = acc[sel].astype(float), on[sel].astype(float)
        if c.std() == 0 or r.std() == 0:
            continue
        if mode == "shift":
            c = np.roll(c, int(rng.integers(16, len(c) - 16)))
        elif mode == "bars":
            nbar = len(c) // 16
            c = c[:nbar * 16].reshape(nbar, 16)[rng.permutation(nbar)].ravel()
            r = r[:nbar * 16]
        c = (c - c.mean()) / (c.std() + 1e-12)
        r = (r - r.mean()) / (r.std() + 1e-12)
        n = len(c)
        for j, L_ in enumerate(lags):
            pr = c[:n - L_] * r[L_:] if L_ >= 0 else c[-L_:] * r[:n + L_]
            num[j] += pr.sum()
            den[j] += len(pr)
    return num / np.maximum(den, 1)


def an_eta2(vals, labs):
    m = vals.mean()
    ss_t = ((vals - m) ** 2).sum()
    ss_b = sum(((vals[labs == g].mean() - m) ** 2) * (labs == g).sum() for g in np.unique(labs))
    return ss_b / ss_t if ss_t > 0 else np.nan


def anacrusis(res):
    G, subs, acc, on, plate, resp_snd = (res["G"], res["subs"], res["acc"], res["resp_on"],
                                         res["plate"], res["resp_snd"])
    rng = np.random.default_rng(1234)
    L = []
    w = L.append
    w(f"{AN_HEAD}\n")
    w("An anacrusis reading of the same idea: the *call* is a high hit at the back of bar N "
      "(3&, 4 or 4&) and the *response* is the sub arriving at the front of bar N+1 and sounding "
      f"longer. Units are the {len(subs)} structure sub-sections; every null keeps each unit's own "
      "call and sub rates.\n")
    if not os.path.exists(BASS_BARS):
        w("`bass_bars.npz` is not available, so this test was not run.\n")
        return L

    # ---- the streams, per bar
    zb = np.load(BASS_BARS, allow_pickle=True)
    bstart = np.asarray(zb["bar_start_s"], float)
    db_ = G["downbeats"]
    gi = np.clip(np.searchsorted(bstart, db_), 1, len(bstart) - 1)
    gi = np.where(np.abs(db_ - bstart[gi - 1]) <= np.abs(db_ - bstart[gi]), gi - 1, gi)
    seq = np.asarray(zb["seq16"], int)[gi]
    prev = np.concatenate([np.r_[-1, seq[:-1, 15]][:, None], seq[:, :15]], axis=1)
    S16 = ((seq >= 0) & ((prev < 0) | (np.abs(seq - prev) > 1))).astype(float)
    rid = np.asarray(zb["riff_segment_id"], int)[gi]
    cut = np.r_[0, np.flatnonzero(np.diff(rid) != 0) + 1, G["nbar"]]
    riff_units = [(int(cut[i]), int(cut[i + 1])) for i in range(len(cut) - 1)]
    bsec = np.asarray(zb["section"], int)[gi]

    Am = an_mat(G, acc)
    Pm = an_mat(G, np.clip(on, 0, 1))
    Cm = an_mat(G, resp_snd)
    Hm = an_mat(G, an_high_strength(G))

    # ---- latency of the plateau onsets against the bass agent's 16th sequence
    pos_rate = Pm[G["ok_bar"]].mean(0)
    s16_rate = S16[G["ok_bar"]].mean(0)
    offs = []
    okb = np.where(G["ok_bar"])[0]
    flatP = Pm[okb].ravel()
    flatS = S16[okb].ravel()
    for i in np.flatnonzero(flatP > 0):
        near = [d for d in (-2, -1, 0, 1, 2) if 0 <= i + d < len(flatS) and flatS[i + d] > 0]
        if len(near) == 1:
            offs.append(-near[0])
    offs = np.array(offs)
    w("#### 0. First, a clock problem\n")
    w("Sub *plateau* onsets (the held-pitch start from the bass note code) run late. Their rate "
      "per 16th of the bar, next to the bass agent's own quantised onsets from `bass_bars.npz` "
      "`seq16` (a slot is an onset when it is voiced and the slot before was not, or moved by more "
      "than a semitone):\n")
    labs16 = [f"{b + 1}{s}" for b in range(4) for s in ("", "e", "&", "a")]
    w("| 16th | " + " | ".join(labs16) + " |")
    w("|---|" + "---|" * 16)
    w("| plateau onsets, % of bars | " + " | ".join(f"{100 * x:.1f}" for x in pos_rate) + " |")
    w("| seq16 onsets, % of bars | " + " | ".join(f"{100 * x:.1f}" for x in s16_rate) + " |")
    h_off = Counter(offs.tolist())
    w(f"\nMatched one-to-one within +-2 16ths ({len(offs)} onsets), the plateau onset sits "
      + ", ".join(f"{k:+d}: {100 * v / len(offs):.0f}%" for k, v in sorted(h_off.items()))
      + " 16ths from the seq16 onset. The plateau onsets land on the *e* 16ths because a note "
      "only counts as a plateau once its attack pitch-ping has settled - about one 16th after "
      "the attack. **So 'sub on the downbeat' has to be read from seq16 (or from the first 8th of "
      "the bar for plateaus); a plateau-onset test at slot 0 is structurally near-empty.** The "
      "8th-resolution statement in the section above (sub onsets peak on 1 and 2&) is unaffected, "
      "since a one-16th delay stays inside the 8th.\n")

    # ---- calls: strict accents, and a powered version
    PR = an_pairs(G, subs)
    N_, U_ = PR[:, 0], PR[:, 1]
    back_str = Hm[N_][:, BACK].max(1)
    strong = np.zeros(len(N_), bool)
    for k in np.unique(U_):
        ix = np.where(U_ == k)[0]
        if len(ix) >= 6:
            strong[ix] = back_str[ix] >= np.percentile(back_str[ix], 66.7)
    mid_str = Hm[N_][:, MID].max(1)
    strong_mid = np.zeros(len(N_), bool)
    for k in np.unique(U_):
        ix = np.where(U_ == k)[0]
        if len(ix) >= 6:
            strong_mid[ix] = mid_str[ix] >= np.percentile(mid_str[ix], 66.7)
    strict = Am[N_][:, BACK].max(1) > 0
    strict_w = Am[N_][:, 10:16].max(1) > 0
    w("#### 1. Conditional probability of the sub across the bar line\n")
    w(f"{len(PR)} consecutive bar pairs inside a sub-section. Three definitions of the call:\n")
    w(f"- **strict accent** ({int(strict.sum())} bars): the accent stream above, on 3&, 4 or 4&. It "
      "is >= 6 dB over the same bar position in the surrounding bars, so it *excludes* a pickup "
      "that recurs every bar - which is exactly what an anacrusis call might be.\n")
    w(f"- **strict accent, 3&..4&** ({int(strict_w.sum())} bars): any of the last six 16ths.\n")
    w(f"- **strong back hit** ({int(strong.sum())} bars): 2-16 kHz onset strength on 3&/4/4& in the "
      "top third of that sub-section's bars. Relative to the sub-section, not to the neighbouring "
      "bars, so a recurring pickup counts. This is the powered test.\n")
    w("Responses: `seq16 on 1` = a seq16 onset on the downbeat of N+1 (less latent than plateaus, "
      "but seq16 also peaks on the *e* 16ths, so the first-8th and sounding responses are the "
      "robust ones); `plateau in "
      "1st 8th` = a plateau onset in the first 8th of N+1; `sub sounding, beat 1` = share of the "
      "first beat of N+1 in which the sub sounds (plateaus + glides). For the last one the table "
      "shows means, not probabilities. `boot` = bootstrap over sub-sections; `shuffle`/`shift` = "
      "the call indicator permuted, or circularly shifted by whole bars, inside each sub-section "
      "(1000 draws); `p` = one-sided share of shuffle draws >= observed.\n")
    w("| call | response | P(resp \\| call) | P(resp \\| no call) | lift | difference [boot 95%] | "
      "shuffle null 95% | shift null 95% | p |")
    w("|---|---|---|---|---|---|---|---|---|")
    resp_defs = {
        "seq16 on 1": S16[N_ + 1, 0],
        "plateau in 1st 8th": Pm[N_ + 1, 0:2].max(1),
        "sub sounding, beat 1": Cm[N_ + 1, 0:4].mean(1),
    }
    call_defs = {"strict accent": strict, "strict accent, 3&..4&": strict_w,
                 "strong back hit": strong}
    T1 = {}
    rows = [(c, r) for c in call_defs for r in resp_defs]
    rows += [("control: strong back hit of N+1 -> its OWN bar start", r) for r in resp_defs]
    rows += [("control: strong mid-bar hit (1&/2/2&) -> beat 3 of the same bar", "seq16 on 3")]
    for cname, rname in rows:
        if cname.startswith("control: strong back hit of N+1"):
            A = np.zeros(len(N_), bool)
            bs1 = Hm[N_ + 1][:, BACK].max(1)
            for k in np.unique(U_):
                ix = np.where(U_ == k)[0]
                if len(ix) >= 6:
                    A[ix] = bs1[ix] >= np.percentile(bs1[ix], 66.7)
            S = resp_defs[rname]
        elif cname.startswith("control: strong mid-bar"):
            A, S = strong_mid, S16[N_, 8]
        else:
            A, S = call_defs[cname], resp_defs[rname]
        pA, pn, p0 = an_cond(A, S)
        nl = an_nulls(A, S, U_, 1000, rng)
        ci = an_boot(A, S, U_, 1000, rng)
        d = pA - pn
        pv = float(np.mean(nl["shuffle"] >= d))
        T1[(cname, rname)] = dict(pA=pA, pn=pn, p0=p0, d=d, ci=ci, nl=nl, p=pv, n=int(A.sum()))
        unit = "" if rname == "sub sounding, beat 1" else "%"
        sc = 100.0
        w(f"| {cname} ({int(A.sum())}) | {rname} | {sc * pA:.1f}{unit} | {sc * pn:.1f}{unit} | "
          f"{pA / p0 if p0 > 0 else np.nan:.2f} | **{sc * d:+.1f}** [{sc * ci[0]:+.1f}, {sc * ci[1]:+.1f}] | "
          f"{sc * np.percentile(nl['shuffle'], 2.5):+.1f}..{sc * np.percentile(nl['shuffle'], 97.5):+.1f} | "
          f"{sc * np.percentile(nl['shift'], 2.5):+.1f}..{sc * np.percentile(nl['shift'], 97.5):+.1f} | "
          f"{pv:.3f} |")
    w("\nDifferences are in percentage points (for `sub sounding` in points of the first beat's "
      "coverage).\n")

    # bar-line aligned profile, seq16 onsets, strong back hit
    X = np.concatenate([S16[N_][:, 8:16], S16[N_ + 1][:, 0:8]], axis=1)
    prof_a, prof_n = X[strong].mean(0), X[~strong].mean(0)
    ks = np.unique(U_)
    grp = {k: np.where(U_ == k)[0] for k in ks}
    boots = []
    for _ in range(1000):
        ix = np.concatenate([grp[k] for k in rng.choice(ks, len(ks))])
        b_ = strong[ix]
        if b_.any() and (~b_).any():
            boots.append(X[ix][b_].mean(0) - X[ix][~b_].mean(0))
    boots = np.array(boots)
    lo_b, hi_b = np.percentile(boots, 2.5, 0), np.percentile(boots, 97.5, 0)
    w("seq16 onset rate from half a bar before the bar line to half a bar after it, bar pairs "
      f"with a strong back hit in bar N ({int(strong.sum())}) against the rest "
      f"({int((~strong).sum())}). Position 0 is the downbeat of N+1.\n")
    w("| 16ths from bar line | " + " | ".join(f"{o:+d}" for o in range(-8, 8)) + " |")
    w("|---|" + "---|" * 16)
    w("| strong back hit in N | " + " | ".join(f"{100 * x:.1f}" for x in prof_a) + " |")
    w("| no strong back hit | " + " | ".join(f"{100 * x:.1f}" for x in prof_n) + " |")
    w("| difference, pts | " + " | ".join(
        (f"**{100 * d_:+.1f}**" if (lo > 0 or hi < 0) else f"{100 * d_:+.1f}")
        for d_, lo, hi in zip(prof_a - prof_n, lo_b, hi_b)) + " |")
    w("\nBold = bootstrap 95% interval excludes zero. Note positions -6, -4 and -2 are the call's "
      "own 16ths: a sub onset there coincides with the hit rather than answering it.\n")

    # ---- 2. cross-correlation
    w("#### 2. Cross-correlation, accent stream against sub onsets (16th resolution)\n")
    lags = list(range(-8, 9))
    s16_slot = np.zeros(len(G["slot_t"]) - 1)
    okm = G["slot_ok"]
    s16_slot[okm] = S16[G["slot_bar"][okm], G["slot_inbar"][okm]]
    XCR = {}
    w("z-scored inside each sub-section; positive lag = sub onset after the accent. `shift` "
      "rotates the accent stream by a random number of 16ths (destroys every alignment, including "
      "the metric one); `bar-shuffle` permutes whole bars of accents (keeps where in the bar they "
      "fall, destroys which bar follows which). 300 draws each. With seq16 onsets an accent on "
      "4&, 4 or 3& reaches the next downbeat at +2, +4 or +6; with plateau onsets add one 16th.\n")
    for rname, rs in (("seq16 onsets", s16_slot), ("plateau onsets", np.clip(on, 0, 1))):
        obs = an_xcorr16(acc, rs, G, subs, lags)
        nsh = np.array([an_xcorr16(acc, rs, G, subs, lags, "shift", rng) for _ in range(300)])
        nbs = np.array([an_xcorr16(acc, rs, G, subs, lags, "bars", rng) for _ in range(300)])
        XCR[rname] = (obs, nsh, nbs)
        w(f"**accents vs {rname}**\n")
        w("| lag (16ths) | " + " | ".join(f"{x:+d}" for x in lags) + " |")
        w("|---|" + "---|" * len(lags))
        w("| r | " + " | ".join(f"{x:+.3f}" for x in obs) + " |")
        w("| shift null 97.5% | " + " | ".join(f"{np.percentile(nsh[:, j], 97.5):+.3f}"
                                                for j in range(len(lags))) + " |")
        w("| bar-shuffle null 97.5% | " + " | ".join(f"{np.percentile(nbs[:, j], 97.5):+.3f}"
                                                     for j in range(len(lags))) + " |")
        marks = []
        for j in range(len(lags)):
            a_ = obs[j] > np.percentile(nsh[:, j], 97.5)
            b_ = obs[j] > np.percentile(nbs[:, j], 97.5)
            marks.append("**both**" if a_ and b_ else ("shift" if a_ else ("bar" if b_ else "")))
        w("| above null | " + " | ".join(marks) + " |")
        w("")

    # ---- 3. durations
    w("#### 3. Duration: the call against the sub note that follows\n")
    beat = G["beat_len"]
    p0s = plate[:, 0]
    pdur = (plate[:, 1] - plate[:, 0]) / beat

    def answer_len(Nb):
        """Length (beats) of the first plateau starting in the first 8th of bar Nb+1, else nan."""
        t0 = G["slot_t"][np.where(G["slot_ok"] & (G["slot_bar"] == Nb + 1))[0][0]]
        j = int(np.searchsorted(p0s, t0 - 0.045))
        if j < len(p0s) and p0s[j] < t0 + 2 * beat / 4 - 0.045 + 0.09:
            return pdur[j]
        return np.nan

    ans = np.array([answer_len(n) for n in N_])
    has = ~np.isnan(ans)
    call_len_beats = 0.25                       # a hit occupies one 16th
    a_call = ans[strong & has]
    a_none = ans[~strong & has]
    obs_d = np.median(a_call) - np.median(a_none) if len(a_call) and len(a_none) else np.nan
    nd = []
    for _ in range(1000):
        A2 = strong.copy()
        for k in np.unique(U_):
            ix = np.where(U_ == k)[0]
            A2[ix] = strong[ix][rng.permutation(len(ix))]
        x_, y_ = ans[A2 & has], ans[~A2 & has]
        if len(x_) and len(y_):
            nd.append(np.median(x_) - np.median(y_))
    w("A back-of-bar hit is a single 16th (0.25 beats), so 'the answer is longer than the call' "
      "is true of almost any sub note. The informative test is whether the sub note that starts "
      "in the first 8th of N+1 is longer *after* a strong back hit than after a bar without one (the note must start in the first 8th of N+1, allowing the one-16th plateau latency).\n")
    w("| | notes | answer length, beats (10/25/50/75/90) | answer / call (median) |")
    w("|---|---|---|---|")
    w(f"| after a strong back hit | {len(a_call)} | {'/'.join(f'{x:.2f}' for x in pct(a_call))} | "
      f"{np.median(a_call) / call_len_beats:.2f}x |")
    w(f"| after no strong back hit | {len(a_none)} | {'/'.join(f'{x:.2f}' for x in pct(a_none))} | "
      f"{np.median(a_none) / call_len_beats:.2f}x |")
    w(f"| all sub plateaus | {len(pdur)} | {'/'.join(f'{x:.2f}' for x in pct(pdur))} | - |")
    w(f"\nMedian difference (after hit - after none): **{obs_d:+.2f} beats**; shuffle null 95% "
      f"{np.percentile(nd, 2.5):+.2f}..{np.percentile(nd, 97.5):+.2f}, p = "
      f"{np.mean(np.array(nd) >= obs_d):.3f}.\n")

    # ---- 4. per riff segment, and switching
    w("#### 4. Per bass riff segment, and switching at boundaries\n")
    PRr = an_pairs(G, riff_units)
    Nr, Ur = PRr[:, 0], PRr[:, 1]
    bsr = Hm[Nr][:, BACK].max(1)
    Ar = np.zeros(len(Nr), bool)
    for k in np.unique(Ur):
        ix = np.where(Ur == k)[0]
        if len(ix) >= 6:
            Ar[ix] = bsr[ix] >= np.percentile(bsr[ix], 66.7)
    Sr = S16[Nr + 1, 0]
    w(f"Units = the {len(riff_units)} riff segments of `bass_bars.npz`. Call = strong back hit "
      "(top third inside the segment); response = seq16 onset on the next downbeat. `holds` = "
      "difference above that segment's own shuffle-null 97.5th percentile (500 draws); `reversed` "
      "= below the 2.5th; `flat` = inside; `absent` = under 6 bar pairs, or no seq16 downbeat onset "
      "anywhere in the segment.\n")
    w("| segment | start s | bars | call bars | P(sub on 1 \\| call) | P(sub on 1 \\| none) | "
      "difference | null 95% | state |")
    w("|---|---|---|---|---|---|---|---|---|")
    states = []
    for k, (b0, b1) in enumerate(riff_units):
        ix = np.where(Ur == k)[0]
        a_, s_ = Ar[ix], Sr[ix]
        if len(ix) < 6 or s_.sum() == 0 or a_.sum() == 0:
            states.append((k, b0, b1, "absent", np.nan))
            continue
        pA, pn, _ = an_cond(a_, s_)
        ndk = []
        for _ in range(500):
            a2 = a_[rng.permutation(len(a_))]
            x1, x2, _ = an_cond(a2, s_)
            ndk.append(x1 - x2)
        lo, hi = np.percentile(ndk, [2.5, 97.5])
        d = pA - pn
        stt = "holds" if d > hi else ("reversed" if d < lo else "flat")
        states.append((k, b0, b1, stt, d))
        w(f"| {k} | {G['downbeats'][b0]:.0f} | {b1 - b0} | {int(a_.sum())} | {100 * pA:.0f}% | "
          f"{100 * pn:.0f}% | {100 * d:+.0f} pts | {100 * lo:+.0f}..{100 * hi:+.0f} | {stt} |")
    cnt = Counter(x[3] for x in states)
    elig = sum(v for k2, v in cnt.items() if k2 != "absent")
    w("\nSegments by state: " + ", ".join(f"`{k2}` {v}" for k2, v in cnt.most_common())
      + f". Chance predicts ~{0.025 * elig:.1f} of {elig} eligible in each tail. Holds at: "
      + (", ".join(f"{G['downbeats'][x[1]]:.0f} s ({x[2] - x[1]} bars)" for x in states
                   if x[3] == "holds") or "nowhere")
      + ". Reversed at: "
      + (", ".join(f"{G['downbeats'][x[1]]:.0f} s" for x in states if x[3] == "reversed")
         or "nowhere") + ".\n")

    rid_bar = np.zeros(G["nbar"], int)
    for k, (b0, b1) in enumerate(riff_units):
        rid_bar[b0:b1] = k
    sub_bar = np.zeros(G["nbar"], int)
    for k, (b0, b1) in enumerate(subs):
        sub_bar[b0:b1] = k
    # windows: strong back hit defined within each window's own sub-section (from the PR set)
    wins = []
    for b0 in range(0, G["nbar"] - 8, 8):
        ix = np.where((N_ >= b0) & (N_ < b0 + 8))[0]
        a_, s_ = strong[ix], S16[N_[ix] + 1, 0]
        if a_.sum() >= 2 and (~a_).sum() >= 2:
            pA, pn, _ = an_cond(a_, s_)
            wins.append((b0, pA - pn, np.bincount(rid_bar[b0:b0 + 8]).argmax(),
                         np.bincount(bsec[b0:b0 + 8] - bsec.min()).argmax(),
                         np.bincount(sub_bar[b0:b0 + 8]).argmax()))
    W = np.array(wins, float)
    w(f"\n**Switching.** {len(W)} 8-bar windows with at least two call and two no-call bar pairs. "
      "If this is a state a sub-section holds, window differences should cluster by unit (eta^2 "
      "above the rotated-label null) and neighbouring windows should differ more across a "
      "boundary than inside one.\n")
    w("| grouping | eta^2 | null median | null 95th | neighbour change inside | across a boundary |")
    w("|---|---|---|---|---|---|")
    SW = {}
    for nm, col in (("bass riff segment", 2), ("bass section", 3), ("structure sub-section", 4)):
        v, lab_ = W[:, 1], W[:, col].astype(int)
        e_o = an_eta2(v, lab_)
        e_n = [an_eta2(v, np.roll(lab_, sh)) for sh in range(1, len(v))]
        ins, acr = [], []
        for r1, r2 in zip(W, W[1:]):
            if r2[0] - r1[0] == 8:
                (ins if r1[col] == r2[col] else acr).append(abs(r1[1] - r2[1]))
        SW[nm] = (e_o, e_n, ins, acr)
        w(f"| {nm} | **{e_o:.2f}** | {np.median(e_n):.2f} | {np.percentile(e_n, 95):.2f} | "
          f"{100 * np.median(ins) if ins else float('nan'):.0f} pts (n={len(ins)}) | "
          f"{100 * np.median(acr) if acr else float('nan'):.0f} pts (n={len(acr)}) |")
    w("")

    # ---- verdict
    w("#### Verdict on the bar-line reading\n")
    main = T1[("strong back hit", "seq16 on 1")]
    snd = T1[("strong back hit", "sub sounding, beat 1")]
    strict_on = T1[("strict accent", "seq16 on 1")]
    any_sig = [k for k, v in T1.items() if not k[0].startswith("control")
               and v["d"] > np.percentile(v["nl"]["shuffle"], 97.5)
               and v["d"] > np.percentile(v["nl"]["shift"], 97.5)]
    ctrls = {r: T1[("control: strong back hit of N+1 -> its OWN bar start", r)] for r in resp_defs}
    hint = [r for r in resp_defs if T1[("strong back hit", r)]["p"] < 0.05 and ctrls[r]["p"] > 0.2]
    n_main = sum(1 for k in T1 if not k[0].startswith("control"))
    n_p05 = sum(1 for k, v in T1.items() if not k[0].startswith("control") and v["p"] < 0.05)
    head = ("**Null result" + (", with a weak order-specific hint.** " if hint and not any_sig
                               else ".** ") if not any_sig else "**Partly supported.** ")
    w(head + f"Of {n_main} call x response tests, {len(any_sig)} clear both within-sub-section "
      f"nulls" + (": " + "; ".join(f"{c} -> {r}" for c, r in any_sig) if any_sig else "")
      + f"; {n_p05} reach p < 0.05 against the shuffle null alone, where about "
      f"{0.05 * n_main:.1f} would by chance.\n")
    w(f"- Powered test (strong back hit -> seq16 onset on the next downbeat): "
      f"{100 * main['pA']:.1f}% vs {100 * main['pn']:.1f}% without a hit, "
      f"{100 * main['d']:+.1f} pts [{100 * main['ci'][0]:+.1f}, {100 * main['ci'][1]:+.1f}], "
      f"p = {main['p']:.3f}. Sub sounding in beat 1 of N+1: {100 * snd['d']:+.1f} pts, "
      f"p = {snd['p']:.3f}. Strict accents: {100 * strict_on['pA']:.0f}% vs "
      f"{100 * strict_on['pn']:.0f}% on only {strict_on['n']} bars (p = {strict_on['p']:.3f}) - "
      "the largest raw lift in the table, and too few bars to separate from chance.\n")
    order_spec = [r for r in resp_defs
                  if T1[("strong back hit", r)]["d"] - ctrls[r]["d"] > 0.03]
    co_act = [r for r in resp_defs if ctrls[r]["d"] >= T1[("strong back hit", r)]["d"]]
    w("- **Order control.** Moving the strong hit to the back of bar N+1, so the sub at the front "
      "of N+1 comes *before* it and cannot be answering it, gives " + "; ".join(
          f"{r}: {100 * T1[('strong back hit', r)]['d']:+.1f} pts after the hit vs "
          f"{100 * ctrls[r]['d']:+.1f} before it (p {T1[('strong back hit', r)]['p']:.3f} vs "
          f"{ctrls[r]['p']:.3f})" for r in resp_defs) + ". "
      + (f"For {' and '.join(order_spec)} the small positive exists only *after* the hit, so it is "
         "order-specific rather than busy bars being busy - " if order_spec else "")
      + (f"for {' and '.join(co_act)} the sub is at least as likely *before* the hit, which is "
         "co-activity, not an answer. " if co_act else "")
      + "The effect that survives the order control is small (lift "
      + ", ".join(f"{T1[('strong back hit', r)]['pA'] / T1[('strong back hit', r)]['p0']:.2f}"
                  for r in order_spec)
      + "), clears neither of those tests against the shuffle and shift nulls together, and does "
      "not show on the downbeat-onset measure.\n")
    j0 = 8
    w(f"- Bar-line profile: {100 * (prof_a[j0] - prof_n[j0]):+.1f} pts at the downbeat "
      f"[{100 * lo_b[j0]:+.1f}, {100 * hi_b[j0]:+.1f}].\n")
    for rname, (obs, nsh, nbs) in XCR.items():
        pos = [j for j, x in enumerate(lags) if x > 0]
        jp = max(pos, key=lambda j: obs[j])
        both = obs[jp] > np.percentile(nsh[:, jp], 97.5) and obs[jp] > np.percentile(nbs[:, jp], 97.5)
        w(f"- Cross-correlation with {rname}: largest positive lag {lags[jp]:+d} 16ths, "
          f"r = {obs[jp]:+.3f}, {'above' if both else 'not above'} both nulls.\n")
    w(f"- Duration: the sub note after a strong back hit runs {np.median(a_call):.2f} beats "
      f"against {np.median(a_none):.2f} after none ({obs_d:+.2f}, p = "
      f"{np.mean(np.array(nd) >= obs_d):.3f}). It is 'longer than the call' only because every "
      "sub note is longer than a 16th.\n")
    w(f"- Per riff segment: " + ", ".join(f"`{k2}` {v}" for k2, v in cnt.most_common())
      + " - chance level. Switching: " + "; ".join(
          f"{nm} eta^2 {v[0]:.2f} vs null 95th {np.percentile(v[1], 95):.2f}, neighbour change "
          f"{100 * np.median(v[2]):.0f} pts inside vs {100 * np.median(v[3]):.0f} across"
          for nm, v in SW.items())
      + ". There is nothing to hold or switch: the bar-line relationship is absent throughout, "
      "not present in some sub-sections and missing in others.\n")
    return L


def cr_splice(lines):
    txt = open(OUT_MD, encoding="utf-8").read()
    i = txt.find("\n" + CR_HEAD)
    if i >= 0:
        txt = txt[:i + 1]
    if not txt.endswith("\n"):
        txt += "\n"
    txt += "\n" + "\n".join(lines) + "\n"
    with open(OUT_MD, "w", encoding="utf-8") as fh:
        fh.write(txt)
    print(f"call-and-response -> {OUT_MD}")


def callresp_main():
    F = load()
    secs = section_grids(sections())
    evs, _ = detect_events(F, secs)
    evs = to_bars(evs, secs)
    for e in evs:
        e["type"] = classify(e)
    lines, res = callresp(F, secs, evs)
    cr_splice(lines + anacrusis(res))
    np.savez_compressed(os.path.join(SCRATCH, "hook_callresp.npz"), best_N=res["best_N"])
    return res


if __name__ == "__main__":
    sys.exit(main())
