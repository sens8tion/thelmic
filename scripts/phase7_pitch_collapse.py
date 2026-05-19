"""Phase 7 — collapse PIPER_PLUNGE and MICA_THROB to 1-2 notes across most slots.

Kept: PIPER slots 0 (descending plunge) and 1 (ascending mirror) — those are
the track's defining gesture. Everything else collapses to 1-2 anchor notes,
preserving original timing/velocity/duration.

PIPER pitch plan:
  slot 2 engine_push  →  alternating E5/B4 (76/71) — 5th
  slot 3 hollow_pause →  E4 (64) only — hollow root
  slot 4 rebuild_lift →  alternating E4/B4 — lifting fifth
  slot 5 payoff_storm →  E5 (76) only — root-locked drop

MICA pitch plan (rhythmic layer, collapse all slots):
  slot 0 glint_drift  →  E6 (88) only
  slot 1 burst_pulse  →  E6 only
  slot 2 engine_push  →  alternating E6/B6 (88/95) — 5th
  slot 3 hollow_pause →  E6 only
  slot 4 rebuild_lift →  alternating E6/B6
  slot 5 payoff_storm →  alternating E6/B6
"""
from __future__ import annotations
import os, time

os.environ.setdefault("LIVE_CHANNEL_ENABLED", "1")

from thelmic.live_channel import LiveChannel


# ── Timing/velocity data carried from previous slots ──────────────────────

# PIPER slot 2 — engine_push (39 notes, cascading)
PIPER_S2_TIMES = [
    (0.0, 100), (0.25, 86), (0.5, 80), (0.75, 76),
    (1.0,  90), (1.25, 80), (1.5, 82), (1.75, 74),
    (2.0,  88), (2.25, 78), (2.5, 80), (2.75, 92),
    (3.0,  76), (3.5,  80), (3.75, 84),
    (4.0,  94), (4.5,  82), (5.0,  86), (5.5, 78),
    (6.0,  88), (6.5,  80), (7.0,  84), (7.5, 100),
    (8.0,  92), (8.5,  80), (9.0,  84), (9.5, 78),
    (10.0, 86), (10.5, 80), (11.0, 82), (11.5, 92),
    (12.0,100), (12.5, 78), (13.0, 82), (13.5, 80),
    (14.0, 88), (14.5, 84), (15.0, 90), (15.5,100),
]
# PIPER slot 3 — hollow_pause (6 notes, sparse)
PIPER_S3_TIMES = [(0.0,80),(3.0,72),(5.5,68),(8.0,78),(11.0,70),(13.5,84)]
# PIPER slot 4 — rebuild_lift (21 notes)
PIPER_S4_TIMES = [
    (0.0,76),(1.5,78),(3.0,80),
    (4.0,84),(5.0,82),(6.5,86),(7.5,88),
    (8.0,90),(8.75,84),(9.5,88),(10.5,86),
    (11.0,84),(11.5,90),
    (12.0,94),(12.5,80),(13.0,92),(13.5,84),
    (14.0,98),(14.5,88),(15.0,92),(15.5,100),
]
# PIPER slot 5 — payoff_storm (30 notes)
PIPER_S5_TIMES = [
    (0.0,100),(0.5,88),(1.0,84),(1.5,80),
    (2.0,92),(2.5,84),(3.0,80),(3.5,86),
    (4.0,90),(4.5,78),(5.0,76),(5.5,96),
    (6.0,78),(6.5,80),(7.0,88),(7.5,76),
    (8.0,100),(8.5,92),(9.0,86),
    (10.0,88),(10.5,82),(11.0,80),(11.5,88),
    (12.0,90),(12.5,80),(13.0,84),
    (14.0,88),(14.5,80),(15.0,96),(15.5,100),
]


# MICA timing — reuse the patterns already built
def burst_16ths():
    out = []
    for w in (0.0, 4.0, 8.0, 12.0):
        for j in range(8): out.append(w + j * 0.25)
    return out

def ramp_clicks():
    return ([i * 0.5 for i in range(8)]
            + [4 + i * 0.5 for i in range(8)]
            + [8 + i * 0.25 for i in range(16)]
            + [12 + i * 0.25 for i in range(8)]
            + [14 + i * 0.125 for i in range(16)])

MICA_TIMES = {
    0: [i * 0.75 for i in range(21) if i*0.75 < 16.0],
    1: burst_16ths(),
    2: [i * 0.5 for i in range(32)],
    3: [0.0, 4.0, 8.0, 12.0],
    4: ramp_clicks(),
    5: [i * 0.5 for i in range(32)],
}


# ── Pitch plans ────────────────────────────────────────────────────────────
# (pitches list, single-or-alternating)
PIPER_PLAN = {
    2: ([76, 71], "engine_push"),     # E5/B4 alternating
    3: ([64],     "hollow_pause"),    # E4 only
    4: ([64, 71], "rebuild_lift"),    # E4/B4 alternating
    5: ([76],     "payoff_storm"),    # E5 only
}
PIPER_DATA = {2: PIPER_S2_TIMES, 3: PIPER_S3_TIMES, 4: PIPER_S4_TIMES, 5: PIPER_S5_TIMES}
PIPER_DUR = 0.18

MICA_PLAN = {
    0: ([88],     "glint_drift"),
    1: ([88],     "burst_pulse"),
    2: ([88, 95], "engine_push"),
    3: ([88],     "hollow_pause"),
    4: ([88, 95], "rebuild_lift"),
    5: ([88, 95], "payoff_storm"),
}
MICA_DUR = 0.12


def main():
    ch = LiveChannel(); ch.start(); time.sleep(0.6)
    try:
        # ── PIPER (T4) slots 2-5 ──
        for slot, (pitches, name) in PIPER_PLAN.items():
            times = PIPER_DATA[slot]
            notes = []
            for i, (t, v) in enumerate(times):
                notes.append({
                    "pitch": pitches[i % len(pitches)],
                    "start_time": t,
                    "duration": PIPER_DUR,
                    "velocity": v,
                })
            ch.add_notes_to_clip(4, slot, notes, replace=True).result(timeout=10)
            print(f"[PIPER slot {slot}] {name}: {len(notes)} notes on pitches {pitches}")

        # ── MICA (T5) all slots ──
        for slot, (pitches, name) in MICA_PLAN.items():
            times = MICA_TIMES[slot]
            notes = []
            for i, t in enumerate(times):
                notes.append({
                    "pitch": pitches[i % len(pitches)],
                    "start_time": t,
                    "duration": MICA_DUR,
                    "velocity": 96 if i % 3 == 0 else 72,
                })
            ch.add_notes_to_clip(5, slot, notes, replace=True).result(timeout=10)
            print(f"[MICA  slot {slot}] {name}: {len(notes)} notes on pitches {pitches}")
    finally:
        ch.stop()


if __name__ == "__main__":
    main()
