"""Build PRE-DROP (scene 3) + DROP OPENER (scene 4) for the jungle session."""
from __future__ import annotations
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from thelmic.live_channel import LiveChannel

KICK, SNARE, HAT_C, HAT_O, RIDE, CRASH = 36, 38, 42, 46, 51, 49


def amen_4bar():
    notes = []
    notes += [(KICK, 0.0, 0.4, 110)]
    notes += [(SNARE, 1.0, 0.35, 100)]
    notes += [(KICK, 1.5, 0.4, 95)]
    notes += [(SNARE, 3.0, 0.35, 105)]
    notes += [(KICK, 4.0, 0.4, 110)]
    notes += [(SNARE, 5.0, 0.35, 100)]
    notes += [(SNARE, 5.5, 0.2, 75)]
    notes += [(SNARE, 6.5, 0.3, 95)]
    notes += [(KICK, 7.5, 0.35, 90)]
    notes += [(KICK, 8.0, 0.4, 110)]
    notes += [(SNARE, 9.0, 0.35, 100)]
    notes += [(KICK, 10.5, 0.35, 95)]
    notes += [(SNARE, 11.0, 0.35, 105)]
    notes += [(KICK, 12.0, 0.4, 110)]
    notes += [(SNARE, 13.0, 0.3, 95)]
    notes += [(SNARE, 13.5, 0.2, 75)]
    notes += [(SNARE, 14.0, 0.35, 100)]
    notes += [(KICK, 14.5, 0.35, 90)]
    notes += [(SNARE, 15.0, 0.3, 95)]
    notes += [(SNARE, 15.5, 0.25, 80)]
    for i in range(64):
        t = i * 0.25
        slot = i % 4
        vel = {0: 92, 1: 65, 2: 78, 3: 65}[slot]
        notes.append((HAT_C, t, 0.18, vel))
    for t in [0.5, 1.5, 2.5, 3.5, 4.5, 5.5, 6.5, 7.5,
              8.5, 9.5, 10.5, 11.5, 12.5, 13.5, 14.5, 15.5]:
        notes.append((HAT_O, t, 0.25, 78))
    return notes


