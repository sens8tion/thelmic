"""Analyze the Drums/Melody/Harmony to MIDI extractions on T9-T11.

For each, find non-empty clip slots, dump count, pitch histogram, BPM
estimate from inter-onset intervals, and the first 16 events.
"""
from __future__ import annotations
import os, sys
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from thelmic.live_channel import LiveChannel

PITCH_NAMES = {
    29: "F1", 30: "F#1", 31: "G1", 32: "G#1", 33: "A1", 34: "Bb1", 35: "B1",
    36: "C2", 37: "C#2", 38: "D2", 39: "Eb2", 40: "E2", 41: "F2", 42: "F#2",
    43: "G2", 44: "Ab2", 45: "A2", 46: "Bb2", 47: "B2", 48: "C3", 49: "C#3",
    50: "D3", 51: "Eb3", 52: "E3", 53: "F3", 54: "F#3", 55: "G3", 56: "Ab3",
    57: "A3", 58: "Bb3", 59: "B3", 60: "C4", 61: "C#4", 62: "D4", 63: "Eb4",
    64: "E4", 65: "F4", 66: "F#4", 67: "G4", 68: "Ab4", 69: "A4", 70: "Bb4",
    71: "B4", 72: "C5", 73: "C#5", 74: "D5", 75: "Eb5", 76: "E5", 77: "F5",
    78: "F#5", 79: "G5", 80: "Ab5", 81: "A5", 82: "Bb5", 83: "B5", 84: "C6",
}

DRUM_NAMES = {36: "KICK", 38: "SNARE", 42: "HAT_C", 46: "HAT_O", 39: "CLAP"}


def analyze_clip(ch: LiveChannel, track: int, slot: int, label: str,
                 is_drums: bool = False) -> None:
    try:
        n = ch.get_clip_notes(track, slot).result(timeout=20)
    except Exception as e:
        print(f"  [{label}] no notes: {e}")
        return
    notes = n.get("notes") or []
    props = ch._enqueue("get_clip_props",
                        {"track_index": track, "clip_index": slot}).result(timeout=5)
    length = props.get("length") or 0
    print(f"  [{label}] {len(notes)} notes over {length:.1f} beats")
    pc = Counter(x["pitch"] for x in notes)
    nm_map = DRUM_NAMES if is_drums else PITCH_NAMES
    print(f"  top pitches:")
    for p, c in pc.most_common(10):
        nm = nm_map.get(p, f"p{p}")
        print(f"    {p:3d} ({nm:7s}): {c:4d}")
    # Velocity stats
    vels = [x["velocity"] for x in notes if x.get("velocity")]
    if vels:
        print(f"  vel: min={min(vels):.0f} max={max(vels):.0f} mean={sum(vels)/len(vels):.0f}")
    # For each top pitch — IOI histogram (gives rhythmic shape)
    if is_drums:
        for pit in (36, 38, 42):
            ts = sorted(set(round(x["start_time"], 3)
                            for x in notes if x["pitch"] == pit))
            if len(ts) < 4:
                continue
            iois = [round(ts[i+1] - ts[i], 3) for i in range(len(ts)-1)]
            bucket = Counter(iois)
            top = bucket.most_common(5)
            nm = DRUM_NAMES.get(pit, f"p{pit}")
            print(f"  {nm} IOI top-5: {top}")
    print()


def main():
    ch = LiveChannel(enabled=True)
    ch.start()
    try:
        # T9 Melody, T10 Harmony, T11 Drums  — slot 1 maps to The Mover audio
        for track, label, is_drums in [
            (9,  "MELODY",  False),
            (10, "HARMONY", False),
            (11, "DRUMS",   True),
        ]:
            print(f"\n=== T{track} {label} (slot 1, The Mover - Final Sickness) ===")
            analyze_clip(ch, track, 1, label, is_drums=is_drums)
    finally:
        ch.stop()


if __name__ == "__main__":
    main()
