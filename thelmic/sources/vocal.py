"""Sung vocals, rendered locally from a score (DiffSinger, TIGER voicebank).

A peer of the other adapters in shape — it yields an audio file with a duration and a
licence — but not in kind: a generator has nothing to search. You do not discover a
vocal, you commission one. So this module exposes

    available() -> bool
    render(spec: VocalSpec) -> Sound
    fetch(sound) -> Path          # the file is already local

and :func:`search` refuses rather than inventing candidates for a text query, which
would make a deterministic commission look like a lookup.

The renderer lives in a separate repo (https://github.com/sens8tion/local-sung-vocals,
by default a sibling of this one; override with ``THELMIC_VOCALGEN``). It has its own
venv and is torch-free, so this shells out to it rather than importing it.

LICENSING — READ THIS. The strictest row in thelmic.sources:

    Voicebank (TIGER DS v106)  CC BY-NC-ND 4.0 + Commons Clause
    Vocoder weights            CC BY-NC-SA 4.0
    Personal use               yes
    Commercial release         NO — both components are NonCommercial

The vocoder's NonCommercial term is not avoidable: DiffSinger cannot render without a
vocoder. Nor is this fixed by choosing another voice — of every English DiffSinger bank
checked (TIGER, Canary, Nishiren Gard, Peiton), none is commercial-clear by default;
all sell or grant commercial rights separately.

Whether NonCommercial weights encumber the *rendered audio* is a real legal question
and an unsettled one. It is flagged here deliberately and left open: do not resolve it
by assumption in either direction.

Two operational rules, both from measurement upstream:

* **The GPU is shared** with Live and anything else running. A contended render has
  produced corrupt output and once triggered a driver reset. ``provider="cpu"`` is the
  default; ``"dml"`` is refused unless the caller passes ``gpu_ok=True`` or sets
  ``THELMIC_VOCAL_ALLOW_GPU=1``, which means the operator was asked.
* **There is no seed.** Identical input gives materially different takes, so a take you
  like cannot be regenerated — keep the file. ``takes > 1`` rolls and ranks on word
  error rate first, tonal quality second.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import wave
from dataclasses import dataclass, field
from pathlib import Path

from ._base import Sound, SourceError
from ._cache import cache_path

# find() skips this: it is commissioned, not searched.
GENERATOR = True

LICENSE = "CC BY-NC-ND-4.0 + Commons-Clause (voicebank); CC BY-NC-SA-4.0 (vocoder)"
BANK = "TIGER_DS_v106"
# Seven modes, measurably distinct (5.3x the run-to-run noise floor). TIGER is a male
# tenor; there is no female voice in this install — that would be another voicebank.
SPEAKERS = ("tiger_mystic", "tiger_vinyl", "tiger_disco", "tiger_royal", "tiger_fresh",
            "tiger_glam", "tiger_electric")
GPU_ENV = "THELMIC_VOCAL_ALLOW_GPU"
COMPLEX_PRO = 6          # Live warp modes are ints over the bridge: 0 Beats .. 6 Complex Pro
_WROTE = re.compile(r"wrote (.+\.wav)\s+\(([\d.]+)s")
_BEST = re.compile(r"(\S+\.wav)")


@dataclass(frozen=True)
class VocalSpec:
    """A commission. ``bpm`` comes from the session (see :func:`spec_for_session`), never
    a guess: that is the whole point of rendering through thelmic rather than standalone.

    ``notes`` is the score's note list, e.g.::

        [{"rest": True, "beats": 0.5},
         {"lyric": "over", "midi": 65, "beats": 2.0, "scoop": -2.4, "scoop_beats": 0.26,
          "vibrato": {"rate": 6.0, "depth": 0.40, "delay": 0.45, "fade": 0.2}}]

    A note may carry ``phonemes`` (a list) instead of ``lyric``, which is how syllables of
    one word go on different pitches.

    Emphasis is per note, and it is COLOUR, not loudness — the voicebank has no energy input:

        ``gender`` (alias ``colour``)   +0.2 is measurably brighter at no cost in level. Negative
                                        values thin the word and then destroy it: keep it >= 0.
        ``velocity`` (alias ``speed``)  small and tonal, 0.9 brighter, 1.15 darker; never level.

    Measured in the renderer's bench/diag_emphasis.py against a noise floor of +-0.5 dB and
    +-100 Hz. For level, put gain on the rendered take (scripts/jungle_vocal_emphasis.py).
    """

    notes: list[dict]
    bpm: float
    speaker: str = "tiger_electric"
    takes: int = 1                  # > 1 rolls and returns the best
    provider: str = "cpu"           # "dml" only after asking for the GPU
    steps: int = 20
    ornaments: bool = True
    session: str | None = None      # sessions/<label>/: numbered takes, and the reasoning
    intent: str | None = None       # required to CREATE a session, ignored if it exists
    truth: str | None = None        # words for the ranking pass; defaults to the lyrics
    extra_args: tuple[str, ...] = field(default_factory=tuple)

    def lyrics(self) -> str:
        return " ".join(str(n["lyric"]) for n in self.notes if n.get("lyric"))

    def score(self) -> dict:
        return {"bpm": float(self.bpm), "notes": list(self.notes)}


def root() -> Path:
    env = os.environ.get("THELMIC_VOCALGEN")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[2].parent / "local-sung-vocals"


def bank_dir() -> Path:
    return root() / "voicebanks" / BANK


def interpreter() -> Path | None:
    """The renderer's own interpreter: it has dependencies thelmic's env doesn't."""
    env = os.environ.get("THELMIC_VOCALGEN_PYTHON")
    if env:
        return Path(env)
    for venv in (".venv-gpu", ".venv"):
        exe = root() / venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        if exe.exists():
            return exe
    return None


