"""The optional speech layer: what is being sung, and where each word sits.

Two different jobs, often confused:

* **Discovery** (:func:`read_text`) guesses words you do not know. Unreliable
  on a short, fast, heavily processed loop, so it is run many times over -
  different instances of the same token, each slowed with a phase vocoder so
  the syllables have room - and the *agreement* between passes is reported
  rather than a single answer. A speech model asked to transcribe audio it
  cannot parse does not fail loudly; it emits fluent filler, often subtitle
  credits or a sign-off. Disagreement across passes is how you catch that.

* **Placement** (:func:`align_text`) takes words you already know and finds
  where each one sits. Forced alignment cannot invent words, so its
  per-word confidence doubles as a *test of the text*: feed it the wrong
  words and the scores collapse. That makes it the honest way to check a
  reading, and the only way to get word-accurate grid positions.

Both need torch and are imported lazily, so the rest of ``ouvido`` runs on a
machine with neither model present.
"""
from __future__ import annotations

import unicodedata
from dataclasses import dataclass, asdict

import numpy as np

from .audio import Grid

__all__ = ["Reading", "WordSpan", "romanise", "read_text", "align_text",
           "attach_words"]

# Slowing the audio gives a speech model more frames per syllable without
# moving the pitch. Anything below about 0.6 starts introducing phase-vocoder
# artefacts that cost more than the extra resolution buys.
DEFAULT_SPEEDS = (1.0, 0.75, 0.6)
ASR_MODEL = "openai/whisper-large-v3"


@dataclass
class Reading:
    """Candidate texts for one token, with the agreement behind each."""

    candidates: list[tuple[str, int]]      # (text, number of passes)
    passes: int
    language: str

    @property
    def best(self) -> str | None:
        return self.candidates[0][0] if self.candidates else None

    @property
    def agreement(self) -> float:
        """Share of passes backing the leading candidate. Below about 0.3 the
        audio should be treated as unreadable, whatever the text says."""
        if not self.candidates or not self.passes:
            return 0.0
        return self.candidates[0][1] / self.passes

    @property
    def readable(self) -> bool:
        return self.agreement >= 0.3 and self.passes >= 3

    def as_dict(self) -> dict:
        return {"candidates": [list(c) for c in self.candidates],
                "passes": self.passes, "language": self.language,
                "best": self.best, "agreement": round(self.agreement, 3),
                "readable": self.readable}


@dataclass
class WordSpan:
    """One word located in one bar."""

    bar: int
    word: str
    slot_exact: float
    start_ms: float
    end_ms: float
    confidence: float

    def as_dict(self) -> dict:
        return asdict(self)


def romanise(text: str) -> list[str]:
    """Strip diacritics and punctuation to the plain-letter tokens the
    multilingual aligner expects. Portuguese loses its accents here, which is
    correct: the aligner models sounds, not orthography."""
    text = unicodedata.normalize("NFD", text.lower())
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return "".join(c if c.isalpha() or c.isspace() else " " for c in text).split()


def _resample_16k(x: np.ndarray, sr: int) -> np.ndarray:
    if sr == 16000:
        return x
    n = int(round(len(x) * 16000 / sr))
    return np.interp(np.linspace(0, len(x) - 1, n), np.arange(len(x)), x)


