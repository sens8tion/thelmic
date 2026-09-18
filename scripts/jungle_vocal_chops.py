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
# pad -> version. New names, because Live holds the old files open on the pads.
# v2: these chops lost the start of their word ("now" was heard as "ow") and are cut again, leading
#     consonant included.
# v3: "now" still read as "ow" on its own, while the same audio inside "bubble, now bubble" read
#     right. The renderer sang it as a slow swell: its first 30 ms are 27 dB under the word's peak
#     and it takes 270 ms to come within 6 dB of it - the other consonant-led chops start 6-17 dB
#     under and get there in 10-90 ms. Hit on its own over drums, only the swell is heard.
REVISED = {37: 2, 38: 2, 39: 2, 42: 2, 43: 2, 46: 3}
# pad -> dB: lift the leading consonant to where the other chops' are, then ramp the lift away over
# the swell, which stays a swell.
ONSET_LIFT = {46: 12.0}
LIFT_HOLD_S, LIFT_RAMP_S = 0.02, 0.2    # held to just past the note (the consonant sits before it)


def chop_file(note, name):
    v = REVISED.get(note, 1)
    return f"{note:02d}-{name}{f'-v{v}' if v > 1 else ''}.wav"


def lift_onset(y, sr, note_at, db):
    """`db` of gain up to `note_at` samples (+ a hold), then down to none over LIFT_RAMP_S, in dB."""
    t = np.arange(len(y))
    hold = note_at + int(LIFT_HOLD_S * sr)
    ramp = np.clip((t - hold) / (LIFT_RAMP_S * sr), 0.0, 1.0)
    return y * 10 ** (db * (1.0 - ramp) / 20)


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


FRAME_S = 0.005


def _db_frames(x, sr):
    """Level per 5 ms frame, dB below the take's peak."""
    win = int(FRAME_S * sr)
    peak = float(np.abs(x).max()) or 1e-9
    r = np.array([np.sqrt(np.mean(x[k:k + win] ** 2)) for k in range(0, len(x) - win + 1, win)])
    return 20 * np.log10(np.maximum(r, 1e-12) / peak)


def _word_start(db, fa, fb, floor_db, lookback):
    """First frame of the word whose note spans frames [fa, fb).

    Walk back from the word's first sound in its window, because the renderer puts a leading
    consonant BEFORE the note (so the vowel lands on the beat): cutting at the note took the "n" off
    "now", and the user heard "ow". Back to the silence before it; or, where words run together, to
    the deepest dip between them. Only a real dip counts: the quiet edge of the look-back is the
    previous word still rising, and taking it put the "a" on "like".
    """
    loud = np.nonzero(db[fa:fb] > floor_db)[0]
    first = fa + int(loud[0]) if len(loud) else fa
    lo = max(0, first - lookback)
    silent = np.nonzero(db[lo:first] <= floor_db)[0]
    if len(silent):
        return lo + int(silent[-1]) + 1
    # the note's own first frame is a candidate too: still falling into it ("now" into the closure
    # of "bubble") means the boundary is the note, not a ripple inside the vowel before it
    seq = db[lo:first + 1]
    dips = [k for k in range(1, len(seq)) if seq[k] <= seq[k - 1] and (k == len(seq) - 1 or seq[k] <= seq[k + 1])]
    if not dips:
        return first
    return lo + min(dips, key=lambda k: (seq[k], -k))      # deepest; on a tie, nearest the note


def tighten(x, sr, a, b, nxt=None, floor_db=-40.0, lookback_s=0.15):
    """The samples of the words whose notes span [a, b) seconds.

    Start where the first word starts sounding (its leading consonant included). End where the last
    stops sounding inside its window - the rests hold breaths at the floor, so not past it - and
    never after the next word (`nxt`, its note's (start, end)) starts, whose leading consonant sits
    before its note too.
    """
    db = _db_frames(x, sr)
    f = lambda t: min(len(db), int(round(t / FRAME_S)))
    look = int(lookback_s / FRAME_S)
    start = _word_start(db, f(a), f(b), floor_db, look)
    loud = np.nonzero(db[start:f(b)] > floor_db)[0]
    stop = int((start + int(loud[-1]) + 1) * FRAME_S * sr + 0.02 * sr) if len(loud) else int(b * sr)
    if nxt is not None:
        stop = min(stop, int(_word_start(db, f(nxt[0]), f(nxt[1]), floor_db, look) * FRAME_S * sr))
    i = max(0, int(start * FRAME_S * sr) - int(0.004 * sr))
    return i, min(stop, len(x))


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
            a, b, nxt = spans[0][1], spans[-1][2], None
        else:
            idx = [k for k, s in enumerate(spans) if s[0] in words]
            a, b = spans[idx[0]][1], spans[idx[-1]][2]
            nxt = spans[idx[-1] + 1][1:] if idx[-1] + 1 < len(spans) else None
        i, j = tighten(x, sr, a, b, nxt)
        seg = x[i:j]
        if note in ONSET_LIFT:
            seg = lift_onset(seg, sr, int(a * sr) - i, ONSET_LIFT[note])
        y = fade(wsola(seg, ratio, sr) if ratio != 1.0 else seg.copy(), sr)
        y *= 0.89 / max(1e-9, float(np.abs(y).max()))
        path = out_dir / chop_file(note, name)
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
        for label, path in (("at 85", KEPT / TAKES[call]), ("at 170", CHOP_DIR / chop_file(note, name))):
            r = subprocess.run([str(py), str(vocal.root() / "bench" / "intelligibility.py"), "--truth", truth,
                                "--model", "base.en", "--download-root", str(vocal.root() / "tools" / "_whisper"),
                                str(path)], capture_output=True, text=True)
            heard = next((ln.split("heard :", 1)[-1].strip() for ln in r.stdout.splitlines() if "heard" in ln), "?")
            wer = next((ln.split(":", 1)[1].strip() for ln in r.stdout.splitlines() if "WER" in ln and ":" in ln), "?")
            print(f"  {name:<22} {label:<7} WER {wer:<8} heard {heard}")


