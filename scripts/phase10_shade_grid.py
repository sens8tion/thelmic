"""Phase 10 — shade the session view by (impact × instrument × density).

Row impact (slot) → hue family in Live's color palette
Instrument strength (track) → which brightness band (saturated / medium / pastel)
Hit density (notes per clip) → shift band darker (dense) or lighter (sparse)

Scene strip itself gets the pure impact hue so the row reads coherently
across all tracks.
"""
from __future__ import annotations
import os, time

os.environ.setdefault("LIVE_CHANNEL_ENABLED", "1")

from thelmic.live_channel import LiveChannel


# ── Slot → hue family (Live palette column 0-13) ──────────────────────────
# 0 = red, 1 = orange, 2 = yellow, 3 = yellow-green, 4 = green,
# 5 = teal, 6 = green-cyan, 7 = cyan, 8 = light-blue, 9 = blue,
# 10 = violet, 11 = magenta, 12 = pink, 13 = gray/white
SLOT_HUE = {
    3: 9,    # hollow_pause   — deep blue (lowest impact)
    0: 8,    # intro          — light blue
    2: 6,    # fallthrough    — green-cyan
    1: 4,    # motif          — green
    4: 2,    # rebuild_lift   — yellow/amber
    7: 1,    # anchor_fire    — orange
    5: 0,    # payoff_storm   — red
    6: 0,    # engine_push    — same red but forced to darkest band → crimson
}

# Force engine_push into a denser/darker band for crimson differentiation
SLOT_BAND_OVERRIDE = {6: 0}  # engine_push always uses band 0 (darkest variant)

# ── Track → instrument strength → base band ───────────────────────────────
# Live palette is 14 hues × 5 brightness rows = 70 colors.
# Row 0 = saturated/dark, Row 4 = palest. Lower index = stronger.
STRENGTH_BAND = {
    1: 0,    # KIK_HOOF       strong → saturated
    2: 0,    # SUB_BOOM (T2)  strong
    3: 0,    # SUB_BOOM (T3)  strong
    0: 1,    # KLIK_SAINT     moderate
    4: 1,    # PIPER_PLUNGE   moderate
    5: 2,    # MICA_THROB     weak → pastel
    6: 2,    # MOIRE_DRIFT    weak
}

# ── Density bucket → band shift ───────────────────────────────────────────
def density_shift(note_count: int) -> int:
    if note_count >= 33:
        return -1      # dense → darker (lower band)
    if note_count <= 8:
        return +1      # sparse → lighter (higher band)
    return 0           # medium

PALETTE_COLS = 14
PALETTE_ROWS = 5


def color_index(slot: int, track: int, note_count: int) -> int:
    hue = SLOT_HUE[slot]
    base_band = STRENGTH_BAND[track]
    shift = density_shift(note_count)
    band = max(0, min(PALETTE_ROWS - 1, base_band + shift))
    if slot in SLOT_BAND_OVERRIDE:
        band = SLOT_BAND_OVERRIDE[slot]
    return hue + band * PALETTE_COLS


SCENE_NAMES = {
    0: "intro",
    1: "motif",
    2: "fallthrough",
    3: "hollow_pause",
    4: "rebuild_lift",
    5: "payoff_storm",
    6: "engine_push",
    7: "anchor_fire",
}


def main():
    ch = LiveChannel(); ch.start(); time.sleep(0.6)
    try:
        s = ch.get_session_info().result(timeout=3)
        n_tracks = s["track_count"]

        for slot, name in SCENE_NAMES.items():
            # Scene strip: pure hue at saturated band 0
            scene_color = SLOT_HUE[slot] + 0 * PALETTE_COLS
            try:
                ch.set_scene_color(slot, scene_color).result(timeout=3)
                ch.set_scene_name(slot, name).result(timeout=3)
            except Exception as e:
                print(f"[scene {slot}] err: {e}")
                continue

            # Per-clip shading
            for ti in range(n_tracks):
                try:
                    r = ch.get_clip_notes(ti, slot).result(timeout=3)
                    count = len(r.get("notes", []))
                except Exception:
                    continue
                if count == 0:
                    continue
                ci = color_index(slot, ti, count)
                try:
                    ch.set_clip_color(ti, slot, ci).result(timeout=3)
                    print(f"  slot{slot} T{ti}: {count} notes -> color {ci}")
                except Exception as e:
                    print(f"  slot{slot} T{ti}: color err {e}")
    finally:
        ch.stop()


if __name__ == "__main__":
    main()
