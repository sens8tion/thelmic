"""JUNGLE SUB AUDITION - three subs that are known to be jungle, next to F-HOLE, to switch between.

The user found the bare Operator sine wasn't doing it. What the forums and press say jungle producers used
(Gearspace, KVR, Dogs On Acid, Attack Magazine, MusicRadar, 2026-09-17 search):
  BOOM-ERANG    an 808 bass drum played as a sub from a sampler, long release (Core Library "Sub 808 Bass")
  TONE-DEAF     the Akai sampler's sine test tone: a sine rendered at 22.05 kHz and 12 bits, in Simpler
  WOBBLE-BOARD  the old-school wobbly sine: two sines detuned so they beat, pushed into a soft shaper

Each is a copy of F-HOLE, so it has the same six row clips and the same effects after the instrument; the row
tone envelopes are cleared (they were Operator's). The copies start MUTED: to hear one, unmute it and mute
F-HOLE. Nothing is launched or stopped, so it's safe while the grid plays. Levels are not matched on the
meter (that needs playback); each starts 4 dB under F-HOLE.

    python scripts/jungle_sub_audition.py
"""
from __future__ import annotations

import math
import os
import sys
import time
import wave

import numpy as np

os.environ.setdefault("LIVE_CHANNEL_ENABLED", "1")
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(SCRIPTS_DIR))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from jungle_reset import index_of, track_names  # noqa: E402

USER_LIB = r"C:\Users\eric\Documents\Ableton\User Library"
TONE_DIR = os.path.join(USER_LIB, "Samples", "Imported", "jungle_subs")
TONE_BROWSER = "user_library/Samples/Imported/jungle_subs"
TONE_FILE = "akai_test_tone_F#0.wav"
FS0_HZ = 440.0 * 2 ** ((30 - 69) / 12)          # 46.25 Hz
ROWS = 6
SAFETY_DB = -4.0


def render_test_tone():
    path = os.path.join(TONE_DIR, TONE_FILE)
    if os.path.exists(path):
        return path
    os.makedirs(TONE_DIR, exist_ok=True)
    sr, secs = 22050, 2.5
    t = np.arange(int(sr * secs)) / sr
    x = 0.89 * np.sin(2 * math.pi * FS0_HZ * t)
    fade = int(0.02 * sr)
    x[-fade:] *= np.linspace(1.0, 0.0, fade)
    x = np.round(x * 2047) / 2047                   # 12 bits, as the S950 stores it
    pcm = (x * 32767).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())
    return path


def devices(ch, t):
    return ch.get_track_info(t).result(timeout=5)["devices"]


