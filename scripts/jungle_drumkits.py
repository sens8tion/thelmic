"""JUNGLE DRUMKITS - move each sliced break from one Simpler onto a Drum Rack, one pad per slice.

Slice N keeps MIDI note 36 + N, so no clip changes. Every pad is its own Simpler on the same break
file with its sample start/end markers set to the slice, so hits ring out on their own pads and
re-hitting a pad restarts only that pad. This needs the remote script whose pad-device property
setter follows dotted paths ("sample.start_marker") and checks attributes on the class.

Per pad: One-Shot, Gate (a short note truncates the hit: roll steps), Fade In 1 ms / Fade Out 3 ms,
the break's Transpose/Detune, and the Volume and velocity sensitivity the track's Simpler had. The
effects after the instrument stay as they are.

Resumable: on a track that is already a Drum Rack, pads whose markers read back right are left
alone and only missing or unfinished pads are set up (a pad load can outlast the bridge's timeout).

    python scripts/jungle_drumkits.py                 # all three breaks
    python scripts/jungle_drumkits.py TOPSOIL         # just one
"""
from __future__ import annotations

import os
import sys
import time

os.environ.setdefault("LIVE_CHANNEL_ENABLED", "1")
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(SCRIPTS_DIR))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from jungle_slices import BREAKS, SLICE_ROOT  # noqa: E402
from jungle_build import fade_raw, SLICE_FADE_IN_MS, SLICE_FADE_OUT_MS  # noqa: E402

DRUM_RACK = "query:Synths#Drum%20Rack"
PAD_LOAD_TIMEOUT_S = 60.0
SOURCES = {     # track -> (browser folder, file, transpose st, detune cents)
    "AMEN-DMENT": ("user_library/Samples/Splice", "TSP_IHD_160_drum_break_amen_chop_4bar.wav", 1.0, 0.0),
    "SWEAT-SHOP": ("user_library/Samples/Imported/segura_breaks",
                   "KCSB1_174_ColdSweatBreak_01_HighToneFortified_NoRide_Saturated_Wide.wav", 0.0, -40.0),
    "TOPSOIL":    ("user_library/Samples/Imported/segura_breaks",
                   "KAPB1_174_ApacheBreak_01_HighTone_Normal.wav", 0.0, -40.0),
}


def _chain(ch, t):
    return [d["class_name"] for d in ch.get_track_info(t).result(timeout=5)["devices"]]


