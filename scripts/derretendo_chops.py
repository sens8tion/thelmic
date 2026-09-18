"""DERRETENDO CHOPS - her vocal chopped three ways, for audition.

The user: "can you chop her vocal in several different ways for me to audition it".

Three MIDI lanes after HARMONIA. Each is a Simpler in Slice mode holding the untouched original
(RP_JV_85_vocal_vibe_Gb), warped in Complex Pro and transposed -4 st, +12 c, like the lead. Simpler
reads the file as 64 beats at 170, as the clip does, so the slices play at her own speed. Nothing is
rendered: the slice points are Simpler's own, visible and movable. Slice N plays on note 36 + N,
Gate mode (the note's length is the chop's), each slice with its own voice so stutters overlap.

- PICADINHO ("minced"): a slice per syllable - der-re-TEN-do MEU co-ra-CAO... - cut just before
  each consonant: the last quiet frame before the syllable, or on legato syllables with no silence
  between them, where the last vowel's band (under 1.5 kHz) has fallen halfway to the consonant's
  trough - so the "c" hiss of coraCAO opens its slice instead of ending "ra"'s. Never after her
  pitch starts. Her notes come from derretendo.LEAD_NOTES.
- PALAVRA ("word"): a slice per word - derretendo, meu, coracao, como, gelo, ao sol, twice.
- GAGUEJA ("stutters"): Live's own 1/16 grid over her first 16 beats ("derretendo meu coracao,
  como") - 64 slices, Simpler's limit.

Pattern clips from row CLIP_ROW down, 8 bars each, with the vocal in a few windows, not every bar.
Launch a section, then a chop clip over it.

    python scripts/derretendo_chops.py
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))
from derretendo import BROWSER, DETUNE, FILE, LEAD_NOTES, TRANSPOSE  # noqa: E402

SRC = Path.home() / "Documents" / "Ableton" / "User Library" / "Samples" / "Splice" / "saudade_originals" / FILE
AFTER = "HARMONIA"
CLIP_ROW = 6                    # row 7: audition rows start here, so a section launch never fires them
CLIP_BEATS = 32.0
LEVEL_DB = -8.0                 # as the lead
BEAT_S = 60.0 / 170.0
SLICE_ROOT = 36
PRE_S, QUIET_DB = 0.30, -45.0   # a syllable's cut: within PRE_S before her pitch starts, the last frame
                                # quieter than QUIET_DB (re peak) - or, legato, where the vowel falls away
BEAT_STYLE, MANUAL_STYLE, SIXTEENTHS = 1, 3, 0      # sample.slicing_style / slicing_beat_division

P1 = ["DER", "re", "TEN", "do", "MEU", "co", "ra", "CAO", "CO", "mo", "GE", "lo", "SOL"]
P2 = ["DER2", "re2", "re2b", "TEN2", "do2", "MEU2", "co2", "ra2", "CAO2", "CO2", "mo2", "mo2b", "GE2", "lo2",
      "ao2", "SOL2", "tail2"]
WORDS = [("derretendo", "DER"), ("meu", "MEU"), ("coracao", "co"), ("como", "CO"), ("gelo", "GE"), ("ao sol", "ao"),
         ("derretendo2", "DER2"), ("meu2", "MEU2"), ("coracao2", "co2"), ("como2", "CO2"), ("gelo2", "GE2"),
         ("ao sol2", "ao2")]


def read_mono():
    from rap_audition import read_wav
    x, sr = read_wav(SRC)
    return x.mean(axis=1), sr


def envelope_db(x, sr, hop_s=0.005):
    hop = int(hop_s * sr)
    rms = np.sqrt(np.array([np.mean(x[i:i + hop] ** 2) for i in range(0, len(x) - hop, hop)]) + 1e-20)
    return 20 * np.log10(rms / rms.max()), hop


def vowel_db(x, sr, hop, lo_hz=80.0, hi_hz=1500.0, win=1024):
    """Energy below 1.5 kHz per hop - the vowel band. A consonant is where it falls away: an "s" or
    "c" is all hiss above it, a "d" or "r" a dip in it."""
    band = None
    out = []
    for i in range(0, len(x) - hop, hop):
        f = x[max(0, i + hop // 2 - win // 2):i + hop // 2 + win // 2]
        f = np.pad(f, (0, win - len(f))) * np.hanning(win)
        spec = np.abs(np.fft.rfft(f)) ** 2
        if band is None:
            hz = np.fft.rfftfreq(win, 1 / sr)
            band = (hz >= lo_hz) & (hz <= hi_hz)
        out.append(spec[band].sum())
    e = np.array(out) + 1e-20
    return 10 * np.log10(e / e.max())


def syllables() -> list[tuple[str, int]]:
    """(name, frame) of every syllable's cut, in order - with phrase 1's "ao", which the pitch tracker
    never saw as a note (it sits between "lo" and SOL), found by its energy."""
    x, sr = read_mono()
    db, hop = envelope_db(x, sr)
    names = P1[:12] + ["ao"] + P1[12:] + P2
    onsets = [n[0] * BEAT_S for n in LEAD_NOTES]
    # phrase 1's "ao": the first sustained sound after "lo" ends, well before SOL
    lo_end = (LEAD_NOTES[11][0] + LEAD_NOTES[11][1]) * BEAT_S + 0.1
    sol = LEAD_NOTES[12][0] * BEAT_S
    loud = [i * hop / sr for i in range(int(lo_end * sr / hop), int((sol - 0.3) * sr / hop))
            if db[i:i + 6].min() > -30]
    if not loud:
        raise SystemExit("no 'ao' found before phrase 1's SOL")
    onsets = onsets[:12] + [loud[0]] + onsets[12:]
    # where the syllable before each one stops sounding (its pitched note's end): the cut is looked
    # for from just before there, or a slow fade would put it inside the syllable before
    ends = [0.0] + [(s + l) * BEAT_S for s, l, _, _ in LEAD_NOTES]
    ends = ends[:13] + [ends[12]] + ends[13:-1]           # "ao" and SOL both follow "lo"
    vdb = vowel_db(x, sr, hop)
    cuts, prev = [], -1.0
    for name, t0, prev_end in zip(names, onsets, ends):
        if name == "DER":
            cuts.append((name, 0))
            prev = 0.0
            continue
        # never after her pitch starts: that's the attack gone
        lo_i = int(max(prev + 0.08, t0 - PRE_S, prev_end - 0.06, 0.0) * sr / hop)
        hi_i = max(lo_i + 1, int((t0 - 0.01) * sr / hop))
        quiet = np.nonzero(db[lo_i:hi_i] < QUIET_DB)[0]
        if len(quiet):
            i = lo_i + quiet[-1]                      # the last silence before the consonant
        else:
            # legato: the consonant starts where the last vowel falls away. From that vowel's peak
            # down to the consonant's trough, cut halfway down the fall - an "s" of 150 ms or more
            # then opens the slice whole, instead of splitting where the band bottoms out
            v = vdb[lo_i:hi_i]
            j_min = int(np.argmin(v))
            j_peak = int(np.argmax(v[:j_min + 1]))
            half = (v[j_peak] + v[j_min]) / 2
            i = lo_i + j_peak + int(np.nonzero(v[j_peak:j_min + 1] <= half)[0][0])
        t = i * hop / sr
        cuts.append((name, int(round(t * sr))))
        prev = t
    return cuts


def lanes():
    cuts = syllables()
    frame = dict(cuts)
    words = [(w, frame[s]) for w, s in WORDS]
    return {
        "PICADINHO": {"style": MANUAL_STYLE, "cuts": cuts},
        "PALAVRA": {"style": MANUAL_STYLE, "cuts": words},
        "GAGUEJA": {"style": BEAT_STYLE, "cuts": [(f"g{k}", int(round(k * BEAT_S / 4 * 44100))) for k in range(64)]},
    }


# ---- patterns: (beat, slice, beats long). Slices by name on PICADINHO and PALAVRA, by grid index on GAGUEJA.
def syl_patterns():
    a = [  # "coracao chamando": co-ra-CAO onto bar 3, a der-der-der stutter into MEU on bar 5,
           # co-ra-CAO again onto bar 7, GE-lo, ao SOL to close
        (7.0, "co", .5), (7.5, "ra", .5), (8.0, "CAO", 1.75),
        (14.0, "DER", .2), (14.25, "DER", .2), (14.5, "DER", .2), (14.75, "DER", .45),
        (15.25, "re", .25), (15.5, "TEN", .25), (15.75, "do", .25), (16.0, "MEU", 1.0),
        (23.0, "co2", .5), (23.5, "ra2", .5), (24.0, "CAO2", 1.75),
        (28.0, "GE", .75), (29.0, "lo", .75), (30.5, "ao", .5), (31.0, "SOL", 1.0)]
    b = [  # "gelo meu": the words reordered - gelo, coracao, gelo, meu - and a 16th-note derretendo
        (0.0, "GE", .5), (0.5, "lo", .75),
        (2.0, "co", .25), (2.25, "ra", .25), (2.5, "CAO", 1.25),
        (8.0, "GE2", .5), (8.5, "lo2", .5), (10.5, "MEU", 1.0),
        (16.0, "DER2", .25), (16.25, "DER2", .25), (16.5, "re2", .25), (16.75, "TEN2", .25),
        (17.0, "do2", .5), (17.5, "MEU2", .75),
        (23.5, "ao2", .5), (24.0, "SOL2", 2.0), (27.0, "tail2", 1.0)]
    return [("coracao chamando", a), ("gelo meu", b)]


def word_patterns(cuts):
    """"chamada": four words in eight bars, each placed so its stressed syllable lands on a bar line."""
    frame = dict(cuts)
    syl = dict(syllables())

    def at(word, stress, bar_beat):
        rel = (syl[stress] - frame[word]) / 44100 / BEAT_S
        return round((bar_beat - rel) * 4) / 4

    lead = {n: (s, l) for (s, l, _, _), n in zip(LEAD_NOTES, P1 + P2)}

    def length(word, last):
        s, l = lead[last]
        return round(s + l - frame[word] / 44100 / BEAT_S + 0.25, 2)
    a = [(at("coracao", "CAO", 8.0), "coracao", length("coracao", "CAO")),
         (at("gelo", "GE", 16.0), "gelo", length("gelo", "lo")),
         (at("ao sol", "SOL", 24.0), "ao sol", length("ao sol", "SOL")),
         (at("meu2", "MEU2", 30.0), "meu2", length("meu2", "MEU2"))]
    return [("chamada", a)]


def grid_patterns():
    def run(step, first, count):          # the grid played straight: her own audio, re-cut
        return [(step + i, first + i, 1) for i in range(count)]

    def stut(step, sl, times):             # one sixteenth, repeated
        return [(step + i, sl, 1) for i in range(times)]
    a = (stut(24, 34, 4) + run(28, 34, 10)                    # ca-ca-ca-ca-CAO: onto bar 3
         + stut(56, 0, 4) + run(60, 0, 8)                     # d-d-d-d-DERre: onto bar 5
         + run(72, 16, 8)                                     # TEN-do
         + stut(104, 21, 3) + run(107, 21, 9)                 # meu-meu-meu-MEU
         + stut(120, 63, 4) + [(124, 63, 4)])                 # ge-ge-ge-ge-GE...
    riff1 = [(0, 34, 2), (2, 35, 2), (4, 16, 1), (5, 16, 1), (6, 17, 2), (8, 54, 2), (10, 57, 2), (12, 63, 4)]
    riff2 = [(0, 0, 1), (1, 0, 1), (2, 0, 1), (3, 1, 1), (4, 26, 2), (6, 29, 2), (8, 34, 4), (12, 21, 2), (14, 22, 2)]
    riff3 = stut(0, 63, 4) + [(4, 63, 4)] + stut(8, 34, 4) + [(12, 34, 4)]
    b = [(16 * bar + s, sl, n) for bar, riff in ((1, riff1), (3, riff2), (5, riff1), (7, riff3)) for s, sl, n in riff]
    as_beats = lambda steps: [(s / 4, sl, n / 4) for s, sl, n in steps]
    return [("gagueira", as_beats(a)), ("rasgo", as_beats(b))]


def notes(pattern, index):
    return [{"pitch": SLICE_ROOT + index[sl], "start_time": float(b), "duration": float(n), "velocity": 100}
            for b, sl, n in pattern]


def main() -> None:
    os.environ.setdefault("LIVE_CHANNEL_ENABLED", "1")
    from thelmic.live_channel import LiveChannel
    from jungle_reset import index_of, track_names
    from jungle_space import set_number
    from jungle_levels_native import ensure_level
    from jungle_build import _wait_for_device, fade_raw
    spec = lanes()
    patterns = {"PICADINHO": syl_patterns(), "PALAVRA": word_patterns(spec["PALAVRA"]["cuts"]),
                "GAGUEJA": grid_patterns()}
    ch = LiveChannel(lower_priority=False)
    ch.start()
    try:
        prev = AFTER
        for name, lane in spec.items():
            if name not in track_names(ch):
                t = ch.create_midi_track(index_of(ch, prev) + 1).result(timeout=10)["index"]
                ch.set_track_name(t, name).result(timeout=5)
            prev = name
            t = index_of(ch, name)
            fresh = not ch.get_track_info(t).result(timeout=5)["device_count"]
            if fresh:
                ch.load_item_at_path(t, BROWSER, FILE).result(timeout=30)
                _wait_for_device(ch, t, 0)
            si = ch.get_sample_info(t, 0).result(timeout=10)
            if fresh or si.get("playback_mode") != 2 or si.get("slice_count") != len(lane["cuts"]):
                ps = {p["name"]: p["index"] for p in ch.get_device_info(t, 0).result(timeout=10)["parameters"]}
                ch.set_device_param(t, 0, ps["Snap"], 0.0).result(timeout=5)      # slice points where they're put
                ch.set_sample_property(t, 0, "warping", True).result(timeout=5)
                ch.set_sample_property(t, 0, "warp_mode", 6).result(timeout=5)   # Complex Pro: formants kept
                ch.set_device_property(t, 0, "playback_mode", 2).result(timeout=5)
                ch.set_sample_property(t, 0, "slicing_style", lane["style"]).result(timeout=5)
                if lane["style"] == BEAT_STYLE:
                    ch.set_sample_property(t, 0, "slicing_beat_division", SIXTEENTHS).result(timeout=5)
                else:
                    res = ch.set_sample_slices(t, 0, times=[f for _, f in lane["cuts"]]).result(timeout=20)
                    if res.get("failed"):
                        print(f"    [warn] {name}: {len(res['failed'])} slice(s) failed: {res['failed'][:3]}")
                ch.set_device_property(t, 0, "slicing_playback_mode", 1).result(timeout=5)   # a voice per slice
                ch.set_device_property(t, 0, "voices", 16).result(timeout=5)
                ch.set_device_param(t, 0, ps["Trigger Mode"], 1.0).result(timeout=5)   # Gate: the note's length
                ch.set_device_param(t, 0, ps["Fade In"], fade_raw(1.0)).result(timeout=5)
                ch.set_device_param(t, 0, ps["Fade Out"], fade_raw(10.0)).result(timeout=5)
                ch.set_device_param(t, 0, ps["Vol < Vel"], 0.0).result(timeout=5)
                set_number(ch, t, 0, "Transpose", float(TRANSPOSE))
                set_number(ch, t, 0, "Detune", float(DETUNE))
                set_number(ch, t, 0, "Volume", 0.0)
                set_number(ch, t, ensure_level(ch, t, name), "Output", LEVEL_DB)
                time.sleep(0.3)
                si = ch.get_sample_info(t, 0).result(timeout=10)
            if si.get("slice_count") != len(lane["cuts"]):
                raise SystemExit(f"{name}: {si.get('slice_count')} slices, expected {len(lane['cuts'])}")
            index = {n: k for k, (n, _) in enumerate(lane["cuts"])} if lane["style"] == MANUAL_STYLE else {k: k for k in range(64)}
            c = ch.get_track_clips(t).result(timeout=10)
            filled = {x.get("slot", x.get("index")) for x in (c.get("clips", c) if isinstance(c, dict) else c)}
            for r, (pname, pattern) in enumerate(patterns[name], start=CLIP_ROW):
                if r not in filled:
                    ch.create_clip(t, r, CLIP_BEATS).result(timeout=10)
                    ch.add_notes_to_clip(t, r, notes(pattern, index), replace=True).result(timeout=10)
                ch.set_clip_name(t, r, f"{name.lower()} - {pname}").result(timeout=5)
            print(f"  {name:<10} (track {t + 1}): {si.get('slice_count')} slices, notes {SLICE_ROOT}-"
                  f"{SLICE_ROOT + si.get('slice_count') - 1}; clips rows {CLIP_ROW + 1}-{CLIP_ROW + len(patterns[name])}: "
                  + ", ".join(p for p, _ in patterns[name]))
    finally:
        ch.stop()


if __name__ == "__main__":
    if "--cuts" in sys.argv:
        for n, f in syllables():
            print(f"  {n:<6} {f / 44100:7.3f} s  beat {f / 44100 / BEAT_S:6.2f}")
    else:
        main()
