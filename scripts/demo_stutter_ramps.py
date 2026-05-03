"""Three mathematically precise stutter ramps — listen and pick.

Each ramp retriggers BREAKBEAST's slot 4 clip at predetermined beat
intervals. launch_quantization=0 (no quant) so timing comes from the
wall clock alone, not Live's grid snap. Bpm-aware so all gaps are
exact musical durations.

Variants:
  1. DOUBLING (geometric ratio 0.5)
       4×(1b) → 4×(½b) → 4×(¼b) → 4×(⅛b) → 2×(1/16b)
       Classic 'stutter ramp' — each tier is twice the previous rate.

  2. TRIPLET ACCELERATE (geometric, triplet base)
       4×(⅔b) → 4×(⅓b) → 4×(⅙b) → 4×(1/12b) → 2×(1/24b)
       Same shape as #1 but on triplet subdivisions — feels like
       acceleration into a swung roll.

  3. ISOCHRONOUS 16TH (trance gate, no accel)
       16×(¼b) — pure mathematical pulse, no ramp. The 'narrowing'
       sensation here is purely the constant fast rate.
"""
from __future__ import annotations
import os, sys, time
os.environ.setdefault("LIVE_CHANNEL_ENABLED", "1")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from thelmic.mediated_session import open_session
from thelmic.agent_helpers import find_track


# Pick the track + slot whose clip we'll stutter
TARGET_TRACK = "ORGAN"          # organ stab — pitched stutter
TARGET_SLOT  = 1                # populated audio clip (organ_bubble_cutchie_Am)

# Three variants — each is a list of beat-intervals between successive hits
VARIANTS = {
    "doubling": (
        "doubling (geometric, ratio ½)",
        [1.0]*4 + [0.5]*4 + [0.25]*4 + [0.125]*4 + [0.0625]*2,
    ),
    "triplet": (
        "triplet accelerate (geometric, triplet base)",
        [2/3]*4 + [1/3]*4 + [1/6]*4 + [1/12]*4 + [1/24]*2,
    ),
    "isochronous": (
        "isochronous 16th (trance gate, no accel)",
        [0.25]*16,
    ),
}


def stutter_ramp(ch, track, slot, intervals_beats, beat_seconds, label):
    """Fire (track, slot) at the specified intervals using wall-clock
    timing. Returns total elapsed seconds."""
    ch.set_launch_quantization(0).result(timeout=3)
    print(f"  ▶ {label}: {len(intervals_beats)+1} hits, "
          f"{sum(intervals_beats):.3f}b total")
    t0 = time.monotonic()
    # First hit at t=0, then each subsequent hit after intervals[i]
    elapsed_beats = 0.0
    ch.fire_clip(track, slot).result(timeout=2)
    for gap in intervals_beats:
        elapsed_beats += gap
        target_t = t0 + elapsed_beats * beat_seconds
        delay = target_t - time.monotonic()
        if delay > 0:
            time.sleep(delay)
        try: ch.fire_clip(track, slot).result(timeout=2)
        except Exception as e:
            print(f"    fire_clip fail: {e}")
    return time.monotonic() - t0


def main():
    with open_session(name="stutter-ramp-demo",
                      expected_tracks=[TARGET_TRACK]) as sess:
        sess.chat("agent", "demoing 3 mathematically precise stutter ramps")
        info = sess.raw_ch.get_session_info().result(timeout=5)
        bpm = info.get("tempo", 165.0)
        beat_seconds = 60.0 / bpm
        track = find_track(sess.raw_ch, TARGET_TRACK)
        if track is None:
            print(f"can't find {TARGET_TRACK}"); return

        for key, (label, intervals) in VARIANTS.items():
            sess.note(f"variant: {key} — {label}")
            elapsed = stutter_ramp(sess.raw_ch, track, TARGET_SLOT,
                                     intervals, beat_seconds, label)
            print(f"    elapsed: {elapsed:.2f}s")
            # Let the final hit ring out, then silence between variants
            time.sleep(1.5)
            sess.raw_ch.stop_all_clips().result(timeout=3)
            time.sleep(1.0)

        # Restore launch quantization to 1-bar
        sess.raw_ch.set_launch_quantization(1).result(timeout=3)
        print("\ndone — pick which one feels right and we'll wire it in.")


if __name__ == "__main__":
    main()
