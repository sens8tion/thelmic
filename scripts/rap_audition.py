"""RAP AUDITION - the Splice rap / MC vocals, fitted to the set's tempo and laid out beside its clips.

The user parked the rendered vocals ("not plastic enough, and quite a long way from deterministic")
and asked for "rap, visceral voice" from Splice, Portuguese and Latin included, set up "for an
audition adjacent to the other clips".

Each loop is time-stretched offline, pitch kept, to 170 - or to 85, half-time, when that is the
smaller stretch - so it plays unwarped and lands on the grid without Live guessing its tempo.
One-shots are left as they are. The stretch is WSOLA with the grain positions chosen on the mono
mix and applied to every channel, so a wet vocal's stereo doesn't smear.

Placement: three new audio tracks at the end of the set, clips from row FIRST_ROW down. Rows
0-5 are the sections, and a clip there would fire every time the user launches one. Rows are
added at the bottom as needed; an existing clip is never replaced.

    python scripts/rap_audition.py            # stretch + place
    python scripts/rap_audition.py --files    # stretch only
"""
from __future__ import annotations

import os
import re
import struct
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

SRC = Path.home() / "Documents" / "Splice" / "Samples" / "thelmic_rap_2026-09-18"
OUT = Path.home() / "Documents" / "Ableton" / "User Library" / "Samples" / "Splice" / "rap_2026-09-18_170"
OUT_BROWSER = "user_library/Samples/Splice/rap_2026-09-18_170"
TEMPO = 170.0
FIRST_ROW = 6
LEVEL_DB = -8.0          # unmatched on the meter, and the user may be playing: start low

# track -> files, in audition order. Names: bars (rap) you'd wash your mouth out for; shouts; and
# "fala serio" (Portuguese: "you're kidding").
LANES = {
    "BARS-OF-SOAP": [   # UK rap, grime, drill, DnB MC
        "VOX_URG_165_vocal_rap_turn_up_dry.wav",
        "007_Vocal_174bpm_G_-_REFLEXDNB_Zenhiser_-_REFLEXDNB_Zenhiser.wav",
        "RKU_AU_140_vocal_lead_male_rap_loop_strikes_dry.wav",
        "RKU_AU_140_vocal_hook_male_rap_loop_unknown_dry.wav",
        "VOX_URG_145_vocal_rap_too_easy_backing_dry.wav",
        "91V_UKB2_140_vocal_hook_male_rap_rave_explode_dry.wav",
        "VOX_UKR_140_vocal_hook_rap_music_gal_dry.wav",
        "VOX_UKR_128_vocal_hook_rap_excuse_dry.wav",
        "004_Vocal_Loop_140bpm_C_-_CONCUSSION_Zenhiser.wav",
        "tp_udnb_174_vocal_phrase_mysterious_Amin.wav",
        "TRKTRN_PASHAGUD_110_VOCAL_GONE.wav",
    ],
    "SHOUT-OUT": [      # ragga, dancehall, jungle / DnB shouts and adlibs
        "91V_VHH_140_Vocal_Dancehall_Soldier_Clean.wav",
        "VR_HBD3_150_vocal_shout_loop_SoundboiKilla_fx.wav",
        "PMRDW3_Vocal_Shout_Jungle.wav",
        "PMJP2_Vocal_Skanka.wav",
        "PMJP3_vocal_like_this_effected.wav",
        "PMWT2_Vocal_Chant_Fiyah.wav",
        "BOS_LevIV_Vocal_Phrase_One_Shot_FireBlazing.wav",
        "DS_UKDNB_vocal_adlib_male_whoop_wet.wav",
        "DS_UKDNB_vocal_adlib_male_whoh_wet.wav",
    ],
    "FALA-SERIO": [     # Brazilian funk MCs, in Portuguese
        "VOX_LBP_150_vocal_hook_arsenal_low_Cmin.wav",
        "VOX_LBP_140_vocal_chop_norave.wav",
        "VOX_LBP_140_vocal_hook_casamento_Cmin.wav",
        "SO_BFV_130_vocal_loop_kelake_Dmin.wav",
        "SO_BFV_130_vocal_loop_rabeta_Fmin.wav",
        "VOX_LBP_130_vocal_phrase_chao_Emin.wav",
        "VOX_LBP_130_vocal_phrase_famoso_Emin.wav",
    ],
}


