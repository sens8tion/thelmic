"""JUNGLE VOCAL CHOPS - the calls cut into words, at the track's tempo, for a Drum Rack.

The calls are rendered unhurried at 85 BPM (words starve when rendered at 170) and need to play at
170. Live's warp would do it on a clip, but a pad plays a sample, the bridge has no warp-marker
control, and Live's auto-warp guesses a short one-shot's tempo. So the 2x time-compression is done
here, with WSOLA: each output grain is taken from wherever in the input best continues the previous
one, so a single clean voice keeps its pitch and formants. Every chop lands on its pad already at
170, exactly.

Measured through the blind transcriber, before and after: "bubble, now bubble" heard perfectly
both ways, "hop, ah" unchanged. "bump, ooh" is misheard after ("I don't know who"), and two
refinements - keeping the first 35 ms uncompressed, and compressing word by word - did no better
and cost "bubble" its legibility. At about a second long the transcriber may be the limit, not the
audio: the user's ear decides.

Cuts come from the score's own timing, tightened to where the word actually sounds.

    python scripts/jungle_vocal_chops.py             # write the chops, check legibility survived
    python scripts/jungle_vocal_chops.py --kit       # both kits: MOUTH-OFF (at 170), BIG-MOUTH (as sung)
"""
from __future__ import annotations

import math
import os
import sys
import wave
from pathlib import Path

import numpy as np

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO = Path(SCRIPTS_DIR).parent
sys.path.insert(0, str(REPO))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from jungle_vocal import CALLS, KEPT  # noqa: E402
from jungle_vocal_takes import read_wav, windows  # noqa: E402

RENDER_BPM, TRACK_BPM = 85.0, 170.0
_IMPORTED = Path(r"C:\Users\eric\Documents\Ableton\User Library\Samples\Imported")
CHOP_DIR = _IMPORTED / "jungle_vocal_chops"
CHOP_BROWSER = "user_library/Samples/Imported/jungle_vocal_chops"
# Two kits side by side, same pads, for comparison (the user: "they may be too short... all the chops
# twice as long"): the chops compressed to the track's 170, and the same cuts as sung, uncompressed.
KITS = {
    "MOUTH-OFF": (RENDER_BPM / TRACK_BPM, "jungle_vocal_chops"),
    "BIG-MOUTH": (1.0, "jungle_vocal_chops_long"),
}
TAKES = {"hop-ah": "call-hop-ah-85bpm-104852.wav", "bump-ooh": "call-bump-ooh-85bpm-104852.wav",
         "bubble-now": "call-bubble-now-85bpm-104406.wav"}
# pad note -> (call, words the chop spans, name). Push's 4x4 starts at 36: words low, whole calls up top.
PADS = {
    36: ("hop-ah", ["hop"], "hop"),
    37: ("hop-ah", ["ah"], "ah"),
    38: ("hop-ah", ["a", "like", "this"], "a-like-this"),
    39: ("hop-ah", ["like"], "like"),
    40: ("hop-ah", ["this"], "this"),
    41: ("bump-ooh", ["bump"], "bump"),
    42: ("bump-ooh", ["ooh"], "ooh"),
    43: ("bump-ooh", ["a", "like", "that"], "a-like-that"),
    44: ("bump-ooh", ["that"], "that"),
    45: ("bubble-now", ["bubble"], "bubble"),
    46: ("bubble-now", ["now"], "now"),
    47: ("bubble-now", ["bubble2"], "bubble-down"),
    48: ("hop-ah", None, "hop-ah-a-like-this"),
    49: ("bump-ooh", None, "bump-ooh-a-like-that"),
    50: ("bubble-now", None, "bubble-now-bubble"),
}


