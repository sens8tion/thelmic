"""Phase 4 — 4 more rows of developing shape (clip slots 2..5).

Scene arc:
  2: engine_push   density variation, 16ths driving
  3: hollow_pause  breakdown, almost empty
  4: rebuild_lift  ramping density, anticipation
  5: payoff_storm  drop, denser than slot 1

Layout: T0 KLIK_SAINT, T1 KIK_HOOF, T2/T3 SUB_BOOM, T4 PIPER_PLUNGE.
All clips 16 beats (4 bars at 174).
"""
from __future__ import annotations
import os, time

os.environ.setdefault("LIVE_CHANNEL_ENABLED", "1")

from thelmic.live_channel import LiveChannel

CLIP_LEN = 16.0
SUB_PITCH = 28  # E1
KICK_PITCH = 36
CLICK_PITCH = 96


# ──────────────────────────────────────────────────────────────────────────
# SLOT 2 — engine_push (double-time)
# ──────────────────────────────────────────────────────────────────────────
S2_CLICKS = [i * 0.25 for i in range(64)]                  # straight 16ths
S2_KICKS  = [i * 0.5  for i in range(32)]                  # 8ths through
S2_SUB    = [(t, 0.4) for t in (i * 0.5 for i in range(32))]  # short sub stabs on every 8th
S2_FLUTE = [
    # Compressed cascading descent — 2 octaves in 2 bars, then mirror in 2 bars
    (0.0,  76, 100), (0.25, 74, 86), (0.5, 71, 80), (0.75, 69, 76),
    (1.0,  67,  90), (1.25, 64, 80), (1.5, 62, 82), (1.75, 59, 74),
    (2.0,  57,  88), (2.25, 55, 78), (2.5, 54, 80), (2.75, 52, 92),
    (3.0,  55,  76), (3.5,  57, 80), (3.75, 59, 84),
    (4.0,  59,  94), (4.5,  62, 82), (5.0,  64, 86), (5.5, 67, 78),
    (6.0,  69,  88), (6.5,  71, 80), (7.0,  74, 84), (7.5, 76, 100),
    # Bars 3-4 — variation
    (8.0,  74,  92), (8.5,  71, 80), (9.0, 67, 84), (9.5, 64, 78),
    (10.0, 62,  86), (10.5, 59, 80), (11.0, 55, 82), (11.5, 52, 92),
    (12.0, 52, 100), (12.5, 55, 78), (13.0, 59, 82), (13.5, 62, 80),
    (14.0, 64,  88), (14.5, 67, 84), (15.0, 71, 90), (15.5, 76, 100),
]


# ──────────────────────────────────────────────────────────────────────────
# SLOT 3 — hollow_pause (breakdown)
# ──────────────────────────────────────────────────────────────────────────
S3_CLICKS = [0.0, 4.0, 8.0, 12.0]                          # only downbeats
S3_KICKS  = [0.0, 8.0]                                     # two kicks only
S3_SUB    = [(0.0, 7.5), (8.0, 7.5)]                       # two long sustained subs
S3_FLUTE = [
    # Hollow phrases — sparse, low register
    (0.0,  64,  80),                                       # E4
    (3.0,  62,  72),                                       # D4
    (5.5,  59,  68),                                       # B3
    (8.0,  57,  78),                                       # A3
    (11.0, 55,  70),                                       # G3
    (13.5, 52,  84),                                       # E3 — resolution
]


# ──────────────────────────────────────────────────────────────────────────
# SLOT 4 — rebuild_lift (ramping anticipation)
# ──────────────────────────────────────────────────────────────────────────
# Click: bar1 8ths, bar2 8ths+, bar3 16ths, bar4 32nds-ish for last 2 beats
S4_CLICKS = (
    [i * 0.5 for i in range(8)]                            # bar1: 8ths
    + [4 + i * 0.5 for i in range(8)]                      # bar2: 8ths
    + [8 + i * 0.25 for i in range(16)]                    # bar3: 16ths
    + [12 + i * 0.25 for i in range(8)]                    # bar4 first half: 16ths
    + [14 + i * 0.125 for i in range(16)]                  # bar4 last half: 32nds
)
# Kicks: ramping density — 2,3,4,6 hits per bar
S4_KICKS = [0.0, 2.0,                                       # bar1: 2
            4.0, 5.5, 7.0,                                  # bar2: 3
            8.0, 9.0, 10.0, 11.0,                           # bar3: 4
            12.0, 12.75, 13.5, 14.0, 14.5, 15.0]            # bar4: 6
S4_SUB = [
    (0.0, 3.5),                                            # bar1: held
    (4.0, 3.5),                                            # bar2: held
    (8.0, 1.0), (9.0, 1.0), (10.0, 1.0), (11.0, 1.0),     # bar3: chopped
    (12.0, 0.5), (12.75, 0.5), (13.5, 0.5),               # bar4: shorter chops
    (14.0, 0.5), (14.5, 0.5), (15.0, 0.9),
]
S4_FLUTE = [
    # Ascending lift across whole 4 bars (rebuild gesture)
    (0.0,  52,  76), (1.5,  55, 78), (3.0, 57, 80),
    (4.0,  59,  84), (5.0,  62, 82), (6.5, 64, 86), (7.5, 67, 88),
    (8.0,  67,  90), (8.75, 69, 84), (9.5, 71, 88), (10.5, 74, 86),
    (11.0, 71,  84), (11.5, 74, 90),
    (12.0, 76,  94), (12.5, 74, 80), (13.0, 76, 92), (13.5, 78, 84),
    (14.0, 76,  98), (14.5, 78, 88), (15.0, 79, 92), (15.5, 76, 100),
]


