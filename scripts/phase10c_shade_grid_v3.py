"""Phase 10c — re-shade with full 5-row spread + cleanup palette probe.

Mapping (per scene):
  COLUMN = scene hue family (constant for the scene)
  ROW    = combined intensity score (track-strength + hit-density), spread
           across the 5 perceptual-intensity-ordered rows:
             score 0 -> row 3 (pale)
             score 1 -> row 0 (bright)
             score 2 -> row 2 (earthy)  [the scene base]
             score 3 -> row 1 (deep)
             score 4 -> row 4 (dark)

This makes EVERY scene span its hue across 3-5 visibly distinct shades
based on how busy that clip is and how foundational its instrument is.

Payoff (col 0) and engine_push (col 0) are forced to uniform rows to avoid
the col-0-pink bleed in rows 0 and 3.
"""
from __future__ import annotations
import os, time

os.environ.setdefault("LIVE_CHANNEL_ENABLED", "1")

from thelmic.live_channel import LiveChannel

# scene → hue column
SLOT_COL = {
    0: 8,   # intro:        ocean blue
    1: 5,   # motif:        green
    2: 7,   # fallthrough:  cyan
    3: 9,   # hollow_pause: blue
    4: 3,   # rebuild_lift: yellow
    5: 0,   # payoff_storm: red (forced uniform)
    6: 0,   # engine_push:  dark red (forced uniform)
    7: 1,   # anchor_fire:  orange
}

# Scenes where every clip gets the same row (avoid pink-row bleed in col 0)
FORCED_ROW = {5: 1, 6: 4}

# score (0-4) → row index (perceptual intensity order)
SCORE_ROW = [3, 0, 2, 1, 4]

TRACK_STRENGTH = {1: 2, 2: 2, 3: 2, 0: 1, 4: 1, 5: 0, 6: 0}

SCENE_NAMES = {
    0: "intro", 1: "motif", 2: "fallthrough", 3: "hollow_pause",
    4: "rebuild_lift", 5: "payoff_storm", 6: "engine_push", 7: "anchor_fire",
}

SCENE_STRIP_COLORS = {  # representative single color for the strip
    0: 8, 1: 33, 2: 7, 3: 51, 4: 17, 5: 14, 6: 56, 7: 15,
}


def density_score(n: int) -> int:
    if n >= 33: return 2
    if n <= 8:  return 0
    return 1


def main():
    ch = LiveChannel(); ch.start(); time.sleep(0.6)
    try:
        # 1) Delete palette probe clips in slots 8-17 across 7 tracks
        for slot in range(8, 18):
            for ti in range(7):
                try:
                    ch.clear_clip(ti, slot).result(timeout=2)
                except Exception:
                    pass
        print("Cleared palette probe slots 8-17")

        # 2) Apply v3 shading
        s = ch.get_session_info().result(timeout=3)
        n_tracks = s["track_count"]
        for slot, name in SCENE_NAMES.items():
            col = SLOT_COL[slot]
            ch.set_scene_color(slot, SCENE_STRIP_COLORS[slot]).result(timeout=3)
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
                    score = "forced"
                else:
                    score = TRACK_STRENGTH.get(ti, 1) + density_score(count)
                    row = SCORE_ROW[score]
                ci = col + row * 14
                ch.set_clip_color(ti, slot, ci).result(timeout=3)
                print(f"  slot{slot}/{name} T{ti}: n={count} score={score} row={row} color={ci}")
    finally:
        ch.stop()


if __name__ == "__main__":
    main()