def wsola(x, ratio, sr, frame_ms=25.0, tolerance_ms=6.0):
    """Time-scale `x` by `ratio` (output length / input length) without changing pitch."""
    n = int(frame_ms / 1000 * sr) // 2 * 2
    hs = n // 2                           # output hop
    ha = hs / ratio                       # input hop
    tol = int(tolerance_ms / 1000 * sr)
    win = np.hanning(n)
    pad = np.concatenate([np.zeros(n + tol), x, np.zeros(2 * n + tol)])
    out_len = int(len(x) * ratio) + n
    y = np.zeros(out_len + n)
    norm = np.zeros(out_len + n)
    prev = n + tol                        # where the last chosen input frame started
    k = 0
    while True:
        out_pos = k * hs
        nominal = int(n + tol + k * ha)
        if out_pos >= out_len or nominal + n + tol >= len(pad):
            break
        if k == 0:
            best = nominal
        else:
            target = pad[prev + hs:prev + hs + n]        # the natural continuation of the last grain
            lo = nominal - tol
            seg = pad[lo:lo + n + 2 * tol]
            corr = np.correlate(seg, target, mode="valid")
            best = lo + int(np.argmax(corr))
        y[out_pos:out_pos + n] += pad[best:best + n] * win
        norm[out_pos:out_pos + n] += win
        prev = best
        k += 1
    y = y[:out_len] / np.maximum(norm[:out_len], 1e-3)
    return y[:int(len(x) * ratio)]


def tighten(x, sr, a, b, floor_db=-40.0):
    """The part of [a, b) that actually sounds, with a little air before the attack."""
    i, j = int(a * sr), int(b * sr)
    seg = x[i:j]
    if not len(seg):
        return i, j
    win = int(0.005 * sr)
    rms = np.array([np.sqrt(np.mean(seg[k:k + win] ** 2)) for k in range(0, max(1, len(seg) - win), win)])
    peak = float(np.abs(x).max()) or 1e-9
    on = np.nonzero(20 * np.log10(np.maximum(rms, 1e-12) / peak) > floor_db)[0]
    if not len(on):
        return i, j
    start = max(0, i + on[0] * win - int(0.004 * sr))
    end = min(len(x), i + (on[-1] + 1) * win + int(0.02 * sr))
    return start, end


def fade(y, sr, in_ms=2.0, out_ms=12.0):
    a, b = int(in_ms / 1000 * sr), int(out_ms / 1000 * sr)
    if len(y) > a + b:
        y[:a] *= np.linspace(0, 1, a)
        y[-b:] *= np.linspace(1, 0, b)
    return y


def write(path: Path, y, sr):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((np.clip(y, -1, 1) * 32767).astype("<i2").tobytes())


def build(ratio=RENDER_BPM / TRACK_BPM, folder="jungle_vocal_chops", only_missing=False):
    out_dir = _IMPORTED / folder
    out_dir.mkdir(parents=True, exist_ok=True)
    made = {}
    for note, (call, words, name) in PADS.items():
        x, sr = read_wav(KEPT / TAKES[call])
        spans = windows(CALLS[call][0], RENDER_BPM)
        if words is None:
            a, b = spans[0][1], spans[-1][2]
        else:
            chosen = [s for s in spans if s[0] in words]
            a, b = chosen[0][1], chosen[-1][2]
        i, j = tighten(x, sr, a, b)
        y = fade(wsola(x[i:j], ratio, sr) if ratio != 1.0 else x[i:j].copy(), sr)
        y *= 0.89 / max(1e-9, float(np.abs(y).max()))
        path = out_dir / f"{note:02d}-{name}.wav"
        if path.exists() and only_missing:
            made[note] = path             # loaded on a pad, and Live holds it open: never rewrite
            continue
        write(path, y, sr)
        made[note] = path
        print(f"  pad {note}  {name:<22} {len(y) / sr * 1000:5.0f} ms  ({folder})")
    return made


def check_legibility():
    """The whole-call chops, before and after compression, through the blind transcriber."""
    import subprocess
    from thelmic.sources import vocal
    py = vocal.root() / ".venv" / "Scripts" / "python.exe"
    for note, (call, words, name) in PADS.items():
        if words is not None:
            continue
        truth = CALLS[call][1]
        for label, path in (("at 85", KEPT / TAKES[call]), ("at 170", CHOP_DIR / f"{note:02d}-{name}.wav")):
            r = subprocess.run([str(py), str(vocal.root() / "bench" / "intelligibility.py"), "--truth", truth,
                                "--model", "base.en", "--download-root", str(vocal.root() / "tools" / "_whisper"),
                                str(path)], capture_output=True, text=True)
            heard = next((ln.split("heard :", 1)[-1].strip() for ln in r.stdout.splitlines() if "heard" in ln), "?")
            wer = next((ln.split(":", 1)[1].strip() for ln in r.stdout.splitlines() if "WER" in ln and ":" in ln), "?")
            print(f"  {name:<22} {label:<7} WER {wer:<8} heard {heard}")


