"""SAUDADE - long sung Portuguese vocal lines, in F# minor, in place of a dreamy drone.

The user: "find me a long sung high vocal to replace what might otherwise be a dreamy ethereal drone
... let's make it portuguese ... key is obviously important for that sung section".

Found on splice.com (its "portuguese" tag and key column; the connector's search has neither): Jullie
Vocals by Rhythm Paints, a female singer recorded in Copacabana. What each loop actually sings was
measured with scripts/vocal_analyse.py - the pack tags a root note only, and "vibe", tagged F#, sings
in C# major. Each is shifted into F# minor (or its relative, A major), her tuning (2-13 cents flat)
corrected, and stretched to 85 - half-time at 170 - so the long notes hang. From row FIRST_ROW down,
beside the other vocal lanes; the whole-bar ones loop as beds (16 bars at 170).

    python scripts/saudade.py            # render + place
    python scripts/saudade.py --files    # render only
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))
from rap_audition import read_wav, write_wav, wsola, FIRST_ROW  # noqa: E402

SRC = Path.home() / "Documents" / "Splice" / "Samples" / "thelmic_portuguese_2026-09-18"
OUT = Path.home() / "Documents" / "Ableton" / "User Library" / "Samples" / "Splice" / "saudade_fsm_85"
BROWSER = "user_library/Samples/Splice/saudade_fsm_85"
TRACK, AFTER = "SAUDADE", "MOUTHFUL"
TEMPO = 85.0
LEVEL_DB = -8.0

# (clip name, file, source bpm, semitones to F# minor, cents her tuning is off) - measured
LINES = [
    ("vou pro mar", "RP_JV_90_vocal_flavor_Gb.wav", 90, 0, -3),           # "I'm going to the sea" - sings F# minor
    ("te encontrar de novo", "RP_JV_85_vocal_jolt_A.wav", 85, +2, -2),     # "I want to find you again" - G major -> A
    ("derretendo meu coracao", "RP_JV_85_vocal_vibe_Gb.wav", 85, -4, -12),  # "melting my heart, like ice in the sun" - C# major -> A
    ("vocalise - lab", "RP_JV_76_vocal_lab_A.wav", 76, 0, -12),             # wordless; the most sustained (51% held); F# minor
    ("hum - strike", "RP_JV_85_vocal_strike_A.wav", 85, -3, -3),            # wordless hum; A minor -> F# minor
    ("ai ooh - mic", "RP_JV_96_vocal_mic_Gb.wav", 96, -2, -13),             # wordless; G# minor -> F# minor
]


def fft_resample(x: np.ndarray, n: int) -> np.ndarray:
    """Band-limited resample of frames x channels to n frames."""
    X = np.fft.rfft(x, axis=0)
    m = n // 2 + 1
    Y = np.zeros((m, x.shape[1]), dtype=complex)
    k = min(m, X.shape[0])
    Y[:k] = X[:k]
    return np.fft.irfft(Y, n, axis=0) * (n / len(x))


def render(src: Path, bpm: float, semitones: float, cents: float, sr_out: int | None = None) -> tuple[np.ndarray, int]:
    """Pitch by `semitones` (plus the tuning correction) and time to TEMPO, formants moving with the pitch."""
    x, sr = read_wav(src)
    ratio = 2 ** ((semitones - cents / 100) / 12)
    y = fft_resample(x, int(round(len(x) / ratio)))                 # played at sr: pitch * ratio
    target = int(round(len(x) * bpm / TEMPO))                       # the source's beats at TEMPO
    y = wsola(y, target / len(y), sr)
    return y * (0.89 / max(1e-9, float(np.abs(y).max()))), sr


def build() -> list[tuple[str, Path]]:
    OUT.mkdir(parents=True, exist_ok=True)
    made = []
    for name, f, bpm, semis, cents in LINES:
        dst = OUT / f"{Path(f).stem}__fsm_{TEMPO:.0f}.wav"
        made.append((name, dst))
        if dst.exists():
            continue
        y, sr = render(SRC / f, bpm, semis, cents)
        write_wav(dst, y, sr)
        print(f"  {name:<24} {semis:+d} st {-cents:+d} c, {bpm} -> {TEMPO:g} bpm: {len(y) / sr:5.1f} s "
              f"({len(y) / sr * TEMPO / 60:.1f} beats at {TEMPO:g})")
    return made


def place(made: list[tuple[str, Path]]) -> None:
    os.environ.setdefault("LIVE_CHANNEL_ENABLED", "1")
    import time
    from thelmic.live_channel import LiveChannel
    from jungle_reset import index_of, track_names
    from jungle_space import set_number
    from jungle_levels_native import ensure_level
    ch = LiveChannel(lower_priority=False)
    ch.start()
    try:
        fresh = TRACK not in track_names(ch)
        if fresh:
            t = ch.create_audio_track(index_of(ch, AFTER) + 1).result(timeout=10)["index"]
            ch.set_track_name(t, TRACK).result(timeout=5)
        t = index_of(ch, TRACK)
        clips = ch.get_track_clips(t).result(timeout=10)
        filled = {c.get("slot", c.get("index")) for c in (clips.get("clips", clips) if isinstance(clips, dict) else clips)}
        have = ch.get_scene_count().result(timeout=5)["count"]
        for _ in range(FIRST_ROW + len(made) - have):
            ch.create_scene(-1).result(timeout=10)
        for row, (name, path) in enumerate(made, start=FIRST_ROW):
            if row in filled:
                continue
            ch.load_audio_to_slot(t, row, BROWSER, path.name).result(timeout=30)
            for _ in range(40):
                try:
                    ch.set_clip_warp(t, row, warping=False).result(timeout=5)
                    break
                except Exception:
                    time.sleep(0.25)
            x, sr = read_wav(path)
            beats = len(x) / sr * TEMPO / 60
            if abs(beats - round(beats / 4) * 4) < 0.1:
                # whole bars: loop it as a bed. Live won't loop an unwarped clip (unwarping cleared the
                # loop), so warp in Re-Pitch, which at the file's own tempo plays the audio untouched
                ch.set_clip_warp(t, row, warping=True, warp_mode=3).result(timeout=5)
                ch.set_clip_loop(t, row, True).result(timeout=5)
            ch.set_clip_name(t, row, name).result(timeout=5)
            print(f"  {TRACK} row {row}: {name}")
        if fresh:
            lv = ensure_level(ch, t, TRACK)
            set_number(ch, t, lv, "Output", LEVEL_DB)
    finally:
        ch.stop()


if __name__ == "__main__":
    made = build()
    if "--files" not in sys.argv:
        place(made)
