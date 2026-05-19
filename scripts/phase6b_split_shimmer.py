"""Restore MICA_THROB on T5 + add MOIRE_DRIFT as a new T6.

T5 keeps its existing Trash device; only the Operator and clips are restored.
T6 is freshly created with the noise/metallic wash patch.
"""
from __future__ import annotations
import os, time

os.environ.setdefault("LIVE_CHANNEL_ENABLED", "1")

from thelmic.live_channel import LiveChannel


T_MICA = 5
CLIP_LEN = 16.0
PENTA = [88, 91, 93, 95, 98]


# ──────────────────────────────────────────────────────────────────────────
# MICA_THROB clip patterns (restoring previous state)
# ──────────────────────────────────────────────────────────────────────────
def burst_16ths():
    out = []
    for w in (0.0, 4.0, 8.0, 12.0):
        for j in range(8): out.append(w + j * 0.25)
    return out

def ramp_clicks():
    out = ([i * 0.5 for i in range(8)]
           + [4 + i * 0.5 for i in range(8)]
           + [8 + i * 0.25 for i in range(16)]
           + [12 + i * 0.25 for i in range(8)]
           + [14 + i * 0.125 for i in range(16)])
    return out

def sixteenth_triplets():
    return [round(i * (1/6.0), 4) for i in range(96) if i * (1/6.0) < 16.0]

MICA_SLOTS = {
    0: ("glint_drift",    [i * 0.75 for i in range(21) if i*0.75 < 16.0]),
    1: ("burst_pulse",    burst_16ths()),
    2: ("engine_push",    [i * 0.5 for i in range(32)]),
    3: ("hollow_pause",   [0.0, 4.0, 8.0, 12.0]),
    4: ("rebuild_lift",   ramp_clicks()),
    5: ("payoff_storm",   sixteenth_triplets()),
}


# ──────────────────────────────────────────────────────────────────────────
# MOIRE_DRIFT clip patterns (long swells)
# ──────────────────────────────────────────────────────────────────────────
MOIRE_SLOTS = {
    0: ("wave_breathe", [(0.0,5.5,76,70),(4.0,5.5,81,75),(8.0,5.5,86,80),(12.0,5.0,79,75)]),
    1: ("burst_pulse",  [(0.0,7.5,79,72),(8.0,7.5,83,78)]),
    2: ("engine_push",  [(0.0,2.5,76,70),(2.0,2.5,81,72),(4.0,2.5,79,74),(6.0,2.5,86,76),
                         (8.0,2.5,83,78),(10.0,2.5,88,78),(12.0,2.5,86,80),(14.0,2.5,91,84)]),
    3: ("hollow_pause", [(0.0,15.5,76,70)]),
    4: ("rebuild_lift", [(0.0,5.0,76,68),(3.0,4.5,81,74),(6.0,4.0,86,78),
                         (9.0,3.5,88,82),(11.5,2.5,91,86),(13.5,2.0,93,92)]),
    5: ("payoff_storm", [(0.0,3.0,76,78),(1.5,3.0,81,78),(3.0,3.0,86,80),(4.5,3.0,88,82),
                         (6.0,3.0,83,80),(7.5,3.0,91,84),(9.0,3.0,79,78),(10.5,3.0,93,86),
                         (12.0,3.0,86,82),(13.5,2.5,88,88)]),
}


MICA_PATCH = [
    ("Algorithm",   0.0),
    ("Osc-A Level", 1.0), ("Osc-A Wave", 0.0), ("A Coarse", 1.0), ("Osc-A Feedb", 0.0),
    ("Ae Attack",   0.0), ("Ae Decay", 0.35), ("Ae Sustain", 0.0), ("Ae Release", 0.20),
    ("Osc-B Level", 0.55), ("B Coarse", 3.0), ("B Fine", 500.0),
    ("Be Attack",   0.0), ("Be Decay", 0.18), ("Be Sustain", 0.0),
    ("Osc-B Feedb", 0.0),
    ("Osc-C Level", 0.0), ("Osc-D Level", 0.0),
    ("Filter On",   0.0),
    ("LFO On",      1.0), ("LFO Type", 0.0), ("LFO Sync", 6.0),
    ("LFO Amt",     0.18), ("LFO < Pe", 1.0),
    ("Volume",      0.42),
]