LEVEL_DB = -8.0          # unmatched on the meter (the user is playing): start low


def swap_sample(ch, t, note, folder, item, before):
    """A new sample on a pad that is already set up, keeping the pad exactly as it was.

    Loading a sample onto a pad gives it a fresh Simpler, which would throw away whatever the user
    has done to it. So every parameter and playback property is read first and written back after.
    Sample markers count samples of the OLD file, so a pad whose markers were moved is left alone.
    """
    import time
    from jungle_drumkits import _load_pad, _pad_device
    props = before["properties"]
    if props.get("sample.start_marker", 0) != 0 or props.get("sample.end_marker") != props.get("sample.length", 0) - 1:
        print(f"  pad {note}: its sample markers were moved - left alone, load {item} by hand")
        return False
    chain = ch.get_drum_pad_chain_info(t, 0, note).result(timeout=10)
    _load_pad(ch, t, note, f"user_library/Samples/Imported/{folder}", item)
    after = None
    for _ in range(40):
        after = _pad_device(ch, t, note)
        if after and str(after["properties"].get("sample.file_path", "")).endswith(item):
            break
        time.sleep(0.25)
    else:
        raise RuntimeError(f"pad {note}: {item} did not load")
    now_props = after["properties"]
    for key in ("playback_mode", "sample.warping"):
        if key in props and now_props.get(key) != props[key]:
            ch.set_drum_pad_chain_device_property(t, 0, note, key, props[key], 0).result(timeout=10)
    now = {p["name"]: p["value"] for p in after["parameters"]}
    restored = []
    for p_ in before["parameters"]:
        if p_["name"] in now and abs(now[p_["name"]] - p_["value"]) > 1e-6:
            ch.set_drum_pad_chain_device_param(t, 0, note, float(p_["value"]), param_name=p_["name"],
                                               chain_device_index=0).result(timeout=10)
            restored.append(p_["name"])
    chain_now = ch.get_drum_pad_chain_info(t, 0, note).result(timeout=10)
    if abs(chain_now["volume"] - chain["volume"]) > 1e-6:
        ch.set_drum_pad_chain_volume(t, 0, note, chain["volume"]).result(timeout=10)
        restored.append("chain volume")
    for key in ("panning", "mute", "sends"):
        if chain_now.get(key) != chain.get(key):
            print(f"    [warn] pad {note}: chain {key} was {chain.get(key)!r}, now {chain_now.get(key)!r} - no setter")
    # read it all back
    check = _pad_device(ch, t, note)
    got = {p["name"]: p["value"] for p in check["parameters"]}
    off = [p_["name"] for p_ in before["parameters"] if p_["name"] in got and abs(got[p_["name"]] - p_["value"]) > 1e-4]
    off += [k for k in ("playback_mode", "sample.warping") if k in props and check["properties"].get(k) != props[k]]
    print(f"  pad {note}: {item}, settings carried over ({len(restored)} rewritten)"
          + (f" - STILL DIFFERENT: {off}" if off else ""))
    return not off


def kit(TRACK="MOUTH-OFF", folder="jungle_vocal_chops"):
    """Put the chops on a Drum Rack on a new track. An existing track keeps everything the user has
    done: an empty pad is filled, a pad holding an older cut of its chop gets the new cut with its
    settings carried over, anything else is left alone. Playback is never stopped."""
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
            want = chop_file(note, name)
            have = _pad_device(ch, t, note)
            loaded = str((have or {}).get("properties", {}).get("sample.file_path", "")).replace("\\", "/").split("/")[-1]
            if have and loaded == want:
                continue
            if have and not loaded.startswith(f"{note:02d}-{name}"):
                print(f"  pad {note} {name}: holds {loaded!r}, not one of these chops - left alone")
                continue
            if have:
                swap_sample(ch, t, note, folder, want, have)
                continue
            _load_pad(ch, t, note, f"user_library/Samples/Imported/{folder}", want)

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
        build(only_missing=True)          # a chop already on a pad is held open by Live
        print()
        check_legibility()
