"""JUNGLE SIDECHAIN - key the sub and reese from the kick, set in real units.

Live's Compressor on F-HOLE and RASP-BERRY, sidechained from BOOT-LEG (Glue can't be keyed over the
bridge). Every value is set by reading what Live DISPLAYS (the bridge's per-parameter "display"
string) and bisecting the raw 0..1 value until the display hits the target, so no unit curve is ever
guessed.

Duck depth: the key is the kick layer, peaking about KEY_PEAK_DB. With ratio R a kick reduces gain
by roughly (key - threshold) * (1 - 1/R), so threshold = key - GR / (1 - 1/R).

    python scripts/jungle_sidechain.py
"""
from __future__ import annotations

import math
import os
import re
import sys
import time

os.environ.setdefault("LIVE_CHANNEL_ENABLED", "1")
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(SCRIPTS_DIR))

KEY_TRACK = "BOOT-LEG"
KEY_PEAK_DB = -2.0              # kick layer peak (it was gain-staged to ~0.80 on the meter)
COMPRESSOR = "query:AudioFx#Compressor"
DUCKS = {
    "F-HOLE":     dict(gr_db=8.0, ratio=4.0, attack_ms=1.0, release_ms=100.0),
    "RASP-BERRY": dict(gr_db=6.0, ratio=4.0, attack_ms=1.0, release_ms=120.0),
}
BISECT_STEPS = 16

_NUM = re.compile(r"-?\d+(?:\.\d+)?")


def parse_display(text: str) -> float:
    """'-15.0 dB' -> -15.0, '4.00 : 1' -> 4.0, '1.00 ms' -> 1.0, '1.20 s' -> 1200.0 (ms), 'inf' -> inf."""
    t = text.strip().lower()
    if "inf" in t:
        return -math.inf if t.startswith("-") else math.inf
    m = _NUM.search(t)
    if not m:
        raise ValueError(f"no number in display {text!r}")
    v = float(m.group())
    if "khz" in t:
        v *= 1000.0
    if re.search(r"\d\s*s$", t):            # seconds, not ms
        v *= 1000.0
    return v


def _param(ch, t, d, name):
    for p in ch.get_device_info(t, d).result(timeout=5)["parameters"]:
        if p["name"] == name:
            if "display" not in p:
                raise SystemExit("the bridge returns no display strings: deploy the remote script "
                                 "(scripts/deploy_remote_script.py) and restart Live")
            return p
    raise KeyError(name)


def set_by_display(ch, t, d, name, target):
    """Bisect the raw value until Live's displayed value reaches `target`; returns the display."""
    p = _param(ch, t, d, name)
    lo, hi = float(p["min"]), float(p["max"])

    def shown(raw):
        ch.set_device_param(t, d, p["index"], raw).result(timeout=3)
        return parse_display(_param(ch, t, d, name)["display"])

    v_lo, v_hi = shown(lo), shown(hi)
    if not min(v_lo, v_hi) <= target <= max(v_lo, v_hi):
        raise ValueError(f"{name}: target {target} is outside what it displays ({v_lo} .. {v_hi})")
    rising = v_hi > v_lo
    for _ in range(BISECT_STEPS):
        mid = (lo + hi) / 2
        if (shown(mid) < target) == rising:
            lo = mid
        else:
            hi = mid
    shown((lo + hi) / 2)
    return _param(ch, t, d, name)["display"]


def set_choice(ch, t, d, name, wanted):
    """For a stepped parameter: try each step until the display reads `wanted`."""
    p = _param(ch, t, d, name)
    for raw in range(int(p["min"]), int(p["max"]) + 1):
        ch.set_device_param(t, d, p["index"], float(raw)).result(timeout=3)
        if _param(ch, t, d, name)["display"].strip().lower() == wanted.lower():
            return wanted
    raise ValueError(f"{name}: no step displays {wanted!r}")


def apply(ch, idx: dict):
    """Key a Compressor on every DUCKS lane from KEY_TRACK, set in real units. idx = {track name: index}."""
    key = idx[KEY_TRACK]
    for lane, spec in DUCKS.items():
        t = idx[lane]
        chain = [x["class_name"] for x in ch.get_track_info(t).result(timeout=5)["devices"]]
        if "Compressor2" not in chain:
            ch.load_device(t, COMPRESSOR).result(timeout=20)
            time.sleep(1.0)
            chain = [x["class_name"] for x in ch.get_track_info(t).result(timeout=5)["devices"]]
        d = len(chain) - 1 - chain[::-1].index("Compressor2")
        ch.set_device_sidechain_source(t, d, key).result(timeout=10)
        source = ch.get_device_routing_options(t, d).result(timeout=5)["current_type"]
        if KEY_TRACK not in source:
            raise SystemExit(f"{lane}: sidechain source reads {source!r}, not {KEY_TRACK}")
        for toggle, raw in (("S/C On", 1.0), ("S/C EQ On", 0.0), ("Makeup", 0.0), ("Auto Release On/Off", 0.0)):
            ch.set_device_param(t, d, _param(ch, t, d, toggle)["index"], raw).result(timeout=3)
        model = set_choice(ch, t, d, "Model", "Peak")
        threshold = KEY_PEAK_DB - spec["gr_db"] / (1.0 - 1.0 / spec["ratio"])
        shown = {name: set_by_display(ch, t, d, name, target)
                 for name, target in (("Ratio", spec["ratio"]), ("Attack", spec["attack_ms"]),
                                      ("Release", spec["release_ms"]), ("Threshold", threshold))}
        knee = _param(ch, t, d, "Knee")["display"]
        print(f"{lane}: Compressor @dev{d} keyed from {source}, model {model}, "
              + ", ".join(f"{k} {v}" for k, v in shown.items()) + f", knee {knee} "
              f"(aiming for ~{spec['gr_db']:g} dB of duck on a {KEY_PEAK_DB:g} dB kick)")


def main():
    from thelmic.live_channel import LiveChannel
    ch = LiveChannel(lower_priority=False)
    ch.start()
    try:
        n = ch.get_session_info().result(timeout=5)["track_count"]
        apply(ch, {ch.get_track_info(i).result(timeout=5)["name"]: i for i in range(n)})
    finally:
        ch.stop()


if __name__ == "__main__":
    main()
