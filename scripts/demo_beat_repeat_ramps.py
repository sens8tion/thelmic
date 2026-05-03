"""Sample-accurate stutter ramps via Ableton's Beat Repeat device.

RPC-fired retriggers smear below 1/16 (RPC latency ≈ gap). Beat Repeat
runs in Live's audio engine at sample rate, so 1/64 and 1/128
subdivisions are mathematically precise. We load Beat Repeat onto ORGAN,
fire its slot 1 clip, and step the Interval parameter down through
subdivisions in real time.

Three variants:
  1. STEADY GATE     — hold 1/16 for 2 bars (constant fast pulse)
  2. RAMP TO SHRED   — 1/4 → 1/8 → 1/16 → 1/32 → 1/64 → 1/128 (1 bar each)
  3. INSTANT SHRED   — slam to 1/128 for 1 bar then off
"""
from __future__ import annotations
import os, sys, time
os.environ.setdefault("LIVE_CHANNEL_ENABLED", "1")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from thelmic.mediated_session import open_session
from thelmic.agent_helpers import find_track, find_device, ensure_device

TARGET_TRACK = "ORGAN"
TARGET_SLOT  = 1
BEAT_REPEAT_URI = "query:AudioFx#Beat%20Repeat"


def _param_idx(ch, t, d):
    di = ch.get_device_info(t, d).result(timeout=5)
    return {p["name"]: p["index"] for p in di["parameters"]}, di["parameters"]


def main():
    with open_session(name="beat-repeat-demo",
                      expected_tracks=[TARGET_TRACK]) as sess:
        bpm = sess.raw_ch.get_session_info().result(timeout=5)["tempo"]
        beat_seconds = 60.0 / bpm
        track = find_track(sess.raw_ch, TARGET_TRACK)
        if track is None:
            print(f"can't find {TARGET_TRACK}"); return

        # Add Beat Repeat (or find existing)
        br_idx = find_device(sess.raw_ch, track, "BeatRepeat")
        if br_idx is None:
            br_idx = ensure_device(sess.raw_ch, track, "BeatRepeat", BEAT_REPEAT_URI)
        idx, params = _param_idx(sess.raw_ch, track, br_idx)
        # Print params so we know what's available
        print("Beat Repeat parameters:")
        for p in params:
            print(f"  [{p['index']:>2}] {p['name']:<24} value={p['value']:<6} "
                  f"min={p['min']:<6} max={p['max']:<6}")

        # Find the relevant params (names vary slightly across Live versions)
        def get(*candidates):
            for c in candidates:
                if c in idx: return idx[c]
            return None

        i_chance = get("Chance")
        i_variation = get("Variation")
        i_grid = get("Grid")
        i_interval = get("Interval")
        i_gate = get("Gate")

        if i_chance is None or i_grid is None:
            print("could not find Chance/Grid params — abort")
            return

        # Configure for mathematical precision
        # Chance = 100% (always replace input with repeat) for the demo windows
        # Variation = 0 (no random offset)
        # Gate = 16 (long enough to hear repeats clearly)
        if i_variation is not None:
            sess.raw_ch.set_device_param(track, br_idx, i_variation, 0.0).result(timeout=2)
        if i_gate is not None:
            di = sess.raw_ch.get_device_info(track, br_idx).result(timeout=3)
            for p in di["parameters"]:
                if p["index"] == i_gate:
                    # Gate uses 16ths typically — set to a long-ish value
                    sess.raw_ch.set_device_param(track, br_idx, i_gate, p["max"]).result(timeout=2)
                    break

        def set_grid(value):
            """Grid is the subdivision parameter (1/4, 1/8, 1/16, ...).
            Often discrete enum. Probe its range and pass directly."""
            sess.raw_ch.set_device_param(track, br_idx, i_grid, value).result(timeout=2)

        def chance_on():
            sess.raw_ch.set_device_param(track, br_idx, i_chance, 1.0).result(timeout=2)

        def chance_off():
            sess.raw_ch.set_device_param(track, br_idx, i_chance, 0.0).result(timeout=2)

        # Probe Grid range to know what values map to subdivisions
        di = sess.raw_ch.get_device_info(track, br_idx).result(timeout=3)
        grid_p = next(p for p in di["parameters"] if p["index"] == i_grid)
        print(f"\nGrid range: min={grid_p['min']} max={grid_p['max']} (typically 0=1/4 ... N=1/128)")
        gmax = grid_p["max"]

        # Helper to get a normalized grid value at a target subdivision
        # Live's Grid param is usually a discrete enum 0..N where higher = finer.
        # We'll just step value 0..gmax linearly.
        def grid_step(step, total):
            """Pick the kth grid value out of total — steps from coarse to fine."""
            return grid_p["min"] + (grid_p["max"] - grid_p["min"]) * (step / max(1, total - 1))

        # Pre-roll: fire ORGAN clip and let it stabilise
        sess.raw_ch.set_launch_quantization(0).result(timeout=2)
        chance_off()
        sess.raw_ch.fire_clip(track, TARGET_SLOT).result(timeout=3)
        time.sleep(0.5)

        # Variant 1: STEADY GATE @ 1/16 for 2 bars
        print("\n▶ STEADY GATE @ 1/16 for 2 bars")
        # 1/16 is roughly 4 steps in for typical Beat Repeat (0=1/4, 1=1/4t, 2=1/8, 3=1/8t, 4=1/16, ...)
        # Use direct enum value 4 if available
        set_grid(min(4.0, gmax))
        chance_on()
        time.sleep(2 * 4 * beat_seconds)   # 2 bars
        chance_off()
        time.sleep(1.0)

        # Variant 2: RAMP TO SHRED — 1/4 → 1/8 → 1/16 → 1/32 → 1/64 → 1/128
        print("\n▶ RAMP TO SHRED — 1/4 to 1/128 over 6 bars")
        chance_on()
        # Step values approximate; depends on Live's Grid enum.
        # Common enum: 0=1/4, 2=1/8, 4=1/16, 6=1/32, 8=1/64, 10=1/128
        ramp_values = [0, 2, 4, 6, 8, min(10, gmax)]
        for gv in ramp_values:
            set_grid(float(gv))
            time.sleep(4 * beat_seconds)   # 1 bar each
        chance_off()
        time.sleep(1.0)

        # Variant 3: INSTANT SHRED — slam to 1/128 for 1 bar
        print("\n▶ INSTANT SHRED — 1/128 for 1 bar")
        set_grid(float(min(10, gmax)))
        chance_on()
        time.sleep(4 * beat_seconds)
        chance_off()
        time.sleep(1.0)

        sess.raw_ch.stop_all_clips().result(timeout=3)
        sess.raw_ch.set_launch_quantization(1).result(timeout=2)
        print("\ndone — pick the variant. Ramp values may need fine-tuning to align "
              "with Live 12's Grid enum.")


if __name__ == "__main__":
    main()
