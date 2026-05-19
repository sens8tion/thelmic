"""Phase 12 — two vocal layers via formant synthesis on Operator.

T7 BARK_INTONE — deep-voice rap stabs.
  4 parallel sine carriers at fundamental + ~F1/F2/F3 formant ratios,
  percussive envelope, low register.

T8 DRONE_LARYNX — folk drone with changing character.
  Same formant stack but sustained envelope, mid register, LFO morphing
  Op C/D levels for vowel-shift over time.
"""
from __future__ import annotations
import os, time

os.environ.setdefault("LIVE_CHANNEL_ENABLED", "1")

from thelmic.live_channel import LiveChannel


CLIP_LEN = 16.0

# ── BARK_INTONE clip patterns (low rap stabs) ─────────────────────────────
# Pitches: A1 anchor with occasional E1/D2 — deep voice range
BARK_SLOTS = {
    0: ("intro", [
        (0.0,  33), (4.0, 33), (8.0, 36), (12.0, 33),    # 4 anchor stabs
    ]),
    1: ("motif", [
        # Follow LONG-stab-stab-HELD architectural rhythm
        (0.0, 33), (1.5, 33), (2.75, 33), (4.0, 36),
        (8.0, 33), (9.5, 33), (10.75, 33), (12.0, 36),
    ]),
    2: ("fallthrough", [
        (0.0, 33), (1.5, 33), (2.75, 33),                # bar1: 3 stabs
        (4.0, 33), (5.5, 33),                            # bar2: 2
        (8.0, 33),                                       # bar3: 1
        (12.0, 31),                                      # bar4: 1 lower
    ]),
    3: ("hollow_pause", [
        (0.0, 33), (8.0, 31),                            # 2 sparse stabs
    ]),
    4: ("rebuild_lift", [
        (0.0, 33), (2.0, 33),                            # bar1: 2
        (4.0, 33), (5.5, 33), (7.0, 33),                 # bar2: 3
        (8.0, 33), (9.0, 33), (10.0, 33), (11.0, 33),    # bar3: 4
        (12.0, 33), (12.75, 33), (13.5, 33),
        (14.0, 33), (14.5, 33), (15.0, 36),              # bar4: 5
    ]),
    5: ("payoff_storm", [
        # Rap-style triplet stabs
        (0.0, 33), (0.667, 33), (1.333, 33), (2.0, 33),
        (4.0, 36), (4.667, 33), (5.333, 33), (6.0, 33),
        (8.0, 33), (8.667, 33), (9.333, 33), (10.0, 33),
        (12.0, 36), (12.667, 33), (13.333, 33), (14.0, 33), (14.667, 33), (15.333, 36),
    ]),
    6: ("engine_push", [
        (i * 0.5, 33 if i % 4 != 3 else 36) for i in range(32)
    ]),
    7: ("anchor_fire", [
        # 4-hit 16th cluster on each downbeat
        (o + c, 33 if c > 0 else 36)
        for o in (0.0, 4.0, 8.0, 12.0)
        for c in (0.0, 0.25, 0.5, 0.75)
    ]),
}


# ── DRONE_LARYNX clip patterns (folk long notes, mid register) ────────────
# (start, duration, pitch, velocity)
DRONE_SLOTS = {
    0: ("intro", [
        (0.0,  7.0, 57, 78),                             # A3
        (8.0,  7.0, 59, 82),                             # B3
    ]),
    1: ("motif", [
        (0.0,  3.5, 57, 80),
        (4.0,  3.5, 59, 78),
        (8.0,  3.5, 62, 84),                             # D4
        (12.0, 3.5, 64, 82),                             # E4
    ]),
    2: ("fallthrough", [
        (0.0,  4.0, 64, 80),                             # E4 (descending)
        (4.0,  4.0, 62, 76),                             # D4
        (8.0,  4.0, 59, 74),                             # B3
        (12.0, 3.9, 57, 72),                             # A3
    ]),
    3: ("hollow_pause", [
        (0.0, 15.5, 57, 76),                             # Single 15.5-beat folk drone on A3
    ]),
    4: ("rebuild_lift", [
        (0.0,  4.0, 57, 70),                             # A3
        (4.0,  4.0, 59, 76),                             # B3
        (8.0,  4.0, 62, 82),                             # D4
        (11.0, 2.5, 64, 86),                             # E4
        (13.5, 2.0, 67, 92),                             # G4
    ]),
    5: ("payoff_storm", [
        (0.0, 15.5, 64, 88),                             # E4 held throughout drop
    ]),
    6: ("engine_push", [
        (0.0, 8.0, 64, 86),                              # E4
        (8.0, 7.9, 67, 90),                              # G4
    ]),
    7: ("anchor_fire", [
        (0.0,  3.5, 64, 86),
        (4.0,  3.5, 67, 84),
        (8.0,  3.5, 64, 88),
        (12.0, 3.8, 69, 92),                             # A4 lift on final
    ]),
}


