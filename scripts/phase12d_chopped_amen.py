"""Phase 12d — chop the amen + vocals across pads, breakcore reshuffle.

Strategy: load the same source sample onto multiple pads, but set each pad's
Simpler S Start / S Length so it plays a DIFFERENT SLICE. Then breakcore
clip patterns stutter between adjacent slices for real chopped feel rather
than full-sample retriggers.

Pad map (16 pads, 36-51):
  36-43  amen_170          8 equal slices (1/8 each)
  44-46  amen_180_breakcore  3 slices
  47     reverse_vocal     full
  48-49  vocal_cutups_2    2 slices
  50     vox_glitch_4      full
  51     stutter_vox       full
"""
from __future__ import annotations
import os, time

os.environ.setdefault("LIVE_CHANNEL_ENABLED", "1")

from thelmic.live_channel import LiveChannel

T_BARK = 7
SAMPLE_DIR = "user_library/Samples/Freesound/cranky_hodgkin"


# (pad_note, sample_filename, S_start, S_length)
PAD_MAP = [
    # 8 amen slices
    (36, "amen_170.mp3",            0.000, 0.125),
    (37, "amen_170.mp3",            0.125, 0.125),
    (38, "amen_170.mp3",            0.250, 0.125),
    (39, "amen_170.mp3",            0.375, 0.125),
    (40, "amen_170.mp3",            0.500, 0.125),
    (41, "amen_170.mp3",            0.625, 0.125),
    (42, "amen_170.mp3",            0.750, 0.125),
    (43, "amen_170.mp3",            0.875, 0.125),
    # 3 breakcore amen slices (different break, harsher)
    (44, "amen_180_breakcore.mp3",  0.000, 0.20),
    (45, "amen_180_breakcore.mp3",  0.30,  0.20),
    (46, "amen_180_breakcore.mp3",  0.60,  0.20),
    # vocal layer
    (47, "reverse_vocal.mp3",       0.000, 1.000),
    (48, "vocal_cutups_2.mp3",      0.000, 0.30),
    (49, "vocal_cutups_2.mp3",      0.40,  0.30),
    (50, "vox_glitch_4.mp3",        0.000, 1.000),
    (51, "stutter_vox.mp3",         0.000, 1.000),
]

# Pad name shortcuts for clip patterns
A0, A1, A2, A3, A4, A5, A6, A7 = 36, 37, 38, 39, 40, 41, 42, 43       # amen slices
B0, B1, B2 = 44, 45, 46                                                # breakcore amen slices
REV, CU1, CU2, GLI, STU = 47, 48, 49, 50, 51                          # vocal layer

# ── Breakcore burst patterns — front-loaded, single-pass ─────────────────
# Stutter between slices = real chopped feel
BARK_BURSTS = {
    0: [   # intro — sparse intro chop: kick slice + reverse stab
        (0.0, A0), (0.5, REV),
    ],
    1: [   # motif — quick chop walk through amen + glitch
        (0.0, A0), (0.25, A2), (0.5, A4), (0.75, A6),
        (1.0, GLI), (1.25, STU), (1.5, REV), (2.0, A1),
    ],
    2: [   # fallthrough — burst then taper, last hit reverse
        (0.0, A0), (0.125, A1), (0.25, A2), (0.375, GLI),
        (0.5, STU), (1.0, A4), (2.0, REV),
    ],
    3: [   # hollow_pause — single reverse stab only
        (0.0, REV),
    ],
    4: [   # rebuild_lift — ramping amen chop walk through all 8 slices
        (0.0,   A0), (0.5,   A1), (1.0,   A2),
        (1.25,  A3), (1.5,   A4), (1.75,  A5),
        (2.0,   GLI),(2.125, A6), (2.25,  STU), (2.375, A7),
        (2.5,   GLI),(2.625, A0), (2.75,  STU), (2.875, A1),
        (3.0,   CU1),(3.25,  CU2),(3.5,   B0),  (3.75,  B1),
    ],
    5: [   # payoff_storm — massive breakcore chop salad
        (0.0, A0), (0.125, A2), (0.25, A4), (0.375, A6),
        (0.5, B0), (0.625, B1), (0.75, B2), (0.875, GLI),
        (1.0, STU), (1.125, REV), (1.25, A1), (1.375, A3),
        (1.5, A5), (1.625, A7), (1.75, B0), (1.875, B2),
        (2.0, CU1), (2.25, CU2), (2.5, GLI), (2.75, STU),
        (3.0, REV), (3.5, B1),
    ],
    6: [   # engine_push — continuous breakcore 32nds across 8 beats
        (i * 0.125, [A0, A1, A2, A3, A4, A5, A6, A7,
                     B0, B1, B2, GLI, STU][i % 13])
        for i in range(64) if i * 0.125 < 8.0
    ],
    7: [   # anchor_fire — tight burst then quiet
        (0.0, A0), (0.125, A2), (0.25, A4), (0.375, A6),
        (0.5, B0), (0.75, REV),
    ],
}


def main():
    ch = LiveChannel(); ch.start(); time.sleep(0.6)
    try:
        # ── Load samples onto all 16 pads, set Start/Length per pad ──
        for note, fname, start, length in PAD_MAP:
            ch.load_sample_to_pad(T_BARK, 0, note, SAMPLE_DIR, fname).result(timeout=20)
            # Set the Simpler in this pad's chain (chain_device_index 0)
            ch.set_drum_pad_chain_device_param(
                T_BARK, 0, note, value=start, param_name="S Start"
            ).result(timeout=5)
            ch.set_drum_pad_chain_device_param(
                T_BARK, 0, note, value=length, param_name="S Length"
            ).result(timeout=5)
            print(f"  pad {note}: {fname} [start={start:.3f} length={length:.3f}]")

        # ── Apply breakcore burst patterns, loop=off ──
        for slot, bursts in BARK_BURSTS.items():
            notes = [{"pitch": pad, "start_time": t, "duration": 0.0625, "velocity": 110}
                     for t, pad in bursts]
            ch.add_notes_to_clip(T_BARK, slot, notes, replace=True).result(timeout=10)
            ch.set_clip_loop(T_BARK, slot, False).result(timeout=3)
            print(f"  T7 slot{slot}: {len(notes)} chops, loop=off")
    finally:
        ch.stop()


if __name__ == "__main__":
    main()
