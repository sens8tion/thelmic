"""Print the session into a linear arrangement.

1. Verify session loaded (resolve track names, fail fast if empty/wrong)
2. Apply anticipation techniques to pre-drop scenes (filter fades, tightening
   ticks, dropped hits)
3. Arm session-record + play the scene sequence with proper timing
4. Stop + leave a printed track in arrangement view
"""
from __future__ import annotations
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from thelmic.live_channel import LiveChannel


# Scene sequence: (slot, bars to hold)
# Final intense section alternates 15 and 16 in 8-bar phrases — they
# play nicely into/out of each other and the swap creates extra dynamic
# interplay vs holding each statically. Total bars unchanged (48 = 32+16).
ARRANGEMENT = [
    (0,  16),  # INTRO pad
    (1,  16),  # STIRRING
    (2,  16),  # BUILD
    (3,  16),  # RISER (anticipation)
    (4,  32),  # DROP
    (5,  16),  # BREAKDOWN
    (6,  16),  # REBUILD (anticipation)
    (7,  32),  # GABBER
    (9,  32),  # BREAKCORE CHAOS
    (10,  8),  # BREAKDOWN POST (short)
    (12, 16),  # FOOTWORK FULL
    (13, 16),  # JUNGLE RETURN (anticipation)
    (14, 32),  # GABBER RECAP
    # Finale alternation: 15↔16 every 8 bars × 6 = 48 bars
    (15,  8),  # DOUBLE PACE FINALE
    (16,  8),  # OUTRO bank
    (15,  8),
    (16,  8),
    (15,  8),
    (16,  8),
]

# Anticipation pre-drop slots (last bar gets fills)
ANTICIPATION_SLOTS = [3, 6, 13]


def find_track(ch, sess_count, name_match):
    """Find first track whose name contains name_match (case-insens). Returns idx or None."""
    for i in range(sess_count):
        info = ch.get_track_info(i).result(timeout=5)
        if name_match.lower() in info["name"].lower():
            return i
    return None


def health_check(ch):
    """Probe session — return (ok, details). Fast-fail if session looks empty/default."""
    try:
        ch.ping().result(timeout=3)
    except Exception as e:
        return False, f"Live not responding: {e}"
    sess = ch.get_session_info().result(timeout=5)
    n = sess["track_count"]
    if n < 6:
        return False, f"only {n} tracks — fresh project? load the jungle set first"
    # Scan for our named tracks
    looking_for = ["TECTONIC", "STAB", "BREAKBEAST", "SUBBONK", "ORGAN",
                    "COLD MIST", "VOX", "HARDKIT"]
    found = []
    missing = []
    for needle in looking_for:
        idx = find_track(ch, n, needle)
        if idx is not None:
            found.append((needle, idx))
        else:
            missing.append(needle)
    if missing:
        return False, f"missing tracks: {missing}"
    return True, found


def kick_snare_pitches():
    return 36, 38, 42, 49


def fill_anticipation(bs):
    """Bar starting at beat `bs` — last bar of a 16-bar pre-drop scene.

    Filter fade + tightening ticks + dropped hits.
    Returns: list of (pitch, start_time, duration, velocity)
    """
    KICK, SNARE, HAT_C, CRASH = kick_snare_pitches()
    out = []
    # Beats 0-1.5: regular pattern but tightening — accelerating closed hat
    for i in range(6):
        t = bs + i * 0.25
        out.append((HAT_C, t, 0.10, 80 + i * 4))
    # Beats 1.5-3: 32nd-note hat ticks (tightening)
    for i in range(12):
        t = bs + 1.5 + i * 0.125
        out.append((HAT_C, t, 0.05, 90 + i * 2))
    # Beat 3-3.5: snare flam roll
    for i in range(4):
        t = bs + 3.0 + i * 0.125
        out.append((SNARE, t, 0.08, 100 + i * 6))
    # Beats 3.5-3.875: silence (DROPPED HITS — anticipation gap)
    # Beat 3.875: final accent — kick + crash + snare unison
    out.append((KICK, bs + 3.875, 0.2, 127))
    out.append((SNARE, bs + 3.875, 0.2, 127))
    out.append((CRASH, bs + 3.875, 4.0, 127))
    return out


