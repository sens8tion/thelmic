"""One-shot script: dress the existing ragga_v1 session with proper dancehall flesh.

Does the following on the running Live (does NOT touch session bindings on disk):
  1. STAB (T5):    replace Operator with Selectah Kit.adg  → chromatic stab voice
                    (Em chord MIDI at 64/67/71 → tuned ragga organ stabs)
  2. HAMMOND new:  add new MIDI track, load 'Wah Synth Organ.adg' from Sounds
                    library, write sustained Em / Am chord clips for dub scenes
  3. PAD (T6):     replace slot-0 audio with RP_SK_87 (87 BPM native dub organ)
                    → fixes the ugly downspeed warp on the 100 bpm guitar pad
  4. VOX (T7):     replace Simpler sample with dv_vocal_rasta (rasta toaster)
  5. FX (T8):      replace slot-0 audio with AA_Dub_Siren_F (no-warp one-shot)
  6. DRUMS (T0):   replace RAGGAJUNGLE clip with a programmatic rolling
                    ragga fill — kick rolls + ghost-snare flurries + 32nd
                    hat carpet + crash splash entry
  7. Set warp modes on the swapped audio clips (Beats for organ loop,
     Re-Pitch for vocal one-shot)
  8. Audition all 4 scenes
"""
from __future__ import annotations
import os, time
os.environ.setdefault('LIVE_CHANNEL_ENABLED', '1')

from thelmic.live_channel import LiveChannel


# ---- track indices (matches current Live session) -----------------------
T_DRUMS = 0
T_BREAK = 1                  # T2 is an orphan we ignore
T_SUB   = 3
T_BASS  = 4
T_STAB  = 5
T_PAD   = 6
T_VOX   = 7
T_FX    = 8
# Scene indices for ragga arrangement
S_DUB_IN, S_STEPPER, S_RAGGAJUNGLE, S_DUBOUT = 0, 1, 2, 3

# Ragga scene clip length
CLIP_LEN = 16.0      # 4 bars

SPLICE_DIR = "user_library/Samples/Splice"


# ---- rolling ragga fill drum pattern ------------------------------------
# Amen-break-style rolling fill: kick rolls, ghost snares, 32nd hat carpet,
# crash splash on bar 1.
KICK, SNARE, HAT_C, HAT_O, CRASH = 36, 38, 42, 46, 49

def rolling_ragga_fill() -> list[dict]:
    notes = []
    # crash splash on the 1
    notes.append({"pitch": CRASH, "time": 0.0, "duration": 1.5, "velocity": 110})
    # 32nd-note closed hats throughout — the rolling carpet
    for s in range(64):  # 64 x 32nd notes = 16 beats
        v = 75 if s % 2 == 0 else 55
        if s % 8 == 0: v += 10   # accent every 8th
        notes.append({"pitch": HAT_C, "time": s * 0.25, "duration": 0.0625, "velocity": v})
    # rolling kicks: vary off-grid each bar
    kick_grid = [
        # bar 0 — establishment
        (0.0, 115), (2.5, 100),
        # bar 1 — push
        (4.0, 110), (5.75, 95), (6.5, 105),
        # bar 2 — break
        (8.0, 110), (10.25, 100), (11.5, 95),
        # bar 3 — kick roll into next
        (12.0, 115), (13.5, 105), (13.875, 100), (14.25, 95), (14.625, 90),
    ]
    for t, v in kick_grid:
        notes.append({"pitch": KICK, "time": t, "duration": 0.25, "velocity": v})
    # ghost-snare flurries — busiest in bars 1 and 3
    snare_grid = [
        (1.0, 112), (1.75, 65), (2.0, 100),  # bar 0: snare on 2, ghost, snare on 3
        (3.5, 80),                            # tail ghost
        (5.0, 110), (5.5, 70), (6.25, 95),   # bar 1: rolling
        (7.0, 105), (7.625, 75), (7.875, 70),
        (9.0, 110), (10.5, 95),               # bar 2
        (12.5, 100), (13.0, 110),             # bar 3: lead-in
        (14.0, 105), (14.75, 75), (15.0, 95), (15.5, 110),  # the roll-out
    ]
    for t, v in snare_grid:
        notes.append({"pitch": SNARE, "time": t, "duration": 0.125, "velocity": v})
    # open hats on the &-of-4 in each bar — the "breath"
    for bar in (0, 1, 2):
        notes.append({"pitch": HAT_O, "time": bar * 4 + 3.5, "duration": 0.5, "velocity": 90})
    return notes


