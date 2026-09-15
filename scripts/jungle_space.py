"""JUNGLE SPACE - the second pass on the jungle session: space, stereo movement, harmony, a lead,
and a second reese. Adds to the set jungle_build made, idempotently (find by track name, find each
effect by its device name), and never touches a track it doesn't name.

  new lanes
    THROW-UP      a copy of AMEN-DMENT's slice kit -> EQ8 (lows out) -> Echo (ping-pong, all wet)
                  -> Hybrid Reverb (Filtered Dub Tech). Only its tails are heard: dub throws.
    RASP-UTIN     Anarchy Reese (Skitter and Step) -> EQ8 -> Utility(bass mono) -> Compressor(SC kick)
    HALO-PERIDOL  Orchid Strings (Skitter and Step) -> EQ8 (lows out) -> Auto Pan -> Compressor(SC kick)
    LIP-SERVICE   Suitcase Uncle Herbie (Electric Keyboards) -> EQ8 -> Echo -> Hybrid Reverb (Keys Bastille)
  inserts on existing lanes
    TOPSOIL / SWEAT-SHOP   a bright short reverb and a slow auto-pan: the tops move and leave tails
    BELL-END               its Echo goes ping-pong with the high end opened up
    RASP-BERRY             the rack's LFO and flanger turned up so the reese moves

Every parameter is set by what Live DISPLAYS (jungle_sidechain.set_by_display), never a guessed curve.

    python scripts/jungle_space.py            # add lanes + effects, apply SETTINGS, key the ducks
    python scripts/jungle_space.py --dump     # print every parameter (with display) of the devices this touches
    python scripts/jungle_space.py --scan "RASP-BERRY" 0 "LFO Rate"   # displays across a parameter's range
"""
from __future__ import annotations

import argparse
import os
import sys
import time

os.environ.setdefault("LIVE_CHANNEL_ENABLED", "1")
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(SCRIPTS_DIR))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from jungle_build import EQ8, ECHO, UTILITY, apply_eq, bell, low_cut  # noqa: E402
from jungle_sidechain import _param, parse_display, set_by_display, set_choice  # noqa: E402

CORE_FX = "packs/Core Library/Devices/Audio Effects"
SKITTER = "packs/Skitter and Step/Sounds"
KEYS = "packs/Electric Keyboards/Sounds/Suitcase Piano"


def uri(u, name, eq=None):
    return dict(uri=u, name=name, eq=eq)


def preset(path, item, eq=None):
    return dict(path=path, item=item, name=item.rsplit(".", 1)[0], eq=eq)


NEW_LANES = [
    dict(name="THROW-UP", after="AMEN-DMENT", copy_of="AMEN-DMENT", keep=1,
         fx=[uri(EQ8, "EQ Eight", eq=[low_cut(500, steep=True)]),
             uri(ECHO, "Echo")]),                       # Echo's own short reverb, not a hall
    dict(name="RASP-UTIN", after="RASP-BERRY", instrument=(f"{SKITTER}/Bass", "Anarchy Reese.adg"),
         fx=[uri(EQ8, "EQ Eight", eq=[low_cut(120, steep=True), bell(300, -3.0)]),
             uri(UTILITY, "Utility")]),
    dict(name="HALO-PERIDOL", after="BELL-END", instrument=(f"{SKITTER}/Pads", "Orchid Strings.adg"),
         fx=[uri(EQ8, "EQ Eight", eq=[low_cut(300, steep=True)]),
             preset(f"{CORE_FX}/Auto Pan-Tremolo", "Pan Wander Trip.adv")]),
    dict(name="LIP-SERVICE", after="HALO-PERIDOL", instrument=(KEYS, "Suitcase Uncle Herbie.adg"),
         fx=[uri(EQ8, "EQ Eight", eq=[low_cut(150)]),
             uri(ECHO, "Echo"),
             preset(f"{CORE_FX}/Hybrid Reverb/Hall", "Keys Bastille.adv")]),
    # one note, over and over, at phrase ends: the rack voices it as a minor chord
    dict(name="STAB-VEST", after="LIP-SERVICE", instrument=(f"{SKITTER}/Pads", "Cavity Soup Stab (minor).adg"),
         fx=[uri(EQ8, "EQ Eight", eq=[low_cut(200)]),
             uri(ECHO, "Echo")]),
]
INSERTS = {
    "TOPSOIL":    [preset(f"{CORE_FX}/Reverb/Room", "High Verb.adv"),
                   preset(f"{CORE_FX}/Auto Pan-Tremolo", "Pan Around The Head.adv")],
    "SWEAT-SHOP": [preset(f"{CORE_FX}/Reverb/Room", "High Verb.adv"),
                   preset(f"{CORE_FX}/Auto Pan-Tremolo", "Pan Pendulum.adv")],
}

