"""Phase 6 — reshape T5 into MOIRE_DRIFT (developing wave shimmer).

Reshape the Operator (T5 dev0) into a noise/metallic wash with slow swell
envelope: no transient, the sound grows in like a reverse cymbal. Trash
(dev1) keeps coloring it. Replace clips slots 0..5 with long held notes
that overlap into a continuous developing wave.
"""
from __future__ import annotations
import os, time

os.environ.setdefault("LIVE_CHANNEL_ENABLED", "1")

from thelmic.live_channel import LiveChannel


T = 5
CLIP_LEN = 16.0

# E minor pentatonic spread across high octaves for shimmery wash
HI_PENTA = [76, 79, 81, 83, 86, 88, 91, 93]  # E5 G5 A5 B5 D6 E6 G6 A6

# ──────────────────────────────────────────────────────────────────────────
# Slot patterns — each "note" is (start, duration, pitch, velocity)
# Notes overlap so waves cross-fade
# ──────────────────────────────────────────────────────────────────────────
SLOTS = {
    0: ("wave_breathe", [
        (0.0,  5.5, 76, 70),
        (4.0,  5.5, 81, 75),
        (8.0,  5.5, 86, 80),
        (12.0, 5.0, 79, 75),
    ]),
    1: ("burst_pulse", [
        # Long swell pair matching the LONG-HELD architecture
        (0.0,  7.5, 79, 72),
        (8.0,  7.5, 83, 78),
    ]),
    2: ("engine_push", [
        # Faster movement, 8 swells, more activity
        (0.0,  2.5, 76, 70), (2.0,  2.5, 81, 72),
        (4.0,  2.5, 79, 74), (6.0,  2.5, 86, 76),
        (8.0,  2.5, 83, 78), (10.0, 2.5, 88, 78),
        (12.0, 2.5, 86, 80), (14.0, 2.5, 91, 84),
    ]),
    3: ("hollow_pause", [
        # Single 16-beat breath — entire scene is one wave
        (0.0, 15.5, 76, 70),
    ]),
    4: ("rebuild_lift", [
        # Ascending wave — each successive note higher + faster
        (0.0,  5.0, 76, 68),
        (3.0,  4.5, 81, 74),
        (6.0,  4.0, 86, 78),
        (9.0,  3.5, 88, 82),
        (11.5, 2.5, 91, 86),
        (13.5, 2.0, 93, 92),
    ]),
    5: ("payoff_storm", [
        # Dense overlapping pentatonic swells — maximum wash
        (0.0,  3.0, 76, 78), (1.5,  3.0, 81, 78),
        (3.0,  3.0, 86, 80), (4.5,  3.0, 88, 82),
        (6.0,  3.0, 83, 80), (7.5,  3.0, 91, 84),
        (9.0,  3.0, 79, 78), (10.5, 3.0, 93, 86),
        (12.0, 3.0, 86, 82), (13.5, 2.5, 88, 88),
    ]),
}


def main() -> None:
    ch = LiveChannel(); ch.start(); time.sleep(0.6)
    try:
        ch.set_track_name(T, "MOIRE_DRIFT").result(timeout=3)

        # ── Reshape Operator (dev0) into noise/metallic wash patch ──
        for n, v in [
            ("Algorithm",     0.0),   # B → A
            # Op A — sine carrier (gets ruined by modulation = wash)
            ("Osc-A Level",   1.0),
            ("Osc-A Wave",    0.0),
            ("A Coarse",      1.0),
            ("Osc-A Feedb",   55.0),  # self-feedback for noise content
            # Slow swell amp envelope — NO transient
            ("Ae Attack",     0.55),  # ~1s+ rise
            ("Ae Decay",      0.0),
            ("Ae Sustain",    1.0),
            ("Ae Release",    0.55),  # slow fade
            # Op B — heavy inharmonic modulation → metallic chaos
            ("Osc-B Level",   0.92),
            ("B Coarse",      11.0),
            ("B Fine",        373.0),
            ("Be Attack",     0.40),  # B also swells, deepens character over time
            ("Be Decay",      0.0),
            ("Be Sustain",    1.0),
            ("Be Release",    0.4),
            ("Osc-B Feedb",   30.0),
            # Silence C/D
            ("Osc-C Level",   0.0),
            ("Osc-D Level",   0.0),
            # Filter — bandpass high for cymbal-shaped spectrum, with LFO motion
            ("Filter On",     1.0),
            ("Filter Freq",   0.82),
            ("Filter Res",    0.55),
            # LFO modulating filter via Pe path (slow developing wave)
            ("LFO On",        1.0),
            ("LFO Type",      0.0),
            ("LFO Sync",      3.0),   # synced, slow
            ("LFO Amt",       0.55),
            ("LFO Retrigger", 1.0),
            ("LFO < Pe",      1.0),
            ("Volume",        0.34),
        ]:
            ch.set_device_param(T, 0, n, v).result(timeout=3)

        # ── Replace clips ──
        for slot, (name, notes) in SLOTS.items():
            ch.clear_clip(T, slot).result(timeout=3)
            ch.create_clip(T, slot, length_beats=CLIP_LEN).result(timeout=5)
            ch.set_clip_name(T, slot, name).result(timeout=3)
            note_list = [{"pitch": p, "start_time": t, "duration": d, "velocity": v}
                         for t, d, p, v in notes]
            ch.add_notes_to_clip(T, slot, note_list).result(timeout=5)
            print(f"[slot {slot}] {name}: {len(notes)} long swells")
    finally:
        ch.stop()


if __name__ == "__main__":
    main()
