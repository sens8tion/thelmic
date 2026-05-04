"""Build a BREAK_RACK MIDI track loaded with Riddim Rager Kit, then write
every breaks_ragga pattern into a slot for audition. Designed as the
substrate for the upcoming scene rebuild.
"""
from __future__ import annotations
import os, time
os.environ.setdefault('LIVE_CHANNEL_ENABLED', '1')

from thelmic.live_channel import LiveChannel
from thelmic.aesthetics.dnb_jungle.breaks_ragga import (
    BREAK_PATTERNS, BREAK_DESCRIPTIONS, CLIP_LENGTH_BEATS,
)

KIT = 'Riddim Rager Kit.adg'


def main() -> None:
    ch = LiveChannel(); ch.start(); time.sleep(0.7)
    try:
        info = ch.get_session_info().result(timeout=5)
        print(f'tempo={info.get("tempo")}  tracks={info.get("track_count")}')

        # 1. find or create BREAK_RACK track
        target = None
        for ti in range(info.get('track_count', 0)):
            nm = ch.get_track_info(ti).result(timeout=3).get('name','')
            if nm == 'BREAK_RACK':
                target = ti; break
        if target is None:
            new_idx = info.get('track_count', 0)
            ch.create_midi_track(new_idx).result(timeout=10); time.sleep(0.4)
            ch.set_track_name(new_idx, 'BREAK_RACK').result(timeout=5); time.sleep(0.2)
            target = new_idx
            print(f'  created BREAK_RACK at T{target}')
        else:
            print(f'  reusing BREAK_RACK at T{target}')

        # 2. load Riddim Rager Kit (skip if already a Drum Rack with kit content)
        tinfo = ch.get_track_info(target).result(timeout=3)
        devs = tinfo.get('devices', [])
        has_drum_rack = any('Drum' in (d.get('class_name') or '') for d in devs)
        if not has_drum_rack:
            ch.load_item_at_path(target, 'drums', KIT).result(timeout=25)
            time.sleep(1.0)
            print(f'  loaded {KIT}')
        else:
            print(f'  drum rack already present; skipping kit load')

        # 3. write each break pattern to a slot
        SCENES = list(BREAK_PATTERNS.keys())
        for slot, name in enumerate(SCENES):
            try: ch.clear_clip(target, slot).result(timeout=3); time.sleep(0.05)
            except Exception: pass
            ch.create_clip(target, slot, CLIP_LENGTH_BEATS).result(timeout=10); time.sleep(0.05)
            notes = BREAK_PATTERNS[name]()
            ch.add_notes_to_clip(target, slot, notes).result(timeout=10); time.sleep(0.05)
            ch.set_clip_name(target, slot, name).result(timeout=5)
            print(f'  slot {slot} {name:22s} ({len(notes):3d} notes)  — {BREAK_DESCRIPTIONS[name]}')

        # 4. apply Swing Reggae groove
        grooves = ch.get_grooves().result(timeout=5).get('grooves', [])
        gidx = next((i for i, g in enumerate(grooves) if 'reggae' in g.get('name','').lower()), None)
        if gidx is not None:
            for slot in range(len(SCENES)):
                try: ch.set_clip_groove(target, slot, gidx).result(timeout=3); time.sleep(0.03)
                except Exception: pass
            print(f'  Swing Reggae groove applied to all {len(SCENES)} clips')

        # 5. audition each break in isolation
        ch.stop_all_clips().result(timeout=3); time.sleep(0.2)
        SECS = 11.5
        print('\n--- audition each break ---')
        for slot, name in enumerate(SCENES):
            print(f'  fire slot {slot} {name}')
            ch.fire_clip(target, slot).result(timeout=3)
            time.sleep(SECS)
        ch.stop_all_clips().result(timeout=3)
    finally:
        ch.stop()


if __name__ == '__main__':
    main()
