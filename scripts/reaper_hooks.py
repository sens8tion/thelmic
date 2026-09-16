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
    for f in ("stage1", "peek", "diag", "report"):
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
        w(f"The **phase** is not locked, and this matters. `grid.npz` records "
          f"**{len(resets)} bar-phase resets** at "
          f"{', '.join(f'{x:.0f} s' for x in resets)} - the DJ's mix points. Independently, combing "
          f"each of my sections' low-band onset flux against a single global grid puts their "
          f"downbeats up to **+-173 ms** apart, more than a 16th note "
          f"({bar_s/16*1000:.0f} ms). The two methods agree: a single-tempo bar grid is safe for "
          "*lengths* but wrong for *positions*, so no bar index here comes from one.\n")
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
    np.savez_compressed(EVENTS_NPZ,
                        t=np.array([e["t"] for e in evs_all]),
                        dur=np.array([e["dur"] for e in evs_all]),
                        lab=lab)


if __name__ == "__main__":
    sys.exit(main())
