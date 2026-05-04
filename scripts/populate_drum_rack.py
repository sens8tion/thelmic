"""Per-pad drum-rack populate test (post-Live-update).

Creates a fresh MIDI track, loads an empty Drum Rack, then per-pad loads
the five User-Library drum samples via load_item_at_path with drum_pad_note.
Reports pad-by-pad whether each sample landed where it was sent.
"""
from __future__ import annotations
import os, time
os.environ.setdefault("LIVE_CHANNEL_ENABLED", "1")
from thelmic.live_channel import LiveChannel

PAD_MAP = [
    (36, "tp_nh_cjb_kick_one_shot_low_punchy.wav",          "KICK"),
    (38, "BOS_AJ_Drum_Snare_One_Shot_Press_A_sharp.wav",    "SNARE"),
    (42, "ZEN_PDB_hi_hat_closed_one_shot_tight.wav",        "HAT_C"),
    (46, "shs_ins_hat_open_one_shot_Fit.wav",               "HAT_O"),
    (49, "cj_cymbal_one_shot_live_ahman.wav",               "CRASH"),
]

USER_LIB_PATH = "user_library/Samples/Splice"


def main() -> None:
    ch = LiveChannel(); ch.start(); time.sleep(0.6)
    try:
        info = ch.get_session_info().result(timeout=5)
        n = int(info["track_count"])
        print(f"[setup] creating MIDI track at index {n}")
        ch.create_midi_track(-1).result(timeout=5); time.sleep(0.3)
        ch.set_track_name(n, "DRUMS_TEST").result(timeout=5)

        print("[setup] loading empty Drum Rack")
        ch.load_item_at_path(n, "instruments", "Drum Rack").result(timeout=10)
        time.sleep(1.2)

        for note, fname, label in PAD_MAP:
            try:
                res = ch.load_item_at_path(
                    n, USER_LIB_PATH, fname, drum_pad_note=note,
                ).result(timeout=20)
                print(f"  pad {note:>3} ({label:<5}) <- {res.get('item_name')}")
            except Exception as e:
                print(f"  pad {note:>3} ({label:<5}) FAIL: {e}")
            time.sleep(0.5)

        time.sleep(0.8)
        print("\n[verify] reading rack state")
        pads = ch.get_drum_pads(n, 0).result(timeout=5)
        populated = [p for p in pads.get("pads", []) if p.get("chain_count", 0) > 0]
        if not populated:
            print("  (no populated pads found)")
        for p in populated:
            chains = ", ".join(c.get("name", "?") for c in p.get("chains", []))
            print(f"  pad {p['note']:>3} name={p['name']!r} chains=[{chains}]")
    finally:
        ch.stop()


if __name__ == "__main__":
    main()
