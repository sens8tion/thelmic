"""Add a BBC ATMOS layer track and wire the 5 BBC RemArc samples into
the existing scenes:

  ATMOS track (audio):
    DUB_IN       BBC_pulsing_bass_hum    drone bed under the dub intro
    STEPPER      BBC_general_crackle     vinyl crackle bed
    RAGGAJUNGLE  BBC_rowdy_crowd_hall    dancehall crowd noise
    DUBOUT       BBC_pulsing_bass_hum    drone reprise (loop)

  FX track slot 4 (RAGGA_FILL):
                 BBC_vinyl_scratch       record-scratch transition one-shot

  FX track slot 4 also keeps the existing dub_siren on slots 0-3;
  factory_siren is layered nowhere by default — it's available in the
  User Library when the user wants it as an alternate.
"""
from __future__ import annotations
import os, time
os.environ.setdefault('LIVE_CHANNEL_ENABLED', '1')

from thelmic.live_channel import LiveChannel

T_FX = 8
S_DUB_IN, S_STEPPER, S_RAGGAJUNGLE, S_DUBOUT, S_RAGGA_FILL = 0, 1, 2, 3, 4
BBC_DIR = "user_library/Samples/BBC"

# (slot, sample_filename, warp_mode)
# warp_mode: 0=Beats 1=Tones 2=Texture 5=Re-Pitch 6=Complex Pro
ATMOS_SCENES = [
    (S_DUB_IN,      "BBC_pulsing_bass_hum.mp3",   2),   # Texture for ambient stretch
    (S_STEPPER,     "BBC_general_crackle.mp3",    2),
    (S_RAGGAJUNGLE, "BBC_rowdy_crowd_hall.mp3",   2),
    (S_DUBOUT,      "BBC_pulsing_bass_hum.mp3",   2),
]


def main() -> None:
    ch = LiveChannel(); ch.start(); time.sleep(0.7)
    try:
        info = ch.get_session_info().result(timeout=5)
        print(f'tempo={info.get("tempo")}  tracks={info.get("track_count")}')

        # 1. find or create ATMOS track
        atmos = None
        for ti in range(info.get('track_count', 0)):
            nm = ch.get_track_info(ti).result(timeout=3).get('name','')
            if nm == 'ATMOS':
                atmos = ti; break
        if atmos is None:
            new_idx = info.get('track_count', 0)
            ch.create_audio_track(new_idx).result(timeout=10); time.sleep(0.4)
            ch.set_track_name(new_idx, 'ATMOS').result(timeout=5); time.sleep(0.2)
            atmos = new_idx
            print(f'  created ATMOS audio track at T{atmos}')
        else:
            print(f'  reusing ATMOS at T{atmos}')

        # 2. load each BBC sample to its slot
        print('\n--- loading BBC samples ---')
        for slot, fname, wmode in ATMOS_SCENES:
            try:
                try: ch.clear_clip(atmos, slot).result(timeout=3); time.sleep(0.05)
                except Exception: pass
                ch.load_audio_to_slot(atmos, slot, BBC_DIR, fname).result(timeout=20)
                time.sleep(0.4)
                # set warp mode + lower gain (atmospheric layer should sit underneath)
                try:
                    ch.set_clip_warp(atmos, slot, warping=True, warp_mode=wmode).result(timeout=5)
                    ch.set_clip_gain(atmos, slot, 0.25).result(timeout=5)   # ~-12 dB
                except Exception: pass
                ch.set_clip_loop(atmos, slot, True).result(timeout=5)
                ch.set_clip_name(atmos, slot, fname.replace('.mp3','')).result(timeout=5)
                print(f'  ATMOS slot {slot}: {fname}  warp_mode={wmode}  gain=-12dB  loop=True')
            except Exception as e:
                print(f'  ATMOS slot {slot} fail: {e}')

        # 3. FX slot 4 (RAGGA_FILL) — vinyl scratch one-shot
        print('\n--- FX slot 4 ← BBC vinyl scratch one-shot ---')
        try:
            try: ch.clear_clip(T_FX, S_RAGGA_FILL).result(timeout=3); time.sleep(0.1)
            except Exception: pass
            ch.load_audio_to_slot(T_FX, S_RAGGA_FILL, BBC_DIR, 'BBC_vinyl_scratch.mp3').result(timeout=20)
            time.sleep(0.4)
            ch.set_clip_warp(T_FX, S_RAGGA_FILL, warping=False).result(timeout=5)
            ch.set_clip_loop(T_FX, S_RAGGA_FILL, False).result(timeout=5)
            ch.set_clip_name(T_FX, S_RAGGA_FILL, 'BBC_vinyl_scratch').result(timeout=5)
            print('  FX slot 4: vinyl scratch one-shot (warp off, loop off)')
        except Exception as e:
            print(f'  FX slot 4 fail: {e}')

        # 4. audition all 5 scenes to hear the atmos layer in context
        print('\n--- audition all scenes with ATMOS underneath ---')
        ch.stop_all_clips().result(timeout=3); time.sleep(0.2)
        for i, n in enumerate(['DUB_IN','STEPPER','RAGGAJUNGLE','DUBOUT','RAGGA_FILL']):
            print(f'  fire {i} {n}')
            ch.fire_scene(i).result(timeout=3)
            time.sleep(11.5)
        ch.stop_all_clips().result(timeout=3)
    finally:
        ch.stop()


if __name__ == '__main__':
    main()
