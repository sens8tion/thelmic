"""Layer the hardcore extension scenes 12 / 13 / 14:

  Scene 12 AMEN_BREAKDOWN  amen + HOOVER drone + VOX call + ATMOS crowd low
  Scene 13 AMEN_REBUILD    amen + KICK_4OTF + HOOVER chord stabs + STAB rave
                            skank + GUITAR punctuations + VOX + ATMOS louder
  Scene 14 HARDCORE_FULL   BREAK amen + KICK_4OTF ghosted + HOOVER rave stabs
                            + STAB skank + GUITAR 4-on-floor + PUNK snare lift
                            + VOX + ATMOS

Avoids HARDCORE_KIT (T14) and BASS_AUDIO (T16) — user has hand-tuned those.
"""
from __future__ import annotations
import os, time
os.environ.setdefault('LIVE_CHANNEL_ENABLED', '1')

from thelmic.live_channel import LiveChannel

T_BREAK, T_STAB, T_PAD, T_VOX, T_FX = 1, 5, 6, 7, 8
T_HAMMOND, T_BREAK_RACK, T_ATMOS = 9, 11, 12
T_GUITAR, T_HOOVER, T_PUNK_KIT, T_KICK = 13, 15, 17, 18
T_BREAK_SLICES = 2   # the TSP_IHD_160 break sliced to MIDI (32 slices, pads 36-67)

CLIP_LEN = 16.0


def n(p, t, d, v):
    return {'pitch': int(p), 'start_time': float(t),
            'duration': float(d), 'velocity': float(v)}


def write(ch, ti, slot, notes, name):
    try: ch.clear_clip(ti, slot).result(timeout=3); time.sleep(0.05)
    except Exception: pass
    ch.create_clip(ti, slot, CLIP_LEN).result(timeout=10); time.sleep(0.05)
    if notes:
        ch.add_notes_to_clip(ti, slot, notes).result(timeout=10); time.sleep(0.05)
    ch.set_clip_name(ti, slot, name).result(timeout=5)


def dupe_atmos(ch, slot, gain):
    """Duplicate the rowdy_crowd from atmos slot 2 to <slot> with proper
    loop region and gain."""
    clips = ch.get_track_clips(T_ATMOS).result(timeout=3).get('clips', [])
    if any(c.get('slot') == slot for c in clips):
        return
    ch.duplicate_clip(T_ATMOS, 2, slot).result(timeout=10); time.sleep(0.1)
    ch.set_clip_loop_region(T_ATMOS, slot, 0.0, 16.0).result(timeout=3)
    ch.set_clip_loop(T_ATMOS, slot, True).result(timeout=3)
    ch.set_clip_warp(T_ATMOS, slot, warping=True, warp_mode=2).result(timeout=3)
    ch.set_clip_gain(T_ATMOS, slot, gain).result(timeout=3)
    ch.set_clip_name(T_ATMOS, slot, 'BBC_rowdy_crowd').result(timeout=3)


# ---- pattern generators ---------------------------------------------

def hoover_breakdown_drone():
    return [n(40, 0.0, 16.0, 95)]

def hoover_rebuild_stabs():
    PROG = [(40, 95), (45, 100), (47, 105), (45, 105)]
    notes = []
    for bar, (p, v) in enumerate(PROG):
        notes.append(n(p, bar * 4, 3.0, v))
        notes.append(n(p + 12, bar * 4 + 3.5, 0.5, v - 5))
    return notes

def hoover_full_hardcore():
    PROG = [(40, 47), (45, 47), (40, 47), (45, 47)]
    notes = []
    for bar, (root, fifth) in enumerate(PROG):
        b0 = bar * 4
        for off, vel in [(0.5, 100), (1.5, 110), (2.5, 100), (3.5, 110)]:
            notes.append(n(root, b0 + off, 0.3, vel))
        notes.append(n(fifth, b0 + 1.5, 0.3, 95))
        notes.append(n(fifth, b0 + 3.5, 0.3, 95))
    return notes

def stab_rave_chord_stabs():
    EM = (52, 55, 59); BM = (59, 62, 66)
    notes = []
    for bar in range(4):
        b0 = bar * 4
        chord = EM if bar % 2 == 0 else BM
        for off in (0.5, 1.5, 2.5, 3.5):
            for p in chord:
                notes.append(n(p, b0 + off, 0.18, 105))
    return notes

