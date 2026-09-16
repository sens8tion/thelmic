"""JUNGLE SUB DIRT - an optional shitty amp on the 808 (BOO-MERANGUE), for going full ragga / dancehall.

The user's source for the sound: sound-system bass through shitty amps. So it is Live's Amp into Cabinet, after
the 808's EQ and before LEVEL:
  Amp      Bass model, input gain pushed, mids up, output down to 6 so blending it in doesn't jump the level
  Cabinet  1x12, dynamic mic close on-axis     a small box that can't hold the sub, so it farts

Both Dry/Wets start at 0%: the lane sounds exactly as before until they're turned up. Turn them TOGETHER (map
one knob to both): the Cabinet's dry signal is the Amp's output, so a Cabinet up on its own colours the clean 808
too. Nothing is launched or stopped. Idempotent: existing devices are re-set, not doubled.

    python scripts/jungle_sub_dirt.py
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

from jungle_reset import index_of  # noqa: E402

SUB = "BOO-MERANGUE"
AMP = [("Amp Type", "Bass"), ("Input Gain", 7.5), ("Volume", 6.0), ("Bass", 6.0), ("Middle", 7.0), ("Treble", 4.0),
       ("Presence", 3.0),
       ("Dry/Wet", 0.0)]
CAB = [("Cabinet Type", "1x12"), ("Microphone Type", "Dynamic"), ("Microphone Position", "Near On-Axis"),
       ("Dry/Wet", 0.0)]


def chain(ch, t):
    return ch.get_track_info(t).result(timeout=5)["devices"]


def place(ch, t, uri, name, before):
    """The device called `name`, loaded if missing, sitting just before the device called `before`."""
    have = next((d["index"] for d in chain(ch, t) if d["name"] == name), None)
    if have is None:
        n = len(chain(ch, t))
        ch.load_device(t, uri).result(timeout=30)
        end = time.monotonic() + 20
        while len(chain(ch, t)) <= n and time.monotonic() < end:
            time.sleep(0.25)
        have = next(d["index"] for d in chain(ch, t) if d["name"] == name)
    target = next(d["index"] for d in chain(ch, t) if d["name"] == before)
    if have > target:
        ch.move_device(t, have, target).result(timeout=10)
    elif have < target - 1:
        ch.move_device(t, have, target - 1).result(timeout=10)
    return next(d["index"] for d in chain(ch, t) if d["name"] == name)


def main():
    from thelmic.live_channel import LiveChannel
    from jungle_space import set_number, set_string, _param
    ch = LiveChannel(lower_priority=False)
    ch.start()
    try:
        t = index_of(ch, SUB)
        before = "Compressor" if any(d["name"] == "Compressor" for d in chain(ch, t)) else "LEVEL"
        for uri, name, settings in (("query:AudioFx#Amp", "Amp", AMP), ("query:AudioFx#Cabinet", "Cabinet", CAB)):
            d = place(ch, t, uri, name, before)
            for pname, target in settings:
                try:
                    (set_string if isinstance(target, str) else set_number)(ch, t, d, pname, target)
                except Exception as e:
                    print(f"  [skip] {name} {pname}: {e!r}")
            d = next(x["index"] for x in chain(ch, t) if x["name"] == name)
            info = ch.get_device_info(t, d).result(timeout=10)
            print(f"  {name}: " + "; ".join(f"{p['name']}={p.get('display')}" for p in info["parameters"][1:]))
        print("  chain: " + " > ".join(x["name"] for x in chain(ch, t)))
    finally:
        ch.stop()


if __name__ == "__main__":
    main()
