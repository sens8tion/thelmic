"""Phase 1 — clicks on 8ths + non-linear short kicks, all native.

Track 0 (KLIK_SAINT): Operator, straight 8ths over 4 bars.
Track 1 (KIK_HOOF):   DS Kick, non-linear short kicks, no 4-on-floor.
"""
from __future__ import annotations
import os, time

os.environ.setdefault("LIVE_CHANNEL_ENABLED", "1")

from thelmic.live_channel import LiveChannel


BPM = 174.0
BARS = 4
BEATS = BARS * 4

# 32 events on 8ths over 4 bars
CLICK_HITS = [i * 0.5 for i in range(BARS * 8)]

# Non-linear kicks — no four-on-floor, mix of anchors + off-grid stabs
KICK_HITS = [0.0, 2.75, 5.5, 7.0, 8.0, 10.5, 12.0, 14.75]

CLICK_PITCH = 60
KICK_PITCH = 36


def notes(hits, pitch, dur, vel):
    return [{"pitch": pitch, "start_time": t, "duration": dur, "velocity": vel} for t in hits]


def main() -> None:
    ch = LiveChannel(); ch.start(); time.sleep(0.6)
    try:
        ch.set_tempo(BPM).result(timeout=3)

        # Track 0 → click
        ch.set_track_name(0, "KLIK_SAINT").result(timeout=3)
        ch.load_device(0, "query:Synths#Operator").result(timeout=20)
        ch.create_clip(0, 0, length_beats=BEATS).result(timeout=5)
        ch.set_clip_name(0, 0, "tik_pulse").result(timeout=3)
        ch.add_notes_to_clip(0, 0, notes(CLICK_HITS, CLICK_PITCH, dur=0.0625, vel=88)).result(timeout=5)

        # Track 1 → kick
        ch.set_track_name(1, "KIK_HOOF").result(timeout=3)
        ch.load_device(1, "query:Synths#DS%20Kick").result(timeout=20)
        ch.create_clip(1, 0, length_beats=BEATS).result(timeout=5)
        ch.set_clip_name(1, 0, "nonlinear_thud").result(timeout=3)
        ch.add_notes_to_clip(1, 0, notes(KICK_HITS, KICK_PITCH, dur=0.0625, vel=110)).result(timeout=5)

        print(f"[done] {BPM} BPM | click 8ths x{len(CLICK_HITS)} | kicks x{len(KICK_HITS)} @ {KICK_HITS}")
    finally:
        ch.stop()


if __name__ == "__main__":
    main()
