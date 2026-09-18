"""JUNGLE VOCAL TAKES - roll each phrase on its own, rank for legibility, and measure the faults.

Each phrase is rendered separately, several times. There is no seed, so takes differ materially;
best_of ranks them on word error rate from a blind transcriber first, tonal quality second.

The ranking catches wrong words. It does not catch the faults that make a hook unusable in a
mix, so every take is also measured here:

  words        voiced segments found vs words expected - a swallowed word shows as a missing
               segment, which is how a starved consonant fails ("over" -> "oh")
  length       each word's sounded duration; a word far shorter than its neighbours is the
               one about to vanish
  pitch        f0 per word against the note it was written on, in cents
  level        peak and whether any word sits far under the others

    python scripts/jungle_vocal_takes.py            # all four phrases
    python scripts/jungle_vocal_takes.py hop bump   # just those
"""
from __future__ import annotations

import math
import os
import re
import shutil
import sys
import time
import wave
from datetime import datetime
from pathlib import Path

import numpy as np

os.environ.setdefault("LIVE_CHANNEL_ENABLED", "1")
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO = Path(SCRIPTS_DIR).parent
sys.path.insert(0, str(REPO))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from jungle_vocal import A3, CS4, E4, FS3, KEPT, SPEAKER, phrase, session_bpm  # noqa: E402

TAKES = 10
# Render unhurried and warp to the grid in Live (the user's idea): at half the session tempo every
# word gets double the time, so nothing is starved, and one bar warps to one bar at 2x on Complex
# Pro. RENDER_BPM=None renders at the session tempo instead.
RENDER_BPM_RATIO = 0.5
# name -> (notes, the words as the transcriber should hear them, the note each word sits on)
PHRASES = {
    # "hop" from CMUdict is hh aa p - an American open vowel, heard as "hope"/"hot". ao is the
    # rounder one. "bubble" is split so each syllable gets its own note rather than blurring.
    "hop": (phrase("hop", CS4, "this"), "hop like this", [CS4, CS4, CS4 - 3]),
    "bump": (phrase("bump", CS4, "that"), "bump like that", [CS4, CS4, CS4 - 3]),
    # "lick like this" failed at every timing: "lick" and "like" are near-identical, the model
    # sang the second and swallowed the first. "it" gives the k a vowel to release into and puts
    # a different word between them. Lands on 3 like the others.
    "lick": ([{"phonemes": ["l", "ih", "k"], "midi": CS4, "beats": 0.7, "scoop": -1.6,
               "scoop_beats": 0.15, "word": "lick"},
              {"phonemes": ["ih", "t"], "midi": CS4, "beats": 0.3, "word": "it"},
              {"lyric": "like", "midi": CS4, "beats": 0.5, "word": "like"},
              {"lyric": "this", "midi": CS4 - 3, "beats": 0.5, "fall": -1.0, "fall_beats": 0.3,
               "word": "this"},
              {"rest": True, "beats": 2.0}],
             "lick it like this", [CS4, CS4, CS4, CS4 - 3]),
    "bubble": ([{"phonemes": ["b", "ah"], "midi": A3, "beats": 0.4, "scoop": -1.2,
                 "scoop_beats": 0.15, "word": "bubble"},
                {"phonemes": ["b", "ax", "l"], "midi": A3, "beats": 0.35, "word": "bubble"},
                {"lyric": "like", "midi": A3, "beats": 0.6, "word": "like"},
                {"phonemes": ["dh", "ae", "t"], "midi": FS3, "beats": 0.65, "fall": -1.0,
                 "fall_beats": 0.3, "word": "that"},
                {"rest": True, "beats": 2.0}],
               "bubble like that", [A3, A3, A3, FS3]),
}

_ROLL = re.compile(r"roll\s+(\d+)\s+WER\s+([\d.]+)%\s+flatness\s+([\d.]+)\s+voiced\s+(\d+)%\s+'(.*)'")


def read_wav(path: Path):
    with wave.open(str(path)) as w:
        sr, n, ch = w.getframerate(), w.getnframes(), w.getnchannels()
        x = np.frombuffer(w.readframes(n), dtype="<i2").astype(np.float64) / 32768.0
    if ch > 1:
        x = x.reshape(-1, ch).mean(axis=1)
    return x, sr


def segments(x, sr, floor_db=-38.0, min_ms=55, gap_ms=45):
    """Sounded stretches: frame RMS gated against the take's own peak."""
    win, hop = int(0.02 * sr), int(0.005 * sr)
    frames = [(i, np.sqrt(np.mean(x[i:i + win] ** 2))) for i in range(0, max(1, len(x) - win), hop)]
    if not frames:
        return []
    peak = max(r for _, r in frames) or 1e-9
    on = [(i, r) for i, r in frames if 20 * math.log10(max(r, 1e-12) / peak) > floor_db]
    out = []
    for i, r in on:
        if out and i - out[-1][1] <= gap_ms / 1000 * sr:
            out[-1][1] = i + win
            out[-1][2] = max(out[-1][2], r)
        else:
            out.append([i, i + win, r])
    return [(a / sr, (b - a) / sr, level) for a, b, level in out if (b - a) / sr * 1000 >= min_ms]


