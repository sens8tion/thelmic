"""Phase 12g — move BARK clips out of scenes 0-7 into their own row range 8-15.

Scenes 0-7 leave T7 empty so scene-fire stops bark instead of firing it.
User manually launches a bark variant from scenes 8-15 when they want it.

Mapping:
  scene 0 intro          → bark clip lives in slot 8
  scene 1 motif          → slot 9
  scene 2 fallthrough    → slot 10
  scene 3 hollow_pause   → slot 11
  scene 4 rebuild_lift   → slot 12
  scene 5 payoff_storm   → slot 13
  scene 6 engine_push    → slot 14
  scene 7 anchor_fire    → slot 15

T7 in scenes 0-7 left empty → firing scene N auto-stops T7's currently playing
bark clip. Bark clips have loop=off so they fire once when clicked.
"""
from __future__ import annotations
import os, time

os.environ.setdefault("LIVE_CHANNEL_ENABLED", "1")

from thelmic.live_channel import LiveChannel

T_BARK = 7

BARK_NAMES = ["bark_intro", "bark_motif", "bark_fallthrough", "bark_hollow",
              "bark_rebuild", "bark_payoff", "bark_engine", "bark_anchor"]


def main():
    ch = LiveChannel(); ch.start(); time.sleep(0.6)
    try:
        # Ensure we have enough scenes (need at least 16)
        info = ch.get_scene_count().result(timeout=3) if hasattr(ch, 'get_scene_count') else None
        current = info.get('scene_count', 8) if info else 8
        while current < 16:
            ch.create_scene(-1).result(timeout=3)
            current += 1

        # 1) Read each existing bark clip's notes, then re-create in target slot
        for src_slot in range(8):
            try:
                r = ch.get_clip_notes(T_BARK, src_slot).result(timeout=3)
                notes_data = r.get('notes', [])
            except Exception:
                notes_data = []
            if not notes_data:
                print(f"  src slot {src_slot}: empty, skip")
                continue
            dst_slot = src_slot + 8

            # Re-build payload from read notes (drop note_id and prob defaults)
            payload = [{"pitch": n["pitch"], "start_time": n["start_time"],
                        "duration": n["duration"], "velocity": n["velocity"]}
                       for n in notes_data]

            # Create dst clip
            try:
                ch.clear_clip(T_BARK, dst_slot).result(timeout=3)
            except Exception:
                pass
            ch.create_clip(T_BARK, dst_slot, length_beats=16.0).result(timeout=5)
            ch.set_clip_name(T_BARK, dst_slot, BARK_NAMES[src_slot]).result(timeout=3)
            ch.add_notes_to_clip(T_BARK, dst_slot, payload).result(timeout=5)
            ch.set_clip_loop(T_BARK, dst_slot, False).result(timeout=3)

            # Delete src
            ch.clear_clip(T_BARK, src_slot).result(timeout=3)
            print(f"  slot {src_slot} -> slot {dst_slot} ({BARK_NAMES[src_slot]}, {len(payload)} chops)")
    finally:
        ch.stop()


if __name__ == "__main__":
    main()
