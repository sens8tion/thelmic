"""JUNGLE LEVELS, NATIVE - the levelled mix moves off the mixer faders, so the MIDImix faders can own them.

Each lane gets a Utility called LEVEL at the end of its chain, holding the level the balancing gave its fader;
every mixer fader (and Main) goes to 0 dB. The MIDImix faders are then mapped natively to the mixer volumes
with 0 dB at the top of their travel: all faders up is exactly the levelled mix, and pulling one down drops
that lane from its level rather than jumping to wherever the slider sits.

Idempotent: an existing LEVEL is re-set, not doubled.

    python scripts/jungle_levels_native.py
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

from jungle_reset import index_of, track_names  # noqa: E402

# the balanced fader levels (jungle_balance.py, as they stood before the reset), in dB. THROW-UP is 3 dB under
# its old fader (its hits no longer drop out by chance), and every lane is 2 dB under, so Main peaks below 0 dBFS
# when every hit plays.
LEVELS = {"SPINE-TINGLER": -8.6, "AMEN-DMENT": -4.2, "COLD-CUTS": -14.0, "CHOPPER": -11.2, "THROW-UP": -1.5,
          "BOO-MERANGUE": -7.6}      # the 808: F-HOLE's -3.6, 4 dB under, not yet matched on the meter
UNITY = 0.85                 # mixer volume raw value for 0 dB


def devices(ch, t):
    return ch.get_track_info(t).result(timeout=5)["devices"]


def ensure_level(ch, t, name):
    have = next((d["index"] for d in devices(ch, t) if d["name"] == "LEVEL"), None)
    if have is not None:
        return have
    before = [d["name"] for d in devices(ch, t)]
    ch.load_device(t, "query:AudioFx#Utility").result(timeout=30)
    end = time.monotonic() + 20
    while len(devices(ch, t)) <= len(before) and time.monotonic() < end:
        time.sleep(0.25)
    after = devices(ch, t)
    if len(after) <= len(before):
        raise SystemExit(f"{name}: Utility did not load")
    # the new Utility is the one the old chain didn't have: compare positions by name
    new = next(d["index"] for d in after if d["index"] >= len(before) or d["name"] != before[d["index"]])
    last = len(after) - 1
    if new != last:
        ch.move_device(t, new, last).result(timeout=10)
    ch.set_device_property(t, last, "name", "LEVEL").result(timeout=5)
    return last


def main():
    from thelmic.live_channel import LiveChannel
    from jungle_space import set_number, _param
    ch = LiveChannel(lower_priority=False)
    ch.start()
    try:
        present = set(track_names(ch))
        for name, db in LEVELS.items():
            if name not in present:
                print(f"  {name}: not in the set, skipped")
                continue
            t = index_of(ch, name)
            d = ensure_level(ch, t, name)
            gain = next(p["name"] for p in ch.get_device_info(t, d).result(timeout=10)["parameters"]
                        if p["name"] in ("Gain", "Output"))
            shown = set_number(ch, t, d, gain, db)
            ch.set_track_volume(t, UNITY).result(timeout=3)
            chain = " > ".join(x["name"] for x in devices(ch, t))
            print(f"  {name:<14} LEVEL {gain} {shown:<9} fader {_mixer_db(ch, t)} | {chain}")
        # Main: the bridge has no master-volume command, but the MIDImix binding still holds the master fader
        # (range 0..0.85): a simulated fader at the top writes 0 dB
        state = ch.midimix_simulate([[0xB0, 62, 127]]).result(timeout=5)["state"]
        print(f"  Main           {state['master']['display'] if state['master'] else 'unbound'}")
        print("== sound check")
        from jungle_kits import meter_test
        for name, notes in (("SPINE-TINGLER", [(36, 0.0, 0.5, 120), (38, 1.0, 0.5, 120)]),
                            ("AMEN-DMENT", [(36, 0.0, 0.5, 120), (38, 1.0, 0.5, 120)]),
                            ("COLD-CUTS", [(36, 0.0, 0.5, 120), (38, 1.0, 0.5, 120)]),
                            ("CHOPPER", [(36, 0.0, 0.5, 120), (40, 1.0, 0.5, 120)]),
                            ("THROW-UP", [(36, 0.0, 0.5, 120), (38, 1.0, 0.5, 120)]),
                            ("BOO-MERANGUE", [(30, 0.0, 1.5, 120)])):
            if name not in present:
                continue
            peak = meter_test(ch, name, notes)
            print(f"  {name:<14} test hits meter {peak:.3f}{'   SILENT' if peak <= 0.01 else ''}")
        print("tracks:", ", ".join(track_names(ch)))
    finally:
        ch.stop()


def _mixer_db(ch, t):
    info = ch.get_track_info(t).result(timeout=5)
    return f"{info.get('volume', 0):.2f}"


if __name__ == "__main__":
    main()
