"""TECTONIC has a ~100Hz peak that dominates the intro when nothing else
is playing. The user notes "it's fine when it's moving" — when the synth
modulates, energy sweeps off 100Hz, so a narrow static bell cut at 100Hz
is inaudible during active sections but tames the static intro peak."""
from __future__ import annotations
import os, sys
os.environ.setdefault("LIVE_CHANNEL_ENABLED", "1")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from thelmic.live_channel import LiveChannel
from thelmic.agent_helpers import (
    health_check, find_track, find_device, ensure_device,
    set_eq_band, EQ8_LOW_SHELF_GUESS,
)

EQ8_URI = "query:Audio%20Effects#EQ%20Eight"


def main():
    ch = LiveChannel(lower_priority=False); ch.start()
    try:
        ok, _ = health_check(ch, expected_track_names=["TECTONIC"])
        if not ok:
            print("halted — load the jungle set first")
            return
        t = find_track(ch, "TECTONIC")
        eq = find_device(ch, t, "Eq8")
        if eq is None:
            eq = ensure_device(ch, t, "Eq8", EQ8_URI)
        # Bell didn't bite — switch to a low-shelf dip. Broad scoop of the
        # low-end region rather than a surgical notch, gentler character.
        set_eq_band(ch, t, eq, 4, ftype=EQ8_LOW_SHELF_GUESS, hz=140.0,
                    gain=-4.0, q_norm=0.5, on=True)
        print(f"  TECTONIC T{t} EQ{eq} band 4: low-shelf dip -4dB @ 140Hz")
    finally:
        ch.stop()


if __name__ == "__main__":
    main()
