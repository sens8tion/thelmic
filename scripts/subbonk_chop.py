"""Slice the SUBBONK audio sample into chunks, drop into a Drum Rack on a
new track, then write a chopped MIDI pattern at 2x density (preserving pitch
since each slice plays at original sample rate without time-stretch)."""
from __future__ import annotations
import os, sys, wave
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from thelmic.live_channel import LiveChannel

SRC = r"C:\Users\eric\Documents\Splice\Samples\ZEN_RETR_175_bass_sub_bonk_Emin.wav"
OUT_DIR = r"C:\Users\eric\Documents\Ableton\User Library\Samples\Splice\subbonk_slices"
N_SLICES = 16
PAD_BASE = 36


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
    written = []
    for i in range(N_SLICES):
        chunk = raw[i*slice_bytes:(i+1)*slice_bytes]
        name = f"subbonk_slice_{i:02d}.wav"
        path = os.path.join(OUT_DIR, name)
        with wave.open(path, "wb") as out:
            out.setnchannels(nch); out.setsampwidth(sw); out.setframerate(sr)
            out.writeframes(chunk)
        written.append(name)
    print(f"sliced {len(written)} chunks (sr={sr}, ch={nch})")
    return written


def chop_pattern(pad_base):
    """4-bar phrase × 4 = 16 bars. Each phrase fires slices at 1-per-beat (= 2x density
    vs the 16-slices-over-8-bars original = 1 per 2 beats).

    Phrase A: linear ascending
    Phrase B: stutter on slices 4, 12 (assumed transient peaks)
    Phrase C: reverse-back
    Phrase D: chopped chaos
    """
    def linear(): return list(range(16))
    def stutter():
        seq = list(range(16))
        for stut_pos in [4, 12]:
            if stut_pos + 1 < 16:
                seq[stut_pos + 1] = stut_pos
        return seq
    def reverse_back(): return list(range(8)) + list(range(15, 7, -1))
    def chopped():
        return [0, 0, 1, 4, 4, 5, 6, 4,
                8, 9, 10, 8, 12, 12, 13, 12]

    phrases = [linear(), stutter(), reverse_back(), chopped()]
    notes = []
    for pi, phrase in enumerate(phrases):
        ps = pi * 16.0  # 4 bars = 16 beats
        for hi, sl in enumerate(phrase):
            t = ps + hi * 1.0   # 1 slice per beat (2x density)
            vel = 100 if hi % 4 == 0 else 90
            notes.append({"pitch": pad_base + sl, "start_time": t,
                          "duration": 0.9, "velocity": vel})
    return notes


def main():
    print("--- slicing SUBBONK ---")
    written = slice_audio()

    ch = LiveChannel(lower_priority=False); ch.start()
    try:
        # Create new MIDI track
        new = ch.create_midi_track(-1).result(timeout=10)
        chop_t = new["index"]
        ch.set_track_name(chop_t, "SUBBONK CHOP").result(timeout=3)

        # Drum Rack
        ch.load_device(chop_t, "query:Synths#Drum%20Rack").result(timeout=15)
        info = ch.get_track_info(chop_t).result(timeout=5)
        rack_idx = info["device_count"] - 1
        print(f"  T{chop_t} SUBBONK CHOP, Drum Rack idx {rack_idx}")

        # Bulk load slices into pads via the proper RPC
        items = [{"name": fname, "note": PAD_BASE + i} for i, fname in enumerate(written)]
        r = ch.bulk_load_drum_pads(chop_t, rack_idx,
                                    "user_library/Samples/Splice/subbonk_slices",
                                    items).result(timeout=60)
        print(f"  loaded {len(r['loaded'])}/{len(items)} slices")

        # Verify with get_drum_pads
        pads = ch.get_drum_pads(chop_t, rack_idx).result(timeout=5)["pads"]
        populated = [p for p in pads if p["chain_count"] > 0]
        print(f"  populated pads: {len(populated)}")

        # Write the chop MIDI clip into scene 12 (FOOTWORK FULL) and scene 14 (JUNGLE RETURN)
        notes = chop_pattern(PAD_BASE)
        for slot in [12, 14]:
            try: ch.clear_clip(chop_t, slot).result(timeout=3)
            except Exception: pass
            ch.create_clip(chop_t, slot, 64.0).result(timeout=10)
            ch.set_clip_name(chop_t, slot, f"subbonk_chop_s{slot}").result(timeout=3)
            ch.add_notes_to_clip(chop_t, slot, notes).result(timeout=10)
            print(f"  T{chop_t} S{slot}: chop pattern ({len(notes)} hits)")

        ch.set_track_volume(chop_t, 0.65).result(timeout=3)
        print(f"\n  T{chop_t} SUBBONK CHOP — slices on pads, chop in scenes 12 + 14")
    finally:
        ch.stop()


if __name__ == "__main__":
    main()
