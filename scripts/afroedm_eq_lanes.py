"""Apply EQ8 HP/LP per role on the 6 lanes."""
from __future__ import annotations
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from thelmic.live_channel import LiveChannel
from thelmic.bridge.helpers.eq import set_eq_band, EQ8_HP_48_GUESS, EQ8_LP_48_GUESS
from thelmic.bridge.helpers.discovery import ensure_device

EQ8_URI = "query:AudioFx#EQ%20Eight"

# (track_name, hp_hz, lp_hz_or_None)
PLAN = [
    ("KICK_BOOM",      30,    None),
    ("PERC_CRISP",     80,    12000),
    ("SUB_VEIN",       30,    700),
    ("BASS_KENYA",     50,    400),
    ("STAB_TWENTYTWO", 200,   6000),
    ("RAP_NAIROBI",    150,   8000),
]


def find_track(ch, name):
    info = ch.get_session_info().result(timeout=5)
    for i in range(info.get("track_count") or 0):
        if ch.get_track_info(i).result(timeout=3).get("name") == name:
            return i
    return None


def main():
    ch = LiveChannel(enabled=True); ch.start()
    try:
        for name, hp, lp in PLAN:
            t = find_track(ch, name)
            if t is None:
                print(f"  {name}: NOT FOUND")
                continue
            eq_idx = ensure_device(ch, t, "Eq8", EQ8_URI)
            set_eq_band(ch, t, eq_idx, 1, ftype=EQ8_HP_48_GUESS, hz=hp)
            if lp is not None:
                set_eq_band(ch, t, eq_idx, 8, ftype=EQ8_LP_48_GUESS, hz=lp)
            print(f"  {name} (T{t}): HP {hp} Hz, LP {'open' if lp is None else f'{lp} Hz'}")
    finally:
        ch.stop()


if __name__ == "__main__":
    main()