# (track, device name, parameter, target). Numbers are set by display (units as Live shows them: Hz,
# %, dB, ms); strings pick the step whose display matches. Read off --dump.
SETTINGS: list[tuple[str, str, str, float | str]] = [
    # the EQ helper's frequency mapping lands low (500 Hz asked, 266 Hz shown), so cut-offs go by display
    ("THROW-UP", "EQ Eight", "1 Frequency A", 500.0),
    ("RASP-UTIN", "EQ Eight", "1 Frequency A", 120.0),
    ("RASP-UTIN", "EQ Eight", "2 Frequency A", 300.0),
    ("HALO-PERIDOL", "EQ Eight", "1 Frequency A", 300.0),
    ("LIP-SERVICE", "EQ Eight", "1 Frequency A", 150.0),
    ("RASP-UTIN", "Utility", "Bass Mono", "On"),
    # THROW-UP: nothing but echoes, bouncing side to side, above the snare's body
    ("THROW-UP", "Echo", "Channel Mode", "Ping Pong"),
    ("THROW-UP", "Echo", "Feedback", 55.0),
    ("THROW-UP", "Echo", "HP Freq", 600.0),
    ("THROW-UP", "Echo", "LP Freq", 9000.0),
    ("THROW-UP", "Echo", "Reverb Level", 20.0),
    ("THROW-UP", "Echo", "Reverb Decay", 40.0),
    ("THROW-UP", "Echo", "Dry Wet", 100.0),
    # lead: a slower ping-pong (dotted quarter) than the bell's dotted eighth; the hall stays behind it
    ("LIP-SERVICE", "Echo", "Channel Mode", "Ping Pong"),
    ("LIP-SERVICE", "Echo", "L Synced", "1/4"),
    ("LIP-SERVICE", "Echo", "Feedback", 35.0),
    ("LIP-SERVICE", "Echo", "HP Freq", 300.0),
    ("LIP-SERVICE", "Echo", "LP Freq", 7000.0),
    ("LIP-SERVICE", "Echo", "Dry Wet", 22.0),
    ("LIP-SERVICE", "Keys Bastille", "Dry/Wet", 28.0),
    ("LIP-SERVICE", "Suitcase Uncle Herbie", "Tremolo Amount", 30.0),
    # tops: reverb presets load 100% wet; keep the tails bright (nothing under 3 kHz goes in)
    ("TOPSOIL", "High Verb", "Input Freq", 3000.0),
    ("TOPSOIL", "High Verb", "Dry/Wet", 25.0),
    ("SWEAT-SHOP", "High Verb", "Input Freq", 3000.0),
    ("SWEAT-SHOP", "High Verb", "Dry/Wet", 20.0),
    # auto-pans synced and out of step with each other: 2 bars on TOPSOIL, 1.5 on SWEAT-SHOP
    ("TOPSOIL", "Pan Around The Head", "Time Mode", "16th"),
    ("TOPSOIL", "Pan Around The Head", "16th", 32.0),
    ("TOPSOIL", "Pan Around The Head", "Amount", 55.0),
    ("SWEAT-SHOP", "Pan Pendulum", "Time Mode", "16th"),
    ("SWEAT-SHOP", "Pan Pendulum", "16th", 24.0),
    ("SWEAT-SHOP", "Pan Pendulum", "Amount", 45.0),
    ("HALO-PERIDOL", "Pan Wander Trip", "Amount", 50.0),
    # bell: ping-pong, the echoes' top end opened up from 1.78 kHz
    ("BELL-END", "Echo", "Channel Mode", "Ping Pong"),
    ("BELL-END", "Echo", "HP Freq", 400.0),
    ("BELL-END", "Echo", "LP Freq", 9000.0),
    ("BELL-END", "Echo", "Feedback", 45.0),
    ("BELL-END", "Echo", "Dry Wet", 30.0),
    # the first reese moves: more flanger, a deeper and slower LFO
    ("RASP-BERRY", "Reese Classic", "Flanger", 35.0),
    ("RASP-BERRY", "Reese Classic", "LFO Amount", 40.0),
    ("RASP-BERRY", "Reese Classic", "LFO Rate", "1/2"),
    # SPACE. Every low cut written through set_eq_band landed about half what was asked, so the breaks
    # were still filling the kick and sub's octave. These are Live's own displayed frequencies.
    ("AMEN-DMENT", "EQ Eight", "1 Frequency A", 120.0),
    ("AMEN-DMENT", "EQ Eight", "2 Frequency A", 300.0),
    ("AMEN-DMENT", "EQ Eight", "3 Frequency A", 10000.0),
    ("SWEAT-SHOP", "EQ Eight", "1 Frequency A", 200.0),
    ("SWEAT-SHOP", "EQ Eight", "2 Frequency A", 300.0),
    ("TOPSOIL", "EQ Eight", "1 Frequency A", 400.0),
    ("BOOT-LEG", "EQ Eight", "1 Frequency A", 40.0),
    ("BOOT-LEG", "EQ Eight", "2 Frequency A", 90.0),
    ("RASP-BERRY", "EQ Eight", "1 Frequency A", 120.0),
    ("RASP-BERRY", "EQ Eight", "2 Frequency A", 300.0),
    ("BELL-END", "EQ Eight", "1 Frequency A", 350.0),
    ("LIP-SERVICE", "EQ Eight", "1 Frequency A", 250.0),
    ("HALO-PERIDOL", "EQ Eight", "1 Frequency A", 350.0),
    # the pad gets out of the bell and lead's way with a dip where they live
    ("HALO-PERIDOL", "EQ Eight", "2 Frequency A", 2000.0),
    ("HALO-PERIDOL", "EQ Eight", "2 Gain A", -4.0),
    # STAB-VEST: nothing under 200 Hz, a short 3/16 ping-pong tail
    ("STAB-VEST", "EQ Eight", "1 Frequency A", 200.0),
    ("STAB-VEST", "Echo", "Channel Mode", "Ping Pong"),
    ("STAB-VEST", "Echo", "Feedback", 28.0),
    ("STAB-VEST", "Echo", "HP Freq", 500.0),
    ("STAB-VEST", "Echo", "LP Freq", 8000.0),
    ("STAB-VEST", "Echo", "Dry Wet", 18.0),
]

