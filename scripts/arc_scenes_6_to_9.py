"""Build the second half of the arc:
  Scene 6  SKA_PIVOT       140 bpm — ska upstroke + walking bass + ska beat
  Scene 7  PUNK_BURN       150 bpm — power chords + 4-on-floor punk drums
  Scene 8  HARDCORE_DROP   174 bpm — gabber kick rack + impact hits
  Scene 9  DNB_FULL        174 bpm — amen audio + reese bass + hoover stabs

Tempo shifts via client-side `fire_scene_with_tempo` helper —
set_tempo(bpm) immediately before fire_scene(idx). Hard switch from
the listener's perspective.

New tracks created on first run:
  GUITAR        MIDI track, Drum Rack with 4 power-chord one-shots
  HARDCORE_KIT  MIDI track, Drum Rack with 4 gabber kicks + 3 impact hits
  HOOVER        MIDI track, Simpler with hoover one-shot
  BASS_AUDIO    audio track, REESEY BASS dupe across DNB scenes
"""
from __future__ import annotations
import os, time
os.environ.setdefault('LIVE_CHANNEL_ENABLED', '1')

from thelmic.live_channel import LiveChannel

# ---- track indices we already know about ------------------------------
T_DRUMS, T_BREAK, T_SUB, T_BASS, T_STAB = 0, 1, 3, 4, 5
T_PAD, T_VOX, T_FX, T_HAMMOND, T_WURLY = 6, 7, 8, 9, 10
T_BREAK_RACK, T_ATMOS = 11, 12
# new tracks created by this script
T_GUITAR        = 13
T_HARDCORE_KIT  = 14
T_HOOVER        = 15
T_BASS_AUDIO    = 16

CLIP_LEN = 16.0
FREESOUND_DIR = "user_library/Samples/Freesound"

# ---- helper ----------------------------------------------------------

def fire_scene_with_tempo(ch, scene: int, bpm: float, dwell: float):
    """Hard tempo switch + scene fire. Tempo lands the moment Live's
    next bar quantum hits, fire_scene queues right after."""
    ch.set_tempo(float(bpm)).result(timeout=3)
    ch.fire_scene(scene).result(timeout=3)
    time.sleep(dwell)


def write_midi(ch, ti, slot, notes, name):
    try: ch.clear_clip(ti, slot).result(timeout=3); time.sleep(0.05)
    except Exception: pass
    ch.create_clip(ti, slot, CLIP_LEN).result(timeout=10); time.sleep(0.05)
    if notes:
        ch.add_notes_to_clip(ti, slot, notes).result(timeout=10); time.sleep(0.05)
    ch.set_clip_name(ti, slot, name).result(timeout=5)


def n(p, t, d, v):
    return {'pitch': int(p), 'start_time': float(t),
            'duration': float(d), 'velocity': float(v)}


# ---- pattern generators ---------------------------------------------

# General pads
KICK, SNARE, HAT_C, HAT_O, CRASH = 36, 38, 42, 46, 49
RIM = 37

# ---- SCENE 6: SKA_PIVOT @ 140 ---------------------------------------

def ska_drums_140():
    """Driving ska beat — kick 1+3, snare 2+4, every-8th closed hat,
    open hat on the &-of-2 and &-of-4 (the ska 'breath')."""
    notes = []
    for bar in range(4):
        b0 = bar * 4
        notes.append(n(KICK,  b0 + 0.0, 0.3, 115))
        notes.append(n(KICK,  b0 + 2.0, 0.3, 110))
        notes.append(n(SNARE, b0 + 1.0, 0.25, 112))
        notes.append(n(SNARE, b0 + 3.0, 0.25, 112))
        for s in range(8):  # 8th hats
            v = 70 if s % 2 == 0 else 60
            notes.append(n(HAT_C, b0 + s * 0.5, 0.125, v))
        notes.append(n(HAT_O, b0 + 1.5, 0.25, 85))
        notes.append(n(HAT_O, b0 + 3.5, 0.25, 90))
    return notes


def ska_bass_140():
    """Walking ska bass — root, fifth on every 8th. E A B A progression."""
    PROG_ROOTS = [40, 45, 47, 45]    # E2 A2 B2 A2 (in higher octave for ska brightness)
    notes = []
    for bar in range(4):
        b0 = bar * 4
        root = PROG_ROOTS[bar]
        fifth = root + 7
        # alternating root/fifth on 8ths
        for s, t in enumerate([0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5]):
            pitch = root if s % 2 == 0 else fifth
            v = 105 if s % 4 == 0 else 92
            notes.append(n(pitch, b0 + t, 0.4, v))
    return notes