# clip names: what each one says, and where from (the file names are pack codes)
LABELS = {
    "VOX_URG_165_vocal_rap_turn_up_dry.wav": "turn up (grime)",
    "007_Vocal_174bpm_G_-_REFLEXDNB_Zenhiser_-_REFLEXDNB_Zenhiser.wav": "DnB MC, 2.5 min",
    "RKU_AU_140_vocal_lead_male_rap_loop_strikes_dry.wav": "strikes (drill)",
    "RKU_AU_140_vocal_hook_male_rap_loop_unknown_dry.wav": "unknown (drill)",
    "VOX_URG_145_vocal_rap_too_easy_backing_dry.wav": "too easy (grime)",
    "91V_UKB2_140_vocal_hook_male_rap_rave_explode_dry.wav": "rave explode",
    "VOX_UKR_140_vocal_hook_rap_music_gal_dry.wav": "music gal",
    "VOX_UKR_128_vocal_hook_rap_excuse_dry.wav": "excuse",
    "004_Vocal_Loop_140bpm_C_-_CONCUSSION_Zenhiser.wav": "concussion (DnB)",
    "tp_udnb_174_vocal_phrase_mysterious_Amin.wav": "mysterious (DnB)",
    "TRKTRN_PASHAGUD_110_VOCAL_GONE.wav": "gone (half-time)",
    "91V_VHH_140_Vocal_Dancehall_Soldier_Clean.wav": "dancehall soldier",
    "VR_HBD3_150_vocal_shout_loop_SoundboiKilla_fx.wav": "soundboi killa",
    "PMRDW3_Vocal_Shout_Jungle.wav": "JUNGLE!",
    "PMJP2_Vocal_Skanka.wav": "skanka",
    "PMJP3_vocal_like_this_effected.wav": "like this",
    "PMWT2_Vocal_Chant_Fiyah.wav": "fiyah",
    "BOS_LevIV_Vocal_Phrase_One_Shot_FireBlazing.wav": "fire blazing",
    "DS_UKDNB_vocal_adlib_male_whoop_wet.wav": "whoop",
    "DS_UKDNB_vocal_adlib_male_whoh_wet.wav": "whoh",
    "VOX_LBP_150_vocal_hook_arsenal_low_Cmin.wav": "arsenal",
    "VOX_LBP_140_vocal_chop_norave.wav": "no rave",
    "VOX_LBP_140_vocal_hook_casamento_Cmin.wav": "casamento",
    "SO_BFV_130_vocal_loop_kelake_Dmin.wav": "kelake",
    "SO_BFV_130_vocal_loop_rabeta_Fmin.wav": "rabeta",
    "VOX_LBP_130_vocal_phrase_chao_Emin.wav": "chão",
    "VOX_LBP_130_vocal_phrase_famoso_Emin.wav": "famoso",
}


# --- WAV in and out, without soundfile ---------------------------------------------------------