# Track pan. Kick, sub, breaks and stabs' weight stay centred; the voices that share the top octave
# sit apart from each other, and the auto-panned lanes are left alone to move.
PANS = {"BELL-END": -0.25, "LIP-SERVICE": 0.25, "STAB-VEST": -0.12}

# devices taken back out. Filtered Dub Tech (a 5.6 s Hybrid Reverb) fed by an echo made an endless shimmer.
REMOVE = {"THROW-UP": ["Filtered Dub Tech"]}

# lanes keyed from the kick, on top of jungle_sidechain.DUCKS
EXTRA_DUCKS = {
    "RASP-UTIN":    dict(gr_db=6.0, ratio=4.0, attack_ms=1.0, release_ms=120.0),
    # the pad is keyed from the LEAD, not the kick: it steps back whenever the lead is playing and
    # comes back up in the lead's rests. That is the space, made automatic.
    "HALO-PERIDOL": dict(gr_db=5.0, ratio=2.5, attack_ms=8.0, release_ms=220.0,
                         key="LIP-SERVICE", key_peak_db=-4.0),
}


# ----------------------------------------------------------------------
def names(ch) -> dict[str, int]:
    n = ch.get_session_info().result(timeout=5)["track_count"]
    return {ch.get_track_info(i).result(timeout=5)["name"]: i for i in range(n)}


def chain(ch, t) -> list[dict]:
    return ch.get_track_info(t).result(timeout=5)["devices"]


def find_device(ch, t, name) -> int | None:
    for d in chain(ch, t):
        if d["name"] == name:
            return d["index"]
    return None


def wait_count(ch, t, before, timeout_s=20.0):
    end = time.monotonic() + timeout_s
    while time.monotonic() < end:
        if len(chain(ch, t)) > before:
            return True
        time.sleep(0.25)
    return False


