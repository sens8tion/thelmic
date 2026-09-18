"""VOCAL KITS - the most impactful phrases on two Drum Racks, replacing the rendered-vocal kits.

The user: "replace mouth off and big mouth with the best clips loaded onto two different drum kits -
one ragga / dancehall / mc - the other the portuguese. pick only the most impactful phrases -
quantize to the beat", and "make sure there's no gap at the front of the clip".

MOUTH-OFF becomes GOB-SMACKED (ragga, dancehall, MC) and BIG-MOUTH becomes BOCA-SUJA (Portuguese:
"dirty mouth"). Each keeps its track - effects, mixer, clips - and gets a fresh Drum Rack, so no
chop from the old kit is left on a pad.

Quantized: every phrase starts ON its first sound - no gap, so a pad hit on the beat speaks on the
beat - and is cut from the clip as it plays in the set, stretched to 170. Then each syllable inside it
is pulled QUANTIZE_STRENGTH of the way onto the nearest 16th, counted from the pad hit (the user:
"75%, go"): measured before, syllables sat 5-40 ms off that grid - some the vocalist's feel, some my
trim, which starting on a soft first consonant left the rest of "acaba com casamento" ~25 ms early.
One stretch whose rate varies through the phrase, anchored at every syllable onset, so there are no
seams; full strength would lose the flow entirely.

    python scripts/vocal_kits.py             # cut, then rebuild the tracks
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
SIXTEENTH_S = 60.0 / 170.0 / 4
QUANTIZE_STRENGTH = 0.75
VERSION = "-q75"       # a new name: Live holds the unquantized files open
TSP = "TSP_HTM_175_vocal_dry_mc_multiplex_{}.wav"

# track -> (the track it replaces, or None for a new one; {pad: (phrase, source clip, span)}). A span is
# (from beat, to beat) on the clip's timeline, None for the whole clip trimmed to its sound, or FULL.
FULL = "full"
KITS = {
    "GOB-SMACKED": ("MOUTH-OFF", {
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
    "BOCA-SUJA": ("BIG-MOUTH", {
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
    # The user: "a third lane which goes full length to play longer, yet beat aligned (uncut)".
    # Whole clips, uncut, on the set's beat - a pickup stays a pickup - with only whole beats of
    # silence taken off the front, and the syllables quantized like the rest.
    "MOUTHFUL": (None, {
        36: ("rave explode", "91V_UKB2_140_vocal_hook_male_rap_rave_explode_dry.wav", FULL),
        37: ("excuse", "VOX_UKR_128_vocal_hook_rap_excuse_dry.wav", FULL),
        38: ("music gal", "VOX_UKR_140_vocal_hook_rap_music_gal_dry.wav", FULL),
        39: ("turn up", "VOX_URG_165_vocal_rap_turn_up_dry.wav", FULL),
        40: ("too easy", "VOX_URG_145_vocal_rap_too_easy_dry.wav", FULL),
        41: ("unknown - drill verse", "RKU_AU_140_vocal_hook_male_rap_loop_unknown_dry.wav", FULL),
        42: ("strikes - drill verse", "RKU_AU_140_vocal_lead_male_rap_loop_strikes_dry.wav", FULL),
        43: ("dancehall soldier", "91V_VHH_140_Vocal_Dancehall_Soldier_Clean.wav", FULL),
        44: ("hold tight", TSP.format("hold_tight_Gmin"), FULL),
        45: ("gone - half-time", "TRKTRN_PASHAGUD_110_VOCAL_GONE.wav", FULL),
        46: ("arsenal", "VOX_LBP_150_vocal_hook_arsenal_low_Cmin.wav", FULL),
        47: ("casamento", "VOX_LBP_140_vocal_hook_casamento_Cmin.wav", FULL),
        48: ("rabeta", "SO_BFV_130_vocal_loop_rabeta_Fmin.wav", FULL),
        49: ("vai de novo", "VOX_LBP_140_vocal_chop_norave.wav", FULL),
    }),
}


def onsets(y: np.ndarray, sr: int) -> list[float]:
    """Syllable onsets, seconds: where the level starts to climb into a rise of 8+ dB within 25 ms
    that reaches within 20 dB of the phrase's peak, at least 90 ms apart. The first is the start."""
    m = np.abs(y).mean(axis=1)
    hop = int(0.005 * sr)
    env = np.array([np.sqrt(np.mean(m[k:k + 2 * hop] ** 2)) for k in range(0, len(m) - 2 * hop, hop)])
    db = 20 * np.log10(np.maximum(env, 1e-9) / max(env.max(), 1e-9))
    out = [0]
    for k in range(5, len(db)):
        if db[k] > -20 and db[k] - db[k - 5] > 8 and (k - out[-1]) * hop / sr > 0.09:
            j = min(range(max(out[-1] + 1, k - 8), k + 1), key=lambda i: db[i])   # where the climb began
            if (j - out[-1]) * hop / sr > 0.06:
                out.append(j)
    return [k * hop / sr for k in out]