def guitar_punct():
    notes = []
    PADS = [36, 37, 38, 39]
    for bar in range(4):
        notes.append(n(PADS[bar % 4], bar * 4, 0.4, 118))
    for bar in (1, 3):
        notes.append(n(PADS[(bar + 1) % 4], bar * 4 + 3.5, 0.25, 105))
    return notes

def guitar_4_on_floor():
    notes = []
    PADS = [36, 37, 38, 39]
    for bar in range(4):
        for beat in range(4):
            notes.append(n(PADS[(bar + beat) % 4], bar * 4 + beat, 0.4, 115))
    return notes

def vox_breakdown_call():
    return [n(62, 0.0, 4.0, 110)]

def vox_rebuild_call():
    return [n(62, 0.0, 4.0, 110), n(62, 8.0, 4.0, 105)]

def vox_full():
    return [n(62, 0.0, 4.0, 115), n(62, 8.0, 4.0, 110)]

# ---- BREAK_SLICES patterns (32 slices on pads 36-67, 8th-note granularity) ----

def break_slices_breakdown_sparse():
    """Just slice 1 (kick) and slice 5 (snare) at slow rate — bones of the
    break peeking through during the breakdown."""
    notes = []
    for bar in range(4):
        b0 = bar * 4
        notes.append(n(36, b0 + 0.0, 0.5, 105))   # slice 1 = kick
        notes.append(n(40, b0 + 2.0, 0.5, 100))   # slice 5 = snare
    return notes


def break_slices_rebuild_pattern():
    """Half-time rearrangement — uses slices 1, 3, 5, 7 at the
    8th-note grid (every 0.5 beats). Familiar but not the original
    sequence; signals 'break is coming back'."""
    notes = []
    SEQ = [36, 38, 40, 42, 36, 38, 40, 42]  # slices 1, 3, 5, 7 repeating
    for bar in range(4):
        b0 = bar * 4
        for s, slc in enumerate(SEQ):
            t = b0 + s * 0.5
            v = 100 if s % 2 == 0 else 88
            notes.append(n(slc, t, 0.4, v))
    return notes


def break_slices_scrambled():
    """Hardcore scramble — re-sequence slices in a non-original order
    on every 8th, with double-hits on accent positions. Classic jungle
    chop move. Pseudo-random but deterministic via index math."""
    # 32 8th-positions in a 16-beat clip
    notes = []
    # chosen permutation order (maps each 8th step to a slice pad 36-50ish)
    PERM = [36, 38, 40, 42, 36, 44, 41, 38,
            36, 39, 47, 42, 41, 36, 50, 38,
            36, 40, 38, 45, 36, 42, 41, 49,
            44, 38, 36, 50, 38, 42, 41, 36]
    VEL = [115, 88, 105, 92, 110, 95, 100, 85,
           118, 90, 100, 95, 105, 110, 95, 92,
           115, 92, 110, 95, 105, 95, 95, 92,
           110, 95, 118, 90, 105, 95, 92, 100]
    for i, (pad, v) in enumerate(zip(PERM, VEL)):
        t = i * 0.5
        notes.append(n(pad, t, 0.4, v))
    return notes


def punk_snare_lift():
    """Sparse 8th-note snare hits leading into a 32nd-note roll on bar 4."""
    notes = []
    for s in range(8):
        if s % 2 == 0:
            t = (s / 2) * 1.0   # bars 0-1 8th hits
            notes.append(n(38, t, 0.1, 95))
    # bar 3 sparse
    for t in (10.0, 11.0):
        notes.append(n(38, t, 0.1, 100))
    # final bar = roll
    for s in range(8):
        t = 12.0 + s * 0.5
        notes.append(n(38, t, 0.15, 95 + s * 3))
    # last 8 32nds
    for s in range(8):
        t = 14.0 + s * 0.25
        v = min(120, 105 + s * 2)
        notes.append(n(38, t, 0.0625, v))
    return notes


# ====================================================================