def amen_4bar(start_offset=0.0):
    KICK, SNARE, HAT_C, _ = kick_snare_pitches()
    notes = []
    base = [
        (KICK, 0.0, 0.4, 110), (SNARE, 1.0, 0.35, 100),
        (KICK, 1.5, 0.4, 95),  (SNARE, 3.0, 0.35, 105),
        (KICK, 4.0, 0.4, 110), (SNARE, 5.0, 0.35, 100),
        (SNARE, 5.5, 0.2, 75), (SNARE, 6.5, 0.3, 95),
        (KICK, 7.5, 0.35, 90),
        (KICK, 8.0, 0.4, 110), (SNARE, 9.0, 0.35, 100),
        (KICK, 10.5, 0.35, 95),(SNARE, 11.0, 0.35, 105),
        (KICK, 12.0, 0.4, 110),(SNARE, 13.0, 0.3, 95),
        (SNARE, 13.5, 0.2, 75),(SNARE, 14.0, 0.35, 100),
        (KICK, 14.5, 0.35, 90),(SNARE, 15.0, 0.3, 95),
        (SNARE, 15.5, 0.25, 80),
    ]
    for p, t, dur, vel in base:
        notes.append((p, t + start_offset, dur, vel))
    for i in range(64):
        t = i * 0.25 + start_offset
        slot = i % 4
        vel = {0: 92, 1: 65, 2: 78, 3: 65}[slot]
        notes.append((HAT_C, t, 0.18, vel))
    return notes


def write_with_anticipation(ch, hardkit_idx, slot, name):
    """3 bars amen + thinned final bar + impact. Plus: pull-back velocity ramp
    over last 4 beats (impact preserved), and gentle breathing on the steady part."""
    from thelmic.agent_helpers import (
        breathe_velocity, pull_back_before_drop,
    )
    KICK, SNARE, HAT_C, CRASH = kick_snare_pitches()
    notes = []
    for rep in range(3):
        for p, t, dur, vel in amen_4bar(rep * 16.0):
            notes.append((p, t, dur, vel))
    for p, t, dur, vel in amen_4bar(48.0):
        if t < 62.0:
            notes.append((p, t, dur, vel))
        elif p == HAT_C and t < 63.875:
            notes.append((p, t, dur, vel))
    for p, t, dur, vel in fill_anticipation(60.0):
        if t >= 63.875 or p == HAT_C or t < 62.0:
            notes.append((p, t, dur, vel))
    # Breathing on bars 0-44 (steady section), 8-beat period, ±8 vel
    notes_breathing = []
    for n in notes:
        if n[1] < 44.0:
            notes_breathing.append(n)
        else:
            notes_breathing.append(n)
    notes_breathing = breathe_velocity(notes_breathing, amplitude=8, period_beats=8.0)
    # Pull-back over last 4 beats before drop at 63.875
    notes_final = pull_back_before_drop(notes_breathing, drop_at_beat=63.875,
                                          pull_window_beats=4.0, min_factor=0.6)
    notes_dicts = [{"pitch": p, "start_time": t, "duration": dur, "velocity": vel}
                   for (p, t, dur, vel) in notes_final if 0.0 <= t < 64.0]
    try: ch.clear_clip(hardkit_idx, slot).result(timeout=3)
    except Exception: pass
    ch.create_clip(hardkit_idx, slot, 64.0).result(timeout=10)
    ch.set_clip_name(hardkit_idx, slot, name).result(timeout=3)
    ch.add_notes_to_clip(hardkit_idx, slot, notes_dicts).result(timeout=10)
    return len(notes_dicts)