LEVEL_DB = -8.0          # unmatched on the meter (the user is playing): start low


def kit(TRACK="MOUTH-OFF", folder="jungle_vocal_chops"):
    """Put the chops on a Drum Rack on a new track. Additive only: an existing track or pad is left
    exactly as the user has it; playback is never stopped."""
    os.environ.setdefault("LIVE_CHANNEL_ENABLED", "1")
    import time
    from thelmic.live_channel import LiveChannel
    from jungle_drumkits import DRUM_RACK, _load_pad, _pad_device
    from jungle_build import fade_raw
    from jungle_reset import index_of, track_names
    from jungle_space import load_fx, find_device, set_number, _param
    from jungle_levels_native import ensure_level
    ch = LiveChannel(lower_priority=False)
    ch.start()
    try:
        fresh = TRACK not in track_names(ch)
        if fresh:
            t = ch.create_midi_track(-1).result(timeout=10)["index"]
            ch.set_track_name(t, TRACK).result(timeout=3)
            ch.load_device(t, DRUM_RACK).result(timeout=30)
            for _ in range(80):
                if ch.get_track_info(t).result(timeout=5)["device_count"]:
                    break
                time.sleep(0.25)
        t = index_of(ch, TRACK)
        for note, (_, _, name) in PADS.items():
            if _pad_device(ch, t, note):
                print(f"  pad {note} {name}: already loaded, left alone")
                continue
            _load_pad(ch, t, note, f"user_library/Samples/Imported/{folder}", f"{note:02d}-{name}.wav")

            def prop(key, value):
                return ch.set_drum_pad_chain_device_property(t, 0, note, key, value, 0).result(timeout=10)

            def param(key, value):
                return ch.set_drum_pad_chain_device_param(t, 0, note, float(value), param_name=key,
                                                          chain_device_index=0).result(timeout=10)
            prop("playback_mode", 1)                    # One-Shot
            try:
                prop("sample.warping", False)           # already at 170: play at the file's own rate
            except Exception as e:
                print(f"    [warn] pad {note}: warping not set ({e})")
            for key, value in (("Trigger Mode", 1), ("Fade In", fade_raw(1.0)), ("Fade Out", fade_raw(8.0)),
                               ("Snap", 0)):
                try:
                    param(key, value)
                except Exception as e:
                    print(f"    [warn] pad {note}: {key} not set ({e})")
            print(f"  pad {note} {name}")
        if fresh:
            # effects that start silent: Beat Repeat off and deterministic, crush and throw at 0%
            br = load_fx(ch, t, dict(uri="query:AudioFx#Beat%20Repeat", name="Beat Repeat"))
            for pname, raw in (("Chance", None), ("Variation", 0.0), ("Device On", 0.0)):
                p_ = _param(ch, t, br, pname)
                ch.set_device_param(t, br, p_["index"], float(p_["max"]) if raw is None else raw).result(timeout=5)
            rd = load_fx(ch, t, dict(uri="query:AudioFx#Redux", name="Redux"))
            ch.set_device_param(t, rd, _param(ch, t, rd, "Dry/Wet")["index"], 0.0).result(timeout=5)
            ec = load_fx(ch, t, dict(uri="query:AudioFx#Echo", name="Echo"))
            ch.set_device_param(t, ec, _param(ch, t, ec, "Dry Wet")["index"], 0.0).result(timeout=5)
            lv = ensure_level(ch, t, TRACK)
            set_number(ch, t, lv, "Output", LEVEL_DB)
        chain = " > ".join(d["name"] for d in ch.get_track_info(t).result(timeout=5)["devices"])
        print(f"  {TRACK}: {chain}")
    finally:
        ch.stop()


if __name__ == "__main__":
    if "--kit" in sys.argv:
        for track, (ratio, folder) in KITS.items():
            build(ratio, folder, only_missing=True)
            kit(track, folder)
    else:
        build()
        print()
        check_legibility()
