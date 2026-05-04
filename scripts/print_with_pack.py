"""Print an aesthetic pack's arrangement to Live's arrangement view.

Usage:
    python scripts/print_with_pack.py [pack_name]

  pack_name defaults to dnb_jungle. Other built-in packs:
    - dnb_jungle    (ragga → Rotterdam arc, BuildDropRelease grammar)
    - ambient_drone (slow textural transformation, StaticDrone grammar)
    - idm_glitch    (rotational variations, Rotational grammar)

The pack is loaded entirely via its module — its arrangement.build_timeline()
returns a Timeline that the bridge engine walks. The bridge knows nothing
about the genre; the pack knows nothing about LOM RPC mechanics.
"""
from __future__ import annotations
import os, sys, time, importlib
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("LIVE_CHANNEL_ENABLED", "1")

from thelmic.bridge import (
    LiveChannel, health_check, hard_reset, arm_take, disarm_take,
    fire_arrangement, ms_to_beats,
)


def main(pack_name: str = "dnb_jungle"):
    pack = importlib.import_module(f"thelmic.aesthetics.{pack_name}")
    print(f"Active pack: {pack.PACK_NAME}")
    print(f"  grammar:  {pack.PACK_GRAMMAR.name}")
    print(f"  bpm:      {pack.PACK_BPM}")
    print(f"  key root: MIDI {pack.PACK_KEY_ROOT}")

    ch = LiveChannel(lower_priority=False); ch.start()
    try:
        # If the pack declares EXPECTED_TRACKS, use them to validate the
        # right session is loaded (not just any 4-track fresh project).
        expected = getattr(pack, "EXPECTED_TRACKS", None)
        ok, detail = health_check(ch,
                                    expected_track_names=list(expected) if expected else None,
                                    min_tracks=len(expected) if expected else 4)
        if not ok:
            print(f"HEALTH CHECK FAILED: {detail}")
            return
        if isinstance(detail, dict):
            print(f"  health OK — {len(detail)} expected tracks present: {list(detail.keys())}")
        else:
            print(f"  health OK")

        sess = ch.get_session_info().result(timeout=5)
        bpm = sess["tempo"]
        bar_seconds = 60.0 / bpm * 4
        OUTRO_LET_REVERB_RING_MS = getattr(pack, "OUTRO_LET_REVERB_RING_MS", 800)

        # Build the pack's timeline
        timeline = pack.build_timeline()
        total_bars = timeline.total_bars()
        print(f"  timeline: {len(timeline.events)} events, "
              f"{total_bars} bars (~{total_bars * bar_seconds / 60:.1f} min @ {bpm}bpm)")

        # Apply pack-specific clip preparations if defined (e.g. anticipation fills)
        if hasattr(pack, "prepare_clips"):
            print("\n  preparing clips...")
            pack.prepare_clips(ch)

        print("\n  hard reset + arming...")
        hard_reset(ch)
        arm_take(ch, start_bar=0.0, launch_quant_bars=1.0, metronome=False)

        print(f"\n  printing to arrangement...")
        elapsed = fire_arrangement(ch, timeline, start_bar=0.0,
                                     bar_seconds=bar_seconds)

        # Tail: let final ramp draw + reverb ring
        beat_seconds = bar_seconds / 4.0
        tail_seconds = max(6 * beat_seconds, OUTRO_LET_REVERB_RING_MS / 1000.0) + 1.0
        time.sleep(tail_seconds)
        disarm_take(ch, restore_quant_bars=8.0)

        print(f"\nPRINT COMPLETE — {elapsed} bars / "
              f"~{elapsed * bar_seconds / 60:.1f} min")
    finally:
        ch.stop()


if __name__ == "__main__":
    main(pack_name=sys.argv[1] if len(sys.argv) > 1 else "dnb_jungle")
