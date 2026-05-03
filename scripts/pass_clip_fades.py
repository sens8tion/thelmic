"""Apply real audio-clip fade-ins to all non-drop sections.

Uses the new set_clip_fades RPC (clip.fade_in_time / fade_out_time).
Only audio clips support this — MIDI clips skipped silently.

Drops keep their hard land. Every other clip gets a 500ms fade-in
so sections actually fade into each other audibly."""
from __future__ import annotations
import os, sys
os.environ.setdefault("LIVE_CHANNEL_ENABLED", "1")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from thelmic.mediated_session import open_session

DROP_SLOTS = {4, 7, 9, 14, 15}    # impact lands hard — short fade only
FADE_IN_S = 0.5        # non-drops: half-second audible fade
DROP_FADE_IN_S = 0.06  # drops: 60ms transient round-off, impact preserved
FADE_OUT_S = 0.0       # never cut mid-sample for non-loopers — handle via loop=False instead
DROP_FADE_OUT_S = 0.0


def main():
    with open_session(name="clip-fades-pass") as sess:
        sess_info = sess.raw_ch.get_session_info().result(timeout=5)
        n_tracks = sess_info["track_count"]
        sess.snapshot("before-clip-fades")
        applied = 0; skipped = 0
        for ti in range(n_tracks):
            try:
                info = sess.raw_ch.get_track_info(ti).result(timeout=5)
            except Exception:
                continue
            if info.get("is_midi_track"):
                # MIDI clips don't support fade_in_time; skip
                continue
            name = info.get("name", f"T{ti}")
            for slot in range(17):
                if slot in DROP_SLOTS:
                    fade_in = DROP_FADE_IN_S; fade_out = DROP_FADE_OUT_S; tag = "DROP"
                else:
                    fade_in = FADE_IN_S; fade_out = FADE_OUT_S; tag = "soft"
                try:
                    res = sess.raw_ch.set_clip_fades(ti, slot,
                                                       fade_in=fade_in,
                                                       fade_out=fade_out
                                                       ).result(timeout=3)
                    applied += 1
                    print(f"  T{ti} {name} S{slot}: in={res.get('fade_in')}s out={res.get('fade_out')}s [{tag}]")
                except Exception as e:
                    estr = str(e)
                    if "No clip" in estr:
                        skipped += 1
                    else:
                        print(f"  T{ti} {name} S{slot}: {estr}")
        sess.note(f"applied {FADE_IN_S}s fade-in to {applied} audio clips, skipped {skipped} empty slots")
        sess.snapshot("after-clip-fades")
        print(f"\n{applied} fade-ins applied across audio tracks, drops kept sharp")


if __name__ == "__main__":
    main()