def ska_skank_stab_140():
    """Off-beat chord stabs on every & — the ska upstroke. Em/Am/Bm/Am."""
    EM = (52, 55, 59); AM = (57, 60, 64); BM = (59, 62, 66)
    PROG = [EM, AM, BM, AM]
    notes = []
    for bar in range(4):
        b0 = bar * 4
        chord = PROG[bar]
        # on every &: 0.5, 1.5, 2.5, 3.5
        for off in (0.5, 1.5, 2.5, 3.5):
            for p in chord:
                notes.append(n(p, b0 + off, 0.18, 95))
    return notes


def guitar_skank_140():
    """Power chord stabs on every off-beat too — doubles the skank
    with a distorted texture. Pads 36-39 are different power-chord
    voicings; rotate through them."""
    notes = []
    PADS = [36, 37, 38, 39]
    for bar in range(4):
        b0 = bar * 4
        pad = PADS[bar % 4]
        for off in (0.5, 1.5, 2.5, 3.5):
            notes.append(n(pad, b0 + off, 0.2, 105))
    return notes


# ---- SCENE 7: PUNK_BURN @ 150 ---------------------------------------

def punk_drums_150():
    """4-on-floor punk — kick every beat, snare 2+4, 16th hat carpet."""
    notes = []
    for bar in range(4):
        b0 = bar * 4
        for beat in range(4):
            notes.append(n(KICK, b0 + beat, 0.25, 118 if beat == 0 else 110))
        notes.append(n(SNARE, b0 + 1.0, 0.25, 115))
        notes.append(n(SNARE, b0 + 3.0, 0.25, 115))
        for s in range(16):
            v = 70 if s % 2 == 0 else 50
            if s % 4 == 0: v += 8
            notes.append(n(HAT_C, b0 + s * 0.25, 0.0625, v))
        notes.append(n(CRASH, b0 + 0.0, 0.5, 110) if bar == 0 else None)
    return [x for x in notes if x is not None]


def punk_guitar_150():
    """Power chord stab on every beat (4-on-floor with the kick).
    Drives the whole punk feel."""
    notes = []
    PADS = [36, 37, 38, 39]
    for bar in range(4):
        b0 = bar * 4
        for beat in range(4):
            pad = PADS[(bar + beat) % 4]
            notes.append(n(pad, b0 + beat, 0.4, 115))
    return notes


# ---- SCENE 8: HARDCORE_DROP @ 174 -----------------------------------
# At project tempo 174, 16th notes = 174 bpm dnb feel; gabber lives at this BPM natively

def hardcore_kicks_174():
    """4-on-the-floor distorted gabber kicks. At 174 this is gabber proper.
    Pad 36 = main hard kick (Hell's Screamer or Heavy Room)."""
    notes = []
    for bar in range(4):
        b0 = bar * 4
        for beat in range(4):
            notes.append(n(36, b0 + beat, 0.25, 122))
    # impact hits on bar boundaries (pads 40-42 = impact_hit voices)
    notes.append(n(40, 0.0,  1.0, 115))   # impact start
    notes.append(n(41, 8.0,  0.5, 105))
    return notes


def hardcore_hoover_174():
    """Hoover synth stabs — 4 chord roots over 4 bars in Em territory,
    on the 1 of each bar, with one accent on bar 4's & for the lift."""
    EM_ROOTS = [40, 45, 47, 45]   # E A B A
    notes = []
    for bar in range(4):
        notes.append(n(EM_ROOTS[bar], bar * 4 + 0.0, 1.5, 110))
    # tail accent
    notes.append(n(EM_ROOTS[0] + 12, 14.5, 1.0, 105))
    return notes


# ---- SCENE 9: DNB_FULL @ 174 ----------------------------------------
# We use the existing breaks_ragga.double_time_dnb() pattern on BREAK_RACK
# plus reece bass audio + amen audio + hoover stabs

