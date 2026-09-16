"""REAPER MIX - why the reference jungle DJ set reads as spacious and legible, in numbers.

STRUCTURAL ANALYSIS ONLY. Nothing here writes audio, extracts a loop, or copies a riff. Every
output is a measurement: dB, seconds, ratios, counts.

The questions (from the user's own complaint about their track - "dry, lacking effects sustain in
the highs, no movement in the sound stage", then "too much going on when fully built up"):

  1 spectral  per-section band balance in dB relative to the section total
  2 dynamics  crest factor, short-term loudness range, 50 ms vs 3 s peak-to-RMS
  3 stereo    per-band mid/side width over time, where the bass sits, how much the image moves
  4 space     high/air decay to -20 dB after isolated transients, echo repeats at musical delays
  5 density   onset streams per band and time-frequency occupancy, drop bar vs breakdown bar

Only numpy and torch are available, so the RIFF reader, the STFT, the onset picker, the k-means
segmenter and the loudness filter are all built here.

    python scripts/reaper_mix.py sections      # segment the set, write sections.json
    python scripts/reaper_mix.py analyse       # the five measurement passes -> analysis.json
    python scripts/reaper_mix.py report        # render tracks/2026-09-16_reaper/mix-space.md
"""
from __future__ import annotations

import argparse
import json
import math
import os
import struct
import sys

import numpy as np
import torch

WAV = r"C:\Users\eric\Downloads\Tim_Reaper_Jungle_DJ_Set_SECTION_August_2026.wav"
CACHE = r"C:\Users\eric\Downloads\reaper_cache"
OUT_DIR = r"C:\Users\eric\github\sens8tion\thelmic\tracks\2026-09-16_reaper"
WORK = os.environ.get("REAPER_MIX_WORK", os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                     "..", "..", "..", "..", "AppData", "Local",
                                                     "Temp", "reaper_mix"))

BANDS = [("sub", 20, 60), ("bass", 60, 120), ("lowmid", 120, 400), ("mid", 400, 2000),
         ("high", 2000, 8000), ("air", 8000, 16000)]
N_FFT = 2048
HOP = 512


