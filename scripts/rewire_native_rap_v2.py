"""Wire user's freshly re-sliced rap MIDI track into RAP_NAIROBI slot.

After user re-sliced CHOP_PREP_RAP (T7) -> Live created a new MIDI track
'rap_FULL_chop_me' (or similar) with a fresh slice rack. This script:

  1. Finds the new sliced rack track (any non-RAP_NAIROBI track with a
     DrumGroupDevice + an auto-generated MIDI clip referencing many pitches)
  2. Reads its slice count
  3. Deletes my 64-slice approximation currently named RAP_NAIROBI
  4. Renames the new sliced track -> RAP_NAIROBI
  5. Sets Trigger Mode=1 on every pad
  6. Wipes auto clip + writes per-scene patterns
  7. Deletes empty CHOP_PREP_RAP source track
"""
from __future__ import annotations
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from thelmic.live_channel import LiveChannel

PAD_BASE = 36
SCENE_LEN = 32.0


def find_track(ch, name):
    info = ch.get_session_info().result(timeout=5)
    for i in range(info.get("track_count") or 0):
        if ch.get_track_info(i).result(timeout=3).get("name") == name:
            return i
    return None


def find_new_slice_track(ch, exclude_indices: set[int]):
    """A drum-rack track with a clip in slot 0 spanning many distinct pitches."""
    info = ch.get_session_info().result(timeout=5)
    tc = info.get("track_count") or 0
    candidates = []
    for i in range(tc):
        if i in exclude_indices: continue
        ti = ch.get_track_info(i).result(timeout=3)
        # must have devices
        if ti.get("device_count", 0) == 0:
            continue
        d0 = ch.get_device_info(i, 0).result(timeout=3)
        if d0.get("class_name") != "DrumGroupDevice":
            continue
        # find a slot with notes
        slice_count = 0
        for s in range(16):
            try:
                r = ch.get_clip_notes(i, s).result(timeout=3)
                if r.get("count", 0) > 10:  # slice racks have lots of unique pitches
                    pitches = {n["pitch"] for n in r["notes"]}
                    slice_count = len(pitches)
                    break
            except Exception:
                pass
        candidates.append((i, ti.get("name"), slice_count))
    return candidates


