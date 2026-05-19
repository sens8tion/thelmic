"""Phase 2 — sub-boom + rasping twang layer, aligned to kicks.

T?  SUB_BOOM    Operator: pure low sine, bloom envelope (slow decay, no sustain).
T?+1 RASP_GRIND Operator: high feedback + linear sustain env → machine rasp.

Both fire on the same hits as KIK_HOOF, with varying pitches in E minor pentatonic
(low octave). Each kick gets a different sub-pitch so no two booms are the same.
"""
from __future__ import annotations
import os, time

os.environ.setdefault("LIVE_CHANNEL_ENABLED", "1")

from thelmic.live_channel import LiveChannel


KICK_HITS = [0.0, 2.75, 5.5, 7.0, 8.0, 10.5, 12.0, 14.75]

# E minor pentatonic, low octave: E1, G1, A1, B1, D2
SUB_PITCHES = [28, 31, 28, 33, 28, 35, 31, 38]
SUB_DURATIONS = [0.9, 0.6, 1.2, 0.5, 1.4, 0.7, 0.5, 1.0]

ALIGN_OFFSET = 0.0  # exact alignment with kick


def main() -> None:
    ch = LiveChannel(); ch.start(); time.sleep(0.6)
    try:
        # Find next free track indices (append at end).
        info = ch.get_session_info().result(timeout=3)
        n = info["track_count"]
        sub_idx = n          # new track will land at this index
        ch.create_midi_track(sub_idx).result(timeout=5)
        rasp_idx = sub_idx + 1
        ch.create_midi_track(rasp_idx).result(timeout=5)

        # --- SUB_BOOM ---
        ch.set_track_name(sub_idx, "SUB_BOOM").result(timeout=3)
        ch.load_device(sub_idx, "query:Synths#Operator").result(timeout=20)
        # Pure sine, bloom envelope.
        for name, val in [
            ("Ae Attack",  0.0),
            ("Ae Decay",   0.55),  # moderate bloom
            ("Ae Sustain", 0.0),   # no sustain, fades out
            ("Ae Release", 0.25),
            ("Volume",     0.45),
        ]:
            ch.set_device_param(sub_idx, 0, name, val).result(timeout=3)

        ch.create_clip(sub_idx, 0, length_beats=16.0).result(timeout=5)
        ch.set_clip_name(sub_idx, 0, "boom_aligned").result(timeout=3)
        sub_notes = [
            {"pitch": p, "start_time": t + ALIGN_OFFSET, "duration": d, "velocity": 105}
            for t, p, d in zip(KICK_HITS, SUB_PITCHES, SUB_DURATIONS)
        ]
        ch.add_notes_to_clip(sub_idx, 0, sub_notes).result(timeout=5)

        # --- RASP_GRIND ---
        ch.set_track_name(rasp_idx, "RASP_GRIND").result(timeout=3)
        ch.load_device(rasp_idx, "query:Synths#Operator").result(timeout=20)
        # Linear sustained tone with heavy feedback → machine rasp.
        for name, val in [
            ("Ae Attack",  0.02),
            ("Ae Decay",   0.0),    # jump to sustain instantly
            ("Ae Sustain", 0.7),    # flat held level
            ("Ae Release", 0.05),
            ("Osc-A Feedb", 75.0),  # heavy harmonic feedback → buzz
            ("Volume",     0.30),
        ]:
            ch.set_device_param(rasp_idx, 0, name, val).result(timeout=3)

        ch.create_clip(rasp_idx, 0, length_beats=16.0).result(timeout=5)
        ch.set_clip_name(rasp_idx, 0, "machine_twang").result(timeout=3)
        # Rasp follows sub pitch one octave up — sits above the sub, not in it.
        rasp_notes = [
            {"pitch": p + 12, "start_time": t + ALIGN_OFFSET, "duration": d, "velocity": 92}
            for t, p, d in zip(KICK_HITS, SUB_PITCHES, SUB_DURATIONS)
        ]
        ch.add_notes_to_clip(rasp_idx, 0, rasp_notes).result(timeout=5)

        print(f"[done] SUB_BOOM @ T{sub_idx} | RASP_GRIND @ T{rasp_idx}")
        print(f"       pitches={SUB_PITCHES} durations={SUB_DURATIONS}")
    finally:
        ch.stop()


if __name__ == "__main__":
    main()