def f0_of(seg, sr, lo=70.0, hi=500.0):
    """Autocorrelation pitch on the steadiest part of a segment."""
    if len(seg) < sr // 40:
        return None
    half = len(seg) // 2                      # after the scoop: the first half is still approaching
    w = seg[half: half + int(0.12 * sr)] if len(seg) > int(0.18 * sr) else seg[half:] if half else seg
    w = w - w.mean()
    if not np.any(w):
        return None
    ac = np.correlate(w, w, mode="full")[len(w) - 1:]
    lo_lag, hi_lag = int(sr / hi), min(int(sr / lo), len(ac) - 1)
    if hi_lag <= lo_lag:
        return None
    lag = int(np.argmax(ac[lo_lag:hi_lag])) + lo_lag
    return sr / lag if ac[lag] > 0.25 * ac[0] else None


def cents(hz, midi):
    if not hz:
        return None
    return 1200 * math.log2(hz / (440.0 * 2 ** ((midi - 69) / 12)))


RENDER_FRAME_S = 512 / 44100      # the bank's hop at its sample rate


def windows(notes, bpm):
    """(label, start_s, end_s) per word, from the score's own timing.

    Notes carry an optional "word" key (the renderer ignores it): two notes sharing a word are
    one window, which is how "bub"+"ble" stays one word. Without it, consecutive phoneme notes
    would be merged blindly - that is what made "like" and "that" read as one 441 ms word.
    """
    beat, out, t = 60.0 / bpm, [], 0.0
    for i, n in enumerate(notes):
        # the renderer's own timeline: each note rounded to whole frames (render.py load_score),
        # which drifts ~10 ms from the beat grid within a bar
        dur = max(1, round(float(n["beats"]) * beat / RENDER_FRAME_S)) * RENDER_FRAME_S
        if n.get("rest"):
            t += dur
            continue
        label = n.get("word") or n.get("lyric") or "".join(n.get("phonemes", []))
        if out and n.get("word") and n["word"] == out[-1][0]:
            out[-1] = (out[-1][0], out[-1][1], t + dur)
        else:
            out.append((label, t, t + dur))
        t += dur
    return out


def measure(path: Path, notes, bpm, words: list[str], midis: list[int]) -> dict:
    x, sr = read_wav(path)
    peak = float(np.abs(x).max()) or 1e-9
    got = []
    for i, (label, a, b) in enumerate(windows(notes, bpm)):
        seg = x[int(a * sr):int(b * sr)]
        if not len(seg):
            continue
        win, hop = int(0.02 * sr), int(0.005 * sr)
        rms = [np.sqrt(np.mean(seg[j:j + win] ** 2)) for j in range(0, max(1, len(seg) - win), hop)]
        loud = [r for r in rms if r > peak * 0.02]          # -34 dB of the take's peak
        hz = f0_of(seg, sr)
        got.append({"word": words[i] if i < len(words) else label,
                    "sounded": len(loud) * hop / sr,
                    "window": b - a,
                    "level_db": 20 * math.log10(max(max(rms, default=0), 1e-12) / peak),
                    "hz": hz, "cents": cents(hz, midis[i]) if i < len(midis) else None})
    # the stop closure at the end of a phrase: a VOICED tail after a gap. A plosive's burst is
    # part of the word, so this needs both voicing and length before it counts.
    last_end = windows(notes, bpm)[-1][2]
    tail = x[int((last_end - 0.14) * sr):int((last_end + 0.10) * sr)]
    win, hop = int(0.02 * sr), int(0.005 * sr)
    trailing, gap = 0.0, False
    for j in range(0, max(1, len(tail) - win), hop):
        f = tail[j:j + win]
        r = np.sqrt(np.mean(f ** 2))
        voiced = np.mean(np.abs(np.diff(np.sign(f)))) / 2 * sr / 2 < 900
        if r <= peak * 0.03:
            gap = True
        elif gap and voiced:
            trailing += hop / sr
    trailing = trailing if trailing >= 0.03 else 0.0
    return {"peak": peak, "segments": got, "expected": len(words), "trailing_ms": trailing * 1000}


def faults(m: dict, words: list[str]) -> list[str]:
    """What would make a take unusable, beyond the wrong-word check the ranking already does."""
    out = []
    for s_ in m["segments"]:
        if s_["sounded"] < 0.35 * s_["window"]:
            out.append(f"{s_['word']!r} sounds for {s_['sounded'] * 1000:.0f} of "
                       f"{s_['window'] * 1000:.0f} ms")
        if s_["level_db"] < -14:
            out.append(f"{s_['word']!r} is {-s_['level_db']:.0f} dB under the take's peak")
        if s_["cents"] is not None and 60 < abs(s_["cents"]) <= 300:
            out.append(f"{s_['word']!r} is {s_['cents']:+.0f} cents off")
    if m.get("trailing_ms"):
        out.append(f"a voiced release of {m['trailing_ms']:.0f} ms after the last word (the \"uh\")")
    if m["peak"] > 0.98:
        out.append("clipped")
    return out


