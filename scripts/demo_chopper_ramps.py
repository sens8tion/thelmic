"""Chopper ramps on ORGAN — programmatically step the Auto-Pan-as-Chopper's
Sync Rate up the subdivision enum so the audio-rate gate tightens.

Sync Rate is a 0..21 enum (slow → fast). Common Live Auto Pan ordering:
  0=8B  1=4B  2=2B  3=1B  4=½  5=½T  6=¼  7=¼T  8=⅛  9=⅛T
  10=¹⁄₁₆ 11=¹⁄₁₆T 12=¹⁄₃₂ 13=¹⁄₃₂T 14=¹⁄₆₄ 15=¹⁄₆₄T 16=¹⁄₁₂₈ ...

Three variants:
  1. STEADY ¹⁄₁₆ for 2 bars                — fixed fast gate
  2. RAMP ¼ → ⅛ → ¹⁄₁₆ → ¹⁄₃₂ over 4 bars  — classic tightening
  3. SHRED ¼ → ¹⁄₁₂₈ over 6 bars            — full Rotterdam gate ramp
"""
from __future__ import annotations
import os, sys, time
os.environ.setdefault("LIVE_CHANNEL_ENABLED", "1")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from thelmic.mediated_session import open_session
from thelmic.agent_helpers import find_track

TARGET_TRACK = "ORGAN"
TARGET_SLOT  = 1
CHOPPER_DEV_NAME = "Chopper"  # the renamed AutoPan
SYNC_RATE_PARAM_NAME = "Sync Rate"

# Sync Rate enum positions — Live 12 Auto Pan ordering (verified by counting
# dotted+triplet between each subdivision):
#   0=8B, 1=4B, 2=2B, 3=1B, 4=½, 5=½ ., 6=½t,
#   7=¼, 8=¼ ., 9=¼t, 10=⅛, 11=⅛ ., 12=⅛t,
#   13=¹⁄₁₆, 14=¹⁄₁₆ ., 15=¹⁄₁₆t,
#   16=¹⁄₃₂, 17=¹⁄₃₂ ., 18=¹⁄₃₂t,
#   19=¹⁄₆₄, 20=¹⁄₆₄ ., 21=¹⁄₆₄t (max — no 1/128 in Auto Pan)
RATE_QUARTER     =  7
RATE_EIGHTH      = 10
RATE_SIXTEENTH   = 13
RATE_THIRTYSEC   = 16
RATE_SIXTYFOURTH = 19
RATE_128         = 21   # Auto Pan tops out at 1/64t — no 1/128


def find_chopper(ch, track):
    info = ch.get_track_info(track).result(timeout=5)
    for di, d in enumerate(info.get("devices", [])):
        if d.get("name") == CHOPPER_DEV_NAME or "chop" in (d.get("name") or "").lower():
            return di
    return None


def run_ramp(ch, track, dev, sync_param_idx, schedule, beat_seconds, label):
    """schedule: list of (sync_rate_value, hold_bars) — set the rate, hold."""
    print(f"\n▶ {label}")
    ch.set_launch_quantization(0).result(timeout=2)
    # First step: set initial rate THEN fire clip
    first_rate, _ = schedule[0]
    ch.set_device_param(track, dev, sync_param_idx, float(first_rate)).result(timeout=2)
    ch.fire_clip(track, TARGET_SLOT).result(timeout=3)
    t0 = time.monotonic()
    elapsed_beats = 0.0
    for rate, hold in schedule:
        # advance to the start of this step (wall clock)
        target_t = t0 + elapsed_beats * beat_seconds
        delay = target_t - time.monotonic()
        if delay > 0: time.sleep(delay)
        ch.set_device_param(track, dev, sync_param_idx, float(rate)).result(timeout=2)
        print(f"    bar {elapsed_beats/4:>4.1f}  Sync Rate = {rate}")
        elapsed_beats += hold * 4
    # Hold the final state through its bars
    target_t = t0 + elapsed_beats * beat_seconds
    delay = target_t - time.monotonic()
    if delay > 0: time.sleep(delay)
    # Disable Chopper so the tail doesn't keep gating
    ch.set_device_param(track, dev, 0, 0.0).result(timeout=2)   # Device On = 0
    time.sleep(0.5)
    ch.stop_all_clips().result(timeout=3)
    time.sleep(0.6)
    # Re-enable for next variant
    ch.set_device_param(track, dev, 0, 1.0).result(timeout=2)


def main():
    with open_session(name="chopper-ramp-demo",
                      expected_tracks=[TARGET_TRACK]) as sess:
        bpm = sess.raw_ch.get_session_info().result(timeout=5)["tempo"]
        beat_seconds = 60.0 / bpm
        track = find_track(sess.raw_ch, TARGET_TRACK)
        dev = find_chopper(sess.raw_ch, track)
        if dev is None:
            print(f"can't find Chopper on {TARGET_TRACK}"); return

        di = sess.raw_ch.get_device_info(track, dev).result(timeout=3)
        sync_idx = next(p["index"] for p in di["parameters"] if p["name"] == SYNC_RATE_PARAM_NAME)
        print(f"Chopper device idx={dev}, Sync Rate param idx={sync_idx}")

        # Variant 1: STEADY 1/16 for 2 bars
        run_ramp(sess.raw_ch, track, dev, sync_idx,
                 [(RATE_SIXTEENTH, 2)],
                 beat_seconds, "STEADY 1/16 for 2 bars")

        # Variant 2: RAMP 1/4 → 1/8 → 1/16 → 1/32 (1 bar each)
        run_ramp(sess.raw_ch, track, dev, sync_idx,
                 [(RATE_QUARTER, 1), (RATE_EIGHTH, 1),
                  (RATE_SIXTEENTH, 1), (RATE_THIRTYSEC, 1)],
                 beat_seconds, "RAMP 1/4→1/8→1/16→1/32 over 4 bars")

        # Variant 3: SHRED 1/4 → 1/128 (1 bar each)
        run_ramp(sess.raw_ch, track, dev, sync_idx,
                 [(RATE_QUARTER, 1), (RATE_EIGHTH, 1),
                  (RATE_SIXTEENTH, 1), (RATE_THIRTYSEC, 1),
                  (RATE_SIXTYFOURTH, 1), (RATE_128, 1)],
                 beat_seconds, "SHRED 1/4→1/128 over 6 bars")

        sess.raw_ch.set_launch_quantization(1).result(timeout=2)
        print("\ndone — pick the variant.")


if __name__ == "__main__":
    main()