def available() -> bool:
    """Is the voicebank on disk? There is no API here and nothing to authenticate."""
    return bank_dir().is_dir() and (root() / "bench" / "render.py").is_file()


def search(query: str, *, limit: int = 10, **filters) -> list[Sound]:
    raise SourceError(
        "vocal is a generator, not a library: there is nothing to search. "
        "Write a score and call vocal.render(VocalSpec(...))."
    )


def render(spec: VocalSpec, *, gpu_ok: bool = False, timeout: float = 900.0) -> Sound:
    """Render ``spec`` to a WAV and return it as a :class:`Sound` carrying the licence.

    Batch when you can: the renderer's cold start (~13.6 s of shader compile) is paid per
    process, not per take, and ``takes > 1`` rolls inside one invocation.
    """
    if not available():
        raise SourceError(f"voicebank not found at {bank_dir()} — set THELMIC_VOCALGEN "
                          "to the local-sung-vocals checkout")
    exe = interpreter()
    if exe is None or not exe.exists():
        raise SourceError(f"no renderer interpreter under {root()}; expected .venv-gpu or "
                          ".venv, or set THELMIC_VOCALGEN_PYTHON")
    if spec.speaker not in SPEAKERS:
        raise SourceError(f"unknown speaker {spec.speaker!r}; have {', '.join(SPEAKERS)}")
    if not spec.notes:
        raise SourceError("empty score")
    if not spec.bpm or spec.bpm <= 0:
        raise SourceError("bpm must come from the session (get_session_info), not a guess")
    if spec.provider == "dml" and not (gpu_ok or os.environ.get(GPU_ENV) == "1"):
        raise SourceError(
            "the GPU is shared with Live, and a contended render has produced corrupt "
            "output and a driver reset. Ask the operator first, then pass gpu_ok=True "
            f"(or set {GPU_ENV}=1). provider='cpu' renders a hook in a couple of seconds."
        )
    if spec.session:
        _ensure_session(exe, spec)

    key = json.dumps({"score": spec.score(), "speaker": spec.speaker, "steps": spec.steps,
                      "ornaments": spec.ornaments, "takes": spec.takes}, sort_keys=True)
    score_path = cache_path("vocal", key + "|score", "json")
    score_path.write_text(json.dumps(spec.score(), indent=1), encoding="utf-8")

    if spec.takes > 1:
        cmd, out_hint = _best_of_cmd(exe, spec, score_path), None
    else:
        out_hint = None if spec.session else cache_path("vocal", key, "wav")
        cmd = _render_cmd(exe, spec, score_path, out_hint)

    try:
        proc = subprocess.run([str(c) for c in cmd], cwd=str(root()), check=True,
                              capture_output=True, text=True, timeout=timeout)
    except subprocess.CalledProcessError as e:
        raise SourceError(f"render failed ({e.returncode}): {(e.stderr or e.stdout or '').strip()[-800:]}") from e
    except subprocess.TimeoutExpired as e:
        raise SourceError(f"render timed out after {timeout:.0f}s") from e

    stdout = proc.stdout or ""
    path, duration = _result_of(stdout, spec, out_hint)
    if duration is None:
        duration = wav_duration(path)
    inferred = _inferred_pronunciations(stdout)

    return Sound(
        source="vocal",
        id=path.stem,
        title=spec.lyrics() or path.stem,
        url=path.as_uri(),
        download_url=None,
        duration=duration,
        license=LICENSE,
        tags=("sung", "diffsinger", spec.speaker, spec.provider),
        extra={
            "path": str(path),
            "bpm": float(spec.bpm),
            "speaker": spec.speaker,
            "provider": spec.provider,
            "takes": spec.takes,
            "score_path": str(score_path),
            "session": spec.session,
            # Surface these: the bank ships pronunciations as an override set, so ordinary
            # words come from CMUdict. A wrong one is far easier to catch in a list than by
            # ear in a mix.
            "inferred_pronunciations": inferred,
            "stdout": stdout[-4000:],
            "commercial_use": False,
            "license_note": ("voicebank and vocoder are both NonCommercial; whether NC "
                             "weights encumber rendered audio is unsettled — do not assume"),
        },
    )