def wait_for(ch, t, pred, timeout=30.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        devs = devices(ch, t)
        if pred(devs):
            return devs
        time.sleep(0.25)
    raise SystemExit(f"track {t}: device load timed out ({[d['name'] for d in devices(ch, t)]})")


def copy_of_fhole(ch, name):
    """A muted copy of F-HOLE called `name`, placed after F-HOLE and any earlier copies; None if it exists."""
    if name in track_names(ch):
        return None
    src = index_of(ch, "F-HOLE")
    ch.duplicate_track(src).result(timeout=90)
    t = src + 1
    ch.set_track_name(t, name).result(timeout=3)
    ch.set_track_mute(t, True).result(timeout=3)
    for row in range(ROWS):
        for pname in ("Pe Amount", "Osc-B Level", "Shaper Mix"):
            try:
                ch.clear_clip_envelope(t, row, t, 0, pname).result(timeout=5)
            except Exception:
                pass
    return t


def swap_instrument(ch, t, load):
    """Delete the Operator at the head of the chain, load a new instrument, and make sure it sits first."""
    if devices(ch, t)[0]["name"] == "Operator":
        ch.delete_device(t, 0).result(timeout=10)
    before = len(devices(ch, t))
    load()
    devs = wait_for(ch, t, lambda d: len(d) > before)
    effects = {"Utility", "EQ Eight", "Compressor", "LEVEL"}
    new = next(d["index"] for d in devs if d["name"] not in effects)
    if new != 0:
        ch.move_device(t, new, 0).result(timeout=10)
    return devices(ch, t)


def trim_level(ch, t, fhole_db):
    from jungle_space import set_number
    d = next(x["index"] for x in devices(ch, t) if x["name"] == "LEVEL")
    return set_number(ch, t, d, "Output", fhole_db + SAFETY_DB)


def main():
    from thelmic.live_channel import LiveChannel
    from jungle_space import set_number, set_string, _param
    render_test_tone()
    ch = LiveChannel(lower_priority=False)
    ch.start()
    try:
        if "F-HOLE" not in track_names(ch):
            raise SystemExit("F-HOLE and TONE-DEAF were dropped on 2026-09-17; BOOM-ERANG and WOBBLE-BOARD are "
                             "the subs left to audition. Nothing to copy from.")
        fh = index_of(ch, "F-HOLE")
        level = next(x["index"] for x in devices(ch, fh) if x["name"] == "LEVEL")
        from jungle_sidechain import parse_display
        fhole_db = float(parse_display(_param(ch, fh, level, "Output")["display"]))

        # WOBBLE-BOARD first: it keeps its Operator
        t = copy_of_fhole(ch, "WOBBLE-BOARD")
        if t is not None:
            for pname, target in (("Algorithm", "Alg. 11"), ("Osc-B On", "On"), ("Osc-B Wave", "Sine")):
                set_string(ch, t, 0, pname, target)
            for pname, raw in (("B Coarse", 1.0), ("Osc-B Level", 1.0), ("Be Sustain", 1.0), ("Shaper Type", 1.0),
                               ("Shaper Mix", 45.0), ("Pe Amount", 1.0)):
                ch.set_device_param(t, 0, _param(ch, t, 0, pname)["index"], raw).result(timeout=5)
            for pname, target in (("B Fine", 22.0), ("Be Attack", 3.0), ("Be Release", 80.0), ("Shaper Drive", 6.0),
                                  ("Volume", float(parse_display(_param(ch, t, 0, "Volume")["display"])) - 6.0)):
                set_number(ch, t, 0, pname, target)
            shown = {k: _param(ch, t, 0, k)["display"] for k in ("Algorithm", "B Coarse", "B Fine", "Osc-B Level",
                                                                  "Shaper Mix", "Volume")}
            print(f"  WOBBLE-BOARD  {shown}  level {trim_level(ch, t, fhole_db)}")

        t = copy_of_fhole(ch, "TONE-DEAF")
        if t is not None:
            devs = swap_instrument(ch, t, lambda: ch.load_item_at_path(t, TONE_BROWSER, TONE_FILE).result(timeout=30))
            params = {p["name"]: p for p in ch.get_device_info(t, 0).result(timeout=10)["parameters"]}
            # Simpler plays the sample at its own pitch on C3 (60): +30 st puts F#0 on F#0 (MIDI 30)
            ch.set_device_param(t, 0, params["Transpose"]["index"], 30.0).result(timeout=5)
            for pname, ms in (("Ve Attack", 3.0), ("Ve Release", 80.0)):
                if pname in params:
                    set_number(ch, t, 0, pname, ms)
            shown = {k: _param(ch, t, 0, k)["display"] for k in ("Transpose", "Ve Attack", "Ve Release") if k in params}
            print(f"  TONE-DEAF     {devs[0]['name']} {shown}  level {trim_level(ch, t, fhole_db)}")

        t = copy_of_fhole(ch, "BOOM-ERANG")
        if t is not None:
            devs = swap_instrument(ch, t, lambda: ch.load_item_at_path(
                t, "packs/Core Library/Devices/Instruments/Simpler/Bass", "Sub 808 Bass.adv").result(timeout=30))
            # the preset's sample (Kick 808 1) settles at 46.9 Hz, F#0 +25 ct, after a drop from ~51 Hz; the preset's
            # own +30 st already puts it on F#0, so only the cents need pulling in
            set_number(ch, t, 0, "Detune", -25.0)
            params = {p["name"]: p.get("display") for p in ch.get_device_info(t, 0).result(timeout=10)["parameters"]}
            shown = {k: params[k] for k in ("Transpose", "Detune", "Ve Attack", "Ve Release") if k in params}
            print(f"  BOOM-ERANG    {devs[0]['name']} {shown}  level {trim_level(ch, t, fhole_db)}")

        for name in ("F-HOLE", "BOOM-ERANG", "TONE-DEAF", "WOBBLE-BOARD"):
            i = index_of(ch, name)
            info = ch.get_track_info(i).result(timeout=5)
            print(f"  {name:<13} muted {info.get('mute')} | {' > '.join(d['name'] for d in info['devices'])}")
    finally:
        ch.stop()


if __name__ == "__main__":
    main()