def main():
    ch = LiveChannel(); ch.start(); time.sleep(0.7)
    try:
        info = ch.get_session_info().result(timeout=5)
        sc = info.get('scene_count', 14)
        while sc < 15:
            ch.create_scene(-1).result(timeout=5); time.sleep(0.05)
            sc += 1
        print(f'scene_count = {sc}')

        # ----- Scene 12 AMEN_BREAKDOWN -----
        print('\n--- scene 12 AMEN_BREAKDOWN: layering ---')
        write(ch, T_HOOVER,        12, hoover_breakdown_drone(),       'HOOVER_drone_E')
        write(ch, T_VOX,           12, vox_breakdown_call(),           'VOX_breakdown_call')
        write(ch, T_BREAK_SLICES,  12, break_slices_breakdown_sparse(),'SLICES_sparse')
        try: dupe_atmos(ch, 12, 0.20)
        except Exception as e: print(f'  ATMOS 12: {e}')
        print('  HOOVER + VOX + ATMOS layered (-14dB)')

        # ----- Scene 13 AMEN_REBUILD -----
        print('\n--- scene 13 AMEN_REBUILD: layering ---')
        write(ch, T_HOOVER,        13, hoover_rebuild_stabs(),     'HOOVER_chord_stabs')
        write(ch, T_STAB,          13, stab_rave_chord_stabs(),    'STAB_rave_skank')
        write(ch, T_GUITAR,        13, guitar_punct(),             'GUITAR_punct')
        write(ch, T_VOX,           13, vox_rebuild_call(),         'VOX_rebuild_call')
        write(ch, T_BREAK_SLICES,  13, break_slices_rebuild_pattern(),'SLICES_half_time')
        try: dupe_atmos(ch, 13, 0.40)
        except Exception as e: print(f'  ATMOS 13: {e}')
        print('  HOOVER + STAB + GUITAR + VOX + ATMOS layered (-8dB)')

        # ----- Scene 14 HARDCORE_FULL -----
        print('\n--- scene 14 HARDCORE_FULL: full mix at 180 ---')
        # BREAK amen reprise
        try:
            brk = ch.get_track_clips(T_BREAK).result(timeout=3).get('clips', [])
            if not any(c.get('slot') == 14 for c in brk):
                ch.duplicate_clip(T_BREAK, 12, 14).result(timeout=10); time.sleep(0.1)
                ch.set_clip_name(T_BREAK, 14, 'AMEN_full_180').result(timeout=3)
                ch.set_clip_gain(T_BREAK, 14, 0.65).result(timeout=3)
        except Exception as e: print(f'  BREAK 14 fail: {e}')
        # KICK_4OTF ghosted variant
        try:
            kc = ch.get_track_clips(T_KICK).result(timeout=3).get('clips', [])
            if not any(c.get('slot') == 14 for c in kc):
                ch.duplicate_clip(T_KICK, 11, 14).result(timeout=10); time.sleep(0.1)
                ch.set_clip_name(T_KICK, 14, 'KICK_4OTF_ghosted').result(timeout=3)
        except Exception as e: print(f'  KICK 14 fail: {e}')
        write(ch, T_HOOVER,        14, hoover_full_hardcore(),   'HOOVER_rave_stabs')
        write(ch, T_STAB,          14, stab_rave_chord_stabs(),  'STAB_rave_skank')
        write(ch, T_GUITAR,        14, guitar_4_on_floor(),      'GUITAR_4on_floor')
        write(ch, T_PUNK_KIT,      14, punk_snare_lift(),        'PUNK_snare_lift')
        write(ch, T_VOX,           14, vox_full(),               'VOX_full')
        write(ch, T_BREAK_SLICES,  14, break_slices_scrambled(), 'SLICES_scrambled')
        try: dupe_atmos(ch, 14, 0.50)
        except Exception as e: print(f'  ATMOS 14: {e}')
        ch.set_scene_tempo(14, 180.0).result(timeout=3)
        print('  scene 14 baked at 180 bpm; full layering done')

        # ----- audition 12 → 13 → 14 -----
        print('\n--- audition the climb ---')
        ch.stop_all_clips().result(timeout=3); time.sleep(0.2)
        for s in (12, 13, 14):
            print(f'  fire {s}')
            ch.fire_scene(s).result(timeout=3)
            time.sleep(5.5)
        ch.stop_all_clips().result(timeout=3)
        ch.set_tempo(87.0).result(timeout=3)
    finally:
        ch.stop()


if __name__ == '__main__':
    main()