# ---- HAMMOND chord pattern: sustained Em / Am chord movement -----------
EM = (52, 55, 59)     # E3 G3 B3
AM = (57, 60, 64)     # A3 C4 E4

def hammond_dub_in() -> list[dict]:
    """Held Em chord across the bar with one Am pivot at bar 3."""
    notes = []
    # bars 0..2 hold Em
    for p in EM:
        notes.append({"pitch": p, "time": 0.0,  "duration": 8.0, "velocity": 70})
        notes.append({"pitch": p, "time": 8.0,  "duration": 4.0, "velocity": 75})
    # bar 3 → Am pivot for movement
    for p in AM:
        notes.append({"pitch": p, "time": 12.0, "duration": 4.0, "velocity": 80})
    return notes


def hammond_stepper() -> list[dict]:
    """Held Em/Am alternating per 2 bars — supports the skank rather than
    competing with it."""
    notes = []
    for p in EM:
        notes.append({"pitch": p, "time": 0.0, "duration": 7.5, "velocity": 65})
    for p in AM:
        notes.append({"pitch": p, "time": 8.0, "duration": 7.5, "velocity": 70})
    return notes


def hammond_dubout() -> list[dict]:
    """Long held chord with Leslie wash — one chord across all 4 bars,
    swelling. Single voicing for the bloom."""
    notes = []
    for p in EM:
        notes.append({"pitch": p, "time": 0.0, "duration": 16.0, "velocity": 85})
    return notes


# ---- main build ---------------------------------------------------------

