"""JUNGLE RESET - strip the section-board set down to six lanes.

Run it on a Save-As copy: the original set keeps the section boards. Every MIDI clip's notes are archived
first, to tracks/2026-09-16_jungle_boards_clips.json.

  Lanes: SPINE-TINGLER, AMEN-DMENT, COLD-CUTS, CHOPPER, THROW-UP, F-HOLE (the sub, later replaced by BOO-MERANGUE).
  The MIDImix is mapped natively by the user; this script no longer binds it.

    python scripts/jungle_reset.py            # dry run: what would be deleted, kept and added
    python scripts/jungle_reset.py --go       # do it
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

os.environ.setdefault("LIVE_CHANNEL_ENABLED", "1")
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(SCRIPTS_DIR)
sys.path.insert(0, REPO)
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

ARCHIVE = os.path.join(REPO, "tracks", "2026-09-16_jungle_boards_clips.json")
STRIPS = ["SPINE-TINGLER", "AMEN-DMENT", "COLD-CUTS", "CHOPPER", "THROW-UP", "F-HOLE"]
BREAKS = ["AMEN-DMENT", "COLD-CUTS", "CHOPPER"]
ROWS = 8
COLOR = {"SPINE-TINGLER": 14, "AMEN-DMENT": 15, "COLD-CUTS": 15, "CHOPPER": 15, "THROW-UP": 17, "F-HOLE": 9}


def track_names(ch) -> list[str]:
    n = ch.get_session_info().result(timeout=5)["track_count"]
    return [ch.get_track_info(i).result(timeout=5)["name"] for i in range(n)]


def index_of(ch, name) -> int:
    return track_names(ch).index(name)


# ---------------------------------------------------------------- archive
def archive(ch):
    if os.path.exists(ARCHIVE):
        print(f"  archive already written: {os.path.relpath(ARCHIVE, REPO)} (left alone)")
        return
    out = []
    for t, name in enumerate(track_names(ch)):
        listing = ch.get_track_clips(t).result(timeout=10)
        for clip in listing["clips"]:
            entry = {"track": name, "track_index": t, "slot": clip["slot"], "name": clip["name"],
                     "length": clip["length"], "audio": clip["is_audio"]}
            if not clip["is_audio"]:
                got = ch.get_clip_notes(t, clip["slot"]).result(timeout=10)
                notes = got.get("notes", got) if isinstance(got, dict) else got
                entry["notes"] = [{k: n[k] for k in ("pitch", "start_time", "duration", "velocity", "probability")
                                   if k in n} for n in notes]
            out.append(entry)
    with open(ARCHIVE, "w") as fh:
        json.dump(out, fh, indent=0)
    print(f"  {len(out)} clips archived to {os.path.relpath(ARCHIVE, REPO)}")


# ---------------------------------------------------------------- strip
def strip_tracks(ch, go):
    names = track_names(ch)
    missing = [s for s in STRIPS if s not in names]
    if missing:
        raise SystemExit(f"missing lanes {missing}: is this the section-board set?")
    doomed = [(i, nm) for i, nm in enumerate(names) if nm not in STRIPS or names.index(nm) != i]
    print(f"  keep:   {', '.join(nm for nm in names if nm in STRIPS)}")
    print(f"  delete: {', '.join(nm for _, nm in doomed)}")
    if not go:
        return
    for i, nm in reversed(doomed):
        if track_names(ch)[i] != nm:
            raise SystemExit(f"track {i} is no longer {nm}: stopping")
        ch.delete_track(i).result(timeout=20)
    print(f"  tracks now: {', '.join(track_names(ch))}")


def strip_scenes(ch, go):
    have = ch.get_scene_count().result(timeout=5)["count"]
    print(f"  scenes: {have} -> {ROWS}, every clip cleared, names cleared")
    if not go:
        return
    ch.stop_all_clips().result(timeout=5)
    for s in range(have - 1, ROWS - 1, -1):
        ch.delete_scene(s).result(timeout=10)
    while ch.get_scene_count().result(timeout=5)["count"] < ROWS:
        ch.create_scene(-1).result(timeout=5)
    for t in range(len(track_names(ch))):
        for clip in ch.get_track_clips(t).result(timeout=10)["clips"]:
            ch.clear_clip(t, clip["slot"]).result(timeout=5)
    for s in range(ROWS):
        ch.set_scene_name(s, "").result(timeout=3)


# ---------------------------------------------------------------- devices
def prepare_devices(ch, go):
    print("  Redux (crush, 0% wet) on COLD-CUTS and CHOPPER; THROW-UP's Echo on at 0% wet")
    print("  F-HOLE Operator: oscillator B on at -inf (bell), shaper curve on at 0% mix (grit)")
    if not go:
        return
    from jungle_space import find_device, load_fx, set_number, _param
    for name in ("COLD-CUTS", "CHOPPER"):
        t = index_of(ch, name)
        fresh = find_device(ch, t, "Redux") is None
        d = load_fx(ch, t, dict(uri="query:AudioFx#Redux", name="Redux"))
        if fresh:
            for pname, raw in (("Bit Depth", 12.0), ("Sample Rate", 0.8), ("Dry/Wet", 0.0)):
                ch.set_device_param(t, d, _param(ch, t, d, pname)["index"], raw).result(timeout=5)
        print(f"  {name}: Redux @dev{d} {_param(ch, t, d, 'Bit Depth')['display']} bits, "
              f"{_param(ch, t, d, 'Sample Rate')['display']}, wet {_param(ch, t, d, 'Dry/Wet')['display']}")
    t = index_of(ch, "THROW-UP")
    d = find_device(ch, t, "Echo")
    if _param(ch, t, d, "Device On")["value"] < 0.5:
        ch.set_device_param(t, d, _param(ch, t, d, "Dry Wet")["index"], 0.0).result(timeout=5)
        ch.set_device_param(t, d, _param(ch, t, d, "Device On")["index"], 1.0).result(timeout=5)
    print(f"  THROW-UP: Echo {_param(ch, t, d, 'Device On')['display']}, wet {_param(ch, t, d, 'Dry Wet')['display']}")
    t = index_of(ch, "F-HOLE")
    if _param(ch, t, 0, "Osc-B On")["value"] < 0.5:
        for pname, raw in (("Osc-B Level", 0.0), ("B Coarse", 1.0), ("Osc-B On", 1.0)):
            ch.set_device_param(t, 0, _param(ch, t, 0, pname)["index"], raw).result(timeout=5)
    if _param(ch, t, 0, "Shaper Type")["value"] < 0.5:
        ch.set_device_param(t, 0, _param(ch, t, 0, "Shaper Mix")["index"], 0.0).result(timeout=5)
        ch.set_device_param(t, 0, _param(ch, t, 0, "Shaper Type")["index"], 1.0).result(timeout=5)
        set_number(ch, t, 0, "Shaper Drive", 6.0)
    print("  F-HOLE: " + ", ".join(f"{k} {_param(ch, t, 0, k)['display']}" for k in
                                   ("Osc-B On", "B Coarse", "Osc-B Level", "Shaper Type", "Shaper Drive",
                                    "Shaper Mix", "Pe Amount")))


def check_sound(ch):
    from jungle_kits import meter_test
    for name, notes in (("F-HOLE", [(30, 0.0, 1.5, 120)]), ("AMEN-DMENT", [(36, 0.0, 0.5, 120), (38, 1.0, 0.5, 120)]),
                        ("COLD-CUTS", [(36, 0.0, 0.5, 120), (38, 1.0, 0.5, 120)]),
                        ("CHOPPER", [(36, 0.0, 0.5, 120), (40, 1.0, 0.5, 120)]),
                        ("THROW-UP", [(36, 0.0, 0.5, 120), (38, 1.0, 0.5, 120)]),
                        ("SPINE-TINGLER", [(36, 0.0, 0.5, 120), (38, 1.0, 0.5, 120)])):
        peak = meter_test(ch, name, notes)
        print(f"  {name:<14} test hits meter {peak:.3f}{'   SILENT' if peak <= 0.01 else ''}")


def colour(ch):
    for name, c in COLOR.items():
        ch.set_track_color(index_of(ch, name), c).result(timeout=3)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Strip the section boards down to six MIDImix lanes.")
    ap.add_argument("--go", action="store_true", help="make the changes (default: dry run)")
    args = ap.parse_args(argv)
    from thelmic.live_channel import LiveChannel
    ch = LiveChannel(lower_priority=False)
    ch.start()
    try:
        print("== archive the clips")
        archive(ch)
        print("== tracks")
        strip_tracks(ch, args.go)
        print("== scenes")
        strip_scenes(ch, args.go)
        print("== devices")
        prepare_devices(ch, args.go)
        if not args.go:
            print("\n(dry run: nothing changed; --go to do it)")
            return
        print("== sound check")
        check_sound(ch)
        colour(ch)
        ch.set_launch_quantization(1).result(timeout=3)
    finally:
        ch.stop()


if __name__ == "__main__":
    main()