def read_wav(path: Path) -> tuple[np.ndarray, int]:
    """(frames x channels float64 in -1..1, sample rate) for PCM 16/24/32-bit or float WAV."""
    b = path.read_bytes()
    if b[:4] != b"RIFF" or b[8:12] != b"WAVE":
        raise ValueError(f"{path.name}: not a RIFF/WAVE file")
    pos, fmt, data = 12, None, None
    while pos + 8 <= len(b):
        cid, size = b[pos:pos + 4], struct.unpack("<I", b[pos + 4:pos + 8])[0]
        body = b[pos + 8:pos + 8 + size]
        if cid == b"fmt ":
            tag, ch, sr, _, _, bits = struct.unpack("<HHIIHH", body[:16])
            if tag == 0xFFFE and len(body) >= 26:
                tag = struct.unpack("<H", body[24:26])[0]      # the sub-format's first two bytes
            fmt = (tag, ch, sr, bits)
        elif cid == b"data":
            data = body
        pos += 8 + size + (size & 1)
    if fmt is None or data is None:
        raise ValueError(f"{path.name}: no fmt or data chunk")
    tag, ch, sr, bits = fmt
    if tag == 3:
        x = np.frombuffer(data, dtype="<f4" if bits == 32 else "<f8").astype(np.float64)
    elif bits == 16:
        x = np.frombuffer(data, dtype="<i2").astype(np.float64) / 32768.0
    elif bits == 24:
        a = np.frombuffer(data[:len(data) // 3 * 3], dtype=np.uint8).reshape(-1, 3).astype(np.int32)
        v = a[:, 0] | (a[:, 1] << 8) | (a[:, 2] << 16)
        x = np.where(v >= 1 << 23, v - (1 << 24), v).astype(np.float64) / float(1 << 23)
    elif bits == 32:
        x = np.frombuffer(data, dtype="<i4").astype(np.float64) / float(1 << 31)
    else:
        raise ValueError(f"{path.name}: {bits}-bit format {tag} not handled")
    n = len(x) // ch * ch
    return x[:n].reshape(-1, ch), sr


def write_wav(path: Path, y: np.ndarray, sr: int) -> None:
    """24-bit PCM."""
    y = np.clip(y, -1.0, 1.0 - 1.0 / (1 << 23))
    v = np.round(y * (1 << 23)).astype(np.int32).reshape(-1)
    v = np.where(v < 0, v + (1 << 24), v).astype(np.uint32)
    raw = np.stack([v & 0xFF, (v >> 8) & 0xFF, (v >> 16) & 0xFF], axis=1).astype(np.uint8).tobytes()
    ch = y.shape[1]
    fmt = struct.pack("<HHIIHH", 1, ch, sr, sr * ch * 3, ch * 3, 24)
    path.write_bytes(b"RIFF" + struct.pack("<I", 36 + len(raw)) + b"WAVE"
                     + b"fmt " + struct.pack("<I", 16) + fmt + b"data" + struct.pack("<I", len(raw)) + raw)


# --- tempo --------------------------------------------------------------------------------------

def source_bpm(name: str) -> float | None:
    """From the Splice file name: `_140_`, `174bpm`, `_130bpm_`. None for a one-shot. The first
    number in tempo range: Zenhiser names open with a track number ("007_Vocal_174bpm_G")."""
    for m in re.finditer(r"(?:^|_)(\d{2,3})(?:bpm)?(?=_|bpm|\.)", Path(name).stem, re.I):
        if 60 <= float(m.group(1)) <= 200:
            return float(m.group(1))
    return None


def target_bpm(bpm: float) -> float:
    """TEMPO, or half of it, whichever is the smaller stretch."""
    return min((TEMPO, TEMPO / 2), key=lambda t: abs(np.log(t / bpm)))


def wsola(x: np.ndarray, ratio: float, sr: int, frame_ms: float = 25.0, tol_ms: float = 6.0) -> np.ndarray:
    """Time-scale frames x channels by `ratio` (output / input length), pitch kept. Grain positions
    are chosen on the mono mix and applied to every channel."""
    n = int(frame_ms / 1000 * sr) // 2 * 2
    hs, ha, tol = n // 2, (n // 2) / ratio, int(tol_ms / 1000 * sr)
    win = np.hanning(n)
    padn = n + tol
    pad = np.concatenate([np.zeros((padn, x.shape[1])), x, np.zeros((2 * n + tol, x.shape[1]))])
    mono = pad.mean(axis=1)
    out_len = int(len(x) * ratio) + n
    y = np.zeros((out_len + n, x.shape[1]))
    norm = np.zeros(out_len + n)
    prev, k = padn, 0
    while True:
        out_pos, nominal = k * hs, int(padn + k * ha)
        if out_pos >= out_len or nominal + n + tol >= len(pad):
            break
        if k == 0:
            best = nominal
        else:
            target = mono[prev + hs:prev + hs + n]
            lo = nominal - tol
            corr = np.correlate(mono[lo:lo + n + 2 * tol], target, mode="valid")
            best = lo + int(np.argmax(corr))
        y[out_pos:out_pos + n] += pad[best:best + n] * win[:, None]
        norm[out_pos:out_pos + n] += win
        prev, k = best, k + 1
    y = y[:out_len] / np.maximum(norm[:out_len], 1e-3)[:, None]
    return y[:int(len(x) * ratio)]


def fitted_name(name: str) -> str:
    bpm = source_bpm(name)
    stem = Path(name).stem
    return f"{stem}__at{int(target_bpm(bpm))}.wav" if bpm else f"{stem}__oneshot.wav"


def build() -> dict[str, Path]:
    OUT.mkdir(parents=True, exist_ok=True)
    made = {}
    for files in LANES.values():
        for name in files:
            dst = OUT / fitted_name(name)
            made[name] = dst
            if dst.exists():
                continue                      # may be loaded in Live, which holds it open
            x, sr = read_wav(SRC / name)
            bpm = source_bpm(name)
            y = wsola(x, bpm / target_bpm(bpm), sr) if bpm and abs(bpm - target_bpm(bpm)) > 0.5 else x
            y = y * (0.89 / max(1e-9, float(np.abs(y).max())))
            write_wav(dst, y, sr)
            what = f"{bpm:g} -> {target_bpm(bpm):g}" if bpm else "one-shot"
            print(f"  {name[:60]:<60} {what:<12} {len(y) / sr:6.1f} s")
    return made


# --- into Live ----------------------------------------------------------------------------------

def place(made: dict[str, Path]) -> None:
    os.environ.setdefault("LIVE_CHANNEL_ENABLED", "1")
    import time
    from thelmic.live_channel import LiveChannel
    from jungle_reset import index_of, track_names
    from jungle_space import set_number
    from jungle_levels_native import ensure_level
    ch = LiveChannel(lower_priority=False)
    ch.start()
    try:
        need = FIRST_ROW + max(len(v) for v in LANES.values())
        have = ch.get_scene_count().result(timeout=5)["count"]
        for _ in range(need - have):
            ch.create_scene(-1).result(timeout=10)
        if need > have:
            print(f"  added {need - have} rows at the bottom (now {need})")
        for lane, files in LANES.items():
            fresh = lane not in track_names(ch)
            if fresh:
                t = ch.create_audio_track(-1).result(timeout=10)["index"]
                ch.set_track_name(t, lane).result(timeout=5)
            t = index_of(ch, lane)
            clips = ch.get_track_clips(t).result(timeout=10)
            filled = {c.get("slot", c.get("index")) for c in (clips.get("clips", clips) if isinstance(clips, dict) else clips)}
            for row, name in enumerate(files, start=FIRST_ROW):
                if row in filled:
                    continue
                ch.load_audio_to_slot(t, row, OUT_BROWSER, made[name].name).result(timeout=30)
                for _ in range(40):
                    try:
                        ch.set_clip_warp(t, row, warping=False).result(timeout=5)
                        break
                    except Exception:
                        time.sleep(0.25)
                label = LABELS.get(name, Path(name).stem[:28])
                ch.set_clip_name(t, row, label).result(timeout=5)
                print(f"  {lane:<13} row {row:2d}  {label}")
            if fresh:
                lv = ensure_level(ch, t, lane)
                set_number(ch, t, lv, "Output", LEVEL_DB)
    finally:
        ch.stop()


if __name__ == "__main__":
    made = build()
    if "--files" not in sys.argv:
        place(made)
