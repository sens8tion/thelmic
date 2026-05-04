"""Three-fold unification pass:

  1. Wurly track: convert E major → Em natural minor by mapping G#→G,
     C#→C, D#→D in place. Also rewrites with the post-restart
     `start_time` field schema (no note loss this time).
  2. All other tonal clips (BASS, STAB, HAMMOND): re-generate notes from
     pack generators and write with `start_time` — fixes the silent
     truncation that happened when clips written with `time` met the
     new add_notes_to_clip handler.
  3. WURLY: load Vinyl Distortion / Dubplate.adv (the iconic Jamaican
     dubplate sound) for ragga dirt.
"""
from __future__ import annotations
import os, time as time_mod
os.environ.setdefault('LIVE_CHANNEL_ENABLED', '1')

from thelmic.live_channel import LiveChannel
from thelmic.aesthetics.dnb_jungle.compose_ragga import (
    drums_dub_in, drums_stepper, drums_raggajungle, drums_dubout,
    bass_stepper, bass_raggajungle,
    organ_skank_tease, organ_skank_stepper, organ_skank_full,
    vox_call_in, vox_toast_stepper, vox_toast_full, vox_echo_dubout,
)


T_DRUMS, T_BASS, T_STAB, T_VOX, T_HAMMOND, T_WURLY = 0, 4, 5, 7, 9, 10
CLIP_LEN = 16.0

# Em natural minor = E F# G A B C D
# E major = E F# G# A B C# D#
# Conversion (major → natural minor): G#(8)→G(7), C#(1)→C(0), D#(3)→D(2)
EMAJ_TO_EMIN = {1: 0, 3: 2, 8: 7}


def to_emin(pitch: int) -> int:
    pc = pitch % 12
    if pc in EMAJ_TO_EMIN:
        return pitch - 1   # always a half-step down
    return pitch


def time_to_starttime(notes: list[dict]) -> list[dict]:
    """Translate the legacy {pitch,time,duration,velocity} schema to the
    post-restart {pitch,start_time,duration,velocity} schema."""
    out = []
    for n in notes:
        if 'start_time' in n:
            out.append(n)
        else:
            out.append({
                'pitch': int(n['pitch']),
                'start_time': float(n.get('time', 0.0)),
                'duration': float(n.get('duration', 0.25)),
                'velocity': float(n.get('velocity', 100)),
            })
    return out


def rewrite_midi_clip(ch, ti: int, slot: int, notes: list[dict],
                      name: str | None = None, length: float = CLIP_LEN) -> None:
    """Replace clip at (ti, slot) entirely with these notes."""
    try: ch.clear_clip(ti, slot).result(timeout=3); time_mod.sleep(0.1)
    except Exception: pass
    ch.create_clip(ti, slot, length).result(timeout=10); time_mod.sleep(0.1)
    if notes:
        ch.add_notes_to_clip(ti, slot, time_to_starttime(notes)).result(timeout=10)
        time_mod.sleep(0.1)
    if name:
        ch.set_clip_name(ti, slot, name).result(timeout=5); time_mod.sleep(0.05)