def remeasure(bpm):
    """Measure the takes already rendered, without rendering anything."""
    import json as _json
    from thelmic.sources._cache import cache_path
    from thelmic.sources import vocal
    for name, (notes, truth, midis) in PHRASES.items():
        words = truth.split()
        spec = vocal.VocalSpec(notes=notes, bpm=bpm, speaker=SPEAKER, takes=TAKES, truth=truth)
        key = _json.dumps({"score": spec.score(), "speaker": spec.speaker, "steps": spec.steps,
                           "ornaments": spec.ornaments, "takes": spec.takes}, sort_keys=True)
        stem = cache_path("vocal", key + "|score", "json").stem
        rolls = sorted((vocal.root() / "out" / "bestof").glob(f"{stem}-roll*.wav"))
        print(f"== {name!r} -> {truth!r}  ({len(rolls)} takes on disk)")
        for roll in rolls:
            m = measure(roll, notes, bpm, words, midis)
            line = "  ".join(f"{s_['word']}: {s_['sounded'] * 1000:3.0f}/{s_['window'] * 1000:3.0f}ms "
                             f"{s_['level_db']:5.1f}dB " + (f"{s_['cents']:+4.0f}c" if s_["cents"] is not None
                                                             and abs(s_["cents"]) <= 300 else "   -")
                             for s_ in m["segments"])
            print(f"   {roll.name[-11:-4]}  {line}")
            for f in faults(m, words):
                print(f"      ! {f}")
        print()


def main(argv=None):
    from thelmic.sources import vocal
    names = argv or sys.argv[1:] or list(PHRASES)
    if names and names[0] == "--measure":
        return remeasure(session_bpm())
    gpu = "--gpu" in names           # the operator asked for it; the GPU is shared with Live
    names = [n for n in names if n != "--gpu"] or list(PHRASES)
    session = session_bpm()
    bpm = session * RENDER_BPM_RATIO      # unhurried: warped back to the grid in Live
    KEPT.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%H%M%S")
    print(f"session {session:g} bpm; rendering at {bpm:g}, warped {1 / RENDER_BPM_RATIO:g}x onto the grid; speaker {SPEAKER}; cpu; {TAKES} takes each")
    summary = []
    for name in names:
        notes, truth, midis = PHRASES[name]
        words = truth.split()
        t0 = time.monotonic()
        try:
            sound = vocal.render(vocal.VocalSpec(notes=notes, bpm=bpm, speaker=SPEAKER,
                                                 takes=TAKES, truth=truth,
                                                 provider="dml" if gpu else "cpu"), gpu_ok=gpu)
        except Exception as e:
            print(f"{name}: {e}\n")
            summary.append((name, None, [str(e)[:120]]))
            continue
        stdout = sound.extra["stdout"]
        rolls = {int(m.group(1)): {"wer": float(m.group(2)), "flat": float(m.group(3)),
                                   "heard": m.group(5)} for m in _ROLL.finditer(stdout)}
        best = Path(sound.extra["path"])
        print(f"== {name!r} -> {truth!r}   {TAKES} takes in {time.monotonic() - t0:.0f}s")
        for i in sorted(rolls):
            roll = best.parent / f"{best.name.rsplit('-roll', 1)[0]}-roll{i:02d}.wav"
            r = rolls[i]
            flags = faults(measure(roll, notes, bpm, words, midis), words) if roll.exists() else ["take missing"]
            mark = "  <- best" if roll == best else ""
            print(f"   roll {i}  WER {r['wer']:5.1f}%  heard {r['heard']!r:<22} "
                  + ("; ".join(flags) if flags else "clean") + mark)
        kept = KEPT / f"phrase-{name}-{bpm:.0f}bpm-{stamp}.wav"
        shutil.copy2(best, kept)
        m = measure(best, notes, bpm, words, midis)
        summary.append((name, kept, faults(m, words)))
        print(f"   kept {kept.relative_to(REPO)}")
        for s_ in m["segments"]:
            c = f"{s_['cents']:+5.0f}c" if s_["cents"] is not None else "   -  "
            print(f"     {s_['word']:<7} sounds {s_['sounded'] * 1000:4.0f} of {s_['window'] * 1000:4.0f} ms"
                  f"  {s_['level_db']:5.1f} dB  {c}")
        print()
    print("== the best of each phrase")
    for name, kept, flags in summary:
        print(f"  {name:<7} {'-' if kept is None else kept.name:<28} "
              + ("; ".join(flags) if flags else "no faults found"))


if __name__ == "__main__":
    main()
