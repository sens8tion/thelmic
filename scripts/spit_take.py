"""SPIT-TAKE - a first pass of rap / MC sub-phrases, cut from the audition clips onto a Drum Rack.

The user: "you do the 1st pass of selection of sub-phrases". Picked for use over jungle: hooks and
instructions an MC would shout, short enough to drop on a pad, each from a clip that measured dry.
The first Push page (pads 36-51) holds the strongest; 52-59 the rest.

A phrase's span comes from the transcriber's word timings (scripts/rap_words.py), which are only
good to a tenth of a second or so. Each cut is then settled on the audio: the start moves to where
the sound actually begins (back through a word already sounding, or forward out of silence), the
end to where it actually stops. Cut from the clip as it plays in the set - stretched to 170 (or 85)
- so every phrase is already on the grid.

    python scripts/spit_take.py             # cut, then load onto SPIT-TAKE
    python scripts/spit_take.py --files     # cut only
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

TRACK = "SPIT-TAKE"
FOLDER = "spit_take"
DIR = Path.home() / "Documents" / "Ableton" / "User Library" / "Samples" / "Imported" / FOLDER
BROWSER = f"user_library/Samples/Imported/{FOLDER}"
LEVEL_DB = -8.0

# pad -> (name, source clip, (from beat, to beat) on the clip's own timeline, or None for all of it)
PICKS = {
    # page 1: the hooks and the instructions
    36: ("oldskool jungalist", "TSP_HTM_175_vocal_dry_mc_multiplex_oldskool_jungalist_Gmin.wav", None),
    37: ("hold tight", "TSP_HTM_175_vocal_dry_mc_multiplex_hold_tight_Gmin.wav", None),
    38: ("lotta mercy", "TSP_HTM_175_vocal_dry_mc_multiplex_lotta_mercy_Gmin.wav", None),
    39: ("riddim", "TSP_HTM_175_vocal_dry_mc_multiplex_riddim_Gmin.wav", None),
    40: ("turn up turn up", "VOX_URG_165_vocal_rap_turn_up_dry.wav", (27.8, 32.1)),
    41: ("get spun up spun up", "VOX_URG_165_vocal_rap_turn_up_dry.wav", (11.3, 16.8)),
    42: ("the crowd say boo", "91V_UKB2_140_vocal_hook_male_rap_rave_explode_dry.wav", (0.0, 3.4)),
    43: ("shock the rave", "91V_UKB2_140_vocal_hook_male_rap_rave_explode_dry.wav", (9.1, 15.5)),
    44: ("whats your excuse", "VOX_UKR_128_vocal_hook_rap_excuse_dry.wav", (0.0, 2.9)),   # to "everybody"
    45: ("want it down low", "VOX_UKR_140_vocal_hook_rap_music_gal_dry.wav", (12.6, 15.3)),
    46: ("just leave me alone", "RKU_AU_140_vocal_hook_male_rap_loop_unknown_dry.wav", (26.2, 28.4)),
    47: ("just show my face", "RKU_AU_140_vocal_hook_male_rap_loop_unknown_dry.wav", (53.4, 55.9)),
    48: ("loudest sound on land", "RKU_AU_140_vocal_lead_male_rap_loop_strikes_dry.wav", (11.3, 15.4)),
    49: ("me a di soldier", "91V_VHH_140_Vocal_Dancehall_Soldier_Clean.wav", (0.0, 3.2)),
    50: ("vai de novo", "VOX_LBP_140_vocal_chop_norave.wav", (0.0, 2.2)),
    51: ("te deixar no chao", "VOX_LBP_150_vocal_hook_arsenal_low_Cmin.wav", (12.6, 15.4)),
    # page 2
    52: ("joga a rabeta no chao", "SO_BFV_130_vocal_loop_rabeta_Fmin.wav", (19.7, 23.4)),
    53: ("give them money im gone", "TRKTRN_PASHAGUD_110_VOCAL_GONE.wav", (1.8, 4.6)),
    54: ("fire blazing", "BOS_LevIV_Vocal_Phrase_One_Shot_FireBlazing.wav", None),
    55: ("pull it", "tp_bmve_vocal_pull_it_dry.wav", None),
    56: ("get em", "tp_bmve_vocal_get_em_dry.wav", None),
    # the whole line: cut to its words' timings, "sem sentimento" came back as "eu sei, eu sei"
    57: ("sabe que e sem sentimento", "VOX_LBP_140_vocal_hook_casamento_Cmin.wav", (11.1, 19.9)),
    58: ("wont leave our gang", "RKU_AU_140_vocal_lead_male_rap_loop_strikes_dry.wav", (58.9, 63.5)),
    59: ("all a mercy", "TSP_HTM_175_vocal_dry_mc_multiplex_all_A_mercy_Gmin.wav", None),
}

SILENT_DB = -45.0      # under the clip's peak
# v2: no gap at the front (the user: "36 has a big ole gap" - the Test Press phrases each sit
# inside a bar of silence, and were loaded whole). New names: Live holds the v1 files open.
VERSION = "-v2"
FRAME_S = 0.005


def settle(x: np.ndarray, sr: int, i: int, j: int, beat_s: float) -> tuple[int, int]:
    """Move [i, j) onto where the phrase actually sounds.

    A start in a gap moves forward to the first sound (at most a beat); an end in a gap moves back
    to the last. A start or end that lands IN sound moves to the deepest dip nearby - not "back to
    silence": rap runs its words together, there is no silence to find, and walking back to it took
    half a beat of the previous word ("DO we turn up", "NOW get spun up").
    """
    mono = x.mean(axis=1)
    peak = float(np.abs(mono).max()) or 1e-9
    win = int(FRAME_S * sr)

    def level(k: int) -> float:
        seg = mono[max(0, k):max(0, k) + win]
        return 20 * np.log10(max(float(np.sqrt(np.mean(seg ** 2))), 1e-12) / peak) if len(seg) else -200.0

    # How far inward a cut may move, measured on the 24 picks: a start up to a quarter beat (the
    # transcriber's word starts run early - an eighth left "NOW I get spun up"), an end only an
    # eighth (a word has dips of its own: a quarter found the one inside "ex-cuse")
    quarter, eighth = int(0.25 * beat_s * sr), int(0.125 * beat_s * sr)
    half, whole = int(0.5 * beat_s * sr), int(beat_s * sr)
    if level(i) > SILENT_DB:
        i = min(range(max(0, i - half), min(len(mono), i + quarter), win), key=level)
    else:
        hi = min(len(mono), i + whole)
        while i < hi and level(i) <= SILENT_DB:
            i += win
    if level(j - win) > SILENT_DB:
        j = min(range(max(i + win, j - eighth), min(len(mono), j + half), win), key=level)
    else:
        while j - win > i + win and level(j - win) <= SILENT_DB:
            j -= win
    return max(0, i - int(0.005 * sr)), min(len(mono), j + int(0.015 * sr))


ONSET_DB = -40.0       # under the phrase's own peak: where it starts sounding
TAIL_DB = -48.0        # and where it has stopped


def tight(y: np.ndarray, sr: int) -> np.ndarray:
    """Trim to where the phrase sounds: no gap at the front (the user: pad 36 "has a big ole gap" -
    the Test Press phrases each sit inside a bar of silence), and none trailing."""
    mono = np.abs(y).mean(axis=1)
    win = int(0.002 * sr)
    env = np.array([np.sqrt(np.mean(mono[k:k + win] ** 2)) for k in range(0, len(mono) - win, win)])
    db = 20 * np.log10(np.maximum(env, 1e-12) / max(env.max(), 1e-12))
    on = np.nonzero(db > ONSET_DB)[0]
    loud = np.nonzero(db > TAIL_DB)[0]
    if not len(on):
        return y
    i = max(0, on[0] * win - int(0.002 * sr))
    j = min(len(y), (loud[-1] + 1) * win + int(0.02 * sr))
    return y[i:j]


def fade(y: np.ndarray, sr: int, in_ms: float = 3.0, out_ms: float = 15.0) -> np.ndarray:
    y = y.copy()
    a, b = int(in_ms / 1000 * sr), int(out_ms / 1000 * sr)
    y[:a] *= np.linspace(0, 1, a)[:, None]
    y[len(y) - b:] *= np.linspace(1, 0, b)[:, None]
    return y


def cut_all() -> dict[int, Path]:
    DIR.mkdir(parents=True, exist_ok=True)
    made = {}
    for pad, (name, src, span) in PICKS.items():
        dst = DIR / f"{pad:02d}-{name.replace(' ', '-')}{VERSION}.wav"
        made[pad] = dst
        if dst.exists():
            continue                                  # Live holds a loaded one open
        x, sr = read_wav(FITTED / fitted_name(src))
        bpm = source_bpm(src)
        beat_s = 60.0 / (target_bpm(bpm) if bpm else 170.0)
        if span:
            i, j = settle(x, sr, int(span[0] * beat_s * sr), int(span[1] * beat_s * sr), beat_s)
        else:
            i, j = 0, len(x)
        y = fade(tight(x[i:j], sr), sr, in_ms=1.0)
        y *= 0.89 / max(1e-9, float(np.abs(y).max()))
        write_wav(dst, y, sr)
        where = f"beats {i / sr / beat_s:5.2f}-{j / sr / beat_s:5.2f}" if span else "whole clip"
        print(f"  pad {pad}  {name:<24} {len(y) / sr:4.2f} s  {where}")
    return made


def kit(made: dict[int, Path]) -> None:
    os.environ.setdefault("LIVE_CHANNEL_ENABLED", "1")
    import time
    from thelmic.live_channel import LiveChannel
    from jungle_drumkits import DRUM_RACK, _load_pad, _pad_device
    from jungle_build import fade_raw
    from jungle_reset import index_of, track_names
    from jungle_space import set_number
    from jungle_levels_native import ensure_level
    ch = LiveChannel(lower_priority=False)
    ch.start()
    try:
        fresh = TRACK not in track_names(ch)
        if fresh:
            t = ch.create_midi_track(-1).result(timeout=10)["index"]
            ch.set_track_name(t, TRACK).result(timeout=3)
            ch.load_device(t, DRUM_RACK).result(timeout=30)
            for _ in range(80):
                if ch.get_track_info(t).result(timeout=5)["device_count"]:
                    break
                time.sleep(0.25)
        t = index_of(ch, TRACK)
        from jungle_vocal_chops import swap_sample
        for pad, path in made.items():
            have = _pad_device(ch, t, pad)
            if have:
                loaded = str(have["properties"].get("sample.file_path", "")).replace("\\", "/").split("/")[-1]
                if loaded != path.name and loaded.startswith(f"{pad:02d}-"):
                    swap_sample(ch, t, pad, FOLDER, path.name, have)      # an older cut: settings kept
                continue
            _load_pad(ch, t, pad, BROWSER, path.name)
            ch.set_drum_pad_chain_device_property(t, 0, pad, "playback_mode", 1, 0).result(timeout=10)   # one-shot
            try:
                ch.set_drum_pad_chain_device_property(t, 0, pad, "sample.warping", False, 0).result(timeout=10)
            except Exception as e:
                print(f"    [warn] pad {pad}: warping not set ({e})")
            # Trigger, not Gate: a phrase plays to its end however short the note
            for key, value in (("Trigger Mode", 0), ("Fade In", fade_raw(1.0)), ("Fade Out", fade_raw(8.0)), ("Snap", 0)):
                try:
                    ch.set_drum_pad_chain_device_param(t, 0, pad, float(value), param_name=key,
                                                       chain_device_index=0).result(timeout=10)
                except Exception as e:
                    print(f"    [warn] pad {pad}: {key} not set ({e})")
            print(f"  pad {pad} {PICKS[pad][0]}")
        if fresh:
            lv = ensure_level(ch, t, TRACK)
            set_number(ch, t, lv, "Output", LEVEL_DB)
        print(f"  {TRACK}: " + " > ".join(d["name"] for d in ch.get_track_info(t).result(timeout=5)["devices"]))
    finally:
        ch.stop()


if __name__ == "__main__":
    made = cut_all()
    if "--files" not in sys.argv:
        kit(made)
