"""SUBBONK ends mid-sample because clips loop and get cut when the
section changes. Fix: turn off looping so each clip plays its sample
exactly once through and ends naturally at sample boundary."""
from __future__ import annotations
import os, sys
os.environ.setdefault("LIVE_CHANNEL_ENABLED", "1")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from thelmic.mediated_session import open_session
from thelmic.agent_helpers import find_track


def main():
    with open_session(name="subbonk-loop-off",
                      expected_tracks=["SUBBONK"]) as sess:
        t = find_track(sess.raw_ch, "SUBBONK")
        if t is None:
            sess.note("SUBBONK missing"); return
        applied = 0
        for slot in range(17):
            try:
                r = sess.raw_ch.set_clip_loop(t, slot, False).result(timeout=3)
                applied += 1
                msg = f"  T{t} SUBBONK S{slot}: looping=False"
                print(msg); sess.note(msg)
            except Exception as e:
                if "No clip" in str(e):
                    continue
                print(f"  T{t} SUBBONK S{slot}: {e}")
        print(f"\n{applied} SUBBONK clips set to loop=False (play sample once, end at sample boundary)")


if __name__ == "__main__":
    main()
