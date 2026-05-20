"""Slow automation curves on HOOVER_LEAD's Trash Tilt Frequency.

User exposed `B2 Trash Tilt Frequency` on the Trash plugin (T3 device 3)
and asked for me to modulate it — but slowly so the changes are
musical, not jittery.

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


HOOVER_TRACK_NAME = "HOOVER_LEAD"
TRASH_PARAM = "B2 Trash Tilt Frequency"

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


# Per-scene breakpoints: list of [time_in_beats, value] across 32-beat clip
# Each scene's curve uses 5-6 points placed ~6-8 beats apart.
SCENE_CURVES = {
    # --- BASE band ---
    3: [
        [0.0,  0.30],   # bar 1: clean entry
        [8.0,  0.35],   # bar 3
        [16.0, 0.40],   # bar 5: midpoint slight rise
        [24.0, 0.45],   # bar 7
        [32.0, 0.50],   # bar 8 end: lifted into S4
    ],
    4: [
        [0.0,  0.50],
        [8.0,  0.60],
        [16.0, 0.70],
        [24.0, 0.78],
        [32.0, 0.85],
    ],
    5: [
        [0.0,  0.75],   # enter dirty
        [8.0,  0.68],
        [16.0, 0.55],   # midpoint clean shift
        [24.0, 0.45],
        [32.0, 0.40],
    ],
    7: [
        [0.0,  0.75],
        [8.0,  0.95],
        [16.0, 0.80],   # dip — breathing room mid-scene
        [24.0, 0.92],
        [32.0, 0.95],
    ],
    # --- DEPRAVED band — all push higher ---
    11: [   # HOOVER_DROP_DEFILED
        [0.0,  0.40],
        [8.0,  0.48],
        [16.0, 0.55],
        [24.0, 0.60],
        [32.0, 0.65],
    ],
    12: [   # ANNIHILATION_UNSEALED
        [0.0,  0.65],
        [8.0,  0.75],
        [16.0, 0.82],
        [24.0, 0.88],
        [32.0, 0.95],
    ],
    13: [   # BREAKDOWN_RANCID
        [0.0,  0.85],   # max dirty entry
        [8.0,  0.75],
        [16.0, 0.62],
        [24.0, 0.52],
        [32.0, 0.50],
    ],
    15: [   # NUCLEAR_TERMINAL
        [0.0,  0.90],
        [8.0,  0.95],
        [16.0, 0.90],
        [24.0, 0.97],
        [32.0, 1.00],
    ],
}


def main():
    ch = LiveChannel(enabled=True); ch.start()
    try:
        info = ch.get_session_info().result(timeout=5)
        tc = info.get("track_count") or 0
        # Find HOOVER_LEAD + Trash device index
        hoover_idx = None
        for t in range(tc):
            ti = ch.get_track_info(t).result(timeout=3)
            if ti.get("name") == HOOVER_TRACK_NAME:
                hoover_idx = t
                break
        if hoover_idx is None:
            print(f"ERROR: {HOOVER_TRACK_NAME} not found")
            return
        ti = ch.get_track_info(hoover_idx).result(timeout=3)
        trash_idx = None
        for di, d in enumerate(ti.get("devices") or []):
            if d.get("name") == "Trash" or d.get("class_name") == "PluginDevice" and "Trash" in (d.get("name") or ""):
                # disambiguate from Serum 2 — both are PluginDevice
                if d.get("name") == "Trash":
                    trash_idx = di
                    break
        if trash_idx is None:
            # fallback: look for the param in each device
            for di, d in enumerate(ti.get("devices") or []):
                info = ch.get_device_info(hoover_idx, di).result(timeout=5)
                names = {p.get("name","") for p in info.get("parameters") or []}
                if TRASH_PARAM in names:
                    trash_idx = di
                    break
        if trash_idx is None:
            print(f"ERROR: Trash device with '{TRASH_PARAM}' not found on T{hoover_idx}")
            return
        print(f"HOOVER_LEAD = T{hoover_idx}, Trash device = [{trash_idx}]")
        print(f"Target param: {TRASH_PARAM!r}\n")

        # Apply each scene's envelope — densify anchors to 32 steps so the
        # staircase reads as a smooth ramp at 190 BPM
        for scene, anchors in SCENE_CURVES.items():
            dense = densify(anchors)
            try:
                ch.set_clip_envelope(
                    clip_track=hoover_idx, clip_index=scene,
                    target_track=hoover_idx, target_device=trash_idx,
                    target_param=TRASH_PARAM, breakpoints=dense,
                ).result(timeout=15)
                lo = min(v for _, v in dense)
                hi = max(v for _, v in dense)
                print(f"  S{scene:2d}: {len(anchors)} anchors -> {len(dense)} dense steps, range {lo:.2f}-{hi:.2f}")
            except Exception as e:
                print(f"  S{scene}: FAILED: {e}")
    finally:
        ch.stop()


if __name__ == "__main__":
    main()
