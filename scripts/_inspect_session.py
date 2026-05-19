"""Quick session inspector — list all tracks, devices, and clip names+files."""
from __future__ import annotations
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from thelmic.live_channel import LiveChannel


def main():
    ch = LiveChannel(enabled=True); ch.start()
    try:
        info = ch.get_session_info().result(timeout=5)
        tc = info.get("track_count") or 0
        print(f"tracks: {tc}\n")
        for i in range(tc):
            ti = ch.get_track_info(i).result(timeout=3)
            devs = ti.get("devices") or []
            dev_names = [d.get("name") for d in devs]
            print(f"T{i}: {ti.get('name')!r:30s}  devices={dev_names}")
            clips = ch._enqueue("get_track_clips", {"track_index": i}).result(timeout=5)
            for c in (clips.get("clips") or []):
                if c.get("has_clip"):
                    fp = c.get("file_path") or ""
                    fp_short = os.path.basename(fp) if fp else ""
                    length = c.get("length") or c.get("length_beats") or "?"
                    print(f"    slot {c.get('slot_index')}: "
                          f"name={c.get('name')!r}  "
                          f"file={fp_short!r}  "
                          f"len={length}")
    finally:
        ch.stop()


if __name__ == "__main__":
    main()
