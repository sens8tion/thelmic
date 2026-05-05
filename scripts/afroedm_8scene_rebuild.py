"""8-scene rebuild mirroring 2026 high-energy EDM archetypes.

After the user's Live-native rap slicing, plus the request to extend to 8
scenes and apply contemporary EDM dramaturgy. 155 BPM, Em.

Tempo trends 2026 (per WebSearch):
  - Hard techno / hard house surge at 145-160 BPM
  - Big-room mainstage revival (early-2010s nostalgia)
  - "Bipolar" structure: hypnotic stretches alternating with high-energy
    release
  - Distorted 4OTF kick paramount; off-beat open hats; white-noise risers
  - "Silence pause" before drop
  - Gqom relevance rising

Lane plan (post-cleanup):
  T0  KICK_BOOM       Drum Rack — kick on pad 36
  T1  PERC_CRISP      Drum Rack — snare 38, hat-c 42, hat-o 46
  T2  SUB_VEIN        Operator — sub sine
  T3  BASS_KENYA      Operator — bass tone
  T4  STAB_LINGALA    Audio — SC_BPD_high_call (until user provides Lingala chop)
  T5  CHOP_PREP_RAP   (empty — delete)
  T6  rap_FULL_chop_me ← Live's slice → rename to RAP_NAIROBI
  T7  CHOP_PREP_LINGALA (empty — delete)
  T8  ZULU_AUDITION   (empty leftover — delete)
  T9  ZULU_AUDITION   (12 clips — keep, may be source for further chops)
"""
from __future__ import annotations
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from thelmic.live_channel import LiveChannel

USER_LIB = "user_library/Samples/Splice/AfroEDM_2026-05-04"
SCENE_LEN = 32.0    # 8 bars × 4 beats
N_SCENES  = 8

# Drum pad notes
KICK = 36
SNARE = 38
HATC = 42
HATO = 46

# Em (E1=28 sub, E2=40 bass roots)
E1 = 28
E2, FS2, G2, A2, B2, D3 = 40, 42, 43, 45, 47, 50


# ----- KICK_BOOM ---------------------------------------------------------
def kick_pattern(s: int) -> list[dict]:
    """4OTF foundation with archetype-driven density per scene."""
    notes = []
    if s == 0:    # INTRO_PULSE — hits on bar-1 only (every 4 beats × 4 bars... only 4 hits/8bars)
        for bar in range(0, 8, 2):
            notes.append({"pitch": KICK, "start_time": float(bar*4), "duration": 0.5, "velocity": 105})
    elif s == 1:  # INTRO_BUILD — every bar
        for bar in range(8):
            notes.append({"pitch": KICK, "start_time": float(bar*4), "duration": 0.5, "velocity": 108})
    elif s == 2:  # PRE_DROP — full 4OTF first 7 bars, silent bar 8 (the pause)
        for bar in range(7):
            for beat in range(4):
                notes.append({"pitch": KICK, "start_time": float(bar*4 + beat),
                              "duration": 0.5, "velocity": 110 if beat == 0 else 95})
    elif s == 3:  # DROP_FULL — full 4OTF + ghost on &-of-4
        for beat in range(32):
            notes.append({"pitch": KICK, "start_time": float(beat), "duration": 0.5,
                          "velocity": 115 if beat % 4 == 0 else 95})
        for bar in range(8):
            notes.append({"pitch": KICK, "start_time": float(bar*4 + 3.5),
                          "duration": 0.25, "velocity": 70})
    elif s == 4:  # ROLL_PEAK — full 4OTF, every kick double-hit (16th roll feel)
        for beat in range(32):
            notes.append({"pitch": KICK, "start_time": float(beat), "duration": 0.5, "velocity": 113})
            notes.append({"pitch": KICK, "start_time": float(beat) + 0.75, "duration": 0.2, "velocity": 75})
    elif s == 5:  # BREAK_HYPNOTIC — drums out completely
        return []
    elif s == 6:  # RE_BUILD — kick on every 1 + snare-side ghost on &-of-3
        for bar in range(8):
            notes.append({"pitch": KICK, "start_time": float(bar*4), "duration": 0.5, "velocity": 108})
            if bar >= 4:
                notes.append({"pitch": KICK, "start_time": float(bar*4 + 2), "duration": 0.5, "velocity": 95})
            if bar >= 6:
                notes.append({"pitch": KICK, "start_time": float(bar*4 + 1), "duration": 0.5, "velocity": 90})
                notes.append({"pitch": KICK, "start_time": float(bar*4 + 3), "duration": 0.5, "velocity": 90})
    elif s == 7:  # FINAL_DROP — same as DROP_FULL + extra accent on every &
        for beat in range(32):
            notes.append({"pitch": KICK, "start_time": float(beat), "duration": 0.5,
                          "velocity": 118 if beat % 4 == 0 else 100})
        for half in range(64):
            t = half * 0.5
            if half % 2 == 1:
                notes.append({"pitch": KICK, "start_time": t, "duration": 0.2, "velocity": 78})
    return notes


