"""
1. Wire user's '09_twentytwo' slice (T7, 55 slices) into STAB lane:
     - delete empty STAB_LINGALA (T4)
     - rename T7 -> STAB_TWENTYTWO
     - read auto MIDI in slot 9 to learn slice palette
     - replace with per-scene stab patterns (sparse early, quad in drops, silent in break)

2. Sidechain SUB_VEIN keyed from KICK_BOOM via Compressor2.
"""
from __future__ import annotations
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from thelmic.live_channel import LiveChannel
from thelmic.bridge.helpers.sidechain import sidechain_pump

PAD_BASE = 36
N_SCENES = 8
SCENE_LEN = 32.0
COMPRESSOR_URI = "query:AudioFx#Compressor"


def find_track(ch, name):
    info = ch.get_session_info().result(timeout=5)
    tc = info.get("track_count") or info.get("num_tracks") or 0
    for i in range(tc):
        ti = ch.get_track_info(i).result(timeout=3)
        if ti.get("name") == name:
            return i
    return None


def stab_pattern(s: int, n: int) -> list[dict]:
    """Per-scene stab patterns. Lower 8 slices = stab fragments."""
    notes = []
    pick = lambda i: PAD_BASE + (i % n)
    if s == 0:    # silent
        return []
    elif s == 1:  # one tease at bar 7
        notes.append({"pitch": pick(2), "start_time": 24.0, "duration": 1.0, "velocity": 90})
    elif s == 2:  # PRE_DROP — accelerating tease
        for bar in (3, 5, 6, 7):
            notes.append({"pitch": pick(bar % 8), "start_time": float(bar*4),
                          "duration": 0.8, "velocity": 90 + bar*2})
        # bar 7-8 stutter
        for half in range(8):
            notes.append({"pitch": pick(half), "start_time": 28.0 + half*0.5,
                          "duration": 0.3, "velocity": 100})
    elif s == 3:  # DROP_FULL — stab on every 1 of every bar
        for bar in range(8):
            notes.append({"pitch": pick(bar), "start_time": float(bar*4),
                          "duration": 1.0, "velocity": 110})
            # +&-of-3 ghost
            notes.append({"pitch": pick(bar + 4), "start_time": float(bar*4 + 2.5),
                          "duration": 0.5, "velocity": 80})
    elif s == 4:  # ROLL_PEAK — quad: every beat 1, 2, 3, 4
        for bar in range(8):
            for beat in range(4):
                notes.append({"pitch": pick(bar*4 + beat), "start_time": float(bar*4 + beat),
                              "duration": 0.7, "velocity": 105 if beat == 0 else 90})
    elif s == 5:  # BREAK — silent
        return []
    elif s == 6:  # RE_BUILD — building density
        density = [1, 1, 2, 2, 4, 4, 8, 8]  # hits/bar
        for bar in range(8):
            d = density[bar]
            for hit in range(d):
                t = bar*4 + (hit * (4.0 / d))
                notes.append({"pitch": pick(bar*2 + hit), "start_time": float(t),
                              "duration": 0.4, "velocity": 80 + bar*4})
    elif s == 7:  # FINAL_DROP — quad+ stutter
        for bar in range(8):
            for beat in range(4):
                notes.append({"pitch": pick(bar*4 + beat), "start_time": float(bar*4 + beat),
                              "duration": 0.7, "velocity": 115 if beat == 0 else 95})
            # &-of-2 stutter
            notes.append({"pitch": pick(bar*4 + 5), "start_time": float(bar*4 + 1.5),
                          "duration": 0.3, "velocity": 88})
    return notes


def main():
    ch = LiveChannel(enabled=True); ch.start()
    try:
        # ---- 1. STAB pivot ----
        t_stab_old = find_track(ch, "STAB_LINGALA")
        if t_stab_old is not None:
            print(f"deleting old STAB_LINGALA at T{t_stab_old}")
            ch.delete_track(t_stab_old).result(timeout=10)

        t_22 = find_track(ch, "09_twentytwo")
        if t_22 is None:
            print("09_twentytwo not found — abort STAB wiring")
        else:
            ch.set_track_name(t_22, "STAB_TWENTYTWO").result(timeout=5)
            ch.set_track_color(t_22, 12).result(timeout=5)
            ch.set_track_volume(t_22, 0.78).result(timeout=5)
            print(f"renamed T{t_22} -> STAB_TWENTYTWO")

            # Read auto MIDI to discover slice count
            # The auto MIDI is in some slot — find the one with notes.
            slice_count = 0
            for s in range(12):
                try:
                    r = ch.get_clip_notes(t_22, s).result(timeout=3)
                    if r.get("count", 0) > 0:
                        ps = sorted({n["pitch"] for n in r["notes"]})
                        slice_count = len(ps)
                        print(f"detected {slice_count} slices in slot {s}")
                        break
                except Exception:
                    pass
            if slice_count == 0:
                slice_count = 32  # fallback

            # Wipe slots 0..7 and write fresh per-scene patterns
            for s in range(N_SCENES):
                try: ch.delete_clip(t_22, s).result(timeout=5)
                except Exception: pass
                ch.create_clip(t_22, s, SCENE_LEN).result(timeout=10)
                scene_names = ["INTRO_PULSE", "INTRO_BUILD", "PRE_DROP", "DROP_FULL",
                               "ROLL_PEAK", "BREAK_HYPNOTIC", "RE_BUILD", "FINAL_DROP"]
                ch.set_clip_name(t_22, s, f"{scene_names[s]}_stab").result(timeout=5)
                notes = stab_pattern(s, slice_count)
                if notes:
                    ch.add_notes_to_clip(t_22, s, notes).result(timeout=10)
                print(f"  S{s} stab: {len(notes)} notes")

            # Also wipe leftover slots 8..11 from the auto-MIDI
            for s in range(8, 12):
                try: ch.delete_clip(t_22, s).result(timeout=3)
                except Exception: pass

        # ---- 2. Sidechain SUB_VEIN keyed from KICK_BOOM ----
        t_kick = find_track(ch, "KICK_BOOM")
        t_sub  = find_track(ch, "SUB_VEIN")
        if t_kick is not None and t_sub is not None:
            print(f"\nsidechaining T{t_sub} (SUB_VEIN) <- T{t_kick} (KICK_BOOM)...")
            cmp_idx = sidechain_pump(ch, target_track=t_sub, source_track=t_kick,
                                       compressor_uri=COMPRESSOR_URI, intensity="heavy")
            print(f"  Compressor at device idx {cmp_idx} on SUB_VEIN, keyed from KICK_BOOM")
        else:
            print(f"missing tracks for sidechain (kick={t_kick} sub={t_sub})")

        # ---- 3. Final state ----
        info = ch.get_session_info().result(timeout=5)
        tc = info.get("track_count") or info.get("num_tracks") or 0
        print("\n--- FINAL TRACKS ---")
        for i in range(tc):
            ti = ch.get_track_info(i).result(timeout=3)
            print(f"  T{i:2d}  {ti.get('name','')!r}")
    finally:
        ch.stop()


if __name__ == "__main__":
    main()