# ──────────────────────────────────────────────────────────────────────────
# SLOT 5 — payoff_storm (drop, densest)
# ──────────────────────────────────────────────────────────────────────────
S5_CLICKS = [i * 0.25 for i in range(64)]                  # full 16ths
# Kicks: dense non-linear — anchor hits + offbeat punches
S5_KICKS = [0.0, 1.0, 2.5, 3.25, 4.0,
            5.5, 6.0, 7.0, 7.75,
            8.0, 9.25, 10.0, 11.5,
            12.0, 12.75, 13.5, 14.0, 14.75, 15.5]
# Sub: anchors + busy stabs
S5_SUB = [
    (0.0, 1.0), (1.0, 0.4), (2.5, 0.4), (3.25, 0.5), (4.0, 0.8),
    (5.5, 0.4), (6.0, 0.4), (7.0, 0.5), (7.75, 0.4),
    (8.0, 1.5), (9.25, 0.5), (10.0, 0.5), (11.5, 0.5),
    (12.0, 1.0), (12.75, 0.4), (13.5, 0.4), (14.0, 0.6), (14.75, 0.4), (15.5, 0.4),
]
S5_FLUTE = [
    # Full octave descent + call/response ornaments — drop melody
    (0.0,  79, 100), (0.5, 76, 88), (1.0, 74, 84), (1.5, 71, 80),
    (2.0,  67,  92), (2.5, 64, 84), (3.0, 62, 80), (3.5, 59, 86),
    (4.0,  57,  90), (4.5, 55, 78), (5.0, 54, 76), (5.5, 52, 96),
    (6.0,  55,  78), (6.5, 57, 80), (7.0, 52, 88), (7.5, 55, 76),
    (8.0,  76, 100), (8.5, 79, 92), (9.0, 76, 86),
    (10.0, 74, 88), (10.5, 71, 82), (11.0, 67, 80), (11.5, 64, 88),
    (12.0, 62, 90), (12.5, 59, 80), (13.0, 57, 84),
    (14.0, 55, 88), (14.5, 54, 80), (15.0, 52, 96), (15.5, 52, 100),
]


SLOTS = {
    2: ("engine_push",   S2_CLICKS, S2_KICKS, S2_SUB, S2_FLUTE),
    3: ("hollow_pause",  S3_CLICKS, S3_KICKS, S3_SUB, S3_FLUTE),
    4: ("rebuild_lift",  S4_CLICKS, S4_KICKS, S4_SUB, S4_FLUTE),
    5: ("payoff_storm",  S5_CLICKS, S5_KICKS, S5_SUB, S5_FLUTE),
}


def make_notes(items, pitch=None, dur=0.0625, vel=None):
    """items: either list of times (uniform pitch/dur/vel), or list of (time, dur), or list of (time, pitch, vel)."""
    notes = []
    for it in items:
        if isinstance(it, tuple):
            if len(it) == 2:
                t, d = it
                notes.append({"pitch": pitch, "start_time": t, "duration": d, "velocity": vel})
            elif len(it) == 3:
                t, p, v = it
                notes.append({"pitch": p, "start_time": t, "duration": dur, "velocity": v})
        else:
            notes.append({"pitch": pitch, "start_time": it, "duration": dur, "velocity": vel})
    return notes


def main() -> None:
    ch = LiveChannel(); ch.start(); time.sleep(0.6)
    try:
        for slot, (name, clicks, kicks, subs, flute) in SLOTS.items():
            # T0 click
            ch.create_clip(0, slot, length_beats=CLIP_LEN).result(timeout=5)
            ch.set_clip_name(0, slot, name).result(timeout=3)
            ch.add_notes_to_clip(0, slot,
                make_notes(clicks, pitch=CLICK_PITCH, dur=0.0625, vel=92)).result(timeout=5)

            # T1 kick
            ch.create_clip(1, slot, length_beats=CLIP_LEN).result(timeout=5)
            ch.set_clip_name(1, slot, name).result(timeout=3)
            ch.add_notes_to_clip(1, slot,
                make_notes(kicks, pitch=KICK_PITCH, dur=0.0625, vel=110)).result(timeout=5)

            # T2 + T3 sub (same content on both layered subs)
            for sub_ti in (2, 3):
                ch.create_clip(sub_ti, slot, length_beats=CLIP_LEN).result(timeout=5)
                ch.set_clip_name(sub_ti, slot, name).result(timeout=3)
                ch.add_notes_to_clip(sub_ti, slot,
                    make_notes(subs, pitch=SUB_PITCH, vel=105)).result(timeout=5)

            # T4 flute
            ch.create_clip(4, slot, length_beats=CLIP_LEN).result(timeout=5)
            ch.set_clip_name(4, slot, name).result(timeout=3)
            ch.add_notes_to_clip(4, slot,
                make_notes(flute, dur=0.18)).result(timeout=5)

            print(f"[slot {slot}] {name}: clicks x{len(clicks)} kicks x{len(kicks)} subs x{len(subs)} flute x{len(flute)}")
    finally:
        ch.stop()


if __name__ == "__main__":
    main()
