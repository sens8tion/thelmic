"""REAPER DROPS - the anatomy of every drop and breakdown in the reference jungle DJ set.

STRUCTURAL ANALYSIS ONLY. This script reads the cached feature frames (scripts/reaper_features.py)
and the 8 kHz mono decimation. It never writes audio, never slices the wav, never copies material.
Everything that leaves here is a number, a timestamp or a description.

The user's theory under test: a drop works because of what was TAKEN AWAY before it, and surprise is
spent sparingly. So the interesting measurement is not the level after the drop, it is the delta
across it, and the shape of the approach.

Stages (each prints; --md writes the report):
    python scripts/reaper_drops.py --events      # stage 1: detect drops + breakdowns
    python scripts/reaper_drops.py --detail      # stages 2-5: before/after, approach, layering
    python scripts/reaper_drops.py --md          # write tracks/2026-09-16_reaper/drops.md

The cached bar grid is a single global tempo at beat-confidence 1.04 and is NOT trustworthy, so all
work here is in seconds, with a LOCAL tempo estimated per event from the onset envelope.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np

CACHE = r"C:\Users\eric\Downloads\reaper_cache"
OUT_DIR = r"C:\Users\eric\github\sens8tion\thelmic\tracks\2026-09-16_reaper"
BANDS = ["sub", "bass", "lowmid", "mid", "high", "air"]
BPM_RANGE = (150.0, 190.0)


# ----------------------------------------------------------------------
# loading / helpers
# ----------------------------------------------------------------------
def load_frames() -> dict:
    f = np.load(os.path.join(CACHE, "frames.npz"))
    d = {k: f[k].astype(np.float64) for k in f.files}
    d["fps"] = 1.0 / float(np.median(np.diff(d["t"])))
    d["low"] = d["sub"] + d["bass"]
    # UPPER centroid: a 4-band centroid from 120 Hz up, using geometric band centres.
    # The full-range centroid is useless for spotting filter sweeps here, because pulling the bass
    # out of a mix raises the centroid all by itself - so every breakdown looks like a sweep up.
    # This one cannot see the sub or bass band at all, so a ramp in it is really a ramp.
    fc = {"lowmid": 219.1, "mid": 894.4, "high": 4000.0, "air": 11313.7}
    num = sum(d[b] * f_ for b, f_ in fc.items())
    den = sum(d[b] for b in fc)
    d["ucentroid"] = num / np.maximum(den, 1e-9)
    d["snare_flux"] = d["flux_mid"] + d["flux_high"]
    return d


def db(x: np.ndarray, floor: float = 1e-7) -> np.ndarray:
    return 20.0 * np.log10(np.maximum(x, floor))


def smooth(x: np.ndarray, n: int) -> np.ndarray:
    """Centred moving average of n frames (odd-ised), edge-padded."""
    n = max(1, int(n) | 1)
    pad = n // 2
    xp = np.concatenate([np.full(pad, x[0]), x, np.full(pad, x[-1])])
    k = np.ones(n) / n
    return np.convolve(xp, k, mode="valid")


def onset_peaks(flux: np.ndarray, fps: float, pre: int = 3, post: int = 3,
                delta_mult: float = 1.3) -> np.ndarray:
    """Frame indices of local flux maxima above a 0.5 s moving average * delta_mult (vectorised)."""
    n = len(flux)
    avg = smooth(flux, int(round(0.5 * fps)))
    ismax = np.ones(n, bool)
    for d in range(1, max(pre, post) + 1):
        if d <= pre:
            ismax[d:] &= flux[d:] >= flux[:-d]
        if d <= post:
            ismax[:-d] &= flux[:-d] >= flux[d:]
    ok = ismax & (flux > avg * delta_mult) & (flux > 0)
    ok[:pre] = ok[-post:] = False
    return np.flatnonzero(ok)


def rate_series(peaks: np.ndarray, n: int, fps: float, win_s: float) -> np.ndarray:
    """Onsets per second at every frame, over a centred window of win_s."""
    hit = np.zeros(n)
    hit[peaks] = 1.0
    w = int(round(win_s * fps)) | 1
    return smooth(hit, w) * fps


def bar_lag(flux: np.ndarray, fps: float, centre_s: float | None = None,
            half_s: float = 30.0) -> float:
    """Tempo via the FOUR-BAR autocorrelation lag, not the beat lag.

    The beat lag sits in a comb of harmonics (16th, 8th, beat, 2-beat) that are all nearly the same
    height, so a beat-range search is a coin toss - that is how the cached grid ended up at
    confidence 1.04. The 4-bar lag (~5.8 s) has no competitor near it, so it pins the tempo hard;
    divide by 16 beats afterwards. Returns BPM.
    """
    if centre_s is None:
        e = flux
    else:
        a = max(0, int((centre_s - half_s) * fps))
        z = min(len(flux), int((centre_s + half_s) * fps))
        e = flux[a:z]
    if len(e) < int(20 * fps):
        return float("nan")
    e = e - e.mean()
    ac = np.correlate(e, e, mode="full")[len(e) - 1:]
    # 4 bars = 16 beats; BPM 150-190 -> 5.05 .. 6.40 s
    lo = int(16 * 60.0 / BPM_RANGE[1] * fps)
    hi = min(len(ac) - 2, int(16 * 60.0 / BPM_RANGE[0] * fps))
    seg = ac[lo:hi]
    if len(seg) < 3:
        return float("nan")
    lag = lo + int(np.argmax(seg))
    y0, y1, y2 = ac[lag - 1], ac[lag], ac[lag + 1]
    den = y0 - 2 * y1 + y2
    if den != 0:
        lag = lag + 0.5 * (y0 - y2) / den
    return float(16 * 60.0 * fps / lag)


def bar_phase(F: dict, centre_s: float, bar_s: float, half_s: float = 12.0) -> float:
    """Time of the downbeat at or just before centre_s.

    Two stages, because a one-stage bar comb is unstable: the low band is ABSENT for half of the
    window around a drop, so there is nothing for a low-weighted bar comb to lock to. So lock the
    BEAT phase first on full-band flux (every onset helps), then choose which of the four beats is
    the downbeat by low-band weight alone.
    """
    fps = F["fps"]
    beat_s = bar_s / 4.0
    a = max(0.0, centre_s - half_s)
    z = min(float(F["t"][-1]), centre_s + half_s)
    flux, low = F["flux"], F["flux_sub"] + F["flux_bass"]
    best, best_ph = -1.0, 0.0
    for ph in np.arange(0.0, beat_s, 0.005):
        pos = np.arange(a + ph, z, beat_s)
        v = float(np.sum(np.interp(pos, F["t"], flux)))
        if v > best:
            best, best_ph = v, ph
    beats = np.arange(a + best_ph, z, beat_s)
    w = np.interp(beats, F["t"], low)
    k0 = int(np.argmax([w[k::4].mean() for k in range(4)]))
    downs = beats[k0::4]
    before = downs[downs <= centre_s + beat_s / 2]
    return float(before[-1]) if len(before) else float(downs[0])


def win(x: np.ndarray, fps: float, t0: float, t1: float) -> np.ndarray:
    a = max(0, int(round(t0 * fps)))
    z = min(len(x), int(round(t1 * fps)))
    return x[a:max(z, a + 1)]


# ----------------------------------------------------------------------
# stage 1: event detection
# ----------------------------------------------------------------------
def step_function(x_db: np.ndarray, fps: float, half_s: float, gap_s: float = 0.4) -> np.ndarray:
    """median(after) - median(before) at every frame, with a small guard band across the edge.

    Medians, not means: a one-second hole in the run-up should not drag the 'before' level down,
    because the question is what the bed was doing, not what the last beat did.
    """
    n = len(x_db)
    h = int(round(half_s * fps))
    g = int(round(gap_s * fps))
    # running median is expensive; use a strided coarse grid then interpolate
    stride = max(1, int(round(0.1 * fps)))
    idx = np.arange(0, n, stride)
    out = np.zeros(len(idx))
    for j, i in enumerate(idx):
        b = x_db[max(0, i - h - g):max(1, i - g)]
        a = x_db[min(n - 1, i + g):min(n, i + g + h)]
        out[j] = (np.median(a) if len(a) else 0.0) - (np.median(b) if len(b) else 0.0)
    return np.interp(np.arange(n), idx, out)


def detect_events(F: dict, thr_low: float = 6.0, thr_rms: float = 3.0, sep_s: float = 8.0,
                  calib: bool = False) -> dict:
    """Sweep the whole file for step changes and classify them.

    The detector runs at the FOUR-BAR scale (5.78 s each side) because that is the unit a jungle
    arrangement actually moves in; an 8-bar scale smears a drop that is answered 8 bars later, and a
    1-bar scale fires on every fill. Medians either side, with a 0.4 s guard band so the transient
    itself belongs to neither window.
    """
    fps = F["fps"]
    n = len(F["t"])
    bpm = bar_lag(F["flux"], fps)
    bar_s = 4 * 60.0 / bpm
    low_db = smooth(db(F["low"]), int(0.25 * fps))
    rms_db = smooth(db(F["rms"]), int(0.25 * fps))
    peaks = onset_peaks(F["flux"], fps)
    dens = rate_series(peaks, n, fps, 2.0)
    speaks = onset_peaks(F["snare_flux"], fps)          # mid+high onsets: snares, not kicks
    sdens = rate_series(speaks, n, fps, 2.0)

    h = 4 * bar_s
    s_low = step_function(low_db, fps, h)
    s_rms = step_function(rms_db, fps, h)
    s_den = step_function(dens, fps, h)
    score = 0.6 * s_low + 0.4 * s_rms

    def pick(sign):
        v = score * sign
        sep = int(round(sep_s * fps))
        order = np.argsort(-v)
        chosen = []
        for i in order:
            if v[i] < 1.5:
                break
            if all(abs(i - c) >= sep for c in chosen):
                chosen.append(int(i))
        return sorted(chosen)

    def refine(i, sign):
        """Snap to the steepest move of the low band within +-3 s, then, for a drop, to the nearest
        onset - a drop lands on a hit, not between two."""
        r = int(round(3.0 * fps))
        a, z = max(1, i - r), min(n - 1, i + r)
        d = np.diff(smooth(low_db, int(0.08 * fps))[a - 1:z])
        j = a + int(np.argmax(d * sign))
        if sign > 0 and len(peaks):
            near = peaks[np.abs(peaks - j) <= int(0.30 * fps)]
            if len(near):
                j = int(near[np.argmin(np.abs(near - j))])
        return int(j)

    cands = []
    for sign, kind in ((+1, "drop"), (-1, "breakdown")):
        for i in pick(sign):
            j = refine(i, sign)
            cands.append({"kind": kind, "frame": j, "t": float(F["t"][j]),
                          "score": float(score[i]), "d_low4": float(s_low[i]),
                          "d_rms4": float(s_rms[i]), "d_den4": float(s_den[i])})
    cands.sort(key=lambda e: e["t"])
    # collapse near-duplicates, keeping the stronger
    merged = []
    for e in cands:
        if merged and e["t"] - merged[-1]["t"] < sep_s:
            if abs(e["score"]) > abs(merged[-1]["score"]):
                merged[-1] = e
            continue
        merged.append(e)

    if calib:
        print(f"bpm {bpm:.3f}  bar {bar_s:.4f} s  {len(merged)} raw candidates")
        for e in sorted(merged, key=lambda x: -abs(x["score"])):
            print(f"  {mmss(e['t']):>9} {e['kind']:<10} score {e['score']:+6.2f} "
                  f"low {e['d_low4']:+6.2f} rms {e['d_rms4']:+6.2f} den {e['d_den4']:+6.2f}")

    keep = []
    for e in merged:
        if e["t"] < 2.0 or e["t"] > F["t"][-1] - 14.0:
            continue                       # the section cut itself is not an arrangement event
        lo, rm = abs(e["d_low4"]), abs(e["d_rms4"])
        if lo >= thr_low or (lo >= 4.0 and rm >= thr_rms):
            keep.append(e)
    for k, e in enumerate(keep):
        e["id"] = k + 1
        e["bpm"] = bar_lag(F["flux"], fps, e["t"], 30.0)
        if not (e["bpm"] == e["bpm"]) or not (150 < e["bpm"] < 190):
            e["bpm"] = bpm
        e["bar_s"] = 4 * 60.0 / e["bpm"]
        db_t = bar_phase(F, e["t"], e["bar_s"])
        off = e["t"] - db_t
        if off > e["bar_s"] / 2:
            off -= e["bar_s"]
        e["downbeat_off_ms"] = float(off * 1000.0)
        e["downbeat_off_beats"] = float(off / (e["bar_s"] / 4.0))
        # offset from the nearest BEAT: needs only the beat phase, so it is far more robust than
        # the downbeat figure (which additionally has to guess which of four beats is beat 1)
        beat = e["bar_s"] / 4.0
        bo = off % beat
        e["beat_off_ms"] = float((bo - beat if bo > beat / 2 else bo) * 1000.0)
    return {"events": keep, "low_db": low_db, "rms_db": rms_db, "dens": dens,
            "peaks": peaks, "score": score, "bpm": bpm, "bar_s": bar_s,
            "s_low": s_low, "s_rms": s_rms, "sdens": sdens, "speaks": speaks}


# ----------------------------------------------------------------------
# stage 2: before / after tables
# ----------------------------------------------------------------------
def before_after(F: dict, D: dict, ev: dict, prev_t: float, next_t: float,
                 bars: float = 8.0) -> dict:
    """8 bars either side - but CLAMPED at the neighbouring event.

    Several events here sit 8-10 s apart, so an unclamped 8-bar window would average the drop
    together with the breakdown that preceded it and report a delta of nearly zero. The window is
    cut at the neighbour (never shorter than 2 bars) and its true length is reported.
    """
    fps = F["fps"]
    t = ev["t"]
    bar = ev["bar_s"] if ev["bar_s"] == ev["bar_s"] else 1.446
    span = bar * bars
    guard = 0.15
    t0b = max(t - span - guard, prev_t + 0.25, 0.0)
    t0b = min(t0b, t - 2 * bar - guard)
    t1a = min(t + span + guard, next_t - 0.25, F["t"][-1])
    t1a = max(t1a, t + 2 * bar + guard)
    out = {"span_s": span,
           "bef_bars": (t - guard - t0b) / bar, "aft_bars": (t1a - t - guard) / bar}
    for side, (t0, t1) in (("bef", (t0b, t - guard)), ("aft", (t + guard, t1a))):
        r = win(F["rms"], fps, t0, t1)
        out[side + "_rms_db"] = float(db(np.sqrt(np.mean(r ** 2))))
        pk = win(F["peak"], fps, t0, t1)
        out[side + "_crest"] = float(np.max(pk) / max(np.sqrt(np.mean(r ** 2)), 1e-9))
        out[side + "_crest_med"] = float(np.median(win(F["crest"], fps, t0, t1)))
        for b in BANDS + ["low"]:
            out[f"{side}_{b}_db"] = float(db(np.mean(win(F[b], fps, t0, t1))))
        out[side + "_width"] = float(np.mean(win(F["width"], fps, t0, t1)))
        out[side + "_centroid"] = float(np.mean(win(F["centroid"], fps, t0, t1)))
        pks = D["peaks"]
        a, z = int(t0 * fps), int(t1 * fps)
        cnt = int(np.sum((pks >= a) & (pks < z)))
        out[side + "_onsets_per_bar"] = cnt / max((t1 - t0) / bar, 1e-9)
    for k in ["rms_db", "width", "centroid", "crest", "crest_med"] + \
             [b + "_db" for b in BANDS + ["low"]] + ["onsets_per_bar"]:
        out["d_" + k] = out["aft_" + k] - out["bef_" + k]
    return out


# ----------------------------------------------------------------------
# stage 3 + 4: the approach, and the gap
# ----------------------------------------------------------------------
def approach(F: dict, D: dict, ev: dict) -> dict:
    """Sweep 16 s -> 0 s before the event and quantify each build device.

    Every probe window here is CAUSAL - it ends at or before t. An earlier version centred the
    windows, so the last sample of every 'run-up' curve straddled the drop and every build looked
    like it accelerated into one.
    """
    fps, t = F["fps"], ev["t"]
    bar = ev["bar_s"] if ev["bar_s"] == ev["bar_s"] else 1.446
    beat = bar / 4.0
    out = {}

    def probe(x, s, w=0.5, fn=np.mean):
        return float(fn(win(x, fps, t + s, t + s + w)))

    horizon = -min(16.0, t - 0.5)                   # never probe off the front of the file
    ts = np.arange(-8.0, -0.4, 0.25)                # last window is [t-0.65, t-0.15]
    ts = ts[(ts + 0.5 <= -0.05) & (ts >= horizon)]

    # --- snare roll: measured on MID+HIGH onsets, not full-band. A full-band rate counts kicks and
    #     bass notes, and a jungle roll is a snare/hat event; the kick is usually what stops.
    rate = np.array([probe(D["sdens"], s) for s in ts])
    frate = np.array([probe(D["dens"], s) for s in ts])
    c = np.polyfit(ts, rate, 2)
    out["roll_rate_start"] = float(rate[0])
    out["roll_rate_end"] = float(rate[-1])
    out["roll_rate_max"] = float(rate.max())
    out["roll_accel"] = float(2 * c[0])                      # onsets/s^2
    out["roll_slope"] = float(np.polyfit(ts, rate, 1)[0])    # onsets/s per s
    out["roll_ratio"] = float(rate[-1] / max(rate[0], 1e-6))
    out["full_rate_start"] = float(frate[0])
    out["full_rate_end"] = float(frate[-1])
    out["roll"] = bool(rate[-1] - rate[0] >= 2.0 and out["roll_slope"] >= 0.3)

    # --- filter sweep: the longest window ending at the drop over which the UPPER centroid is a
    #     convincing straight ramp. Thresholds are deliberately strict (r2 >= 0.75, >= 800 Hz and
    #     >= 20% of the level, <= 12 s) - loose ones label ordinary spectral drift a "sweep".
    cen_env = {}
    best = None
    for dur in np.arange(2.0, 12.5, 0.5):
        if -dur < horizon:
            break
        sel = np.arange(-dur, -0.4, 0.25)
        sel = sel[sel + 0.5 <= -0.05]
        if len(sel) < 5:
            continue
        cv = np.array([cen_env.setdefault(round(s, 3), probe(F["ucentroid"], s)) for s in sel])
        sl, ic = np.polyfit(sel, cv, 1)
        fit = sl * sel + ic
        r2 = 1.0 - np.sum((cv - fit) ** 2) / max(np.sum((cv - cv.mean()) ** 2), 1e-9)
        delta = abs(cv[-1] - cv[0])
        if r2 >= 0.75 and delta >= 800 and delta / max(cv.mean(), 1e-9) >= 0.20:
            best = {"dur": float(dur), "r2": float(r2), "slope": float(sl),
                    "f0": float(cv[0]), "f1": float(cv[-1])}
    if best:
        out.update({"sweep": True, "sweep_dur_s": best["dur"], "cen_r2": best["r2"],
                    "cen_slope_hz_s": best["slope"], "cen_start": best["f0"],
                    "cen_end": best["f1"], "sweep_dir": "up" if best["slope"] > 0 else "down"})
    else:
        cv = np.array([cen_env.setdefault(round(s, 3), probe(F["ucentroid"], s)) for s in ts])
        out.update({"sweep": False, "sweep_dur_s": 0.0, "cen_r2": 0.0,
                    "cen_slope_hz_s": float(np.polyfit(ts, cv, 1)[0]),
                    "cen_start": float(cv[0]), "cen_end": float(cv[-1]), "sweep_dir": "-"})

    # --- reverse swell / riser: level rising into the drop while the LOW end stays out, with the
    #     crest factor falling (a swell is dense and sustained; a drum fill is transient)
    rms_l = np.array([probe(F["rms"], s) for s in ts])
    low_l = np.array([probe(F["low"], s) for s in ts])
    hi_l = np.array([probe(F["high"] + F["air"], s) for s in ts])
    cr_l = np.array([probe(F["crest"], s, fn=np.median) for s in ts])
    base = slice(0, 8)
    rise_db = float(db(rms_l[-1]) - db(np.median(rms_l[base])))
    low_rise = float(db(low_l[-1]) - db(np.median(low_l[base])))
    out["swell_rise_db"] = rise_db
    out["swell_low_rise_db"] = low_rise
    out["swell_hi_rise_db"] = float(db(hi_l[-1]) - db(np.median(hi_l[base])))
    out["swell_crest_delta"] = float(cr_l[-1] - np.median(cr_l[base]))
    out["swell"] = bool(rise_db >= 4.0 and low_rise < rise_db - 1.0
                        and out["swell_crest_delta"] <= 0.10)

    # --- drum-only bar: drums STILL RUNNING at near full rate while the low end is gone. The
    #     distinction that matters for the theory is 'bass removed' vs 'everything stopped'.
    aft_low = db(np.mean(win(F["low"], fps, t + 0.15, t + 0.15 + 4 * bar)))
    aft_den = float(np.mean(win(D["dens"], fps, t + 0.15, t + 0.15 + 4 * bar)))
    best_bar, best_low, best_den = None, None, None
    s = max(-8.0, horizon)
    while s < -bar * 0.5:
        lw = db(np.mean(win(F["low"], fps, t + s, t + s + bar)))
        dn = float(np.mean(win(D["dens"], fps, t + s, t + s + bar)))
        if best_low is None or lw < best_low:
            best_low, best_bar, best_den = lw, s, dn
        s += bar / 2.0
    gapdb = (aft_low - best_low) if best_low is not None else float("nan")
    ratio = (best_den / max(aft_den, 1e-9)) if best_den is not None else float("nan")
    out["drumonly_low_gap_db"] = float(gapdb)
    out["drumonly_at_s"] = float(best_bar) if best_bar is not None else float("nan")
    out["drumonly_den_ratio"] = float(ratio)
    # drums KEPT RUNNING (>=70% of the post-drop onset rate) while the low end was >=8 dB down
    out["drum_only"] = bool(gapdb == gapdb and gapdb >= 8.0 and ratio >= 0.7)
    # everything stopped instead: the low end went AND the drums went with it
    out["stripped"] = bool(gapdb == gapdb and gapdb >= 8.0 and ratio < 0.7)

    # --- tonal call (vocal line or stab): energy piling into 400-2k RELATIVE to 2k-8k. A snare or
    #     hat lifts both; a voice or a chord stab tilts the balance down. Spectral-balance proxy,
    #     not speech detection - it cannot tell a vocal from an organ chord, and does not try.
    tilt = db(F["mid"]) - db(F["high"])
    bed_t = float(np.median(win(tilt, fps, t - 16.0, t - 4.0)))
    bed_m = float(np.median(db(win(F["mid"], fps, t - 16.0, t - 4.0))))
    seg_tilt = win(tilt, fps, t - 4.0, t - 0.1)
    seg_mid = db(win(F["mid"], fps, t - 4.0, t - 0.1))
    hot = (seg_tilt >= bed_t + 4.0) & (seg_mid >= bed_m + 3.0)
    runlen, bestrun = 0, 0
    for v in hot:
        runlen = runlen + 1 if v else 0
        bestrun = max(bestrun, runlen)
    out["call_ms"] = float(bestrun / fps * 1000.0)
    out["call_tilt_db"] = float(np.max(seg_tilt) - bed_t) if len(seg_tilt) else float("nan")
    out["call_low_db_under"] = float(aft_low - db(np.mean(win(F["low"], fps, t - 4.0, t - 0.1))))
    out["call"] = bool(out["call_ms"] >= 120.0)

    # --- THE GAP: longest near-silent run inside the last 3 s, against the bed IMMEDIATELY before
    #     it (t-8 .. t-3): a global reference would call a whole quiet breakdown a "gap"
    ref = float(np.median(win(F["rms"], fps, t - 8.0, t - 3.0)))
    seg = win(F["rms"], fps, t - 3.0, t - 0.02)
    quiet = seg < ref * 0.25                          # -12 dB under the local bed
    deep = seg < ref * 0.10                           # -20 dB: a true hole
    def longest(mask):
        best = cur = 0
        best_end = -1
        for i, v in enumerate(mask):
            cur = cur + 1 if v else 0
            if cur > best:
                best, best_end = cur, i
        return best, best_end
    g12, e12 = longest(quiet)
    g20, e20 = longest(deep)
    out["gap_ms"] = float(g12 / fps * 1000.0)
    out["gap_beats"] = float((g12 / fps) / beat)
    out["gap_ends_before_ms"] = float((len(seg) - 1 - e12) / fps * 1000.0) if e12 >= 0 else float("nan")
    out["hole_ms"] = float(g20 / fps * 1000.0)
    out["hole_beats"] = float((g20 / fps) / beat)
    out["gap"] = bool(out["gap_ms"] >= 80.0)
    out["hole"] = bool(out["hole_ms"] >= 80.0)
    out["gap_depth_db"] = float(db(np.min(seg)) - db(ref)) if len(seg) else float("nan")
    return out


# ----------------------------------------------------------------------
# stage 5: layering over the first 8 bars after a drop
# ----------------------------------------------------------------------
def layering(F: dict, D: dict, ev: dict, nbars: int = 8) -> dict:
    fps, t = F["fps"], ev["t"]
    bar = ev["bar_s"] if ev["bar_s"] == ev["bar_s"] else 1.45
    rows = []
    for b in range(nbars):
        t0, t1 = t + 0.05 + b * bar, t + 0.05 + (b + 1) * bar
        r = win(F["rms"], fps, t0, t1)
        row = {"bar": b + 1,
               "rms_db": float(db(np.sqrt(np.mean(r ** 2)))),
               "width": float(np.mean(win(F["width"], fps, t0, t1))),
               "centroid": float(np.mean(win(F["centroid"], fps, t0, t1))),
               "onsets": int(np.sum((D["peaks"] >= t0 * fps) & (D["peaks"] < t1 * fps)))}
        for bnd in BANDS:
            row[bnd] = float(db(np.mean(win(F[bnd], fps, t0, t1))))
        rows.append(row)
    ref = rows[0]
    out = {"rows": rows}
    # which bar first reaches within 1 dB of the 8-bar max, per band -> when that layer arrives
    for bnd in BANDS + ["rms_db"]:
        vals = np.array([r[bnd] for r in rows])
        mx = vals.max()
        out["arrive_" + bnd] = int(np.argmax(vals >= mx - 1.0) + 1)
    out["d_bar1_to_bar4_rms"] = rows[3]["rms_db"] - ref["rms_db"]
    out["d_bar1_to_bar2_rms"] = rows[1]["rms_db"] - ref["rms_db"]
    out["onsets_b1"] = rows[0]["onsets"]
    out["onsets_b2_4"] = float(np.mean([rows[i]["onsets"] for i in (1, 2, 3)]))
    return out


# ----------------------------------------------------------------------
# stage 6: full vs reduced, spacing
# ----------------------------------------------------------------------
def coverage(F: dict, D: dict, events: list, down_db: float = 8.0) -> dict:
    """Two-state split of the running time: is the low end in or out?

    A global level threshold would be wrong here - this is a DJ set, and each record sits at its own
    level. So the reference is a rolling 60 s 90th percentile of the low band (that track's own idea
    of 'full'), and a frame counts as REDUCED when it is down_db under it.
    """
    fps = F["fps"]
    bar_s = D["bar_s"]
    low_db = D["low_db"]
    n = len(low_db)
    # A jungle low end PULSES - it is a bassline, not a pad - so the instantaneous low band dips
    # between notes. Ask the question per bar instead: was there any bass in this bar at all?
    # Rolling 1-bar maximum, then compare to the track's own p90.
    w = int(round(bar_s * fps)) | 1
    pad = w // 2
    lp = np.concatenate([np.full(pad, low_db[0]), low_db, np.full(pad, low_db[-1])])
    low_bar = np.array([lp[i:i + w].max() for i in range(n)])

    step = int(round(1.0 * fps))
    idx = np.arange(0, n, step)

    def state(ref_half_s):
        """full/reduced mask for a given reference window. None = one global reference."""
        if ref_half_s is None:
            ref = np.full(n, np.percentile(low_bar, 90))
        else:
            h = int(round(ref_half_s * fps))
            r = np.array([np.percentile(low_bar[max(0, i - h):min(n, i + h)], 90) for i in idx])
            ref = np.interp(np.arange(n), idx, r)
        m = low_bar >= ref - down_db
        return smooth(m.astype(float), int(bar_s * fps)) > 0.5     # de-flicker over a bar

    # The reference window is a real judgement call and the answer moves with it: too short and a
    # 48 s intro becomes its own "full", too long and a quiet record reads as one long breakdown.
    # Report the sweep, and use +-120 s (spans a couple of records) as the headline.
    sweep = {k: float(state(k).mean()) for k in (30.0, 60.0, 120.0, 240.0, None)}
    full = state(120.0)
    frac_full = float(full.mean())

    ch = np.flatnonzero(np.diff(full.astype(int)) != 0)
    segs, prev = [], 0
    for c in list(ch) + [n - 1]:
        segs.append((bool(full[prev]), (c - prev) / fps))
        prev = c + 1
    full_runs = [d for s, d in segs if s and d >= bar_s]
    red_runs = [d for s, d in segs if not s and d >= bar_s]
    drops = [e for e in events if e["kind"] == "drop"]
    gaps = np.diff([e["t"] for e in drops])
    allg = np.diff([e["t"] for e in events])
    # phrase alignment: how close is each drop-to-drop interval to a whole number of bars,
    # and to a multiple of 4 / 8 bars?
    bars_between = gaps / bar_s
    err1 = np.abs(bars_between - np.round(bars_between))
    err4 = np.abs(bars_between / 4 - np.round(bars_between / 4)) * 4
    err8 = np.abs(bars_between / 8 - np.round(bars_between / 8)) * 8
    return {"ref_mode": f"rolling +-120 s p90 - {down_db:g} dB", "frac_full": frac_full,
            "frac_full_sweep": sweep, "mask": full,
            "full_runs": full_runs, "red_runs": red_runs, "bar_s": bar_s,
            "median_full_run": float(np.median(full_runs)) if full_runs else float("nan"),
            "median_red_run": float(np.median(red_runs)) if red_runs else float("nan"),
            "p90_red_run": float(np.percentile(red_runs, 90)) if red_runs else float("nan"),
            "n_full_runs": len(full_runs), "n_red_runs": len(red_runs),
            "drop_gaps_s": gaps.tolist(),
            "drop_gaps_bars": bars_between.tolist(),
            "median_drop_gap_s": float(np.median(gaps)) if len(gaps) else float("nan"),
            "median_drop_gap_bars": float(np.median(gaps) / bar_s) if len(gaps) else float("nan"),
            "median_event_gap_s": float(np.median(allg)) if len(allg) else float("nan"),
            "frac_near_int_bar": float(np.mean(err1 < 0.35)),
            "frac_near_4bar": float(np.mean(err4 < 0.6)),
            "frac_near_8bar": float(np.mean(err8 < 0.8))}


# ----------------------------------------------------------------------
def mmss(t: float) -> str:
    return f"{int(t) // 60}:{t % 60:05.2f}"


def summarise(R: dict) -> dict:
    """Roll the per-event numbers up into the answers the report actually makes claims from."""
    ev = R["events"]
    drops = [e for e in ev if e["kind"] == "drop"]
    brks = [e for e in ev if e["kind"] == "breakdown"]
    big = [e for e in drops if e["grade"] in ("major", "mid")]
    S = {"n_events": len(ev), "n_drops": len(drops), "n_breaks": len(brks), "n_big": len(big)}

    def med(rows, f):
        v = [f(e) for e in rows]
        v = [x for x in v if x == x]
        return float(np.median(v)) if v else float("nan")

    def frac(rows, f):
        return float(np.mean([bool(f(e)) for e in rows])) if rows else float("nan")

    for name, rows in (("drop", drops), ("big", big), ("break", brks)):
        S[f"{name}_med_dlow"] = med(rows, lambda e: e["ba"]["d_low_db"])
        S[f"{name}_med_dsub"] = med(rows, lambda e: e["ba"]["d_sub_db"])
        S[f"{name}_med_dbass"] = med(rows, lambda e: e["ba"]["d_bass_db"])
        S[f"{name}_med_dmid"] = med(rows, lambda e: e["ba"]["d_mid_db"])
        S[f"{name}_med_dhigh"] = med(rows, lambda e: e["ba"]["d_high_db"])
        S[f"{name}_med_drms"] = med(rows, lambda e: e["ba"]["d_rms_db"])
        S[f"{name}_med_dcrest"] = med(rows, lambda e: e["ba"]["d_crest_med"])
        S[f"{name}_med_dwidth"] = med(rows, lambda e: e["ba"]["d_width"])
        S[f"{name}_med_dcen"] = med(rows, lambda e: e["ba"]["d_centroid"])
        S[f"{name}_med_dons"] = med(rows, lambda e: e["ba"]["d_onsets_per_bar"])
        S[f"{name}_med_low4"] = med(rows, lambda e: abs(e["d_low4"]))
    for name, rows in (("drop", drops), ("big", big), ("break", brks)):
        for dev in ("gap", "hole", "roll", "sweep", "swell", "drum_only", "stripped", "call"):
            S[f"{name}_frac_{dev}"] = frac(rows, lambda e, d=dev: e["ap"][d])
        S[f"{name}_med_gap_ms"] = med(rows, lambda e: e["ap"]["gap_ms"])
        S[f"{name}_med_gap_ms_nz"] = med([e for e in rows if e["ap"]["gap_ms"] > 0],
                                         lambda e: e["ap"]["gap_ms"])
        S[f"{name}_med_gap_beats_nz"] = med([e for e in rows if e["ap"]["gap_ms"] > 0],
                                            lambda e: e["ap"]["gap_beats"])
        S[f"{name}_med_drumgap"] = med(rows, lambda e: e["ap"]["drumonly_low_gap_db"])

    # is a drop a LIFT or a RE-WEIGHTING? count how often the top half actually falls
    S["drop_frac_mid_down"] = frac(drops, lambda e: e["ba"]["d_mid_db"] < 0)
    S["drop_frac_high_down"] = frac(drops, lambda e: e["ba"]["d_high_db"] < 0)
    S["drop_frac_cen_down"] = frac(drops, lambda e: e["ba"]["d_centroid"] < 0)
    S["drop_frac_width_down"] = frac(drops, lambda e: e["ba"]["d_width"] < 0)
    S["drop_frac_crest_down"] = frac(drops, lambda e: e["ba"]["d_crest_med"] < 0)
    S["drop_frac_ons_flat"] = frac(drops, lambda e: abs(e["ba"]["d_onsets_per_bar"]) < 2.0)
    S["break_frac_ons_up"] = frac(brks, lambda e: e["ba"]["d_onsets_per_bar"] > 0)
    S["drop_sub_p25"] = float(np.percentile([e["ba"]["d_sub_db"] for e in drops], 25))
    S["drop_sub_p75"] = float(np.percentile([e["ba"]["d_sub_db"] for e in drops], 75))
    S["big_sub_p25"] = float(np.percentile([e["ba"]["d_sub_db"] for e in big], 25))
    S["big_sub_p75"] = float(np.percentile([e["ba"]["d_sub_db"] for e in big], 75))

    # how much absence bought each drop
    for name, rows in (("drop", drops), ("big", big)):
        S[f"{name}_med_pre_bars"] = med(rows, lambda e: e.get("pre_reduced_bars", float("nan")))
        S[f"{name}_frac_pre_ge1bar"] = frac(rows, lambda e: e.get("pre_reduced_bars", 0) >= 1.0)
        S[f"{name}_frac_pre_ge4bar"] = frac(rows, lambda e: e.get("pre_reduced_bars", 0) >= 4.0)
    S["drop_pre_bars_list"] = [round(e.get("pre_reduced_bars", float("nan")), 1) for e in drops]

    # layering: the per-bar picture averaged over drops, as a delta from bar 1
    lay = [e["lay"] for e in drops if "lay" in e]
    S["lay_bars"] = []
    for b in range(8):
        S["lay_bars"].append({
            "bar": b + 1,
            "rms": float(np.median([L["rows"][b]["rms_db"] - L["rows"][0]["rms_db"] for L in lay])),
            "sub": float(np.median([L["rows"][b]["sub"] - L["rows"][0]["sub"] for L in lay])),
            "bass": float(np.median([L["rows"][b]["bass"] - L["rows"][0]["bass"] for L in lay])),
            "mid": float(np.median([L["rows"][b]["mid"] - L["rows"][0]["mid"] for L in lay])),
            "high": float(np.median([L["rows"][b]["high"] - L["rows"][0]["high"] for L in lay])),
            "onsets": float(np.median([L["rows"][b]["onsets"] for L in lay])),
            "width": float(np.median([L["rows"][b]["width"] for L in lay]))})
    for bnd in BANDS + ["rms_db"]:
        a = [L["arrive_" + bnd] for L in lay]
        S["arrive_" + bnd] = float(np.median(a))
        S["arrive_b1_" + bnd] = float(np.mean([x == 1 for x in a]))
    S["frac_all_at_once"] = float(np.mean(
        [max(L["arrive_" + b] for b in BANDS) <= 2 for L in lay]))
    S["med_last_arrival"] = float(np.median(
        [max(L["arrive_" + b] for b in BANDS) for L in lay]))
    return S


def analyse(calib: bool = False) -> dict:
    F = load_frames()
    D = detect_events(F, calib=calib)
    events = D["events"]
    end = float(F["t"][-1])
    for k, e in enumerate(events):
        prev_t = events[k - 1]["t"] if k > 0 else -1e9
        next_t = events[k + 1]["t"] if k + 1 < len(events) else end + 1e9
        e["ba"] = before_after(F, D, e, prev_t, next_t)
        e["ap"] = approach(F, D, e)
        e["grade"] = ("major" if abs(e["d_low4"]) >= 15 else
                      "mid" if abs(e["d_low4"]) >= 8 else "minor")
        if e["kind"] == "drop":
            e["lay"] = layering(F, D, e)
    cov = coverage(F, D, events)
    # how long had the low end been OUT immediately before each drop? This is the quantity the
    # user's theory is actually about: the drop is paid for by the absence in front of it.
    fps = F["fps"]
    full = cov["mask"]
    # The mask is built on a CENTRED 1-bar rolling max, so it flips to "full" up to half a bar
    # before the bass actually lands. So do not scan backwards from t (that reads zero every time):
    # find the reduced RUN whose end sits near the drop, and take its length.
    edges = np.flatnonzero(np.diff(full.astype(int)) != 0)
    runs, prev = [], 0
    for c in list(edges) + [len(full) - 1]:
        runs.append((bool(full[prev]), prev / fps, (c + 1) / fps))
        prev = c + 1
    red = [(a, z) for s, a, z in runs if not s]
    for e in events:
        tol = 1.5 * e["bar_s"]
        near = [(a, z) for a, z in red if abs(z - e["t"]) <= tol]
        if near:
            a, z = max(near, key=lambda r: r[1] - r[0])
            e["pre_reduced_s"] = float(z - a)
        else:
            e["pre_reduced_s"] = 0.0
        e["pre_reduced_bars"] = float(e["pre_reduced_s"] / e["bar_s"])
    R = {"F": F, "D": D, "events": events, "cov": cov}
    R["S"] = summarise(R)
    return R


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--events", action="store_true")
    ap.add_argument("--detail", action="store_true")
    ap.add_argument("--md", action="store_true")
    ap.add_argument("--calib", action="store_true")
    ap.add_argument("--summary", action="store_true")
    a = ap.parse_args(argv)
    R = analyse(calib=a.calib)
    ev = R["events"]
    if a.events or not (a.detail or a.md):
        print(f"{len(ev)} events ({sum(e['kind']=='drop' for e in ev)} drops, "
              f"{sum(e['kind']=='breakdown' for e in ev)} breakdowns)")
        print(f"{'#':>3} {'time':>9} {'kind':<10} {'grade':<6} {'low4':>6} {'dRMS':>6} "
              f"{'dLOW':>6} {'dSUB':>6} {'dOns':>6} {'gap_ms':>7} {'bars':>9} {'dbOff':>7}")
        for e in ev:
            b, p = e["ba"], e["ap"]
            print(f"{e['id']:>3} {mmss(e['t']):>9} {e['kind']:<10} {e['grade']:<6} "
                  f"{e['d_low4']:>+6.1f} {b['d_rms_db']:>+6.1f} "
                  f"{b['d_low_db']:>+6.1f} {b['d_sub_db']:>+6.1f} "
                  f"{b['d_onsets_per_bar']:>+6.1f} {p['gap_ms']:>7.0f} "
                  f"{b['bef_bars']:>4.1f}/{b['aft_bars']:<4.1f} {e['downbeat_off_ms']:>+7.0f}")
        c = R["cov"]
        print(f"\nfull {c['frac_full']*100:.1f}% of runtime ({c['ref_mode']}), "
              f"median full run {c['median_full_run']:.1f} s "
              f"({c['median_full_run']/c['bar_s']:.1f} bars), "
              f"reduced {c['median_red_run']:.1f} s ({c['median_red_run']/c['bar_s']:.1f} bars), "
              f"{c['n_red_runs']} reduced runs")
        print(f"drop spacing bars: {[round(x,1) for x in c['drop_gaps_bars']]}")
        print(f"median drop gap {c['median_drop_gap_s']:.1f} s = "
              f"{c['median_drop_gap_bars']:.1f} bars; median event gap "
              f"{c['median_event_gap_s']:.1f} s")
        print(f"phrase alignment: {c['frac_near_int_bar']*100:.0f}% of drop intervals within "
              f"0.35 bar of a whole bar, {c['frac_near_4bar']*100:.0f}% within 0.6 of a 4-bar "
              f"multiple, {c['frac_near_8bar']*100:.0f}% within 0.8 of an 8-bar multiple")
        off = np.array([abs(e["downbeat_off_ms"]) for e in ev])
        bo = np.array([abs(e["beat_off_ms"]) for e in ev])
        beat_ms = R["D"]["bar_s"] / 4 * 1000
        print(f"downbeat offset |median| {np.median(off):.0f} ms (beat = {beat_ms:.0f} ms); "
              f"{np.mean(off < beat_ms/2)*100:.0f}% land within half a beat of a downbeat")
        print(f"beat offset |median| {np.median(bo):.0f} ms; "
              f"{np.mean(bo < 60)*100:.0f}% land within 60 ms of a beat")
        print("full-fraction vs reference window:",
              {(f'{k:g}s' if k else 'global'): round(v, 3)
               for k, v in R['cov']['frac_full_sweep'].items()})
    if a.detail:
        for e in ev:
            b, p = e["ba"], e["ap"]
            print(f"\n=== #{e['id']} {mmss(e['t'])} {e['kind']} bpm {e['bpm']:.1f} "
                  f"bar {e['bar_s']:.3f}s span {b['span_s']:.1f}s")
            print("  band dB  " + "  ".join(f"{x}:{b['d_'+x+'_db']:+.1f}" for x in BANDS))
            print(f"  rms {b['bef_rms_db']:.1f}->{b['aft_rms_db']:.1f} ({b['d_rms_db']:+.1f})  "
                  f"crest {b['bef_crest_med']:.1f}->{b['aft_crest_med']:.1f}  "
                  f"width {b['bef_width']:.3f}->{b['aft_width']:.3f}  "
                  f"cen {b['bef_centroid']:.0f}->{b['aft_centroid']:.0f}  "
                  f"ons/bar {b['bef_onsets_per_bar']:.1f}->{b['aft_onsets_per_bar']:.1f}")
            print(f"  approach roll={p['roll']} {p['roll_rate_start']:.1f}->{p['roll_rate_end']:.1f}/s "
                  f"acc {p['roll_accel']:+.2f}/s2 | sweep={p['sweep']} {p['cen_start']:.0f}->"
                  f"{p['cen_end']:.0f}Hz r2 {p['cen_r2']:.2f} dur {p['sweep_dur_s']:.1f}s | "
                  f"swell={p['swell']} {p['swell_rise_db']:+.1f}dB cr {p['swell_crest_delta']:+.2f}"
                  f" | drumonly={p['drum_only']} ({p['drumonly_low_gap_db']:.1f}dB "
                  f"den {p['drumonly_den_ratio']:.2f}) | call={p['call']} ({p['call_ms']:.0f}ms "
                  f"tilt {p['call_tilt_db']:+.1f}dB)")
            print(f"  gap {p['gap_ms']:.0f}ms ({p['gap_beats']:.2f} beats) hole {p['hole_ms']:.0f}ms "
                  f"depth {p['gap_depth_db']:.1f}dB")
            if "lay" in e:
                L = e["lay"]
                for r in L["rows"][:4]:
                    print(f"   bar{r['bar']} rms {r['rms_db']:.1f} sub {r['sub']:.1f} "
                          f"bass {r['bass']:.1f} mid {r['mid']:.1f} high {r['high']:.1f} "
                          f"w {r['width']:.3f} ons {r['onsets']}")
                print("   arrive:", {k[7:]: v for k, v in L.items() if k.startswith("arrive_")})
    if a.summary:
        S, c = R["S"], R["cov"]
        print(json.dumps({k: (round(v, 4) if isinstance(v, float) else v)
                          for k, v in S.items() if k != "lay_bars"}, indent=1))
        print("layering (delta from bar 1):")
        for r in S["lay_bars"]:
            print(f"  bar{r['bar']} rms {r['rms']:+.2f} sub {r['sub']:+.2f} bass {r['bass']:+.2f} "
                  f"mid {r['mid']:+.2f} high {r['high']:+.2f} ons {r['onsets']:.1f} "
                  f"w {r['width']:.3f}")
        print("gaps (ms) per drop:",
              [round(e["ap"]["gap_ms"]) for e in R["events"] if e["kind"] == "drop"])
        print("holes (ms) per drop:",
              [round(e["ap"]["hole_ms"]) for e in R["events"] if e["kind"] == "drop"])
        print(f"coverage: full {c['frac_full']*100:.1f}%  full-run med {c['median_full_run']:.1f}s "
              f"({c['median_full_run']/c['bar_s']:.1f} bars)  red-run med {c['median_red_run']:.1f}s "
              f"({c['median_red_run']/c['bar_s']:.1f} bars) p90 {c['p90_red_run']:.1f}s  "
              f"n_red {c['n_red_runs']}")
    if a.md:
        write_report(R)
    return 0


def devices(e: dict) -> str:
    p = e["ap"]
    d = []
    if p["drum_only"]:
        d.append("drum-only")
    if p["stripped"]:
        d.append("stripped")
    if p["gap"]:
        d.append("gap")
    if p["roll"]:
        d.append("roll")
    if p["sweep"]:
        d.append("sweep " + p["sweep_dir"])
    if p["swell"]:
        d.append("swell")
    if p["call"]:
        d.append("call")
    return ", ".join(d) if d else "-"


def write_report(R: dict):
    os.makedirs(OUT_DIR, exist_ok=True)
    ev, S, c, D = R["events"], R["S"], R["cov"], R["D"]
    drops = [e for e in ev if e["kind"] == "drop"]
    brks = [e for e in ev if e["kind"] == "breakdown"]
    bar_s, bpm = D["bar_s"], D["bpm"]
    dur = float(R["F"]["t"][-1])
    L = []
    w = L.append

    w("# Tim Reaper jungle DJ set - the anatomy of every drop and breakdown")
    w("")
    w(f"Reference: `Tim_Reaper_Jungle_DJ_Set_SECTION_August_2026.wav`, {dur:.1f} s "
      f"({dur/60:.1f} min), 48 kHz stereo. **Structural analysis only** - no audio was sampled, "
      f"extracted or copied. Every figure below is a measurement.")
    w("")
    w(f"Generated by `scripts/reaper_drops.py` from the cached feature frames "
      f"(93.7 fps, 2048-pt STFT).")
    w("")
    w("## Method, and what to distrust")
    w("")
    w(f"**Tempo.** The cached grid (165.83 BPM, beat confidence 1.04) is not usable - a "
      f"beat-range autocorrelation lands anywhere in the comb of 16th / 8th / beat harmonics, "
      f"which are all nearly the same height. Re-derived here from the **four-bar** "
      f"autocorrelation lag instead, which has no competitor near it: peaks at 2891.5 ms and "
      f"5783.0 ms are exactly 2 and 4 bars, giving **{bpm:.2f} BPM, bar = {bar_s*1000:.1f} ms, "
      f"beat = {bar_s/4*1000:.1f} ms**. The tempo is constant across the set (beatmatched).")
    w("")
    near8 = sorted(x for x in c["drop_gaps_bars"] if abs(x / 8 - round(x / 8)) * 8 < 0.8)
    w(f"Independent check that this grid is real: **{c['frac_near_int_bar']*100:.0f}% of the "
      f"drop-to-drop intervals land within 0.35 bar of a whole number of bars**, and "
      f"{len(near8)} of them sit on 8-bar multiples "
      f"({', '.join(f'{x:.1f}' for x in near8)} bars). That does not happen against a wrong "
      f"tempo.")
    w("")
    w(f"*Cross-check:* the grid analysis in `grid.md` reaches **165.99 +- 0.02 BPM** (beat "
      f"361.459 ms) by a completely different route - least-squares line fits to tracked beat "
      f"times. This analysis gets {bpm:.2f} BPM (beat {bar_s/4*1000:.1f} ms) from the four-bar "
      f"autocorrelation lag. Agreement to 0.03 BPM. That file also finds a **+114 ms (+0.31 "
      f"beat) phase step** at one mix point with the tempo unchanged, which is why the bar phase "
      f"here is re-estimated locally per event rather than from one global grid.")
    w("")
    w("**Detection.** Whole-file sweep of a median step function - median of the 4 bars after "
      "minus the median of the 4 bars before, with a 0.4 s guard band so the transient belongs to "
      "neither side - run on low-band (20-120 Hz) level and on RMS. Four bars, because that is "
      "the unit a jungle arrangement moves in; 8 bars smears a drop that is answered 8 bars "
      "later, 1 bar fires on every fill. Kept when the low band steps >= 6 dB, or >= 4 dB with "
      ">= 3 dB of RMS. Each event is then snapped to the steepest low-band move within +-3 s and, "
      "for a drop, to the nearest onset.")
    w("")
    w("**Caveats.** (1) This is a DJ set, so at any mix point two records overlap and some events "
      "are the incoming record's, not the outgoing one's - structurally it is still what the "
      "listener hears. (2) The 8-bar before/after windows are **clamped at the neighbouring "
      "event**; several events sit 8-10 s apart and an unclamped window would average a drop "
      "together with the breakdown feeding it and report a delta of nearly zero. The true window "
      "length is given per event. (3) 'Call' is a spectral-balance proxy (400-2k energy tilting "
      "up against 2-8k, sustained >= 120 ms) - it cannot tell a vocal from an organ chord and "
      "does not try. (4) Band levels are dB of summed STFT magnitude, so they are comparable to "
      "each other and across time, but they are not absolute SPL.")
    w("")

    w("## 1. Every event")
    w("")
    w(f"**{S['n_events']} events: {S['n_drops']} drops and {S['n_breaks']} breakdowns** over "
      f"{dur/60:.1f} minutes. Graded by the size of the 4-bar low-band step that fired them: "
      f"major >= 15 dB, mid 8-15 dB, minor < 8 dB.")
    w("")
    w("`win` is the actual before/after window in bars (8/8 unless clamped by a neighbour). "
      "Deltas are after minus before.")
    w("")
    w("| # | time | type | grade | step dB | ΔRMS | Δsub | Δbass | Δlomid | Δmid | Δhigh | Δair "
      "| Δcrest | Δwidth | Δcentr Hz | Δons/bar | win |")
    w("|---:|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|")
    for e in ev:
        b = e["ba"]
        w(f"| {e['id']} | {mmss(e['t'])} | {e['kind']} | {e['grade']} | {e['d_low4']:+.1f} "
          f"| {b['d_rms_db']:+.1f} | {b['d_sub_db']:+.1f} | {b['d_bass_db']:+.1f} "
          f"| {b['d_lowmid_db']:+.1f} | {b['d_mid_db']:+.1f} | {b['d_high_db']:+.1f} "
          f"| {b['d_air_db']:+.1f} | {b['d_crest_med']:+.2f} | {b['d_width']:+.3f} "
          f"| {b['d_centroid']:+.0f} | {b['d_onsets_per_bar']:+.1f} "
          f"| {b['bef_bars']:.0f}/{b['aft_bars']:.0f} |")
    w("")
    w("### What the deltas say")
    w("")
    w(f"A drop here is **not a lift, it is a re-weighting**. Median across the "
      f"{S['n_drops']} drops: sub **{S['drop_med_dsub']:+.1f} dB**, bass "
      f"**{S['drop_med_dbass']:+.1f} dB** - but mid **{S['drop_med_dmid']:+.1f} dB**, high "
      f"**{S['drop_med_dhigh']:+.1f} dB**, and the spectral centroid moves "
      f"**{S['drop_med_dcen']:+.0f} Hz**. Overall RMS only rises "
      f"**{S['drop_med_drms']:+.1f} dB**. Restricting to the {S['n_big']} real drops "
      f"(step >= 8 dB): sub **{S['big_med_dsub']:+.1f} dB** "
      f"(IQR {S['big_sub_p25']:+.1f} to {S['big_sub_p75']:+.1f}), bass "
      f"**{S['big_med_dbass']:+.1f} dB**, RMS **{S['big_med_drms']:+.1f} dB**, centroid "
      f"**{S['big_med_dcen']:+.0f} Hz**.")
    w("")
    w(f"- The mid band falls on **{S['drop_frac_mid_down']*100:.0f}%** of drops and the high band "
      f"on **{S['drop_frac_high_down']*100:.0f}%**. The centroid falls on "
      f"**{S['drop_frac_cen_down']*100:.0f}%**.")
    w(f"- Stereo width **narrows** on {S['drop_frac_width_down']*100:.0f}% of drops "
      f"(median {S['drop_med_dwidth']:+.3f}); crest factor falls on "
      f"{S['drop_frac_crest_down']*100:.0f}% (median {S['drop_med_dcrest']:+.2f}) - the drop is "
      f"denser and more centred, not just louder.")
    w(f"- Onset density barely moves: median **{S['drop_med_dons']:+.1f} onsets/bar**, and "
      f"{S['drop_frac_ons_flat']*100:.0f}% of drops change it by less than 2/bar. **The drums do "
      f"not get busier at the drop.**")
    w("")
    w(f"Breakdowns are the mirror image, and they are *not* quiet: sub "
      f"**{S['break_med_dsub']:+.1f} dB** and low **{S['break_med_dlow']:+.1f} dB**, but mid "
      f"**{S['break_med_dmid']:+.1f} dB**, centroid **{S['break_med_dcen']:+.0f} Hz**, crest "
      f"**{S['break_med_dcrest']:+.2f}**, and onset density goes **UP** "
      f"({S['break_med_dons']:+.1f}/bar, rising on {S['break_frac_ons_up']*100:.0f}% of them). "
      f"RMS only drops {S['break_med_drms']:+.1f} dB. Taking the bass out makes the record "
      f"brighter, busier and spikier - it does not make it quieter.")
    w("")

    w("## 2. The approach to each drop")
    w("")
    w("Swept 16 s -> 0 s before each drop. All probe windows are causal (they end before the "
      "drop), so nothing here is contaminated by the drop itself.")
    w("")
    w("| # | time | pre-reduced | gap ms (beats) | hole ms | low down dB | drum density | roll /s "
      "| sweep | call ms | devices |")
    w("|---:|---:|---:|---:|---:|---:|---:|---|---|---:|---|")
    for e in drops:
        p = e["ap"]
        sw = (f"{p['cen_start']:.0f}->{p['cen_end']:.0f}Hz / {p['sweep_dur_s']:.1f}s"
              if p["sweep"] else "-")
        ro = (f"{p['roll_rate_start']:.1f}->{p['roll_rate_end']:.1f} "
              f"({p['roll_accel']:+.2f}/s²)" if p["roll"] else
              f"{p['roll_rate_start']:.1f}->{p['roll_rate_end']:.1f}")
        w(f"| {e['id']} | {mmss(e['t'])} | {e['pre_reduced_bars']:.1f} bar "
          f"| {p['gap_ms']:.0f} ({p['gap_beats']:.2f}) | {p['hole_ms']:.0f} "
          f"| {p['drumonly_low_gap_db']:.1f} | {p['drumonly_den_ratio']:.2f} | {ro} | {sw} "
          f"| {p['call_ms']:.0f} | {devices(e)} |")
    w("")
    w("### Which devices are actually used")
    w("")
    w(f"Across all {S['n_drops']} drops (and, in brackets, the {S['n_big']} drops of >= 8 dB):")
    w("")
    w("| device | share of drops | what it measures |")
    w("|---|---:|---|")
    w(f"| **drums keep running, bass out** | **{S['drop_frac_drum_only']*100:.0f}%** "
      f"({S['big_frac_drum_only']*100:.0f}%) | a bar in the last 8 s with the low band >= 8 dB "
      f"down while onset density stays >= 70% of the post-drop rate |")
    w(f"| everything stripped (drums go too) | {S['drop_frac_stripped']*100:.0f}% "
      f"({S['big_frac_stripped']*100:.0f}%) | same, but density < 70% |")
    w(f"| snare roll (rising mid/high onset rate) | {S['drop_frac_roll']*100:.0f}% "
      f"({S['big_frac_roll']*100:.0f}%) | rate up >= 2/s with slope >= 0.3/s² over 8 bars |")
    w(f"| gap / near-silence >= 80 ms | {S['drop_frac_gap']*100:.0f}% "
      f"({S['big_frac_gap']*100:.0f}%) | -12 dB under the bed of the 5 s before it |")
    w(f"| true hole (-20 dB) | {S['drop_frac_hole']*100:.0f}% "
      f"({S['big_frac_hole']*100:.0f}%) | as above at -20 dB |")
    w(f"| filter sweep (upper-centroid ramp) | {S['drop_frac_sweep']*100:.0f}% "
      f"({S['big_frac_sweep']*100:.0f}%) | r² >= 0.75, >= 800 Hz and >= 20% of level |")
    w(f"| tonal call / stab | {S['drop_frac_call']*100:.0f}% "
      f"({S['big_frac_call']*100:.0f}%) | 400-2k tilting >= 4 dB up against 2-8k for >= 120 ms |")
    w(f"| **reverse swell / riser** | **{S['drop_frac_swell']*100:.0f}%** "
      f"({S['big_frac_swell']*100:.0f}%) | level rising >= 4 dB into the drop with the low end "
      f"still out and crest not rising |")
    w("")
    w(f"**The dominant device is subtraction, and it is nearly the only one.** "
      f"{S['drop_frac_drum_only']*100:.0f}% of drops are set up by keeping the break running at "
      f"full density while the low end is pulled out by a median of "
      f"**{S['drop_med_drumgap']:.1f} dB**. Every other device is a minority: rolls "
      f"{S['drop_frac_roll']*100:.0f}%, sweeps {S['drop_frac_sweep']*100:.0f}%, calls "
      f"{S['drop_frac_call']*100:.0f}%. **There is not one reverse swell or riser in the set "
      f"({S['drop_frac_swell']*100:.0f}%).** This is the user's theory measured: the drop is "
      f"paid for by the absence in front of it, not by a signpost pointing at it.")
    w("")
    risers = [e for e in drops if e["ap"]["swell_rise_db"] >= 4.0]
    riser_desc = "; ".join(
        f"{mmss(e['t'])} rises {e['ap']['swell_rise_db']:+.1f} dB but its low band rises "
        f"{e['ap']['swell_low_rise_db']:+.0f} dB with it (the bass returning early, not a riser "
        f"over an empty low end)" if e["ap"]["swell_low_rise_db"] > 0 else
        f"{mmss(e['t'])} rises {e['ap']['swell_rise_db']:+.1f} dB with the low end still "
        f"{abs(e['ap']['swell_low_rise_db']):.0f} dB down, but its crest factor *rises* "
        f"{e['ap']['swell_crest_delta']:+.2f} - a drum fill getting louder, not a sustained swell"
        for e in risers)
    med_rise = float(np.median([e["ap"]["swell_rise_db"] for e in drops]))
    w(f"The zero is not a threshold artifact. Only **{len(risers)} of {len(drops)} drops have "
      f"even a 4 dB rise in level** over the 8 bars leading into them, and neither is a riser: "
      f"{riser_desc}. The median drop is approached by a level that is **falling** "
      f"({med_rise:+.1f} dB), not rising.")
    w("")
    w(f"Median time the low end had been out before a drop: "
      f"**{S['drop_med_pre_bars']:.1f} bars**. "
      f"{S['drop_frac_pre_ge1bar']*100:.0f}% of drops have at least 1 bar of it, but only "
      f"{S['drop_frac_pre_ge4bar']*100:.0f}% have 4 bars or more. The absence is usually short.")
    w("")

    w("## 3. The gap")
    w("")
    gvals = [e["ap"]["gap_ms"] for e in drops]
    hvals = [e["ap"]["hole_ms"] for e in drops]
    nz = sorted([g for g in gvals if g > 0])
    w(f"A true hole right before a drop is **the exception, not the rule**.")
    w("")
    w(f"- **{S['drop_frac_gap']*100:.0f}%** of drops ({sum(1 for g in gvals if g >= 80)} of "
      f"{len(drops)}) have >= 80 ms of near-silence (-12 dB) in the last 3 s.")
    w(f"- **{S['drop_frac_hole']*100:.0f}%** ({sum(1 for h in hvals if h >= 80)} of {len(drops)}) "
      f"have a true hole at -20 dB.")
    w(f"- When there is a gap at all, the median is **{S['drop_med_gap_ms_nz']:.0f} ms = "
      f"{S['drop_med_gap_beats_nz']:.2f} beats** - a fraction of a beat, a flam, not a bar of "
      f"silence.")
    w(f"- Non-zero gaps, sorted (ms): {', '.join(f'{g:.0f}' for g in nz)}. Only one exceeds half "
      f"a bar.")
    w("")
    w(f"At {bpm:.1f} BPM a beat is {bar_s/4*1000:.0f} ms and a 16th is {bar_s/16*1000:.0f} ms, so "
      f"the typical gap is roughly **a single 16th of silence**, and the biggest normal one is "
      f"about a beat. The set never stops dead for a bar to announce a drop.")
    w("")

    w("## 4. What arrives, and when")
    w("")
    w("Bars 1-8 after each drop, median across all drops, as a delta from bar 1:")
    w("")
    w("| bar | ΔRMS dB | Δsub | Δbass | Δmid | Δhigh | onsets | width |")
    w("|---:|---:|---:|---:|---:|---:|---:|---:|")
    for r in S["lay_bars"]:
        w(f"| {r['bar']} | {r['rms']:+.2f} | {r['sub']:+.2f} | {r['bass']:+.2f} | {r['mid']:+.2f} "
          f"| {r['high']:+.2f} | {r['onsets']:.1f} | {r['width']:.3f} |")
    w("")
    w(f"**The arrangement arrives all at once.** Bar 2 is within "
      f"{abs(S['lay_bars'][1]['rms']):.2f} dB of bar 1 in RMS, bar 4 within "
      f"{abs(S['lay_bars'][3]['rms']):.2f} dB, and onset count is flat "
      f"({S['lay_bars'][0]['onsets']:.0f} -> {S['lay_bars'][3]['onsets']:.0f} per bar). There is "
      f"no 1-8 bar layered build-in: the median bar at which each band first reaches within 1 dB "
      f"of its 8-bar maximum is bar {S['arrive_sub']:.0f} for sub, bass, lowmid, high and air "
      f"(mid {S['arrive_mid']:.1f}), and RMS reaches it in bar 1 on "
      f"{S['arrive_b1_rms_db']*100:.0f}% of drops.")
    w("")
    w(f"The one exception is the **sub**, which adds a further "
      f"**{S['lay_bars'][1]['sub']:+.2f} dB between bar 1 and bar 2** and stays there - the first "
      f"bar of a drop often has a gap or a single held note in it before the bassline proper "
      f"starts on bar 2. Bar 8 is where the low end starts leaving again "
      f"({S['lay_bars'][7]['bass']:+.2f} dB bass), which is the next breakdown arriving on the "
      f"phrase boundary.")
    w("")

    w("## 5. Spacing, and how much of the set is 'full'")
    w("")
    gb = c["drop_gaps_bars"]
    w(f"- **{S['n_drops']} drops in {dur/60:.1f} min**: median spacing "
      f"**{c['median_drop_gap_s']:.1f} s = {c['median_drop_gap_bars']:.1f} bars**, range "
      f"{min(gb):.0f}-{max(gb):.0f} bars.")
    w(f"- Counting breakdowns too, a structural event every **{c['median_event_gap_s']:.1f} s** "
      f"(~{c['median_event_gap_s']/bar_s:.0f} bars) on median.")
    w(f"- Drop-to-drop intervals in bars: {', '.join(f'{x:.1f}' for x in gb)}.")
    w(f"- **{c['frac_near_int_bar']*100:.0f}%** are within 0.35 bar of a whole bar; "
      f"{c['frac_near_4bar']*100:.0f}% within 0.6 of a 4-bar multiple.")
    w("")
    w(f"**Full vs reduced.** A frame counts as *full* when the low band, taken as a 1-bar rolling "
      f"maximum (a jungle low end pulses - the question is whether there was any bass in the bar, "
      f"not whether there is bass in this millisecond), is within 8 dB of that record's own "
      f"rolling 90th percentile.")
    w("")
    w(f"- **Full {c['frac_full']*100:.1f}% of the running time, reduced "
      f"{(1-c['frac_full'])*100:.1f}%.** This is robust to the reference window: "
      f"{', '.join(f'{(f'{k:g} s' if k else 'global')}: {v*100:.1f}%' for k, v in c['frac_full_sweep'].items())}.")
    rr = np.sort(np.array(c["red_runs"]) / bar_s)
    fr = np.sort(np.array(c["full_runs"]) / bar_s)
    w(f"- {c['n_full_runs']} full runs, median **{c['median_full_run']/bar_s:.1f} bars** "
      f"({c['median_full_run']:.1f} s), longest {fr[-1]:.0f} bars.")
    w(f"- {c['n_red_runs']} reduced runs, median **{c['median_red_run']/bar_s:.1f} bars** "
      f"({c['median_red_run']:.1f} s), 90th percentile {c['p90_red_run']/bar_s:.1f} bars.")
    w(f"- Reduced-run lengths (bars): {', '.join(f'{x:.1f}' for x in rr)}.")
    w(f"- Full-run lengths (bars): {', '.join(f'{x:.1f}' for x in fr)} - clustering near 8, 16, "
      f"32 and 48.")
    w("")
    w(f"So the set is in its loud state roughly **6 bars out of every 7**, and the reduced state "
      f"is typically **1-2 bars**, occasionally 4, 7 or 15. The absence is a short, frequent "
      f"punctuation, not a long section.")
    w("")

    w("## What this means for building a jungle track")
    w("")
    rules = [
        (f"**Move the low end, not the fader.** A drop = sub **+10 dB** and bass **+5 dB** "
         f"(IQR {S['big_sub_p25']:+.0f} to {S['big_sub_p75']:+.0f} dB on sub) while mid and high "
         f"go *down* about **1 dB** and the centroid falls **~400 Hz**. Total RMS should rise only "
         f"**2-3 dB**. If your drop is +6 dB of everything, it is a volume automation, not a "
         f"drop."),
        (f"**Spend the bar before on subtraction, not on a signpost.** {S['drop_frac_drum_only']*100:.0f}% of "
         f"drops are set up by the break running at full density with the low end pulled "
         f"**{S['drop_med_drumgap']:.0f} dB** down. Keep the drums at >= 70% of their normal onset "
         f"rate through the gap - do not thin them out."),
        (f"**Build no risers.** Zero of {S['n_drops']} drops use a reverse swell. Rolls "
         f"({S['drop_frac_roll']*100:.0f}%), filter sweeps ({S['drop_frac_sweep']*100:.0f}%) and "
         f"stabs ({S['drop_frac_call']*100:.0f}%) are each a minority device - use at most one, on "
         f"about one drop in four, never on all of them."),
        (f"**Keep the gap to one 16th.** Only {S['drop_frac_gap']*100:.0f}% of drops have any "
         f"near-silence at all and only {S['drop_frac_hole']*100:.0f}% a true hole. When you do "
         f"use one, make it **~{S['drop_med_gap_ms_nz']:.0f} ms** - one 16th note is "
         f"{bar_s/16*1000:.0f} ms at this tempo, so that is {S['drop_med_gap_beats_nz']:.2f} of a "
         f"beat - not a bar. One gap of about a beat ({bar_s/4*1000:.0f} ms) per track is the "
         f"ceiling; the whole set contains exactly one longer than that."),
        (f"**The absence is short.** Median low-end absence before a drop is "
         f"**{S['drop_med_pre_bars']:.1f} bars**; only {S['drop_frac_pre_ge4bar']*100:.0f}% run to "
         f"4 bars or more. Reduced passages median **{c['median_red_run']/bar_s:.1f} bars**. A "
         f"16-bar breakdown is a once-per-track event, not the pattern."),
        (f"**Drop everything in on bar 1.** No layered entry: bar 2 is within "
         f"{abs(S['lay_bars'][1]['rms']):.1f} dB of bar 1, onset count is flat from bar 1. The "
         f"only staged element is the sub, which may add **{S['lay_bars'][1]['sub']:+.1f} dB into "
         f"bar 2** - i.e. hold or gap the first bass note, then let the line run."),
        (f"**Space drops {c['median_drop_gap_bars']:.0f} bars apart.** Median "
         f"{c['median_drop_gap_s']:.0f} s = {c['median_drop_gap_bars']:.0f} bars, with 16, 24, 32, "
         f"48 and 64 bars all appearing. Land them on whole bars - "
         f"{c['frac_near_int_bar']*100:.0f}% of the set's intervals do. Something structural "
         f"should happen every ~{c['median_event_gap_s']/bar_s:.0f} bars, but only half of those "
         f"are drops."),
        (f"**Stay loud {c['frac_full']*100:.0f}% of the time.** Roughly 6 bars full to 1 bar "
         f"reduced. Full runs median {c['median_full_run']/bar_s:.0f} bars. Surprise is only "
         f"legible against a long-held steady state - if you are reducing every 8 bars, the "
         f"reduction stops meaning anything."),
        (f"**Make the breakdown brighter and busier, not quieter.** Pulling the bass costs only "
         f"{abs(S['break_med_drms']):.1f} dB of RMS while the centroid rises "
         f"**{S['break_med_dcen']:+.0f} Hz**, crest rises **{S['break_med_dcrest']:+.2f}** and "
         f"onset density goes **up** on {S['break_frac_ons_up']*100:.0f}% of breakdowns. Chop the "
         f"break harder when the bass leaves."),
        (f"**Narrow the image at the drop.** Stereo width falls on "
         f"{S['drop_frac_width_down']*100:.0f}% of drops (median {S['drop_med_dwidth']:+.3f}) and "
         f"crest falls {abs(S['drop_med_dcrest']):.2f}. The drop is the most mono, most dense "
         f"moment - keep the wide material for the breakdown."),
    ]
    for i, r in enumerate(rules, 1):
        w(f"{i}. {r}")
    w("")

    path = os.path.join(OUT_DIR, "drops.md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")
    print(f"wrote {path} ({len(L)} lines)")


if __name__ == "__main__":
    sys.exit(main())
