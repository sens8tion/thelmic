"""Build the 6-lane × 4-scene afro-EDM session in Live.

Lane plan (track index → role):
  T0  KICK_BOOM      Drum Rack, 19_Kick on pad 36
  T1  PERC_CRISP     Drum Rack, snare 38 + hat-c 42 + hat-o 46
  T2  SUB_VEIN       Operator (default sine) — sustained Em sub
  T3  BASS_KENYA     Operator — walking Em bass
  T4  STAB_LINGALA   Audio — chops of SC_BPD_high_call + Lingala
  T5  RAP_NAIROBI    Audio — DS_VAH3_124_rap_dry chopped/warped

Scenes (8 bars / 32 beats each at 126 BPM, Em):
  S0  KISWAHILI_CALL    sub holds + sparse kick + rap fragment
  S1  PEMBA_BUILD       + perc 16ths + stab vocal
  S2  KILIMANJARO_DROP  full kit + bass walk + rap chops + stabs
  S3  RIFT_SOLO         drums out + sub hold + rap solo + stab tail
"""
from __future__ import annotations
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from thelmic.live_channel import LiveChannel

USER_LIB = "user_library/Samples/Splice/AfroEDM_2026-05-04"

KICK_PAD, SNARE_PAD, HATC_PAD, HATO_PAD = 36, 38, 42, 46

# Em scale (MIDI). E2=40 base for sub.
E1, E2, G2, A2, B2, D3, E3 = 28, 40, 43, 45, 47, 50, 52

T_KICK, T_PERC, T_SUB, T_BASS, T_STAB, T_RAP = 0, 1, 2, 3, 4, 5
TRACK_NAMES = {
    T_KICK: "KICK_BOOM",
    T_PERC: "PERC_CRISP",
    T_SUB:  "SUB_VEIN",
    T_BASS: "BASS_KENYA",
    T_STAB: "STAB_LINGALA",
    T_RAP:  "RAP_NAIROBI",
}

# ----- pattern builders ---------------------------------------------------

def kick_pattern(scene: int) -> list[dict]:
    """4OTF kick patterns. Scene 0 sparse, S1/S2 full, S3 drops out."""
    notes = []
    if scene == 0:
        beats = [0, 8, 16, 24]                          # bar-1s only (4 hits in 8 bars)
    elif scene == 1:
        beats = [b for b in range(0, 32) if b % 4 == 0] # full 4OTF
    elif scene == 2:
        beats = [b for b in range(0, 32) if b % 4 == 0] + [3.75, 11.75, 19.75, 27.75]  # +ghost
    else:                                                # S3 break — kick gone
        beats = []
    for b in beats:
        vel = 110 if (b % 4 == 0) else 70
        notes.append({"pitch": KICK_PAD, "start_time": float(b), "duration": 0.5, "velocity": vel})
    return notes


def perc_pattern(scene: int) -> list[dict]:
    """Snares on 2/4, hats vary."""
    notes = []
    if scene == 0:
        return []                                       # silence
    # snares 2 + 4 of every bar
    for bar in range(8):
        for hit in (1, 3):                              # beats 2 and 4 (0-indexed +1)
            notes.append({"pitch": SNARE_PAD, "start_time": float(bar*4 + hit + 1), "duration": 0.25, "velocity": 100})
    if scene >= 1:
        # 8th-note closed hats
        for i in range(64):                             # 32 beats × 2
            t = i * 0.5
            vel = 80 if (i % 2 == 0) else 60
            notes.append({"pitch": HATC_PAD, "start_time": t, "duration": 0.2, "velocity": vel})
    if scene == 2:
        # +open hats on the &-of-2 of every bar
        for bar in range(8):
            notes.append({"pitch": HATO_PAD, "start_time": float(bar*4 + 1.5), "duration": 0.5, "velocity": 90})
    if scene == 3:
        # break: just open hat on bar 8 beat 1 as "tail"
        notes.append({"pitch": HATO_PAD, "start_time": 28.0, "duration": 1.0, "velocity": 70})
    return notes


def sub_pattern(scene: int) -> list[dict]:
    """Sustained E1 sub. Length varies per scene."""
    notes = []
    if scene == 0:
        # 2-bar holds × 4 = 8 bars
        for bar in range(0, 8, 2):
            notes.append({"pitch": E1, "start_time": float(bar*4), "duration": 8.0, "velocity": 95})
    elif scene == 1:
        # 1-bar pulses on every 1
        for bar in range(8):
            notes.append({"pitch": E1, "start_time": float(bar*4), "duration": 4.0, "velocity": 100})
    elif scene == 2:
        # tied to kick: hits on every kick (every beat)
        for b in range(0, 32):
            notes.append({"pitch": E1, "start_time": float(b), "duration": 1.0, "velocity": 100})
    elif scene == 3:
        # one big hold across the full 8 bars
        notes.append({"pitch": E1, "start_time": 0.0, "duration": 32.0, "velocity": 90})
    return notes


def bass_pattern(scene: int) -> list[dict]:
    """Walking Em bass (E G A B / E A B D). One bar per chord, 8 bars."""
    if scene < 2:
        return []                                       # bass enters at S2
    progression = [E2, G2, A2, B2, E2, A2, B2, D3]      # 8 bars × 1 note/bar root
    notes = []
    for bar, root in enumerate(progression):
        # 1 + & + 3 + & rhythm — 4 hits per bar
        for off in (0.0, 1.5, 2.0, 3.5):
            notes.append({"pitch": root, "start_time": float(bar*4 + off), "duration": 0.5, "velocity": 100})
    if scene == 3:                                      # break: hold roots only
        notes = [{"pitch": E2, "start_time": float(bar*4), "duration": 4.0, "velocity": 90} for bar in range(8)]
    return notes