def _wait_count(ch, t, want, timeout=15.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if ch.get_track_info(t).result(timeout=5)["device_count"] == want:
            return
        time.sleep(0.25)
    raise RuntimeError(f"track {t}: device count never reached {want}")


def _pad_device(ch, t, note):
    """The pad's Simpler info (params with displays, sample markers), or None if the pad is empty."""
    try:
        return ch.get_drum_pad_chain_device_info(t, 0, note, 0).result(timeout=10)
    except Exception:
        return None


def _load_pad(ch, t, note, folder, item):
    try:
        ch.load_sample_to_pad(t, 0, note, folder, item).result(timeout=PAD_LOAD_TIMEOUT_S)
    except Exception:
        # the load can land after the RPC gives up: wait for the pad's Simpler before calling it failed
        for _ in range(60):
            if _pad_device(ch, t, note):
                return
            time.sleep(0.5)
        raise


def convert(ch, t, name):
    frames, labels = BREAKS[name]
    folder, item, transpose, detune = SOURCES[name]
    chain = _chain(ch, t)

    if chain and chain[0] == "DrumGroupDevice":
        ref = _pad_device(ch, t, SLICE_ROOT)
        if ref is None:
            raise SystemExit(f"{name}: a Drum Rack is here but pad {SLICE_ROOT} is empty; nothing to take levels from")
        ref_params = {p["name"]: p["value"] for p in ref["parameters"]}
        volume, vel_sens = ref_params["Volume"], ref_params["Vol < Vel"]
        total = int(ref["properties"]["sample.length"])
        print(f"{name}: Drum Rack already here; finishing any pad that isn't set up")
    elif chain and chain[0] == "OriginalSimpler":
        old = {p["name"]: p["value"] for p in ch.get_device_info(t, 0).result(timeout=5)["parameters"]}
        total = int(ch.get_sample_info(t, 0).result(timeout=5)["length"])
        volume, vel_sens = old["Volume"], old.get("Vol < Vel", 0.35)
        ch.delete_device(t, 0).result(timeout=10)
        _wait_count(ch, t, len(chain) - 1)
        ch.load_device(t, DRUM_RACK).result(timeout=20)
        _wait_count(ch, t, len(chain))
        rack = _chain(ch, t).index("DrumGroupDevice")
        if rack != 0:
            ch.move_device(t, rack, 0).result(timeout=10)
            time.sleep(0.4)
        print(f"{name}: Drum Rack in place of the Simpler ({len(frames)} pads, volume {volume:g} dB)")
    else:
        raise SystemExit(f"{name}: expected a sliced Simpler or a Drum Rack at device 0, found {chain}")

    for n, start in enumerate(frames):
        note = SLICE_ROOT + n
        end = (frames[n + 1] if n + 1 < len(frames) else total) - 1
        existing = _pad_device(ch, t, note)
        if existing and (existing["properties"].get("sample.start_marker"),
                         existing["properties"].get("sample.end_marker")) == (start, end):
            print(f"  pad {note}: slice {n:2d} already set up")
            continue
        if existing is None:
            _load_pad(ch, t, note, folder, item)

        def prop(key, value):
            return ch.set_drum_pad_chain_device_property(t, 0, note, key, value, 0).result(timeout=10)

        def param(key, value):
            return ch.set_drum_pad_chain_device_param(t, 0, note, float(value), param_name=key,
                                                      chain_device_index=0).result(timeout=10)

        prop("playback_mode", 1)                       # One-Shot
        try:
            prop("sample.warping", False)              # play at the file's own rate
        except Exception as e:
            print(f"    [warn] pad {note}: warping not set ({e})")
        prop("sample.start_marker", int(start))
        prop("sample.end_marker", int(end))
        for key, value in (("Trigger Mode", 1), ("Fade In", fade_raw(SLICE_FADE_IN_MS)),
                           ("Fade Out", fade_raw(SLICE_FADE_OUT_MS)), ("Transpose", transpose),
                           ("Detune", detune), ("Volume", volume), ("Vol < Vel", vel_sens), ("Snap", 0)):
            param(key, value)

        info = _pad_device(ch, t, note)
        props = info["properties"] if info else {}
        if (props.get("sample.start_marker"), props.get("sample.end_marker")) != (start, end):
            raise SystemExit(f"{name} pad {note}: markers read back {props.get('sample.start_marker')}.."
                             f"{props.get('sample.end_marker')}, wanted {start}..{end}")
        shown = {p["name"]: p.get("display", "?") for p in info["parameters"]
                 if p["name"] in ("Fade In", "Fade Out", "Transpose", "Detune")}
        print(f"  pad {note}: slice {n:2d} {labels[n]:<12} {start}..{end}  "
              + " ".join(f"{k}={v}" for k, v in shown.items()))
    print(f"{name}: chain now {' > '.join(_chain(ch, t))}")


def main(argv=None):
    wanted = (argv if argv is not None else sys.argv[1:]) or list(SOURCES)
    unknown = [w for w in wanted if w not in SOURCES]
    if unknown:
        raise SystemExit(f"unknown break tracks {unknown}; choose from {list(SOURCES)}")
    from thelmic.live_channel import LiveChannel
    ch = LiveChannel(lower_priority=False)
    ch.start()
    try:
        n = ch.get_session_info().result(timeout=5)["track_count"]
        idx = {ch.get_track_info(i).result(timeout=5)["name"]: i for i in range(n)}
        probe = ch.get_device_info(idx[wanted[0]], 0).result(timeout=5)["parameters"]
        if probe and "display" not in probe[0]:
            raise SystemExit("the bridge is the old version (no display strings): deploy it and restart Live")
        for name in wanted:
            convert(ch, idx[name], name)
    finally:
        ch.stop()


if __name__ == "__main__":
    main()
