"""Phase 3 — staccato flute, 2-octave descent in E minor across 4 bars.

Operator: single sine carrier shaped into a flute-like pop. Short env, mild
filter, slight pitch-env breath at attack. Phrase descends from E5 to E3,
staying on E natural minor (E F# G A B C D).
"""
from __future__ import annotations
import os, time

os.environ.setdefault("LIVE_CHANNEL_ENABLED", "1")

from thelmic.live_channel import LiveChannel


# (start_time, midi_pitch, velocity) — 4-bar phrase, 16 beats
PHRASE = [
    # Bar 1 — high register, around E5
    (0.0,  76, 100),  # E5
    (0.5,  79,  84),  # G5
    (1.0,  78,  78),  # F#5
    (2.0,  76,  92),  # E5
    (2.5,  74,  80),  # D5
    (3.5,  71,  84),  # B4
    # Bar 2 — middle, descending
    (4.0,  69,  92),  # A4
    (4.5,  67,  78),  # G4
    (5.0,  64,  86),  # E4
    (6.0,  66,  74),  # F#4
    (6.5,  64,  80),  # E4
    (7.5,  62,  84),  # D4
    # Bar 3 — lower, approach
    (8.0,  59,  90),  # B3
    (8.5,  57,  78),  # A3
    (9.5,  55,  84),  # G3
    (10.5, 54,  72),  # F#3
    (11.5, 52,  94),  # E3 — first landing
    # Bar 4 — settle on E3
    (12.0, 52, 100),  # E3
    (12.5, 55,  74),  # G3 grace
    (13.0, 52,  84),  # E3
    (14.0, 54,  70),  # F#3
    (14.5, 52,  80),  # E3
    (15.5, 52,  96),  # E3 final
]

STACCATO_DUR = 0.18  # ~62ms at 174 BPM


def main() -> None:
    ch = LiveChannel(); ch.start(); time.sleep(0.6)
    try:
        s = ch.get_session_info().result(timeout=3)
        T = s["track_count"]  # append at end
        ch.create_midi_track(T).result(timeout=5)
        ch.set_track_name(T, "PIPER_PLUNGE").result(timeout=3)
        ch.load_device(T, "query:Synths#Operator").result(timeout=20)

        # Flute-like Operator: single sine, short pop env, mild lowpass, soft pitch-blow at attack.
        for n, v in [
            # Single Op A sine carrier
            ("Algorithm",     0.0),
            ("Osc-A Level",   1.0),
            ("Osc-A Wave",    0.0),
            ("Osc-A Feedb",   0.0),
            ("A Coarse",      1.0),
            # Staccato amp envelope: quick attack, fast decay to silence
            ("Ae Attack",     0.05),
            ("Ae Decay",      0.18),
            ("Ae Sustain",    0.0),
            ("Ae Release",    0.04),
            # Silence other operators
            ("Osc-B Level",   0.0),
            ("Osc-C Level",   0.0),
            ("Osc-D Level",   0.0),
            # Light pitch-env scoop at attack — flute "blow" articulation
            ("Pe On",         1.0),
            ("Pe Attack",     0.0),
            ("Pe Decay",      0.08),
            ("Pe Sustain",    0.0),
            ("Pe Release",    0.0),
            ("Time",         -40.0),
            # Lowpass for hollow flute timbre
            ("Filter On",     1.0),
            ("Filter Freq",   0.78),
            ("Filter Res",    0.18),
            ("Volume",        0.50),
        ]:
            ch.set_device_param(T, 0, n, v).result(timeout=3)

        # Clip
        ch.create_clip(T, 0, length_beats=16.0).result(timeout=5)
        ch.set_clip_name(T, 0, "two_octave_fall").result(timeout=3)
        notes = [
            {"pitch": p, "start_time": t, "duration": STACCATO_DUR, "velocity": v}
            for t, p, v in PHRASE
        ]
        ch.add_notes_to_clip(T, 0, notes).result(timeout=5)

        lo, hi = min(p for _, p, _ in PHRASE), max(p for _, p, _ in PHRASE)
        print(f"[done] PIPER_PLUNGE @ T{T} | {len(PHRASE)} notes | range {lo}..{hi} (span {hi-lo} st)")
    finally:
        ch.stop()


if __name__ == "__main__":
    main()
