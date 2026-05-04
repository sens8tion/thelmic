"""Transport rituals — # mechanical, genre-neutral.

The arm/disarm sequence is fundamental to printing session-view content
into the arrangement timeline; not specific to any genre.
"""
from __future__ import annotations


def ms_to_beats(ms: float, bpm: float) -> float:
    return (ms / 1000.0) * (bpm / 60.0)


def hard_reset(ch) -> None:
    """Wipe lingering record/session state from any prior run; playhead 0."""
    for fn in (lambda: ch.stop_playback(),
               lambda: ch.set_record_mode(False),
               lambda: ch.set_session_record(False)):
        try: fn().result(timeout=3)
        except Exception: pass
    ch.stop_all_clips().result(timeout=3)
    ch.back_to_arrangement().result(timeout=3)
    ch.set_song_time(0.0).result(timeout=3)


def arm_take(ch, start_bar: float = 0.0, launch_quant_bars: float = 1.0,
              metronome: bool = False) -> None:
    """Arm transport-record + session-record at the given start bar.
    Run hard_reset first if there's stale state from a prior take."""
    ch.stop_playback().result(timeout=3)
    ch.stop_all_clips().result(timeout=3)
    ch.back_to_arrangement().result(timeout=3)
    ch.set_song_time(start_bar * 4.0).result(timeout=5)   # 4 beats per bar
    ch.set_record_mode(True).result(timeout=5)
    ch.set_session_record(True).result(timeout=5)
    ch.set_metronome(metronome).result(timeout=5)
    ch.set_launch_quantization(launch_quant_bars).result(timeout=5)


def disarm_take(ch, restore_quant_bars: float = 8.0) -> None:
    """Stop transport, disarm record, restore quant."""
    ch.stop_playback().result(timeout=5)
    ch.set_session_record(False).result(timeout=5)
    ch.set_record_mode(False).result(timeout=5)
    ch.set_launch_quantization(restore_quant_bars).result(timeout=5)
