"""Phase 12b — replace synth vocal layers with real samples.

T7 BARK_INTONE: strip Operator, load Drum Rack with 5 deep-voice stab samples
                on pads 36-43. Retarget all BARK clips to cycle pad notes.
T8 DRONE_LARYNX: strip Operator, load 'Throat Singing in a Cave' as Simpler
                (pitched). Existing MIDI clip notes play sample at those pitches.
"""
from __future__ import annotations
import os, time

os.environ.setdefault("LIVE_CHANNEL_ENABLED", "1")

from thelmic.live_channel import LiveChannel


T_BARK = 7
T_DRONE = 8
SAMPLE_DIR = "user_library/Samples/Freesound/cranky_hodgkin"

# Drum Rack pad assignments for stab variations
BARK_PADS = [
    (36, "yeah_deep_vocal.mp3"),       # main "yeah" — anchor stabs
    (38, "clear_deep_voice.mp3"),      # short stab
    (40, "hah_sharp.mp3"),             # sharp word
    (41, "blue_aww.mp3"),              # aww
    (43, "yeah_thats_right.mp3"),      # longer baritone
]
PAD_NOTES = [n for n, _ in BARK_PADS]


def retarget_bark_clip_pitches(ch, slot, hits):
    """Replace clip notes' pitches with cycling pad notes."""
    notes = []
    for i, (t, _old_pitch) in enumerate(hits):
        notes.append({
            "pitch": PAD_NOTES[i % len(PAD_NOTES)],
            "start_time": t,
            "duration": 0.18,
            "velocity": 102,
        })
    ch.add_notes_to_clip(T_BARK, slot, notes, replace=True).result(timeout=10)


# Existing BARK clip hits (timing + previous pitch — only the timing is reused)
BARK_HITS = {
    0: [(0.0,33), (4.0,33), (8.0,36), (12.0,33)],
    1: [(0.0,33),(1.5,33),(2.75,33),(4.0,36),(8.0,33),(9.5,33),(10.75,33),(12.0,36)],
    2: [(0.0,33),(1.5,33),(2.75,33),(4.0,33),(5.5,33),(8.0,33),(12.0,31)],
    3: [(0.0,33),(8.0,31)],
    4: [(0.0,33),(2.0,33),(4.0,33),(5.5,33),(7.0,33),
        (8.0,33),(9.0,33),(10.0,33),(11.0,33),
        (12.0,33),(12.75,33),(13.5,33),(14.0,33),(14.5,33),(15.0,36)],
    5: [(0.0,33),(0.667,33),(1.333,33),(2.0,33),
        (4.0,36),(4.667,33),(5.333,33),(6.0,33),
        (8.0,33),(8.667,33),(9.333,33),(10.0,33),
        (12.0,36),(12.667,33),(13.333,33),(14.0,33),(14.667,33),(15.333,36)],
    6: [(i*0.5, 33) for i in range(32)],
    7: [(o+c, 33) for o in (0.0,4.0,8.0,12.0) for c in (0.0,0.25,0.5,0.75)],
}


def main():
    ch = LiveChannel(); ch.start(); time.sleep(0.6)
    try:
        # ── T7 BARK_INTONE: strip Operator, load Drum Rack + 5 stabs ──
        # Delete the current Operator at device 0
        ch.delete_device(T_BARK, 0).result(timeout=5)
        ch.load_device(T_BARK, "query:Synths#Drum%20Rack").result(timeout=20)
        # Load each stab into its pad
        for note, fname in BARK_PADS:
            ch.load_sample_to_pad(T_BARK, 0, note, SAMPLE_DIR, fname).result(timeout=20)
            print(f"  BARK pad {note}: {fname}")
        # Retarget all BARK clip pitches to cycle through pad notes
        for slot, hits in BARK_HITS.items():
            retarget_bark_clip_pitches(ch, slot, hits)
            print(f"  BARK slot{slot}: {len(hits)} hits cycling {PAD_NOTES}")

        # ── T8 DRONE_LARYNX: strip Operator, load throat-singing sample ──
        ch.delete_device(T_DRONE, 0).result(timeout=5)
        # load_item_at_path drops audio into a Simpler by default
        ch.load_item_at_path(T_DRONE, SAMPLE_DIR,
                             item_name="throat_singing_cave.mp3").result(timeout=20)
        print(f"  DRONE_LARYNX: throat_singing_cave.mp3 → Simpler (pitched)")
        print(f"  (existing clip notes E3..A4 will play the sample at those pitches)")
    finally:
        ch.stop()


if __name__ == "__main__":
    main()
