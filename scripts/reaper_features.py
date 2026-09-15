"""REAPER FEATURES - one pass over the reference DJ-set wav, cached for the analysis agents.

The reference is STRUCTURAL SOURCE MATERIAL ONLY (the user's rule): nothing is ever sampled, lifted
or reused from it. What comes out of here is numbers about arrangement, rhythm and balance.

This box has numpy and torch and nothing else - no librosa, scipy or soundfile - so everything is
built here: a small RIFF reader, a torch STFT, spectral-flux onsets, an autocorrelation tempo
estimate, a beat phase and bar grid, and per-bar / per-16th aggregates.

Outputs (into the cache dir, default <wav dir>/reaper_cache):
  frames.npz   frame-rate features (~86 fps): t, rms, band energies, flux, centroid, width, crest
  bars.npz     per-bar: rms, bands, onset count, crest, width, centroid, plus
               grid16 (bars x 16 x 3 bands) onset strength, offs16 (bars x 16) microtiming in ms
  meta.json    sample rate, duration, bpm, beat/bar times, grid confidence, band edges

    python scripts/reaper_features.py                     # build the cache
    python scripts/reaper_features.py --summary           # print what is in it

Reading it back:
    import numpy as np, json
    f = np.load(CACHE + "/frames.npz"); b = np.load(CACHE + "/bars.npz")
    meta = json.load(open(CACHE + "/meta.json"))
"""
from __future__ import annotations

import argparse
import json
import os
import struct
import sys

import numpy as np
import torch

WAV = r"C:\Users\eric\Downloads\Tim_Reaper_Jungle_DJ_Set_SECTION_August_2026.wav"
N_FFT = 2048
HOP = 512
BANDS = {"sub": (20, 60), "bass": (60, 120), "lowmid": (120, 400), "mid": (400, 2000),
         "high": (2000, 8000), "air": (8000, 16000)}
BPM_RANGE = (150.0, 190.0)


# ----------------------------------------------------------------------
# WAV (no soundfile here: parse the RIFF chunks directly)
# ----------------------------------------------------------------------
def read_wav(path: str) -> tuple[np.ndarray, int]:
    """-> (samples [n, channels] float32 in -1..1, sample rate). PCM 8/16/24/32 and float 32/64."""
    with open(path, "rb") as fh:
        raw = fh.read()
    if raw[:4] != b"RIFF" or raw[8:12] != b"WAVE":
        raise ValueError("not a RIFF/WAVE file")
    pos, fmt, data = 12, None, None
    while pos + 8 <= len(raw):
        cid, size = raw[pos:pos + 4], struct.unpack("<I", raw[pos + 4:pos + 8])[0]
        body = raw[pos + 8:pos + 8 + size]
        if cid == b"fmt ":
            fmt = struct.unpack("<HHIIHH", body[:16])
        elif cid == b"data":
            data = body
        pos += 8 + size + (size & 1)
    if fmt is None or data is None:
        raise ValueError("missing fmt or data chunk")
    tag, ch, sr, _, _, bits = fmt
    if tag == 0xFFFE:                       # WAVE_FORMAT_EXTENSIBLE: the real tag is in the GUID
        tag = 3 if bits == 32 and b"\x03\x00" in raw[:200] else 1
    if tag == 1 and bits == 16:
        x = np.frombuffer(data, "<i2").astype(np.float32) / 32768.0
    elif tag == 1 and bits == 24:
        b = np.frombuffer(data, np.uint8).reshape(-1, 3).astype(np.int32)
        v = (b[:, 0] | (b[:, 1] << 8) | (b[:, 2] << 16))
        v = np.where(v & 0x800000, v - 0x1000000, v)
        x = v.astype(np.float32) / 8388608.0
    elif tag == 1 and bits == 32:
        x = np.frombuffer(data, "<i4").astype(np.float32) / 2147483648.0
    elif tag == 1 and bits == 8:
        x = (np.frombuffer(data, np.uint8).astype(np.float32) - 128.0) / 128.0
    elif tag == 3 and bits == 32:
        x = np.frombuffer(data, "<f4").astype(np.float32)
    elif tag == 3 and bits == 64:
        x = np.frombuffer(data, "<f8").astype(np.float32)
    else:
        raise ValueError(f"unsupported format tag {tag} / {bits} bits")
    return x.reshape(-1, ch), sr


