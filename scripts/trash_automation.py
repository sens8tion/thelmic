"""Slow automation curves on Trash Tilt Frequency, per track.

User has exposed `B2 Trash Tilt Frequency` on HOOVER_LEAD (T3) and
SIREN_FX (T5) and asked for me to modulate them — slowly so the
changes are musical, not jittery.

Live 12's clip-envelope API only exposes `insert_step(time, length, value)`
which creates FLAT segments — it does NOT linearly interpolate between
distant breakpoints. To produce a smooth-feeling ramp we have to
pre-interpolate client-side: take our N anchor points, densify to
32 breakpoints per clip (one per beat), each a 1-beat-long step at
the linearly-interpolated value. Over an 8-bar/32-beat clip that
reads as a clean ramp.

Per-scene curve philosophy:
  S3 HOOVER_DROP   — first statement, somewhat clean: 0.30 -> 0.50
  S4 ANNIHILATION  — climbing chaos:                  0.50 -> 0.85
  S5 BREAKDOWN_BLD — descending wails get cleaner:    0.75 -> 0.40
  S7 NUCLEAR       — max depravity with slow wave:    0.75 -> 0.95 -> 0.80 -> 0.95

Depraved twins ramp higher — more trash on the depraved band:
  S11 HOOVER_DROP_DEFILED  : 0.40 -> 0.65
  S12 ANNIHILATION_UNSEALED: 0.65 -> 0.95
  S13 BREAKDOWN_RANCID     : 0.85 -> 0.50
  S15 NUCLEAR_TERMINAL     : 0.90 -> 0.95 -> 0.90 -> 1.00
"""
from __future__ import annotations
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("LIVE_CHANNEL_ENABLED", "1")

from thelmic.live_channel import LiveChannel


TRASH_PARAM = "B2 Trash Tilt Frequency"
# Tracks to automate. Add more if user exposes Trash on additional lanes.
TRACKS_TO_AUTOMATE = ("HOOVER_LEAD", "SIREN_FX", "ACID_TONGUE")

# Densify anchor breakpoints into N evenly-spaced steps spanning 0..CLIP_LEN
CLIP_LEN = 32.0
DENSE_STEPS = 32  # one step per beat — perceived as smooth ramp at 190 BPM


def densify(anchors: list) -> list:
    """Linearly interpolate the (t, v) anchors into DENSE_STEPS breakpoints
    evenly spaced across [0, CLIP_LEN]."""
    out = []
    step = CLIP_LEN / DENSE_STEPS
    for i in range(DENSE_STEPS):
        t = i * step
        # Find the two anchors bracketing t
        before = anchors[0]
        after = anchors[-1]
        for j in range(len(anchors) - 1):
            if anchors[j][0] <= t <= anchors[j+1][0]:
                before, after = anchors[j], anchors[j+1]
                break
        t0, v0 = before
        t1, v1 = after
        if t1 == t0:
            v = v0
        else:
            frac = (t - t0) / (t1 - t0)
            v = v0 + frac * (v1 - v0)
        out.append([t, v])
    return out


# Per-track, per-scene anchor breakpoints. Each list = [time_in_beats, value]
# across a 32-beat clip. Densified to 32 steps before write.

# Wider sweeps — each scene's curve covers a much larger value range
# so the timbre actually transforms across the 8 bars instead of
# nudging. Most curves now span 0.50+ of the parameter range, several
# go from near-floor to near-ceiling in a single scene.

HOOVER_CURVES = {
    # --- BASE band ---
    3: [[0.0, 0.15], [8.0, 0.30], [16.0, 0.50], [24.0, 0.70], [32.0, 0.85]],  # clean entry -> dirty exit (0.70 sweep)
    4: [[0.0, 0.30], [8.0, 0.65], [16.0, 0.95], [24.0, 0.50], [32.0, 0.90]],  # climb -> peak -> dip -> peak (turbulent)
    5: [[0.0, 0.95], [8.0, 0.40], [16.0, 0.80], [24.0, 0.25], [32.0, 0.10]],  # dirty enter -> swing -> void
    7: [[0.0, 0.40], [8.0, 1.00], [16.0, 0.30], [24.0, 0.95], [32.0, 1.00]],  # wild oscillation, hits ceiling+floor
    # --- DEPRAVED band — higher floor, ceiling-touching ---
    11: [[0.0, 0.20], [8.0, 0.50], [16.0, 0.85], [24.0, 0.65], [32.0, 1.00]],
    12: [[0.0, 0.40], [8.0, 0.90], [16.0, 1.00], [24.0, 0.55], [32.0, 1.00]],
    13: [[0.0, 1.00], [8.0, 0.50], [16.0, 0.95], [24.0, 0.30], [32.0, 0.10]],
    15: [[0.0, 0.55], [8.0, 1.00], [16.0, 0.40], [24.0, 1.00], [32.0, 1.00]],
}

