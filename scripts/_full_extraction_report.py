"""Full extraction report: Melody / Harmony / Drums × Angerfist / The Mover.

For each (track, slot), dump:
  - Note count + clip length
  - Pitch histogram (top 10)
  - Pitch-class histogram (scale degrees vs A as root)
  - Density timeline (16-beat buckets) with shape tags
"""
from __future__ import annotations
import os, sys
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from thelmic.live_channel import LiveChannel

T_MELODY  = 9
T_HARMONY = 10
T_DRUMS   = 11

CONVERSIONS = [
    (T_MELODY,  "MELODY"),
    (T_HARMONY, "HARMONY"),
    (T_DRUMS,   "DRUMS"),
]
AUDIO_SLOTS = [
    (0, "ANGERFIST - LETHAL ASSASSINS"),
    (1, "THE MOVER - FINAL SICKNESS"),
]

BUCKET = 16.0
SPARK = " .:-=+*#@"
DRUM_NAMES = {36: "K", 38: "S", 42: "H"}
PC_NAMES = {0: "A", 1: "Bb", 2: "B", 3: "C", 4: "C#", 5: "D",
            6: "Eb", 7: "E", 8: "F", 9: "F#", 10: "G", 11: "G#"}


def sparkline(values: list[float], width: int = 80) -> str:
    if not values:
        return ""
    mx = max(values) or 1
    if len(values) <= width:
        out_vals = values
    else:
        step = len(values) / width
        out_vals = [max(values[int(i*step):int((i+1)*step)] or [0])
                    for i in range(width)]
    return "".join(SPARK[max(0, min(len(SPARK)-1, int(v/mx*(len(SPARK)-1))))]
                   for v in out_vals)


def analyze(ch: LiveChannel, track: int, slot: int, label: str,
            audio_label: str, is_drums: bool) -> None:
    try:
        n = ch.get_clip_notes(track, slot).result(timeout=30)
    except Exception as e:
        print(f"  [no clip: {e}]")
        return
    notes = n.get("notes") or []
    if not notes:
        print(f"  [empty]")
        return
    props = ch._enqueue("get_clip_props",
                        {"track_index": track, "clip_index": slot}).result(timeout=5)
    length = float(props.get("length") or 0)
    print(f"\n--- {label} on {audio_label} ---")
    print(f"  {len(notes)} notes, {length:.0f} beats ({length/4:.0f} bars)")

    # Pitch hist
    pc = Counter(x["pitch"] for x in notes)
    print(f"  top pitches: ", end="")
    parts = []
    for p, c in pc.most_common(8):
        nm = DRUM_NAMES.get(p, f"p{p}") if is_drums else f"{p}"
        parts.append(f"{nm}={c}")
    print(", ".join(parts))

    # Pitch-class histogram relative to A=0 (only meaningful for non-drums)
    if not is_drums:
        pc_count = Counter((p - 33) % 12 for p in (x["pitch"] for x in notes))
        print(f"  pitch-class (root=A):")
        total = sum(pc_count.values())
        for cls in range(12):
            nm = PC_NAMES[cls]
            cnt = pc_count.get(cls, 0)
            pct = 100 * cnt / total if total else 0
            barw = int(pct / 2)
            print(f"    {nm:>2s}: {cnt:5d} ({pct:5.1f}%) {'#' * barw}")

    # Density timeline
    n_bk = int(length / BUCKET) + 1
    bk = [0] * n_bk
    for note in notes:
        idx = int(note["start_time"] / BUCKET)
        if 0 <= idx < n_bk:
            bk[idx] += 1
    print(f"  density timeline ({BUCKET:.0f}-beat buckets):")
    print(f"    {sparkline(bk, width=80)}")


def main():
    ch = LiveChannel(enabled=True); ch.start()
    try:
        for slot, audio in AUDIO_SLOTS:
            print(f"\n{'='*72}")
            print(f"=== {audio}")
            print(f"{'='*72}")
            for t, label in CONVERSIONS:
                analyze(ch, t, slot, label, audio, is_drums=(t == T_DRUMS))
    finally:
        ch.stop()


if __name__ == "__main__":
    main()
