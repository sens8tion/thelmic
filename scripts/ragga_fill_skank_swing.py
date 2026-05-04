"""Three-part add-on:
  A. add a 5th scene RAGGA_FILL — rolling drum fill in isolation,
     intended as a 4-bar transition between full scenes
  B. import factory 'Progression Reggae Upbeat Skank I-IV-V-IV C Major
     85 bpm.alc', transpose it down to Em as an alternate skank pattern
  C. apply Live's 'Swing Reggae.agr' groove to the drums for natural swing
"""
from __future__ import annotations
import os, time
os.environ.setdefault('LIVE_CHANNEL_ENABLED', '1')

from thelmic.live_channel import LiveChannel


T_DRUMS, T_STAB, T_PAD, T_FX, T_VOX, T_HAMMOND = 0, 5, 6, 8, 7, 9
T_SUB = 3
S_FILL = 4   # new fifth scene
CLIP_LEN = 16.0

KICK, SNARE, HAT_C, HAT_O, CRASH = 36, 38, 42, 46, 49


# ---- A. RAGGA_FILL drum content -----------------------------------------

def fill_drums() -> list[dict]:
    """Standalone rolling fill — denser than the in-scene RAGGAJUNGLE
    version, designed to be auditioned as a 4-bar transition."""
    notes = []
    notes.append({"pitch": CRASH, "time": 0.0,  "duration": 1.5, "velocity": 115})
    # 32nd hat carpet
    for s in range(64):
        v = 78 if s % 2 == 0 else 58
        if s % 8 == 0: v += 12
        if s % 16 == 0: v += 6
        notes.append({"pitch": HAT_C, "time": s * 0.25, "duration": 0.0625, "velocity": v})
    # increasingly dense kicks
    kicks = [(0.0, 118), (1.5, 95),
             (4.0, 115), (5.5, 100), (6.75, 95),
             (8.0, 115), (9.0, 95), (10.5, 105), (11.5, 100),
             # bar 4 = avalanche
             (12.0, 115), (12.5, 100), (13.0, 110), (13.5, 95),
             (14.0, 105), (14.375, 95), (14.75, 100), (15.125, 90), (15.5, 110)]
    for t, v in kicks:
        notes.append({"pitch": KICK, "time": t, "duration": 0.2, "velocity": v})
    # ghost-snare flurries that tighten into a roll
    snares = [(1.0, 110), (1.75, 65),  (2.5, 100),
              (3.0, 110), (3.625, 75), (3.875, 80),
              (5.0, 110), (5.5, 70),   (6.0, 95),
              (7.0, 110), (7.5, 80),   (7.75, 75),
              (9.0, 110), (10.0, 90),  (10.5, 80), (11.0, 105),
              # bar 4 roll
              (13.0, 105), (13.25, 75), (13.5, 90),
              (14.0, 105), (14.25, 80), (14.5, 95),
              (15.0, 110), (15.125, 85), (15.25, 100), (15.375, 90),
              (15.5, 115), (15.625, 95), (15.75, 105), (15.875, 100)]
    for t, v in snares:
        notes.append({"pitch": SNARE, "time": t, "duration": 0.0625, "velocity": v})
    # open-hat punctuation
    for bar in (0, 1, 2):
        notes.append({"pitch": HAT_O, "time": bar * 4 + 3.5, "duration": 0.5, "velocity": 90})
    return notes


def fill_sub() -> list[dict]:
    """Single sustained low E to anchor the fill — gives it punch
    without competing with the drums."""
    return [
        {"pitch": 28, "time": 0.0,  "duration": 12.0, "velocity": 108},  # E1
        {"pitch": 28, "time": 12.0, "duration": 4.0,  "velocity": 110},  # accent on bar 4
    ]


# ---- main ---------------------------------------------------------------

