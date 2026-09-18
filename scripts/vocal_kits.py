"""VOCAL KITS - the most impactful phrases on two Drum Racks, replacing the rendered-vocal kits.

The user: "replace mouth off and big mouth with the best clips loaded onto two different drum kits -
one ragga / dancehall / mc - the other the portuguese. pick only the most impactful phrases -
quantize to the beat", and "make sure there's no gap at the front of the clip".

MOUTH-OFF becomes GOB-SMACKED (ragga, dancehall, MC) and BIG-MOUTH becomes BOCA-SUJA (Portuguese:
"dirty mouth"). Each keeps its track - effects, mixer, clips - and gets a fresh Drum Rack, so no
chop from the old kit is left on a pad.

Quantized: every phrase starts ON its first sound - no gap, so a pad hit on the beat speaks on the
beat - and is cut from the clip as it plays in the set, stretched to 170, so the rest of the phrase
stays on the grid.

    python scripts/vocal_kits.py             # cut, then rebuild the two tracks
    python scripts/vocal_kits.py --files     # cut only
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))
from rap_audition import OUT as FITTED, fitted_name, read_wav, source_bpm, target_bpm, write_wav  # noqa: E402
from spit_take import fade, settle, tight  # noqa: E402

ROOT = Path.home() / "Documents" / "Ableton" / "User Library" / "Samples" / "Imported" / "vocal_kits"
TSP = "TSP_HTM_175_vocal_dry_mc_multiplex_{}.wav"

# old track -> (new name, {pad: (phrase, source clip, (from beat, to beat) on the clip's timeline, or None)})
KITS = {
    "MOUTH-OFF": ("GOB-SMACKED", {
        # bottom row: the jungle MC's own words
        36: ("oldskool jungalist", TSP.format("oldskool_jungalist_Gmin"), None),
        37: ("hold tight", TSP.format("hold_tight_Gmin"), None),
        38: ("lotta mercy", TSP.format("lotta_mercy_Gmin"), None),
        39: ("riddim", TSP.format("riddim_Gmin"), None),
        40: ("me a di soldier", "91V_VHH_140_Vocal_Dancehall_Soldier_Clean.wav", (0.0, 3.2)),
        41: ("fire blazing", "BOS_LevIV_Vocal_Phrase_One_Shot_FireBlazing.wav", None),
        42: ("all a mercy", TSP.format("all_A_mercy_Gmin"), None),
        43: ("together", TSP.format("together_Bmin"), None),
        44: ("pull it", "tp_bmve_vocal_pull_it_dry.wav", None),
        45: ("get em", "tp_bmve_vocal_get_em_dry.wav", None),
        46: ("head top", "tp_bmve_vocal_head_top_dry.wav", None),
        47: ("skuh", TSP.format("skuh__Gmin"), None),
        48: ("shock the rave", "91V_UKB2_140_vocal_hook_male_rap_rave_explode_dry.wav", (9.1, 15.5)),
        49: ("loudest sound on land", "RKU_AU_140_vocal_lead_male_rap_loop_strikes_dry.wav", (11.3, 15.4)),
        50: ("turn up turn up", "VOX_URG_165_vocal_rap_turn_up_dry.wav", (27.8, 32.1)),
        51: ("whats your excuse", "VOX_UKR_128_vocal_hook_rap_excuse_dry.wav", (0.0, 2.9)),
    }),
    "BIG-MOUTH": ("BOCA-SUJA", {
        36: ("te deixar no chao", "VOX_LBP_150_vocal_hook_arsenal_low_Cmin.wav", (12.6, 15.4)),      # put you on the floor
        37: ("eu tenho um arsenal", "VOX_LBP_150_vocal_hook_arsenal_low_Cmin.wav", (7.9, 11.2)),     # I've got an arsenal
        38: ("nao sou de faccao", "VOX_LBP_150_vocal_hook_arsenal_low_Cmin.wav", (3.9, 7.2)),       # I'm not in a gang
        39: ("faco o sinal", "VOX_LBP_150_vocal_hook_arsenal_low_Cmin.wav", (0.0, 3.1)),            # I throw up the sign
        40: ("joga a rabeta no chao", "SO_BFV_130_vocal_loop_rabeta_Fmin.wav", (19.7, 23.4)),      # drop that booty to the floor
        41: ("joga a rabeta", "SO_BFV_130_vocal_loop_rabeta_Fmin.wav", (15.5, 17.6)),              # throw that booty
        42: ("rebola lento", "VOX_LBP_140_vocal_hook_casamento_Cmin.wav", (0.0, 3.5)),             # when she winds it slow
        43: ("acaba com casamento", "VOX_LBP_140_vocal_hook_casamento_Cmin.wav", (7.5, 11.1)),     # ends marriages
        44: ("sem sentimento", "VOX_LBP_140_vocal_hook_casamento_Cmin.wav", (11.1, 19.9)),        # without feelings
        45: ("vai de novo", "VOX_LBP_140_vocal_chop_norave.wav", (0.0, 2.2)),                      # go again (check by ear)
    }),
}


def cut(src: str, span) -> tuple[np.ndarray, int]:
    x, sr = read_wav(FITTED / fitted_name(src))
    bpm = source_bpm(src)
    beat_s = 60.0 / (target_bpm(bpm) if bpm else 170.0)
    if span:
        i, j = settle(x, sr, int(span[0] * beat_s * sr), int(span[1] * beat_s * sr), beat_s)
        x = x[i:j]
    y = fade(tight(x, sr), sr, in_ms=1.0)
    return y * (0.89 / max(1e-9, float(np.abs(y).max()))), sr


def lead_gap_ms(y: np.ndarray, sr: int) -> float:
    """Milliseconds before the file first comes within 30 dB of its peak."""
    mono = np.abs(y).mean(axis=1)
    return float(np.argmax(mono > mono.max() * 10 ** (-30 / 20))) / sr * 1000


def build() -> dict[str, dict[int, Path]]:
    made = {}
    for old, (new, picks) in KITS.items():
        out = ROOT / new
        out.mkdir(parents=True, exist_ok=True)
        made[new] = {}
        for pad, (phrase, src, span) in picks.items():
            dst = out / f"{pad:02d}-{phrase.replace(' ', '-')}.wav"
            made[new][pad] = dst
            if dst.exists():
                continue
            y, sr = cut(src, span)
            write_wav(dst, y, sr)
            print(f"  {new:<12} pad {pad}  {phrase:<24} {len(y) / sr:4.2f} s  lead-in {lead_gap_ms(y, sr):4.1f} ms")
    return made


def rebuild(made: dict[str, dict[int, Path]]) -> None:
    """Rename each old kit track, swap its Drum Rack for a fresh one, fill the pads. The effects
    after the rack, the mixer and the clips stay."""
    os.environ.setdefault("LIVE_CHANNEL_ENABLED", "1")
    import time
    from thelmic.live_channel import LiveChannel
    from jungle_drumkits import DRUM_RACK, _load_pad, _pad_device
    from jungle_build import fade_raw
    from jungle_reset import index_of, track_names
    ch = LiveChannel(lower_priority=False)
    ch.start()
    try:
        for old, (new, picks) in KITS.items():
            names = track_names(ch)
            if new not in names:
                t = index_of(ch, old)
                devs = ch.get_track_info(t).result(timeout=5)["devices"]
                if not devs or devs[0]["name"] != "Drum Rack" or devs[0].get("class_name", "DrumGroupDevice") != "DrumGroupDevice":
                    raise SystemExit(f"{old}: expected its Drum Rack first, found {[d['name'] for d in devs]}")
                ch.delete_device(t, 0).result(timeout=10)
                ch.load_device(t, DRUM_RACK).result(timeout=30)
                for _ in range(80):
                    devs = ch.get_track_info(t).result(timeout=5)["devices"]
                    if any(d["name"] == "Drum Rack" for d in devs):
                        break
                    time.sleep(0.25)
                order = [d["name"] for d in devs]
                if order[0] != "Drum Rack":
                    raise SystemExit(f"{old}: the new Drum Rack landed at {order.index('Drum Rack')}: {order}")
                ch.set_track_name(t, new).result(timeout=5)
                print(f"  {old} -> {new}: " + " > ".join(order))
            t = index_of(ch, new)
            for pad, path in made[new].items():
                if _pad_device(ch, t, pad):
                    continue
                _load_pad(ch, t, pad, f"user_library/Samples/Imported/vocal_kits/{new}", path.name)
                ch.set_drum_pad_chain_device_property(t, 0, pad, "playback_mode", 1, 0).result(timeout=10)
                try:
                    ch.set_drum_pad_chain_device_property(t, 0, pad, "sample.warping", False, 0).result(timeout=10)
                except Exception as e:
                    print(f"    [warn] pad {pad}: warping not set ({e})")
                for key, value in (("Trigger Mode", 0), ("Fade In", fade_raw(0.0)), ("Fade Out", fade_raw(8.0)), ("Snap", 0)):
                    try:
                        ch.set_drum_pad_chain_device_param(t, 0, pad, float(value), param_name=key,
                                                           chain_device_index=0).result(timeout=10)
                    except Exception as e:
                        print(f"    [warn] pad {pad}: {key} not set ({e})")
                print(f"  {new:<12} pad {pad} {picks[pad][0]}")
    finally:
        ch.stop()


if __name__ == "__main__":
    made = build()
    if "--files" not in sys.argv:
        rebuild(made)