def add_hardkit_decay_tail(ch, hardkit_idx, slot=16):
    """When HARDKIT exits into a quieter outro, append a low-vel CRASH that
    rings out + a soft KICK to give bottom-end a graceful fall."""
    from thelmic.agent_helpers import crash_decay_tail, low_kick_decay_tail
    try:
        cinfo = ch.get_clip_info(hardkit_idx, slot).result(timeout=3)
    except Exception:
        return
    if not cinfo:
        return
    clip_len = cinfo.get("length", 16.0)
    cut_at = max(0.0, clip_len - 8.0)  # tail starts 2 bars before clip end
    # crash @ cut_at rings 6 beats; soft kick 1 beat later for low-end air
    cp, ct, cd, cv = crash_decay_tail(cut_at, vel=72, dur=6.0)
    kp, kt, kd, kv = low_kick_decay_tail(cut_at + 1.0, vel=55, dur=2.5)
    extra = [
        {"pitch": cp, "start_time": ct, "duration": cd, "velocity": cv},
        {"pitch": kp, "start_time": kt, "duration": kd, "velocity": kv},
    ]
    ch.add_notes_to_clip(hardkit_idx, slot, extra).result(timeout=10)
    print(f"    HARDKIT outro tail: crash@{ct} (vel{cv}, {cd}b) + soft kick@{kt}")


def soften_outro(ch, sess_count, bpm, outro_slot=16):
    """Stagger outro instrument exits by ms and let reverb ring.

    Walk through harsh→gentle exit order; clear notes in the last bar of each
    voice's outro clip in staggered ms steps. Sub/kick stay until the very end.
    """
    from thelmic.agent_helpers import (
        ms_to_beats, OUTRO_INSTRUMENT_STAGGER_MS, soft_outro_offsets,
    )
    # Exit order: harsh first, bottom-end last (perceived smoothness)
    exit_order = ["STAB", "ORGAN", "VOX", "COLD MIST", "BREAKBEAST", "TECTONIC", "SUBBONK", "HARDKIT"]
    offsets_ms = [i * OUTRO_INSTRUMENT_STAGGER_MS for i in range(len(exit_order))]
    print(f"  outro stagger: {offsets_ms} ms")

    for name, off_ms in zip(exit_order, offsets_ms):
        idx = find_track(ch, sess_count, name)
        if idx is None:
            continue
        try:
            cinfo = ch.get_clip_info(idx, outro_slot).result(timeout=3)
        except Exception:
            continue
        if not cinfo or cinfo.get("name") in (None, ""):
            continue
        clip_len = cinfo.get("length", 16.0)
        # Cut tail point in beats — leave reverb tail by trimming notes only,
        # not clip length. Cut at clip_len - small ms offset.
        cut_at = clip_len - ms_to_beats(off_ms, bpm)
        try:
            notes = ch.get_clip_notes(idx, outro_slot).result(timeout=5).get("notes", [])
        except Exception:
            continue
        # Truncate notes that extend past cut point; remove notes starting after.
        new_notes = []
        for n in notes:
            t = n["start_time"]; dur = n["duration"]
            if t >= cut_at:
                continue
            if t + dur > cut_at:
                dur = max(0.05, cut_at - t)
            new_notes.append({"pitch": n["pitch"], "start_time": t,
                              "duration": dur, "velocity": n["velocity"]})
        try:
            ch.clear_clip(idx, outro_slot).result(timeout=3)
            ch.create_clip(idx, outro_slot, clip_len).result(timeout=5)
            ch.set_clip_name(idx, outro_slot, f"outro_{name.lower()}_taper").result(timeout=3)
            if new_notes:
                ch.add_notes_to_clip(idx, outro_slot, new_notes).result(timeout=10)
            print(f"    {name}: cut at beat {cut_at:.3f} ({off_ms}ms taper)")
        except Exception as e:
            print(f"    {name}: skip ({e})")