def rap_pattern(s, n):
    pick = lambda i: PAD_BASE + (i % n)
    notes = []
    if s == 0:
        notes.append({"pitch": pick(0), "start_time": 4.0, "duration": 4.0, "velocity": 90})
        notes.append({"pitch": pick(n-1), "start_time": 24.0, "duration": 4.0, "velocity": 80})
    elif s == 1:
        for bar in range(0, 8, 2):
            notes.append({"pitch": pick((bar//2)*(n//4)), "start_time": float(bar*4),
                          "duration": 6.0, "velocity": 95})
    elif s == 2:
        for i in range(8):
            notes.append({"pitch": pick(i*(n//16) or i), "start_time": float(i*2),
                          "duration": 1.8, "velocity": 92+i})
        for beat in range(8):
            notes.append({"pitch": pick(16 + beat*(n//32 or 1)), "start_time": 16.0+float(beat),
                          "duration": 0.95, "velocity": 100})
        for half in range(16):
            notes.append({"pitch": pick(24+half), "start_time": 24.0+half*0.5,
                          "duration": 0.45, "velocity": 105})
    elif s == 3:
        for beat in range(32):
            notes.append({"pitch": pick(beat*2), "start_time": float(beat),
                          "duration": 0.95, "velocity": 105 if beat%4==0 else 90})
    elif s == 4:
        for half in range(64):
            slc = (half*(n//64 or 1)) % n
            if half % 4 == 1: slc = (slc-1) % n
            notes.append({"pitch": pick(slc), "start_time": half*0.5,
                          "duration": 0.45, "velocity": 110 if half%8==0 else 92})
    elif s == 5:
        picks = [0, n//4, n//2, 3*n//4]
        for i, slc in enumerate(picks):
            notes.append({"pitch": pick(slc), "start_time": float(i*8),
                          "duration": 7.0, "velocity": 95})
    elif s == 6:
        for i in range(8):
            notes.append({"pitch": pick(i*(n//16) or i), "start_time": float(i*2),
                          "duration": 1.8, "velocity": 92})
        for beat in range(16):
            notes.append({"pitch": pick(16+beat*3), "start_time": 16.0+float(beat),
                          "duration": 0.9, "velocity": 95+beat})
    elif s == 7:
        for half in range(64):
            slc = (half*3 + half//4) % n
            if half % 8 == 1: slc = (slc-2) % n
            notes.append({"pitch": pick(slc), "start_time": half*0.5,
                          "duration": 0.4, "velocity": 115 if half%4==0 else 95})
    return notes


def main():
    ch = LiveChannel(enabled=True); ch.start()
    try:
        # 1. Identify current RAP_NAIROBI (the 64-slice approximation to discard)
        old_rap = find_track(ch, "RAP_NAIROBI")
        print(f"current RAP_NAIROBI at T{old_rap} (will delete)")

        # 2. Find the new sliced track (any drum-rack track NOT being RAP_NAIROBI/STAB_TWENTYTWO)
        stab_t = find_track(ch, "STAB_TWENTYTWO")
        exclude = {old_rap, stab_t} - {None}
        cands = find_new_slice_track(ch, exclude)
        print(f"slice-rack candidates: {cands}")
        # Pick the candidate with the most slices (Live's slicing typically ~80-120)
        cands.sort(key=lambda x: -x[2])
        if not cands or cands[0][2] < 8:
            print("No fresh slice rack detected. Did you slice CHOP_PREP_RAP?")
            return
        new_t, new_name, slice_count = cands[0]
        print(f"new slice rack: T{new_t} '{new_name}' with {slice_count} slices")

        # 3. Delete old RAP_NAIROBI (the 64-slice approximation)
        if old_rap is not None and old_rap != new_t:
            ch.delete_track(old_rap).result(timeout=10)
            print(f"deleted old RAP_NAIROBI at T{old_rap}")
            # Reindex new_t if it shifted
            if new_t > old_rap:
                new_t -= 1
                print(f"  shifted new track index -> T{new_t}")

        # 4. Rename new track
        ch.set_track_name(new_t, "RAP_NAIROBI").result(timeout=5)
        ch.set_track_color(new_t, 14).result(timeout=5)
        ch.set_track_volume(new_t, 0.85).result(timeout=5)
        print(f"renamed T{new_t} -> RAP_NAIROBI")

        # 5. Set Trigger Mode=1 on every pad
        ok = fail = 0
        for i in range(slice_count):
            try:
                ch.set_drum_pad_chain_device_param(
                    track_index=new_t, device_index=0,
                    note=PAD_BASE+i, chain_device_index=0,
                    param_name="Trigger Mode", value=1.0,
                ).result(timeout=4)
                ok += 1
            except Exception as e:
                fail += 1
                if fail <= 2: print(f"  pad {PAD_BASE+i}: {type(e).__name__}: {e}")
        print(f"Trigger Mode=1: {ok} ok / {fail} fail")

        # 6. Wipe slots 0..7 (incl Live's auto clip wherever it landed) + write patterns
        for s in range(16):
            try: ch.delete_clip(new_t, s).result(timeout=3)
            except Exception: pass
        scene_names = ["INTRO_PULSE","INTRO_BUILD","PRE_DROP","DROP_FULL",
                       "ROLL_PEAK","BREAK_HYPNOTIC","RE_BUILD","FINAL_DROP"]
        for s in range(8):
            ch.create_clip(new_t, s, SCENE_LEN).result(timeout=8)
            ch.set_clip_name(new_t, s, f"{scene_names[s]}_rap").result(timeout=3)
            notes = rap_pattern(s, slice_count)
            if notes:
                ch.add_notes_to_clip(new_t, s, notes).result(timeout=8)
            print(f"  S{s}: {len(notes)} notes")

        # 7. Delete empty CHOP_PREP_RAP
        prep = find_track(ch, "CHOP_PREP_RAP")
        if prep is not None:
            ch.delete_track(prep).result(timeout=10)
            print(f"deleted empty CHOP_PREP_RAP at T{prep}")

        # 8. Final state
        info = ch.get_session_info().result(timeout=5)
        print("\n--- FINAL TRACKS ---")
        for i in range(info.get("track_count") or 0):
            ti = ch.get_track_info(i).result(timeout=3)
            print(f"  T{i:2d}  {ti.get('name','')!r}")
    finally:
        ch.stop()


if __name__ == "__main__":
    main()