# ----------------------------------------------------------------------
# Frame features
# ----------------------------------------------------------------------
def frame_features(x: np.ndarray, sr: int) -> dict:
    mid = x.mean(axis=1)
    side = (x[:, 0] - x[:, 1]) / 2 if x.shape[1] > 1 else np.zeros_like(mid)
    win = torch.hann_window(N_FFT)
    spec = {}
    for name, sig in (("mid", mid), ("side", side)):
        S = torch.stft(torch.from_numpy(np.ascontiguousarray(sig)), N_FFT, HOP, window=win,
                       center=True, return_complex=True).abs().numpy()
        spec[name] = S
    S = spec["mid"]
    freqs = np.fft.rfftfreq(N_FFT, 1 / sr)
    n = S.shape[1]
    out = {"t": np.arange(n) * HOP / sr}

    for name, (lo, hi) in BANDS.items():
        sel = (freqs >= lo) & (freqs < hi)
        out[name] = S[sel].sum(axis=0)
        out["flux_" + name] = np.concatenate([[0.0], np.maximum(0.0, np.diff(out[name]))])
    out["flux"] = np.concatenate([[0.0], np.maximum(0.0, np.diff(S, axis=1)).sum(axis=0)])
    out["centroid"] = (S * freqs[:, None]).sum(axis=0) / np.maximum(S.sum(axis=0), 1e-9)
    out["width"] = spec["side"].sum(axis=0) / np.maximum(S.sum(axis=0) + spec["side"].sum(axis=0), 1e-9)

    # time-domain RMS and crest per HOP block (cumulative sums and reduceat: a sliding window over a
    # ten-minute file would allocate hundreds of MB)
    edges = np.minimum(np.arange(n) * HOP, len(mid) - 1)
    csum = np.concatenate([[0.0], np.cumsum(mid.astype(np.float64) ** 2)])
    hi = np.minimum(edges + HOP, len(mid))
    out["rms"] = np.sqrt((csum[hi] - csum[edges]) / np.maximum(hi - edges, 1)).astype(np.float32)
    out["peak"] = np.maximum.reduceat(np.abs(mid), edges)[:n]
    out["crest"] = out["peak"] / np.maximum(out["rms"], 1e-9)
    return out


# ----------------------------------------------------------------------
# Tempo, beats, bars
# ----------------------------------------------------------------------
def tempo_and_grid(env: np.ndarray, sr: int, hop: int = HOP) -> dict:
    """Autocorrelation tempo over BPM_RANGE, then the beat phase that best explains the onsets, then
    the bar phase that puts the most low-end weight on beat 1."""
    e = env - env.mean()
    ac = np.correlate(e, e, mode="full")[len(e) - 1:]
    fps = sr / hop
    lags = np.arange(len(ac))
    with np.errstate(divide="ignore"):
        bpm = 60.0 * fps / np.maximum(lags, 1e-9)
    ok = (bpm >= BPM_RANGE[0]) & (bpm <= BPM_RANGE[1])
    lag = int(lags[ok][np.argmax(ac[ok])])
    best_bpm = 60.0 * fps / lag

    # refine: try lags around the peak at sub-sample resolution via parabolic interpolation
    if 1 <= lag < len(ac) - 1:
        y0, y1, y2 = ac[lag - 1], ac[lag], ac[lag + 1]
        denom = (y0 - 2 * y1 + y2)
        if denom != 0:
            lag_f = lag + 0.5 * (y0 - y2) / denom
            best_bpm = 60.0 * fps / lag_f
    beat_frames = 60.0 * fps / best_bpm

    # beat phase: comb over one beat, scoring the onset envelope at every beat position
    scores = []
    for phase in np.arange(0, beat_frames, 0.25):
        pos = np.arange(phase, len(env) - 1, beat_frames)
        scores.append(np.interp(pos, np.arange(len(env)), env).sum())
    phase = float(np.arange(0, beat_frames, 0.25)[int(np.argmax(scores))])
    beats = np.arange(phase, len(env) - 1, beat_frames)
    conf = float(max(scores) / (np.mean(scores) + 1e-9))
    return {"bpm": float(best_bpm), "beat_frames": float(beat_frames), "phase": phase,
            "beats": beats, "beat_confidence": conf}


def bar_phase(beats: np.ndarray, low: np.ndarray) -> int:
    """Which of the four beats carries the most low end: that one is beat 1."""
    w = np.interp(beats, np.arange(len(low)), low)
    return int(np.argmax([w[k::4].mean() for k in range(4)]))


