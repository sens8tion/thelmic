"""Re-slice the rap WAV into 8 long chunks (~2.2s each), replace
RAP_NAIROBI's slice rack with these longer chunks so each trigger has
real run-time.
"""
from __future__ import annotations
import os, sys, wave
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from thelmic.live_channel import LiveChannel

USER_LIB_FS = os.path.expandvars(r"%USERPROFILE%\Documents\Ableton\User Library\Samples\Splice\AfroEDM_2026-05-04")
USER_LIB_REL = "user_library/Samples/Splice/AfroEDM_2026-05-04"
SRC = os.path.join(USER_LIB_FS, "DS_VAH3_124_rap_dry.wav")
DST_REL = "user_library/Samples/Splice/AfroEDM_2026-05-04/rap_long"
DST_FS = os.path.join(USER_LIB_FS, "rap_long")
N_CHUNKS = 8
PAD_BASE = 36
SCENE_LEN = 32.0


def slice_long():
    os.makedirs(DST_FS, exist_ok=True)
    with wave.open(SRC, "rb") as w:
        nch, sw, sr = w.getnchannels(), w.getsampwidth(), w.getframerate()
        nframes = w.getnframes()
        raw = w.readframes(nframes)
    bpf = nch * sw
    chunk_b = (nframes * bpf // N_CHUNKS) // bpf * bpf
    written = []
    for i in range(N_CHUNKS):
        chunk = raw[i*chunk_b : (i+1)*chunk_b]
        if not chunk:
            continue
        name = f"rap_long_{i:02d}.wav"
        with wave.open(os.path.join(DST_FS, name), "wb") as out:
            out.setnchannels(nch); out.setsampwidth(sw); out.setframerate(sr)
            out.writeframes(chunk)
        written.append(name)
    chunk_secs = chunk_b / bpf / sr
    print(f"sliced {len(written)} chunks, ~{chunk_secs:.2f}s each")
    return written


def find_track(ch, name):
    info = ch.get_session_info().result(timeout=5)
    tc = info.get("track_count") or 0
    for i in range(tc):
        if ch.get_track_info(i).result(timeout=3).get("name") == name:
            return i
    return None


def rap_pattern_long(s, n):
    """Patterns adapted to 8 chunks (each ~2.2s = ~5.7 beats at 155 BPM).

    Note durations cap at 4 beats so chunks don't overlap awkwardly.
    Spacing chosen so each chunk has air to breathe.
    """
    pick = lambda i: PAD_BASE + (i % n)
    notes = []
    if s == 0:    # INTRO_PULSE — 2 fragments, well-spaced
        notes.append({"pitch": pick(0), "start_time": 4.0, "duration": 4.0, "velocity": 90})
        notes.append({"pitch": pick(7), "start_time": 24.0, "duration": 4.0, "velocity": 80})
    elif s == 1:  # INTRO_BUILD — 4 chunks, every 8 beats
        for bar in range(4):
            notes.append({"pitch": pick(bar*2), "start_time": float(bar*8), "duration": 5.0, "velocity": 95})
    elif s == 2:  # PRE_DROP — accelerating
        notes.append({"pitch": pick(0), "start_time": 0.0,  "duration": 5.0, "velocity": 95})
        notes.append({"pitch": pick(2), "start_time": 8.0,  "duration": 5.0, "velocity": 100})
        notes.append({"pitch": pick(4), "start_time": 16.0, "duration": 3.0, "velocity": 105})
        # bars 6-7 quicker fragments
        for i in range(4):
            notes.append({"pitch": pick(5+i), "start_time": 22.0 + i*2.0,
                          "duration": 1.8, "velocity": 105})
    elif s == 3:  # DROP_FULL — 4 chunks at 8-beat intervals
        for bar in range(4):
            notes.append({"pitch": pick(bar*2), "start_time": float(bar*8), "duration": 5.0,
                          "velocity": 110})
    elif s == 4:  # ROLL_PEAK — 8 chunks at 4-beat intervals (each fully audible)
        for bar in range(8):
            notes.append({"pitch": pick(bar), "start_time": float(bar*4), "duration": 3.5,
                          "velocity": 110 if bar%2==0 else 95})
    elif s == 5:  # BREAK_HYPNOTIC — solo, very long with reverb tail
        notes.append({"pitch": pick(0), "start_time": 0.0,  "duration": 6.5, "velocity": 95})
        notes.append({"pitch": pick(2), "start_time": 8.0,  "duration": 6.5, "velocity": 92})
        notes.append({"pitch": pick(4), "start_time": 16.0, "duration": 6.5, "velocity": 95})
        notes.append({"pitch": pick(7), "start_time": 24.0, "duration": 6.5, "velocity": 88})
    elif s == 6:  # RE_BUILD — pyramid acceleration
        notes.append({"pitch": pick(0), "start_time": 0.0,  "duration": 6.0, "velocity": 92})
        notes.append({"pitch": pick(1), "start_time": 8.0,  "duration": 6.0, "velocity": 96})
        notes.append({"pitch": pick(2), "start_time": 16.0, "duration": 3.5, "velocity": 100})
        notes.append({"pitch": pick(3), "start_time": 20.0, "duration": 3.5, "velocity": 100})
        for i in range(4):
            notes.append({"pitch": pick(4+i), "start_time": 24.0 + i*2.0,
                          "duration": 1.8, "velocity": 105 + i})
    elif s == 7:  # FINAL_DROP — 8 chunks at 4-beat intervals
        for bar in range(8):
            notes.append({"pitch": pick(bar), "start_time": float(bar*4), "duration": 3.5,
                          "velocity": 115 if bar%4==0 else 100})
    return notes


def main():
    files = slice_long()
    ch = LiveChannel(enabled=True); ch.start()
    try:
        t_rap = find_track(ch, "RAP_NAIROBI")
        if t_rap is None:
            print("RAP_NAIROBI not found — abort"); return
        print(f"RAP_NAIROBI at T{t_rap}; rebuilding rack...")

        # Remove the existing Drum Rack device (the 83-slice rack)
        info = ch.get_track_info(t_rap).result(timeout=5)
        for d_idx in range(info.get("device_count", 0) - 1, -1, -1):
            di = ch.get_device_info(t_rap, d_idx).result(timeout=3)
            if di.get("class_name") == "DrumGroupDevice":
                ch.delete_device(t_rap, d_idx).result(timeout=10)
                print(f"  removed old DrumGroupDevice at idx {d_idx}")

        # Load a fresh empty Drum Rack
        ch.load_device(t_rap, "query:Synths#Drum%20Rack").result(timeout=20)
        info_t = ch.get_track_info(t_rap).result(timeout=5)
        rack_idx = info_t.get("device_count", 1) - 1

        # Load chunks onto pads 36..43
        for i, fname in enumerate(files):
            ch.load_sample_to_pad(t_rap, rack_idx, PAD_BASE + i,
                                   DST_REL, fname).result(timeout=15)
        print(f"  loaded {len(files)} long chunks to pads {PAD_BASE}..{PAD_BASE + len(files) - 1}")

        # Rewrite all 8 scene clips with patterns adapted to N_CHUNKS=8 pads
        for s in range(8):
            try: ch.delete_clip(t_rap, s).result(timeout=5)
            except Exception: pass
            ch.create_clip(t_rap, s, SCENE_LEN).result(timeout=8)
            ch.set_clip_name(t_rap, s, f"rap_S{s}").result(timeout=3)
            notes = rap_pattern_long(s, len(files))
            if notes:
                ch.add_notes_to_clip(t_rap, s, notes).result(timeout=8)
            avg = sum(n["duration"] for n in notes) / max(1, len(notes))
            print(f"  S{s}: {len(notes)} notes, avg dur {avg:.2f} beats")

        print("\nDONE — RAP_NAIROBI rack now has 8 chunks of ~2.2s each.")
    finally:
        ch.stop()


if __name__ == "__main__":
    main()
