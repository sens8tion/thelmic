"""Reading and framing: WAV in, musical grid and low-level contours out.

Deliberately stdlib + numpy only, so the base layer runs anywhere the bridge
runs. The optional speech layer (``ouvido.speech``) is the only part that
wants torch.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass

import numpy as np

__all__ = ["read_wav", "Grid", "envelope_db", "f0_contour", "band_energy_db"]


def read_wav(path: str) -> tuple[np.ndarray, int]:
    """Return (mono float64 in [-1, 1], sample_rate).

    Handles PCM 16/24/32 and IEEE float 32, including WAVE_FORMAT_EXTENSIBLE.
    Multi-channel input is averaged down to mono: every measure in this package
    is about time and spectrum, not stereo placement.
    """
    with open(path, "rb") as fh:
        data = fh.read()
    if data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise ValueError(f"not a RIFF/WAVE file: {path}")
    pos, fmt, pcm = 12, None, None
    while pos + 8 <= len(data):
        cid = data[pos:pos + 4]
        size = struct.unpack("<I", data[pos + 4:pos + 8])[0]
        body = data[pos + 8:pos + 8 + size]
        if cid == b"fmt ":
            tag, nch, sr, _br, _ba, bits = struct.unpack("<HHIIHH", body[:16])
            if tag == 0xFFFE and size >= 40:            # EXTENSIBLE: real tag is in the GUID
                tag = struct.unpack("<H", body[24:26])[0]
            fmt = (tag, nch, sr, bits)
        elif cid == b"data":
            pcm = body
        pos += 8 + size + (size & 1)
    if fmt is None or pcm is None:
        raise ValueError(f"missing fmt or data chunk: {path}")
    tag, nch, sr, bits = fmt
    if tag == 3 and bits == 32:
        x = np.frombuffer(pcm, dtype="<f4").astype(np.float64)
    elif tag == 1 and bits == 16:
        x = np.frombuffer(pcm, dtype="<i2").astype(np.float64) / 2 ** 15
    elif tag == 1 and bits == 24:
        raw = np.frombuffer(pcm, dtype=np.uint8)
        raw = raw[: (len(raw) // 3) * 3].reshape(-1, 3)
        pad = np.zeros((len(raw), 4), dtype=np.uint8)
        pad[:, 1:] = raw                                 # little-endian sign extension
        x = pad.view("<i4").ravel().astype(np.float64) / 2 ** 31
    elif tag == 1 and bits == 32:
        x = np.frombuffer(pcm, dtype="<i4").astype(np.float64) / 2 ** 31
    else:
        raise ValueError(f"unsupported WAV format tag={tag} bits={bits}")
    x = x[: (len(x) // nch) * nch].reshape(-1, nch)
    return x.mean(axis=1), sr


@dataclass(frozen=True)
class Grid:
    """The musical grid a clip is measured against.

    ``offset`` is how much later the audio starts than bar 0 of the
    arrangement, in seconds. A stem captured by routing rather than by
    resampling typically needs one; measure it, do not assume it is zero.
    """

    bpm: float
    beats_per_bar: int = 4
    subdivision: int = 16                # slots per bar
    offset: float = 0.0

    @property
    def beat(self) -> float:
        return 60.0 / self.bpm

    @property
    def bar(self) -> float:
        return self.beat * self.beats_per_bar

    @property
    def slot(self) -> float:
        """Seconds per grid slot (a 16th, by default)."""
        return self.bar / self.subdivision

    def bar_bounds(self, bar_index: int) -> tuple[float, float]:
        """Seconds spanned by one bar, in the audio's own timeline."""
        return (bar_index * self.bar - self.offset,
                (bar_index + 1) * self.bar - self.offset)

    def position(self, t: float, bar_index: int) -> tuple[float, int, float]:
        """Map an absolute time to (fractional slot, nearest slot, error in ms).

        The error is signed: negative means the event arrived early.
        """
        rel = t + self.offset - bar_index * self.bar
        frac = rel / self.slot
        nearest = int(round(frac)) % self.subdivision
        err = (frac - round(frac)) * self.slot * 1000.0
        return frac, nearest, err


def envelope_db(x: np.ndarray, sr: int, hop: float = 0.005,
                band: tuple[float, float] | None = (300.0, 3400.0),
                smooth: int = 3) -> tuple[np.ndarray, float]:
    """RMS envelope in dB at ``hop`` resolution, optionally band-limited.

    The default band is the telephone band, where syllabic energy lives and
    where low-frequency instruments in a leaky stem do least damage. Returns
    (envelope_db, frames_per_second).
    """
    if band is not None:
        spec = np.fft.rfft(x)
        freqs = np.fft.rfftfreq(len(x), 1 / sr)
        spec = spec * ((freqs >= band[0]) & (freqs <= band[1]))
        x = np.fft.irfft(spec, n=len(x))
    h = max(1, int(hop * sr))
    n = max(0, (len(x) - h) // h)
    rms = np.sqrt(np.array([np.mean(x[i * h:i * h + h] ** 2) for i in range(n)]) + 1e-14)
    db = 20 * np.log10(rms + 1e-7)
    if smooth > 1:
        db = np.convolve(db, np.ones(smooth) / smooth, mode="same")
    return db, 1.0 / hop


def f0_contour(x: np.ndarray, sr: int, hop: float = 0.005, window: float = 0.04,
               fmin: float = 80.0, fmax: float = 400.0,
               threshold: float = 0.35) -> np.ndarray:
    """Autocorrelation pitch per frame, 0 where unvoiced.

    Cheap and adequate for deciding *whether* a frame is voiced, which is all
    the syllable detector needs. It is octave-prone on creaky or nasal finals,
    so never read a single frame's value as the pitch of a syllable - take a
    median over the nucleus, and corroborate a claim about register with
    :func:`band_energy_db` rather than with f0 alone.
    """
    h = max(1, int(hop * sr))
    w = max(2, int(window * sr))
    n = max(0, (len(x) - w) // h)
    out = np.zeros(n)
    lo, hi = int(sr / fmax), int(sr / fmin)
    for i in range(n):
        seg = x[i * h:i * h + w]
        if np.sqrt(np.mean(seg ** 2)) < 1e-4:
            continue
        seg = seg - seg.mean()
        ac = np.correlate(seg, seg, "full")[len(seg) - 1:]
        if hi >= len(ac) or hi <= lo or ac[0] <= 0:
            continue
        k = lo + int(np.argmax(ac[lo:hi]))
        if ac[k] > threshold * ac[0]:
            out[i] = sr / k
    return out


def band_energy_db(x: np.ndarray, sr: int, lo: float, hi: float) -> float:
    """RMS level of one frequency band, in dB. Loudness-independent comparisons
    of *balance* between two moments are what this is for."""
    if len(x) < 8:
        return -120.0
    spec = np.abs(np.fft.rfft(x * np.hanning(len(x))))
    freqs = np.fft.rfftfreq(len(x), 1 / sr)
    sel = (freqs >= lo) & (freqs < hi)
    if not sel.any():
        return -120.0
    return float(20 * np.log10(np.sqrt(np.mean(spec[sel] ** 2)) + 1e-9))