# Siren moves more dramatically too — air-raid wash that actually
# transforms its character under your ears across each scene.
SIREN_CURVES = {
    # --- BASE band ---
    0: [[0.0, 0.00], [8.0, 0.20], [16.0, 0.50], [24.0, 0.75], [32.0, 0.95]],   # BLACKOUT cold floor -> filthy ceiling
    2: [[0.0, 0.05], [16.0, 0.50], [24.0, 0.80], [32.0, 1.00]],                # IRON_MARCH zero -> max
    3: [[0.0, 0.20], [16.0, 0.85], [32.0, 0.15]],                               # HOOVER_DROP arch hump
    4: [[0.0, 0.20], [8.0, 0.90], [16.0, 0.30], [24.0, 0.95], [32.0, 0.50]],   # ANNIHILATION turbulent peaks+dips
    5: [[0.0, 1.00], [8.0, 0.25], [16.0, 0.90], [24.0, 0.30], [32.0, 1.00]],   # BREAKDOWN siren foreground — extreme oscillation
    6: [[0.0, 0.00], [8.0, 0.25], [16.0, 0.55], [24.0, 0.85], [32.0, 1.00]],   # REBUILD floor -> ceiling climb
    7: [[0.0, 0.50], [8.0, 1.00], [16.0, 0.20], [24.0, 1.00], [32.0, 0.80]],   # NUCLEAR ceiling-floor-ceiling
    # --- DEPRAVED band — hit hard floor + hard ceiling ---
    8:  [[0.0, 0.00], [8.0, 0.30], [16.0, 0.65], [24.0, 0.90], [32.0, 1.00]],
    10: [[0.0, 0.20], [16.0, 0.65], [24.0, 0.95], [32.0, 1.00]],
    11: [[0.0, 0.30], [16.0, 1.00], [32.0, 0.30]],
    12: [[0.0, 0.40], [8.0, 1.00], [16.0, 0.50], [24.0, 1.00], [32.0, 0.70]],
    13: [[0.0, 1.00], [8.0, 0.45], [16.0, 1.00], [24.0, 0.40], [32.0, 1.00]],
    14: [[0.0, 0.15], [8.0, 0.55], [16.0, 0.85], [24.0, 1.00], [32.0, 1.00]],
    15: [[0.0, 0.70], [8.0, 1.00], [16.0, 0.40], [24.0, 1.00], [32.0, 1.00]],
}

# ACID_TONGUE is a depraved lane — fires only in S8-S15. It plays on
# the depraved peaks: S12 (ANNIHILATION_UNSEALED) and S15 (NUCLEAR_TERMINAL).
# Already a filthy squelch by nature, so curves sit high and oscillate
# rather than ramping from clean to dirty — the 16th-note phrase wants
# the trash to evolve under it, not bury it.
ACID_CURVES = {
    12: [[0.0, 0.40], [8.0, 1.00], [16.0, 0.15], [24.0, 1.00], [32.0, 0.70]],
    15: [[0.0, 0.70], [8.0, 1.00], [16.0, 0.40], [24.0, 1.00], [32.0, 1.00]],
}

PER_TRACK_CURVES = {
    "HOOVER_LEAD": HOOVER_CURVES,
    "SIREN_FX":    SIREN_CURVES,
    "ACID_TONGUE": ACID_CURVES,
}


def _find_trash_device(ch, track_idx: int) -> int | None:
    """Locate the Trash plugin's device index on a given track."""
    ti = ch.get_track_info(track_idx).result(timeout=5)
    for di, d in enumerate(ti.get("devices") or []):
        if d.get("name") == "Trash":
            return di
    # Fallback: scan device params for the trash freq name
    for di, _ in enumerate(ti.get("devices") or []):
        info = ch.get_device_info(track_idx, di).result(timeout=5)
        names = {p.get("name","") for p in info.get("parameters") or []}
        if TRASH_PARAM in names:
            return di
    return None


def main():
    ch = LiveChannel(enabled=True); ch.start()
    try:
        info = ch.get_session_info().result(timeout=10)
        tc = info.get("track_count") or 0
        # name -> idx (single-pass)
        name_to_idx = {}
        futs = [ch.get_track_info(t) for t in range(tc)]
        for t, f in enumerate(futs):
            try:
                ti = f.result(timeout=5)
                if ti.get("name"):
                    name_to_idx[ti.get("name")] = t
            except Exception:
                pass

        for track_name in TRACKS_TO_AUTOMATE:
            t_idx = name_to_idx.get(track_name)
            if t_idx is None:
                print(f"[{track_name}] track not found, skipping")
                continue
            trash_di = _find_trash_device(ch, t_idx)
            if trash_di is None:
                print(f"[{track_name}] no Trash device with {TRASH_PARAM!r}, skipping")
                continue
            curves = PER_TRACK_CURVES.get(track_name, {})
            print(f"\n=== {track_name} (T{t_idx}, Trash at [{trash_di}]) — {len(curves)} scenes ===")
            for scene, anchors in curves.items():
                dense = densify(anchors)
                try:
                    ch.set_clip_envelope(
                        clip_track=t_idx, clip_index=scene,
                        target_track=t_idx, target_device=trash_di,
                        target_param=TRASH_PARAM, breakpoints=dense,
                    ).result(timeout=15)
                    lo = min(v for _, v in dense)
                    hi = max(v for _, v in dense)
                    print(f"  S{scene:2d}: {len(anchors)} anchors -> {len(dense)} steps, "
                          f"range {lo:.2f}-{hi:.2f}")
                except Exception as e:
                    print(f"  S{scene:2d}: FAILED: {e}")
    finally:
        ch.stop()


if __name__ == "__main__":
    main()
