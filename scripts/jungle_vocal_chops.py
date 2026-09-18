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

Cuts come from the renderer's own note boundaries, which are its word boundaries (see `cut`).

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
# The calls on the root, 6 takes each on the CPU. Picked on the transcriber AND per-word levels:
# where it ranked a take with a word 14-19 dB under the rest, an even take heard the same won.
TAKES = {"hop-ah": "call-hop-ah-85bpm-150339.wav",                # the strongest th, no faults (roll 2)
         "bump-ooh": "call-bump-ooh-85bpm-150339.wav",            # "Bump who are like that?" - th strong, no faults (roll 4)
         "bubble-now": "call-bubble-now-85bpm-145401.wav",        # "bubble now bubble" (5 of 6 exact)
         "bump-to-the-mix": "call-bump-to-the-mix-85bpm-145401.wav"}  # "Bump to the mixer" (roll 1): the chop trims the er
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
    # the user: "bump to the mix" - bump is already on 41; the rest plays after it
    51: ("bump-to-the-mix", ["to", "the", "mix"], "to-the-mix"),
    52: ("bump-to-the-mix", ["mix"], "mix"),
    53: ("bump-to-the-mix", None, "bump-to-the-mix"),
}
# Chop files are named for their set, and a pad holding an older cut of the same chop is swapped
# with its settings kept. "root": the calls sung on F#3, cut on the renderer's own note boundaries.
# Earlier sets (melodic takes; v2 kept the consonant, v3 lifted "now") are in git.
SET = "root"


def chop_file(note, name):
    return f"{note:02d}-{name}-{SET}.wav"


# A word opening on a continuant can start far under its own vowel: "now" was sung as a swell, 27 dB
# under its peak, and read as "ow" on a pad; on the root takes the h of "hop" and the th of "that"
# start 40-46 dB under. Such an onset is lifted to LIFT_TARGET_DB under the peak (at most
# LIFT_MAX_DB) - about where a fricative sits beside its vowel in speech - and eased out over the
# LIFT_RAMP_S before the vowel arrives. Eased out AFTER it, the lift raised the vowel too and the
# consonant stayed exactly as far under it. Stops (b, p, t, k) are left alone: their quiet
# part is the closure, and lifting that adds a hum.
CONTINUANT = {"n", "m", "ng", "l", "r", "w", "y", "dh", "th", "s", "z", "sh", "zh", "f", "v", "hh"}
LIFT_TARGET_DB, LIFT_MAX_DB = -18.0, 18.0
VOWEL_WITHIN_DB, LIFT_RAMP_S = 12.0, 0.03


def _frames_db(y, sr, frame_s):
    win = int(frame_s * sr)
    return np.array([20 * np.log10(max(float(np.sqrt(np.mean(y[k:k + win] ** 2))), 1e-12))
                     for k in range(0, len(y) - win + 1, win)])


def onset_under_peak(y, sr):
    """dB of the first 30 ms of sound under the chop's loudest 10 ms."""
    db = _frames_db(y, sr, 0.01)
    peak = db.max()
    on = int(np.nonzero(db > peak - 45)[0][0])
    return float(db[on:on + 3].mean() - peak)


def vowel_arrives(y, sr):
    """Seconds until the first 10 ms within VOWEL_WITHIN_DB of the chop's loudest."""
    db = _frames_db(y, sr, 0.01)
    return float(np.nonzero(db > db.max() - VOWEL_WITHIN_DB)[0][0]) * 0.01


def lift_onset(y, sr, db, until_s):
    """`db` of gain, down to none over the LIFT_RAMP_S that ends at `until_s`, in dB."""
    t = np.arange(len(y))
    ramp = np.clip((t - int((until_s - LIFT_RAMP_S) * sr)) / (LIFT_RAMP_S * sr), 0.0, 1.0)
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
QUIET_DB = -55.0    # silence, under the take's peak: the weakest consonant sits above it
FLOOR_DB = -40.0    # where a word has stopped ringing (the rests hold breaths at about this)
PRE_S = 0.06        # how far before its note a word may start sounding: the model anticipates
TAIL_S = 0.08       # how far past its note a word may ring into a rest
UNVOICED_END = {"s", "k", "t", "p", "f", "th", "sh", "ch", "hh"}


