"""Print the 8-scene afro-EDM arc to arrangement view.

8 scenes × 8 bars at 155 BPM, song-time-aligned. 8-bar tail.
"""
from __future__ import annotations
import os, time
os.environ.setdefault('LIVE_CHANNEL_ENABLED', '1')
from thelmic.live_channel import LiveChannel

SCENE_NAMES = ['INTRO_PULSE','INTRO_BUILD','PRE_DROP','DROP_FULL',
               'ROLL_PEAK','BREAK_HYPNOTIC','RE_BUILD','FINAL_DROP']
N_SCENES = 8
BARS_PER_SCENE = 8
BEATS_PER_SCENE = BARS_PER_SCENE * 4   # 32
TAIL_BARS = 8
BPM = 155.0
POLL = 0.05


def song_time(ch):
    s = ch.get_listener_snapshot().result(timeout=2)
    return float(s.get('current_song_time', 0.0) or 0.0)


def wait_for(ch, target, deadline):
    while True:
        if song_time(ch) >= target:
            return True
        if time.monotonic() > deadline:
            return False
        time.sleep(POLL)


def main():
    ch = LiveChannel(); ch.start(); time.sleep(0.7)
    try:
        ch.stop_all_clips().result(timeout=3); time.sleep(0.2)
        ch.back_to_arrangement().result(timeout=3); time.sleep(0.1)
        ch.set_song_time(0.0).result(timeout=3); time.sleep(0.1)
        ch.set_tempo(BPM).result(timeout=3); time.sleep(0.1)
        ch.set_session_record(True).result(timeout=3)
        ch.set_record_mode(True).result(timeout=3); time.sleep(0.2)
        ch.start_playback().result(timeout=3); time.sleep(0.15)

        print('=== printing 8 scenes ===')
        wall_start = time.monotonic()
        for s in range(N_SCENES):
            target = s * BEATS_PER_SCENE
            cap = wall_start + (s + 2) * BEATS_PER_SCENE * 60.0 / BPM * 2
            if s > 0:
                wait_for(ch, float(target), cap)
            info = ch.get_session_info().result(timeout=2)
            print(f"  fire {s} {SCENE_NAMES[s]:14s} @ {BPM} bpm  st={info.get('song_time','?')}")
            ch.fire_scene(s).result(timeout=3)

        # tail
        tail_end = N_SCENES * BEATS_PER_SCENE + TAIL_BARS * 4
        print(f"\n  tail to beat {tail_end}")
        wait_for(ch, float(tail_end), time.monotonic() + 30.0)

        ch.stop_playback().result(timeout=3); time.sleep(0.3)
        ch.set_session_record(False).result(timeout=3)
        ch.set_record_mode(False).result(timeout=3)
        ch.stop_all_clips().result(timeout=3); time.sleep(0.2)
        ch.back_to_arrangement().result(timeout=3); time.sleep(0.1)
        ch.set_song_time(0.0).result(timeout=3)
        info = ch.get_session_info().result(timeout=2)
        print(f"\n=== printed; final st={info.get('song_time')} ===")
    finally:
        ch.stop()


if __name__ == '__main__':
    main()
