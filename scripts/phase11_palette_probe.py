"""Lay out all 70 Live palette colors as labeled empty clips for screenshot mapping.

Fills slots 8..17 across all 7 tracks (70 cells). Each clip is named "cN"
where N = color_index, and its color_index is set to N. Screenshot the grid,
send the image back, and we can build an authoritative palette map.
"""
from __future__ import annotations
import os, time

os.environ.setdefault("LIVE_CHANNEL_ENABLED", "1")

from thelmic.live_channel import LiveChannel

START_SLOT = 8
N_TRACKS = 7
N_COLORS = 70  # 14 hues × 5 rows in Live 12


def main():
    ch = LiveChannel(); ch.start(); time.sleep(0.6)
    try:
        # Ensure enough scenes exist
        needed = START_SLOT + (N_COLORS + N_TRACKS - 1) // N_TRACKS
        info = ch.get_scene_count().result(timeout=3) if hasattr(ch, 'get_scene_count') else None
        current = info.get('scene_count', 8) if info else 8
        while current < needed:
            ch.create_scene(-1).result(timeout=3)
            current += 1
        print(f"Scenes: {current}")
        for idx in range(N_COLORS):
            slot = START_SLOT + (idx // N_TRACKS)
            track = idx % N_TRACKS
            # Empty clip — just need a slot we can color and label
            try:
                ch.clear_clip(track, slot).result(timeout=3)
            except Exception:
                pass
            ch.create_clip(track, slot, length_beats=1.0).result(timeout=5)
            ch.set_clip_name(track, slot, f"c{idx}").result(timeout=3)
            ch.set_clip_color(track, slot, idx).result(timeout=3)
        print(f"Laid out {N_COLORS} palette clips in slots {START_SLOT}..{START_SLOT + N_COLORS//N_TRACKS}")
    finally:
        ch.stop()


if __name__ == "__main__":
    main()
