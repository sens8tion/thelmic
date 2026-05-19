"""Phase 5 — MICA_THROB shimmer layer.

Operator FM bell:
  Op A: sine carrier (high register)
  Op B: modulator at 3.5:1 inharmonic ratio → glass/bell tone
  Bell envelope: zero attack, medium decay, no sustain

Rhythmic element: dotted-8th pulse (every 0.75 beat) — 21 hits across 16 beats,
deliberately cross-rhythmic against the 4/4 grid. Pitch cycles through high
E minor pentatonic for shimmer movement.

Routed with send to A-Reverb for halo.
"""
from __future__ import annotations
import os, time

os.environ.setdefault("LIVE_CHANNEL_ENABLED", "1")

from thelmic.live_channel import LiveChannel


# High E minor pentatonic — E6, G6, A6, B6, D7
PENTA_HIGH = [88, 91, 93, 95, 98]

# Dotted 8th = 0.75 beat
PULSE = 0.75


def main() -> None:
    ch = LiveChannel(); ch.start(); time.sleep(0.6)
    try:
        s = ch.get_session_info().result(timeout=3)
        T = s["track_count"]
        ch.create_midi_track(T).result(timeout=5)
        ch.set_track_name(T, "MICA_THROB").result(timeout=3)
        ch.load_device(T, "query:Synths#Operator").result(timeout=20)

        # FM bell patch — Op B modulating Op A, inharmonic ratio
        for n, v in [
            ("Algorithm",    0.0),       # default: B → A
            # Op A — high sine carrier
            ("Osc-A Level",  1.0),
            ("Osc-A Wave",   0.0),
            ("A Coarse",     1.0),
            ("Osc-A Feedb",  0.0),
            # Bell envelope on A
            ("Ae Attack",    0.0),
            ("Ae Decay",     0.35),
            ("Ae Sustain",   0.0),
            ("Ae Release",   0.20),
            # Op B — modulator at inharmonic ratio
            ("Osc-B Level",  0.55),
            ("B Coarse",     3.0),       # ratio 3
            ("B Fine",       500.0),     # +half coarse → effective 3.5:1
            ("Be Attack",    0.0),
            ("Be Decay",     0.18),      # faster decay than A → shimmer fades quickly
            ("Be Sustain",   0.0),
            # Silence C/D
            ("Osc-C Level",  0.0),
            ("Osc-D Level",  0.0),
            # Light high-pass via filter (or leave open) — open for full shimmer
            ("Filter On",    0.0),
            # Subtle LFO for movement
            ("LFO On",       1.0),
            ("LFO Type",     0.0),       # sine
            ("LFO Sync",     6.0),       # synced
            ("LFO Amt",      0.18),
            ("LFO < Pe",     1.0),
            ("Volume",       0.42),
        ]:
            ch.set_device_param(T, 0, n, v).result(timeout=3)

        # Send to A-Reverb (send index 0)
        ch.set_send(T, 0, 0.55).result(timeout=3)

        # Build the rhythmic pulse — 21 dotted-8th hits, cycling pentatonic
        notes = []
        for i in range(21):
            t = i * PULSE
            if t >= 16.0:
                break
            pitch = PENTA_HIGH[i % len(PENTA_HIGH)]
            # Velocity wave — accent every 3rd hit for shimmer pulsing
            vel = 96 if i % 3 == 0 else 72
            notes.append({"pitch": pitch, "start_time": t, "duration": 0.12, "velocity": vel})

        ch.create_clip(T, 0, length_beats=16.0).result(timeout=5)
        ch.set_clip_name(T, 0, "glint_drift").result(timeout=3)
        ch.add_notes_to_clip(T, 0, notes).result(timeout=5)

        print(f"[done] MICA_THROB @ T{T} | {len(notes)} hits | dotted-8th pulse | A-Reverb send=0.55")
    finally:
        ch.stop()


if __name__ == "__main__":
    main()