def main(num_takes=1):
    """num_takes>1: each take prints starting at take_index * (total_bars + gap)
    so they sit side-by-side on the arrangement timeline. Save .als manually
    via File>Save As to checkpoint."""
    from thelmic.agent_helpers import take_start_bar, TAKE_GAP_BARS
    ch = LiveChannel(lower_priority=False); ch.start()
    try:
        ok, detail = health_check(ch)
        if not ok:
            print(f"HEALTH CHECK FAILED: {detail}")
            print("Open your saved jungle Live set, then re-run.")
            return
        print(f"health OK — found tracks: {detail}")

        sess = ch.get_session_info().result(timeout=5)
        n = sess["track_count"]
        bpm = sess["tempo"]

        T_HARDKIT = find_track(ch, n, "HARDKIT")
        T_PAD = find_track(ch, n, "COLD MIST")
        if T_HARDKIT is None or T_PAD is None:
            print("can't find HARDKIT or COLD MIST track")
            return

        # ---- Apply anticipation to pre-drop scenes ----
        print("\napplying anticipation fills to pre-drop scenes (thinned build, sacred impact)...")
        for slot in ANTICIPATION_SLOTS:
            try:
                n_notes = write_with_anticipation(ch, T_HARDKIT, slot,
                                                    f"slot{slot}_anticipation")
                print(f"  slot {slot}: {n_notes} notes (thinned 2-beat window + impact)")
            except Exception as e:
                print(f"  slot {slot} fail: {e}")

        # ---- Soften outro on slot 16 ----
        print("\nstaggering outro exits on slot 16 (harsh-first, sub/kick last)...")
        try:
            soften_outro(ch, n, bpm, outro_slot=16)
        except Exception as e:
            print(f"  outro soften fail: {e}")

        # ---- HARDKIT decay tail (crash + soft kick) into the outro ----
        print("adding HARDKIT decay tail (crash ring + soft kick)...")
        try:
            add_hardkit_decay_tail(ch, T_HARDKIT, slot=16)
        except Exception as e:
            print(f"  hardkit tail fail: {e}")

        # ---- Arm session record + run arrangement (per take) ----
        bar_seconds = 60.0 / bpm * 4
        total_bars = sum(b for _, b in ARRANGEMENT)
        print(f"\n  bpm={bpm}, 1 bar = {bar_seconds:.3f}s")
        print(f"  total per take: {total_bars} bars = {total_bars * bar_seconds:.1f}s")
        print(f"  takes: {num_takes} (gap {TAKE_GAP_BARS} bars between)")

        for take_i in range(num_takes):
            start_bar = take_start_bar(take_i, total_bars, TAKE_GAP_BARS)
            print(f"\n=== take {take_i+1}/{num_takes} starting bar {start_bar} ===")
            ch.set_song_time(start_bar * 4.0).result(timeout=5)  # 4 beats per bar
            ch.stop_all_clips().result(timeout=5)
            ch.back_to_arrangement().result(timeout=5)
            ch.set_record_mode(True).result(timeout=5)
            ch.set_session_record(True).result(timeout=5)
            ch.set_metronome(False).result(timeout=5)
            ch.set_launch_quantization(1).result(timeout=5)

            ch.fire_scene(ARRANGEMENT[0][0]).result(timeout=5)
            time.sleep(0.1)
            ch.start_playback().result(timeout=5)

            elapsed_bars = 0
            for i, (slot, bars) in enumerate(ARRANGEMENT):
                if i == 0:
                    time.sleep(bars * bar_seconds)
                    elapsed_bars += bars
                    continue
                ch.fire_scene(slot).result(timeout=5)
                print(f"  bar {start_bar + elapsed_bars:>3d}: fired slot {slot} (hold {bars})")
                time.sleep(bars * bar_seconds)
                elapsed_bars += bars

            time.sleep(0.5)
            ch.stop_playback().result(timeout=5)
            ch.set_session_record(False).result(timeout=5)
            ch.set_record_mode(False).result(timeout=5)

        ch.set_launch_quantization(8).result(timeout=5)
        total_arr_bars = num_takes * total_bars + (num_takes - 1) * TAKE_GAP_BARS
        print(f"\nARRANGEMENT COMPLETE — {num_takes} take(s), {total_arr_bars} bars / ~{total_arr_bars * bar_seconds / 60:.1f} min")
        print("Open Arrangement View. Save As to checkpoint a take you like.")
    finally:
        ch.stop()


if __name__ == "__main__":
    import sys
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    main(num_takes=n)
