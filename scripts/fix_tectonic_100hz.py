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
    set_eq_band, EQ8_BELL,
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
        # Narrow bell @ 100Hz, -3.5dB, fairly tight Q (~0.72)
        # Inaudible when the synth is modulating off the band; tames intro.
        set_eq_band(ch, t, eq, 4, ftype=EQ8_BELL, hz=100.0,
                    gain=-3.5, q_norm=0.72, on=True)
        print(f"  TECTONIC T{t} EQ{eq} band 4: bell -3.5dB @ 100Hz, Q=0.72")
        print(f"  (transparent when modulating, tames static intro)")
    finally:
        ch.stop()


if __name__ == "__main__":
    main()
