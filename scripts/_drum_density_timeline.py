"""Drum-density timeline over the full Drums-to-MIDI extraction.

Buckets the clip into N-beat windows and shows hits per bucket, broken
out by KICK/SNARE/HAT, plus a sparkline of overall density. Useful for
spotting builds, drops, and denouements in the source track.
"""
from __future__ import annotations
import os, sys
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from thelmic.live_channel import LiveChannel

BUCKET_BEATS = 16.0   # one bucket = 16 beats ≈ 4 bars at Live's 190 BPM
T_DRUMS = 11          # T11 = Drums to MIDI track

PITCH_LABEL = {36: "K", 38: "S", 42: "H"}

SPARK = " .:-=+*#@"  # ASCII safe (Windows cp1252 chokes on block chars)


def sparkline(values: list[float], width: int = 80) -> str:
    if not values:
        return ""
    mx = max(values) or 1
    # Resample to width buckets
    if len(values) <= width:
        out_vals = values
    else:
        # Take max within each output bucket so peaks don't get averaged out
        step = len(values) / width
        out_vals = []
        for i in range(width):
            lo, hi = int(i * step), int((i + 1) * step)
            chunk = values[lo:hi] or [0]
            out_vals.append(max(chunk))
    chars = []
    for v in out_vals:
        idx = int((v / mx) * (len(SPARK) - 1))
        chars.append(SPARK[max(0, min(len(SPARK) - 1, idx))])
    return "".join(chars)


def analyze_slot(ch: LiveChannel, slot: int, label: str) -> None:
    n = ch.get_clip_notes(T_DRUMS, slot).result(timeout=30)
    notes = n.get("notes") or []
    props = ch._enqueue("get_clip_props",
                        {"track_index": T_DRUMS, "clip_index": slot}).result(timeout=5)
    length = float(props.get("length") or 0)
    print(f"\n{'='*70}\n{label}  (T{T_DRUMS} slot {slot})")
    print(f"{'='*70}")
    print(f"Clip length: {length:.1f} beats  ({length/4:.1f} bars at 4/4)")
    print(f"Total notes: {len(notes)}")

    # Bucket by start_time
    n_buckets = int(length / BUCKET_BEATS) + 1
    bk = [{"K": 0, "S": 0, "H": 0, "tot": 0} for _ in range(n_buckets)]
    for note in notes:
        t = note["start_time"]
        p = note["pitch"]
        idx = int(t / BUCKET_BEATS)
        if idx >= n_buckets:
            continue
        lbl = PITCH_LABEL.get(p)
        if lbl:
            bk[idx][lbl] += 1
            bk[idx]["tot"] += 1

    # Print sparkline overview
    print("\n=== overall density (each char = ~10 beats) ===")
    print(sparkline([b["tot"] for b in bk], width=100))

    # Print per-bucket detail with role-shape highlights
    print(f"\n=== per-bucket detail ({BUCKET_BEATS:.0f}-beat windows) ===")
    print(f"{'bar':>4s} {'time':>6s}  {'K':>4s} {'S':>4s} {'H':>4s} {'tot':>4s}  shape  visual")
    max_tot = max((b["tot"] for b in bk), default=1)
    for i, b in enumerate(bk):
        bar_start = i * BUCKET_BEATS / 4
        t_beat = i * BUCKET_BEATS
        barw = int(40 * b["tot"] / max_tot)
        visual = "#" * barw
        tags = []
        if b["tot"] == 0:
            tags.append("SILENCE")
        elif b["tot"] < max_tot * 0.20:
            tags.append("sparse")
        elif b["tot"] > max_tot * 0.85:
            tags.append("PEAK")
        if b["K"] == 0 and b["tot"] > 0:
            tags.append("no-kick")
        if b["H"] > b["K"] * 1.5 and b["H"] > 30:
            tags.append("hat-heavy")
        if b["S"] > b["K"] * 1.5 and b["S"] > 20:
            tags.append("snare-heavy")
        shape = " ".join(tags) or "-"
        print(f"{int(bar_start):4d} {t_beat:6.0f}  "
              f"{b['K']:4d} {b['S']:4d} {b['H']:4d} {b['tot']:4d}  "
              f"{shape:30s} {visual}")


def main():
    ch = LiveChannel(enabled=True); ch.start()
    try:
        analyze_slot(ch, 0, "ANGERFIST - LETHAL ASSASSINS")
        analyze_slot(ch, 1, "THE MOVER - FINAL SICKNESS")
    finally:
        ch.stop()


if __name__ == "__main__":
    main()
