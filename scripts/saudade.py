"""SAUDADE - long sung Portuguese vocal lines, in F# minor, in place of a dreamy drone.

The user: "find me a long sung high vocal to replace what might otherwise be a dreamy ethereal drone
... let's make it portuguese ... key is obviously important for that sung section".

Found on splice.com (its "portuguese" tag and key column; the connector's search has neither): Jullie
Vocals by Rhythm Paints, a female singer recorded in Copacabana. What each loop actually sings was
measured with scripts/vocal_analyse.py - the pack tags a root note only, and "vibe", tagged F#, sings
in C# major.

Pitch and time are Live's own, on the untouched originals (the user: "you've introduced artifacts. Do
it natively in ableton instead"). The first version shifted offline - an FFT resample, then a WSOLA
stretch back to length - and the WSOLA grains warbled on the held vowels. Now each clip is warped in
Complex Pro (formants kept), transposed into F# minor or its relative A major, and detuned by her
measured tuning (2-13 cents flat). Tempo is Live's auto-warp: it reads a 16-bar loop as 64 beats at
170 whatever it was recorded at, which is half-time - the long notes hang. From row FIRST_ROW down,
beside the other vocal lanes; the whole-bar ones loop as beds.

    python scripts/saudade.py
"""
from __future__ import annotations

import os
import shutil
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))
from rap_audition import FIRST_ROW  # noqa: E402

SRC = Path.home() / "Documents" / "Splice" / "Samples" / "thelmic_portuguese_2026-09-18"
LIB = Path.home() / "Documents" / "Ableton" / "User Library" / "Samples" / "Splice" / "saudade_originals"
BROWSER = "user_library/Samples/Splice/saudade_originals"
TRACK, AFTER = "SAUDADE", "MOUTHFUL"
LEVEL_DB = -8.0
COMPLEX_PRO = 6
HALF_TIME_BEATS = 64.0     # a 16-bar loop at half-time: 16 bars x 4 beats at 170
COMPLEX = 4
# The vocalise's chipmunk is baked into the sample (pitched up, formants and all). Complex Pro keeps
# formants, so an octave down in it was "a low chipmunk" that "sounds resampled" (the user); Complex
# moves the formants down with the pitch, which undoes it.
WARP_MODE = {"vocalise - lab": COMPLEX}

# (clip name, file, semitones into F# minor / A major, cents her tuning is off) - measured
LINES = [
    ("vou pro mar", "RP_JV_90_vocal_flavor_Gb.wav", 0, -3),            # "I'm going to the sea" - sings F# minor
    ("te encontrar de novo", "RP_JV_85_vocal_jolt_A.wav", +2, -2),      # "I want to find you again" - G major -> A
    ("derretendo meu coracao", "RP_JV_85_vocal_vibe_Gb.wav", -4, -12),   # "melting my heart, like ice in the sun" - C# major -> A
    ("vocalise - lab", "RP_JV_76_vocal_lab_A.wav", -12, -12),            # wordless; the most sustained (51% held); F# minor.
                                                                          # An octave down: at pitch it's chipmunk (the user) -
                                                                          # and in Complex, not Pro: see WARP_MODE
    ("hum - strike", "RP_JV_85_vocal_strike_A.wav", -3, -3),             # wordless hum; A minor -> F# minor
    ("ai ooh - mic", "RP_JV_96_vocal_mic_Gb.wav", -2, -13),              # wordless; G# minor -> F# minor
]


def mirror() -> None:
    """Live loads from its User Library, not from Splice's folder."""
    LIB.mkdir(parents=True, exist_ok=True)
    for _, f, _, _ in LINES:
        if not (LIB / f).exists():
            shutil.copy2(SRC / f, LIB / f)


def place() -> None:
    os.environ.setdefault("LIVE_CHANNEL_ENABLED", "1")
    from thelmic.live_channel import LiveChannel
    from jungle_reset import index_of, track_names
    from jungle_space import set_number
    from jungle_levels_native import ensure_level
    ch = LiveChannel(lower_priority=False)
    ch.start()
    try:
        names = {n for n, _, _, _ in LINES}
        if TRACK in track_names(ch):
            t = index_of(ch, TRACK)
            devs = [d["name"] for d in ch.get_track_info(t).result(timeout=5)["devices"]]
            clips = ch.get_track_clips(t).result(timeout=10)
            clips = clips.get("clips", clips) if isinstance(clips, dict) else clips
            got = {c.get("name") for c in clips}
            if not got <= names or not set(devs) <= {"LEVEL"}:
                raise SystemExit(f"{TRACK} holds more than this script put there ({devs}, {sorted(got)}): left alone")
            paths = [str(ch.get_clip_props(t, c.get("slot", c.get("index"))).result(timeout=5).get("file_path", ""))
                     for c in clips]
            if any("__fsm_" in p_ for p_ in paths):
                # the offline-shifted version, exactly as this script made it: replace it
                ch.delete_track(t).result(timeout=10)
                print(f"  removed the offline-shifted {TRACK} (track {t + 1})")
        if TRACK not in track_names(ch):
            t = ch.create_audio_track(index_of(ch, AFTER) + 1).result(timeout=10)["index"]
            ch.set_track_name(t, TRACK).result(timeout=5)
        t = index_of(ch, TRACK)
        clips = ch.get_track_clips(t).result(timeout=10)
        filled = {c.get("slot", c.get("index")) for c in (clips.get("clips", clips) if isinstance(clips, dict) else clips)}
        have = ch.get_scene_count().result(timeout=5)["count"]
        for _ in range(FIRST_ROW + len(LINES) - have):
            ch.create_scene(-1).result(timeout=10)
        for row, (name, f, semis, cents) in enumerate(LINES, start=FIRST_ROW):
            if row not in filled:
                ch.load_audio_to_slot(t, row, BROWSER, f).result(timeout=30)
            for _ in range(40):
                try:
                    ch.set_clip_warp(t, row, warping=True, warp_mode=WARP_MODE.get(name, COMPLEX_PRO)).result(timeout=5)
                    break
                except Exception:
                    time.sleep(0.25)
            ch.set_clip_pitch(t, row, coarse=semis, fine=-cents).result(timeout=5)
            ch.set_clip_name(t, row, name).result(timeout=5)
            props = ch.get_clip_props(t, row).result(timeout=5)
            if abs(float(props.get("length", 0)) - HALF_TIME_BEATS) < 0.01:
                ch.set_clip_loop(t, row, True).result(timeout=5)          # a 16-bar bed
            else:
                # not whole bars ("vou pro mar", 20.6 beats): auto-warp guessed 8 bars and squeezed it
                # ~20% faster. Unwarped, it plays at her own tempo - a line, not a bed, and untouched
                ch.set_clip_warp(t, row, warping=False).result(timeout=5)
            props = ch.get_clip_props(t, row).result(timeout=5)
            print(f"  row {row + 1}: {name:<24} transpose {int(props.get('pitch_coarse', 0)):+d} "
                  f"detune {int(props.get('pitch_fine', 0)):+d}"
                  f"  warp mode {props.get('warp_mode')}  {props.get('length')} beats  loop {props.get('looping')}")
        lv = ensure_level(ch, t, TRACK)
        set_number(ch, t, lv, "Output", LEVEL_DB)
    finally:
        ch.stop()


if __name__ == "__main__":
    mirror()
    place()
