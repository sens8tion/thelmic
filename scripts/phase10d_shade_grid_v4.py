"""Phase 10d — scene-anchored shading with strength+density nudges.

Each scene has a BASE intensity (its impact rank 0-4). Per-clip row is:
    final_score = clamp(0..4,  scene_base + (strength-1) + (density-1))

So scenes look distinct (different base = different dominant row), and
within a scene clips spread ±2 rows based on their instrument's strength
and how busy they are.

Row mapping (perceptual intensity order):
    score 0 -> row 3 (pale)
    score 1 -> row 0 (bright)
    score 2 -> row 2 (earthy)
    score 3 -> row 1 (deep)
    score 4 -> row 4 (dark)
"""
from __future__ import annotations
import os, time

os.environ.setdefault("LIVE_CHANNEL_ENABLED", "1")

from thelmic.live_channel import LiveChannel

SLOT_COL = {
    0: 8, 1: 5, 2: 7, 3: 9, 4: 3, 5: 0, 6: 0, 7: 1,
}

# Scene base impact (0 = lowest, 4 = peak)
SCENE_BASE = {
    3: 0,   # hollow_pause
    0: 1,   # intro
    2: 2,   # fallthrough
    1: 3,   # motif
    4: 3,   # rebuild_lift
    7: 4,   # anchor_fire
    5: 4,   # payoff_storm (forced)
    6: 4,   # engine_push  (forced)
}

FORCED_ROW = {5: 1, 6: 4}

SCORE_ROW = [3, 0, 2, 1, 4]  # row index per perceptual score

TRACK_STRENGTH = {1: 2, 2: 2, 3: 2, 0: 1, 4: 1, 5: 0, 6: 0}

SCENE_NAMES = {
    0: "intro", 1: "motif", 2: "fallthrough", 3: "hollow_pause",
    4: "rebuild_lift", 5: "payoff_storm", 6: "engine_push", 7: "anchor_fire",
}

# Scene strip color — use the scene's dominant clip color
SCENE_STRIP = {0: 8, 1: 19, 2: 35, 3: 51, 4: 17, 5: 14, 6: 56, 7: 57}


def density_score(n: int) -> int:
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
                    score_str = "forced"
                else:
                    raw = SCENE_BASE[slot] + (TRACK_STRENGTH.get(ti, 1) - 1) + (density_score(count) - 1)
                    score = max(0, min(4, raw))
                    row = SCORE_ROW[score]
                    score_str = f"{raw}->{score}"
                ci = col + row * 14
                ch.set_clip_color(ti, slot, ci).result(timeout=3)
                print(f"  slot{slot}/{name} T{ti}: n={count} score={score_str} row={row} color={ci}")
    finally:
        ch.stop()


if __name__ == "__main__":
    main()
