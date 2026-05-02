"""Pass 2: smooth non-drop entries via fade-in + sub-second filter sweep.

Drops stay sharp (impact-is-sacred). Anything else that comes in mid-track
gets a 250ms volume ramp + 400ms HP filter sweep down to its resting HP.
Specifically targets ORGAN (which the user flagged as appearing too abruptly
around bars 17-18) and applies the same pattern to every non-drop entry.

Drop slots in the current arrangement are 4 (DROP), 7 (GABBER),
14 (GABBER RECAP), 15 (DOUBLE PACE FINALE). Everything else is treated as
a non-drop entry."""
from __future__ import annotations
import os, sys
os.environ.setdefault("LIVE_CHANNEL_ENABLED", "1")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from thelmic.mediated_session import open_session
from thelmic.agent_helpers import (
    find_track, find_device, smooth_clip_entry, FREQ_SEPARATION,
)

# Drops — keep sharp, no smooth-in
DROP_SLOTS = {4, 7, 14, 15}

# Tracks to smooth + their resting HP target (from FREQ_SEPARATION)
SMOOTH_TARGETS = [
    ("TECTONIC",   "mid_bass"),
    ("STAB",       "stab"),
    ("ORGAN",      "organ"),     # the one explicitly flagged
    ("COLD MIST",  "pad"),
    ("VOX",        "vox"),
]


def main():
    with open_session(name="smooth-entries-pass",
                      expected_tracks=[n for n, _ in SMOOTH_TARGETS]) as sess:
        sess.chat("agent", "smoothing non-drop entries: 250ms fade + 400ms HP sweep")
        sess.snapshot("before-smooth-entries")

        sess_info = sess.raw_ch.get_session_info().result(timeout=5)
        bpm = sess_info.get("tempo", 120.0)

        for name, role in SMOOTH_TARGETS:
            t = find_track(sess.raw_ch, name)
            if t is None:
                sess.note(f"missing track {name}, skipping")
                continue
            eq = find_device(sess.raw_ch, t, "Eq8")
            if eq is None:
                sess.note(f"T{t} {name}: no EQ8 — run freq-separation pass first")
                continue
            resting_hp_hz = FREQ_SEPARATION[role][0]
            # Try every slot 0..16. Empty slots / drop slots are skipped.
            # Both MIDI and audio clips supported — set_clip_envelope errs
            # on empties, we swallow that.
            applied = 0
            for slot in range(17):
                if slot in DROP_SLOTS:
                    continue
                ok = smooth_clip_entry(sess.raw_ch, t, slot,
                                        sweep_ms=400,
                                        sweep_from_hz=2000.0,
                                        sweep_to_hz=resting_hp_hz,
                                        eq_device_index=eq, eq_band=1, bpm=bpm)
                if ok:
                    applied += 1
                    msg = f"  T{t} {name} S{slot}: 400ms HP sweep 2000→{resting_hp_hz}Hz"
                    print(msg); sess.note(msg)
            if applied == 0:
                sess.note(f"T{t} {name}: no clips found in non-drop slots")

        sess.snapshot("after-smooth-entries")
        sess.chat("agent", "smooth-entries pass complete; drops still sharp")


if __name__ == "__main__":
    main()
