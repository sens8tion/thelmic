"""Ramp Chopper Amount toward the drop — realtime version.

Clip envelopes on audio clip device params are silently dropped by
Live (verified empirically: writes succeed, automation never plays).
This implementation instead schedules set_device_param calls during
session_record, which Live DOES capture as arrangement automation
when printing the take.

Default behaviour: dry audition (no record). Pass --record to arm
session_record so the ramp gets baked into the arrangement at the
current playhead position.
"""
from __future__ import annotations
import os, sys, time
os.environ.setdefault("LIVE_CHANNEL_ENABLED", "1")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from thelmic.mediated_session import open_session
from thelmic.agent_helpers import find_track

TARGET_TRACK = "ORGAN"
TARGET_SLOT  = 6
RAMP_HOLD_BARS  = 12
RAMP_GROW_BARS  = 4
LOW_AMOUNT      = 0.0
PEAK_AMOUNT     = 1.0
N_STEPS         = 32          # finer = smoother (RPC handles ~30 Hz fine)


def main(record_mode=False):
    with open_session(name="chopper-amount-ramp",
                      expected_tracks=[TARGET_TRACK]) as sess:
        bpm = sess.raw_ch.get_session_info().result(timeout=5)["tempo"]
        beat_seconds = 60.0 / bpm
        track = find_track(sess.raw_ch, TARGET_TRACK)
        info = sess.raw_ch.get_track_info(track).result(timeout=5)

        chopper_idxs = [di for di, d in enumerate(info.get("devices", []))
                         if d.get("class_name") == "AutoPan"
                         and "chop" in (d.get("name") or "").lower()]
        if not chopper_idxs:
            print("no Choppers on ORGAN — abort"); return
        print(f"Found Choppers at {chopper_idxs}")

        amount_idxs = {}
        for d in chopper_idxs:
            di = sess.raw_ch.get_device_info(track, d).result(timeout=3)
            amount_idxs[d] = next(p["index"] for p in di["parameters"]
                                    if p["name"] == "Amount")

        # Set initial low amount
        for d in chopper_idxs:
            sess.raw_ch.set_device_param(track, d, amount_idxs[d],
                                            LOW_AMOUNT).result(timeout=2)

        if record_mode:
            print("\n[REC] hard reset + arm session_record so the ramp prints to arrangement...")
            sess.raw_ch.stop_playback().result(timeout=3)
            sess.raw_ch.set_record_mode(False).result(timeout=3)
            sess.raw_ch.set_session_record(False).result(timeout=3)
            sess.raw_ch.stop_all_clips().result(timeout=3)
            sess.raw_ch.back_to_arrangement().result(timeout=3)
            sess.raw_ch.set_song_time(0.0).result(timeout=3)
            sess.raw_ch.set_record_mode(True).result(timeout=3)
            sess.raw_ch.set_session_record(True).result(timeout=3)
            sess.raw_ch.set_metronome(False).result(timeout=3)
            sess.raw_ch.set_launch_quantization(0).result(timeout=2)
        else:
            sess.raw_ch.set_launch_quantization(0).result(timeout=2)

        sess.raw_ch.fire_clip(track, TARGET_SLOT).result(timeout=3)
        if record_mode:
            sess.raw_ch.start_playback().result(timeout=3)
        t0 = time.monotonic()

        print(f"\nRamp: Amount={LOW_AMOUNT} for {RAMP_HOLD_BARS}b → "
              f"{PEAK_AMOUNT} over {RAMP_GROW_BARS}b in {N_STEPS} steps")

        # Hold low for the first window
        time.sleep(RAMP_HOLD_BARS * 4 * beat_seconds)

        # Step the ramp
        for k in range(1, N_STEPS + 1):
            value = LOW_AMOUNT + (PEAK_AMOUNT - LOW_AMOUNT) * (k / N_STEPS)
            for d in chopper_idxs:
                try:
                    sess.raw_ch.set_device_param(track, d, amount_idxs[d],
                                                    value).result(timeout=1)
                except Exception:
                    pass
            target_t = t0 + (RAMP_HOLD_BARS * 4 + (k * RAMP_GROW_BARS * 4 / N_STEPS)) * beat_seconds
            delay = target_t - time.monotonic()
            if delay > 0: time.sleep(delay)

        # Hold peak for 1 bar so the captured automation reads steady at the top
        time.sleep(4 * beat_seconds)

        if record_mode:
            sess.raw_ch.stop_playback().result(timeout=3)
            sess.raw_ch.set_session_record(False).result(timeout=3)
            sess.raw_ch.set_record_mode(False).result(timeout=3)
            sess.raw_ch.set_launch_quantization(1).result(timeout=2)
            print("done — arrangement should now contain Amount automation lanes "
                  "on ORGAN for all 3 Choppers, 12 bars low + 4 bar ramp + 1 bar peak")
        else:
            sess.raw_ch.stop_all_clips().result(timeout=3)
            sess.raw_ch.set_launch_quantization(1).result(timeout=2)
            print("done — audition only (no record). Pass --record to bake into arrangement.")


if __name__ == "__main__":
    main(record_mode="--record" in sys.argv)