def warp(x: np.ndarray, sr: int, src: list[float], dst: list[float], frame_ms=25.0, tol_ms=6.0) -> np.ndarray:
    """WSOLA along a time map: output time dst[k] plays input time src[k], linear between. Grain
    positions are chosen on the mono mix and applied to every channel (rap_audition.wsola, with the
    input hop following the map instead of a fixed ratio)."""
    n = int(frame_ms / 1000 * sr) // 2 * 2
    hs, tol = n // 2, int(tol_ms / 1000 * sr)
    win = np.hanning(n)
    padn = n + tol
    pad = np.concatenate([np.zeros((padn, x.shape[1])), x, np.zeros((2 * n + tol, x.shape[1]))])
    mono = pad.mean(axis=1)
    out_len = int(dst[-1] * sr)
    src_s, dst_s = np.array(src) * sr, np.array(dst) * sr
    y = np.zeros((out_len + 2 * n, x.shape[1]))
    norm = np.zeros(out_len + 2 * n)
    prev, k = padn, 0
    while k * hs < out_len:
        out_pos = k * hs
        nominal = padn + int(np.interp(out_pos, dst_s, src_s))
        if nominal + n + tol >= len(pad):
            break
        if k == 0:
            best = nominal
        else:
            target = mono[prev + hs:prev + hs + n]
            lo = nominal - tol
            best = lo + int(np.argmax(np.correlate(mono[lo:lo + n + 2 * tol], target, mode="valid")))
        y[out_pos:out_pos + n] += pad[best:best + n] * win[:, None]
        norm[out_pos:out_pos + n] += win
        prev, k = best, k + 1
    return (y[:out_len] / np.maximum(norm[:out_len], 1e-3)[:, None])


def quantize(y: np.ndarray, sr: int, strength: float = QUANTIZE_STRENGTH) -> tuple[np.ndarray, list, list]:
    """Pull each syllable `strength` of the way onto the nearest 16th from the start. The start stays
    put (no gap) and the tail after the last syllable keeps its length. A move that would squash or
    stretch a gap past 0.6-1.6x, or collide with the syllable before, is skipped."""
    src = onsets(y, sr)
    dst = [0.0]
    kept = [0.0]
    for o in src[1:]:
        g = round(o / SIXTEENTH_S) * SIXTEENTH_S
        q = o + strength * (g - o)
        span_in, span_out = o - kept[-1], q - dst[-1]
        if span_out <= 0.04 or not 0.6 <= span_out / span_in <= 1.6:
            continue
        kept.append(o)
        dst.append(q)
    end = len(y) / sr
    kept.append(end)
    dst.append(dst[-1] + (end - kept[-2]))
    if len(kept) <= 2:
        return y, kept, dst
    return warp(y, sr, kept, dst), kept, dst


def grid_error_ms(y: np.ndarray, sr: int) -> float:
    """Median distance of the syllables from the 16th grid counted from the start, in ms."""
    t = np.array(onsets(y, sr)[1:])
    return float(np.median(np.abs(t - np.round(t / SIXTEENTH_S) * SIXTEENTH_S)) * 1000) if len(t) else 0.0


