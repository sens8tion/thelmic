"""JUNGLE VOCAL EMPHASIS - put the stress where you want it, after the render.

The voicebank has energy embedding switched off, so the score cannot ask for a loud word. But the
score knows exactly when every word happens, so emphasis can be applied to the rendered take:
per-word gain, ramped at the boundaries so nothing steps.

This is audio-side emphasis. It changes how loud a word is, not how it is sung - a genuinely
stressed delivery needs the emphasis written into the note (longer, higher, a deeper scoop, or a
gap before it), or the renderer's per-frame gender/velocity inputs wired up.

Gains survive warping, so apply them before the take goes into Live.

    python scripts/jungle_vocal_emphasis.py bubble +3 0 -1      # per word, in dB
    python scripts/jungle_vocal_emphasis.py bubble --lead 3     # just lift the first word
"""
from __future__ import annotations

import os
import shutil
import sys
import wave
from pathlib import Path

import numpy as np

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO = Path(SCRIPTS_DIR).parent
sys.path.insert(0, str(REPO))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from jungle_vocal import KEPT  # noqa: E402
from jungle_vocal_takes import PHRASES, RENDER_BPM_RATIO, read_wav, windows  # noqa: E402

RAMP_MS = 12.0          # long enough not to click, short enough not to smear the consonant


def emphasise(x, sr, spans, gains_db, ramp_ms=RAMP_MS):
    """Multiply each word's span by its gain, ramping in and out."""
    g = np.ones(len(x))
    ramp = max(1, int(ramp_ms / 1000 * sr))
    for (_, a, b), db in zip(spans, gains_db):
        if not db:
            continue
        i, j = int(a * sr), min(len(x), int(b * sr))
        if j <= i:
            continue
        target = 10 ** (db / 20)
        seg = np.full(j - i, target)
        n = min(ramp, (j - i) // 2)
        if n:
            seg[:n] = np.linspace(g[i], target, n)
            seg[-n:] = np.linspace(target, 1.0, n)
        g[i:j] = seg
    out = x * g
    peak = float(np.abs(out).max())
    if peak > 0.97:                      # keep the headroom the renderer left
        out *= 0.97 / peak
    return out


def write_wav(path: Path, x, sr):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype("<i2").tobytes())


def latest(name: str) -> Path:
    takes = sorted(KEPT.glob(f"phrase-{name}-*bpm-*.wav"))
    if not takes:
        raise SystemExit(f"no kept take for {name!r} in {KEPT}")
    return takes[-1]


def main(argv=None):
    argv = list(argv or sys.argv[1:])
    if not argv:
        raise SystemExit(__doc__)
    name = argv.pop(0)
    notes, truth, _ = PHRASES[name]
    words = truth.split()
    bpm = 170.0 * RENDER_BPM_RATIO
    spans = windows(notes, bpm)
    if argv[:1] == ["--lead"]:
        gains = [float(argv[1])] + [0.0] * (len(spans) - 1)
    else:
        gains = [float(v) for v in argv] + [0.0] * (len(spans) - len(argv))
    src = latest(name)
    x, sr = read_wav(src)
    out = emphasise(x, sr, spans, gains)
    dst = src.with_name(src.stem + "-emph.wav")
    write_wav(dst, out, sr)
    print(f"{src.name} -> {dst.name}")
    for (word, a, b), db in zip(spans, gains):
        print(f"   {word:<7} {a:.2f}-{b:.2f}s  {db:+.1f} dB")
    return dst


if __name__ == "__main__":
    main()
