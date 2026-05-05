"""Revert RAP_NAIROBI to transient-sliced short samples (64 slices),
auto-set Trigger Mode=1 on each pad so each slice plays its full natural
decay regardless of MIDI note duration.

Builds on Trigger Mode RPC added to remote script today.
"""
from __future__ import annotations
import os, sys, wave, struct, math, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from thelmic.live_channel import LiveChannel

USER_LIB_FS = os.path.expandvars(r"%USERPROFILE%\Documents\Ableton\User Library\Samples\Splice\AfroEDM_2026-05-04")
RAP_SRC = os.path.join(USER_LIB_FS, "DS_VAH3_124_rap_dry.wav")
SLICE_DIR_FS  = os.path.join(USER_LIB_FS, "rap_slices_64")
SLICE_DIR_REL = "user_library/Samples/Splice/AfroEDM_2026-05-04/rap_slices_64"
N_SLICES = 64
PAD_BASE = 36
SCENE_LEN = 32.0
FRAME_MS = 10
HOP_MS = 5
MIN_SLICE_MS = 100


def detect_transients(path, n):
    with wave.open(path, "rb") as w:
        nch, sw, sr = w.getnchannels(), w.getsampwidth(), w.getframerate()
        nframes = w.getnframes()
        raw = w.readframes(nframes)
    if sw == 2:
        samples = struct.unpack(f"<{nframes*nch}h", raw)
    elif sw == 3:
        samples = []
        for i in range(0, len(raw), 3):
            v = raw[i] | (raw[i+1]<<8) | (raw[i+2]<<16)
            if v & 0x800000: v -= 0x1000000
            samples.append(v)
    else:
        raise RuntimeError(f"sw={sw}")
    mono = samples if nch==1 else [(samples[i]+samples[i+1])//2 for i in range(0,len(samples),nch)]
    fn = int(sr*FRAME_MS/1000); hn = int(sr*HOP_MS/1000)
    nf = max(0, (len(mono)-fn)//hn + 1)
    rms = [math.sqrt(sum(x*x for x in mono[k*hn:k*hn+fn])/fn) for k in range(nf)]
    flux = [0.0] + [max(0.0, rms[i]-rms[i-1]) for i in range(1,len(rms))]
    min_gap = MIN_SLICE_MS // HOP_MS
    indexed = sorted(range(len(flux)), key=lambda i: -flux[i])
    chosen = []
    for idx in indexed:
        if any(abs(idx-c)<min_gap for c in chosen): continue
        chosen.append(idx)
        if len(chosen)>=n-1: break
    chosen.sort()
    starts = sorted(set([0] + [c*hn for c in chosen]))
    return starts[:n], sr, sw, nch, raw, nframes


def slice_at(starts, raw, nframes, nch, sw):
    os.makedirs(SLICE_DIR_FS, exist_ok=True)
    bpf = nch*sw
    se = [s*bpf for s in starts] + [nframes*bpf]
    files = []
    for i in range(len(starts)):
        chunk = raw[se[i]:se[i+1]]
        if len(chunk) < bpf: continue
        name = f"rap_T_{i:02d}.wav"
        with wave.open(os.path.join(SLICE_DIR_FS, name), "wb") as out:
            out.setnchannels(nch); out.setsampwidth(sw)
            out.setframerate(44100)  # placeholder, fixed below
            out.writeframes(chunk)
        files.append(name)
    return files


def slice_at_proper(starts, raw, nframes, nch, sw, sr):
    os.makedirs(SLICE_DIR_FS, exist_ok=True)
    bpf = nch*sw
    se = [s*bpf for s in starts] + [nframes*bpf]
    files = []
    for i in range(len(starts)):
        chunk = raw[se[i]:se[i+1]]
        if len(chunk) < bpf: continue
        name = f"rap_T_{i:02d}.wav"
        with wave.open(os.path.join(SLICE_DIR_FS, name), "wb") as out:
            out.setnchannels(nch); out.setsampwidth(sw); out.setframerate(sr)
            out.writeframes(chunk)
        files.append(name)
    return files


def find_track(ch, name):
    info = ch.get_session_info().result(timeout=5)
    for i in range(info.get("track_count") or 0):
        if ch.get_track_info(i).result(timeout=3).get("name") == name:
            return i
    return None


def rap_pattern(s, n):
    pick = lambda i: PAD_BASE + (i % n)
    notes = []
    if s == 0:
        notes.append({"pitch": pick(0), "start_time": 4.0, "duration": 4.0, "velocity": 90})
        notes.append({"pitch": pick(n-1), "start_time": 24.0, "duration": 4.0, "velocity": 80})
    elif s == 1:
        for bar in range(0, 8, 2):
            notes.append({"pitch": pick((bar//2)*(n//4)), "start_time": float(bar*4),
                          "duration": 6.0, "velocity": 95})
    elif s == 2:
        for i in range(8):
            notes.append({"pitch": pick(i*(n//16)), "start_time": float(i*2),
                          "duration": 1.8, "velocity": 92+i})
        for beat in range(8):
            notes.append({"pitch": pick(16 + beat*(n//32 or 1)), "start_time": 16.0+float(beat),
                          "duration": 0.95, "velocity": 100})
        for half in range(16):
            notes.append({"pitch": pick(24+half), "start_time": 24.0+half*0.5,
                          "duration": 0.45, "velocity": 105})
    elif s == 3:
        for beat in range(32):
            notes.append({"pitch": pick(beat*2), "start_time": float(beat),
                          "duration": 0.95, "velocity": 105 if beat%4==0 else 90})
    elif s == 4:
        for half in range(64):
            slc = (half*(n//64 or 1)) % n
            if half % 4 == 1: slc = (slc-1) % n
            notes.append({"pitch": pick(slc), "start_time": half*0.5,
                          "duration": 0.45, "velocity": 110 if half%8==0 else 92})
    elif s == 5:
        picks = [0, n//4, n//2, 3*n//4]
        for i, slc in enumerate(picks):
            notes.append({"pitch": pick(slc), "start_time": float(i*8),
                          "duration": 7.0, "velocity": 95})
    elif s == 6:
        for i in range(8):
            notes.append({"pitch": pick(i*(n//16)), "start_time": float(i*2),
                          "duration": 1.8, "velocity": 92})
        for beat in range(16):
            notes.append({"pitch": pick(16+beat*3), "start_time": 16.0+float(beat),
                          "duration": 0.9, "velocity": 95+beat})
    elif s == 7:
        for half in range(64):
            slc = (half*3 + half//4) % n
            if half % 8 == 1: slc = (slc-2) % n
            notes.append({"pitch": pick(slc), "start_time": half*0.5,
                          "duration": 0.4, "velocity": 115 if half%4==0 else 95})
    return notes


def main():
    print("--- transient detection (N=64) ---")
    starts, sr, sw, nch, raw, nframes = detect_transients(RAP_SRC, N_SLICES)
    files = slice_at_proper(starts, raw, nframes, nch, sw, sr)
    print(f"sliced {len(files)} chunks at sr={sr}")

    ch = LiveChannel(enabled=True); ch.start()
    try:
        t_rap = find_track(ch, "RAP_NAIROBI")
        if t_rap is None: print("RAP_NAIROBI not found"); return
        print(f"RAP_NAIROBI at T{t_rap}")

        # Remove current Drum Rack
        info = ch.get_track_info(t_rap).result(timeout=5)
        for d_idx in range(info.get("device_count", 0)-1, -1, -1):
            di = ch.get_device_info(t_rap, d_idx).result(timeout=3)
            if di.get("class_name") == "DrumGroupDevice":
                ch.delete_device(t_rap, d_idx).result(timeout=10)
                print(f"  removed DrumGroupDevice at idx {d_idx}")

        # Load fresh Drum Rack
        ch.load_device(t_rap, "query:Synths#Drum%20Rack").result(timeout=20)
        info_t = ch.get_track_info(t_rap).result(timeout=5)
        rack_idx = info_t.get("device_count", 1) - 1

        # Load slices
        for i, fname in enumerate(files):
            ch.load_sample_to_pad(t_rap, rack_idx, PAD_BASE+i,
                                   SLICE_DIR_REL, fname).result(timeout=15)
        print(f"  loaded {len(files)} slices to pads {PAD_BASE}..{PAD_BASE+len(files)-1}")

        # Set Trigger Mode=1 on each pad
        ok = fail = 0
        for i in range(len(files)):
            try:
                ch.set_drum_pad_chain_device_param(
                    track_index=t_rap, device_index=rack_idx,
                    note=PAD_BASE+i, chain_device_index=0,
                    param_name="Trigger Mode", value=1.0,
                ).result(timeout=5)
                ok += 1
            except Exception:
                fail += 1
        print(f"  Trigger Mode=1: {ok} ok / {fail} fail")

        # Write per-scene patterns
        for s in range(8):
            try: ch.delete_clip(t_rap, s).result(timeout=5)
            except Exception: pass
            ch.create_clip(t_rap, s, SCENE_LEN).result(timeout=8)
            ch.set_clip_name(t_rap, s, f"rap_S{s}").result(timeout=3)
            notes = rap_pattern(s, len(files))
            if notes:
                ch.add_notes_to_clip(t_rap, s, notes).result(timeout=8)
            print(f"  S{s}: {len(notes)} notes")
        print("DONE")
    finally:
        ch.stop()


if __name__ == "__main__":
    main()
