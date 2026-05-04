"""Print all 15 scenes consecutively into the arrangement view, 4 bars
each, respecting their per-scene tempos. Includes a couple of fuck-about
flourishes at key transitions:
  • Vinyl scratch flourish on the bar-end of scene 5 (wurly_remix)
    bridging the hard 87→140 tempo jump into SKA_PIVOT
  • Reverse-crash-style guitar flourish on the bar-end of scene 11
    bridging into the AMEN_BREAKDOWN at 180

Uses session_record + arrangement_record so Live captures the live
session-view scene fires straight into the arrangement timeline.
"""
from __future__ import annotations
import os, time
os.environ.setdefault('LIVE_CHANNEL_ENABLED', '1')

from thelmic.live_channel import LiveChannel

# Per-scene tempo (matches what's baked via set_scene_tempo)
SCENE_TEMPOS = [
    87, 87, 87, 87, 87, 87,    # 0-5 dub + breakdown
    140, 150,                  # 6-7 ska/punk
    174, 174,                  # 8-9 hardcore_drop / dnb_full
    180, 180,                  # 10-11 KICK_4OTF lanes
    180, 180, 180,             # 12-14 amen breakdown / rebuild / hardcore_full
]
SCENE_NAMES = [
    'DUB_IN', 'STEPPER', 'RAGGAJUNGLE', 'DUBOUT', 'RAGGA_FILL', 'WURLY_REMIX',
    'SKA_PIVOT', 'PUNK_BURN',
    'HARDCORE_DROP', 'DNB_FULL',
    'KICK_4OTF', 'KICK_4OTF_ghost',
    'AMEN_BREAKDOWN', 'AMEN_REBUILD', 'HARDCORE_FULL',
]
BARS_PER_SCENE = 4
T_FX = 8     # for vinyl-scratch flourish


def beats_for_bars(bars: int) -> float:
    return float(bars * 4)


def seconds_for_bars(bars: int, bpm: float) -> float:
    return beats_for_bars(bars) * 60.0 / bpm


def main():
    ch = LiveChannel(); ch.start(); time.sleep(0.7)
    try:
        # ---- prep ----
        ch.stop_all_clips().result(timeout=3); time.sleep(0.2)
        ch.back_to_arrangement().result(timeout=3); time.sleep(0.1)
        ch.set_song_time(0.0).result(timeout=3); time.sleep(0.1)
        ch.set_tempo(float(SCENE_TEMPOS[0])).result(timeout=3); time.sleep(0.1)

        # arm session_record so session firing captures into arrangement.
        # set_record_mode is the global arrangement-record arm; both needed.
        ch.set_session_record(True).result(timeout=3)
        ch.set_record_mode(True).result(timeout=3)
        time.sleep(0.2)

        ch.start_playback().result(timeout=3)
        time.sleep(0.1)
        print('=== printing arc 0..14 → arrangement ===')

        # walk scenes
        for scene, (bpm, name) in enumerate(zip(SCENE_TEMPOS, SCENE_NAMES)):
            print(f'  fire {scene:2d} {name:18s} @ {bpm} bpm  ({BARS_PER_SCENE} bars = {seconds_for_bars(BARS_PER_SCENE, bpm):.2f}s)')
            ch.fire_scene(scene).result(timeout=3)
            dwell = seconds_for_bars(BARS_PER_SCENE, bpm)
            # ---- fuck-about flourish: vinyl scratch on the &-of-4 of last
            # bar of scene 5 (87 bpm), heralding the ska pivot ----
            if scene == 5:
                # 3.5 bars in, fire FX clip 4 (vinyl scratch one-shot)
                early = seconds_for_bars(BARS_PER_SCENE, bpm) - (60.0 / bpm) * 0.5
                time.sleep(early)
                try:
                    ch.fire_clip(T_FX, 4).result(timeout=2)
                    print(f'    + vinyl scratch flourish (FX slot 4)')
                except Exception as e:
                    print(f'    flourish fail: {e}')
                time.sleep(dwell - early)
            elif scene == 11:
                # bar-end flourish before AMEN_BREAKDOWN
                early = seconds_for_bars(BARS_PER_SCENE, bpm) - (60.0 / bpm) * 0.5
                time.sleep(early)
                try:
                    ch.fire_clip(T_FX, 4).result(timeout=2)
                    print(f'    + vinyl scratch flourish (FX slot 4)')
                except Exception as e:
                    print(f'    flourish fail: {e}')
                time.sleep(dwell - early)
            else:
                time.sleep(dwell)

        # ---- finalise ----
        time.sleep(0.5)   # brief tail to capture last scene's resonance
        ch.stop_playback().result(timeout=3); time.sleep(0.2)
        ch.set_session_record(False).result(timeout=3)
        ch.set_record_mode(False).result(timeout=3)
        ch.stop_all_clips().result(timeout=3); time.sleep(0.2)
        ch.back_to_arrangement().result(timeout=3); time.sleep(0.1)
        ch.set_song_time(0.0).result(timeout=3)
        ch.set_tempo(87.0).result(timeout=3)
        print('\n=== arrangement printed; transport reset ===')
    finally:
        ch.stop()


if __name__ == '__main__':
    main()