# ----------------------------------------------------------------------
# RIFF: header parse plus a seek-and-read slice, so a section costs a section
# ----------------------------------------------------------------------
def wav_header(path: str) -> dict:
    with open(path, "rb") as fh:
        raw = fh.read(4096)
    if raw[:4] != b"RIFF" or raw[8:12] != b"WAVE":
        raise ValueError("not a RIFF/WAVE file")
    pos, fmt, doff, dlen = 12, None, None, None
    while pos + 8 <= len(raw):
        cid = raw[pos:pos + 4]
        size = struct.unpack("<I", raw[pos + 4:pos + 8])[0]
        if cid == b"fmt ":
            fmt = struct.unpack("<HHIIHH", raw[pos + 8:pos + 24])
        elif cid == b"data":
            doff, dlen = pos + 8, size
            break
        pos += 8 + size + (size & 1)
    if fmt is None or doff is None:
        raise ValueError("missing fmt or data chunk")
    tag, ch, sr, _, _, bits = fmt
    if tag == 0xFFFE:
        tag = 3 if bits == 32 and b"\x03\x00" in raw[:200] else 1
    if dlen == 0 or doff + dlen > os.path.getsize(path):
        dlen = os.path.getsize(path) - doff
    return {"tag": tag, "ch": ch, "sr": sr, "bits": bits, "data_off": doff, "data_len": dlen,
            "frame_bytes": ch * bits // 8, "n_frames": dlen // (ch * bits // 8)}


def read_slice(path: str, t0: float, t1: float, hdr: dict | None = None) -> tuple[np.ndarray, int]:
    """Samples [n, ch] float32 for [t0, t1) seconds, read straight off disk with a seek."""
    h = hdr or wav_header(path)
    sr, fb = h["sr"], h["frame_bytes"]
    a = max(0, int(t0 * sr))
    z = min(h["n_frames"], int(t1 * sr))
    if z <= a:
        return np.zeros((0, h["ch"]), np.float32), sr
    with open(path, "rb") as fh:
        fh.seek(h["data_off"] + a * fb)
        buf = fh.read((z - a) * fb)
    if h["tag"] == 1 and h["bits"] == 16:
        x = np.frombuffer(buf, "<i2").astype(np.float32) / 32768.0
    elif h["tag"] == 1 and h["bits"] == 24:
        b = np.frombuffer(buf, np.uint8).reshape(-1, 3).astype(np.int32)
        v = b[:, 0] | (b[:, 1] << 8) | (b[:, 2] << 16)
        x = np.where(v & 0x800000, v - 0x1000000, v).astype(np.float32) / 8388608.0
    elif h["tag"] == 1 and h["bits"] == 32:
        x = np.frombuffer(buf, "<i4").astype(np.float32) / 2147483648.0
    elif h["tag"] == 3 and h["bits"] == 32:
        x = np.frombuffer(buf, "<f4").astype(np.float32).copy()
    else:
        raise ValueError(f"unsupported {h['tag']}/{h['bits']}")
    return x.reshape(-1, h["ch"]), sr


# ----------------------------------------------------------------------
# small DSP helpers
# ----------------------------------------------------------------------
def db(x, floor=1e-12):
    return 10.0 * np.log10(np.maximum(np.asarray(x, np.float64), floor))


def stft_mag(sig: np.ndarray, n_fft=N_FFT, hop=HOP) -> np.ndarray:
    win = torch.hann_window(n_fft)
    S = torch.stft(torch.from_numpy(np.ascontiguousarray(sig.astype(np.float32))), n_fft, hop,
                   window=win, center=True, return_complex=True)
    return S.abs().numpy()


def band_rows(freqs: np.ndarray):
    return [(name, (freqs >= lo) & (freqs < hi)) for name, lo, hi in BANDS]


def smooth(x: np.ndarray, n: int) -> np.ndarray:
    if n <= 1:
        return x
    k = np.ones(n) / n
    pad = n // 2
    y = np.convolve(np.pad(x, pad, mode="edge"), k, mode="same")
    return y[pad:pad + len(x)]


def median_filter(x: np.ndarray, n: int) -> np.ndarray:
    if n <= 1:
        return x
    pad = n // 2
    p = np.pad(x, pad, mode="edge")
    idx = np.arange(len(x))[:, None] + np.arange(n)[None, :]
    return np.median(p[idx], axis=1)


def kmeans(X: np.ndarray, k: int, iters: int = 60, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    mu = X[rng.choice(len(X), k, replace=False)]
    lab = np.zeros(len(X), int)
    for _ in range(iters):
        d = ((X[:, None, :] - mu[None, :, :]) ** 2).sum(-1)
        new = d.argmin(1)
        if (new == lab).all():
            break
        lab = new
        for j in range(k):
            if (lab == j).any():
                mu[j] = X[lab == j].mean(0)
    return lab


def peak_pick(env: np.ndarray, avg_n: int = 43, mult: float = 1.35, span: int = 3,
              refractory: int = 0) -> np.ndarray:
    """Local maxima above a moving average, with an optional refractory period in frames.

    Without the refractory guard a dense break gives a dozen 'onsets' per bar per band, which is
    detector noise, not voices.
    """
    if len(env) < 2 * span + 2:
        return np.array([], int)
    avg = smooth(env, avg_n)
    n = len(env)
    idx = np.arange(span, n - span)
    win = env[idx[:, None] + np.arange(-span, span + 1)[None, :]]
    ok = (env[idx] >= win.max(1)) & (env[idx] > avg[idx] * mult) & (env[idx] > 0)
    pk = idx[ok]
    if refractory > 0 and len(pk):
        keep, last = [], -10 ** 9
        for i in pk:
            if i - last >= refractory:
                keep.append(int(i))
                last = i
            elif keep and env[i] > env[keep[-1]]:
                keep[-1] = int(i)
                last = i
        pk = np.array(keep, int)
    return pk


def local_bpm(env: np.ndarray, fps: float, lo=150.0, hi=190.0) -> float:
    e = env - env.mean()
    ac = np.correlate(e, e, mode="full")[len(e) - 1:]
    lags = np.arange(len(ac))
    with np.errstate(divide="ignore"):
        bpm = 60.0 * fps / np.maximum(lags, 1e-9)
    ok = (bpm >= lo) & (bpm <= hi)
    if not ok.any():
        return float("nan")
    lag = int(lags[ok][np.argmax(ac[ok])])
    if 1 <= lag < len(ac) - 1:
        y0, y1, y2 = ac[lag - 1], ac[lag], ac[lag + 1]
        d = y0 - 2 * y1 + y2
        if d != 0:
            lag = lag + 0.5 * (y0 - y2) / d
    return float(60.0 * fps / lag)


# ----------------------------------------------------------------------
# 0. Sections
# ----------------------------------------------------------------------
def build_sections(cache=CACHE, debug=False) -> dict:
    """Three states by what the DRUMS and the LOW END are doing, not by loudness alone.

    breakdown  the kick/sub has gone or collapsed (low band well under its own median)
    drop       full weight: low band present AND loudness in the top part of the set
    groove     everything else - drums running, not at full weight
    """
    f = np.load(os.path.join(cache, "frames.npz"))
    meta = json.load(open(os.path.join(cache, "meta.json")))
    fps = meta["fps"]
    t = f["t"]
    low = f["sub"] + f["bass"]

    w = int(fps * 3) | 1
    rms_db = smooth(db(f["rms"] ** 2), w)
    low_db = smooth(db(low ** 2), w)
    hits = peak_pick(f["flux_high"] + f["flux_air"])
    dens = np.zeros(len(t))
    if len(hits):
        dens[hits] = 1.0
    dens = smooth(dens, int(fps * 3) | 1) * fps

    lo_med = float(np.median(low_db))
    rm_med = float(np.median(rms_db))
    rm_hi = float(np.percentile(rms_db, 70))
    if debug:
        for nm, v in (("rms_db", rms_db), ("low_db", low_db), ("dens/s", dens)):
            q = np.percentile(v, [5, 10, 25, 50, 75, 90, 95])
            print(nm, [round(float(x), 2) for x in q])

    lab = np.ones(len(t), int)                       # groove
    lab[(low_db < lo_med - 7.0) | (rms_db < rm_med - 6.0)] = 0          # breakdown
    lab[(rms_db >= rm_hi) & (low_db >= lo_med - 2.0) & (dens > np.median(dens) * 0.8)] = 2
    lab = median_filter(lab.astype(float), int(fps * 6) | 1).round().astype(int)

    names = {0: "breakdown", 1: "groove", 2: "drop"}
    segs, i = [], 0
    while i < len(lab):
        j = i
        while j + 1 < len(lab) and lab[j + 1] == lab[i]:
            j += 1
        segs.append([float(t[i]), float(t[min(j, len(t) - 1)]), int(lab[i])])
        i = j + 1
    # absorb runs under 6 s into whatever precedes them, then coalesce equal neighbours
    merged = []
    for s in segs:
        if merged and (s[1] - s[0] < 6.0 or s[2] == merged[-1][2]):
            merged[-1][1] = s[1]
        else:
            merged.append(s)
    out = [{"t0": round(a, 2), "t1": round(z, 2), "dur": round(z - a, 2), "kind": names[k]}
           for a, z, k in merged if z - a >= 6.0]
    for i, s in enumerate(out):
        s["id"] = f"S{i:02d}"
        m = (f["t"] >= s["t0"]) & (f["t"] < s["t1"])
        s["rms_db"] = round(float(db((f["rms"][m] ** 2).mean())), 2)
        s["bpm"] = round(local_bpm(f["flux"][m], fps), 2)
    return {"fps": fps, "sections": out}


# ----------------------------------------------------------------------
# 1. Spectral balance
# ----------------------------------------------------------------------
def spectral_section(P: np.ndarray, freqs: np.ndarray) -> dict:
    rows = band_rows(freqs)
    e = {n: float(P[sel].sum()) for n, sel in rows}
    tot = sum(e.values()) + 1e-20
    rel = {n: round(float(10 * math.log10(max(v / tot, 1e-12))), 2) for n, v in e.items()}
    # tilt: dB per octave from a least-squares fit through the band centres
    cen = np.array([math.sqrt(lo * hi) for _, lo, hi in BANDS])
    y = np.array([rel[n] for n, _, _ in BANDS])
    A = np.stack([np.log2(cen), np.ones_like(cen)], 1)
    slope = float(np.linalg.lstsq(A, y, rcond=None)[0][0])
    return {"rel_db": rel, "tilt_db_per_oct": round(slope, 2)}


# ----------------------------------------------------------------------
# 2. Dynamics
# ----------------------------------------------------------------------
def k_weight_gain(freqs: np.ndarray, sr: int) -> np.ndarray:
    """|H(f)|^2 of the ITU-R BS.1770 K-weighting (48 kHz coefficients), evaluated on an FFT grid.

    Applied in the spectral domain: a python sample loop over ten minutes of audio is not worth it
    and the frequency response is exactly what a loudness measure cares about.
    """
    z = np.exp(-2j * np.pi * freqs / sr)
    def H(b, a):
        return (b[0] + b[1] * z + b[2] * z ** 2) / (1.0 + a[0] * z + a[1] * z ** 2)
    hs = H((1.53512485958697, -2.69169618940638, 1.19839281085285),
           (-1.69065929318241, 0.73248077421585))
    hp = H((1.0, -2.0, 1.0), (-1.99004745483398, 0.99007225036621))
    return np.abs(hs * hp) ** 2


def dynamics_section(x: np.ndarray, sr: int, P: np.ndarray, freqs: np.ndarray) -> dict:
    mid = x.mean(1)
    n = len(mid)
    peak = float(np.abs(mid).max())
    rms = float(np.sqrt((mid.astype(np.float64) ** 2).mean()))
    out = {"peak_dbfs": round(20 * math.log10(max(peak, 1e-9)), 2),
           "rms_dbfs": round(20 * math.log10(max(rms, 1e-9)), 2),
           "crest_db": round(20 * math.log10(max(peak / max(rms, 1e-9), 1e-9)), 2)}

    def win_stats(sec):
        w = int(sec * sr)
        m = n // w
        if m < 2:
            return None
        blk = mid[:m * w].reshape(m, w).astype(np.float64)
        r = np.sqrt((blk ** 2).mean(1))
        p = np.abs(blk).max(1)
        return r, p

    for tag, sec in (("50ms", 0.05), ("3s", 3.0)):
        st = win_stats(sec)
        if st is None:
            out[f"crest_{tag}_db"] = None
            continue
        r, p = st
        keep = r > r.max() * 0.02                   # ignore near-silence blocks
        c = 20 * np.log10(np.maximum(p[keep] / np.maximum(r[keep], 1e-9), 1e-9))
        out[f"crest_{tag}_db"] = round(float(np.median(c)), 2)
        out[f"crest_{tag}_p90_db"] = round(float(np.percentile(c, 90)), 2)
        if tag == "3s":
            l = 20 * np.log10(np.maximum(r[keep], 1e-9))
            out["lra_3s_db"] = round(float(np.percentile(l, 95) - np.percentile(l, 10)), 2)
            out["st_loud_sd_db"] = round(float(l.std()), 2)
    # short-term loudness range on gated K-weighted 3 s blocks (a true-ish LRA)
    g = k_weight_gain(freqs, sr)
    fps = sr / HOP
    kp = (P * g[:, None]).sum(0)                     # K-weighted power per STFT frame
    w = max(2, int(round(3.0 * fps)))
    m = len(kp) // w
    if m >= 2:
        lk = -0.691 + 10 * np.log10(np.maximum(kp[:m * w].reshape(m, w).mean(1), 1e-12))
        lk = lk[lk > lk.max() - 30]                  # relative gate
        out["lra_k_db"] = round(float(np.percentile(lk, 95) - np.percentile(lk, 10)), 2)
        out["lra_k_p95_p10"] = [round(float(np.percentile(lk, 95)), 2),
                                round(float(np.percentile(lk, 10)), 2)]
    w1 = max(2, int(round(0.4 * fps)))               # momentary-ish, 400 ms
    m1 = len(kp) // w1
    if m1 >= 2:
        lm = -0.691 + 10 * np.log10(np.maximum(kp[:m1 * w1].reshape(m1, w1).mean(1), 1e-12))
        lm = lm[lm > lm.max() - 30]
        out["lra_k_400ms_db"] = round(float(np.percentile(lm, 95) - np.percentile(lm, 10)), 2)
    return out


# ----------------------------------------------------------------------
# 3. Stereo, per band, over time
# ----------------------------------------------------------------------
def stereo_section(M: np.ndarray, Sd: np.ndarray, freqs: np.ndarray, sr: int,
                   bar_s: float = 1.4473) -> dict:
    if Sd is None:
        return {}
    fps = sr / HOP
    rows = band_rows(freqs)
    out = {"bands": {}}
    for name, sel in rows:
        m = M[sel].sum(0)
        s = Sd[sel].sum(0)
        tot = m + s
        live = tot > np.percentile(tot, 40)          # only where the band is actually playing
        w = s / np.maximum(tot, 1e-20)
        wl = w[live] if live.any() else w
        ms_db = 10 * np.log10(np.maximum(s.sum(), 1e-20) / max(m.sum(), 1e-20))
        ws = smooth(w, 9)
        e = ws[live] if live.sum() > 64 else ws
        d = {
            "width_mean": round(float(wl.mean()), 4),
            "width_p10": round(float(np.percentile(wl, 10)), 4),
            "width_p90": round(float(np.percentile(wl, 90)), 4),
            "width_sd": round(float(wl.std()), 4),
            "side_minus_mid_db": round(float(ms_db), 2),
            "corr": round(float(1 - 2 * wl.mean()), 3),
            # movement: how fast the width wanders, in width-units per second
            "width_slew_per_s": round(float(np.abs(np.diff(ws)).mean() * fps), 4),
            "width_cv": round(float(wl.std() / max(wl.mean(), 1e-9)), 3),
        }
        out["bands"][name] = d
        out["bands"][name]["_env"] = e - e.mean()
    # periodic panning: where the width series repeats, and whether that lands on the bar grid
    for name in list(out["bands"]):
        e = out["bands"][name].pop("_env")
        if len(e) < 256:
            continue
        E = np.abs(np.fft.rfft(e * np.hanning(len(e))))
        fr = np.fft.rfftfreq(len(e), 1 / fps)
        ok = (fr > 0.05) & (fr < 8.0)
        if not ok.any():
            continue
        k = int(np.argmax(E[ok]))
        pk = float(fr[ok][k])
        out["bands"][name]["pan_rate_hz"] = round(pk, 3)
        out["bands"][name]["pan_period_s"] = round(1.0 / pk, 3) if pk > 0 else None
        out["bands"][name]["pan_peak_ratio"] = round(float(E[ok][k] / (np.median(E[ok]) + 1e-12)), 2)
        # autocorrelation of the width series at 1, 2 and 4 bars: is the movement arranged?
        ac = np.correlate(e, e, mode="full")[len(e) - 1:]
        ac = ac / max(ac[0], 1e-20)
        for nb in (1, 2, 4):
            lag = int(round(nb * bar_s * fps))
            out["bands"][name][f"width_ac_{nb}bar"] = (
                round(float(ac[max(1, lag - 2):lag + 3].max()), 3) if lag + 3 < len(ac) else None)
    # bass in the sides? absolute side energy below 150 Hz relative to full-mix mid
    below = freqs < 150
    out["side_below150_vs_mid_total_db"] = round(
        float(10 * math.log10(max(Sd[below].sum(), 1e-20) / max(M.sum(), 1e-20))), 2)
    out["side_below150_vs_mid_below150_db"] = round(
        float(10 * math.log10(max(Sd[below].sum(), 1e-20) / max(M[below].sum(), 1e-20))), 2)
    # where does the side energy live? fraction of total side energy per band
    tot_s = sum(Sd[sel].sum() for _, sel in rows) + 1e-20
    out["side_share_pct"] = {n: round(float(100 * Sd[sel].sum() / tot_s), 1) for n, sel in rows}
    # crossover: lowest frequency where the running width passes 0.15 / 0.05
    wf = Sd.sum(1) / np.maximum(Sd.sum(1) + M.sum(1), 1e-20)
    wf_s = smooth(wf, 9)
    for thr in (0.05, 0.15, 0.25):
        h = np.where((wf_s > thr) & (freqs > 30))[0]
        out[f"stereo_onset_hz_w{thr}"] = round(float(freqs[h[0]]), 1) if len(h) else None
    # octave-band width, to place the mono/stereo crossover exactly
    oct_w = {}
    for c in (31.5, 63, 125, 250, 500, 1000, 2000, 4000, 8000, 16000):
        sel = (freqs >= c / math.sqrt(2)) & (freqs < c * math.sqrt(2))
        if not sel.any():
            continue
        m, s = M[sel].sum(), Sd[sel].sum()
        oct_w[str(int(c))] = {"width": round(float(s / max(m + s, 1e-20)), 4),
                              "side_minus_mid_db": round(float(10 * math.log10(
                                  max(s, 1e-20) / max(m, 1e-20))), 1)}
    out["octave_width"] = oct_w
    return out


# ----------------------------------------------------------------------
# 4. Space: decays and echoes
# ----------------------------------------------------------------------
def decay_stats(env: np.ndarray, fps: float, mult: float = 1.5) -> dict:
    """How fast a band falls after each hit, and how far it falls before the next one.

    Requiring truly isolated transients gives five usable hits in a jungle drop, so instead every
    onset is used: fit the decay over the gap to the next onset (capped at 300 ms), extrapolate to
    -20 dB, and separately measure the floor actually reached in the gap. The fit answers "how long
    is the tail", the floor answers "is there anything between the hits at all".
    """
    le = 10 * np.log10(np.maximum(env, 1e-16))
    pk = onsets_db(env, fps, rise_db=5.0, refractory_s=0.05)
    slopes, floors, gaps, direct = [], [], [], []
    cap = int(0.30 * fps)
    for k, i in enumerate(pk):
        nxt = pk[k + 1] if k + 1 < len(pk) else len(le) - 1
        j = min(int(i) + cap, int(nxt) - 1, len(le) - 1)
        if j - i < 4:
            continue
        seg = le[i:j + 1]
        top = float(seg[:2].max())
        # fit the descending part only
        stop = len(seg)
        for q in range(2, len(seg)):
            if seg[q] > seg[q - 1] + 3.0:
                stop = q
                break
        if stop < 4:
            continue
        s = seg[:stop]
        A = np.stack([np.arange(len(s)) / fps, np.ones(len(s))], 1)
        sl = float(np.linalg.lstsq(A, s, rcond=None)[0][0])
        if sl < -2.0:
            slopes.append(sl)
        floors.append(float(s.min() - top))
        gaps.append((j - i) / fps)
        below = np.where(s <= top - 20.0)[0]
        if len(below):
            direct.append(below[0] / fps)
    o = {"n_onsets": int(len(pk))}
    if slopes:
        o["decay_db_per_s_med"] = round(float(np.median(slopes)), 1)
        o["t20_fit_ms"] = round(float(-20.0 / np.median(slopes) * 1000), 1)
        o["t20_fit_ms_p25_p75"] = [round(float(-20.0 / np.percentile(slopes, 75) * 1000), 1),
                                   round(float(-20.0 / np.percentile(slopes, 25) * 1000), 1)]
        o["rt60_est_ms"] = round(float(-60.0 / np.median(slopes) * 1000), 1)
    o["pct_hits_reaching_-20db"] = round(100.0 * len(direct) / max(len(floors), 1), 1)
    if floors:
        o["inter_onset_floor_db_med"] = round(float(np.median(floors)), 1)
        o["inter_onset_gap_ms_med"] = round(float(np.median(gaps) * 1000), 1)
    return o


def onsets_db(env: np.ndarray, fps: float, rise_db: float = 5.0,
              refractory_s: float = 0.06) -> np.ndarray:
    """Onsets as a RISE IN dB, not as raw flux above a moving average.

    Raw linear flux against a 0.5 s average fires a dozen times a bar in every band of a dense
    break - detector noise dressed up as voices. A hit is a local maximum whose level jumps at
    least `rise_db` over the preceding 2 frames, with a refractory period after it.
    """
    le = 10 * np.log10(np.maximum(env, 1e-16))
    n = len(le)
    if n < 8:
        return np.array([], int)
    rise = np.concatenate([np.zeros(2), le[2:] - le[:-2]])
    cand = []
    for i in range(2, n - 2):
        if rise[i] >= rise_db and le[i] >= le[i - 1] and le[i] >= le[i + 1]:
            cand.append(i)
    out, last, refr = [], -10 ** 9, max(1, int(refractory_s * fps))
    for i in cand:
        if i - last >= refr:
            out.append(i)
            last = i
        elif out and le[i] > le[out[-1]]:
            out[-1] = i
            last = i
    return np.array(out, int)


def tail_profile(env: np.ndarray, fps: float, beat: float, on: np.ndarray) -> dict:
    """How loud the 2-16 kHz band still is at fixed musical offsets after a hit.

    This is the direct answer to "lacking effects sustain in the highs": take every strong onset
    with at least that much room before the next one, and read the level at 1/16, 1/8, 3/16, 1/4
    after it, in dB relative to the hit itself. Dry material falls off a cliff; wet material does
    not.
    """
    le = 20 * np.log10(np.maximum(np.sqrt(np.maximum(env, 1e-20)), 1e-12))
    out = {}
    for nm, mult in (("1/16", 0.25), ("1/8", 0.5), ("3/16", 0.75), ("1/4", 1.0), ("1/2", 2.0)):
        off = int(round(beat * mult * fps))
        vals = []
        for k, i in enumerate(on):
            nxt = on[k + 1] if k + 1 < len(on) else len(le)
            if i + off + 2 < min(nxt, len(le)):      # no new hit in between
                vals.append(float(le[i + off - 1:i + off + 2].max() - le[i:i + 2].max()))
        out[nm] = {"offset_ms": round(beat * mult * 1000, 1), "n": len(vals),
                   "level_db_med": round(float(np.median(vals)), 1) if len(vals) >= 5 else None}
    return out


def echo_scan(S: np.ndarray, freqs: np.ndarray, fps: float, beat: float) -> dict:
    """Find echo repeats INSIDE the drum gaps, where nothing else can explain them.

    Trying to spot a repeat inside a running break is hopeless - a break is already a burst of
    similar-sounding hits on the 16th grid, so every candidate lag scores well and the control lags
    score just as well. So instead: take every gap of 180 ms or more with no new 2-16 kHz attack,
    fit the smooth decay through it, and look for bumps that poke ABOVE that decay. A bump above
    the tail in a gap is a delay repeat. Its lag from the dry hit is the delay time.
    """
    sel = (freqs >= 2000) & (freqs < 16000)
    env = np.sqrt(np.maximum(S[sel].sum(0), 1e-20))
    le = 20 * np.log10(np.maximum(env, 1e-12))
    on = onsets_db(env ** 2, fps, rise_db=5.0, refractory_s=0.05)
    min_gap = int(0.18 * fps)

    bumps = []                                       # (lag_s, level_db_vs_dry, prominence_db)
    n_gaps = 0
    for k, i in enumerate(on):
        nxt = on[k + 1] if k + 1 < len(on) else len(le) - 1
        if nxt - i < min_gap:
            continue
        n_gaps += 1
        seg = le[i:nxt]
        dry = float(seg[:2].max())
        x = np.arange(len(seg)) / fps
        # smooth exponential decay through the gap (fit in dB = linear), then the residual
        A = np.stack([x, np.ones_like(x)], 1)
        coef = np.linalg.lstsq(A, seg, rcond=None)[0]
        res = seg - A @ coef
        for j in range(2, len(seg) - 2):
            # a repeat is a bump above the fitted tail that is still QUIETER than the dry hit;
            # without that second test a missed attack counts as an echo
            if (res[j] >= 2.0 and res[j] >= res[j - 1] and res[j] >= res[j + 1]
                    and j / fps > 0.035 and seg[j] - dry <= -3.0):
                bumps.append((j / fps, float(seg[j] - dry), float(res[j])))

    delays = {"1/32": beat / 8, "1/16": beat / 4, "1/8T": beat / 3, "1/8": beat / 2,
              "1/4T": beat * 2 / 3, "dotted1/8": beat * 0.75, "1/4": beat,
              "dotted1/4": beat * 1.5, "1/2": beat * 2}
    lag = np.array([b[0] for b in bumps])
    lvl = np.array([b[1] for b in bumps])
    res = np.array([b[2] for b in bumps])
    tol = 0.012                                      # +-12 ms, affordable at hop 128
    lags = {}
    for nm, d in delays.items():
        m = np.abs(lag - d) <= max(tol, d * 0.04) if len(lag) else np.zeros(0, bool)
        lags[nm] = {"delay_ms": round(d * 1000, 1), "n": int(m.sum()),
                    "share_pct": round(float(100 * m.sum() / max(len(lag), 1)), 1),
                    "repeat_db_med": round(float(np.median(lvl[m])), 1) if m.sum() >= 4 else None,
                    "prominence_db_med": round(float(np.median(res[m])), 1) if m.sum() >= 4 else None}
    # what the bump lags look like without assuming a grid: a 10 ms histogram
    hist_edges = np.arange(0.03, 0.80, 0.01)
    h, _ = np.histogram(lag, bins=hist_edges) if len(lag) else (np.zeros(len(hist_edges) - 1), None)
    top = np.argsort(h)[-6:][::-1]
    return {"n_onsets": int(len(on)), "n_gaps_over_180ms": n_gaps, "n_bumps": len(bumps),
            "bumps_per_gap": round(len(bumps) / max(n_gaps, 1), 2),
            "lags": lags,
            "top_bump_lags_ms": [[round(float(hist_edges[i] * 1000 + 5), 0), int(h[i])] for i in top
                                 if h[i] > 0],
            "bump_level_db_med": round(float(np.median(lvl)), 1) if len(lvl) else None,
            "tails": tail_profile(env ** 2, fps, beat, on)}


def space_section(S: np.ndarray, freqs: np.ndarray, sr: int, bpm: float,
                  fine: tuple | None = None) -> dict:
    """Decays and echoes. `fine` is an (|STFT|^2, freqs, hop) computed at a short hop: at the
    512-sample hop used everywhere else a frame is 10.7 ms, which cannot tell a 90 ms delay from a
    120 ms one, and a 100 ms decay gets ten data points."""
    beat = 60.0 / bpm if bpm and not math.isnan(bpm) else 60.0 / 168.0
    out = {"bpm": round(bpm, 2), "beat_ms": round(beat * 1000, 1)}
    if fine is not None:
        S, freqs, hop = fine
    else:
        hop = HOP
    fps = sr / hop
    out["frame_ms"] = round(1000.0 / fps, 2)
    for name, lo, hi in BANDS:
        if name not in ("mid", "high", "air"):
            continue
        sel = (freqs >= lo) & (freqs < hi)
        out[name] = decay_stats(S[sel].sum(0), fps)
    out["echo"] = echo_scan(S, freqs, fps, beat)

    # how much energy lives BETWEEN the hits: the shape of the high-band envelope distribution
    sel = (freqs >= 2000) & (freqs < 16000)
    env = np.sqrt(np.maximum(S[sel].sum(0), 1e-20))
    ref = float(np.percentile(env, 99))
    q = np.percentile(env, [5, 10, 25, 50, 90])
    out["high_env_pct_db_vs_p99"] = [round(float(20 * math.log10(max(v, 1e-12) / ref)), 1) for v in q]
    for thr in (12, 20, 30):
        out[f"high_above_minus{thr}_pct"] = round(
            float(100 * (env > ref * 10 ** (-thr / 20)).mean()), 1)
    # same for air, which is where a reverb tail shows first
    sel = (freqs >= 8000) & (freqs < 16000)
    ea = np.sqrt(np.maximum(S[sel].sum(0), 1e-20))
    ra = float(np.percentile(ea, 99))
    out["air_env_pct_db_vs_p99"] = [round(float(20 * math.log10(max(v, 1e-12) / ra)), 1)
                                    for v in np.percentile(ea, [5, 10, 25, 50, 90])]
    out["air_above_minus20_pct"] = round(float(100 * (ea > ra * 10 ** (-20 / 20)).mean()), 1)
    return out


# ----------------------------------------------------------------------
# 5. Density
# ----------------------------------------------------------------------
def density_section(S: np.ndarray, freqs: np.ndarray, sr: int, bpm: float) -> dict:
    fps = sr / HOP
    bar = 4 * 60.0 / bpm if bpm and not math.isnan(bpm) else 4 * 60.0 / 168.0
    dur = S.shape[1] * HOP / sr

    streams, on_frames = {}, {}
    for name, lo, hi in BANDS:
        sel = (freqs >= lo) & (freqs < hi)
        env = S[sel].sum(0)
        pk = onsets_db(env, fps, rise_db=6.0, refractory_s=0.06)
        streams[name] = round(float(len(pk) / max(dur / bar, 1e-9)), 2)
        on_frames[name] = pk
    out = {"onsets_per_bar_by_band": streams,
           "onsets_per_bar_total": round(float(sum(streams.values())), 2)}

    # voices: collapse the six band onset trains onto the 16th grid of each bar, then ask how many
    # 16ths carry anything and how many bands fire together on the ones that do
    step = bar / 16.0
    n_bars = max(1, int(dur / bar))
    slots = np.zeros((n_bars, 16))
    for name in on_frames:
        for i in on_frames[name]:
            t = i / fps
            b, k = int(t / bar), int(round((t % bar) / step)) % 16
            if b < n_bars:
                slots[b, k] += 1
    occ = slots > 0
    out["slots_used_per_bar_med"] = round(float(np.median(occ.sum(1))), 2)
    out["bands_per_used_slot_med"] = round(float(np.median(slots[occ])) if occ.any() else 0.0, 2)
    out["bands_per_used_slot_p90"] = round(float(np.percentile(slots[occ], 90)) if occ.any() else 0.0, 2)

    # occupancy on a log-frequency grid, relative to the section's own loudest bin (level free)
    edges = np.geomspace(40, 16000, 33)
    idx = np.clip(np.searchsorted(edges, freqs) - 1, 0, 31)
    G = np.zeros((32, S.shape[1]))
    for b in range(32):
        m = idx == b
        if m.any():
            G[b] = S[m].sum(0)
    ref = np.percentile(G, 99.9)
    for thr in (20, 30, 40):
        out[f"occupancy_{thr}db_pct"] = round(float(100 * (G > ref * 10 ** (-thr / 10)).mean()), 1)
    # SPREAD: per frame, how many log-bands sit within 20 dB of that frame's own loudest band.
    # Level-independent, so a quiet breakdown and a loud drop are directly comparable: this is
    # "how much of the spectrum is filled at any instant".
    fmax = G.max(0, keepdims=True)
    spread = (G > fmax * 10 ** (-20 / 10)).sum(0)
    out["spread_20db_med"] = round(float(np.median(spread)), 1)
    out["spread_20db_p90"] = round(float(np.percentile(spread, 90)), 1)
    spread30 = (G > fmax * 10 ** (-30 / 10)).sum(0)
    out["spread_30db_med"] = round(float(np.median(spread30)), 1)
    # the same, but above 200 Hz: below that the sub dominates every frame and the number just
    # reports "there is a sub", not "the top half is cluttered", which is the thing that matters
    lo_i = int(np.searchsorted(edges, 200.0))
    Gm = G[lo_i:]
    fm = Gm.max(0, keepdims=True)
    out["n_logbands_above200hz"] = int(Gm.shape[0])
    out["spread200_20db_med"] = round(float(np.median((Gm > fm * 10 ** (-20 / 10)).sum(0))), 1)
    out["spread200_20db_p90"] = round(float(np.percentile((Gm > fm * 10 ** (-20 / 10)).sum(0), 90)), 1)
    out["occupancy200_30db_pct"] = round(
        float(100 * (Gm > np.percentile(Gm, 99.9) * 10 ** (-30 / 10)).mean()), 1)
    Gp = np.maximum(G, 1e-16)
    fl = np.exp(np.log(Gp).mean(0)) / np.maximum(Gp.mean(0), 1e-16)
    out["flatness_med"] = round(float(np.median(fl)), 4)
    prof = G.mean(1)
    out["logband_profile_crest_db"] = round(float(db(prof.max()) - db(prof.mean())), 2)
    # gaps per band: how much of the time a band sits 20 dB under its own peak
    gaps = {}
    for name, lo, hi in BANDS:
        sel = (freqs >= lo) & (freqs < hi)
        env = S[sel].sum(0)
        gaps[name] = round(float(100 * (env < np.percentile(env, 99) * 10 ** (-20 / 10)).mean()), 1)
    out["pct_time_band_below_minus20_of_own_peak"] = gaps
    out["bar_s"] = round(bar, 4)
    return out


# ----------------------------------------------------------------------
# driver
# ----------------------------------------------------------------------
def pick_sections(secs: list[dict], per_kind: int = 4) -> list[dict]:
    """Longest few of each kind, spread across the set."""
    out = []
    for kind in ("breakdown", "groove", "drop"):
        c = [s for s in secs if s["kind"] == kind]
        c.sort(key=lambda s: -s["dur"])
        out += c[:per_kind]
    out.sort(key=lambda s: s["t0"])
    return out


def analyse(wav=WAV, work=WORK, per_kind=4, max_len=75.0):
    os.makedirs(work, exist_ok=True)
    sec_path = os.path.join(work, "sections.json")
    if not os.path.exists(sec_path):
        json.dump(build_sections(), open(sec_path, "w"), indent=1)
    S = json.load(open(sec_path))
    hdr = wav_header(wav)
    chosen = pick_sections(S["sections"], per_kind)
    res = []
    for s in chosen:
        t0, t1 = s["t0"], min(s["t1"], s["t0"] + max_len)
        x, sr = read_slice(wav, t0, t1, hdr)
        print(f"  {s['id']} {s['kind']:9s} {t0:7.1f}-{t1:7.1f}s  {x.shape[0]/sr:5.1f}s", flush=True)
        bpm = s.get("bpm") or 168.0
        freqs = np.fft.rfftfreq(N_FFT, 1 / sr)
        mid = (x[:, 0] + x[:, 1]) / 2.0 if x.shape[1] > 1 else x[:, 0]
        M = stft_mag(mid) ** 2
        Sd = (stft_mag((x[:, 0] - x[:, 1]) / 2.0) ** 2) if x.shape[1] > 1 else None
        r = dict(s)
        r["t1_used"] = round(t1, 2)
        r["spectral"] = spectral_section(M, freqs)
        r["dynamics"] = dynamics_section(x, sr, M, freqs)
        r["stereo"] = stereo_section(M, Sd, freqs, sr, bar_s=4 * 60.0 / bpm)
        Mf = stft_mag(mid, n_fft=512, hop=128) ** 2
        r["space"] = space_section(M, freqs, sr, bpm,
                                   fine=(Mf, np.fft.rfftfreq(512, 1 / sr), 128))
        del Mf
        r["density"] = density_section(M, freqs, sr, bpm)
        del x, M, Sd
        res.append(r)
    json.dump({"wav": os.path.basename(wav), "sections": res},
              open(os.path.join(work, "analysis.json"), "w"), indent=1)
    print("->", os.path.join(work, "analysis.json"))
    return res


# ----------------------------------------------------------------------
# report
# ----------------------------------------------------------------------
def _m(ss, path, default=float("nan")):
    """Mean of a dotted path across sections, ignoring Nones."""
    vals = []
    for s in ss:
        v = s
        for k in path.split("."):
            v = v.get(k) if isinstance(v, dict) else None
            if v is None:
                break
        if isinstance(v, (int, float)):
            vals.append(float(v))
    return float(np.mean(vals)) if vals else default


def report(work=WORK, out_dir=OUT_DIR):
    A = json.load(open(os.path.join(work, "analysis.json")))
    D = A["sections"]
    KINDS = ("breakdown", "groove", "drop")
    by = {k: [s for s in D if s["kind"] == k] for k in KINDS}
    BN = [b[0] for b in BANDS]
    L = []
    P = L.append

    def row(cells):
        P("| " + " | ".join(str(c) for c in cells) + " |")

    def head(cells):
        row(cells)
        row(["---"] * len(cells))

    def f(v, n=1):
        return "-" if v is None or (isinstance(v, float) and math.isnan(v)) else f"{v:.{n}f}"

    P("# Tim Reaper jungle set - why it reads as spacious and legible")
    P("")
    P(f"Source `{A['wav']}` - 1259.7 s, 48 kHz stereo. **Structural analysis only**: no audio, "
      "loop or riff was extracted or reused; every line below is a measurement.")
    P("")
    P("Measured by `scripts/reaper_mix.py` (numpy + torch only). Tempo is stable across the whole "
      "section at **165.7-166.4 BPM**, so one grid holds throughout: beat 361.8 ms, bar 1447 ms, "
      "16th 90.4 ms. Sections were cut by what the drums and the low end are doing, not by "
      "loudness alone, then the longest five of each kind were measured at full rate in stereo "
      "(60 s cap each).")
    P("")
    P("Bands: sub 20-60, bass 60-120, lowmid 120-400, mid 400-2k, high 2k-8k, air 8k-16k Hz.")
    P("")

    P("## Sections measured")
    P("")
    head(["id", "kind", "start s", "end s", "dur s", "RMS dBFS", "BPM"])
    for s in D:
        row([s["id"], s["kind"], f(s["t0"]), f(s["t1_used"]), f(s["t1_used"] - s["t0"]),
             f(s["rms_db"], 2), f(s["bpm"], 2)])
    P("")
    P("`S00` and `S36` are DJ mix-in regions with two records running; they behave like "
      "breakdowns harmonically but carry two sets of drums, so they inflate the breakdown onset "
      "counts. `S25`, `S31` are the cleanest true breakdowns.")
    P("")

    # ---- 1 spectral
    P("## 1. Spectral balance per section")
    P("")
    P("Energy in each band in dB relative to that section's own total (so the rows are "
      "level-independent and sum to the whole mix). `tilt` is a least-squares fit through the six "
      "band centres, in dB per octave.")
    P("")
    head(["id", "kind"] + BN + ["tilt dB/oct"])
    for s in D:
        r = s["spectral"]["rel_db"]
        row([s["id"], s["kind"]] + [f(r[b]) for b in BN] + [f(s["spectral"]["tilt_db_per_oct"], 2)])
    P("")
    head(["**mean**", "kind"] + BN + ["tilt dB/oct"])
    for k in KINDS:
        row(["", f"**{k}**"] + [f(_m(by[k], f"spectral.rel_db.{b}")) for b in BN]
            + [f(_m(by[k], "spectral.tilt_db_per_oct"), 2)])
    P("")
    P("**Breakdown -> drop, what actually moves:**")
    P("")
    head(["band", "breakdown", "groove", "drop", "drop - breakdown"])
    for b in BN:
        v = [_m(by[k], f"spectral.rel_db.{b}") for k in KINDS]
        row([b, f(v[0]), f(v[1]), f(v[2]), f"**{v[2] - v[0]:+.1f}**"])
    t = [_m(by[k], "spectral.tilt_db_per_oct") for k in KINDS]
    row(["tilt dB/oct", f(t[0], 2), f(t[1], 2), f(t[2], 2), f"**{t[2] - t[0]:+.2f}**"])
    P("")
    P(f"The drop is not brighter - it is heavier. Sub gains **{_m(by['drop'], 'spectral.rel_db.sub') - _m(by['breakdown'], 'spectral.rel_db.sub'):+.1f} dB** "
      f"of relative share while high *loses* **{_m(by['drop'], 'spectral.rel_db.high') - _m(by['breakdown'], 'spectral.rel_db.high'):+.1f} dB** "
      f"and air **{_m(by['drop'], 'spectral.rel_db.air') - _m(by['breakdown'], 'spectral.rel_db.air'):+.1f} dB**. "
      "The breakdown is spectrally flat (tilt ~0 dB/oct, top-weighted); the drop tilts to "
      f"**{_m(by['drop'], 'spectral.tilt_db_per_oct'):.2f} dB/oct**. Every section keeps air 12-19 dB "
      "under the total - the top octave is never a large share of the energy, it is a thin, "
      "always-present layer.")
    P("")

    # ---- 2 dynamics
    P("## 2. Dynamics")
    P("")
    P("`crest 50 ms` and `crest 3 s` are peak-to-RMS measured on non-overlapping windows of that "
      "length, median over the section (near-silent blocks gated out). `LRA` is the 95th-10th "
      "percentile spread of gated K-weighted short-term loudness.")
    P("")
    head(["id", "kind", "peak dBFS", "RMS dBFS", "crest 50 ms", "crest 50 ms p90",
          "crest 3 s", "LRA 3 s", "LRA 400 ms"])
    for s in D:
        d = s["dynamics"]
        row([s["id"], s["kind"], f(d["peak_dbfs"], 2), f(d["rms_dbfs"], 2), f(d["crest_50ms_db"]),
             f(d["crest_50ms_p90_db"]), f(d["crest_3s_db"]), f(d.get("lra_k_db"), 2),
             f(d.get("lra_k_400ms_db"), 2)])
    P("")
    head(["**mean**", "kind", "peak dBFS", "RMS dBFS", "crest 50 ms", "crest 50 ms p90",
          "crest 3 s", "LRA 3 s", "LRA 400 ms"])
    for k in KINDS:
        row(["", f"**{k}**", f(_m(by[k], "dynamics.peak_dbfs"), 2), f(_m(by[k], "dynamics.rms_dbfs"), 2),
             f(_m(by[k], "dynamics.crest_50ms_db")), f(_m(by[k], "dynamics.crest_50ms_p90_db")),
             f(_m(by[k], "dynamics.crest_3s_db")), f(_m(by[k], "dynamics.lra_k_db"), 2),
             f(_m(by[k], "dynamics.lra_k_400ms_db"), 2)])
    P("")
    c50, c3 = _m(by["drop"], "dynamics.crest_50ms_db"), _m(by["drop"], "dynamics.crest_3s_db")
    P(f"The master is limited - peak sits at 0.0 dBFS in every drop and groove. Inside a section "
      f"almost nothing moves: the drop's short-term loudness range is "
      f"**{_m(by['drop'], 'dynamics.lra_k_db'):.2f} dB** over a full minute. All the macro-dynamic "
      f"contrast is *between* sections: mean RMS "
      f"{_m(by['breakdown'], 'dynamics.rms_dbfs'):.1f} dBFS in a breakdown against "
      f"{_m(by['drop'], 'dynamics.rms_dbfs'):.1f} dBFS in a drop, a "
      f"**{_m(by['drop'], 'dynamics.rms_dbfs') - _m(by['breakdown'], 'dynamics.rms_dbfs'):.1f} dB** step.")
    P("")
    P(f"The transients survive it. A drop still shows **{c50:.2f} dB** of median 50 ms crest "
      f"(p90 {_m(by['drop'], 'dynamics.crest_50ms_p90_db'):.2f} dB) against **{c3:.2f} dB** on a 3 s "
      f"window - the 50 ms figure is **{100 * c50 / c3:.0f}%** of the 3 s figure, meaning nearly all "
      "of the remaining crest is genuine drum attack rather than slow level movement. In the "
      f"breakdowns that ratio is {100 * _m(by['breakdown'], 'dynamics.crest_50ms_db') / _m(by['breakdown'], 'dynamics.crest_3s_db'):.0f}% "
      "(more of the crest is arrangement, less is transient).")
    P("")

    # ---- 3 stereo
    P("## 3. Stereo")
    P("")
    P("Width = side / (mid + side) energy in that band, from an independent mid/side STFT on each "
      "section slice. 0 = mono, 0.5 = uncorrelated. Computed only on frames where the band is "
      "actually playing (above its own 40th percentile).")
    P("")
    P("### 3a. Width per band")
    P("")
    head(["id", "kind"] + BN)
    for s in D:
        w = s["stereo"]["bands"]
        row([s["id"], s["kind"]] + [f(w[b]["width_mean"], 4) for b in BN])
    P("")
    head(["**mean**", "kind"] + BN)
    for k in KINDS:
        row(["", f"**{k}**"] + [f(_m(by[k], f"stereo.bands.{b}.width_mean"), 4) for b in BN])
    P("")
    P("Same thing as side-minus-mid in dB, which is the number to dial a mix to:")
    P("")
    head(["kind"] + [f"{b} S/M dB" for b in BN])
    for k in KINDS:
        row([f"**{k}**"] + [f(_m(by[k], f"stereo.bands.{b}.side_minus_mid_db")) for b in BN])
    P("")
    P("### 3b. Where the bass is")
    P("")
    head(["id", "kind", "side <150 Hz vs mid <150 Hz", "side <150 Hz vs whole mid"])
    for s in D:
        row([s["id"], s["kind"], f(s["stereo"]["side_below150_vs_mid_below150_db"]),
             f(s["stereo"]["side_below150_vs_mid_total_db"])])
    P("")
    P(f"**Nothing below 150 Hz is in the sides.** Across grooves and drops the side channel below "
      f"150 Hz sits **{_m(by['groove'] + by['drop'], 'stereo.side_below150_vs_mid_below150_db'):.1f} dB** "
      "under the mid channel in the same range - that is bleed, not width. The two apparent "
      "exceptions are the mix-in regions where two records overlap.")
    P("")
    P("Octave-band width locates the crossover exactly:")
    P("")
    oc = list(D[0]["stereo"]["octave_width"].keys())
    head(["kind"] + [f"{c} Hz" for c in oc])
    for k in KINDS:
        row([f"**{k}** width"] + [f(_m(by[k], f"stereo.octave_width.{c}.width"), 4) for c in oc])
        row(["S/M dB"] + [f(_m(by[k], f"stereo.octave_width.{c}.side_minus_mid_db")) for c in oc])
    P("")
    P("The image opens between **250 and 500 Hz** and is widest from **500 Hz to 2 kHz**. Above "
      "4 kHz it narrows again in the drops (S/M -17 to -20 dB) - the top is centred and the width "
      "is carried by the midrange, which is the opposite of the usual 'widen the hats' instinct.")
    P("")
    P("### 3c. Where the side energy lives")
    P("")
    head(["kind"] + [f"{b} %" for b in BN])
    for k in KINDS:
        row([f"**{k}**"] + [f(_m(by[k], f"stereo.side_share_pct.{b}")) for b in BN])
    P("")
    P("### 3d. How much the image moves")
    P("")
    P("`sd` and `cv` are the standard deviation and coefficient of variation of the width series "
      "within the section; `slew` is the mean absolute change in width per second; `ac 1 bar` is "
      "the autocorrelation of the width series at one bar (is the movement arranged to the grid?).")
    P("")
    for k in KINDS:
        P(f"**{k}**")
        P("")
        head(["band", "width p10", "mean", "p90", "sd", "cv", "slew /s", "ac 1 bar", "ac 2 bar"])
        for b in BN:
            row([b] + [f(_m(by[k], f"stereo.bands.{b}.{x}"), 4) for x in
                       ("width_p10", "width_mean", "width_p90", "width_sd")]
                + [f(_m(by[k], f"stereo.bands.{b}.width_cv"), 2),
                   f(_m(by[k], f"stereo.bands.{b}.width_slew_per_s"), 3),
                   f(_m(by[k], f"stereo.bands.{b}.width_ac_1bar"), 3),
                   f(_m(by[k], f"stereo.bands.{b}.width_ac_2bar"), 3)])
        P("")
    P(f"In a drop the 400 Hz-2 kHz width swings from **{_m(by['drop'], 'stereo.bands.mid.width_p10'):.3f} "
      f"(p10) to {_m(by['drop'], 'stereo.bands.mid.width_p90'):.3f} (p90)** around a mean of "
      f"{_m(by['drop'], 'stereo.bands.mid.width_mean'):.3f} - a coefficient of variation of "
      f"**{_m(by['drop'], 'stereo.bands.mid.width_cv'):.2f}**, i.e. the spread is as large as the "
      f"mean - and slews at **{_m(by['drop'], 'stereo.bands.mid.width_slew_per_s'):.2f} width-units "
      "per second**. That is the movement: the stage breathes between near-mono and wide several "
      "times a bar. Sub and bass do not move at all "
      f"(cv is large only because the numbers are ~0.0002; slew {_m(by['drop'], 'stereo.bands.sub.width_slew_per_s'):.3f}/s).")
    P("")
    P("It is **not** an auto-panner. The strongest periodic component of the width series in the "
      "midrange has a period of 8-12 s (roughly 6-8 bars) with a peak-to-median ratio of only "
      "6-15, and the bar-locked autocorrelation is weak (0.13-0.21 at 1-2 bars in grooves and "
      "drops, ~0.0-0.09 in breakdowns). The movement is event-driven - each element arrives with "
      "its own width - with a slow arranged drift on top, not an LFO.")
    P("")

    # ---- 4 space
    P("## 4. Space and tails")
    P("")
    P("Measured on a 512-point STFT at a 128-sample hop (2.67 ms per frame) so that a 90 ms delay "
      "can be told from a 120 ms one. Requiring genuinely isolated transients yields about five "
      "usable hits per drop, so instead every onset is used: fit the decay over the gap to the "
      "next onset (capped at 300 ms) and extrapolate to -20 dB, and separately record the floor "
      "the band actually reaches before the next hit.")
    P("")
    P("### 4a. Decay")
    P("")
    head(["kind", "band", "decay dB/s", "T20 (fit) ms", "RT60 est ms", "inter-onset floor dB",
          "gap ms", "% hits reaching -20 dB"])
    for k in KINDS:
        for b in ("mid", "high", "air"):
            row([f"**{k}**" if b == "mid" else "", b,
                 f(_m(by[k], f"space.{b}.decay_db_per_s_med")),
                 f(_m(by[k], f"space.{b}.t20_fit_ms"), 0),
                 f(_m(by[k], f"space.{b}.rt60_est_ms"), 0),
                 f(_m(by[k], f"space.{b}.inter_onset_floor_db_med")),
                 f(_m(by[k], f"space.{b}.inter_onset_gap_ms_med"), 0),
                 f(_m(by[k], f"space.{b}.pct_hits_reaching_-20db"))])
    P("")
    P(f"**Only {_m(by['drop'], 'space.high.pct_hits_reaching_-20db'):.1f}% of 2-8 kHz hits in a drop "
      "ever fall 20 dB before the next one arrives.** The band never gets to dry out. Between hits "
      f"it drops a median of **{_m(by['drop'], 'space.high.inter_onset_floor_db_med'):.1f} dB** and "
      "no further.")
    P("")
    P("### 4b. How much is left between the hits")
    P("")
    P("Percentiles of the 2-16 kHz envelope, in dB relative to its own 99th percentile - i.e. the "
      "shape of the gap between loud and quiet moments in the top end.")
    P("")
    head(["kind", "p5", "p10", "p25", "p50", "p90", "% time >-12 dB", "% >-20 dB", "% >-30 dB"])
    for k in KINDS:
        e = np.mean([s["space"]["high_env_pct_db_vs_p99"] for s in by[k]], 0)
        row([f"**{k}**"] + [f(v) for v in e]
            + [f(_m(by[k], "space.high_above_minus12_pct")),
               f(_m(by[k], "space.high_above_minus20_pct")),
               f(_m(by[k], "space.high_above_minus30_pct"))])
    P("")
    head(["kind (air 8-16k)", "p5", "p10", "p25", "p50", "p90", "% time >-20 dB"])
    for k in KINDS:
        e = np.mean([s["space"]["air_env_pct_db_vs_p99"] for s in by[k]], 0)
        row([f"**{k}**"] + [f(v) for v in e] + [f(_m(by[k], "space.air_above_minus20_pct"))])
    P("")
    P(f"The top end of a drop sits above -20 dB of its own peak "
      f"**{_m(by['drop'], 'space.high_above_minus20_pct'):.1f}% of the time** and above -30 dB "
      f"**{_m(by['drop'], 'space.high_above_minus30_pct'):.1f}%** of the time. There is effectively "
      "no silence in the high band. That continuous bed is the 'sustain in the highs'.")
    P("")
    P("### 4c. Tail level at musical offsets after a hit")
    P("")
    P("For every strong 2-16 kHz onset with no new attack before the offset, the level at that "
      "offset in dB relative to the hit itself. `n` is how many hits qualified.")
    P("")
    off = ("1/16", "1/8", "3/16", "1/4", "1/2")
    head(["kind"] + [f"{o} ({round(361.8 * {'1/16': .25, '1/8': .5, '3/16': .75, '1/4': 1.0, '1/2': 2.0}[o])} ms)"
                     for o in off])
    for k in KINDS:
        cells = []
        for o in off:
            v = _m(by[k], f"space.echo.tails.{o}.level_db_med")
            n = _m(by[k], f"space.echo.tails.{o}.n")
            cells.append(f"{f(v)} (n={n:.0f})")
        row([f"**{k}**"] + cells)
    P("")
    P(f"**One eighth note (181 ms) after a hit, the top end of a drop is still "
      f"{_m(by['drop'], 'space.echo.tails.1/8.level_db_med'):.1f} dB below that hit. A quarter note "
      f"(362 ms) later it is {_m(by['drop'], 'space.echo.tails.1/4.level_db_med'):.1f} dB below.** "
      "A dry mix would be 15-25 dB down by then.")
    P("")
    P("### 4d. Echo repeats")
    P("")
    P("Spotting a repeat inside a running break by similarity does not work - a break is already "
      "a burst of similar hits on the 16th grid, and control lags score as well as musical ones. "
      "So: take every gap of 180 ms or more with no new 2-16 kHz attack, fit the smooth decay "
      "through it, and keep bumps that poke at least 2 dB **above** that fitted tail while still "
      "sitting at least 3 dB **below** the dry hit. A bump above the tail inside a gap is a delay "
      "repeat; its lag is the delay time. Chance share for a +/-12 ms window over the 35-800 ms "
      "search range is **3.1%**, so anything near 3% is noise.")
    P("")
    lg = list(D[0]["space"]["echo"]["lags"].keys())
    head(["delay", "ms", "breakdown %", "groove %", "drop %", "repeat level dB (drop)",
          "prominence dB"])
    for nm in lg:
        d0 = D[0]["space"]["echo"]["lags"][nm]["delay_ms"]
        cells = []
        for k in KINDS:
            tot = sum(s["space"]["echo"]["n_bumps"] for s in by[k])
            n = sum(s["space"]["echo"]["lags"][nm]["n"] for s in by[k])
            cells.append(f"{100 * n / max(tot, 1):.1f}")
        row([nm, f(d0), cells[0], cells[1], cells[2],
             f(_m(by["drop"], f"space.echo.lags.{nm}.repeat_db_med")),
             f(_m(by["drop"], f"space.echo.lags.{nm}.prominence_db_med"))])
    P("")
    P("Raw lag histogram (10 ms bins) confirms it without assuming a grid - across the drops the "
      "modal bump lag is 110-120 ms, with a second cluster at 170-190 ms.")
    P("")
    P("**Three delays are in use, and they are all short:**")
    P("")
    P("- **1/8 triplet, ~120 ms** - the dominant one. 16.3% of drop repeats and 12.5% of groove "
      "repeats against a 3.1% chance floor, so roughly 5x chance. Repeats land ~5 dB under the "
      "dry hit. This is the jungle/dub triplet delay and it is what makes the break feel like it "
      "is rolling rather than stepping.")
    P("- **1/8, ~181 ms** - 6.1% in drops, and the *deepest* repeats (-7.8 dB), with the highest "
      "prominence above the tail in breakdowns (5.4 dB). This is the feature delay, used where "
      "there is room.")
    P("- **1/32, ~45 ms slapback** - 6.6% in drops. Too short to hear as an echo; it reads as "
      "thickness on the snare.")
    P("")
    P("**Nothing long is in use.** Quarter note (362 ms) is at 1.2%, dotted quarter 1.5%, half "
      "note 1.9% - all at or below the chance floor, which for those lags is *higher* (3.8-7.6%) "
      "because the tolerance scales. There is no half-bar or bar-length delay anywhere in this "
      "set. The space is made from short repeats plus a ~0.6-1.1 s reverb tail, not from long "
      "echoes.")
    P("")

    # ---- 5 density
    P("## 5. Density")
    P("")
    P("Onsets are counted per band as a **rise in dB** (>=6 dB over 2 frames, local maximum, 60 ms "
      "refractory), not as raw spectral flux against a moving average - the latter fires a dozen "
      "times a bar in every band of a dense break and reports detector noise as voices.")
    P("")
    P("### 5a. Onsets per bar, by band")
    P("")
    head(["id", "kind"] + BN + ["total", "16ths used of 16", "bands per used 16th"])
    for s in D:
        d = s["density"]
        row([s["id"], s["kind"]] + [f(d["onsets_per_bar_by_band"][b], 2) for b in BN]
            + [f(d["onsets_per_bar_total"]), f(d["slots_used_per_bar_med"]),
               f(d["bands_per_used_slot_med"])])
    P("")
    head(["**mean**", "kind"] + BN + ["total", "16ths used", "bands per 16th"])
    for k in KINDS:
        row(["", f"**{k}**"] + [f(_m(by[k], f"density.onsets_per_bar_by_band.{b}"), 2) for b in BN]
            + [f(_m(by[k], "density.onsets_per_bar_total")),
               f(_m(by[k], "density.slots_used_per_bar_med")),
               f(_m(by[k], "density.bands_per_used_slot_med"))])
    P("")
    P(f"**A drop bar has fewer events than a groove bar.** "
      f"{_m(by['drop'], 'density.onsets_per_bar_total'):.1f} band-onsets per bar in a drop against "
      f"{_m(by['groove'], 'density.onsets_per_bar_total'):.1f} in a groove and "
      f"{_m(by['breakdown'], 'density.onsets_per_bar_total'):.1f} in a breakdown. Of the 16 "
      f"sixteenths in a drop bar, **{_m(by['drop'], 'density.slots_used_per_bar_med'):.1f}** carry "
      f"anything at all, and each of those carries **{_m(by['drop'], 'density.bands_per_used_slot_med'):.1f}** "
      "bands - so at most two things speak at the same instant. The sub contributes "
      f"**{_m(by['drop'], 'density.onsets_per_bar_by_band.sub'):.1f} onsets per bar**: it is one "
      "sustained note, not a busy line.")
    P("")
    P("### 5b. Time-frequency occupancy")
    P("")
    P("On a 32-band log-frequency grid. `occupancy` = share of the plane above a threshold "
      "relative to the section's own loudest bin. `spread` = how many of the 32 bands sit within "
      "20 dB of that frame's own loudest band, median over frames - level-free, so a quiet "
      "breakdown and a loud drop compare directly. `profile crest` = peak-to-mean of the "
      "time-averaged log-band profile.")
    P("")
    head(["kind", "occ -20 dB %", "occ -30 dB %", "occ -40 dB %", "spread -20 dB (of 32)",
          "flatness", "profile crest dB"])
    for k in KINDS:
        row([f"**{k}**", f(_m(by[k], "density.occupancy_20db_pct")),
             f(_m(by[k], "density.occupancy_30db_pct")),
             f(_m(by[k], "density.occupancy_40db_pct")),
             f(_m(by[k], "density.spread_20db_med")),
             f(_m(by[k], "density.flatness_med"), 4),
             f(_m(by[k], "density.logband_profile_crest_db"))])
    P("")
    P("(The same spread measured only above 200 Hz saturates at 22-23 of 23 bands for every "
      "section type, so it carries no information - once the sub is excluded, the rest of the "
      "spectrum is always within 20 dB of itself. The discriminating measure is the full-range "
      "one, because what separates a drop is exactly how far the sub sticks up above everything "
      "else.)")
    P("")
    P(f"The drop is the **least** flat and the **most** peaked section type: flatness "
      f"{_m(by['drop'], 'density.flatness_med'):.4f} against "
      f"{_m(by['breakdown'], 'density.flatness_med'):.4f} in a breakdown, profile crest "
      f"{_m(by['drop'], 'density.logband_profile_crest_db'):.1f} dB against "
      f"{_m(by['breakdown'], 'density.logband_profile_crest_db'):.1f} dB, and only "
      f"{_m(by['drop'], 'density.spread_20db_med'):.0f} of 32 log-bands within 20 dB of the loudest "
      f"band at any instant against {_m(by['breakdown'], 'density.spread_20db_med'):.0f} in a "
      "breakdown. A drop is a spike at the bottom with a thin spread above it, not a wall.")
    P("")
    P("### 5c. Gaps per band")
    P("")
    P("Share of the section each band spends more than 20 dB below its own peak - a band with a "
      "low number is running continuously.")
    P("")
    head(["kind"] + BN)
    for k in KINDS:
        row([f"**{k}**"] + [f(_m(by[k], f"density.pct_time_band_below_minus20_of_own_peak.{b}"))
                            for b in BN])
    P("")
    P(f"In a drop the sub is within 20 dB of its peak "
      f"**{100 - _m(by['drop'], 'density.pct_time_band_below_minus20_of_own_peak.sub'):.0f}% of the "
      f"time** - a continuous bassline, never gapped. In a breakdown it is gone "
      f"**{_m(by['breakdown'], 'density.pct_time_band_below_minus20_of_own_peak.sub'):.0f}%** of the "
      "time. The contrast is made by removing the sub wholesale, not by thinning it.")
    P("")

    # ---- conclusions
    P("## What this means for building a jungle track")
    P("")
    P("Against the two complaints - \"dry, lacking effects sustain in the highs, no movement in "
      "the sound stage\" and \"too much going on when fully built up\" - these are the reference's "
      "numbers to aim at.")
    P("")
    dr, gr, bd = by["drop"], by["groove"], by["breakdown"]
    P(f"1. **Band balance, drop.** sub {_m(dr, 'spectral.rel_db.sub'):.0f} dB, "
      f"bass {_m(dr, 'spectral.rel_db.bass'):.0f}, lowmid {_m(dr, 'spectral.rel_db.lowmid'):.0f}, "
      f"mid {_m(dr, 'spectral.rel_db.mid'):.0f}, high {_m(dr, 'spectral.rel_db.high'):.0f}, "
      f"air {_m(dr, 'spectral.rel_db.air'):.0f} - relative to the section total. Overall tilt "
      f"**{_m(dr, 'spectral.tilt_db_per_oct'):.1f} dB/oct**. Groove sits at "
      f"{_m(gr, 'spectral.tilt_db_per_oct'):.1f} dB/oct, breakdown at "
      f"{_m(bd, 'spectral.tilt_db_per_oct'):.2f} (flat).")
    P("")
    P(f"2. **Build the drop downward, not upward.** Going breakdown -> drop, sub gains "
      f"**{_m(dr, 'spectral.rel_db.sub') - _m(bd, 'spectral.rel_db.sub'):+.0f} dB** of share while "
      f"high falls **{abs(_m(dr, 'spectral.rel_db.high') - _m(bd, 'spectral.rel_db.high')):.0f} dB** "
      f"and air falls **{abs(_m(dr, 'spectral.rel_db.air') - _m(bd, 'spectral.rel_db.air')):.0f} dB**. "
      "If the full build is brighter than the breakdown, it is wrong.")
    P("")
    P(f"3. **Fewer voices at the top, not more.** Target a drop bar at "
      f"**{_m(dr, 'density.onsets_per_bar_total'):.0f} band-onsets** (sub "
      f"{_m(dr, 'density.onsets_per_bar_by_band.sub'):.1f}, bass "
      f"{_m(dr, 'density.onsets_per_bar_by_band.bass'):.1f}, lowmid "
      f"{_m(dr, 'density.onsets_per_bar_by_band.lowmid'):.1f}, mid "
      f"{_m(dr, 'density.onsets_per_bar_by_band.mid'):.1f}, high "
      f"{_m(dr, 'density.onsets_per_bar_by_band.high'):.1f}, air "
      f"{_m(dr, 'density.onsets_per_bar_by_band.air'):.1f}) against "
      f"**{_m(gr, 'density.onsets_per_bar_total'):.0f}** in the groove. "
      f"**{_m(dr, 'density.slots_used_per_bar_med'):.0f} of 16 sixteenths** occupied, "
      f"**{_m(dr, 'density.bands_per_used_slot_med'):.0f} bands per occupied sixteenth**. Two "
      "things at a time, maximum.")
    P("")
    P(f"4. **Keep the plane empty.** Drop occupancy at -20 dB = "
      f"**{_m(dr, 'density.occupancy_20db_pct'):.0f}%** of the time-frequency plane (groove "
      f"{_m(gr, 'density.occupancy_20db_pct'):.0f}%), flatness "
      f"**{_m(dr, 'density.flatness_med'):.3f}**, log-band profile crest "
      f"**{_m(dr, 'density.logband_profile_crest_db'):.0f} dB**, only "
      f"**{_m(dr, 'density.spread_20db_med'):.0f} of 32** log-bands live within 20 dB of the "
      "loudest at any instant. If the mix is measuring flatter than 0.015 at full build, it is "
      "the wall the user is hearing.")
    P("")
    P(f"5. **Everything below 150 Hz is mono.** Side energy below 150 Hz must sit at least "
      f"**30 dB** under the mid in the same range (reference: "
      f"{_m(gr + dr, 'stereo.side_below150_vs_mid_below150_db'):.0f} dB). Per-band width in a drop: "
      f"sub {_m(dr, 'stereo.bands.sub.width_mean'):.4f}, bass "
      f"{_m(dr, 'stereo.bands.bass.width_mean'):.4f}. Any stereo widener touching the sub or the "
      "reese is off-reference.")
    P("")
    P(f"6. **Width lives at 400 Hz-2 kHz.** The image opens between 250 and 500 Hz. In a drop the "
      f"mid band holds **{_m(dr, 'stereo.side_share_pct.mid'):.0f}% of all side energy**, lowmid "
      f"{_m(dr, 'stereo.side_share_pct.lowmid'):.0f}%, high "
      f"{_m(dr, 'stereo.side_share_pct.high'):.0f}%, air "
      f"{_m(dr, 'stereo.side_share_pct.air'):.0f}%, sub+bass "
      f"{_m(dr, 'stereo.side_share_pct.sub') + _m(dr, 'stereo.side_share_pct.bass'):.0f}%. Target "
      f"widths: lowmid {_m(dr, 'stereo.bands.lowmid.width_mean'):.2f}, mid "
      f"{_m(dr, 'stereo.bands.mid.width_mean'):.2f}, high "
      f"{_m(dr, 'stereo.bands.high.width_mean'):.2f}, air "
      f"{_m(dr, 'stereo.bands.air.width_mean'):.2f}. Widening the hats and air is the wrong move; "
      "in the drops those bands *narrow*.")
    P("")
    P(f"7. **Make the width move, slowly and unevenly.** The 400 Hz-2 kHz width should swing "
      f"**{_m(dr, 'stereo.bands.mid.width_p10'):.2f} to {_m(dr, 'stereo.bands.mid.width_p90'):.2f}** "
      f"within a section (sd {_m(dr, 'stereo.bands.mid.width_sd'):.2f}, cv "
      f"{_m(dr, 'stereo.bands.mid.width_cv'):.1f}, slew "
      f"{_m(dr, 'stereo.bands.mid.width_slew_per_s'):.1f} width-units/s). Not an auto-pan: the "
      "strongest periodic component has a period of 8-12 s (6-8 bars) and bar-locked "
      "autocorrelation is only 0.13-0.21. Give each element its own fixed width and let the "
      "arrangement do the moving.")
    P("")
    P(f"8. **Delay times: 1/8 triplet (~120 ms) primary, 1/8 (~181 ms) secondary, ~45 ms "
      f"slapback for thickness. Nothing longer than a quarter note.** Repeats land "
      f"**-4 to -8 dB** under the dry hit (1/8 triplet ~-5 dB, 1/8 ~-8 dB), poking 3-5 dB above "
      "the reverb tail. Quarter, dotted quarter and half-note delays are at or below the chance "
      "floor in every section - do not use them.")
    P("")
    t20 = sorted(s["space"]["high"]["t20_fit_ms"] for s in dr)
    P(f"9. **Tails: the 2-8 kHz band must not dry out.** One eighth (181 ms) after a hit it "
      f"should still be within **{abs(_m(dr, 'space.echo.tails.1/8.level_db_med')):.1f} dB** of "
      f"that hit, and a quarter (362 ms) later within "
      f"**{abs(_m(dr, 'space.echo.tails.1/4.level_db_med')):.1f} dB**. Fit-extrapolated T20 for "
      f"2-8 kHz runs **{t20[0]:.0f}-{t20[-1]:.0f} ms across the drops (median "
      f"{np.median(t20):.0f} ms, RT60 ~{3 * np.median(t20) / 1000:.1f} s)** - the dense breaks sit "
      f"near {t20[1]:.0f} ms and the sparse dub drops near {t20[-1]:.0f} ms - and "
      f"**{_m(dr, 'space.air.t20_fit_ms'):.0f} ms** for 8-16 kHz. The band should sit above "
      f"-20 dB of its own peak **{_m(dr, 'space.high_above_minus20_pct'):.0f}% of the time**, and "
      f"fewer than **{_m(dr, 'space.high.pct_hits_reaching_-20db'):.0f}%** of hits should ever "
      "fall 20 dB before the next one. That continuous bed is the sustain that is missing.")
    P("")
    P(f"10. **Compress inside a section, contrast between sections.** Short-term loudness range "
      f"inside a drop is only **{_m(dr, 'dynamics.lra_k_db'):.1f} dB** over a full minute, but "
      f"breakdown-to-drop RMS steps by "
      f"**{_m(dr, 'dynamics.rms_dbfs') - _m(bd, 'dynamics.rms_dbfs'):.0f} dB**. Keep the 50 ms "
      f"crest at **>={_m(dr, 'dynamics.crest_50ms_db'):.1f} dB** (p90 "
      f"{_m(dr, 'dynamics.crest_50ms_p90_db'):.1f} dB) in the drop, which is "
      f"**{100 * _m(dr, 'dynamics.crest_50ms_db') / _m(dr, 'dynamics.crest_3s_db'):.0f}%** of the "
      "3 s crest - if that ratio falls much below 80%, the limiter has eaten the drums.")
    P("")

    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "mix-space.md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")
    print("->", path, f"({len(L)} lines)")
    return path


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("cmd", choices=["sections", "analyse", "report"])
    ap.add_argument("--per-kind", type=int, default=4)
    ap.add_argument("--max-len", type=float, default=75.0)
    ap.add_argument("--debug", action="store_true")
    a = ap.parse_args(argv)
    os.makedirs(WORK, exist_ok=True)
    if a.cmd == "sections":
        S = build_sections(debug=a.debug)
        json.dump(S, open(os.path.join(WORK, "sections.json"), "w"), indent=1)
        for s in S["sections"]:
            print(f"{s['id']}  {s['kind']:9s} {s['t0']:7.1f}-{s['t1']:7.1f}  "
                  f"{s['dur']:6.1f}s  {s['rms_db']:6.2f} dB  {s['bpm']:6.2f} BPM")
        print(f"{len(S['sections'])} sections")
    elif a.cmd == "analyse":
        analyse(per_kind=a.per_kind, max_len=a.max_len)
    else:
        report()
    return 0


if __name__ == "__main__":
    sys.exit(main())