def main() -> None:
    ch = LiveChannel(); ch.start(); time.sleep(0.6)
    try:
        info = ch.get_session_info().result(timeout=5)
        print(f'tempo={info.get("tempo")}  tracks={info.get("track_count")}')

        # ====== A. RAGGA_FILL scene ======
        print('\n--- A. RAGGA_FILL scene at slot 4 ---')
        try:
            # ensure the scene exists; create_scene if not (older Live default = 8)
            # Just write into slot 4 directly — Live auto-creates scenes for empty slots.
            for ti in (T_DRUMS,):
                try: ch.clear_clip(ti, S_FILL).result(timeout=3); time.sleep(0.05)
                except Exception: pass
            ch.create_clip(T_DRUMS, S_FILL, CLIP_LEN).result(timeout=10); time.sleep(0.1)
            ch.add_notes_to_clip(T_DRUMS, S_FILL, fill_drums()).result(timeout=10); time.sleep(0.1)
            ch.set_clip_name(T_DRUMS, S_FILL, 'RAGGA_FILL').result(timeout=5)
            print(f'  drums fill: {len(fill_drums())} notes')
        except Exception as e:
            print(f'  drums fill fail: {e}')

        # SUB anchor under the fill
        try:
            try: ch.clear_clip(T_SUB, S_FILL).result(timeout=3); time.sleep(0.05)
            except Exception: pass
            # SUB is audio — duplicate slot 0 audio clip into slot 4
            ch.duplicate_clip(T_SUB, 0, S_FILL).result(timeout=10); time.sleep(0.1)
            print('  sub: duped slot 0 -> slot 4')
        except Exception as e:
            print(f'  sub fill fail: {e}')

        # ====== B. factory skank progression on STAB slot 4 ======
        print('\n--- B. factory reggae skank progression on STAB ---')
        try:
            # Select scene 4 then select STAB so load_item drops there
            ch.select_track(T_STAB).result(timeout=3); time.sleep(0.1)
            ch.select_scene(S_FILL).result(timeout=3); time.sleep(0.1)
            ch.load_item_at_path(
                T_STAB,
                'packs/Electric Keyboards/MIDI Clips',
                'Progression Reggae Upbeat Skank I - IV - V - IV C Major 85 bpm.alc',
            ).result(timeout=20)
            time.sleep(0.6)
            # Verify it landed
            clips = ch.get_track_clips(T_STAB).result(timeout=3).get('clips', [])
            slot4 = next((c for c in clips if c.get('slot') == S_FILL), None)
            if slot4:
                print(f"  loaded factory clip: {slot4.get('name')}")
                # Transpose down to E by setting clip pitch coarse=-8 semitones
                # (C → E is 4 semitones up or 8 down; -8 keeps it lower-octave)
                try:
                    ch.set_clip_pitch(T_STAB, S_FILL, coarse=-8).result(timeout=5)
                    print('  set clip pitch -8 semitones (C → E lower oct)')
                except Exception as e:
                    print(f'  clip pitch fail (likely audio-only param): {e}')
                    # fallback: read MIDI notes, transpose, write back
                    try:
                        notes = ch.get_clip_notes(T_STAB, S_FILL).result(timeout=5).get('notes', [])
                        if notes:
                            ch.remove_clip_notes(T_STAB, S_FILL).result(timeout=5); time.sleep(0.1)
                            transposed = [{**n, 'pitch': max(0, min(127, n['pitch'] - 8))} for n in notes]
                            ch.add_notes_to_clip(T_STAB, S_FILL, transposed).result(timeout=5)
                            print(f'  transposed {len(notes)} MIDI notes by -8 semitones')
                    except Exception as e2:
                        print(f'  midi transpose fallback fail: {e2}')
                ch.set_clip_name(T_STAB, S_FILL, 'FACTORY_SKANK_Em').result(timeout=5)
            else:
                print('  factory clip did NOT land on slot 4')
        except Exception as e:
            print(f'  factory skank fail: {e}')

        # PAD audio dupe into slot 4 too — the dub organ underneath the fill
        try:
            ch.duplicate_clip(T_PAD, 0, S_FILL).result(timeout=10); time.sleep(0.1)
        except Exception as e:
            print(f'  pad slot 4 fail: {e}')

        # ====== C. apply Swing Reggae groove to drums ======
        print('\n--- C. Swing Reggae groove on drums ---')
        try:
            # First check the current pool
            grooves = ch.get_grooves().result(timeout=5).get('grooves', [])
            print(f'  current groove pool: {[g.get("name") for g in grooves]}')

            target_idx = None
            for i, g in enumerate(grooves):
                if 'reggae' in (g.get('name','').lower()):
                    target_idx = i; break

            if target_idx is None:
                # load Swing Reggae.agr from the factory pack — drops into pool
                try:
                    # Browser path for grooves needs verification; try loading with select_track first
                    ch.select_track(T_DRUMS).result(timeout=3); time.sleep(0.1)
                    ch.load_item_at_path(
                        T_DRUMS,
                        'packs/Drum Booth/Grooves',
                        'Swing Reggae.agr',
                    ).result(timeout=20)
                    time.sleep(0.6)
                    grooves = ch.get_grooves().result(timeout=5).get('grooves', [])
                    print(f'  pool after load: {[g.get("name") for g in grooves]}')
                    for i, g in enumerate(grooves):
                        if 'reggae' in (g.get('name','').lower()):
                            target_idx = i; break
                except Exception as e:
                    print(f'  groove load fail: {e}')

            if target_idx is not None:
                # apply to all DRUMS clips and the rolling fill
                for slot in range(5):
                    try:
                        ch.set_clip_groove(T_DRUMS, slot, target_idx).result(timeout=5)
                        print(f'  applied groove[{target_idx}] to DRUMS slot {slot}')
                    except Exception as e:
                        print(f'  apply slot {slot}: {e}')
            else:
                print('  no Reggae groove found — skipping groove apply')
        except Exception as e:
            print(f'  groove fail: {e}')

        # ====== audition the new RAGGA_FILL scene ======
        print('\n--- audition slot 4 (RAGGA_FILL) ---')
        ch.stop_all_clips().result(timeout=3); time.sleep(0.3)
        ch.fire_scene(S_FILL).result(timeout=3)
        time.sleep(11.5)
        ch.stop_all_clips().result(timeout=3)

        # Final state print
        print('\n--- final state ---')
        info = ch.get_session_info().result(timeout=5)
        for ti in range(info.get('track_count', 0)):
            nm = ch.get_track_info(ti).result(timeout=3).get('name','?')
            clips = ch.get_track_clips(ti).result(timeout=3).get('clips', [])
            slots = sorted([(c.get('slot'), c.get('name')) for c in clips])
            print(f'  T{ti:2d} {nm:30s} {slots}')
    finally:
        ch.stop()


if __name__ == '__main__':
    main()