def _unvoiced_end(x, sr, stop, floor_db, hiss_hz=4000.0):
    """Where the final unvoiced sound (s, k, t, p...) stops, searching back from `stop`: the renderer
    can add a voiced schwa after it - "mix" came back as "mixer" in most takes, with ~90 ms of
    low, voiced sound after the s."""
    win = int(FRAME_S * sr)
    peak = float(np.abs(x).max()) or 1e-9
    for k in range(stop - 2 * win, max(0, stop - int(0.3 * sr)), -win):
        seg = x[k:k + 2 * win]
        if 20 * np.log10(max(np.sqrt(np.mean(seg ** 2)), 1e-12) / peak) <= floor_db:
            continue
        mag = np.abs(np.fft.rfft(seg * np.hanning(len(seg))))
        centroid = (mag * np.fft.rfftfreq(len(seg), 1 / sr)).sum() / max(mag.sum(), 1e-9)
        if centroid > hiss_hz:
            return min(stop, k + 2 * win)
    return stop


def cut(x, sr, spans, first, last, unvoiced_end=False):
    """Samples [i, j) for the words spans[first..last] (from `windows`), on the renderer's timeline.

    The renderer fits every phoneme of a word inside its note (render.py, durations_and_f0), so a
    note's boundaries are its word's: however quiet the consonant, it starts at the note. Cutting
    where the sound crossed a level instead lost the quiet ones - the "th" of "this", the "n" of
    "now". After a rest a word may begin sounding a little early, so walk back to silence (at most
    PRE_S); where words run together, cut at the boundary. At the end, ring on into a rest until the
    sound drops under the floor (at most TAIL_S), and trim a vowel grown after an unvoiced ending.
    """
    peak = float(np.abs(x).max()) or 1e-9
    win = int(FRAME_S * sr)

    def level(k0, k1):
        return 20 * np.log10(max(float(np.sqrt(np.mean(x[k0:k1] ** 2))), 1e-12) / peak)

    a, b = spans[first][1], spans[last][2]
    i, j = int(round(a * sr)), int(round(b * sr))
    prev_end = spans[first - 1][2] if first > 0 else 0.0
    if a - prev_end > 0.02:                                  # after a rest
        lo = max(int(prev_end * sr), i - int(PRE_S * sr))
        while i - win >= lo and level(i - win, i) > QUIET_DB:
            i -= win
    nxt = spans[last + 1][1] if last + 1 < len(spans) else None
    if nxt is None or nxt - b > 0.02:                        # into a rest
        hi = min(len(x), j + int(TAIL_S * sr))
        if nxt is not None:
            hi = min(hi, int(nxt * sr) - int(PRE_S * sr))    # leave the next word its run-up
        while j + win <= hi and level(j, j + win) > FLOOR_DB:
            j += win
    if unvoiced_end:
        j = _unvoiced_end(x, sr, j, FLOOR_DB)
    return i, min(j, len(x))


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
        notes = CALLS[call][0]
        spans = windows(notes, RENDER_BPM)
        idx = list(range(len(spans))) if words is None else [k for k, s_ in enumerate(spans) if s_[0] in words]
        first, last = idx[0], idx[-1]
        opening = next(n_ for n_ in notes if n_.get("word") == spans[first][0])["phonemes"][0]
        closing = [n_ for n_ in notes if n_.get("word") == spans[last][0]][-1]["phonemes"][-1]
        i, j = cut(x, sr, spans, first, last, unvoiced_end=closing in UNVOICED_END)
        seg = x[i:j].copy()
        lift = 0.0
        if opening in CONTINUANT:
            lift = float(np.clip(LIFT_TARGET_DB - onset_under_peak(seg, sr), 0.0, LIFT_MAX_DB))
            if lift >= 1.0:
                seg = lift_onset(seg, sr, lift, vowel_arrives(seg, sr))
        y = fade(wsola(seg, ratio, sr) if ratio != 1.0 else seg, sr)
        y *= 0.89 / max(1e-9, float(np.abs(y).max()))
        path = out_dir / chop_file(note, name)
        if path.exists() and only_missing:
            made[note] = path             # loaded on a pad, and Live holds it open: never rewrite
            continue
        write(path, y, sr)
        made[note] = path
        print(f"  pad {note}  {name:<22} {len(y) / sr * 1000:5.0f} ms  ({folder})"
              + (f"  onset lifted {lift:.0f} dB" if lift >= 1.0 else ""))
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
