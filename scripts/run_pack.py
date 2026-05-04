"""Run an aesthetic pack through its lifecycle phases.

  python scripts/run_pack.py [pack_name] [--phases p1,p2,...] [--skip-drops]

Phases (all run in order if not specified):
  setup     — ensure required devices / instruments are present
  pull      — pull Splice samples (no-op if MCP unavailable)
  compose   — write the pack's MIDI patterns into session-view clips
  mix       — frequency separation + audio fades + loop=False where needed
  prepare   — pre-print transforms (anticipation fills, decay tails)
  preview   — fire scenes in session view (NO record) — audition only
  print     — fire arrangement, capture into arrangement automation

Examples:
  # Full lifecycle: setup → pull → compose → mix → prepare → preview → print
  python scripts/run_pack.py dnb_jungle

  # Just preview the existing content
  python scripts/run_pack.py dnb_jungle --phases preview

  # Re-compose + mix + prepare, audition, then commit-print
  python scripts/run_pack.py dnb_jungle --phases compose,mix,prepare,preview,print

  # Audition the structure without the drops
  python scripts/run_pack.py dnb_jungle --phases preview --skip-drops

  # Just print without rebuilding (assumes content already there)
  python scripts/run_pack.py dnb_jungle --phases print
"""
from __future__ import annotations
import os, sys, time, argparse, importlib
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("LIVE_CHANNEL_ENABLED", "1")

from thelmic.bridge import (
    LiveChannel, health_check, hard_reset, arm_take, disarm_take,
    fire_arrangement,
)


ALL_PHASES = ("setup", "pull", "compose", "mix", "prepare", "preview", "print")


def run(pack_name: str, phases: list[str], skip_drops: bool = False):
    pack = importlib.import_module(f"thelmic.aesthetics.{pack_name}")
    print(f"=" * 60)
    print(f"Pack:    {pack.PACK_NAME}")
    print(f"Grammar: {pack.PACK_GRAMMAR.name}")
    print(f"BPM:     {pack.PACK_BPM}")
    print(f"Phases:  {' → '.join(phases)}")
    print(f"=" * 60)

    ch = LiveChannel(lower_priority=False); ch.start()
    try:
        # Validate session. If "setup" is in phases, bootstrap will
        # create missing tracks — so we ONLY enforce track-name presence
        # for non-setup runs (where the pack assumes content already
        # exists and is just printing / previewing).
        expected = getattr(pack, "EXPECTED_TRACKS", None)
        if "setup" in phases:
            print(f"  [health] skipped — setup will bootstrap missing tracks")
        else:
            ok, detail = health_check(ch,
                                        expected_track_names=list(expected) if expected else None,
                                        min_tracks=len(expected) if expected else 4)
            if not ok:
                print(f"\nHEALTH CHECK FAILED: {detail}")
                print("\nEither load the pack's expected session, or re-run with --phases setup,...")
                return
            if isinstance(detail, dict):
                print(f"  health OK — {len(detail)} expected tracks present")
            else:
                print(f"  health OK")

        roles = None

        if "setup" in phases:
            roles = pack.setup_session(ch)

        if "pull" in phases:
            pack.pull_samples(ch)

        if "compose" in phases:
            pack.compose_clips(ch, roles=roles)

        if "mix" in phases:
            pack.configure_mix(ch, roles=roles)

        if "prepare" in phases:
            pack.prepare_clips(ch, roles=roles)

        if "preview" in phases:
            pack.preview_session(ch, hold_bars_per_scene=8.0, skip_drops=skip_drops)

        if "print" in phases:
            print("\n[print] arming session_record + walking timeline...")
            sess = ch.get_session_info().result(timeout=5)
            bpm = sess["tempo"]
            bar_seconds = 60.0 / bpm * 4
            timeline = pack.build_timeline()
            print(f"  timeline: {len(timeline.events)} events, "
                  f"{timeline.total_bars()} bars (~{timeline.total_bars() * bar_seconds / 60:.1f} min @ {bpm}bpm)")
            hard_reset(ch)
            arm_take(ch, start_bar=0.0, launch_quant_bars=1.0, metronome=False)
            elapsed = fire_arrangement(ch, timeline, start_bar=0.0,
                                         bar_seconds=bar_seconds)
            beat_seconds = bar_seconds / 4.0
            tail_seconds = max(6 * beat_seconds,
                                getattr(pack, "OUTRO_LET_REVERB_RING_MS", 800) / 1000.0) + 1.0
            time.sleep(tail_seconds)
            disarm_take(ch, restore_quant_bars=8.0)
            print(f"\n[print] COMPLETE — {elapsed} bars / "
                  f"~{elapsed * bar_seconds / 60:.1f} min")

        print("\n" + "=" * 60)
        print("Lifecycle complete.")
        print("=" * 60)
    finally:
        ch.stop()


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pack_name", nargs="?", default="dnb_jungle")
    ap.add_argument("--phases", default=",".join(ALL_PHASES),
                     help="comma-separated subset of " + ", ".join(ALL_PHASES))
    ap.add_argument("--skip-drops", action="store_true",
                     help="preview without firing drop scenes")
    args = ap.parse_args()

    requested = [p.strip() for p in args.phases.split(",") if p.strip()]
    invalid = [p for p in requested if p not in ALL_PHASES]
    if invalid:
        print(f"Unknown phase(s): {invalid}")
        print(f"Valid phases: {ALL_PHASES}")
        sys.exit(2)
    # Preserve order of ALL_PHASES even if user lists out of order
    phases = [p for p in ALL_PHASES if p in requested]

    run(args.pack_name, phases, skip_drops=args.skip_drops)


if __name__ == "__main__":
    main()
