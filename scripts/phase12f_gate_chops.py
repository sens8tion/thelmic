"""Phase 12f — gate-mode chopping so clips don't play in full.

Trigger Mode = 1 (Gate) makes the sample play only while the MIDI note
is held. Combined with short clip-note durations, we get clean chops
bounded by the note length, not the sample length.

Also try to switch Simpler to 1-Shot playback mode via device property
as a belt-and-braces approach.
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

# (start_time, pad, duration_in_beats)
# Note durations chosen per chop intent: 0.125 = tight 32nd, 0.25 = 16th chop,
# 0.5 = 8th syllable. Vocal pads get longer notes so syllable plays.
BARK_BURSTS = {
    0: [(0.0, K1, 0.25), (1.0, RV, 0.5), (2.5, S1, 0.25)],
    1: [(0.0, K1, 0.25), (1.5, S1, 0.25), (2.75, CU1, 0.4), (4.0, K2, 0.25),
        (8.0, K1g, 0.25), (10.75, RV, 0.4)],
    2: [(0.0, K1, 0.25), (1.5, S1, 0.25), (2.75, S1g, 0.2),
        (4.0, G1, 0.2), (6.0, RV, 0.4)],
    3: [(0.0, RV, 0.5)],
    4: [(0.0, K1, 0.25), (1.0, S1, 0.25), (2.0, K2, 0.25), (2.5, G1, 0.2),
        (3.0, S2, 0.25), (3.25, K3, 0.2), (3.5, GL, 0.2), (3.75, ST, 0.2)],
    5: [(0.0, K1, 0.25), (0.5, K1g, 0.2), (1.0, S1, 0.25), (1.25, S1g, 0.15),
        (2.0, K2, 0.25), (2.25, G1, 0.15), (2.5, K3, 0.2), (3.0, S2, 0.25), (3.5, F1, 0.3),
        (4.0, K1, 0.25), (4.5, CU1, 0.3), (5.0, S1, 0.25), (5.5, RV, 0.3),
        (6.0, BK, 0.2), (7.0, S2, 0.25)],
    6: [(0.0, K1, 0.25), (0.5, K1g, 0.2), (1.0, S1, 0.25), (1.5, K2, 0.2),
        (2.0, G1, 0.2), (2.5, K3, 0.2), (3.0, S2, 0.25), (3.5, F1, 0.25),
        (4.0, K1, 0.25), (4.5, GL, 0.2), (5.0, S1, 0.25), (5.5, K2, 0.2),
        (6.0, ST, 0.2), (6.5, K3, 0.2), (7.0, S2, 0.25), (7.5, BS, 0.2)],
    7: [(0.0, K1, 0.15), (0.125, K1g, 0.1), (0.25, S1g, 0.1),
        (0.375, G1, 0.1), (0.5, S1, 0.3)],
}


def main():
    ch = LiveChannel(); ch.start(); time.sleep(0.6)
    try:
        for note, fname, start, length, transpose in PAD_MAP:
            ch.load_sample_to_pad(T_BARK, 0, note, SAMPLE_DIR, fname).result(timeout=20)
            # Try to switch to one-shot mode (best-effort, may silently fail)
            try:
                ch._enqueue('set_drum_pad_chain_device_property', {
                    'track_index': T_BARK, 'device_index': 0, 'note': note,
                    'chain_device_index': 0,
                    'property_name': 'playback_mode', 'value': 1,
                }).result(timeout=3)
            except Exception:
                pass
            # Gate mode + fast release + S Start/Length + no snap
            for pname, pval in [
                ("Snap",        0.0),
                ("Trigger Mode", 1.0),     # Gate mode — respect note off
                ("Ve Release",  0.0),      # cut instantly on note off
                ("Ve Sustain",  1.0),
                ("S Start",     start),
                ("S Length",    length),
            ]:
                ch.set_drum_pad_chain_device_param(
                    T_BARK, 0, note, value=pval, param_name=pname
                ).result(timeout=5)
            if transpose != 0.0:
                ch.set_drum_pad_chain_device_param(
                    T_BARK, 0, note, value=transpose, param_name="Transpose"
                ).result(timeout=5)
            print(f"  pad {note}: {fname[:22]:22} start={start:.3f} len={length:.3f}")

        for slot, bursts in BARK_BURSTS.items():
            notes = [{"pitch": pad, "start_time": t, "duration": dur, "velocity": 110}
                     for t, pad, dur in bursts]
            ch.add_notes_to_clip(T_BARK, slot, notes, replace=True).result(timeout=10)
            ch.set_clip_loop(T_BARK, slot, False).result(timeout=3)
            print(f"  T7 slot{slot}: {len(notes)} chops (gated), loop=off")
    finally:
        ch.stop()


if __name__ == "__main__":
    main()
