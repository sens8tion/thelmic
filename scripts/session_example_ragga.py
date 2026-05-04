"""Demo: build a ragga-style 8x4 session.

Same pack (dnb_jungle), same channel set (drums, break, sub, bass, stab,
pad, vox, fx), same bindings — but `intent.overrides["arrangement"] =
"ragga"` selects the ragga LAYOUT + SCENE_PLAN: scenes are
DUB_IN / STEPPER / RAGGAJUNGLE / DUBOUT, and the 'stab' channel carries
ragga organ skanks rather than chord stabs.
"""
from __future__ import annotations
import os, time

os.environ.setdefault("LIVE_CHANNEL_ENABLED", "1")

from thelmic.live_channel import LiveChannel
from thelmic.sessions import Session


def define_ragga_v1() -> Session:
    sess = Session.open("ragga_v1", pack="dnb_jungle")
    sess.intent.concept = "roots-rock stepper → ragga jungle slam → dub"
    sess.intent.bpm = 87.0      # half-time stepper feel; doubles to 174 if pushed
    sess.intent.key_root = "Em"
    sess.intent.mood = "warm, dub-soaked, off-beat skank-led"
    sess.intent.arc = ["DUB_IN", "STEPPER", "RAGGAJUNGLE", "DUBOUT"]
    sess.intent.overrides["arrangement"] = "ragga"

    SPLICE = "user_library/Samples/Splice"
    # drum pads (same hotswap path as jungle_v1)
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

    # audio + sampler channels
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
        "Ragga arrangement: DUB_IN → STEPPER → RAGGAJUNGLE → DUBOUT.\n"
        "Stab channel hosts the off-beat organ skank (Em / Am chords).\n"
        "Bass plays a roots-rock walking line (root, fifth, octave).\n"
        "Same channel set, same bindings as jungle_v1 — only the\n"
        "arrangement (layout scenes + scene_plan) differs."
    )
    sess.save()
    return sess


def main() -> None:
    sess = define_ragga_v1()
    print(f"[def] saved {sess.dir}")
    ch = LiveChannel(); ch.start(); time.sleep(0.6)
    try:
        result = sess.build(ch)
        print("[build]", result)
    finally:
        ch.stop()


if __name__ == "__main__":
    main()
