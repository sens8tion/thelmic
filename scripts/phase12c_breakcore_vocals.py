"""Phase 12c — breakcore overhaul of T7 BARK_INTONE.

- Replace cliche shout samples with Amen breaks + glitched/reversed vocal chops
- Front-load breakcore bursts at the START of each clip (notes happen in first
  1-4 beats, then silence)
- Set ALL T7 + T8 clips loop=False so they fire single-pass when triggered
"""
from __future__ import annotations
import os, time

os.environ.setdefault("LIVE_CHANNEL_ENABLED", "1")

from thelmic.live_channel import LiveChannel

T_BARK = 7
T_DRONE = 8
SAMPLE_DIR = "user_library/Samples/Freesound/cranky_hodgkin"

PADS = [
    (36, "amen_170.mp3"),               # main amen — long break
    (38, "amen_180_breakcore.mp3"),     # alt amen breakcore
    (40, "vox_glitch_4.mp3"),           # short glitch stutter
    (41, "stutter_vox.mp3"),            # granular stutter
    (43, "reverse_vocal.mp3"),          # reversed vocal phrase
    (45, "vocal_cutups_2.mp3"),         # industrial vocal cut-ups
]

# Pad ID shortcuts
AMEN1, AMEN2, GLITCH, STUTTER, REVERSE, CUTUPS = 36, 38, 40, 41, 43, 45

# ── Breakcore burst patterns per scene ────────────────────────────────────
# All bursts happen at the start of the clip — rest of the clip is silent.
# (time, pad) tuples
BARK_BURSTS = {
    0: [   # intro — sparse: amen + reverse stab
        (0.0, AMEN1), (0.25, REVERSE),
    ],
    1: [   # motif — front cluster, glitch stutters + amen
        (0.0, AMEN1), (0.125, GLITCH), (0.25, STUTTER),
        (0.5, GLITCH), (0.75, REVERSE), (1.0, STUTTER), (1.25, GLITCH),
    ],
    2: [   # fallthrough — burst then taper
        (0.0, AMEN1), (0.125, GLITCH), (0.25, STUTTER), (0.5, GLITCH),
        (1.0, REVERSE), (2.0, CUTUPS),
    ],
    3: [   # hollow_pause — single reverse stab
        (0.0, REVERSE),
    ],
    4: [   # rebuild_lift — ramping breakcore stutters across first 4 beats
        (0.0, AMEN1),
        (0.5, GLITCH), (1.0, GLITCH),
        (1.25, STUTTER), (1.5, GLITCH), (1.75, STUTTER),
        (2.0, GLITCH), (2.125, STUTTER), (2.25, GLITCH), (2.375, STUTTER),
        (2.5, GLITCH), (2.625, STUTTER), (2.75, GLITCH),
        (3.0, CUTUPS),
    ],
    5: [   # payoff_storm — massive breakcore burst, two amen layers + 32nd stutters
        (0.0, AMEN1), (0.125, GLITCH), (0.25, STUTTER), (0.375, GLITCH),
        (0.5, AMEN2), (0.625, STUTTER), (0.75, GLITCH), (0.875, STUTTER),
        (1.0, GLITCH), (1.125, STUTTER), (1.25, REVERSE), (1.5, AMEN1),
        (2.0, AMEN2), (2.5, CUTUPS), (3.0, REVERSE),
    ],
    6: [   # engine_push — continuous breakcore through first 8 beats
        (i * 0.125, [GLITCH, STUTTER, GLITCH, AMEN2][i % 4])
        for i in range(64) if i * 0.125 < 8.0
    ],
    7: [   # anchor_fire — single tight cluster on the clip start
        (0.0, AMEN1), (0.125, GLITCH), (0.25, STUTTER), (0.375, GLITCH),
        (0.5, REVERSE),
    ],
}


def main():
    ch = LiveChannel(); ch.start(); time.sleep(0.6)
    try:
        # ── Add pad 45 if not already present, then reload all 6 pads ──
        for note, fname in PADS:
            ch.load_sample_to_pad(T_BARK, 0, note, SAMPLE_DIR, fname).result(timeout=20)
            print(f"  pad {note}: {fname}")

        # ── Replace BARK clips with breakcore bursts, loop off ──
        for slot, bursts in BARK_BURSTS.items():
            notes = [{"pitch": pad, "start_time": t, "duration": 0.0625, "velocity": 110}
                     for t, pad in bursts]
            ch.add_notes_to_clip(T_BARK, slot, notes, replace=True).result(timeout=10)
            ch.set_clip_loop(T_BARK, slot, False).result(timeout=3)
            print(f"  T7 slot{slot}: {len(notes)} hits front-loaded, loop=off")

        # ── T8 DRONE clips also single-pass ──
        for slot in range(8):
            try:
                ch.set_clip_loop(T_DRONE, slot, False).result(timeout=3)
                print(f"  T8 slot{slot}: loop=off")
            except Exception as e:
                print(f"  T8 slot{slot}: skip ({e})")
    finally:
        ch.stop()


if __name__ == "__main__":
    main()
