"""Pass 1: sound-stage frequency separation of concerns.

Each track gets a track-level EQ8 with HP (and optional LP) tuned to its
role so voices stop masking each other in the bass region. Standard
mix-engineering carving."""
from __future__ import annotations
import os, sys
os.environ.setdefault("LIVE_CHANNEL_ENABLED", "1")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from thelmic.mediated_session import open_session
from thelmic.agent_helpers import apply_freq_separation, FREQ_SEPARATION

# Map session tracks to their mix roles (sound-stage assignment)
TRACK_ROLES = {
    "TECTONIC":   "mid_bass",   # mid-bass synth, gets 50-400Hz pocket
    "STAB":       "stab",       # mid stab, HP 200
    "BREAKBEAST": "drums_bus",  # break sample track, just rumble cleanup
    "SUBBONK":    "sub",        # sub bass, 30-700Hz pocket
    "ORGAN":      "organ",      # mid harmonic, HP 180
    "COLD MIST":  "pad",        # pad, HP 250 lets kick/sub breathe
    "VOX":        "vox",        # vocal stabs, HP 150
    "HARDKIT":    "drums_bus",  # drum rack, HP 40 keeps kick body
}


def main():
    with open_session(name="freq-separation-pass",
                      expected_tracks=list(TRACK_ROLES.keys())) as sess:
        sess.chat("agent", "starting frequency-separation pass — HP/LP per role")
        sess.snapshot("before-freq-separation")

        for name, role in TRACK_ROLES.items():
            from thelmic.agent_helpers import find_track
            t = find_track(sess.raw_ch, name)
            if t is None:
                sess.note(f"missing track {name}, skipping")
                continue
            hp, lp = FREQ_SEPARATION[role]
            try:
                eq = apply_freq_separation(sess.raw_ch, t, role)
                lp_str = f" / LP@{lp}Hz" if lp else ""
                msg = f"  T{t} {name} ({role}): HP@{hp}Hz{lp_str} on EQ{eq}"
                print(msg); sess.note(msg)
            except Exception as e:
                err = f"  T{t} {name}: failed {e}"
                print(err); sess.note(err, kind="error")

        sess.snapshot("after-freq-separation")
        sess.chat("agent", "freq-separation pass complete")


if __name__ == "__main__":
    main()
