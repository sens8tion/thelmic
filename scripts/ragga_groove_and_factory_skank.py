"""Now that the new RPCs are live (post Live restart):

  1. Load Live's factory 'Swing Reggae.agr' groove into the pool, then
     apply it to all DRUMS + STAB clips (slots 0..4).
  2. Replace STAB slot 4 with the factory MIDI clip
     'Progression Reggae Upbeat Skank I-IV-V-IV C Major 85 bpm.alc',
     then transpose -8 semitones (C → E lower-octave) for Em.
"""
from __future__ import annotations
import os, time
os.environ.setdefault('LIVE_CHANNEL_ENABLED', '1')

from thelmic.live_channel import LiveChannel

T_DRUMS, T_STAB = 0, 5
S_FILL = 4


def main() -> None:
    ch = LiveChannel(); ch.start(); time.sleep(0.7)
    try:
        info = ch.get_session_info().result(timeout=5)
        print(f'tempo={info.get("tempo")}  tracks={info.get("track_count")}')

        # ====== 1. Swing Reggae groove → pool, then apply ======
        print('\n--- 1. Swing Reggae groove ---')
        # check pool first
        grooves = ch.get_grooves().result(timeout=5).get('grooves', [])
        target_idx = None
        for i, g in enumerate(grooves):
            if 'reggae' in (g.get('name','').lower()):
                target_idx = i; break

        if target_idx is None:
            # Need to load Swing Reggae.agr into the pool. The cleanest
            # path is to select the DRUMS track + an empty scene, then
            # load — Live's browser drops the .agr into the groove pool.
            try:
                ch.select_track(T_DRUMS).result(timeout=3); time.sleep(0.1)
                # try loading on track first; .agr should land in pool
                ch.load_item_at_path(
                    T_DRUMS, 'packs/Drum Booth/Grooves', 'Swing Reggae.agr',
                ).result(timeout=20)
                time.sleep(0.6)
            except Exception as e:
                print(f'  load Swing Reggae.agr: {e}')
                # try Straight Reggae as fallback
                try:
                    ch.load_item_at_path(
                        T_DRUMS, 'packs/Drum Booth/Grooves', 'Straight Reggae.agr',
                    ).result(timeout=20)
                    time.sleep(0.6)
                    print('  fallback: loaded Straight Reggae.agr')
                except Exception as e2:
                    print(f'  Straight Reggae.agr fallback: {e2}')

            grooves = ch.get_grooves().result(timeout=5).get('grooves', [])
            print(f'  pool now: {[g.get("name") for g in grooves]}')
            for i, g in enumerate(grooves):
                if 'reggae' in (g.get('name','').lower()):
                    target_idx = i; break

        if target_idx is not None:
            # apply to DRUMS slots 0..4 and STAB slots 0..4
            applied = 0
            for ti, label in [(T_DRUMS, 'DRUMS'), (T_STAB, 'STAB')]:
                clips = ch.get_track_clips(ti).result(timeout=3).get('clips', [])
                slots = sorted({c.get('slot') for c in clips if c.get('slot') is not None})
                for slot in slots:
                    try:
                        ch.set_clip_groove(ti, slot, target_idx).result(timeout=5)
                        time.sleep(0.05)
                        applied += 1
                    except Exception as e:
                        print(f'  {label} slot {slot} groove fail: {e}')
            print(f'  applied groove[{target_idx}] = {grooves[target_idx].get("name")} to {applied} clips')
        else:
            print('  no Reggae groove found in pool — skipping apply')

        # ====== 2. Factory skank progression on STAB slot 4 ======
        print('\n--- 2. Factory skank on STAB slot 4 ---')
        try:
            # clear what we wrote earlier
            try: ch.clear_clip(T_STAB, S_FILL).result(timeout=3); time.sleep(0.1)
            except Exception: pass
            # select target so load_item drops there
            ch.select_track(T_STAB).result(timeout=3); time.sleep(0.1)
            ch.select_scene(S_FILL).result(timeout=3); time.sleep(0.1)
            ch.load_item_at_path(
                T_STAB,
                'packs/Electric Keyboards/MIDI Clips',
                'Progression Reggae Upbeat Skank I - IV - V - IV C Major 85 bpm.alc',
            ).result(timeout=20)
            time.sleep(0.6)
            clips = ch.get_track_clips(T_STAB).result(timeout=3).get('clips', [])
            slot4 = next((c for c in clips if c.get('slot') == S_FILL), None)
            if slot4 is None:
                print('  factory clip did NOT land on slot 4')
            else:
                print(f'  loaded: {slot4.get("name")}')
                # transpose: read MIDI notes, shift -8 semitones (C → E lower)
                try:
                    notes = ch.get_clip_notes(T_STAB, S_FILL).result(timeout=5).get('notes', [])
                    if notes:
                        transposed = [
                            {**n, 'pitch': max(0, min(127, int(n['pitch']) - 8))}
                            for n in notes
                        ]
                        ch.remove_clip_notes(T_STAB, S_FILL).result(timeout=5); time.sleep(0.1)
                        ch.add_notes_to_clip(T_STAB, S_FILL, transposed).result(timeout=5)
                        print(f'  transposed {len(notes)} notes by -8 semitones (C → Em octave-lower)')
                    else:
                        print('  factory clip had no readable notes — keeping as-is')
                except Exception as e:
                    print(f'  transpose fail: {e}')
                ch.set_clip_name(T_STAB, S_FILL, 'FACTORY_SKANK_Em').result(timeout=5)
                # also apply the reggae groove if present
                if target_idx is not None:
                    try:
                        ch.set_clip_groove(T_STAB, S_FILL, target_idx).result(timeout=5)
                        print('  groove applied to factory skank')
                    except Exception as e:
                        print(f'  groove on factory skank fail: {e}')
        except Exception as e:
            print(f'  factory skank fail: {e}')

        # ====== audition the result ======
        print('\n--- audition: 5 scenes with reggae swing baked in ---')
        ch.stop_all_clips().result(timeout=3); time.sleep(0.3)
        for i, n in enumerate(['DUB_IN','STEPPER','RAGGAJUNGLE_ROLL','DUBOUT','RAGGA_FILL']):
            print(f'  fire {i} {n}')
            ch.fire_scene(i).result(timeout=3)
            time.sleep(11.5)
        ch.stop_all_clips().result(timeout=3)

        # final state
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
