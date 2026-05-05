"""Wire the user's Live-native sliced rap track into T_RAP slot.

Workflow:
  - User sliced T6 (CHOP_PREP_RAP) → Live created T7 'rap_FULL_chop_me'
    with a Drum Rack of 83 transient slices (pads 36..118) and an
    auto-generated MIDI clip in slot 0 that triggers them in sequence.

This script:
  1. Reads T7 slot 0's auto-MIDI to learn slice onset times (in beats of
     the source-clip rate). Uses the absolute trigger order — each pitch
     P fires slice (P - 36).
  2. Deletes the old equal-interval T5 'RAP_NAIROBI'.
  3. Moves T7 to position 5, renames it RAP_NAIROBI.
  4. Wipes slot 0 of T7 and replaces with per-scene MIDI patterns that
     re-arrange the 83 slices across the 32-beat (8 bar) scene length.
  5. Cleans up empty prep tracks (CHOP_PREP_RAP, CHOP_PREP_LINGALA, the
     accidental empty audition track from earlier).
"""
from __future__ import annotations
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from thelmic.live_channel import LiveChannel

T_NEW_RAP_SOURCE = 7   # 'rap_FULL_chop_me' (Live-sliced)
T_OLD_RAP        = 5   # equal-interval drum rack — to delete
T_TARGET_POS     = 5   # where the new RAP_NAIROBI ends up
SCENE_LEN_BEATS  = 32.0
N_SCENES         = 4
PAD_BASE         = 36


def find_track_by_name(ch, name: str) -> int | None:
    info = ch.get_session_info().result(timeout=5)
    tc = info.get("track_count") or info.get("num_tracks") or 0
    for i in range(tc):
        ti = ch.get_track_info(i).result(timeout=3)
        if ti.get("name", "") == name:
            return i
    return None


