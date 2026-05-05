"""Transient-based rap chop using stdlib only (no scipy / numpy / librosa).

Approach:
  1. Decode WAV via `wave` → int16 PCM
  2. Mono-sum to single channel
  3. Compute frame-level RMS (10 ms frames, 5 ms hop)
  4. Spectral-flux-ish onset score = max(0, rms[k] - rms[k-1])
  5. Pick N highest peaks with min-spacing constraint
  6. Slice at those boundaries, write WAVs, load to Drum Rack pads

Then writes per-scene rap MIDI patterns triggering the (now naturally aligned)
slice pads.
"""
from __future__ import annotations
import os, sys, wave, struct, math
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from thelmic.live_channel import LiveChannel

USER_LIB_FS = os.path.expandvars(r"%USERPROFILE%\Documents\Ableton\User Library\Samples\Splice\AfroEDM_2026-05-04")
RAP_SRC = os.path.join(USER_LIB_FS, "DS_VAH3_124_rap_dry.wav")
SLICE_DIR_FS = os.path.join(USER_LIB_FS, "rap_slices")
SLICE_DIR_REL = "user_library/Samples/Splice/AfroEDM_2026-05-04/rap_slices"
N_SLICES = 16
PAD_BASE = 36
T_RAP = 5

FRAME_MS = 10
HOP_MS = 5
MIN_SLICE_MS = 200          # min spacing between transients


