"""Print all 15 scenes consecutively into the arrangement, 4 bars each
at their baked per-scene tempos.

v2: aligns scene fires to song_time (project beat counter) instead of
wall-clock. Each scene is fired when song_time crosses the expected
beat boundary, which immunises against quantization slippage between
scenes. Plus an 8-bar tail at the end so the last scene's clips
record fully before stop_playback.

Two flourishes preserved:
  • vinyl scratch on the &-of-4 of scene 5 (the dub→ska tempo jump)
  • vinyl scratch on the &-of-4 of scene 11 (into AMEN_BREAKDOWN)
"""
from __future__ import annotations
import os, time
os.environ.setdefault('LIVE_CHANNEL_ENABLED', '1')

from thelmic.live_channel import LiveChannel

SCENE_TEMPOS = [
    87, 87, 87, 87, 87, 87,
    140, 150,
    174, 174,
    180, 180,
    180, 180, 180,
]
SCENE_NAMES = [
    'DUB_IN', 'STEPPER', 'RAGGAJUNGLE', 'DUBOUT', 'RAGGA_FILL', 'WURLY_REMIX',
    'SKA_PIVOT', 'PUNK_BURN',
    'HARDCORE_DROP', 'DNB_FULL',
    'KICK_4OTF', 'KICK_4OTF_ghost',
    'AMEN_BREAKDOWN', 'AMEN_REBUILD', 'HARDCORE_FULL',
]
BARS_PER_SCENE = 4
BEATS_PER_SCENE = BARS_PER_SCENE * 4   # 16
TAIL_BARS = 8         # generous tail so last scene records fully
POLL_INTERVAL = 0.05  # 50ms — fine enough at 180 bpm
T_FX = 8


def get_song_time(ch) -> float:
    """Project beat counter via get_listener_snapshot."""
    s = ch.get_listener_snapshot().result(timeout=2)
    return float(s.get('current_song_time', 0.0) or 0.0)


def wait_until_song_time(ch, target_beat: float, deadline: float) -> bool:
    while True:
        st = get_song_time(ch)
        if st >= target_beat:
            return True
        if time.monotonic() > deadline:
            return False
        time.sleep(POLL_INTERVAL)


def main():
    ch = LiveChannel(); ch.start(); time.sleep(0.7)
    try:
        # ---- prep ----
        ch.stop_all_clips().result(timeout=3); time.sleep(0.2)
        ch.back_to_arrangement().result(timeout=3); time.sleep(0.1)
        ch.set_song_time(0.0).result(timeout=3); time.sleep(0.1)
        ch.set_tempo(float(SCENE_TEMPOS[0])).result(timeout=3); time.sleep(0.1)

        ch.set_session_record(True).result(timeout=3)
        ch.set_record_mode(True).result(timeout=3)
        time.sleep(0.2)

        ch.start_playback().result(timeout=3)
        time.sleep(0.15)
        print('=== printing arc 0..14 (song-time aligned) ===')

        wall_start = time.monotonic()
        for scene, (bpm, name) in enumerate(zip(SCENE_TEMPOS, SCENE_NAMES)):
            target_beat = scene * BEATS_PER_SCENE
            # generous wall-clock cap = 2× the expected scene length
            cap = wall_start + (scene + 2) * BEATS_PER_SCENE * 60.0 / 87.0 * 2
            if scene > 0:
                ok = wait_until_song_time(ch, float(target_beat), cap)
                if not ok:
                    print(f'  WARN: scene {scene} fire delayed past wall-clock cap')
            info = ch.get_session_info().result(timeout=2)
            st = info.get('song_time', '?')
            print(f'  fire {scene:2d} {name:18s} @ {bpm} bpm  song_time={st}')
            ch.fire_scene(scene).result(timeout=3)
            # flourishes — fire on bar-3.5 of scenes 5 and 11
            if scene in (5, 11):
                # wait until 3.5 bars into the scene = target_beat + 14 beats
                flourish_at = target_beat + 14.0
                wait_until_song_time(ch, flourish_at, cap)
                try:
                    ch.fire_clip(T_FX, 4).result(timeout=2)
                    print(f'    + vinyl scratch flourish at song_time≈{flourish_at}')
                except Exception as e:
                    print(f'    flourish fail: {e}')

        # ---- tail: let the last scene complete then keep recording 8 more bars ----
        last_scene_end = len(SCENE_TEMPOS) * BEATS_PER_SCENE
        tail_target = last_scene_end + TAIL_BARS * 4
        print(f'\n  recording tail to beat {tail_target} ({TAIL_BARS} bars at 180 bpm = {TAIL_BARS * 4 * 60 / 180:.1f}s)')
        # generous cap
        cap = time.monotonic() + 30.0
        wait_until_song_time(ch, float(tail_target), cap)

        # ---- finalise ----
        ch.stop_playback().result(timeout=3); time.sleep(0.3)
        ch.set_session_record(False).result(timeout=3)
        ch.set_record_mode(False).result(timeout=3)
        ch.stop_all_clips().result(timeout=3); time.sleep(0.2)
        ch.back_to_arrangement().result(timeout=3); time.sleep(0.1)
        ch.set_song_time(0.0).result(timeout=3)
        ch.set_tempo(87.0).result(timeout=3)
        info = ch.get_session_info().result(timeout=2)
        print(f'\n=== printed; final song_time={info.get("song_time")}, tempo back to 87 ===')
    finally:
        ch.stop()


if __name__ == '__main__':
    main()