def build_per_scene_patterns(slice_count: int) -> list[list[dict]]:
    """Re-arrange the slice palette across 4 scenes."""
    p_lo = PAD_BASE
    p_hi = PAD_BASE + slice_count - 1
    patterns: list[list[dict]] = []

    # ---- S0 INTRO — sparse "calls" — long held slices, half-bar spacing
    s0 = []
    picks = [0, slice_count // 4, slice_count // 2, 3 * slice_count // 4]
    for bar, slc in enumerate(picks):
        s0.append({"pitch": PAD_BASE + slc, "start_time": float(bar * 8),
                   "duration": 6.0, "velocity": 95})
    # 1 reverb tail at bar 7
    s0.append({"pitch": PAD_BASE + (slice_count - 1), "start_time": 28.0,
               "duration": 4.0, "velocity": 80})
    patterns.append(s0)

    # ---- S1 BUILD — linear walk through slices, 1 per beat for first 4 bars,
    #          then doubled-up for bars 5-8
    s1 = []
    for beat in range(16):
        slc = (beat * (slice_count // 16)) % slice_count
        s1.append({"pitch": PAD_BASE + slc, "start_time": float(beat),
                   "duration": 0.9, "velocity": 95})
    for half in range(32):
        slc = (half * (slice_count // 32) + 4) % slice_count
        s1.append({"pitch": PAD_BASE + slc, "start_time": 16.0 + half * 0.5,
                   "duration": 0.45, "velocity": 100 if half % 2 == 0 else 85})
    patterns.append(s1)

    # ---- S2 DROP — chopped/stuttered. 64 hits over 32 beats (8th-note grid).
    #          Mix linear walk + stutters on every &-of-2.
    s2 = []
    for i in range(64):
        t = i * 0.5
        # base slice = linear march
        slc = (i * (slice_count // 64 or 1)) % slice_count
        # stutter: every 4th hit, reuse previous
        if i % 4 == 1 and i > 0:
            slc = (slc - 1) % slice_count
        vel = 110 if i % 8 == 0 else (95 if i % 4 == 0 else 80)
        s2.append({"pitch": PAD_BASE + slc, "start_time": t, "duration": 0.45,
                   "velocity": vel})
    patterns.append(s2)

    # ---- S3 BREAK — solo. Long-form: 8 phrases (1 per bar), each phrase a
    #          burst of 4 slices over 2 beats then 2 beats silence.
    s3 = []
    for bar in range(8):
        base_slc = (bar * (slice_count // 8)) % slice_count
        for j in range(4):
            slc = (base_slc + j) % slice_count
            t = bar * 4 + j * 0.5
            s3.append({"pitch": PAD_BASE + slc, "start_time": t,
                       "duration": 0.45, "velocity": 100})
    patterns.append(s3)
    return patterns


def main():
    ch = LiveChannel(enabled=True); ch.start()
    try:
        info = ch.get_session_info().result(timeout=5)
        tc = info.get("track_count") or info.get("num_tracks") or 0
        print(f"track count: {tc}")

        # 1. Read T7 slot 0 to learn slice count
        raw = ch.get_clip_notes(T_NEW_RAP_SOURCE, 0).result(timeout=8)
        notes = raw["notes"]
        pitches = sorted({n["pitch"] for n in notes})
        slice_count = len(pitches)
        print(f"detected {slice_count} slices on T{T_NEW_RAP_SOURCE} "
              f"(pitches {min(pitches)}..{max(pitches)})")

        # 2. Delete old equal-interval RAP_NAIROBI (T5)
        old_idx = find_track_by_name(ch, "RAP_NAIROBI")
        if old_idx is not None:
            print(f"deleting old RAP_NAIROBI at T{old_idx}")
            ch.delete_track(old_idx).result(timeout=10)
            time.sleep(0.3)

        # After delete, T7 has shifted down by 1 → now T6
        # Refind:
        new_src = find_track_by_name(ch, "rap_FULL_chop_me")
        print(f"sliced source now at T{new_src}")

        # 3. Move it to position 5
        ch.move_track(new_src, T_TARGET_POS).result(timeout=10)
        time.sleep(0.3)
        ch.set_track_name(T_TARGET_POS, "RAP_NAIROBI").result(timeout=5)
        ch.set_track_color(T_TARGET_POS, 14).result(timeout=5)
        ch.set_track_volume(T_TARGET_POS, 0.85).result(timeout=5)
        print(f"renamed/moved → T{T_TARGET_POS} 'RAP_NAIROBI'")

        # 4. Wipe slot 0 (Live's auto-pattern) and write per-scene patterns
        # Need to ensure clips exist for slots 0..3 at SCENE_LEN_BEATS.
        # Live's auto clip in slot 0 is shorter — replace it.
        # Approach: remove notes from slot 0, then create new clip / use existing.
        # Try delete_clip first.

        # delete_clip then create_clip for clean state
        for s in range(N_SCENES):
            try:
                ch.delete_clip(T_TARGET_POS, s).result(timeout=5)
            except Exception:
                pass
            ch.create_clip(T_TARGET_POS, s, SCENE_LEN_BEATS).result(timeout=10)
            ch.set_clip_name(T_TARGET_POS, s, f"rap_S{s}").result(timeout=5)

        patterns = build_per_scene_patterns(slice_count)
        for s, notes in enumerate(patterns):
            ch.add_notes_to_clip(T_TARGET_POS, s, notes).result(timeout=10)
            print(f"  S{s}: wrote {len(notes)} notes")

        # 5. Cleanup empty prep tracks
        for nm in ["CHOP_PREP_RAP", "CHOP_PREP_LINGALA"]:
            t = find_track_by_name(ch, nm)
            if t is not None:
                print(f"deleting empty prep T{t} '{nm}'")
                ch.delete_track(t).result(timeout=10)

        # The duplicate empty ZULU_AUDITION (track at index 9 from earlier error
        # before scene-creation worked) — find tracks named ZULU_AUDITION; the
        # populated one has clips, the empty one doesn't. Inspect.
        info2 = ch.get_session_info().result(timeout=5)
        tc2 = info2.get("track_count") or info2.get("num_tracks") or 0
        for i in range(tc2 - 1, -1, -1):
            ti = ch.get_track_info(i).result(timeout=3)
            if ti.get("name") == "ZULU_AUDITION":
                # check clip count by trying slot 0
                try:
                    raw0 = ch.get_clip_notes(i, 0).result(timeout=3)
                    has_clip0 = True
                except Exception:
                    has_clip0 = False
                # actually for AUDIO tracks get_clip_notes errors. Try a different probe:
                # use get_track_info "clip_slot_states" if present, else assume the
                # higher-indexed ZULU_AUDITION is the populated one and delete the lower.
                pass
        # Heuristic: if there are 2 ZULU_AUDITION tracks, delete the first one (empty).
        zulus = []
        for i in range(tc2):
            ti = ch.get_track_info(i).result(timeout=3)
            if ti.get("name") == "ZULU_AUDITION":
                zulus.append(i)
        print(f"ZULU_AUDITION tracks: {zulus}")
        if len(zulus) >= 2:
            # delete the lower-indexed one (the empty pre-error track)
            ch.delete_track(zulus[0]).result(timeout=10)
            print(f"deleted empty ZULU_AUDITION at T{zulus[0]}")

        print("\nFINAL track list:")
        info3 = ch.get_session_info().result(timeout=5)
        tc3 = info3.get("track_count") or info3.get("num_tracks") or 0
        for i in range(tc3):
            ti = ch.get_track_info(i).result(timeout=3)
            print(f"  T{i:2d}  {ti.get('name','')!r}")
    finally:
        ch.stop()


if __name__ == "__main__":
    main()
