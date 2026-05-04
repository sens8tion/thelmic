"""Demo: define a session by intent + bindings, save, build into Live.

This creates `sessions/jungle_v1/` on disk and reconstructs it in a fresh
Live project. Re-running is a no-op: load_session.build(ch) is idempotent.
"""
from __future__ import annotations
import os, time

os.environ.setdefault("LIVE_CHANNEL_ENABLED", "1")

from thelmic.live_channel import LiveChannel
from thelmic.sessions import Session


def define_jungle_v1() -> Session:
    sess = Session.open("jungle_v1", pack="dnb_jungle")
    sess.intent.concept = "ragga jungle → Rotterdam gabber arc"
    sess.intent.bpm = 174.0
    sess.intent.key_root = "Em"
    sess.intent.mood = "menacing, sub-heavy"
    sess.intent.arc = ["BUILD", "DROP", "BREAK", "DROP2"]

    SPLICE = "user_library/Samples/Splice"
    # drum-pad bindings (per-pad hotswap path)
    sess.bindings.set_sample("drums.kick",  SPLICE,
        "tp_nh_cjb_kick_one_shot_low_punchy.wav", pad_note=36)
    sess.bindings.set_sample("drums.snare", SPLICE,
        "BOS_AJ_Drum_Snare_One_Shot_Press_A_sharp.wav", pad_note=38)
    sess.bindings.set_sample("drums.hat_c", SPLICE,
        "ZEN_PDB_hi_hat_closed_one_shot_tight.wav", pad_note=42)
    sess.bindings.set_sample("drums.hat_o", SPLICE,
        "shs_ins_hat_open_one_shot_Fit.wav", pad_note=46)
    sess.bindings.set_sample("drums.crash", SPLICE,
        "cj_cymbal_one_shot_live_ahman.wav", pad_note=49)

    # role-track samples (8 channels: drums, break, sub, bass, stab, pad, vox, fx)
    sess.bindings.set_sample("break", SPLICE,
        "TSP_IHD_160_drum_break_amen_chop_4bar.wav")
    sess.bindings.set_sample("sub",   SPLICE,
        "ZEN_RETR_175_bass_sub_bonk_Emin.wav")
    sess.bindings.set_sample("pad",   SPLICE,
        "100_-_Em_-_Guitar_Pad_Texture.wav")
    sess.bindings.set_sample("vox",   SPLICE,
        "X10_PDH_100_vocal_yo_chargie.wav")
    sess.bindings.set_sample("fx",    SPLICE,
        "AFP_SDRL_156_organ_bubble_cutchie_Am.wav")

    sess.notes = (
        "Hand-set bindings for the canonical jungle session. Drum pads use\n"
        "the post-Live-update hotswap path (load_sample_to_pad), not the\n"
        "factory 24_7 Kit fallback."
    )
    sess.save()
    return sess


def main() -> None:
    sess = define_jungle_v1()
    print(f"[def] saved {sess.dir}")
    ch = LiveChannel(); ch.start(); time.sleep(0.6)
    try:
        result = sess.build(ch)
        print("[build]", result)
    finally:
        ch.stop()


if __name__ == "__main__":
    main()