def whole_beats(x: np.ndarray, sr: int) -> np.ndarray:
    """The whole clip, uncut, on the set's beat: only complete beats of silence come off the front,
    so a pickup still lands where it did against the beat (the "yeah" of "turn up" on the and), and
    the silence after the last sound off the end. Whole bars kept up to 1.4 s of waiting."""
    m = np.abs(x).mean(axis=1)
    first = np.nonzero(m > m.max() * 10 ** (-30 / 20))[0]      # the first word, not a breath before it
    loud = np.nonzero(m > m.max() * 10 ** (-45 / 20))[0]
    if not len(first):
        return x
    beat = int(60.0 / 170.0 * sr)
    start = (first[0] // beat) * beat
    return x[start:min(len(x), loud[-1] + int(0.05 * sr))]


def cut(src: str, span) -> tuple[np.ndarray, int]:
    x, sr = read_wav(FITTED / fitted_name(src))
    bpm = source_bpm(src)
    beat_s = 60.0 / (target_bpm(bpm) if bpm else 170.0)
    if span == FULL:
        raw = whole_beats(x, sr)
    else:
        if span:
            i, j = settle(x, sr, int(span[0] * beat_s * sr), int(span[1] * beat_s * sr), beat_s)
            x = x[i:j]
        raw = tight(x, sr)
    y, _, _ = quantize(raw, sr)
    if grid_error_ms(y, sr) >= grid_error_ms(raw, sr):
        y = raw          # quantizing moved it further off ("eu tenho um arsenal": 5 ms -> 19 ms)
    y = fade(y, sr, in_ms=1.0)
    return y * (0.89 / max(1e-9, float(np.abs(y).max()))), sr


def lead_gap_ms(y: np.ndarray, sr: int) -> float:
    """Milliseconds before the file first comes within 30 dB of its peak."""
    mono = np.abs(y).mean(axis=1)
    return float(np.argmax(mono > mono.max() * 10 ** (-30 / 20))) / sr * 1000


def build() -> dict[str, dict[int, Path]]:
    made = {}
    for new, (old, picks) in KITS.items():
        out = ROOT / new
        out.mkdir(parents=True, exist_ok=True)
        made[new] = {}
        for pad, (phrase, src, span) in picks.items():
            dst = out / f"{pad:02d}-{phrase.replace(' ', '-')}{VERSION}.wav"
            made[new][pad] = dst
            if dst.exists():
                continue
            y, sr = cut(src, span)
            write_wav(dst, y, sr)
            print(f"  {new:<12} pad {pad}  {phrase:<24} {len(y) / sr:5.2f} s  lead-in {lead_gap_ms(y, sr):6.1f} ms"
                  f"  off-grid {grid_error_ms(y, sr):3.0f} ms")
    return made


def rebuild(made: dict[str, dict[int, Path]]) -> None:
    """A kit that replaces a track: rename it and swap its Drum Rack for a fresh one - the effects
    after the rack, the mixer and the clips stay. A new kit: a new track beside the previous kit,
    with the same effects (silent until turned up). Then fill the pads; a pad holding an older cut
    of its phrase gets the new one with its settings kept."""
    os.environ.setdefault("LIVE_CHANNEL_ENABLED", "1")
    import time
    from thelmic.live_channel import LiveChannel
    from jungle_drumkits import DRUM_RACK, _load_pad, _pad_device
    from jungle_build import fade_raw
    from jungle_reset import index_of, track_names
    from jungle_space import load_fx, set_number, _param
    from jungle_levels_native import ensure_level
    from jungle_vocal_chops import swap_sample, LEVEL_DB
    ch = LiveChannel(lower_priority=False)
    ch.start()

    def fresh_rack(t):
        ch.load_device(t, DRUM_RACK).result(timeout=30)
        for _ in range(80):
            devs = ch.get_track_info(t).result(timeout=5)["devices"]
            if any(d["name"] == "Drum Rack" for d in devs):
                return [d["name"] for d in devs]
            time.sleep(0.25)
        raise SystemExit("the Drum Rack never appeared")

    try:
        previous = None
        for new, (old, picks) in KITS.items():
            if new not in track_names(ch):
                if old:
                    t = index_of(ch, old)
                    devs = ch.get_track_info(t).result(timeout=5)["devices"]
                    if not devs or devs[0]["name"] != "Drum Rack" or devs[0].get("class_name", "DrumGroupDevice") != "DrumGroupDevice":
                        raise SystemExit(f"{old}: expected its Drum Rack first, found {[d['name'] for d in devs]}")
                    ch.delete_device(t, 0).result(timeout=10)
                    order = fresh_rack(t)
                    if order[0] != "Drum Rack":
                        raise SystemExit(f"{old}: the new Drum Rack landed at {order.index('Drum Rack')}: {order}")
                    ch.set_track_name(t, new).result(timeout=5)
                    print(f"  {old} -> {new}: " + " > ".join(order))
                else:
                    at = index_of(ch, previous) + 1 if previous else -1
                    t = ch.create_midi_track(at).result(timeout=10)["index"]
                    ch.set_track_name(t, new).result(timeout=5)
                    fresh_rack(t)
                    br = load_fx(ch, t, dict(uri="query:AudioFx#Beat%20Repeat", name="Beat Repeat"))
                    for pname, raw in (("Chance", None), ("Variation", 0.0), ("Device On", 0.0)):
                        p_ = _param(ch, t, br, pname)
                        ch.set_device_param(t, br, p_["index"], float(p_["max"]) if raw is None else raw).result(timeout=5)
                    rd = load_fx(ch, t, dict(uri="query:AudioFx#Redux", name="Redux"))
                    ch.set_device_param(t, rd, _param(ch, t, rd, "Dry/Wet")["index"], 0.0).result(timeout=5)
                    ec = load_fx(ch, t, dict(uri="query:AudioFx#Echo", name="Echo"))
                    ch.set_device_param(t, ec, _param(ch, t, ec, "Dry Wet")["index"], 0.0).result(timeout=5)
                    lv = ensure_level(ch, t, new)
                    set_number(ch, t, lv, "Output", LEVEL_DB)
                    print(f"  new {new} at track {t}: "
                          + " > ".join(d["name"] for d in ch.get_track_info(t).result(timeout=5)["devices"]))
            previous = new
            t = index_of(ch, new)
            for pad, path in made[new].items():
                have = _pad_device(ch, t, pad)
                if have:
                    loaded = str(have["properties"].get("sample.file_path", "")).replace(chr(92), "/").split("/")[-1]
                    if loaded != path.name and loaded.startswith(f"{pad:02d}-"):
                        swap_sample(ch, t, pad, f"vocal_kits/{new}", path.name, have)   # an older cut: settings kept
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