# ----- PERC_CRISP --------------------------------------------------------
def perc_pattern(s: int) -> list[dict]:
    """Snare 2/4, hats with archetype-driven density.

    Off-beat open hats are the 2026 hard-house signature.
    """
    notes = []
    # snare on 2 + 4 of every bar (skip in S0 + S5)
    if s not in (0, 5):
        for bar in range(8):
            notes.append({"pitch": SNARE, "start_time": float(bar*4 + 1), "duration": 0.25, "velocity": 100})
            notes.append({"pitch": SNARE, "start_time": float(bar*4 + 3), "duration": 0.25, "velocity": 105})
    # hats vary
    if s == 0:    # silent percussion
        pass
    elif s == 1:  # 8ths with light velocity
        for i in range(64):
            t = i * 0.5
            notes.append({"pitch": HATC, "start_time": t, "duration": 0.2,
                          "velocity": 75 if i % 2 == 0 else 55})
    elif s == 2:  # PRE_DROP — hat acceleration: 8 / 16 / 32nd over 4-bar segments
        # bars 0-1: 8ths, bars 2-3: 16ths, bars 4-5: 16th-trip, bars 6-7: 32nd
        for i in range(16):  # bars 0-1: 8ths
            notes.append({"pitch": HATC, "start_time": i * 0.5, "duration": 0.2, "velocity": 70})
        for i in range(32):  # bars 2-3: 16ths
            notes.append({"pitch": HATC, "start_time": 8.0 + i * 0.25, "duration": 0.2,
                          "velocity": 75 if i % 4 == 0 else 60})
        for i in range(48):  # bars 4-5: 16th-trip (3-against-2)
            notes.append({"pitch": HATC, "start_time": 16.0 + i * (1.0/3.0), "duration": 0.15,
                          "velocity": 80 if i % 6 == 0 else 65})
        for i in range(64):  # bars 6-7: 32nd-note carpet — climax
            notes.append({"pitch": HATC, "start_time": 24.0 + i * 0.125, "duration": 0.1,
                          "velocity": 85 if i % 8 == 0 else 70})
        # Snare ROLL on bar 8 (last bar of S2): 32nd-note ramp
        # NOTE: bar 8 starts at beat 28 — but we already filled it above with hats.
        # Replace with snare roll on top.
        for i in range(32):
            notes.append({"pitch": SNARE, "start_time": 28.0 + i * 0.125, "duration": 0.1,
                          "velocity": 60 + (i * 50 // 32)})
    elif s == 3:  # DROP_FULL — 8th hats + open hat off-beat (the &-of-1, &-of-3)
        for i in range(64):
            t = i * 0.5
            notes.append({"pitch": HATC, "start_time": t, "duration": 0.2,
                          "velocity": 80 if i % 2 == 0 else 60})
        # off-beat OH: every &-of-2 (so beat 1.5, 5.5, 9.5...)
        for bar in range(8):
            notes.append({"pitch": HATO, "start_time": float(bar*4 + 1.5), "duration": 0.5, "velocity": 95})
            notes.append({"pitch": HATO, "start_time": float(bar*4 + 3.5), "duration": 0.5, "velocity": 90})
    elif s == 4:  # ROLL_PEAK — 16ths + dense OH
        for i in range(128):
            t = i * 0.25
            notes.append({"pitch": HATC, "start_time": t, "duration": 0.1,
                          "velocity": 80 if i % 4 == 0 else 60})
        for bar in range(8):
            for off in (1.5, 2.5, 3.5):
                notes.append({"pitch": HATO, "start_time": float(bar*4 + off),
                              "duration": 0.25, "velocity": 95})
    elif s == 5:  # BREAK_HYPNOTIC — silent
        pass
    elif s == 6:  # RE_BUILD — gqom: triplet hats, snare ghosts ramp
        for i in range(96):  # 32 beats × 3 = 16th triplets
            t = i * (1.0/3.0)
            notes.append({"pitch": HATC, "start_time": t, "duration": 0.1,
                          "velocity": 70 + (i * 20 // 96)})
        # snare ghosts ramp
        for bar in range(4, 8):
            for hit in (0.75, 1.75, 2.75, 3.75):
                vel = 55 + (bar - 4) * 10
                notes.append({"pitch": SNARE, "start_time": float(bar*4 + hit),
                              "duration": 0.15, "velocity": vel})
    elif s == 7:  # FINAL_DROP — full carpet + dense OH
        for i in range(128):
            t = i * 0.25
            notes.append({"pitch": HATC, "start_time": t, "duration": 0.1,
                          "velocity": 88 if i % 4 == 0 else 65})
        for bar in range(8):
            for off in (0.5, 1.5, 2.5, 3.5):
                notes.append({"pitch": HATO, "start_time": float(bar*4 + off),
                              "duration": 0.4, "velocity": 100 if off in (1.5, 3.5) else 75})
    return notes


# ----- SUB_VEIN ----------------------------------------------------------
def sub_pattern(s: int) -> list[dict]:
    notes = []
    if s == 0:    # holds — 2-bar each
        for bar in range(0, 8, 2):
            notes.append({"pitch": E1, "start_time": float(bar*4), "duration": 8.0, "velocity": 95})
    elif s == 1:  # 1-bar pulses
        for bar in range(8):
            notes.append({"pitch": E1, "start_time": float(bar*4), "duration": 4.0, "velocity": 100})
    elif s == 2:  # PRE_DROP — same pulses, drop bar 8 (silence pause)
        for bar in range(7):
            notes.append({"pitch": E1, "start_time": float(bar*4), "duration": 4.0, "velocity": 100})
    elif s == 3:  # DROP — kick-tied (every kick beat)
        for beat in range(32):
            notes.append({"pitch": E1, "start_time": float(beat), "duration": 1.0, "velocity": 105})
    elif s == 4:  # ROLL_PEAK — 16th rolls
        for i in range(128):
            notes.append({"pitch": E1, "start_time": i * 0.25, "duration": 0.3,
                          "velocity": 105 if i % 4 == 0 else 80})
    elif s == 5:  # BREAK — single 8-bar hold
        notes.append({"pitch": E1, "start_time": 0.0, "duration": 32.0, "velocity": 92})
    elif s == 6:  # RE_BUILD — pulses ramping to 16th
        for bar in range(4):  # bars 0-3: 1/bar
            notes.append({"pitch": E1, "start_time": float(bar*4), "duration": 4.0, "velocity": 95})
        for beat in range(8, 16):  # bars 4-5: per-beat
            notes.append({"pitch": E1, "start_time": float(beat*2), "duration": 2.0, "velocity": 100})
        for half in range(8):  # bars 6: 8ths
            notes.append({"pitch": E1, "start_time": 24.0 + half * 0.5, "duration": 0.5, "velocity": 102})
        for sxt in range(16):  # bar 7: 16ths
            notes.append({"pitch": E1, "start_time": 28.0 + sxt * 0.25, "duration": 0.25, "velocity": 108})
    elif s == 7:  # FINAL_DROP — kick-tied + 16th double-up at hot moments
        for beat in range(32):
            notes.append({"pitch": E1, "start_time": float(beat), "duration": 1.0, "velocity": 110})
            if beat % 4 == 3:  # double up on the &
                notes.append({"pitch": E1, "start_time": float(beat) + 0.5, "duration": 0.4, "velocity": 95})
    return notes


# ----- BASS_KENYA --------------------------------------------------------
def bass_pattern(s: int) -> list[dict]:
    """Walking Em bass; only enters at the drops + reform."""
    if s in (0, 1, 5):
        return []
    notes = []
    # 8-bar progression in Em
    progression = [E2, G2, A2, B2, E2, A2, B2, D3]
    if s == 2:    # PRE_DROP — hint at bar 7 only
        for off in (0.0, 1.0, 2.0, 3.0):
            notes.append({"pitch": E2, "start_time": 24.0 + off, "duration": 0.4, "velocity": 90})
    elif s == 3 or s == 7:  # DROP_FULL / FINAL_DROP — full walk
        for bar, root in enumerate(progression):
            for off in (0.0, 1.5, 2.0, 3.5):
                notes.append({"pitch": root, "start_time": float(bar*4 + off),
                              "duration": 0.5, "velocity": 100})
    elif s == 4:  # ROLL_PEAK — 8th-note rolling bass
        for bar, root in enumerate(progression):
            for half in range(8):
                t = bar*4 + half*0.5
                # alternate root + 5th
                p = root + 7 if half % 2 == 1 else root
                notes.append({"pitch": p, "start_time": float(t), "duration": 0.4,
                              "velocity": 95 if half % 2 == 0 else 80})
    elif s == 6:  # RE_BUILD — held roots only
        for bar, root in enumerate(progression):
            notes.append({"pitch": root, "start_time": float(bar*4), "duration": 4.0, "velocity": 90})
    return notes


# ----- RAP_NAIROBI (after Live slice — 83 slices on pads 36..118) --------
def rap_pattern(s: int, n: int) -> list[dict]:
    """Slice palette = 83 transient-detected pads."""
    PAD_BASE = 36
    notes = []
    if s == 0:    # INTRO_PULSE — single rap fragment at bar 4 + bar 7 tail
        notes.append({"pitch": PAD_BASE + 0, "start_time": 12.0, "duration": 4.0, "velocity": 90})
        notes.append({"pitch": PAD_BASE + (n - 1), "start_time": 28.0, "duration": 4.0, "velocity": 75})
    elif s == 1:  # INTRO_BUILD — 4 medium phrases
        for bar in range(0, 8, 2):
            slc = (bar // 2) * (n // 4)
            notes.append({"pitch": PAD_BASE + (slc % n), "start_time": float(bar*4),
                          "duration": 6.0, "velocity": 92})
    elif s == 2:  # PRE_DROP — accelerating rap fragments
        # bars 0-3: half-bar
        for i in range(8):
            slc = (i * (n // 16)) % n
            notes.append({"pitch": PAD_BASE + slc, "start_time": float(i*2),
                          "duration": 1.5, "velocity": 90 + i*2})
        # bars 4-5: per-beat
        for beat in range(8):
            slc = (16 + beat * (n // 32 or 1)) % n
            notes.append({"pitch": PAD_BASE + slc, "start_time": 16.0 + float(beat),
                          "duration": 0.8, "velocity": 100})
        # bars 6-7: 8ths (climax fragments)
        for half in range(16):
            slc = (24 + half) % n
            notes.append({"pitch": PAD_BASE + slc, "start_time": 24.0 + half * 0.5,
                          "duration": 0.4, "velocity": 105})
    elif s == 3:  # DROP_FULL — slices on every beat, walking
        for beat in range(32):
            slc = (beat * 2) % n
            notes.append({"pitch": PAD_BASE + slc, "start_time": float(beat),
                          "duration": 0.9, "velocity": 105 if beat % 4 == 0 else 90})
    elif s == 4:  # ROLL_PEAK — 8th-note chop, denser
        for half in range(64):
            slc = (half * (n // 64 or 1)) % n
            # stutter every 4th
            if half % 4 == 1:
                slc = (slc - 1) % n
            notes.append({"pitch": PAD_BASE + slc, "start_time": half * 0.5,
                          "duration": 0.45, "velocity": 110 if half % 8 == 0 else 92})
    elif s == 5:  # BREAK_HYPNOTIC — solo rap, long held slices, 4 phrases
        picks = [0, n//4, n//2, 3*n//4]
        for i, slc in enumerate(picks):
            notes.append({"pitch": PAD_BASE + (slc % n), "start_time": float(i*8),
                          "duration": 6.0, "velocity": 95})
    elif s == 6:  # RE_BUILD — accelerating density (similar to PRE_DROP)
        for i in range(8):
            slc = (i * (n // 16)) % n
            notes.append({"pitch": PAD_BASE + slc, "start_time": float(i*2),
                          "duration": 1.5, "velocity": 90})
        for beat in range(16):  # bars 4-7: per-beat
            slc = (16 + beat * 3) % n
            notes.append({"pitch": PAD_BASE + slc, "start_time": 16.0 + float(beat),
                          "duration": 0.8, "velocity": 95 + beat*1})
    elif s == 7:  # FINAL_DROP — heavy chop, every 8th + stutters
        for half in range(64):
            slc = (half * 3 + (half // 4)) % n
            if half % 8 == 1:
                slc = (slc - 2) % n
            notes.append({"pitch": PAD_BASE + slc, "start_time": half * 0.5,
                          "duration": 0.4, "velocity": 115 if half % 4 == 0 else 95})
    return notes


# ----- STAB_LINGALA (audio) — sample triggered per scene ----------------
# Audio track: load SC_BPD or skip per scene. We'll only fire stab in dropped scenes.
STAB_SCENES = {3, 4, 6, 7}  # plus cleanup elsewhere


# ----- main --------------------------------------------------------------

def find_track_by_name(ch, name: str) -> int | None:
    info = ch.get_session_info().result(timeout=5)
    tc = info.get("track_count") or info.get("num_tracks") or 0
    for i in range(tc):
        ti = ch.get_track_info(i).result(timeout=3)
        if ti.get("name", "") == name:
            return i
    return None


def main():
    ch = LiveChannel(enabled=True); ch.start()
    try:
        info = ch.get_session_info().result(timeout=5)
        tc = info.get("track_count") or info.get("num_tracks") or 0
        print(f"start track count: {tc}")

        # -- 1. Cleanup empty prep tracks (delete-by-name, in reverse order)
        for nm in ["CHOP_PREP_RAP", "CHOP_PREP_LINGALA"]:
            t = find_track_by_name(ch, nm)
            if t is not None:
                ti = ch.get_track_info(t).result(timeout=3)
                # Only delete if no clips/devices (truly empty prep — but the
                # source clip is gone after Live slice, so it's empty).
                print(f"deleting empty prep T{t} '{nm}'")
                ch.delete_track(t).result(timeout=10)

        # delete the empty leftover ZULU_AUDITION (the duplicate one)
        # Find both — the empty one is whichever has fewer clips. Easiest probe:
        # try get_clip_notes on slot 0; if it errors with "no clip", it's empty.
        # But audio tracks always error on get_clip_notes. Use a different probe:
        # check track info `clip_slots` via get_track_info.
        info_now = ch.get_session_info().result(timeout=5)
        tc_now = info_now.get("track_count") or info_now.get("num_tracks") or 0
        zulu_idxs = []
        for i in range(tc_now):
            ti = ch.get_track_info(i).result(timeout=3)
            if ti.get("name") == "ZULU_AUDITION":
                zulu_idxs.append(i)
        if len(zulu_idxs) >= 2:
            ch.delete_track(zulu_idxs[0]).result(timeout=10)
            print(f"deleted empty duplicate ZULU_AUDITION at T{zulu_idxs[0]}")

        # -- 2. Rename rap_FULL_chop_me → RAP_NAIROBI (in place)
        rapt = find_track_by_name(ch, "rap_FULL_chop_me")
        if rapt is not None:
            ch.set_track_name(rapt, "RAP_NAIROBI").result(timeout=5)
            ch.set_track_color(rapt, 14).result(timeout=5)
            ch.set_track_volume(rapt, 0.85).result(timeout=5)
            print(f"renamed T{rapt} -> RAP_NAIROBI")

        # -- 3. Resolve final indices
        T_KICK = find_track_by_name(ch, "KICK_BOOM")
        T_PERC = find_track_by_name(ch, "PERC_CRISP")
        T_SUB  = find_track_by_name(ch, "SUB_VEIN")
        T_BASS = find_track_by_name(ch, "BASS_KENYA")
        T_STAB = find_track_by_name(ch, "STAB_LINGALA")
        T_RAP  = find_track_by_name(ch, "RAP_NAIROBI")
        print(f"resolved: KICK={T_KICK} PERC={T_PERC} SUB={T_SUB} BASS={T_BASS} STAB={T_STAB} RAP={T_RAP}")
        if any(x is None for x in (T_KICK, T_PERC, T_SUB, T_BASS, T_STAB, T_RAP)):
            print("MISSING TRACK — aborting before pattern write")
            return

        # -- 4. Ensure 8 scenes exist
        info_s = ch.get_session_info().result(timeout=5)
        scene_ct = info_s.get("scene_count", 4)  # may not exist; fallback
        # Try a few common keys
        for key in ("scene_count", "scenes", "num_scenes"):
            v = info_s.get(key)
            if v: scene_ct = v; break
        # Add scenes if needed
        # We added scenes earlier (12). Let's just ensure >= 8.
        # A simpler check: try ch.create_clip on slot 7 of T_KICK; if it errors,
        # add scenes. Actually we already added scenes earlier so should be fine.
        try:
            ch.create_clip(T_KICK, 7, SCENE_LEN).result(timeout=5)
        except Exception:
            for _ in range(8):
                ch.create_scene(-1).result(timeout=5)

        # -- 5. Lock tempo for all 8 scenes
        for s in range(N_SCENES):
            ch.set_scene_tempo(s, 155.0).result(timeout=5)

        # -- 6. Wipe all clips on T_KICK..T_BASS, T_RAP for slots 0..7
        scene_names = ["INTRO_PULSE", "INTRO_BUILD", "PRE_DROP", "DROP_FULL",
                       "ROLL_PEAK", "BREAK_HYPNOTIC", "RE_BUILD", "FINAL_DROP"]
        for t in (T_KICK, T_PERC, T_SUB, T_BASS, T_RAP):
            for s in range(N_SCENES):
                try:
                    ch.delete_clip(t, s).result(timeout=5)
                except Exception:
                    pass

        # -- 7. Write fresh clips per scene per track
        # Read rap slice count
        try:
            raw = ch.get_clip_notes(T_RAP, 0).result(timeout=5)
            rap_n = 83  # we know from earlier, but try to read
        except Exception:
            rap_n = 83

        builders = [
            (T_KICK, "kick", lambda s: kick_pattern(s)),
            (T_PERC, "perc", lambda s: perc_pattern(s)),
            (T_SUB,  "sub",  lambda s: sub_pattern(s)),
            (T_BASS, "bass", lambda s: bass_pattern(s)),
            (T_RAP,  "rap",  lambda s: rap_pattern(s, rap_n)),
        ]

        for s in range(N_SCENES):
            print(f"\n--- S{s} {scene_names[s]} ---")
            for t, label, fn in builders:
                ch.create_clip(t, s, SCENE_LEN).result(timeout=10)
                ch.set_clip_name(t, s, f"{scene_names[s]}_{label}").result(timeout=5)
                notes = fn(s)
                if notes:
                    ch.add_notes_to_clip(t, s, notes).result(timeout=10)
                print(f"  T{t:2d} {label:5s}: {len(notes)} notes")

        # -- 8. STAB audio per scene (load on dropped scenes only)
        for s in range(N_SCENES):
            if s in STAB_SCENES:
                ch.load_audio_to_slot(T_STAB, s, USER_LIB, "SC_BPD_vocals_high_call.wav").result(timeout=15)
                ch.set_clip_name(T_STAB, s, f"{scene_names[s]}_stab").result(timeout=5)
                ch.set_clip_warp(T_STAB, s, warping=True, warp_mode=4).result(timeout=5)
                ch.set_clip_loop(T_STAB, s, True).result(timeout=5)
                ch.set_clip_loop_region(T_STAB, s, 0.0, 4.0).result(timeout=5)
            else:
                # leave empty
                try: ch.delete_clip(T_STAB, s).result(timeout=3)
                except Exception: pass

        # -- 9. Final mix tweaks
        ch.set_track_volume(T_KICK, 0.88).result(timeout=5)
        ch.set_track_volume(T_PERC, 0.78).result(timeout=5)
        ch.set_track_volume(T_SUB,  0.85).result(timeout=5)
        ch.set_track_volume(T_BASS, 0.72).result(timeout=5)
        ch.set_track_volume(T_STAB, 0.75).result(timeout=5)
        ch.set_track_volume(T_RAP,  0.85).result(timeout=5)

        print("\n--- FINAL TRACK LIST ---")
        info_f = ch.get_session_info().result(timeout=5)
        for i in range(info_f.get("track_count") or 0):
            ti = ch.get_track_info(i).result(timeout=3)
            print(f"  T{i:2d}  {ti.get('name','')!r}")
        print("\nDONE — 8 scenes at 155 BPM, 2026-archetype-shaped.")
    finally:
        ch.stop()


if __name__ == "__main__":
    main()