def load_fx(ch, t, spec) -> int:
    """Load an effect at the END of track t's chain (Live inserts after the selected device, so move it
    there if it landed elsewhere) unless a device of that name is already on the track."""
    have = find_device(ch, t, spec["name"])
    if have is not None:
        return have
    before = len(chain(ch, t))
    if "uri" in spec:
        ch.load_device(t, spec["uri"]).result(timeout=30)
    else:
        ch.load_item_at_path(t, spec["path"], spec["item"]).result(timeout=30)
    if not wait_count(ch, t, before):
        raise RuntimeError(f"{spec['name']} did not load on track {t}")
    devs = chain(ch, t)
    new = [d["index"] for d in devs if d["name"] == spec["name"]]
    d = new[-1] if new else devs[-1]["index"]
    if d != len(devs) - 1:
        ch.move_device(t, d, len(devs) - 1).result(timeout=10)
        d = find_device(ch, t, spec["name"])
    if spec.get("eq"):
        apply_eq(ch, t, d, spec["eq"], confident_eq=False)
    print(f"   + {spec['name']} @dev{d}  ({' > '.join(x['name'] for x in chain(ch, t))})")
    return d


def ensure_lane(ch, lane) -> int:
    idx = names(ch)
    if lane["name"] in idx:
        return idx[lane["name"]]
    at = idx[lane["after"]] + 1
    if "copy_of" in lane:
        src = idx[lane["copy_of"]]
        ch.duplicate_track(src).result(timeout=60)          # the copy lands at src + 1
        t = src + 1
        ch.set_track_name(t, lane["name"]).result(timeout=3)
        if t != at:
            raise RuntimeError(f"{lane['name']}: copy landed at {t}, expected {at}")
        for d in range(len(chain(ch, t)) - 1, lane["keep"] - 1, -1):   # drop the source's effects
            ch.delete_device(t, d).result(timeout=10)
        print(f"  copied {lane['copy_of']} -> track {t}: {lane['name']} ({chain(ch, t)[0]['name']})")
    else:
        ch.create_midi_track(at).result(timeout=10)
        t = at
        ch.set_track_name(t, lane["name"]).result(timeout=3)
        path, item = lane["instrument"]
        ch.load_item_at_path(t, path, item).result(timeout=60)
        if not wait_count(ch, t, 0, timeout_s=30.0):
            raise RuntimeError(f"{lane['name']}: {item} did not load")
        print(f"  created track {t}: {lane['name']} <- {item} ({chain(ch, t)[0]['class_name']})")
    return t


def set_text(ch, t, d, name, wanted, steps=128):
    """A continuous parameter whose display is text (e.g. a synced rate '1/8'): scan for the display."""
    p = _param(ch, t, d, name)
    lo, hi = float(p["min"]), float(p["max"])
    for k in range(steps + 1):
        raw = lo + (hi - lo) * k / steps
        ch.set_device_param(t, d, p["index"], raw).result(timeout=3)
        if _param(ch, t, d, name)["display"].strip().lower() == wanted.lower():
            return wanted
    raise ValueError(f"{name}: nothing displays {wanted!r}")


def close(a, b):
    return abs(a - b) <= max(0.02 * abs(b), 0.5)


def set_number(ch, t, d, name, target):
    """Set a numeric parameter to what Live DISPLAYS. Plenty of parameters' raw values already ARE the
    displayed unit (an EQ frequency in Hz, an auto-pan rate in 16ths), so try that first: it costs two
    calls and lands exactly on a stepped value. Otherwise bisect the raw range against the display."""
    p = _param(ch, t, d, name)
    if close(parse_display(p["display"]), target):
        return p["display"]                       # already there: reruns cost one call per setting
    if float(p["min"]) <= target <= float(p["max"]):
        ch.set_device_param(t, d, p["index"], float(target)).result(timeout=6)
        shown = _param(ch, t, d, name)["display"]
        if close(parse_display(shown), target):
            return shown
    return set_by_display(ch, t, d, name, float(target))


def set_string(ch, t, d, name, target):
    p = _param(ch, t, d, name)
    if p["display"].strip().lower() == target.lower():
        return p["display"]
    return (set_choice if p.get("is_quantized") else set_text)(ch, t, d, name, target)