def main() -> None:
    ch = LiveChannel(); ch.start(); time.sleep(0.6)
    try:
        info = ch.get_session_info().result(timeout=5)
        print(f'tempo={info.get("tempo")}  tracks={info.get("track_count")}')

        # 1. STAB ← Selectah Kit (replaces Operator on T5)
        print('\n--- 1. STAB ← Selectah Kit ---')
        try:
            ch.load_item_at_path(T_STAB, 'drums', 'Selectah Kit.adg').result(timeout=20)
            print('  loaded Selectah Kit on STAB')
            time.sleep(0.8)
        except Exception as e:
            print(f'  STAB fail: {e}')

        # 2. HAMMOND track — create after FX
        print('\n--- 2. HAMMOND track ---')
        info = ch.get_session_info().result(timeout=5)
        ham_idx = info.get('track_count', 9)
        try:
            ch.create_midi_track(ham_idx).result(timeout=10); time.sleep(0.4)
            ch.set_track_name(ham_idx, 'HAMMOND').result(timeout=5); time.sleep(0.2)
            # Load Wah Synth Organ from Sounds/Synth Keys
            try:
                ch.load_item_at_path(ham_idx, 'sounds/Synth Keys', 'Wah Synth Organ.adg').result(timeout=20)
                print('  loaded Wah Synth Organ on HAMMOND')
            except Exception:
                # fall back to Mad Farfisa from Bass folder (Farfisa = the reggae organ)
                ch.load_item_at_path(ham_idx, 'sounds/Bass', 'Mad Farfisa.adv').result(timeout=20)
                print('  fallback: loaded Mad Farfisa on HAMMOND')
            time.sleep(0.8)

            # Write sustained chord clips
            for slot, name, fn in [
                (S_DUB_IN, 'DUB_IN', hammond_dub_in),
                (S_STEPPER, 'STEPPER', hammond_stepper),
                (S_DUBOUT, 'DUBOUT', hammond_dubout),
            ]:
                ch.create_clip(ham_idx, slot, CLIP_LEN).result(timeout=10); time.sleep(0.1)
                ch.add_notes_to_clip(ham_idx, slot, fn()).result(timeout=10); time.sleep(0.1)
                ch.set_clip_name(ham_idx, slot, name).result(timeout=5); time.sleep(0.1)
                print(f'  HAMMOND {name}: {len(fn())} notes')
        except Exception as e:
            print(f'  HAMMOND fail: {e}')

        # 3. PAD slot 0 ← RP_SK_87_Keys_organ_feeler_G  (native 87 bpm dub organ)
        print('\n--- 3. PAD ← native 87 bpm dub organ ---')
        try:
            # clear existing, then load
            for slot in range(4):
                try: ch.clear_clip(T_PAD, slot).result(timeout=3); time.sleep(0.05)
                except Exception: pass
            ch.load_audio_to_slot(T_PAD, 0, SPLICE_DIR,
                                   'RP_SK_87_Keys_organ_feeler_G.wav').result(timeout=20)
            time.sleep(0.4)
            # warp mode 6 = Complex Pro (best for sustained tonal content)
            try:
                ch.set_clip_warp(T_PAD, 0, warping=True, warp_mode=6).result(timeout=5)
            except Exception: pass
            # duplicate to other scenes
            for tgt in (1, 2, 3):
                ch.duplicate_clip(T_PAD, 0, tgt).result(timeout=10); time.sleep(0.1)
            print('  PAD reloaded; duplicated to scenes 1..3')
        except Exception as e:
            print(f'  PAD fail: {e}')

        # 4. VOX Simpler ← dv_vocal_rasta
        print('\n--- 4. VOX ← dv_vocal_rasta ---')
        try:
            ch.load_item_at_path(T_VOX, SPLICE_DIR,
                                  'dv_vocal_rasta.wav').result(timeout=20)
            time.sleep(0.5)
            print('  VOX Simpler reloaded with rasta toast')
        except Exception as e:
            print(f'  VOX fail: {e}')

        # 5. FX slot 0 ← AA_Dub_Siren_F
        print('\n--- 5. FX ← AA_Dub_Siren_F ---')
        try:
            for slot in range(4):
                try: ch.clear_clip(T_FX, slot).result(timeout=3); time.sleep(0.05)
                except Exception: pass
            ch.load_audio_to_slot(T_FX, 0, SPLICE_DIR,
                                   'AA_Dub_Siren_F.wav').result(timeout=20)
            time.sleep(0.4)
            try:
                ch.set_clip_warp(T_FX, 0, warping=False).result(timeout=5)  # one-shot, no warp
            except Exception: pass
            # dupe into scenes that use FX
            for tgt in (S_RAGGAJUNGLE, S_DUBOUT, S_DUB_IN):
                ch.duplicate_clip(T_FX, 0, tgt).result(timeout=10); time.sleep(0.1)
            print('  FX reloaded with dub siren')
        except Exception as e:
            print(f'  FX fail: {e}')

        # 6. DRUMS RAGGAJUNGLE clip ← rolling ragga fill
        print('\n--- 6. DRUMS RAGGAJUNGLE ← rolling ragga fill ---')
        try:
            ch.clear_clip(T_DRUMS, S_RAGGAJUNGLE).result(timeout=5); time.sleep(0.1)
            ch.create_clip(T_DRUMS, S_RAGGAJUNGLE, CLIP_LEN).result(timeout=10); time.sleep(0.1)
            notes = rolling_ragga_fill()
            ch.add_notes_to_clip(T_DRUMS, S_RAGGAJUNGLE, notes).result(timeout=10); time.sleep(0.1)
            ch.set_clip_name(T_DRUMS, S_RAGGAJUNGLE, 'RAGGAJUNGLE_ROLL').result(timeout=5)
            print(f'  rolling fill: {len(notes)} notes')
        except Exception as e:
            print(f'  rolling fill fail: {e}')

        # 7. Audition all 4 scenes
        print('\n--- 7. audition ---')
        ch.stop_all_clips().result(timeout=3); time.sleep(0.3)
        # at 87 bpm, 16 beats = 11.0s per scene
        SECS = 11.5
        SCENE_NAMES = ['DUB_IN', 'STEPPER', 'RAGGAJUNGLE_ROLL', 'DUBOUT']
        for i, n in enumerate(SCENE_NAMES):
            print(f'  fire {i} {n}')
            ch.fire_scene(i).result(timeout=3)
            time.sleep(SECS)
        ch.stop_all_clips().result(timeout=3)
        print('--- done ---')
    finally:
        ch.stop()


if __name__ == '__main__':
    main()
