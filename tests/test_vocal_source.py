"""thelmic.sources.vocal — contract, licence, GPU consent and command building.

The renderer is faked throughout: no audio is rendered, and the GPU is never touched.
"""

from __future__ import annotations

import json
import wave
from pathlib import Path

import pytest

from thelmic import sources
from thelmic.sources import SourceError, vocal


@pytest.fixture
def install(tmp_path, monkeypatch):
    """A stand-in for the local-sung-vocals checkout, with a fake interpreter."""
    (tmp_path / "voicebanks" / vocal.BANK).mkdir(parents=True)
    (tmp_path / "bench").mkdir()
    (tmp_path / "bench" / "render.py").write_text("", encoding="utf-8")
    exe = tmp_path / "python.exe"
    exe.write_text("", encoding="utf-8")
    monkeypatch.setenv("THELMIC_VOCALGEN", str(tmp_path))
    monkeypatch.setenv("THELMIC_VOCALGEN_PYTHON", str(exe))
    monkeypatch.delenv(vocal.GPU_ENV, raising=False)
    return tmp_path


@pytest.fixture
def runs(monkeypatch):
    """Record the commands, write the WAV the renderer would have written."""
    calls = []

    class Result:
        returncode = 0
        stderr = ""

        def __init__(self, stdout):
            self.stdout = stdout

    def fake_run(cmd, **kwargs):
        calls.append([str(c) for c in cmd])
        out = Path(cmd[4]) if "--session" not in [str(c) for c in cmd] and len(cmd) > 4 else None
        if out is not None and str(out).endswith(".wav"):
            out.parent.mkdir(parents=True, exist_ok=True)
            with wave.open(str(out), "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(44100)
                w.writeframes(b"\0\0" * 44100)
            return Result(f"bank=TIGER  speaker=x\n  wrote {out}  (1.00s, peak was 0.5)\n")
        return Result("  wrote nowhere.wav  (1.00s, peak was 0.5)\n")

    monkeypatch.setattr(vocal.subprocess, "run", fake_run)
    return calls


SCORE = [{"rest": True, "beats": 0.5},
         {"lyric": "over", "midi": 65, "beats": 2.0, "scoop": -2.4},
         {"lyric": "this", "midi": 68, "beats": 1.0}]


def test_contract_is_a_generator_not_a_library(install):
    assert vocal.GENERATOR is True
    for name in ("available", "render", "fetch"):
        assert callable(getattr(vocal, name))
    assert vocal.available() is True
    with pytest.raises(SourceError) as e:
        vocal.search("something sung")
    assert "generator" in str(e.value)


def test_find_skips_it(install):
    assert "vocal" in sources.list_sources()
    assert sources.find("anything", limit=3, sources=["vocal"]) == []


def test_licence_is_the_strict_row(install, runs):
    sound = vocal.render(vocal.VocalSpec(notes=SCORE, bpm=170))
    assert sound.license == "CC BY-NC-ND-4.0 + Commons-Clause (voicebank); CC BY-NC-SA-4.0 (vocoder)"
    assert sound.extra["commercial_use"] is False
    assert "unsettled" in sound.extra["license_note"]
    assert sound.source == "vocal"
    assert sound.duration == pytest.approx(1.0, abs=0.05)


def test_the_gpu_needs_asking(install, runs):
    spec = vocal.VocalSpec(notes=SCORE, bpm=170, provider="dml")
    with pytest.raises(SourceError) as e:
        vocal.render(spec)
    assert "Ask the operator" in str(e.value)
    assert runs == []                                   # nothing ran
    vocal.render(spec, gpu_ok=True)                     # asked and answered
    assert "--provider" in runs[0] and "dml" in runs[0]


def test_the_gpu_can_be_allowed_by_environment(install, runs, monkeypatch):
    monkeypatch.setenv(vocal.GPU_ENV, "1")
    vocal.render(vocal.VocalSpec(notes=SCORE, bpm=170, provider="dml"))
    assert "dml" in runs[0]


def test_cpu_is_the_default_and_the_score_carries_the_session_tempo(install, runs):
    sound = vocal.render(vocal.VocalSpec(notes=SCORE, bpm=170))
    cmd = runs[0]
    assert cmd[-1] == "cpu" or "cpu" in cmd
    assert "--speaker" in cmd and "tiger_electric" in cmd
    score = json.loads(Path(sound.extra["score_path"]).read_text(encoding="utf-8"))
    assert score["bpm"] == 170.0
    assert score["notes"] == SCORE
    assert sound.title == "over this"


def test_bpm_and_speaker_are_checked(install, runs):
    with pytest.raises(SourceError) as e:
        vocal.render(vocal.VocalSpec(notes=SCORE, bpm=0))
    assert "bpm" in str(e.value)
    with pytest.raises(SourceError):
        vocal.render(vocal.VocalSpec(notes=SCORE, bpm=170, speaker="tiger_soprano"))
    with pytest.raises(SourceError):
        vocal.render(vocal.VocalSpec(notes=[], bpm=170))
    assert runs == []


def test_several_takes_roll_and_rank(install, runs, monkeypatch):
    best = install / "out" / "bestof" / "score-roll03.wav"

    def fake_run(cmd, **kwargs):
        runs.append([str(c) for c in cmd])

        class R:
            returncode = 0
            stderr = ""
            stdout = ("  roll  3  WER   0.0%  flatness 0.2\n"
                      "3/8 takes fully legible\n"
                      f"best: {best.name}  (most tonal of the clean takes, flatness 0.2)\n")
        return R()

    monkeypatch.setattr(vocal.subprocess, "run", fake_run)
    sound = vocal.render(vocal.VocalSpec(notes=SCORE, bpm=170, takes=8))
    cmd = runs[0]
    assert "best_of.py" in cmd[1]
    assert "--truth" in cmd and "over this" in cmd      # ranked on the words, from the score
    assert "--takes" in cmd and "8" in cmd
    assert Path(sound.extra["path"]) == best


def test_no_legible_take_is_an_error_not_a_silent_pick(install, runs, monkeypatch):
    def fake_run(cmd, **kwargs):
        class R:
            returncode = 0
            stderr = ""
            stdout = "NONE fully legible -- the phrase is too marginal at this length.\n"
        return R()

    monkeypatch.setattr(vocal.subprocess, "run", fake_run)
    with pytest.raises(SourceError) as e:
        vocal.render(vocal.VocalSpec(notes=SCORE, bpm=170, takes=4))
    assert "lengthen the weak word" in str(e.value).lower()


def test_inferred_pronunciations_are_surfaced(install, runs, monkeypatch):
    out = install / "out.wav"

    def fake_run(cmd, **kwargs):
        with wave.open(str(out), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(44100)
            w.writeframes(b"\0\0" * 4410)

        class R:
            returncode = 0
            stderr = ""
            stdout = ("bank=TIGER\n  2 word(s) pronounced from CMUdict, not the bank:\n"
                      "    moon           m uw n\n"
                      "    dreamers       d r iy m er z\n"
                      f"  wrote {out}  (0.10s, peak was 0.5)\n")
        return R()

    monkeypatch.setattr(vocal.subprocess, "run", fake_run)
    sound = vocal.render(vocal.VocalSpec(notes=SCORE, bpm=170))
    assert sound.extra["inferred_pronunciations"] == {"moon": "m uw n", "dreamers": "d r iy m er z"}


def test_fetch_returns_the_local_file_and_says_so_when_it_is_gone(install, runs):
    sound = vocal.render(vocal.VocalSpec(notes=SCORE, bpm=170))
    path = vocal.fetch(sound)
    assert path.exists() and path.suffix == ".wav"
    path.unlink()
    with pytest.raises(SourceError) as e:
        vocal.fetch(sound)
    assert "no seed" in str(e.value)


def test_a_session_needs_its_intent_before_it_is_created(install, runs):
    with pytest.raises(SourceError) as e:
        vocal.render(vocal.VocalSpec(notes=SCORE, bpm=170, session="hook"))
    assert "intent" in str(e.value)
    assert runs == []


def test_spec_for_session_takes_the_tempo_from_live(install):
    class Future:
        def __init__(self, value):
            self.value = value

        def result(self, timeout=None):
            return self.value

    class Channel:
        def get_session_info(self):
            return Future({"tempo": 170.0, "track_count": 6})

    spec = vocal.spec_for_session(Channel(), SCORE, speaker="tiger_royal")
    assert spec.bpm == 170.0 and spec.speaker == "tiger_royal"
