"""Phase 9 — slot 7 ANCHOR_FIRE: thinned payoff_storm focused on the 'ones'.

Bar downbeats (beats 0, 4, 8, 12) get the impact. Each downbeat is hit by
the full stack — kick, sub, piper, plus a small 16th-cluster on klik/mica
to keep momentum. Between bars: silence on percussion, sustained sub/moire
carries the energy without being busy.
"""
from __future__ import annotations
import os, time

os.environ.setdefault("LIVE_CHANNEL_ENABLED", "1")

from thelmic.live_channel import LiveChannel

CLIP_LEN = 16.0
SLOT = 7
NAME = "anchor_fire"

ONES = [0.0, 4.0, 8.0, 12.0]

# Klik/Mica: 4-hit 16th cluster starting on each "one" — burst then silence
CLUSTER = [0.0, 0.25, 0.5, 0.75]
BURST_HITS = [o + c for o in ONES for c in CLUSTER]  # 16 hits

# Kick: just the ones — 4 anchor impacts
KICK_HITS = list(ONES)

# Sub: 4 long held booms on each one, 3.5 beats each
SUB_NOTES = [(t, 3.5) for t in ONES]

# Piper: E5 anchor only on each one
PIPER_HITS = list(ONES)

# Moire: 4 long swells, one per bar, starting on each downbeat
MOIRE_NOTES = [(t, 3.8, 88, 86) for t in ONES]


def main():
    ch = LiveChannel(); ch.start(); time.sleep(0.6)
    try:
        for ti in (0, 1, 2, 3, 4, 5, 6):
            try:
                ch.clear_clip(ti, SLOT).result(timeout=3)
            except Exception:
                pass
            ch.create_clip(ti, SLOT, length_beats=CLIP_LEN).result(timeout=5)
            ch.set_clip_name(ti, SLOT, NAME).result(timeout=3)

        # T0 KLIK — 16th-cluster bursts on the ones
        click_notes = [{"pitch":96,"start_time":t,"duration":0.0625,
                        "velocity":98 if i%4==0 else 78}
                       for i,t in enumerate(BURST_HITS)]
        ch.add_notes_to_clip(0, SLOT, click_notes).result(timeout=5)

        # T1 KIK — only the ones
        kick_notes = [{"pitch":36,"start_time":t,"duration":0.0625,"velocity":115}
                      for t in KICK_HITS]
        ch.add_notes_to_clip(1, SLOT, kick_notes).result(timeout=5)

        # T2/T3 SUB — long held booms on the ones
        sub_notes = [{"pitch":28,"start_time":t,"duration":d,"velocity":108}
                     for t,d in SUB_NOTES]
        for ti in (2, 3):
            ch.add_notes_to_clip(ti, SLOT, sub_notes).result(timeout=5)

        # T4 PIPER — single E5 stab on each one
        piper_notes = [{"pitch":76,"start_time":t,"duration":0.18,"velocity":94}
                       for t in PIPER_HITS]
        ch.add_notes_to_clip(4, SLOT, piper_notes).result(timeout=5)

        # T5 MICA — same burst pattern as klik (E6)
        mica_notes = [{"pitch":88,"start_time":t,"duration":0.12,
                       "velocity":96 if i%4==0 else 72}
                      for i,t in enumerate(BURST_HITS)]
        ch.add_notes_to_clip(5, SLOT, mica_notes).result(timeout=5)

        # T6 MOIRE — long swells, one per bar
        moire_notes = [{"pitch":p,"start_time":t,"duration":d,"velocity":v}
                       for t,d,p,v in MOIRE_NOTES]
        ch.add_notes_to_clip(6, SLOT, moire_notes).result(timeout=5)

        print(f"[done] slot {SLOT} '{NAME}': "
              f"klik x{len(click_notes)} | kik x{len(kick_notes)} | "
              f"sub x{len(sub_notes)} | piper x{len(piper_notes)} | "
              f"mica x{len(mica_notes)} | moire x{len(moire_notes)}")
    finally:
        ch.stop()


if __name__ == "__main__":
    main()
