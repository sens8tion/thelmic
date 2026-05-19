"""Phase 10e — within-scene variation via max() instead of sum.

Score = scene_base + max(strength, density), clamped 0..4.
max() removes the strength/density anti-correlation that was collapsing
the previous v4 mapping. Within each scene clips now spread 2-3 rows.
"""
from __future__ import annotations
import os, time

os.environ.setdefault("LIVE_CHANNEL_ENABLED", "1")

from thelmic.live_channel import LiveChannel

SLOT_COL = {0:8, 1:5, 2:7, 3:9, 4:3, 5:0, 6:0, 7:1}

# Tightened bases so anchor_fire doesn't saturate at row 4
SCENE_BASE = {3:0, 0:1, 2:1, 1:2, 4:2, 7:2, 5:4, 6:4}

FORCED_ROW = {5:1, 6:4}
SCORE_ROW = [3, 0, 2, 1, 4]
TRACK_STRENGTH = {1:2, 2:2, 3:2, 0:1, 4:1, 5:0, 6:0}

SCENE_NAMES = {0:"intro", 1:"motif", 2:"fallthrough", 3:"hollow_pause",
               4:"rebuild_lift", 5:"payoff_storm", 6:"engine_push", 7:"anchor_fire"}
SCENE_STRIP = {0:8, 1:33, 2:35, 3:51, 4:17, 5:14, 6:56, 7:29}


def density_score(n):
    if n >= 33: return 2
    if n <= 8:  return 0
    return 1


def main():
    ch = LiveChannel(); ch.start(); time.sleep(0.6)
    try:
        s = ch.get_session_info().result(timeout=3)
        n_tracks = s["track_count"]
        for slot, name in SCENE_NAMES.items():
            col = SLOT_COL[slot]
            ch.set_scene_color(slot, SCENE_STRIP[slot]).result(timeout=3)
            ch.set_scene_name(slot, name).result(timeout=3)
            for ti in range(n_tracks):
                try:
                    r = ch.get_clip_notes(ti, slot).result(timeout=3)
                    count = len(r.get("notes", []))
                except Exception:
                    continue
                if count == 0:
                    continue
                if slot in FORCED_ROW:
                    row = FORCED_ROW[slot]
                    info = "forced"
                else:
                    sd = max(TRACK_STRENGTH.get(ti, 1), density_score(count))
                    raw = SCENE_BASE[slot] + sd
                    score = max(0, min(4, raw))
                    row = SCORE_ROW[score]
                    info = f"max(s,d)={sd} raw={raw} score={score}"
                ci = col + row * 14
                ch.set_clip_color(ti, slot, ci).result(timeout=3)
                print(f"  slot{slot}/{name} T{ti}: n={count} {info} row={row} color={ci}")
    finally:
        ch.stop()


if __name__ == "__main__":
    main()