# ----------------------------------------------------------------------
# Per-bar aggregation
# ----------------------------------------------------------------------
def bar_features(f: dict, sr: int, grid: dict, first_beat: int) -> dict:
    beats, bf = grid["beats"], grid["beat_frames"]
    starts = beats[first_beat::4]
    n_bars = len(starts) - 1
    cols = ["rms", "crest", "centroid", "width"] + list(BANDS)
    out = {c: np.zeros(n_bars, np.float32) for c in cols}
    out["onsets"] = np.zeros(n_bars, np.float32)
    grid16 = np.zeros((n_bars, 16, 3), np.float32)
    offs16 = np.zeros((n_bars, 16), np.float32)

    flux = f["flux"]
    peaks = onset_peaks(flux)
    bands3 = [f["sub"] + f["bass"], f["lowmid"] + f["mid"], f["high"] + f["air"]]
    flux3 = [f["flux_sub"] + f["flux_bass"], f["flux_lowmid"] + f["flux_mid"], f["flux_high"] + f["flux_air"]]
    for b in range(n_bars):
        a, z = starts[b], starts[b + 1]
        sl = slice(int(round(a)), max(int(round(a)) + 1, int(round(z))))
        for c in cols:
            out[c][b] = f[c][sl].mean()
        inside = peaks[(peaks >= a) & (peaks < z)]
        out["onsets"][b] = len(inside)
        step = (z - a) / 16.0
        for k in range(16):
            centre = a + k * step
            near = inside[np.abs(inside - centre) <= step * 0.5]
            if len(near):
                j = int(round(near[np.argmin(np.abs(near - centre))]))
                offs16[b, k] = (j - centre) * HOP / sr * 1000.0        # ms early(-) / late(+)
                for i in range(3):
                    grid16[b, k, i] = flux3[i][j]
            else:
                offs16[b, k] = np.nan
    out["grid16"] = grid16
    out["offs16"] = offs16
    out["bar_start_s"] = (starts[:-1] * HOP / sr).astype(np.float32)
    for i, name in enumerate(("low", "mid", "high")):
        out["e_" + name] = np.array([bands3[i][slice(int(round(starts[b])), int(round(starts[b + 1])))].mean()
                                     for b in range(n_bars)], np.float32)
    return out


def onset_peaks(flux: np.ndarray, pre: int = 3, post: int = 3, delta_mult: float = 1.3) -> np.ndarray:
    """Frame indices where the flux is a local max and above a moving average * delta_mult."""
    n = len(flux)
    k = 43                                     # ~0.5 s moving average
    kernel = np.ones(k) / k
    avg = np.convolve(flux, kernel, mode="same")
    out = []
    for i in range(pre, n - post):
        seg = flux[i - pre:i + post + 1]
        if flux[i] == seg.max() and flux[i] > avg[i] * delta_mult and flux[i] > 0:
            out.append(i)
    return np.array(out, np.float32)


# ----------------------------------------------------------------------
def build(wav: str, cache: str):
    x, sr = read_wav(wav)
    dur = len(x) / sr
    print(f"{os.path.basename(wav)}: {dur:.1f} s, {sr} Hz, {x.shape[1]} ch")
    f = frame_features(x, sr)
    print(f"frames: {len(f['t'])} at {sr / HOP:.1f} fps")
    env = f["flux"] / (np.max(f["flux"]) or 1.0)
    grid = tempo_and_grid(env, sr)
    first = bar_phase(grid["beats"], f["sub"] + f["bass"])
    print(f"tempo {grid['bpm']:.2f} BPM, beat confidence {grid['beat_confidence']:.1f}, "
          f"downbeat = beat {first} of the first four")
    bars = bar_features(f, sr, grid, first)
    n_bars = len(bars["rms"])
    print(f"bars: {n_bars} ({n_bars / 4:.1f} four-bar phrases, {n_bars / 8:.1f} eight-bar)")

    os.makedirs(cache, exist_ok=True)
    np.savez_compressed(os.path.join(cache, "frames.npz"), **{k: v.astype(np.float32) for k, v in f.items()})
    np.savez_compressed(os.path.join(cache, "bars.npz"), **bars)
    meta = {"wav": wav, "sr": sr, "duration_s": dur, "channels": int(x.shape[1]),
            "n_fft": N_FFT, "hop": HOP, "fps": sr / HOP, "bands": BANDS,
            "bpm": grid["bpm"], "beat_frames": grid["beat_frames"], "beat_phase": grid["phase"],
            "beat_confidence": grid["beat_confidence"], "downbeat_of_first_four": first,
            "n_bars": int(n_bars), "bar_len_s": grid["beat_frames"] * 4 * HOP / sr,
            "beats_s": (grid["beats"] * HOP / sr).round(4).tolist()}
    with open(os.path.join(cache, "meta.json"), "w") as fh:
        json.dump(meta, fh, indent=1)
    print(f"cache -> {cache}")
    return meta


def summary(cache: str):
    meta = json.load(open(os.path.join(cache, "meta.json")))
    bars = np.load(os.path.join(cache, "bars.npz"))
    print(json.dumps({k: v for k, v in meta.items() if k != "beats_s"}, indent=1))
    print("bars.npz:", {k: bars[k].shape for k in bars.files})
    rms = bars["rms"]
    loud = np.argsort(rms)[-5:][::-1]
    print("loudest bars:", [(int(b), round(float(rms[b]), 4)) for b in loud])


def main(argv=None):
    ap = argparse.ArgumentParser(description="Cache features of the reference DJ set for analysis.")
    ap.add_argument("--wav", default=WAV)
    ap.add_argument("--cache", default=None)
    ap.add_argument("--summary", action="store_true")
    a = ap.parse_args(argv)
    cache = a.cache or os.path.join(os.path.dirname(a.wav), "reaper_cache")
    if a.summary:
        summary(cache)
    else:
        build(a.wav, cache)
    return 0


if __name__ == "__main__":
    sys.exit(main())
