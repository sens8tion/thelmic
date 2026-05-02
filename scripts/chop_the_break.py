"""Slice the BREAKBEAST audio into 32 chunks, drop into a Drum Rack, write a
chopped MIDI pattern that re-arranges them across the 16-bar loop.
"""
from __future__ import annotations
import os, sys, wave
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from thelmic.live_channel import LiveChannel

SRC = r"C:\Users\eric\Documents\Splice\Samples\TSP_ENEIV2_174_drum_crisp_full.wav"
OUT_DIR = r"C:\Users\eric\Documents\Ableton\User Library\Samples\Splice\amen_slices"
N_SLICES = 32
PAD_BASE = 36  # slice 0 -> pad 36, slice 1 -> pad 37, ...


def slice_audio():
    os.makedirs(OUT_DIR, exist_ok=True)
    with wave.open(SRC, "rb") as w:
        nch = w.getnchannels()
        sw = w.getsampwidth()
        sr = w.getframerate()
        nframes = w.getnframes()
        raw = w.readframes(nframes)

    bytes_per_frame = nch * sw
    total_bytes = nframes * bytes_per_frame
    slice_bytes = (total_bytes // N_SLICES) // bytes_per_frame * bytes_per_frame
    slice_frames = slice_bytes // bytes_per_frame

    written = []
    for i in range(N_SLICES):
        start = i * slice_bytes
        end = start + slice_bytes
        chunk = raw[start:end]
        name = f"amen_slice_{i:02d}.wav"
        path = os.path.join(OUT_DIR, name)
        with wave.open(path, "wb") as out:
            out.setnchannels(nch)
            out.setsampwidth(sw)
            out.setframerate(sr)
            out.writeframes(chunk)
        written.append(name)
    print(f"sliced {len(written)} chunks ({slice_frames} frames each, sr={sr}, ch={nch})")
    return written


def chop_pattern():
    """Re-arranged pattern: linear with stutters and reverses inserted.

    Returns list of (start_beat, slice_idx) — fire one slice per 16th over 64 beats.
    With 32 slices and 64 beats × 4 sixteenths/beat = 256 hits — too dense.
    Better: 8th-note grid = 128 hits over 64 beats, each slice plays for ~half a beat.
    """
    hits = []
    # 8th-note grid over 16 bars = 128 positions
    # Pattern: 4-bar phrase × 4 (vary slightly each phrase)
    # Each 4-bar phrase = 32 hits
    # Slices 0..31 = the original break across one 4-bar pass
    # Phrase A: linear (0..31)
    # Phrase B: stutter on snares — slice positions 4, 12, 20, 28 (assumed snare hits) repeat
    # Phrase C: reverse second half (linear first half)
    # Phrase D: chopped — heavy re-arrangement

    def linear():
        return list(range(32))

    def stutter():
        # Original slice with stutters on positions 4, 12, 20, 28 (likely snare hits)
        seq = list(range(32))
        for snare_pos in [4, 12, 20, 28]:
            # repeat the slice at snare_pos in the next slot (replacing whatever was there)
            if snare_pos + 1 < 32:
                seq[snare_pos + 1] = snare_pos
        return seq

    def reverse_back():
        # First half linear, second half reversed
        return list(range(16)) + list(range(31, 15, -1))

    def chop_heavy():
        # Heavy chop — jumping pattern
        return [
            0, 0, 1, 4, 4, 5, 6, 4,    # bar 1
            8, 9, 10, 8, 12, 12, 13, 12,
            16, 17, 18, 16, 20, 20, 4, 21,
            24, 25, 24, 26, 28, 28, 29, 31,
        ]

    phrases = [linear(), stutter(), reverse_back(), chop_heavy()]
    for phrase_idx, phrase in enumerate(phrases):
        phrase_start = phrase_idx * 16.0  # 4 bars = 16 beats
        for hit_idx, slice_idx in enumerate(phrase):
            t = phrase_start + hit_idx * 0.5  # 8th-note grid
            hits.append((t, slice_idx))
    return hits


def main():
    print("--- slicing audio ---")
    written = slice_audio()

    ch = LiveChannel(lower_priority=False); ch.start()
    try:
        # Create new MIDI track for the chopped break
        new = ch.create_midi_track(-1).result(timeout=10)
        chop_t = new["index"]
        ch.set_track_name(chop_t, "AMEN CHOPPED").result(timeout=3)

        # Empty Drum Rack
        ch.load_device(chop_t, "query:Synths#Drum%20Rack").result(timeout=15)
        info = ch.get_track_info(chop_t).result(timeout=5)
        rack_idx = info["device_count"] - 1
        print(f"  T{chop_t} AMEN CHOPPED, Drum Rack at idx {rack_idx}")

        # Load each slice into a drum pad
        for i, fname in enumerate(written):
            note = PAD_BASE + i
            try:
                ch.load_item_at_path(
                    chop_t, "user_library/Samples/Splice/amen_slices",
                    fname, drum_pad_note=note, drum_device_index=rack_idx,
                ).result(timeout=20)
                if i % 8 == 0:
                    print(f"    pad {note}: {fname}")
            except Exception as e:
                print(f"    pad {note} failed: {e}")
        print(f"  loaded {len(written)} slices into pads {PAD_BASE}..{PAD_BASE+len(written)-1}")

        # Write the chop pattern as MIDI
        hits = chop_pattern()
        notes = []
        for (t, slice_idx) in hits:
            # vary velocity slightly so it doesn't feel mechanical
            vel = 95 + ((slice_idx * 7) % 21) - 10
            notes.append({"pitch": PAD_BASE + slice_idx,
                          "start_time": float(t),
                          "duration": 0.45,
                          "velocity": int(vel)})

        ch.create_clip(chop_t, 4, 64.0).result(timeout=10)   # drop scene
        ch.set_clip_name(chop_t, 4, "amen_REARRANGED").result(timeout=3)
        ch.add_notes_to_clip(chop_t, 4, notes).result(timeout=10)
        ch.create_clip(chop_t, 7, 64.0).result(timeout=10)   # final scene
        ch.set_clip_name(chop_t, 7, "amen_REARRANGED_FINAL").result(timeout=3)
        ch.add_notes_to_clip(chop_t, 7, notes).result(timeout=10)

        ch.set_track_volume(chop_t, 0.55).result(timeout=3)  # sit alongside, not on top
        print(f"  wrote {len(notes)} chop hits across scene 4 + scene 7")
    finally:
        ch.stop()


if __name__ == "__main__":
    main()