def fetch(sound: Sound) -> Path:
    """The file is already local — this exists for interface compatibility."""
    p = sound.extra.get("path")
    if not p:
        raise SourceError("this Sound carries no path; it did not come from vocal.render()")
    path = Path(p)
    if not path.exists():
        raise SourceError(f"{path} is gone. There is no seed: a take cannot be re-rolled "
                          "identically, so a lost take is lost — render a new one.")
    return path


def spec_for_session(channel, notes: list[dict], **kwargs) -> VocalSpec:
    """Build a spec at the Live session's tempo, so the vocal fits by construction.

    ``channel`` is a started LiveChannel.
    """
    info = channel.get_session_info().result(timeout=5)
    return VocalSpec(notes=notes, bpm=float(info["tempo"]), **kwargs)


def into_live(channel, sound: Sound, *, name: str = "VOCAL-CHORD", warp: bool = True):
    """Load a rendered vocal onto a new audio track. Creates a track: call it deliberately.

    Warp mode is Complex Pro — it survives formant-heavy material without the chipmunk
    artefacts of Beats or Tones. The render was made at the session tempo, so warping has
    almost nothing to correct.
    """
    path = fetch(sound)
    track = channel.create_audio_track(-1).result(timeout=10)
    index = track["index"] if isinstance(track, dict) and "index" in track else \
        channel.get_session_info().result(timeout=5)["track_count"] - 1
    channel.set_track_name(index, name).result(timeout=5)
    channel.load_item_at_path(index, str(path.parent), path.name).result(timeout=30)
    if warp:
        channel.set_clip_warp(index, 0, warping=True, warp_mode=COMPLEX_PRO).result(timeout=5)
    return index


def wav_duration(path: Path) -> float | None:
    try:
        with wave.open(str(path)) as w:
            return w.getnframes() / float(w.getframerate())
    except Exception:
        return None


# ---------------------------------------------------------------- internals
def _render_cmd(exe: Path, spec: VocalSpec, score: Path, out: Path | None) -> list:
    cmd = [exe, root() / "bench" / "render.py", bank_dir(), score]
    if spec.session:
        cmd += ["--session", spec.session]
    else:
        cmd += [out]
    cmd += ["--speaker", spec.speaker, "--steps", str(spec.steps), "--provider", spec.provider]
    if not spec.ornaments:
        cmd += ["--no-ornaments"]
    return cmd + list(spec.extra_args)


def _best_of_cmd(exe: Path, spec: VocalSpec, score: Path) -> list:
    truth = spec.truth or spec.lyrics()
    if not truth:
        raise SourceError("takes > 1 ranks on word error rate, so it needs the words: "
                          "give the score lyrics or set VocalSpec.truth")
    cmd = [exe, root() / "bench" / "best_of.py", score, "--truth", truth,
           "--takes", str(spec.takes), "--speaker", spec.speaker, "--steps", str(spec.steps),
           "--provider", spec.provider]
    if spec.session:
        cmd += ["--session", spec.session]
    return cmd + list(spec.extra_args)


def _ensure_session(exe: Path, spec: VocalSpec) -> None:
    """Sessions carry intent and decisions, not parameters — the part that evaporates."""
    if (root() / "sessions" / spec.session / "session.yaml").exists():
        return
    if not spec.intent:
        raise SourceError(f"session {spec.session!r} doesn't exist yet; pass intent= saying "
                          "why this vocal, which voice was rejected and what for")
    subprocess.run([str(exe), str(root() / "bench" / "session.py"), "new", spec.session,
                    "--intent", spec.intent], cwd=str(root()), check=True,
                   capture_output=True, text=True)


def _result_of(stdout: str, spec: VocalSpec, out_hint: Path | None):
    """(path, duration) of the take that was kept."""
    if spec.takes > 1:
        for line in stdout.splitlines():
            if line.startswith("best:") or "<-- best" in line:
                m = _BEST.search(line)
                if m:
                    name = Path(m.group(1)).name
                    base = (root() / "sessions" / spec.session / "renders" if spec.session
                            else root() / "out" / "bestof")
                    return base / name, None
        raise SourceError("no take was fully legible: lengthen the weak word rather than "
                          f"re-rolling.\n{stdout[-800:]}")
    m = _WROTE.search(stdout)
    if m:
        return Path(m.group(1).strip()), float(m.group(2))
    if out_hint and out_hint.exists():
        return out_hint, None
    raise SourceError(f"the renderer printed no output path:\n{stdout[-800:]}")


def _inferred_pronunciations(stdout: str) -> dict:
    out: dict[str, str] = {}
    lines = stdout.splitlines()
    for i, line in enumerate(lines):
        if "pronounced from CMUdict" in line:
            for follow in lines[i + 1:]:
                parts = follow.split()
                if not follow.startswith("    ") or len(parts) < 2:
                    break
                out[parts[0]] = " ".join(parts[1:])
    return out