# ── Formant patch (shared structure) ──────────────────────────────────────
# Algorithm 10 — all 4 ops as parallel carriers (additive formant stack)
# Ratios approx: 1.0 (fundamental), 5.0 (F1), 10.0 (F2), 22.0 (F3)
FORMANT_BASE = [
    ("Algorithm", 10.0),
    # Op A — fundamental
    ("Osc-A On", 1.0), ("Osc-A Level", 1.0), ("Osc-A Wave", 0.0),
    ("A Coarse", 1.0), ("Osc-A Feedb", 0.0),
    # Op B — F1
    ("Osc-B On", 1.0), ("Osc-B Level", 0.55), ("Osc-B Wave", 0.0),
    ("B Coarse", 5.0), ("B Fine", 0.0), ("Osc-B Feedb", 0.0),
    # Op C — F2
    ("Osc-C On", 1.0), ("Osc-C Level", 0.40), ("Osc-C Wave", 0.0),
    ("C Coarse", 10.0), ("C Fine", 0.0),
    # Op D — F3 (high)
    ("Osc-D On", 1.0), ("Osc-D Level", 0.20), ("Osc-D Wave", 0.0),
    ("D Coarse", 22.0), ("D Fine", 0.0),
]

BARK_ENV = [   # percussive — short attack, no sustain
    ("Ae Attack", 0.0),  ("Ae Decay", 0.18), ("Ae Sustain", 0.0), ("Ae Release", 0.08),
    ("Be Attack", 0.0),  ("Be Decay", 0.15), ("Be Sustain", 0.0), ("Be Release", 0.08),
    ("Ce Attack", 0.0),  ("Ce Decay", 0.12), ("Ce Sustain", 0.0), ("Ce Release", 0.08),
    ("De Attack", 0.0),  ("De Decay", 0.10), ("De Sustain", 0.0), ("De Release", 0.06),
    ("Volume", 0.42),
    ("Filter On", 1.0), ("Filter Freq", 0.55), ("Filter Res", 0.30),
]

DRONE_ENV = [  # sustained with vowel morph via LFO routing to Op C/D level
    ("Ae Attack", 0.30), ("Ae Decay", 0.0), ("Ae Sustain", 1.0), ("Ae Release", 0.50),
    ("Be Attack", 0.30), ("Be Decay", 0.0), ("Be Sustain", 1.0), ("Be Release", 0.50),
    ("Ce Attack", 0.40), ("Ce Decay", 0.0), ("Ce Sustain", 1.0), ("Ce Release", 0.50),
    ("De Attack", 0.50), ("De Decay", 0.0), ("De Sustain", 1.0), ("De Release", 0.40),
    ("Volume", 0.34),
    # LFO modulates pitch — slow vowel-like wobble
    ("LFO On", 1.0), ("LFO Type", 0.0), ("LFO Sync", 4.0),
    ("LFO Amt", 0.15), ("LFO < Pe", 1.0),
    ("Filter On", 1.0), ("Filter Freq", 0.60), ("Filter Res", 0.40),
]


def build_track(ch, t_idx, name, patch_env, slots, send_reverb=0.4):
    ch.set_track_name(t_idx, name).result(timeout=3)
    ch.load_device(t_idx, "query:Synths#Operator").result(timeout=20)
    for n, v in FORMANT_BASE + patch_env:
        ch.set_device_param(t_idx, 0, n, v).result(timeout=3)
    ch.set_send(t_idx, 0, send_reverb).result(timeout=3)
    for slot, (clipname, notes) in slots.items():
        try:
            ch.clear_clip(t_idx, slot).result(timeout=3)
        except Exception:
            pass
        ch.create_clip(t_idx, slot, length_beats=CLIP_LEN).result(timeout=5)
        ch.set_clip_name(t_idx, slot, clipname).result(timeout=3)
        if isinstance(notes[0], tuple) and len(notes[0]) == 2:
            # (time, pitch) — BARK stabs
            note_list = [{"pitch": p, "start_time": t, "duration": 0.12, "velocity": 102}
                         for t, p in notes]
        else:
            # (time, dur, pitch, vel) — DRONE
            note_list = [{"pitch": p, "start_time": t, "duration": d, "velocity": v}
                         for t, d, p, v in notes]
        ch.add_notes_to_clip(t_idx, slot, note_list).result(timeout=5)


def main():
    ch = LiveChannel(); ch.start(); time.sleep(0.6)
    try:
        s = ch.get_session_info().result(timeout=3)
        n = s["track_count"]
        t_bark = n
        t_drone = n + 1
        ch.create_midi_track(t_bark).result(timeout=5)
        ch.create_midi_track(t_drone).result(timeout=5)

        build_track(ch, t_bark, "BARK_INTONE", BARK_ENV, BARK_SLOTS, send_reverb=0.25)
        build_track(ch, t_drone, "DRONE_LARYNX", DRONE_ENV, DRONE_SLOTS, send_reverb=0.65)

        print(f"[done] T{t_bark} BARK_INTONE | T{t_drone} DRONE_LARYNX")
        for slot, (name, notes) in BARK_SLOTS.items():
            print(f"  slot{slot} {name}: bark x{len(notes)} | drone x{len(DRONE_SLOTS[slot][1])}")
    finally:
        ch.stop()


if __name__ == "__main__":
    main()
