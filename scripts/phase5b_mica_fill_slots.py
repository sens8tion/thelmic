"""Fill MICA_THROB slots 1..5 to match each scene's character."""
from __future__ import annotations
import os, time

os.environ.setdefault("LIVE_CHANNEL_ENABLED", "1")

from thelmic.live_channel import LiveChannel

PENTA = [88, 91, 93, 95, 98]  # E6 G6 A6 B6 D7
T = 5                          # MICA_THROB
DUR = 0.12


def vel_for(i):
    return 96 if i % 3 == 0 else 72


def cycle_notes(times):
    return [{"pitch": PENTA[i % 5], "start_time": t, "duration": DUR, "velocity": vel_for(i)}
            for i, t in enumerate(times)]


# Slot 1 — burst_pulse: 16ths during stab windows (0-2, 4-6, 8-10, 12-14), silent during holds
S1 = []
for w in (0.0, 4.0, 8.0, 12.0):
    for j in range(8):                            # 8 sixteenths per 2-beat burst
        S1.append(w + j * 0.25)

# Slot 2 — engine_push: straight 8ths, 32 hits driving
S2 = [i * 0.5 for i in range(32)]

# Slot 3 — hollow_pause: 4 hits, downbeats only, top of pentatonic for sparkle
S3 = [0.0, 4.0, 8.0, 12.0]

# Slot 4 — rebuild_lift: ramping density matching click ramp
S4 = (
    [i * 0.5  for i in range(8)]                  # bar1 8ths
    + [4 + i * 0.5  for i in range(8)]            # bar2 8ths
    + [8 + i * 0.25 for i in range(16)]           # bar3 16ths
    + [12 + i * 0.25 for i in range(8)]           # bar4a 16ths
    + [14 + i * 0.125 for i in range(16)]         # bar4b 32nds
)

# Slot 5 — payoff_storm: 16th-triplets through, max density (~96 hits = 6 per beat × 16)
S5 = [round(i * (1/6.0), 4) for i in range(96) if i * (1/6.0) < 16.0]


SLOTS = {1: ("burst_pulse", S1), 2: ("engine_push", S2),
         3: ("hollow_pause", S3), 4: ("rebuild_lift", S4),
         5: ("payoff_storm", S5)}


def main():
    ch = LiveChannel(); ch.start(); time.sleep(0.6)
    try:
        for slot, (name, times) in SLOTS.items():
            ch.create_clip(T, slot, length_beats=16.0).result(timeout=5)
            ch.set_clip_name(T, slot, name).result(timeout=3)
            ch.add_notes_to_clip(T, slot, cycle_notes(times)).result(timeout=5)
            print(f"[slot {slot}] {name}: {len(times)} hits")
    finally:
        ch.stop()


if __name__ == "__main__":
    main()
