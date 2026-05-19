"""Phase 12e — careful, musical breakcore chops.

Amen 170 mapped to its actual structure:
  slice 0  = beat 1 kick      (K1)
  slice 1  = beat 1.25 ghost  (K1g)
  slice 4  = beat 2 snare     (S1)
  slice 5  = beat 2.25 ghost  (S1g)
  slice 6  = beat 2.5 ghost   (G1)
  slice 8  = beat 3 kick      (K2)
  slice 10 = beat 3.5 kick    (K3)
  slice 12 = beat 4 snare     (S2)
  slice 14 = beat 4.5 fill    (F1)

Tempo: amen is 170 BPM, session is 174 → transpose all amen pads +0.4
semitones (about 174/170 ratio) so slices land in tune with the room.

Vocal pads are SHORT syllable slices (0.1-0.15s), not full clips.

Clip patterns are sparse and rhythmic. Each chop is on a meaningful beat
position. Most slots have 2-8 hits.
"""
from __future__ import annotations
import os, time

os.environ.setdefault("LIVE_CHANNEL_ENABLED", "1")

from thelmic.live_channel import LiveChannel

T_BARK = 7
SAMPLE_DIR = "user_library/Samples/Freesound/cranky_hodgkin"
AMEN_TRANSPOSE = 0.4

PAD_MAP = [
    (36, "amen_170.mp3",          0/16,  1/16, AMEN_TRANSPOSE),
    (37, "amen_170.mp3",          1/16,  1/16, AMEN_TRANSPOSE),
    (38, "amen_170.mp3",          4/16,  1/16, AMEN_TRANSPOSE),
    (39, "amen_170.mp3",          5/16,  1/16, AMEN_TRANSPOSE),
    (40, "amen_170.mp3",          6/16,  1/16, AMEN_TRANSPOSE),
    (41, "amen_170.mp3",          8/16,  1/16, AMEN_TRANSPOSE),
    (42, "amen_170.mp3",         10/16,  1/16, AMEN_TRANSPOSE),
    (43, "amen_170.mp3",         12/16,  1/16, AMEN_TRANSPOSE),
    (44, "amen_170.mp3",         14/16,  2/16, AMEN_TRANSPOSE),
    (45, "amen_180_breakcore.mp3", 0.00,  0.08, 0.0),
    (46, "amen_180_breakcore.mp3", 0.35,  0.06, 0.0),
    (47, "reverse_vocal.mp3",      0.00,  0.12, 0.0),
    (48, "vocal_cutups_2.mp3",     0.20,  0.10, 0.0),
    (49, "vocal_cutups_2.mp3",     0.55,  0.10, 0.0),
    (50, "vox_glitch_4.mp3",       0.00,  1.00, 0.0),
    (51, "stutter_vox.mp3",        0.00,  1.00, 0.0),
]

K1, K1g, S1, S1g, G1, K2, K3, S2, F1 = 36, 37, 38, 39, 40, 41, 42, 43, 44
BK, BS = 45, 46
RV, CU1, CU2, GL, ST = 47, 48, 49, 50, 51

BARK_BURSTS = {
    0: [(0.0, K1), (1.0, RV), (2.5, S1)],
    1: [(0.0, K1), (1.5, S1), (2.75, CU1), (4.0, K2),
        (8.0, K1g), (10.75, RV)],
    2: [(0.0, K1), (1.5, S1), (2.75, S1g), (4.0, G1), (6.0, RV)],
    3: [(0.0, RV)],
    4: [(0.0, K1), (1.0, S1), (2.0, K2), (2.5, G1),
        (3.0, S2), (3.25, K3), (3.5, GL), (3.75, ST)],
    5: [(0.0, K1), (0.5, K1g), (1.0, S1), (1.25, S1g),
        (2.0, K2), (2.25, G1), (2.5, K3), (3.0, S2), (3.5, F1),
        (4.0, K1), (4.5, CU1), (5.0, S1), (5.5, RV),
        (6.0, BK), (7.0, S2)],
    6: [(0.0, K1), (0.5, K1g), (1.0, S1), (1.5, K2),
        (2.0, G1), (2.5, K3), (3.0, S2), (3.5, F1),
        (4.0, K1), (4.5, GL), (5.0, S1), (5.5, K2),
        (6.0, ST), (6.5, K3), (7.0, S2), (7.5, BS)],
    7: [(0.0, K1), (0.125, K1g), (0.25, S1g), (0.375, G1), (0.5, S1)],
}


def main():
    ch = LiveChannel(); ch.start(); time.sleep(0.6)
    try:
        for note, fname, start, length, transpose in PAD_MAP:
            ch.load_sample_to_pad(T_BARK, 0, note, SAMPLE_DIR, fname).result(timeout=20)
            ch.set_drum_pad_chain_device_param(
                T_BARK, 0, note, value=start, param_name="S Start"
            ).result(timeout=5)
            ch.set_drum_pad_chain_device_param(
                T_BARK, 0, note, value=length, param_name="S Length"
            ).result(timeout=5)
            if transpose != 0.0:
                ch.set_drum_pad_chain_device_param(
                    T_BARK, 0, note, value=transpose, param_name="Transpose"
                ).result(timeout=5)
            print(f"  pad {note}: {fname[:24]:24} start={start:.3f} len={length:.3f} tr={transpose:+.2f}")

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
