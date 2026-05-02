"""Prep the arrangement for a SoundCloud render.

Sets the arrangement loop region to cover the full printed track + tail
so File > Export Audio/Video uses the right bounds. Live's Export is a
UI-only dialog (no API), so this script preps state and prints the
exact click sequence."""
from __future__ import annotations
import os, sys
os.environ.setdefault("LIVE_CHANNEL_ENABLED", "1")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from thelmic.mediated_session import open_session

# Match arrangement_record's ARRANGEMENT total: 312 bars + ~3s tail
TOTAL_BARS = 312
TAIL_BARS = 4    # crash-decay + reverb tail margin


def main():
    with open_session(name="prep-soundcloud-cut") as sess:
        info = sess.raw_ch.get_session_info().result(timeout=5)
        bpm = info.get("tempo", 165.0)
        bar_seconds = 60.0 / bpm * 4
        total_seconds = (TOTAL_BARS + TAIL_BARS) * bar_seconds
        sess.note(f"prepping render: {TOTAL_BARS}+{TAIL_BARS} bars = {total_seconds/60:.2f} min @ {bpm}bpm")

        # Set arrangement loop bounds (in BEATS — 4 per bar)
        loop_end_beats = (TOTAL_BARS + TAIL_BARS) * 4.0
        try:
            sess.raw_ch.set_arrangement_loop(0.0, loop_end_beats, True).result(timeout=5)
            print(f"  arrangement loop: 0 → bar {TOTAL_BARS + TAIL_BARS} ({loop_end_beats} beats)")
        except Exception as e:
            print(f"  set_arrangement_loop fail: {e}")
            sess.note(f"loop fail: {e}", kind="error")

        sess.snapshot("ready-for-render")
        print()
        print("=" * 60)
        print("READY FOR SOUNDCLOUD CUT")
        print("=" * 60)
        print(f"  bpm:      {bpm}")
        print(f"  length:   {total_seconds/60:.2f} min ({total_seconds:.1f}s)")
        print(f"  bars:     {TOTAL_BARS} + {TAIL_BARS} tail = {TOTAL_BARS + TAIL_BARS}")
        print()
        print("In Live, hit Ctrl+Shift+R (Export Audio/Video):")
        print("  Rendered Track:    Master")
        print("  Render Start:      1.1.1")
        print(f"  Render Length:     {TOTAL_BARS + TAIL_BARS}.1.1")
        print("  Sample Rate:       44100 Hz")
        print("  Bit Depth:         24")
        print("  PCM:               WAV")
        print("  Convert to Mp3:    Off  (lossless to SoundCloud, they'll transcode)")
        print("  Normalize:         Off  (preserve master glue tonality)")
        print("  Render as Loop:    Off")
        print("  Create Analysis:   Off")
        print("  → Save as e.g. thelmic_jungle_v1.wav")
        print()
        print("SoundCloud upload notes:")
        print("  • title:     irreverent — go with the vibe (e.g. 'breakcore therapy')")
        print("  • genre:     Drum & Bass / Jungle / Breakcore (multi tag)")
        print("  • bpm:       165")
        print("  • key:       G minor")
        print("  • tags:      jungle, breakcore, gabber, agentic, hand-built")


if __name__ == "__main__":
    main()