def main() -> None:
    ch = LiveChannel(); ch.start(); time_mod.sleep(0.7)
    try:
        info = ch.get_session_info().result(timeout=5)
        print(f'tempo={info.get("tempo")}  tracks={info.get("track_count")}')

        # ====== 1. WURLY: E major → Em natural minor ======
        print('\n--- 1. WURLY → Em natural minor ---')
        try:
            notes = ch.get_clip_notes(T_WURLY, 0).result(timeout=5).get('notes', [])
            print(f'  read {len(notes)} notes')
            new = []
            shifted = 0
            for n in notes:
                p = int(n['pitch'])
                np = to_emin(p)
                if np != p: shifted += 1
                new.append({
                    'pitch': np,
                    'start_time': float(n['start_time']),
                    'duration': float(n['duration']),
                    'velocity': float(n.get('velocity', 100)),
                })
            ch.remove_clip_notes(T_WURLY, 0).result(timeout=5); time_mod.sleep(0.2)
            ch.add_notes_to_clip(T_WURLY, 0, new).result(timeout=5); time_mod.sleep(0.1)
            ch.set_clip_name(T_WURLY, 0, 'WURLY_SKANK_Em').result(timeout=5)
            print(f'  flattened {shifted}/{len(notes)} notes (G#→G, C#→C, D#→D)')

            verify = ch.get_clip_notes(T_WURLY, 0).result(timeout=5).get('notes', [])
            from collections import Counter
            pcs = Counter(int(n['pitch']) % 12 for n in verify)
            EM_NATURAL = {4, 6, 7, 9, 11, 0, 2}
            outside = sum(v for k, v in pcs.items() if k not in EM_NATURAL)
            print(f'  verify: {len(verify)} notes, {outside} out-of-Em-natural')
        except Exception as e:
            print(f'  WURLY transpose fail: {e}')

        # ====== 2. Regenerate tonal clips with start_time schema ======
        print('\n--- 2. Re-write tonal clips with start_time field ---')
        regen = [
            (T_DRUMS, 0, 'DUB_IN',      drums_dub_in),
            (T_DRUMS, 1, 'STEPPER',     drums_stepper),
            (T_DRUMS, 3, 'DUBOUT',      drums_dubout),
            # NB: don't touch DRUMS slot 2 (RAGGAJUNGLE_ROLL) or slot 4 (RAGGA_FILL)
            #     — those are bespoke fills written elsewhere
            (T_BASS,  1, 'STEPPER',     bass_stepper),
            (T_BASS,  2, 'RAGGAJUNGLE', bass_raggajungle),
            (T_STAB,  0, 'DUB_IN',      organ_skank_tease),
            (T_STAB,  1, 'STEPPER',     organ_skank_stepper),
            (T_STAB,  2, 'RAGGAJUNGLE', organ_skank_full),
            (T_STAB,  3, 'DUBOUT',      organ_skank_tease),
            (T_VOX,   0, 'DUB_IN',      vox_call_in),
            (T_VOX,   1, 'STEPPER',     vox_toast_stepper),
            (T_VOX,   2, 'RAGGAJUNGLE', vox_toast_full),
            (T_VOX,   3, 'DUBOUT',      vox_echo_dubout),
        ]
        for ti, slot, name, fn in regen:
            try:
                notes = fn()
                rewrite_midi_clip(ch, ti, slot, notes, name=name)
                # readback for sanity
                back = ch.get_clip_notes(ti, slot).result(timeout=3).get('notes', [])
                ok = '✓' if len(back) >= int(0.9 * len(notes)) else 'X'
                print(f'  {ok} T{ti} slot {slot} {name:13s}: wrote {len(notes)}, read back {len(back)}')
            except Exception as e:
                print(f'  T{ti} slot {slot} {name}: {e}')

        # also regen HAMMOND chord clips (already written but truncated)
        print('  HAMMOND chord re-writes...')
        EM = (52, 55, 59); AM = (57, 60, 64)
        def hammond_dub_in():
            notes = []
            for p in EM:
                notes.append({'pitch': p, 'time': 0.0,  'duration': 8.0, 'velocity': 70})
                notes.append({'pitch': p, 'time': 8.0,  'duration': 4.0, 'velocity': 75})
            for p in AM:
                notes.append({'pitch': p, 'time': 12.0, 'duration': 4.0, 'velocity': 80})
            return notes
        def hammond_stepper():
            notes = []
            for p in EM:
                notes.append({'pitch': p, 'time': 0.0, 'duration': 7.5, 'velocity': 65})
            for p in AM:
                notes.append({'pitch': p, 'time': 8.0, 'duration': 7.5, 'velocity': 70})
            return notes
        def hammond_dubout():
            return [{'pitch': p, 'time': 0.0, 'duration': 16.0, 'velocity': 85} for p in EM]
        for slot, name, fn in [
            (0, 'DUB_IN', hammond_dub_in),
            (1, 'STEPPER', hammond_stepper),
            (3, 'DUBOUT', hammond_dubout),
        ]:
            try:
                notes = fn()
                rewrite_midi_clip(ch, T_HAMMOND, slot, notes, name=name)
                back = ch.get_clip_notes(T_HAMMOND, slot).result(timeout=3).get('notes', [])
                ok = '✓' if len(back) == len(notes) else 'X'
                print(f'  {ok} HAMMOND slot {slot} {name:13s}: wrote {len(notes)}, read back {len(back)}')
            except Exception as e:
                print(f'  HAMMOND slot {slot}: {e}')

        # re-apply Swing Reggae groove to everything tonal we just rewrote
        print('\n--- re-apply Swing Reggae groove ---')
        grooves = ch.get_grooves().result(timeout=5).get('grooves', [])
        gidx = next((i for i, g in enumerate(grooves) if 'reggae' in g.get('name','').lower()), None)
        if gidx is not None:
            for ti, label in [(T_DRUMS,'DRUMS'),(T_STAB,'STAB'),(T_HAMMOND,'HAMMOND'),(T_WURLY,'WURLY')]:
                clips = ch.get_track_clips(ti).result(timeout=3).get('clips', [])
                for c in clips:
                    slot = c.get('slot')
                    try:
                        ch.set_clip_groove(ti, slot, gidx).result(timeout=3); time_mod.sleep(0.03)
                    except Exception: pass
            print(f'  groove[{gidx}] reapplied across DRUMS/STAB/HAMMOND/WURLY')

        # ====== 3. WURLY: load Vinyl Distortion / Dubplate.adv ======
        print('\n--- 3. dirty up WURLY with Dubplate vinyl distortion ---')
        try:
            ch.select_track(T_WURLY).result(timeout=3); time_mod.sleep(0.1)
            ch.load_item_at_path(
                T_WURLY, 'audio_effects/Vinyl Distortion', 'Dubplate.adv',
            ).result(timeout=20)
            time_mod.sleep(0.5)
            print('  loaded Dubplate.adv on WURLY')
        except Exception as e:
            print(f'  Dubplate fail: {e}')

        # also a touch of Saturator "A Bit Warmer" for tube glue
        try:
            ch.load_item_at_path(
                T_WURLY, 'audio_effects/Saturator', 'A Bit Warmer.adv',
            ).result(timeout=20)
            time_mod.sleep(0.5)
            print('  layered A Bit Warmer.adv saturation')
        except Exception as e:
            print(f'  Saturator fail: {e}')

        # ====== audition ======
        print('\n--- audition: 4 main scenes ---')
        ch.stop_all_clips().result(timeout=3); time_mod.sleep(0.3)
        for i, n in enumerate(['DUB_IN','STEPPER','RAGGAJUNGLE_ROLL','DUBOUT']):
            print(f'  fire {i} {n}')
            ch.fire_scene(i).result(timeout=3)
            time_mod.sleep(11.5)
        ch.stop_all_clips().result(timeout=3)

        # final audit
        print('\n--- final key audit ---')
        from collections import Counter
        NAMES = ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B']
        EM_NATURAL = {4, 6, 7, 9, 11, 0, 2}
        for ti, label in [(T_BASS,'BASS'),(T_STAB,'STAB'),(T_HAMMOND,'HAMMOND'),(T_WURLY,'WURLY')]:
            clips = ch.get_track_clips(ti).result(timeout=3).get('clips', [])
            total_notes = 0; total_out = 0
            for c in clips:
                slot = c.get('slot')
                if c.get('is_audio'): continue
                ns = ch.get_clip_notes(ti, slot).result(timeout=3).get('notes', [])
                pcs = Counter(int(n['pitch']) % 12 for n in ns)
                out = sum(v for k,v in pcs.items() if k not in EM_NATURAL)
                total_notes += len(ns); total_out += out
            verdict = 'Em ✓' if total_out == 0 else f'OUT {total_out}'
            print(f'  T{ti} {label:8s}: {total_notes} notes, {verdict}')
    finally:
        ch.stop()


if __name__ == '__main__':
    main()
