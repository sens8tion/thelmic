"""Phase 10f — column-shift shading for CRANKY_HODGKIN (uses bridge helper).

The algorithm lives in `thelmic.bridge.helpers.shading`. This script is
just the recipe for THIS track's scenes + track strength assignments.
"""
from __future__ import annotations
import os, time

os.environ.setdefault("LIVE_CHANNEL_ENABLED", "1")

from thelmic.live_channel import LiveChannel
from thelmic.bridge.helpers import SceneShading, ShadingConfig, apply_shading


CONFIG = ShadingConfig(
    scenes={
        # slot: (identity_col, row, col_range)
        3: SceneShading(9, 3, (7, 10)),    # hollow_pause — pale blue
        0: SceneShading(8, 0, (6, 10)),    # intro        — bright ocean blue
        2: SceneShading(7, 2, (5,  9)),    # fallthrough  — earthy cyan
        1: SceneShading(5, 1, (3,  7)),    # motif        — deep green
        4: SceneShading(3, 1, (1,  5)),    # rebuild_lift — deep yellow
        7: SceneShading(1, 1, (0,  3)),    # anchor_fire  — deep orange
        5: SceneShading(0, 1, None),       # payoff_storm — uniform red (col 0 in row 1)
        6: SceneShading(0, 4, None),       # engine_push  — uniform maroon
    },
    track_strength={
        1: 2, 2: 2, 3: 2,   # KIK_HOOF + both SUB_BOOMs: foundation
        0: 1, 4: 1, 7: 1,   # KLIK_SAINT + PIPER_PLUNGE + BARK_INTONE: moderate
        5: 0, 6: 0, 8: 0,   # MICA_THROB + MOIRE_DRIFT + DRONE_LARYNX: weak/atmospheric
    },
    scene_names={
        0: "intro", 1: "motif", 2: "fallthrough", 3: "hollow_pause",
        4: "rebuild_lift", 5: "payoff_storm", 6: "engine_push", 7: "anchor_fire",
    },
)


def main():
    ch = LiveChannel(); ch.start(); time.sleep(0.6)
    try:
        summary = apply_shading(ch, CONFIG)
        for slot, clips in summary.items():
            print(f"slot {slot}: {len(clips)} clips colored")
            for ti, ci, n in clips:
                print(f"  T{ti}: n={n} color={ci}")
    finally:
        ch.stop()


if __name__ == "__main__":
    main()