def apply_settings(ch):
    idx = names(ch)
    for track, dev, pname, target in SETTINGS:
        t = idx[track]
        d = find_device(ch, t, dev)
        if d is None:
            print(f"  [skip] {track}: no device {dev!r}")
            continue
        for attempt in (1, 2):          # the bridge times out when Live is busy; one retry is enough
            try:
                shown = (set_string if isinstance(target, str) else set_number)(ch, t, d, pname, target)
                print(f"  {track:<12} {dev:<22} {pname:<18} -> {shown}")
                break
            except Exception as e:
                if attempt == 2:
                    print(f"  [skip] {track} {dev} {pname} -> {target}: {e!r}")
                else:
                    time.sleep(2.0)
    for track, pan in PANS.items():
        if track not in idx:
            continue
        try:
            ch.set_track_pan(idx[track], float(pan)).result(timeout=5)
            print(f"  {track:<12} pan{' ' * 33}-> {pan:+.2f}")
        except Exception as e:
            print(f"  [skip] pan {track}: {e!r}")


def touched(ch):
    idx = names(ch)
    out = []
    for lane in NEW_LANES:
        if lane["name"] in idx:
            out += [(lane["name"], d) for d in chain(ch, idx[lane["name"]])]
    for track, specs in INSERTS.items():
        want = {s["name"] for s in specs}
        out += [(track, d) for d in chain(ch, idx[track]) if d["name"] in want]
    out += [("BELL-END", d) for d in chain(ch, idx["BELL-END"]) if d["name"] == "Echo"]
    out += [("RASP-BERRY", chain(ch, idx["RASP-BERRY"])[0])]
    return idx, out


def dump(ch):
    idx, devs = touched(ch)
    for track, d in devs:
        info = ch.get_device_info(idx[track], d["index"]).result(timeout=5)
        print(f"\n== {track} @dev{d['index']} {d['name']} ({d['class_name']})")
        print("   " + "; ".join(f"{p['name']}={p.get('display', p['value'])}"
                              + ("*" if p.get("is_quantized") else "") for p in info["parameters"]))


def scan(ch, track, d, pname, steps=40):
    t = names(ch)[track]
    p = _param(ch, t, d, pname)
    start = p["value"]
    seen = []
    for k in range(steps + 1):
        raw = p["min"] + (p["max"] - p["min"]) * k / steps
        ch.set_device_param(t, d, p["index"], raw).result(timeout=3)
        shown = _param(ch, t, d, pname)["display"]
        if not seen or seen[-1][1] != shown:
            seen.append((round(raw, 3), shown))
    ch.set_device_param(t, d, p["index"], start).result(timeout=3)
    print(f"{track} dev{d} {pname}: " + "  ".join(f"{r}={s}" for r, s in seen))


def build(ch):
    print("== lanes ==")
    for lane in NEW_LANES:
        t = ensure_lane(ch, lane)
        for spec in lane["fx"]:
            load_fx(ch, t, spec)
    print("\n== inserts ==")
    for track, specs in INSERTS.items():
        t = names(ch)[track]
        print(f"  {track}")
        for spec in specs:
            load_fx(ch, t, spec)
    for track, gone in REMOVE.items():
        t = names(ch)[track]
        for dev in gone:
            d = find_device(ch, t, dev)
            if d is not None:
                ch.delete_device(t, d).result(timeout=10)
                print(f"  - {track}: removed {dev}")
    print("\n== settings ==")
    apply_settings(ch)
    print("\n== ducks ==")
    import jungle_sidechain
    jungle_sidechain.DUCKS.update(EXTRA_DUCKS)
    jungle_sidechain.apply(ch, names(ch))


def main(argv=None):
    ap = argparse.ArgumentParser(description="Space, movement, harmony and a second reese for the jungle set.")
    ap.add_argument("--dump", action="store_true")
    ap.add_argument("--settings", action="store_true", help="apply SETTINGS only (lanes and effects already exist)")
    ap.add_argument("--scan", nargs=3, metavar=("TRACK", "DEVICE", "PARAM"))
    args = ap.parse_args(argv)
    from thelmic.live_channel import LiveChannel
    ch = LiveChannel(lower_priority=False)
    ch.start()
    try:
        if args.scan:
            scan(ch, args.scan[0], int(args.scan[1]), args.scan[2])
        elif args.dump:
            dump(ch)
        elif args.settings:
            apply_settings(ch)
        else:
            build(ch)
    finally:
        ch.stop()


if __name__ == "__main__":
    main()