def detect_transients(path: str, n: int) -> list[int]:
    """Return n start-frame indices marking slice boundaries (0 = first slice)."""
    with wave.open(path, "rb") as w:
        nch, sw, sr = w.getnchannels(), w.getsampwidth(), w.getframerate()
        nframes = w.getnframes()
        raw = w.readframes(nframes)
    if sw == 2:
        fmt = f"<{nframes * nch}h"
        samples = struct.unpack(fmt, raw)
    elif sw == 3:
        # 24-bit signed little-endian — sign-extend 3 bytes → 32-bit int
        samples = []
        for i in range(0, len(raw), 3):
            b0, b1, b2 = raw[i], raw[i+1], raw[i+2]
            v = b0 | (b1 << 8) | (b2 << 16)
            if v & 0x800000:
                v -= 0x1000000
            samples.append(v)
    elif sw == 4:
        fmt = f"<{nframes * nch}i"
        samples = struct.unpack(fmt, raw)
    else:
        raise RuntimeError(f"unsupported sampwidth={sw}")

    if nch == 1:
        mono = samples
    else:
        mono = [(samples[i] + samples[i+1]) // 2 for i in range(0, len(samples), nch)]

    frame_n = int(sr * FRAME_MS / 1000)
    hop_n   = int(sr * HOP_MS / 1000)
    n_frames = max(0, (len(mono) - frame_n) // hop_n + 1)

    # RMS per frame
    rms = []
    for k in range(n_frames):
        s = k * hop_n
        chunk = mono[s : s + frame_n]
        # mean-square in floats
        acc = 0
        for x in chunk:
            acc += x * x
        rms.append(math.sqrt(acc / frame_n))

    # Onset = positive 1st-difference of RMS
    flux = [0.0] + [max(0.0, rms[i] - rms[i-1]) for i in range(1, len(rms))]

    # Pick N best peaks with min-spacing (in hop-frames)
    min_hop_gap = MIN_SLICE_MS // HOP_MS
    indexed = sorted(range(len(flux)), key=lambda i: -flux[i])
    chosen = []
    for idx in indexed:
        if any(abs(idx - c) < min_hop_gap for c in chosen):
            continue
        chosen.append(idx)
        if len(chosen) >= n - 1:
            break
    chosen.sort()
    # Convert hop-frames to sample-frames; prepend 0 for the first slice start
    starts = [0] + [c * hop_n for c in chosen]
    # Dedupe + clamp
    starts = sorted(set(starts))
    return starts[:n]


def slice_at(path_in: str, starts: list[int]) -> list[str]:
    os.makedirs(SLICE_DIR_FS, exist_ok=True)
    with wave.open(path_in, "rb") as w:
        nch, sw, sr = w.getnchannels(), w.getsampwidth(), w.getframerate()
        nframes = w.getnframes()
        raw = w.readframes(nframes)
    bpf = nch * sw
    starts_b = [s * bpf for s in starts] + [nframes * bpf]
    written = []
    for i in range(len(starts)):
        chunk = raw[starts_b[i] : starts_b[i+1]]
        if len(chunk) < bpf:
            continue
        name = f"rap_T_{i:02d}.wav"
        with wave.open(os.path.join(SLICE_DIR_FS, name), "wb") as out:
            out.setnchannels(nch); out.setsampwidth(sw); out.setframerate(sr)
            out.writeframes(chunk)
        written.append(name)
    return written


def rap_pattern(scene: int, n: int) -> list[dict]:
    notes = []
    if scene == 0:
        for bar in range(0, 8, 2):
            slc = (bar // 2) % n
            notes.append({"pitch": PAD_BASE + slc, "start_time": float(bar*4), "duration": 2.0, "velocity": 95})
    elif scene == 1:
        for bar in range(8):
            notes.append({"pitch": PAD_BASE + (bar % n), "start_time": float(bar*4), "duration": 2.0, "velocity": 100})
    elif scene == 2:
        # rapid alternating-density chop
        seq = [0, 4, 1, 5, 2, 6, 3, 7,  8, 12, 9, 13, 10, 14, 11, 15,
               0, 0, 1, 1, 4, 4, 5, 5,  8, 8, 12, 12, 9, 9, 13, 13]
        for beat, slc in enumerate(seq):
            notes.append({"pitch": PAD_BASE + (slc % n), "start_time": float(beat),
                          "duration": 0.9, "velocity": 105 if beat % 4 == 0 else 90})
    else:
        # break — solo phrases, one per 2 bars
        for i, slc in enumerate([0, max(1, n//2), n//4, max(1, 3*n//4)]):
            notes.append({"pitch": PAD_BASE + (slc % n), "start_time": float(i*8),
                          "duration": 4.0, "velocity": 100})
    return notes


def main():
    print("--- detecting transients ---")
    starts = detect_transients(RAP_SRC, N_SLICES)
    print(f"found {len(starts)} slice points (frame indices, sr=44100):")
    print(" ", ", ".join(f"{s/44100:.2f}s" for s in starts))

    print("--- slicing ---")
    files = slice_at(RAP_SRC, starts)
    print(f"wrote {len(files)} slices")

    ch = LiveChannel(enabled=True); ch.start()
    try:
        # 1. delete current T_RAP, recreate
        info = ch.get_session_info().result(timeout=5)
        tc = info.get("track_count") or info.get("num_tracks") or 0
        ch.delete_track(T_RAP).result(timeout=10)
        new = ch.create_midi_track(-1).result(timeout=10)
        new_idx = new["index"] if isinstance(new, dict) and "index" in new else (tc - 1)
        ch.set_track_name(new_idx, "RAP_NAIROBI").result(timeout=5)
        ch.load_device(new_idx, "query:Synths#Drum%20Rack").result(timeout=20)
        info_t = ch.get_track_info(new_idx).result(timeout=5)
        rack_idx = info_t.get("device_count", 1) - 1

        # 2. load slices
        for i, fname in enumerate(files):
            ch.load_sample_to_pad(new_idx, rack_idx, PAD_BASE + i,
                                   SLICE_DIR_REL, fname).result(timeout=15)

        # 3. patterns
        for s in range(4):
            notes = rap_pattern(s, len(files))
            ch.create_clip(new_idx, s, 32.0).result(timeout=10)
            ch.set_clip_name(new_idx, s, f"rap_S{s}").result(timeout=5)
            if notes:
                ch.add_notes_to_clip(new_idx, s, notes).result(timeout=10)
            print(f"  S{s}: {len(notes)} notes")

        ch.set_track_volume(new_idx, 0.85).result(timeout=5)
        ch.set_track_color(new_idx, 14).result(timeout=5)
        print("done.")
    finally:
        ch.stop()


if __name__ == "__main__":
    main()
