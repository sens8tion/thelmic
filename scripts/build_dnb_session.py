"""Hand-built DnB session — drums / bass / pad / lead across 4 scenes.

Composes notes directly (no thelmic generators). Drops into Live via the
LOM channel.

Layout:
  T0  3RDEYEZ drum kit
  T1  Operator (reese bass)
  T4  Operator (pad)
  T5  Operator (lead)

Scenes (row index in Live's session view):
  0  INTRO       pad only
  1  DROP        drums + bass + pad
  2  BREAKDOWN   pad + sparse lead
  3  DROP+       drums + bass + pad + lead

Key: A minor.  Tempo: 174.  Length per clip: 16 bars (64 beats).
Chord progression (4 bars each): Am — F — C — G.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from thelmic.live_channel import LiveChannel

# --- pitch helpers -----------------------------------------------------
# Standard MIDI: C4 = 60.  Live displays one octave lower than this.
A2 = 45  # bass root for Am
F2 = 41
C3 = 48
G2 = 43
# triads
A3, C4, E4 = 57, 60, 64       # Am triad voicing
F3, A3_, C4_ = 53, 57, 60     # F   ("3rdless" stacks; mirror of Am)
C4__, E4__, G4 = 60, 64, 67   # C
G3, B3, D4 = 55, 59, 62       # G

# drum kit (GM)
KICK = 36
SNARE = 38
HAT_C = 42
HAT_O = 46
RIDE = 51

# transposition offsets per chord (relative to Am bass at A2=45)
CHORD_OFFSETS = [0, -4, 3, -2]   # Am, F, C, G in semitones from Am


# ---------------------------------------------------------------------
# Bass — 2-bar A-minor reese pattern, transposed per chord, 8 copies = 16 bars
# ---------------------------------------------------------------------

# (offset_in_pattern_beats, midi_pitch_offset_from_root, duration, velocity)
# pitch is encoded as semitones above the chord root (A2 for Am)
_BASS_2BAR = [
    (0.00, 0,   0.75, 105),  # root anchor
    (0.75, 0,   0.25,  80),
    (1.00, 7,   0.50,  95),  # 5th
    (1.50, 0,   0.50,  90),
    (2.00, 3,   0.50, 100),  # b3
    (2.50, 0,   0.50,  90),
    (3.00, -2,  0.25,  85),  # b7 below
    (3.25, 0,   0.75, 100),
    (4.00, 0,   0.50, 105),
    (4.50, 0,   0.25,  80),
    (4.75, 5,   0.25,  90),  # 4th passing
    (5.00, 7,   0.50, 100),
    (5.50, 0,   0.50,  90),
    (6.00, 3,   0.50, 100),
    (6.50, -2,  0.50,  95),
    (7.00, 0,   1.00, 105),
]


def build_bass_16bar():
    notes = []
    for chord_idx, offset_semi in enumerate(CHORD_OFFSETS):
        chord_start_beat = chord_idx * 16  # each chord lasts 4 bars = 16 beats
        # 2 copies of the 2-bar pattern fit in the 4-bar chord region
        for copy_idx in range(2):
            copy_start = chord_start_beat + copy_idx * 8
            for off_beat, semi_off, dur, vel in _BASS_2BAR:
                notes.append({
                    "pitch": A2 + offset_semi + semi_off,
                    "start_time": copy_start + off_beat,
                    "duration": dur,
                    "velocity": vel,
                })
    return notes


# ---------------------------------------------------------------------
# Drums — 4-bar pattern × 4 = 16 bars
# ---------------------------------------------------------------------

def build_drums_4bar():
    """One 4-bar (16-beat) DnB pattern."""
    notes = []
    # Kicks
    for t, vel in [
        (0.00, 110), (2.50, 100),
        (4.00, 110), (6.75,  95),
        (8.00, 110), (10.50, 100),
        (12.00, 110), (14.50, 95),
    ]:
        notes.append({"pitch": KICK, "start_time": t, "duration": 0.5, "velocity": vel})
    # Snares (every backbeat)
    for t in [1, 3, 5, 7, 9, 11, 13, 15]:
        notes.append({"pitch": SNARE, "start_time": float(t), "duration": 0.5, "velocity": 100})
    # Closed hats — 16th note grid, with velocity articulation
    for i in range(64):  # 16 beats × 4 sixteenths
        t = i * 0.25
        # accent pattern: 1 strong, 2 medium, 3 weak, 4 medium, repeat
        slot = i % 4
        vel = {0: 95, 1: 70, 2: 80, 3: 70}[slot]
        notes.append({"pitch": HAT_C, "start_time": t, "duration": 0.2, "velocity": vel})
    # Open hat accents on the 'and' of beats 1, 3 of each bar
    for t in [0.5, 2.5, 4.5, 6.5, 8.5, 10.5, 12.5, 14.5]:
        notes.append({"pitch": HAT_O, "start_time": t, "duration": 0.3, "velocity": 90})
    return notes


def build_drums_16bar():
    notes = []
    pattern = build_drums_4bar()
    for rep in range(4):
        offset = rep * 16.0
        for n in pattern:
            notes.append({**n, "start_time": n["start_time"] + offset})
    return notes


def build_drums_16bar_drop_plus():
    """DROP+ variant: same base pattern + ride cymbal layer + extra snare ghosts."""
    notes = build_drums_16bar()
    # Ride cymbal — quarter notes through bars 9-16 (back half)
    for beat in range(32, 64):
        if beat % 1 == 0:
            notes.append({"pitch": RIDE, "start_time": float(beat), "duration": 0.4, "velocity": 75})
    # Snare ghosts on 16th-note offsets
    for bar in range(16):
        # add a ghost at 1.25 beats of each bar's middle
        notes.append({
            "pitch": SNARE,
            "start_time": bar * 4.0 + 2.75,
            "duration": 0.15,
            "velocity": 45,
        })
    return notes


# ---------------------------------------------------------------------
# Pad — long-held triads, one per chord (4 chords × 3 notes = 12 notes)
# ---------------------------------------------------------------------

PAD_CHORDS = [
    [57, 60, 64],   # Am: A3 C4 E4
    [53, 57, 60],   # F:  F3 A3 C4
    [60, 64, 67],   # C:  C4 E4 G4
    [55, 59, 62],   # G:  G3 B3 D4
]


def build_pad_16bar():
    notes = []
    for chord_idx, triad in enumerate(PAD_CHORDS):
        start = chord_idx * 16.0
        for pitch in triad:
            notes.append({
                "pitch": pitch,
                "start_time": start,
                # Just shy of 4 bars so envelopes overlap rather than collide
                "duration": 15.5,
                "velocity": 78,
            })
    return notes


# ---------------------------------------------------------------------
# Lead — 4-bar pentatonic phrase × 4
# ---------------------------------------------------------------------

# A minor pentatonic upper-octave: A4=69, C5=72, D5=74, E5=76, G5=79, A5=81
_LEAD_4BAR = [
    (0.00, 76, 0.50,  95),  # E5
    (0.75, 67, 0.25,  85),  # G4 ghost
    (2.00, 69, 1.50, 100),  # A4 syncopated long
    (5.50, 72, 0.50,  95),  # C5
    (6.00, 74, 0.50, 100),  # D5
    (7.00, 76, 1.00, 105),  # E5
    (10.00, 79, 0.50, 100), # G5
    (10.50, 81, 0.25, 105), # A5 peak
    (11.00, 79, 0.50,  95), # G5
    (13.00, 76, 2.00, 100), # E5 sustain
]


def build_lead_16bar(sparse=False):
    notes = []
    for rep in range(4):
        offset = rep * 16.0
        # transpose each rep by chord offset to stay diatonic
        chord_off = CHORD_OFFSETS[rep]  # 0, -4, +3, -2
        for t, p, dur, vel in _LEAD_4BAR:
            if sparse:
                # Drop every other note for breakdown
                if (t * 100) % 200 < 100:  # crude even/odd test
                    continue
            notes.append({
                "pitch": p + chord_off,
                "start_time": offset + t,
                "duration": dur,
                "velocity": vel,
            })
    return notes


# ---------------------------------------------------------------------
# Drive
# ---------------------------------------------------------------------

def main():
    ch = LiveChannel(lower_priority=False)
    ch.start()
    try:
        # Confirm tempo
        sess = ch.get_session_info().result(timeout=5)
        print(f"tempo: {sess['tempo']}  tracks: {sess['track_count']}")

        # Track indices
        T_DRUMS, T_BASS, T_PAD, T_LEAD = 0, 1, 4, 5

        # Build clip note arrays
        drums_main = build_drums_16bar()
        drums_drop_plus = build_drums_16bar_drop_plus()
        bass = build_bass_16bar()
        pad = build_pad_16bar()
        lead_full = build_lead_16bar(sparse=False)
        lead_sparse = build_lead_16bar(sparse=True)

        print()
        print(f"drums (drop):     {len(drums_main)} notes")
        print(f"drums (drop+):    {len(drums_drop_plus)} notes")
        print(f"bass:             {len(bass)} notes")
        print(f"pad:              {len(pad)} notes")
        print(f"lead full:        {len(lead_full)} notes")
        print(f"lead sparse:      {len(lead_sparse)} notes")
        print()

        def write(track, slot, name, notes, length=64.0):
            ch.create_clip(track, slot, length).result(timeout=10)
            ch.set_clip_name(track, slot, name).result(timeout=5)
            ch.add_notes_to_clip(track, slot, notes).result(timeout=10)
            print(f"  T{track} S{slot}  '{name}'  ({len(notes)} notes)")

        # Rename tracks for vibe
        ch.set_track_name(T_DRUMS, "ULTRAKICK").result(timeout=5)
        ch.set_track_name(T_BASS, "ESOPHAGUS").result(timeout=5)
        ch.set_track_name(T_PAD, "FOG MACHINE").result(timeout=5)
        ch.set_track_name(T_LEAD, "ICEPICK").result(timeout=5)

        # SCENE 0: INTRO — pad only
        print("scene 0 (INTRO):")
        write(T_PAD, 0, "fog_drift", pad)

        # SCENE 1: DROP — drums + bass + pad
        print("scene 1 (DROP):")
        write(T_DRUMS, 1, "skull_violence", drums_main)
        write(T_BASS, 1, "esophagus_hug", bass)
        write(T_PAD, 1, "cult_drone", pad)

        # SCENE 2: BREAKDOWN — pad + sparse lead
        print("scene 2 (BREAKDOWN):")
        write(T_PAD, 2, "tear_jerker", pad)
        write(T_LEAD, 2, "ghost_yodel", lead_sparse)

        # SCENE 3: DROP+ — drums variant + bass + pad + full lead
        print("scene 3 (DROP+):")
        write(T_DRUMS, 3, "skull_violence_XTREME", drums_drop_plus)
        write(T_BASS, 3, "esophagus_hug_again", bass)
        write(T_PAD, 3, "cult_drone_THICK", pad)
        write(T_LEAD, 3, "ghost_yodel_FULL", lead_full)

        # Set track volumes for a musical mix
        print()
        print("mixing...")
        ch.set_track_volume(T_DRUMS, 0.85).result(timeout=5)
        ch.set_track_volume(T_BASS, 0.80).result(timeout=5)
        ch.set_track_volume(T_PAD, 0.65).result(timeout=5)   # pad sits behind
        ch.set_track_volume(T_LEAD, 0.72).result(timeout=5)

        # Fire scene 1 (the drop)
        print()
        print("firing scene 1 (DROP)...")
        ch.fire_clip(T_DRUMS, 1).result(timeout=5)
        ch.fire_clip(T_BASS, 1).result(timeout=5)
        ch.fire_clip(T_PAD, 1).result(timeout=5)

        print()
        print("STATUS:", ch.status().as_dict())
    finally:
        ch.stop()


if __name__ == "__main__":
    main()