def dnb_hoover_174():
    """Sparser hoover — accent on every other bar's 1 + a syncopated stab."""
    notes = []
    notes.append(n(40, 0.0,  3.0, 105))     # E2 long bed
    notes.append(n(45, 4.0,  2.0, 100))     # A2 bar 2
    notes.append(n(47, 8.0,  3.0, 105))     # B2 bar 3
    notes.append(n(45, 12.0, 2.5, 100))     # A2 bar 4
    return notes


# =========================================================================

def main():
    ch = LiveChannel(); ch.start(); time.sleep(0.7)
    try:
        info = ch.get_session_info().result(timeout=5)
        print(f'tempo={info.get("tempo")}  tracks={info.get("track_count")}')

        # ensure at least 10 scenes exist (slots 0..9)
        scene_count = info.get('scene_count', 0)
        while scene_count < 10:
            ch.create_scene(-1).result(timeout=5); time.sleep(0.05)
            scene_count += 1
        print(f'  scene count: {scene_count}')

        # ============== A. infrastructure tracks ==============
        existing_names = {ch.get_track_info(ti).result(timeout=3).get('name','')
                          for ti in range(info.get('track_count', 0))}

        # GUITAR — drum rack with 4 power chord one-shots on pads 36-39
        if 'GUITAR' not in existing_names:
            idx = info.get('track_count', 0)
            ch.create_midi_track(idx).result(timeout=10); time.sleep(0.4)
            ch.set_track_name(idx, 'GUITAR').result(timeout=5); time.sleep(0.2)
            # load empty drum rack first
            ch.load_item_at_path(idx, 'drums', 'Selectah Kit.adg').result(timeout=20); time.sleep(0.8)
            print(f'  created GUITAR at T{idx}')
            POWER_CHORDS = [
                (36, 'FS_power_chord_31936_14_Dist_guitar_power_d_pm2_flac.mp3'),
                (37, 'FS_power_chord_31935_13_Dist_guitar_power_d_pm_flac.mp3'),
                (38, 'FS_power_chord_31934_12_Dist_guitar_power_d_short_flac.mp3'),
                (39, 'FS_power_chord_31931_09_Dist_guitar_power_a_pm2_flac.mp3'),
            ]
            for pad, fname in POWER_CHORDS:
                try:
                    ch.load_sample_to_pad(idx, 0, pad, FREESOUND_DIR, fname).result(timeout=20)
                    print(f'    pad {pad} ← {fname[:40]}')
                    time.sleep(0.3)
                except Exception as e:
                    print(f'    pad {pad} fail: {e}')
            T_G = idx
        else:
            T_G = next(ti for ti in range(info.get('track_count', 0))
                       if ch.get_track_info(ti).result(timeout=3).get('name') == 'GUITAR')
            print(f'  reusing GUITAR at T{T_G}')

        info = ch.get_session_info().result(timeout=5)
        existing_names = {ch.get_track_info(ti).result(timeout=3).get('name','')
                          for ti in range(info.get('track_count', 0))}

        # HARDCORE_KIT — gabber kicks (pad 36) + impact hits (40-42)
        if 'HARDCORE_KIT' not in existing_names:
            idx = info.get('track_count', 0)
            ch.create_midi_track(idx).result(timeout=10); time.sleep(0.4)
            ch.set_track_name(idx, 'HARDCORE_KIT').result(timeout=5); time.sleep(0.2)
            ch.load_item_at_path(idx, 'drums', 'Selectah Kit.adg').result(timeout=20); time.sleep(0.8)
            print(f'  created HARDCORE_KIT at T{idx}')
            HC_PADS = [
                (36, 'FS_gabber_kick_331863_xKicks_-_Hell_s_Screamer_aif.mp3'),
                (37, 'FS_gabber_kick_331864_xKicks_-_Heavy_Room_aif.mp3'),
                (38, 'FS_gabber_kick_331865_xKicks_-_HiPhase_aif.mp3'),
                (40, 'FS_impact_hit_195790_cinematic_boom_130730_06_wav.mp3'),
                (41, 'FS_impact_hit_553521_Pop_down_impact_1-2_Without_attack_4lrs_mltprcssng__wav.mp3'),
                (42, 'FS_impact_hit_553518_Pop_down_impact_4_9lrs_mltprcssng__wav.mp3'),
            ]
            for pad, fname in HC_PADS:
                try:
                    ch.load_sample_to_pad(idx, 0, pad, FREESOUND_DIR, fname).result(timeout=20)
                    print(f'    pad {pad} ← {fname[:50]}')
                    time.sleep(0.3)
                except Exception as e:
                    print(f'    pad {pad} fail: {e}')
            T_HC = idx
        else:
            T_HC = next(ti for ti in range(info.get('track_count', 0))
                        if ch.get_track_info(ti).result(timeout=3).get('name') == 'HARDCORE_KIT')
            print(f'  reusing HARDCORE_KIT at T{T_HC}')

        info = ch.get_session_info().result(timeout=5)
        existing_names = {ch.get_track_info(ti).result(timeout=3).get('name','')
                          for ti in range(info.get('track_count', 0))}

        # HOOVER — Simpler with the Hoover Synth
        if 'HOOVER' not in existing_names:
            idx = info.get('track_count', 0)
            ch.create_midi_track(idx).result(timeout=10); time.sleep(0.4)
            ch.set_track_name(idx, 'HOOVER').result(timeout=5); time.sleep(0.2)
            ch.load_item_at_path(idx, FREESOUND_DIR,
                                  'FS_hoover_399542_Hoover_Synth.mp3').result(timeout=20)
            time.sleep(0.6)
            T_H = idx
            print(f'  created HOOVER at T{T_H}')
        else:
            T_H = next(ti for ti in range(info.get('track_count', 0))
                       if ch.get_track_info(ti).result(timeout=3).get('name') == 'HOOVER')
            print(f'  reusing HOOVER at T{T_H}')

        info = ch.get_session_info().result(timeout=5)
        existing_names = {ch.get_track_info(ti).result(timeout=3).get('name','')
                          for ti in range(info.get('track_count', 0))}

        # BASS_AUDIO — REESEY BASS audio for DNB scenes
        if 'BASS_AUDIO' not in existing_names:
            idx = info.get('track_count', 0)
            ch.create_audio_track(idx).result(timeout=10); time.sleep(0.4)
            ch.set_track_name(idx, 'BASS_AUDIO').result(timeout=5); time.sleep(0.2)
            T_BA = idx
            # load reese on slot 9 directly
            print(f'  created BASS_AUDIO at T{T_BA}')
        else:
            T_BA = next(ti for ti in range(info.get('track_count', 0))
                        if ch.get_track_info(ti).result(timeout=3).get('name') == 'BASS_AUDIO')
            print(f'  reusing BASS_AUDIO at T{T_BA}')

        # ============== B. write scene 6-9 clips ==============
        print('\n--- writing scene clips ---')

        # SCENE 6 — SKA_PIVOT
        write_midi(ch, T_DRUMS,  6, ska_drums_140(),       'SKA_drums_140')
        write_midi(ch, T_BASS,   6, ska_bass_140(),        'SKA_bass_walk')
        write_midi(ch, T_STAB,   6, ska_skank_stab_140(),  'SKA_skank_stab')
        write_midi(ch, T_G,      6, guitar_skank_140(),    'SKA_guitar_skank')
        # ATMOS slot 6 — dupe rowdy crowd from slot 2 if not already
        try:
            atmos_clips = ch.get_track_clips(T_ATMOS).result(timeout=3).get('clips', [])
            if not any(c.get('slot') == 6 for c in atmos_clips):
                ch.duplicate_clip(T_ATMOS, 2, 6).result(timeout=10); time.sleep(0.1)
                ch.set_clip_gain(T_ATMOS, 6, 0.30).result(timeout=3)
                ch.set_clip_name(T_ATMOS, 6, 'BBC_rowdy_crowd').result(timeout=3)
        except Exception as e: print(f'  ATMOS slot 6: {e}')
        print('  scene 6 SKA_PIVOT written')

        # SCENE 7 — PUNK_BURN
        write_midi(ch, T_DRUMS,  7, punk_drums_150(),  'PUNK_drums_150')
        write_midi(ch, T_G,      7, punk_guitar_150(), 'PUNK_guitar_chords')
        print('  scene 7 PUNK_BURN written')

        # SCENE 8 — HARDCORE_DROP
        write_midi(ch, T_HC,     8, hardcore_kicks_174(), 'HC_gabber_kicks')
        write_midi(ch, T_H,      8, hardcore_hoover_174(),'HC_hoover_chords')
        # BASS_AUDIO slot 8 = reese bass
        try:
            bclips = ch.get_track_clips(T_BA).result(timeout=3).get('clips', [])
            if not any(c.get('slot') == 8 for c in bclips):
                ch.load_audio_to_slot(T_BA, 8, FREESOUND_DIR,
                                       'FS_reece_bass_265151_REESEY_BASS__90BPM__D.mp3').result(timeout=20)
                time.sleep(0.4)
                ch.set_clip_warp(T_BA, 8, warping=True, warp_mode=6).result(timeout=3)
                ch.set_clip_loop(T_BA, 8, True).result(timeout=3)
                ch.set_clip_name(T_BA, 8, 'REESE_bass').result(timeout=3)
        except Exception as e: print(f'  BASS_AUDIO slot 8: {e}')
        print('  scene 8 HARDCORE_DROP written')

        # SCENE 9 — DNB_FULL
        # use existing BREAK_RACK double_time_dnb pattern duped to slot 9
        try:
            br_clips = ch.get_track_clips(T_BREAK_RACK).result(timeout=3).get('clips', [])
            if not any(c.get('slot') == 9 for c in br_clips):
                ch.duplicate_clip(T_BREAK_RACK, 4, 9).result(timeout=10); time.sleep(0.1)
                ch.set_clip_name(T_BREAK_RACK, 9, 'DNB_double_time').result(timeout=3)
        except Exception as e: print(f'  BREAK_RACK slot 9: {e}')
        # BREAK audio: amen on slot 9
        try:
            brk_clips = ch.get_track_clips(T_BREAK).result(timeout=3).get('clips', [])
            if not any(c.get('slot') == 9 for c in brk_clips):
                ch.load_audio_to_slot(T_BREAK, 9, FREESOUND_DIR,
                                       'FS_dnb_break_337825_Break_Dnb_174_Bpm_01_wav.mp3').result(timeout=20)
                time.sleep(0.4)
                ch.set_clip_warp(T_BREAK, 9, warping=True, warp_mode=0).result(timeout=3)
                ch.set_clip_loop(T_BREAK, 9, True).result(timeout=3)
                ch.set_clip_name(T_BREAK, 9, 'DNB_break_174').result(timeout=3)
        except Exception as e: print(f'  BREAK slot 9: {e}')
        # BASS_AUDIO slot 9 = reese
        try:
            bclips = ch.get_track_clips(T_BA).result(timeout=3).get('clips', [])
            if not any(c.get('slot') == 9 for c in bclips):
                ch.duplicate_clip(T_BA, 8, 9).result(timeout=10); time.sleep(0.1)
                ch.set_clip_name(T_BA, 9, 'REESE_bass').result(timeout=3)
        except Exception as e: print(f'  BASS_AUDIO slot 9: {e}')
        write_midi(ch, T_H, 9, dnb_hoover_174(), 'DNB_hoover_bed')
        print('  scene 9 DNB_FULL written')

        # ============== C. audition the full arc 0..9 ==============
        print('\n--- AUDITION FULL ARC ---')
        ch.stop_all_clips().result(timeout=3); time.sleep(0.3)
        TEMPOS = [
            (0, 'DUB_IN',         87, 11.5),
            (1, 'STEPPER',        87, 11.5),
            (2, 'RAGGAJUNGLE',    87, 11.5),
            (3, 'DUBOUT',         87, 11.5),
            (4, 'RAGGA_FILL',     87, 11.5),
            (5, 'WURLY_REMIX',    87, 22.0),     # full wurly cycle
            (6, 'SKA_PIVOT',     140,  6.85),    # 16 beats at 140 = 6.85s
            (7, 'PUNK_BURN',     150,  6.40),    # 16 beats at 150 = 6.4s
            (8, 'HARDCORE_DROP', 174,  5.52),    # 16 beats at 174 = 5.52s
            (9, 'DNB_FULL',      174,  5.52),
        ]
        for scene, label, bpm, dwell in TEMPOS:
            print(f'  fire {scene} {label:14s} @ {bpm} bpm')
            fire_scene_with_tempo(ch, scene, bpm, dwell)
        ch.stop_all_clips().result(timeout=3)
        ch.set_tempo(87.0).result(timeout=3)   # restore base tempo
        print('--- arc complete, tempo restored to 87 ---')
    finally:
        ch.stop()


if __name__ == '__main__':
    main()