MOIRE_PATCH = [
    ("Algorithm",     0.0),
    ("Osc-A Level",   1.0), ("Osc-A Wave", 0.0), ("A Coarse", 1.0), ("Osc-A Feedb", 55.0),
    ("Ae Attack",     0.55), ("Ae Decay", 0.0), ("Ae Sustain", 1.0), ("Ae Release", 0.55),
    ("Osc-B Level",   0.92), ("B Coarse", 11.0), ("B Fine", 373.0),
    ("Be Attack",     0.40), ("Be Decay", 0.0), ("Be Sustain", 1.0), ("Be Release", 0.4),
    ("Osc-B Feedb",   30.0),
    ("Osc-C Level",   0.0), ("Osc-D Level", 0.0),
    ("Filter On",     1.0), ("Filter Freq", 0.82), ("Filter Res", 0.55),
    ("LFO On",        1.0), ("LFO Type", 0.0), ("LFO Sync", 3.0),
    ("LFO Amt",       0.55), ("LFO Retrigger", 1.0), ("LFO < Pe", 1.0),
    ("Volume",        0.34),
]


def main() -> None:
    ch = LiveChannel(); ch.start(); time.sleep(0.6)
    try:
        # ── RESTORE T5 MICA_THROB ──
        ch.set_track_name(T_MICA, "MICA_THROB").result(timeout=3)
        for n, v in MICA_PATCH:
            ch.set_device_param(T_MICA, 0, n, v).result(timeout=3)
        # rebuild clips
        for slot, (name, times) in MICA_SLOTS.items():
            ch.clear_clip(T_MICA, slot).result(timeout=3)
            ch.create_clip(T_MICA, slot, length_beats=CLIP_LEN).result(timeout=5)
            ch.set_clip_name(T_MICA, slot, name).result(timeout=3)
            notes = [{"pitch": PENTA[i%5], "start_time": t, "duration": 0.12,
                      "velocity": 96 if i%3==0 else 72} for i,t in enumerate(times)]
            ch.add_notes_to_clip(T_MICA, slot, notes).result(timeout=5)
        print(f"[restored] T5 MICA_THROB — Operator + {len(MICA_SLOTS)} clips (Trash untouched)")

        # ── CREATE T6 MOIRE_DRIFT ──
        s = ch.get_session_info().result(timeout=3)
        T_MOIRE = s["track_count"]
        ch.create_midi_track(T_MOIRE).result(timeout=5)
        ch.set_track_name(T_MOIRE, "MOIRE_DRIFT").result(timeout=3)
        ch.load_device(T_MOIRE, "query:Synths#Operator").result(timeout=20)
        for n, v in MOIRE_PATCH:
            ch.set_device_param(T_MOIRE, 0, n, v).result(timeout=3)
        for slot, (name, notes) in MOIRE_SLOTS.items():
            ch.create_clip(T_MOIRE, slot, length_beats=CLIP_LEN).result(timeout=5)
            ch.set_clip_name(T_MOIRE, slot, name).result(timeout=3)
            note_list = [{"pitch": p, "start_time": t, "duration": d, "velocity": v}
                         for t, d, p, v in notes]
            ch.add_notes_to_clip(T_MOIRE, slot, note_list).result(timeout=5)
        print(f"[new] T{T_MOIRE} MOIRE_DRIFT — Operator wash + {len(MOIRE_SLOTS)} clips")
    finally:
        ch.stop()


if __name__ == "__main__":
    main()
