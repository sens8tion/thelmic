"""Phase 10b — re-shade with corrected palette mapping.

Live 12 palette is 14 columns × 5 rows. Empirical column → hue map:
  0 pink/red, 1 orange, 2 peach, 3 yellow, 4 lime, 5 green, 6 teal,
  7 cyan, 8 ocean blue, 9 blue, 10 purple, 11 magenta, 12 dark-magenta,
  13 gray/white.
Row order (by perceived intensity ascending): row 3 pale, row 0 bright,
row 2 earthy, row 1 deep, row 4 dark.
"""
from __future__ import annotations
import os, time

os.environ.setdefault("LIVE_CHANNEL_ENABLED", "1")

from thelmic.live_channel import LiveChannel


# Hue column per slot
SLOT_COL = {
    3: 9,   # hollow_pause
    0: 8,   # intro
    2: 7,   # fallthrough
    1: 5,   # motif
    4: 3,   # rebuild_lift
    7: 1,   # anchor_fire
    5: 0,   # payoff_storm (forced row 1)
    6: 0,   # engine_push  (forced row 4)
}

# Slots where every clip gets the same row (avoid pink-row bleed in col 0)
FORCED_ROW = {5: 1, 6: 4}

# Intensity score → row (ordered weakest visual to strongest visual)
INTENSITY_ROW = [3, 0, 2, 1, 4]

# Track → strength score 0/1/2
TRACK_STRENGTH = {
    1: 2, 2: 2, 3: 2,        # kick + both subs: strong
    0: 1, 4: 1,              # klik + piper: moderate
    5: 0, 6: 0,              # mica + moire: weak
}


def density_score(n: int) -> int:
    if n >= 33: return 2
    if n <= 8:  return 0
    return 1


SCENE_NAMES = {
    0: "intro", 1: "motif", 2: "fallthrough", 3: "hollow_pause",
    4: "rebuild_lift", 5: "payoff_storm", 6: "engine_push", 7: "anchor_fire",
}

# Scene strip color: row 1 (deep saturated) for high impact, row 0 (bright)
# for medium/low — pick a representative single tone per scene.
SCENE_STRIP_ROW = {
    0: 0, 1: 1, 2: 1, 3: 0, 4: 1, 5: 1, 6: 4, 7: 1,
}


def main():
    ch = LiveChannel(); ch.start(); time.sleep(0.6)
    try:
        s = ch.get_session_info().result(timeout=3)
        n_tracks = s["track_count"]

        for slot, name in SCENE_NAMES.items():
            col = SLOT_COL[slot]
            strip_color = col + SCENE_STRIP_ROW[slot] * 14
            ch.set_scene_color(slot, strip_color).result(timeout=3)
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
                else:
                    score = TRACK_STRENGTH.get(ti, 1) + density_score(count)
                    row = INTENSITY_ROW[score]
                ci = col + row * 14
                ch.set_clip_color(ti, slot, ci).result(timeout=3)
                print(f"  slot{slot}/{name} T{ti}: n={count} score={(TRACK_STRENGTH.get(ti,1)+density_score(count)) if slot not in FORCED_ROW else 'forced'} -> row={row} color={ci}")
    finally:
        ch.stop()


if __name__ == "__main__":
    main()
