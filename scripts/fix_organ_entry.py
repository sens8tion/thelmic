"""ORGAN's first-bar entry was still popping despite the 400ms HP sweep —
the EQ8 HP filter type is one of the unverified values (EQ8_HP_12_GUESS),
so the sweep may not be doing what we expect audibly. Belt-and-braces fix:
do the fade in MIDI velocity space instead, which works regardless of
synth or filter routing.

For ORGAN's first appearance slots (1, 2, 3, 6), scale velocity of every
note in the first 4 beats (one bar) by a linear ramp 0.30 → 1.00. The
synth's velocity sensitivity does the fade for us. Filter sweep remains
in place as a complement."""
from __future__ import annotations
import os, sys
os.environ.setdefault("LIVE_CHANNEL_ENABLED", "1")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from thelmic.mediated_session import open_session
from thelmic.agent_helpers import find_track

ORGAN_FADE_SLOTS = [1, 2, 3, 6]
RAMP_BEATS = 4.0     # one bar at 4/4
RAMP_FROM = 0.30     # 30% of original velocity at the start
RAMP_TO   = 1.00     # 100% by end of ramp


def main():
    with open_session(name="organ-fade-in",
                      expected_tracks=["ORGAN"]) as sess:
        t = find_track(sess.raw_ch, "ORGAN")
        if t is None:
            sess.note("ORGAN missing")
            return
        sess.chat("agent", "applying velocity-ramp fade-in to ORGAN entries")
        sess.snapshot("before-organ-velocity-fade")

        for slot in ORGAN_FADE_SLOTS:
            try:
                notes = sess.raw_ch.get_clip_notes(t, slot).result(timeout=3).get("notes", [])
            except Exception as e:
                sess.note(f"ORGAN S{slot}: get_clip_notes failed {e}")
                continue
            if not notes:
                sess.note(f"ORGAN S{slot}: empty / audio clip — skipping")
                continue
            ramped = []
            touched = 0
            for n in notes:
                t0 = n["start_time"]
                if t0 < RAMP_BEATS:
                    x = max(0.0, min(1.0, t0 / RAMP_BEATS))
                    factor = RAMP_FROM + (RAMP_TO - RAMP_FROM) * x
                    new_vel = max(1, min(127, int(n["velocity"] * factor)))
                    touched += 1
                else:
                    new_vel = n["velocity"]
                ramped.append({"pitch": n["pitch"], "start_time": t0,
                                "duration": n["duration"], "velocity": new_vel})
            try:
                clip_len = max(n["start_time"] + n["duration"] for n in notes)
                clip_len = max(clip_len, RAMP_BEATS)
                sess.raw_ch.clear_clip(t, slot).result(timeout=3)
                sess.raw_ch.create_clip(t, slot, float(clip_len)).result(timeout=5)
                sess.raw_ch.set_clip_name(t, slot, f"organ_s{slot}_faded").result(timeout=3)
                sess.raw_ch.add_notes_to_clip(t, slot, ramped).result(timeout=10)
                msg = f"  ORGAN S{slot}: ramped {touched}/{len(notes)} notes (vel {RAMP_FROM:.0%}→{RAMP_TO:.0%} over {RAMP_BEATS}b)"
                print(msg); sess.note(msg)
            except Exception as e:
                err = f"  ORGAN S{slot}: rewrite failed {e}"
                print(err); sess.note(err, kind="error")

        sess.snapshot("after-organ-velocity-fade")


if __name__ == "__main__":
    main()
