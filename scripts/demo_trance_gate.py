"""Trance-gate demo: sample plays continuously while a square-wave LFO
chops the volume at increasingly tight rates.

Mechanism: Utility device added to ORGAN; clip envelope on Utility's
Gain writes a square wave with tightening period. Live evaluates the
envelope at audio rate so 1/32 / 1/64 transitions are sample-precise.

Three variants:
  1. STEADY  — constant 1/16 gate for 2 bars
  2. RAMP    — 1/4 → 1/8 → 1/16 → 1/32 over 4 bars
  3. SHRED   — 1/4 → 1/8 → 1/16 → 1/32 → 1/64 → 1/128 over 6 bars
"""
from __future__ import annotations
import os, sys, time
os.environ.setdefault("LIVE_CHANNEL_ENABLED", "1")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from thelmic.mediated_session import open_session
from thelmic.agent_helpers import find_track, find_device, ensure_device

TARGET_TRACK = "ORGAN"
TARGET_SLOT  = 1
UTILITY_URI  = "query:AudioFx#Utility"

ON_DB  =   0.0
OFF_DB = -60.0
EDGE_BEATS = 0.001    # near-instant transition between on and off


def square_breakpoints(rate_per_bar_schedule):
    """Build (time_beats, gain_dB) breakpoints for a square wave whose
    period changes per bar.

    rate_per_bar_schedule: list of cycles-per-bar values, one per bar.
        e.g. [4, 8, 16, 32] = bar1 4 cycles, bar2 8, bar3 16, bar4 32.
    """
    bp = []
    t = 0.0
    bar_len = 4.0    # 4 beats per bar
    for cycles in rate_per_bar_schedule:
        period = bar_len / cycles
        for _ in range(cycles):
            # on for first half
            bp.append((t, ON_DB))
            half = t + period / 2
            bp.append((half - EDGE_BEATS, ON_DB))
            bp.append((half, OFF_DB))
            # off for second half
            bp.append((t + period - EDGE_BEATS, OFF_DB))
            t += period
    bp.append((t, ON_DB))   # restore on at end
    return bp


def write_envelope_and_play(sess, track, slot, util_idx, util_gain_param,
                              breakpoints, label, beat_seconds):
    print(f"\n▶ {label}  ({len(breakpoints)} breakpoints over "
          f"{breakpoints[-1][0]:.1f} beats)")
    sess.raw_ch.set_clip_envelope(track, slot,
                                    target_track=track,
                                    target_device=util_idx,
                                    target_param=util_gain_param,
                                    breakpoints=breakpoints).result(timeout=5)
    sess.raw_ch.set_launch_quantization(0).result(timeout=2)
    sess.raw_ch.fire_clip(track, slot).result(timeout=3)
    duration_s = breakpoints[-1][0] * beat_seconds + 0.6
    time.sleep(duration_s)
    sess.raw_ch.stop_all_clips().result(timeout=3)
    time.sleep(0.8)
    # Clear envelope between variants
    sess.raw_ch.clear_clip_envelope(track, slot,
                                      target_track=track,
                                      target_device=util_idx,
                                      target_param=util_gain_param).result(timeout=3)


def main():
    with open_session(name="trance-gate-demo",
                      expected_tracks=[TARGET_TRACK]) as sess:
        bpm = sess.raw_ch.get_session_info().result(timeout=5)["tempo"]
        beat_seconds = 60.0 / bpm
        track = find_track(sess.raw_ch, TARGET_TRACK)
        if track is None:
            print(f"can't find {TARGET_TRACK}"); return

        util_idx = find_device(sess.raw_ch, track, "Utility")
        if util_idx is None:
            util_idx = ensure_device(sess.raw_ch, track, "Utility", UTILITY_URI)

        di = sess.raw_ch.get_device_info(track, util_idx).result(timeout=3)
        gain_param = next((p for p in di["parameters"] if p["name"] == "Gain"), None)
        if gain_param is None:
            print("Utility has no Gain param? params:")
            for p in di["parameters"]:
                print(f"  {p['name']}")
            return
        gain_index = gain_param["index"]
        print(f"Utility Gain param: index={gain_index} "
              f"min={gain_param['min']} max={gain_param['max']}")

        # Variant 1: STEADY 1/16 for 2 bars (16 cycles per bar, 2 bars)
        write_envelope_and_play(
            sess, track, TARGET_SLOT, util_idx, "Gain",
            square_breakpoints([16, 16]),
            "STEADY 1/16 for 2 bars", beat_seconds)

        # Variant 2: RAMP 1/4 → 1/8 → 1/16 → 1/32 (4 bars)
        write_envelope_and_play(
            sess, track, TARGET_SLOT, util_idx, "Gain",
            square_breakpoints([4, 8, 16, 32]),
            "RAMP 1/4→1/8→1/16→1/32 over 4 bars", beat_seconds)

        # Variant 3: SHRED 1/4 → 1/128 (6 bars)
        write_envelope_and_play(
            sess, track, TARGET_SLOT, util_idx, "Gain",
            square_breakpoints([4, 8, 16, 32, 64, 128]),
            "SHRED 1/4→1/8→1/16→1/32→1/64→1/128 over 6 bars", beat_seconds)

        sess.raw_ch.set_launch_quantization(1).result(timeout=2)
        print("\ndone — pick the variant.")


if __name__ == "__main__":
    main()