def main():
    ch = LiveChannel(lower_priority=False); ch.start()
    try:
        # ---- PRE-DROP (scene 3) ----
        pre_drums = []
        # bar 5-8: kick on every bar
        for bar in range(4, 8):
            pre_drums.append({"pitch": KICK, "start_time": bar * 4.0, "duration": 0.5, "velocity": 95})
        # bar 9-12: kick + 8th hats
        for bar in range(8, 12):
            pre_drums.append({"pitch": KICK, "start_time": bar * 4.0, "duration": 0.5, "velocity": 100})
            for h in range(8):
                t = bar * 4.0 + h * 0.5
                vel = 60 + (h % 2) * 15
                pre_drums.append({"pitch": HAT_C, "start_time": t, "duration": 0.2, "velocity": vel})
        # bar 13-15: 16th hats with rising intensity, ghost snares
        for bar in range(12, 15):
            pre_drums.append({"pitch": KICK, "start_time": bar * 4.0, "duration": 0.5, "velocity": 105})
            for h in range(16):
                t = bar * 4.0 + h * 0.25
                vel = 55 + (h % 4) * 10 + (bar - 12) * 8
                pre_drums.append({"pitch": HAT_C, "start_time": t, "duration": 0.16, "velocity": vel})
            pre_drums.append({"pitch": SNARE, "start_time": bar * 4.0 + 2.0,
                              "duration": 0.3, "velocity": 70 + (bar - 12) * 10})
        # bar 16: tease — kick + crash on beat 4
        pre_drums.append({"pitch": KICK,  "start_time": 60.0, "duration": 0.5, "velocity": 110})
        pre_drums.append({"pitch": CRASH, "start_time": 60.0, "duration": 4.0, "velocity": 105})

        pre_pad = [
            {"pitch": 55, "start_time": 0.0, "duration": 60.0, "velocity": 75},
            {"pitch": 58, "start_time": 0.0, "duration": 60.0, "velocity": 75},
            {"pitch": 62, "start_time": 0.0, "duration": 60.0, "velocity": 75},
        ]

        pre_stab = []
        for bar in [4, 8, 12]:
            for pitch in [55, 58, 62]:
                pre_stab.append({"pitch": pitch, "start_time": bar * 4.0 + 2.5,
                                 "duration": 0.3, "velocity": 80})

        pre_sub = [{"pitch": 43, "start_time": 60.0, "duration": 3.95, "velocity": 110}]

        # ---- DROP OPENER (scene 4) ----
        drop_drums = []
        for rep in range(4):
            offset = rep * 16.0
            for p, t, dur, vel in amen_4bar():
                drop_drums.append({"pitch": p, "start_time": t + offset, "duration": dur, "velocity": vel})
        drop_drums.append({"pitch": CRASH, "start_time": 0.0, "duration": 4.0, "velocity": 115})
        drop_drums.append({"pitch": KICK,  "start_time": 0.0, "duration": 0.5, "velocity": 120})

        SUB_ROOTS = [43, 39, 41, 43]
        drop_sub = []
        for chord_idx, root in enumerate(SUB_ROOTS):
            chord_start = chord_idx * 16.0
            for bar in range(4):
                drop_sub.append({"pitch": root, "start_time": chord_start + bar * 4.0,
                                 "duration": 3.95, "velocity": 110})

        TRIADS = [[55, 58, 62], [51, 55, 58], [53, 57, 60], [55, 58, 62]]
        drop_stab = []
        for chord_idx, triad in enumerate(TRIADS):
            chord_start = chord_idx * 16.0
            for bar in range(4):
                bar_start = chord_start + bar * 4.0
                for off in [0.5, 1.5, 2.5, 3.5]:
                    t = bar_start + off
                    vel = 95 if off == 0.5 else 88
                    for pitch in triad:
                        drop_stab.append({"pitch": pitch, "start_time": t,
                                          "duration": 0.22, "velocity": vel})

        drop_pad = []
        for chord_idx, triad in enumerate(TRIADS):
            chord_start = chord_idx * 16.0
            for pitch in triad:
                drop_pad.append({"pitch": pitch, "start_time": chord_start,
                                 "duration": 15.5, "velocity": 75})

        # Write all clips
        def write(track, slot, name, notes):
            ch.create_clip(track, slot, 64.0).result(timeout=10)
            ch.set_clip_name(track, slot, name).result(timeout=5)
            ch.add_notes_to_clip(track, slot, notes).result(timeout=10)
            print(f"  T{track} S{slot}: {name} ({len(notes)} notes)")

        print("PRE-DROP scene 3:")
        write(0, 3, "predrop_breath", pre_drums)
        write(1, 3, "predrop_silence", pre_sub)
        write(4, 3, "predrop_whisper", pre_stab)
        write(5, 3, "predrop_swell", pre_pad)

        print("DROP OPENER scene 4:")
        write(0, 4, "drop_OPENER_smash", drop_drums)
        write(1, 4, "drop_OPENER_sub", drop_sub)
        write(4, 4, "drop_OPENER_skank", drop_stab)
        write(5, 4, "drop_OPENER_pad", drop_pad)

        # Pre-drop pad filter swell
        print("PRE-DROP automation envelopes...")
        swell = [(0.0, 0.30), (16.0, 0.35), (32.0, 0.45), (48.0, 0.60), (60.0, 0.78), (63.99, 0.85)]
        ch.set_clip_envelope(5, 3, 5, 0, "Filter Freq", swell).result(timeout=10)

        info = ch.get_track_info(0).result(timeout=5)
        db_idx = next(i for i, d in enumerate(info["devices"]) if d["class_name"] == "DrumBuss")
        drive_swell = [(0.0, 0.20), (40.0, 0.25), (56.0, 0.35), (60.0, 0.50), (63.99, 0.55)]
        ch.set_clip_envelope(0, 3, 0, db_idx, "Drive", drive_swell).result(timeout=10)
        print("  pad filter swell + drum buss drive swell")

        ch.fire_scene(3).result(timeout=5)
        print()
        print("FIRED scene 3 (PRE-DROP). Click scene 4 (DROP OPENER) to fall in.")
    finally:
        ch.stop()


if __name__ == "__main__":
    main()