def read_text(segments: list[np.ndarray], sr: int, language: str = "pt",
              speeds: tuple[float, ...] = DEFAULT_SPEEDS,
              model_id: str = ASR_MODEL) -> Reading:
    """Guess the words in one token from several instances of it.

    ``segments`` are separate occurrences of the same token; each is
    transcribed at each speed, and the votes are pooled. Pass a *dry* signal if
    you have one - a reverb tail smears the consonants that carry the
    identity of a syllable.
    """
    import torch
    import librosa
    from transformers import WhisperForConditionalGeneration, WhisperProcessor

    dev = "cuda" if torch.cuda.is_available() else "cpu"
    dtype = torch.float16 if dev == "cuda" else torch.float32
    proc = WhisperProcessor.from_pretrained(model_id)
    model = WhisperForConditionalGeneration.from_pretrained(
        model_id, torch_dtype=dtype).to(dev).eval()

    votes: dict[str, int] = {}
    passes = 0
    for seg in segments:
        audio = _resample_16k(np.asarray(seg, dtype=np.float64), sr)
        peak = np.abs(audio).max()
        if peak < 1e-5 or len(audio) < 8000:
            continue
        audio = audio / peak * 0.9
        for speed in speeds:
            clip = librosa.effects.time_stretch(audio, rate=speed) if speed != 1.0 else audio
            inputs = proc(clip, sampling_rate=16000, return_tensors="pt",
                          return_attention_mask=True)
            with torch.no_grad():
                ids = model.generate(
                    inputs.input_features.to(dev, dtype),
                    attention_mask=inputs.attention_mask.to(dev),
                    language=language, task="transcribe",
                    return_timestamps=True, max_new_tokens=96,
                    num_beams=5, temperature=0.0)
            text = proc.batch_decode(ids, skip_special_tokens=True)[0].strip()
            passes += 1
            if text:
                key = " ".join(text.lower().split())
                votes[key] = votes.get(key, 0) + 1
    ranked = sorted(votes.items(), key=lambda kv: -kv[1])
    return Reading(candidates=ranked, passes=passes, language=language)


def align_text(x: np.ndarray, sr: int, grid: Grid, bars: list[int],
               text: str) -> list[WordSpan]:
    """Locate each word of a known text inside each of ``bars``.

    The confidence returned per word is the aligner's own, and it is the point:
    a correct text produces high scores on the words that really anchor the
    phrase, and a wrong text produces uniformly low ones. Read the scores
    before believing the positions.
    """
    import torch
    import torchaudio

    words = romanise(text)
    if not words:
        return []
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    bundle = torchaudio.pipelines.MMS_FA
    model = bundle.get_model().to(dev).eval()
    tokenizer = bundle.get_tokenizer()
    aligner = bundle.get_aligner()

    out: list[WordSpan] = []
    for bar in bars:
        t0, t1 = grid.bar_bounds(bar)
        a, b = int(max(0.0, t0) * sr), int(min(t1, len(x) / sr) * sr)
        seg = np.asarray(x[a:b], dtype=np.float64)
        peak = np.abs(seg).max() if len(seg) else 0.0
        if len(seg) < sr // 10 or peak < 1e-4:
            continue
        wav = torch.tensor(seg / peak * 0.95, dtype=torch.float32).unsqueeze(0)
        wav = torchaudio.functional.resample(wav, sr, bundle.sample_rate).to(dev)
        with torch.inference_mode():
            emission, _ = model(wav)
        try:
            spans = aligner(emission[0], tokenizer(words))
        except Exception:
            continue
        ratio = wav.shape[1] / emission.shape[1] / bundle.sample_rate
        for word, span in zip(words, spans):
            start, end = span[0].start * ratio, span[-1].end * ratio
            out.append(WordSpan(
                bar=bar, word=word,
                slot_exact=round(start / grid.slot, 2),
                start_ms=round(start * 1000, 1), end_ms=round(end * 1000, 1),
                confidence=round(float(np.mean([s.score for s in span])), 3)))
    return out


def attach_words(syllables, spans: list[WordSpan], tolerance_slots: float = 1.0):
    """Label each syllable with the word whose span it falls in.

    Mutates and returns ``syllables``. Words that the aligner placed with low
    confidence still get attached - the confidence travels with them, so a
    consumer can filter - because discarding them here would hide the very
    signal that says the text is wrong.
    """
    by_bar: dict[int, list[WordSpan]] = {}
    for s in spans:
        by_bar.setdefault(s.bar, []).append(s)
    for syl in syllables:
        best, best_gap = None, tolerance_slots
        for span in by_bar.get(syl.bar, []):
            end_slot = span.slot_exact + (span.end_ms - span.start_ms) / 1000.0 / 0.0843
            if span.slot_exact - tolerance_slots <= syl.slot_exact <= end_slot + tolerance_slots:
                gap = abs(syl.slot_exact - span.slot_exact)
                if gap < best_gap:
                    best, best_gap = span, gap
        if best is not None:
            syl.word = best.word
            syl.word_confidence = best.confidence
    return syllables
