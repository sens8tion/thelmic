"""Bump session to 155 BPM, slice the rap WAV into 16 chops, rebuild T_RAP as
a Drum Rack lane that fires slices on a MIDI grid (so original rap pitch is
preserved while triggering at 155 BPM regardless of source-loop tempo).
"""
from __future__ import annotations
import os, sys, wave
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from thelmic.live_channel import LiveChannel

USER_LIB = "user_library/Samples/Splice/AfroEDM_2026-05-04"
USER_LIB_FS = os.path.expandvars(r"%USERPROFILE%\Documents\Ableton\User Library\Samples\Splice\AfroEDM_2026-05-04")

RAP_SRC_NAME = "DS_VAH3_124_rap_dry.wav"
RAP_SLICE_DIR_REL = "user_library/Samples/Splice/AfroEDM_2026-05-04/rap_slices"
RAP_SLICE_DIR_FS = os.path.join(USER_LIB_FS, "rap_slices")
N_SLICES = 16
PAD_BASE = 36

T_RAP = 5   # current audio track index after the cleanup deleted defaults

# ---- audio slice ---------------------------------------------------------

def slice_rap():
    os.makedirs(RAP_SLICE_DIR_FS, exist_ok=True)
    src = os.path.join(USER_LIB_FS, RAP_SRC_NAME)
    with wave.open(src, "rb") as w:
        nch, sw, sr = w.getnchannels(), w.getsampwidth(), w.getframerate()
        nframes = w.getnframes()
        raw = w.readframes(nframes)
    bpf = nch * sw
    slice_bytes = (nframes * bpf // N_SLICES) // bpf * bpf
    written = []
    for i in range(N_SLICES):
        chunk = raw[i*slice_bytes : (i+1)*slice_bytes]
        name = f"rap_slice_{i:02d}.wav"
        path = os.path.join(RAP_SLICE_DIR_FS, name)
        with wave.open(path, "wb") as out:
            out.setnchannels(nch); out.setsampwidth(sw); out.setframerate(sr)
            out.writeframes(chunk)
        written.append(name)
    print(f"sliced {len(written)} rap chunks (sr={sr}, ch={nch})")
    return written


# ---- per-scene rap trigger patterns --------------------------------------
# 8 bars × 4 beats = 32 beats per scene
# Slice pads are PAD_BASE..PAD_BASE+15 (36..51)

def rap_pattern(scene: int) -> list[dict]:
    notes = []
    if scene == 0:
        # sparse — one slice every 2 bars (4 hits over 8 bars)
        for bar in range(0, 8, 2):
            slc = (bar // 2) % N_SLICES
            notes.append({"pitch": PAD_BASE + slc, "start_time": float(bar*4), "duration": 2.0, "velocity": 95})
    elif scene == 1:
        # one slice per bar — linear walk through first 8 slices
        for bar in range(8):
            notes.append({"pitch": PAD_BASE + bar, "start_time": float(bar*4), "duration": 2.0, "velocity": 100})
    elif scene == 2:
        # rapid chop — one slice per beat, mixed sequence
        seq = [0, 4, 1, 5, 2, 6, 3, 7,  8, 12, 9, 13, 10, 14, 11, 15,
               0, 0, 1, 1, 4, 4, 5, 5,  8, 8, 12, 12, 9, 9, 13, 13]
        for beat, slc in enumerate(seq):
            notes.append({"pitch": PAD_BASE + (slc % N_SLICES), "start_time": float(beat),
                          "duration": 0.9, "velocity": 105 if beat % 4 == 0 else 90})
    else:  # scene 3 — solo break, one slice per half-bar (4 hits)
        for i, slc in enumerate([0, 8, 4, 12]):
            notes.append({"pitch": PAD_BASE + slc, "start_time": float(i*8), "duration": 4.0, "velocity": 100})
    return notes


# ---- main ----------------------------------------------------------------

def main():
    print("--- slicing rap ---")
    slice_files = slice_rap()

    ch = LiveChannel(enabled=True); ch.start()
    try:
        # 1. set tempo
        print("setting tempo 155...")
        ch.set_tempo(155.0).result(timeout=5)
        for s in range(4):
            ch.set_scene_tempo(s, 155.0).result(timeout=5)

        # 2. delete current T_RAP (audio) and re-create as MIDI at the same index
        info = ch.get_session_info().result(timeout=5)
        tc = info.get("track_count") or info.get("num_tracks") or 0
        print(f"track count: {tc}")
        ch.delete_track(T_RAP).result(timeout=10)
        # create at the end then... no, we want it back at index 5. create_midi_track(-1) appends.
        new = ch.create_midi_track(-1).result(timeout=10)
        new_idx = new["index"] if isinstance(new, dict) and "index" in new else (tc - 1)
        # rename + drum rack on the new track
        ch.set_track_name(new_idx, "RAP_NAIROBI").result(timeout=5)
        ch.load_device(new_idx, "query:Synths#Drum%20Rack").result(timeout=20)

        # 3. load slices onto pads
        print("loading rap slices to pads...")
        info_t = ch.get_track_info(new_idx).result(timeout=5)
        rack_idx = info_t.get("device_count", 1) - 1
        for i, fname in enumerate(slice_files):
            ch.load_sample_to_pad(new_idx, rack_idx, PAD_BASE + i,
                                   RAP_SLICE_DIR_REL, fname).result(timeout=15)

        # 4. write MIDI clips per scene
        print("writing MIDI rap clips...")
        for s in range(4):
            notes = rap_pattern(s)
            ch.create_clip(new_idx, s, 32.0).result(timeout=10)
            ch.set_clip_name(new_idx, s, f"rap_S{s}").result(timeout=5)
            if notes:
                ch.add_notes_to_clip(new_idx, s, notes).result(timeout=10)
            print(f"  S{s}: {len(notes)} notes")

        ch.set_track_volume(new_idx, 0.85).result(timeout=5)
        ch.set_track_color(new_idx, 14).result(timeout=5)
        print(f"\nRAP_NAIROBI rebuilt at T{new_idx}. Tempo locked to 155.")
        print("STATUS:", ch.status().as_dict())
    finally:
        ch.stop()


if __name__ == "__main__":
    main()