# ----- main ----------------------------------------------------------------

def main():
    ch = LiveChannel(enabled=True)
    ch.start()
    try:
        info = ch.get_session_info().result(timeout=5)
        existing = info.get("track_count") or info.get("num_tracks") or 0
        print(f"existing tracks: {existing} | tempo: {info.get('tempo')}")

        # Set tempo
        ch.set_tempo(126.0).result(timeout=5)

        # Create the 6 tracks we need (6 - existing). If existing >= 6, we just rename.
        # Default Live set has 2 MIDI + 2 Audio = 4 tracks. We want T0..T3 MIDI, T4..T5 audio.
        # Strategy: ensure at least 4 MIDI + 2 audio in the right order.
        # For simplicity assume a fresh empty set: create 4 MIDI then 2 audio.
        for _ in range(4):
            ch.create_midi_track(-1).result(timeout=5)
        for _ in range(2):
            ch.create_audio_track(-1).result(timeout=5)
        # If Live had defaults already, the new tracks land at the end. We'll work on the
        # last 6 indices.
        # Refetch track count
        info2 = ch.get_session_info().result(timeout=5)
        total = info2.get("track_count") or info2.get("num_tracks") or 0
        offset = total - 6
        print(f"total tracks now: {total} | using indices {offset}..{offset+5}")

        # Apply offset to track indices
        Tk = T_KICK + offset
        Tp = T_PERC + offset
        Ts = T_SUB  + offset
        Tb = T_BASS + offset
        Tx = T_STAB + offset
        Tr = T_RAP  + offset

        # Name tracks
        for local_idx, name in TRACK_NAMES.items():
            ch.set_track_name(local_idx + offset, name).result(timeout=5)

        # ---- INSTRUMENTS ----
        print("loading instruments...")
        # Drum Racks on KICK + PERC
        ch.load_device(Tk, "query:Synths#Drum%20Rack").result(timeout=20)
        ch.load_device(Tp, "query:Synths#Drum%20Rack").result(timeout=20)
        # Operators on SUB + BASS
        ch.load_device(Ts, "query:Synths#Operator").result(timeout=20)
        ch.load_device(Tb, "query:Synths#Operator").result(timeout=20)

        # ---- DRUM PADS ----
        print("loading drum pads...")
        ch.load_sample_to_pad(Tk, 0, KICK_PAD, USER_LIB, "19_Kick.wav").result(timeout=15)
        ch.load_sample_to_pad(Tp, 0, SNARE_PAD, USER_LIB, "JORDY_DAZZ_snare_smack.wav").result(timeout=15)
        ch.load_sample_to_pad(Tp, 0, HATC_PAD, USER_LIB, "pmt_clhat_coral_short.wav").result(timeout=15)
        ch.load_sample_to_pad(Tp, 0, HATO_PAD, USER_LIB, "Hihat_Open.wav").result(timeout=15)

        # ---- CLIPS PER SCENE ----
        scene_len = 32.0  # 8 bars × 4 beats
        print("writing MIDI clips...")
        for s in range(4):
            for track, builder in [
                (Tk, kick_pattern),
                (Tp, perc_pattern),
                (Ts, sub_pattern),
                (Tb, bass_pattern),
            ]:
                notes = builder(s)
                ch.create_clip(track, s, scene_len).result(timeout=10)
                ch.set_clip_name(track, s, f"S{s}").result(timeout=5)
                if notes:
                    ch.add_notes_to_clip(track, s, notes).result(timeout=10)
                print(f"  T{track} S{s}: {len(notes)} notes")

        # ---- AUDIO CLIPS ----
        print("loading audio clips...")
        # Stab — same chop in slots 1/2/3 (skip S0)
        for s in (1, 2, 3):
            ch.load_audio_to_slot(Tx, s, USER_LIB, "SC_BPD_vocals_high_call.wav").result(timeout=15)
            ch.set_clip_name(Tx, s, f"stab_S{s}").result(timeout=5)
            ch.set_clip_warp(Tx, s, warping=True, warp_mode=4).result(timeout=5)  # warp Complex Pro
            ch.set_clip_loop(Tx, s, True).result(timeout=5)
        # Rap — full long phrase in slots 0,2,3 (S1 = silence)
        for s in (0, 2, 3):
            ch.load_audio_to_slot(Tr, s, USER_LIB, "DS_VAH3_124_rap_dry.wav").result(timeout=15)
            ch.set_clip_name(Tr, s, f"rap_S{s}").result(timeout=5)
            ch.set_clip_warp(Tr, s, warping=True, warp_mode=4).result(timeout=5)
            ch.set_clip_loop(Tr, s, True).result(timeout=5)
            ch.set_clip_loop_region(Tr, s, 0.0, scene_len).result(timeout=5)

        # ---- MIX ----
        print("mixing...")
        ch.set_track_volume(Tk, 0.85).result(timeout=5)
        ch.set_track_volume(Tp, 0.78).result(timeout=5)
        ch.set_track_volume(Ts, 0.82).result(timeout=5)
        ch.set_track_volume(Tb, 0.72).result(timeout=5)
        ch.set_track_volume(Tx, 0.75).result(timeout=5)
        ch.set_track_volume(Tr, 0.85).result(timeout=5)

        # Track colors (subtle visual grouping)
        for t, c in [(Tk, 1), (Tp, 1), (Ts, 8), (Tb, 8), (Tx, 14), (Tr, 14)]:
            ch.set_track_color(t, c).result(timeout=5)

        print("\nDONE — fire scene 1 in Live to audition.")
        print("STATUS:", ch.status().as_dict())
    finally:
        ch.stop()


if __name__ == "__main__":
    main()
