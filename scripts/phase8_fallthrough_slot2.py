"""Phase 8 — slot 2 FALLTHROUGH: bridges burst_pulse → hollow_pause.

Density tapers across the 4 bars on every track. Pitch logic matches the
collapsed-pitch direction (single notes / fifths), no melodic sweeping
except in PIPER_PLUNGE which descends to land on E4 (hollow_pause's first
note).
"""
from __future__ import annotations
import os, time

os.environ.setdefault("LIVE_CHANNEL_ENABLED", "1")

from thelmic.live_channel import LiveChannel

CLIP_LEN = 16.0
SLOT = 2
NAME = "fallthrough"

# ── KLIK_SAINT (T0): bursts shrink each bar ───────────────────────────────
# bar1: 8 sixteenths in beats 0-2
# bar2: 4 eighths in beats 4-6
# bar3: 2 quarters in beats 8-10
# bar4: 1 hit at beat 12, then silence
CLICK_HITS = (
    [i * 0.25 for i in range(8)]                # bar1: 8 × 16ths
    + [4.0 + i * 0.5 for i in range(4)]         # bar2: 4 × 8ths
    + [8.0, 9.0]                                # bar3: 2 × quarters
    + [12.0]                                    # bar4: 1 hit
)

# ── KIK_HOOF (T1): tapering 3-2-1-1 ───────────────────────────────────────
KICK_HITS = [0.0, 1.5, 2.75,                    # bar1: 3
             4.0, 5.5,                          # bar2: 2
             8.0,                               # bar3: 1
             12.0]                              # bar4: 1

# ── SUB_BOOM (T2/T3): motif degrades into longer holds ────────────────────
# (start, duration) — single pitch E1
SUB_NOTES = [
    (0.0,  1.0),                                # stab
    (1.5,  0.5),                                # stab
    (2.75, 0.5),                                # stab
    (4.0,  3.5),                                # long held (motif's signature)
    (8.0,  3.5),                                # bar3: long held only
    (12.0, 3.9),                                # bar4: longest held, fading into hollow
]

# ── PIPER_PLUNGE (T4): staccato descent landing on E4 ─────────────────────
# Pitch steps down: E5 → D5 → B4 → A4 → G4 → E4 (hollow_pause's first note)
PIPER_NOTES = [
    (0.0,  76, 88),                             # E5 bar1
    (1.5,  74, 80),                             # D5
    (3.0,  71, 84),                             # B4
    (4.0,  71, 86),                             # B4 bar2
    (5.5,  69, 78),                             # A4
    (7.0,  67, 82),                             # G4
    (8.0,  67, 84),                             # G4 bar3
    (10.0, 64, 78),                             # E4 (anchor)
    (12.0, 64, 80),                             # E4 bar4 (settled)
    (14.0, 64, 72),                             # E4 (whisper before hollow)
]

# ── MICA_THROB (T5): thinning pulses, single E6 ───────────────────────────
MICA_HITS = (
    [i * 0.25 for i in range(8)]                # bar1: 16ths burst
    + [4.0 + i * 0.5 for i in range(4)]         # bar2: 8ths
    + [8.0, 9.0]                                # bar3: quarters
    + [12.0]                                    # bar4: single
)

# ── MOIRE_DRIFT (T6): two long swells, each longer than the last ──────────
# Sets up the single 15.5-beat wave of hollow_pause
MOIRE_NOTES = [
    (0.0, 7.0,  88, 70),                        # 7-beat swell at E6
    (8.0, 7.5,  88, 76),                        # 7.5-beat swell — leans into the breakdown
]


def main():
    ch = LiveChannel(); ch.start(); time.sleep(0.6)
    try:
        # Make sure clip exists fresh
        for ti in (0, 1, 2, 3, 4, 5, 6):
            try:
                ch.clear_clip(ti, SLOT).result(timeout=3)
            except Exception:
                pass
            ch.create_clip(ti, SLOT, length_beats=CLIP_LEN).result(timeout=5)
            ch.set_clip_name(ti, SLOT, NAME).result(timeout=3)

        # T0 click
        click_notes = [{"pitch":96,"start_time":t,"duration":0.0625,"velocity":88}
                       for t in CLICK_HITS]
        ch.add_notes_to_clip(0, SLOT, click_notes).result(timeout=5)

        # T1 kick
        kick_notes = [{"pitch":36,"start_time":t,"duration":0.0625,"velocity":110}
                      for t in KICK_HITS]
        ch.add_notes_to_clip(1, SLOT, kick_notes).result(timeout=5)

        # T2 / T3 sub (both layers same content)
        sub_notes = [{"pitch":28,"start_time":t,"duration":d,"velocity":105}
                     for t,d in SUB_NOTES]
        for ti in (2, 3):
            ch.add_notes_to_clip(ti, SLOT, sub_notes).result(timeout=5)

        # T4 PIPER
        piper_notes = [{"pitch":p,"start_time":t,"duration":0.18,"velocity":v}
                       for t,p,v in PIPER_NOTES]
        ch.add_notes_to_clip(4, SLOT, piper_notes).result(timeout=5)

        # T5 MICA
        mica_notes = [{"pitch":88,"start_time":t,"duration":0.12,
                       "velocity":96 if i%3==0 else 72}
                      for i,t in enumerate(MICA_HITS)]
        ch.add_notes_to_clip(5, SLOT, mica_notes).result(timeout=5)

        # T6 MOIRE
        moire_notes = [{"pitch":p,"start_time":t,"duration":d,"velocity":v}
                       for t,d,p,v in MOIRE_NOTES]
        ch.add_notes_to_clip(6, SLOT, moire_notes).result(timeout=5)

        print(f"[done] slot {SLOT} '{NAME}': "
              f"click x{len(CLICK_HITS)} | kick x{len(KICK_HITS)} | "
              f"sub x{len(SUB_NOTES)} | piper x{len(PIPER_NOTES)} | "
              f"mica x{len(MICA_HITS)} | moire x{len(MOIRE_NOTES)}")
    finally:
        ch.stop()


if __name__ == "__main__":
    main()
