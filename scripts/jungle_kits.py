"""JUNGLE KITS - drum infrastructure for the scene rules (tracks/2026-09-16_jungle_scene_rules.md).

Main breaks, one per section, full range:
  AMEN-DMENT   Amen        (already there)
  COLD-CUTS    Cold Sweat  copy of SWEAT-SHOP's slice kit, reverb and auto-pan removed, low cut 120 Hz
  CHOPPER      Apache      copy of TOPSOIL's slice kit, Redux, reverb and auto-pan removed, low cut 120 Hz

Variant pads on each main break, from note 72: pitched and start-offset copies of slices (the break
file with markers), plus reversed and stretched slices rendered to files. The stretch is a grain
stretch with no phase alignment, so it carries sampler-style metallic artefacts on purpose.

Spine lanes (kick on 1, snares on 2 and 4, kick on the "and" of 3), each with its own voice:
  SPINE-TINGLER  Bonzo Kit (Beat Tools)               Drum Buss, Drums Room reverb
  SPINAL-TAP     Vintage Madman Kit (Chop and Swing)  Saturator, Snare Plate Digital Vintage
  SPINELESS      909 Flavour Kit (Drum Essentials)    Redux, 45 ms slapback

Idempotent: existing tracks, pads and effects are left alone. Every new track is checked on the meter.
Writes scripts/jungle_kit_map.json (variant pads, spine kick/snare notes) for jungle_rows.py.

    python scripts/jungle_kits.py --render    # just render the reversed/stretched files
    python scripts/jungle_kits.py             # render if needed, then build in Live
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import wave

import numpy as np

os.environ.setdefault("LIVE_CHANNEL_ENABLED", "1")
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(SCRIPTS_DIR))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from jungle_slices import BREAKS  # noqa: E402

USER_LIB = r"C:\Users\eric\Documents\Ableton\User Library"
VARIANT_DIR = os.path.join(USER_LIB, "Samples", "Imported", "jungle_variants")
VARIANT_BROWSER = "user_library/Samples/Imported/jungle_variants"
MAP_PATH = os.path.join(SCRIPTS_DIR, "jungle_kit_map.json")
CORE_FX = "packs/Core Library/Devices/Audio Effects"

# source break for each slice map in jungle_slices.BREAKS (keyed by the track the slices were cut for)
BREAK_FILES = {
    "AMEN-DMENT": ("user_library/Samples/Splice", r"Samples\Splice", "TSP_IHD_160_drum_break_amen_chop_4bar.wav", 1.0, 0.0),
    "SWEAT-SHOP": ("user_library/Samples/Imported/segura_breaks", r"Samples\Imported\segura_breaks",
                   "KCSB1_174_ColdSweatBreak_01_HighToneFortified_NoRide_Saturated_Wide.wav", 0.0, -40.0),
    "TOPSOIL": ("user_library/Samples/Imported/segura_breaks", r"Samples\Imported\segura_breaks",
                "KAPB1_174_ApacheBreak_01_HighTone_Normal.wav", 0.0, -40.0),
}
# main break track -> (slices from, copy of track, effects to remove)
MAIN_BREAKS = {
    "AMEN-DMENT": ("AMEN-DMENT", None, ()),
    "COLD-CUTS": ("SWEAT-SHOP", "SWEAT-SHOP", ("High Verb", "Pan Pendulum")),
    "CHOPPER": ("TOPSOIL", "TOPSOIL", ("Redux", "High Verb", "Pan Around The Head")),
}
# variant pads: note -> (kind, slice, amount). pitch: semitones; offset: fraction of the slice skipped;
# stretch: length factor. Slices chosen by label: snares for pitch/stretch/stutter, a kick pitched down,
# a snare and a hat or hand drum reversed.
VARIANTS = {
    "AMEN-DMENT": {72: ("pitch", 21, 12), 73: ("pitch", 9, 7), 74: ("pitch", 0, -3), 75: ("offset", 21, 0.3),
                   76: ("reverse", 21, 0), 77: ("reverse", 22, 0), 78: ("stretch", 21, 2.0), 79: ("stretch", 17, 1.5)},
    "COLD-CUTS": {72: ("pitch", 2, 12), 73: ("pitch", 12, 7), 74: ("pitch", 0, -3), 75: ("offset", 7, 0.3),
                  76: ("reverse", 2, 0), 77: ("reverse", 9, 0), 78: ("stretch", 12, 2.0), 79: ("stretch", 4, 1.5)},
    "CHOPPER": {72: ("pitch", 4, 12), 73: ("pitch", 11, 7), 74: ("pitch", 0, -3), 75: ("offset", 18, 0.3),
                76: ("reverse", 11, 0), 77: ("reverse", 20, 0), 78: ("stretch", 18, 2.0), 79: ("stretch", 8, 1.5)},
}
SPINES = {
    "SPINE-TINGLER": dict(kit=("packs/Beat Tools/Drums", "Bonzo Kit.adg"),
                          fx=[dict(uri="query:AudioFx#Drum%20Buss", name="Drum Buss"),
                              dict(path=f"{CORE_FX}/Reverb/Room", item="Drums Room.adv", name="Drums Room")],
                          settings=[("Drums Room", "Dry/Wet", 15.0)]),
    "SPINAL-TAP": dict(kit=("packs/Chop and Swing/Drums", "Vintage Madman Kit.adg"),
                       fx=[dict(uri="query:AudioFx#Saturator", name="Saturator"),
                           dict(path=f"{CORE_FX}/Hybrid Reverb/Drums", item="Snare Plate Digital Vintage.adv",
                                name="Snare Plate Digital Vintage")],
                       settings=[("Saturator", "Drive", 6.0), ("Snare Plate Digital Vintage", "Dry/Wet", 20.0)]),
    "SPINELESS": dict(kit=("packs/Drum Essentials/Drums/Drum Machines", "909 Flavour Kit.adg"),
                      fx=[dict(uri="query:AudioFx#Redux", name="Redux"), dict(uri="query:AudioFx#Echo", name="Echo")],
                      settings=[("Redux", "Dry/Wet", 40.0), ("Echo", "L Sync", "Off"), ("Echo", "L Time", 45.0),
                                ("Echo", "R Time", 45.0), ("Echo", "Feedback", 15.0), ("Echo", "Dry Wet", 15.0)]),
}
SPINE_AFTER = "AMEN-DMENT"
LOW_CUT_HZ = 120.0
FADE_S = 0.003


# ---------------------------------------------------------------- offline rendering
def _read(path):
    from reaper_features import read_wav
    return read_wav(path)


def _write(path, x, sr):
    y = np.clip(x, -1.0, 1.0)
    pcm = (y * 32767.0).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(pcm.shape[1])
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())


def _fade(x, sr):
    n = min(int(FADE_S * sr), len(x) // 4)
    if n > 0:
        ramp = np.linspace(0.0, 1.0, n)[:, None]
        x[:n] *= ramp
        x[-n:] *= ramp[::-1]
    return x


def grain_stretch(x, factor, sr, grain_s=0.04):
    """Stretch by `factor` with Hann-windowed grains laid down at half-grain hops and read at hop/factor,
    with no phase alignment - the smeared, metallic repeats of an old sampler's timestretch."""
    n = int(grain_s * sr)
    hop_out = n // 2
    hop_in = hop_out / factor
    win = np.hanning(n)[:, None]
    out_len = int(len(x) * factor) + n
    out = np.zeros((out_len, x.shape[1]))
    norm = np.zeros((out_len, 1))
    k = 0
    while True:
        src = int(k * hop_in)
        dst = k * hop_out
        if src + n > len(x) or dst + n > out_len:
            break
        out[dst:dst + n] += x[src:src + n] * win
        norm[dst:dst + n] += win
        k += 1
    out = out / np.maximum(norm, 1e-3)
    return out[:int(len(x) * factor)]


def variant_file(main, kind, slice_idx, amount):
    tag = {"AMEN-DMENT": "amen", "COLD-CUTS": "coldsweat", "CHOPPER": "apache"}[main]
    suffix = "rev" if kind == "reverse" else f"x{amount:g}".replace(".", "p")
    return f"{tag}_s{slice_idx:02d}_{suffix}.wav"


def render():
    os.makedirs(VARIANT_DIR, exist_ok=True)
    made = 0
    for main, (slices_from, _, _) in MAIN_BREAKS.items():
        _, disk_dir, fname, _, _ = BREAK_FILES[slices_from]
        x, sr = _read(os.path.join(USER_LIB, disk_dir, fname))
        frames = BREAKS[slices_from][0]
        for note, (kind, s, amount) in VARIANTS[main].items():
            if kind not in ("reverse", "stretch"):
                continue
            out = os.path.join(VARIANT_DIR, variant_file(main, kind, s, amount))
            if os.path.exists(out):
                continue
            a, z = frames[s], (frames[s + 1] if s + 1 < len(frames) else len(x))
            seg = x[a:z].astype(np.float64)
            seg = seg[::-1].copy() if kind == "reverse" else grain_stretch(seg, amount, sr)
            _write(out, _fade(seg, sr), sr)
            made += 1
            print(f"  rendered {os.path.basename(out)} ({len(seg) / sr * 1000:.0f} ms)")
    print(f"  {made} variant file(s) rendered into {VARIANT_DIR}")


# ---------------------------------------------------------------- Live
def names(ch):
    n = ch.get_session_info().result(timeout=5)["track_count"]
    out = {}
    for i in range(n):
        out.setdefault(ch.get_track_info(i).result(timeout=5)["name"], i)
    return out


def meter_test(ch, track, notes):
    """Write a 1-bar test clip, fire it and read the track meter. Stops playback: only for new tracks."""
    from jungle_build import write_clip
    t = names(ch)[track]
    slot = ch.get_scene_count().result(timeout=5)["count"] - 1
    write_clip(ch, t, slot, "test", notes, 4.0)
    ch.set_launch_quantization(0).result(timeout=3)
    ch.stop_all_clips().result(timeout=3)
    time.sleep(0.3)
    ch.fire_clip(t, slot).result(timeout=3)
    time.sleep(0.3)
    peak, end = 0.0, time.monotonic() + 2.0
    while time.monotonic() < end:
        for m in ch.get_all_meters().result(timeout=2)["meters"]:
            if m["name"] == track:
                peak = max(peak, m.get("left", 0.0), m.get("right", 0.0))
        time.sleep(0.04)
    ch.stop_all_clips().result(timeout=3)
    ch.clear_clip(t, slot).result(timeout=5)
    ch.set_launch_quantization(1).result(timeout=3)
    return peak


def ensure_main_breaks(ch):
    from jungle_space import chain, find_device, set_number
    scenes = ch.get_scene_count().result(timeout=5)["count"]
    for main, (_, copy_of, strip) in MAIN_BREAKS.items():
        if copy_of is None or main in names(ch):
            continue
        src = names(ch)[copy_of]
        ch.duplicate_track(src).result(timeout=90)
        t = src + 1
        ch.set_track_name(t, main).result(timeout=3)
        for s in range(scenes):
            try:
                ch.clear_clip(t, s).result(timeout=5)
            except Exception:
                pass
        for dev in strip:
            d = find_device(ch, t, dev)
            if d is not None:
                ch.delete_device(t, d).result(timeout=10)
        d = find_device(ch, t, "EQ Eight")
        shown = set_number(ch, t, d, "1 Frequency A", LOW_CUT_HZ) if d is not None else "no EQ"
        print(f"  {main}: copied from {copy_of}, low cut {shown}, chain {' > '.join(x['name'] for x in chain(ch, t))}")
        peak = meter_test(ch, main, [(36, 0.0, 0.5, 120), (38, 1.0, 0.5, 120)])
        print(f"  {main}: test hits meter {peak:.3f}")
        if peak <= 0.01:
            raise SystemExit(f"{main} is silent")


def ensure_variant_pads(ch):
    from jungle_drumkits import _load_pad, _pad_device
    from jungle_build import fade_raw, SLICE_FADE_IN_MS, SLICE_FADE_OUT_MS
    for main, (slices_from, _, _) in MAIN_BREAKS.items():
        t = names(ch)[main]
        folder, _, fname, transpose, detune = BREAK_FILES[slices_from]
        frames = BREAKS[slices_from][0]
        ref = _pad_device(ch, t, 36)
        ref_params = {p["name"]: p["value"] for p in ref["parameters"]}
        total = int(ref["properties"]["sample.length"])
        for note, (kind, s, amount) in VARIANTS[main].items():
            existing = _pad_device(ch, t, note)
            if existing is not None:
                continue
            a, z = frames[s], (frames[s + 1] if s + 1 < len(frames) else total) - 1
            if kind in ("pitch", "offset"):
                _load_pad(ch, t, note, folder, fname)
            else:
                _load_pad(ch, t, note, VARIANT_BROWSER, variant_file(main, kind, s, amount))

            def prop(key, value):
                return ch.set_drum_pad_chain_device_property(t, 0, note, key, value, 0).result(timeout=10)

            def param(key, value):
                return ch.set_drum_pad_chain_device_param(t, 0, note, float(value), param_name=key,
                                                          chain_device_index=0).result(timeout=10)

            prop("playback_mode", 1)
            try:
                prop("sample.warping", False)
            except Exception:
                pass
            if kind in ("pitch", "offset"):
                start = a + int((z - a) * amount) if kind == "offset" else a
                prop("sample.start_marker", int(start))
                prop("sample.end_marker", int(z))
            semis = transpose + (amount if kind == "pitch" else 0)
            for key, value in (("Trigger Mode", 1), ("Fade In", fade_raw(SLICE_FADE_IN_MS)),
                               ("Fade Out", fade_raw(SLICE_FADE_OUT_MS)), ("Transpose", semis),
                               ("Detune", detune), ("Volume", ref_params["Volume"]),
                               ("Vol < Vel", ref_params["Vol < Vel"]), ("Snap", 0)):
                param(key, value)
            print(f"  {main} pad {note}: {kind} of slice {s} ({amount:g})")


def ensure_spines(ch):
    from jungle_space import load_fx, find_device, set_number, set_string
    spine_map = {}
    try:
        with open(MAP_PATH) as fh:
            previously_mapped = set(json.load(fh).get("spines", {}))
    except FileNotFoundError:
        previously_mapped = set()
    for spine, spec in SPINES.items():
        idx = names(ch)
        new = spine not in idx
        if new:
            at = idx[SPINE_AFTER] + 1
            ch.create_midi_track(at).result(timeout=10)
            ch.set_track_name(at, spine).result(timeout=3)
            path, item = spec["kit"]
            ch.load_item_at_path(at, path, item).result(timeout=60)
            for _ in range(80):
                if ch.get_track_info(at).result(timeout=5)["device_count"] > 0:
                    break
                time.sleep(0.25)
            ch.set_track_volume(at, 0.6).result(timeout=3)
        t = names(ch)[spine]
        for fx in spec["fx"]:
            load_fx(ch, t, fx)
        for dev, pname, target in spec["settings"]:
            d = find_device(ch, t, dev)
            try:
                (set_string if isinstance(target, str) else set_number)(ch, t, d, pname, target)
            except Exception as e:
                print(f"  [skip] {spine} {dev} {pname}: {e!r}")
        try:
            pads = ch.get_drum_pads(t, 0).result(timeout=10)
            pads = pads.get("pads", pads) if isinstance(pads, dict) else pads
            named = [(int(p["note"]), str(p.get("name", ""))) for p in pads if p.get("name")]
        except Exception:
            # factory kits are often an Instrument Rack around the Drum Rack, and the bridge only lists pads
            # on a bare Drum Rack: fall back on Ableton's kit layout (kick C1, snare D1), confirmed by ear
            named = []
            print(f"  {spine}: pad names not reachable (kit wrapped in an Instrument Rack); using kick C1, snare D1")
        kick = next((n for n, nm in named if "kick" in nm.lower() or nm.lower().startswith("bd")), 36)
        snare = next((n for n, nm in named if "snare" in nm.lower() or nm.lower().startswith("sd")), 38)
        spine_map[spine] = {"kick": kick, "snare": snare}
        print(f"  {spine}: kick pad {kick} ({dict(named).get(kick, 'by convention')}), "
              f"snare pad {snare} ({dict(named).get(snare, 'by convention')})")
        if new or spine not in previously_mapped:     # metered once: when created, or never recorded
            peak = meter_test(ch, spine, [(kick, 0.0, 0.5, 120), (snare, 1.0, 0.5, 120)])
            print(f"  {spine}: test hits meter {peak:.3f}")
            if peak <= 0.01:
                raise SystemExit(f"{spine} is silent")
    return spine_map


def main(argv=None):
    ap = argparse.ArgumentParser(description="Build the jungle drum kits: main breaks, variant pads, spines.")
    ap.add_argument("--render", action="store_true", help="only render the reversed/stretched files")
    args = ap.parse_args(argv)
    render()
    if args.render:
        return
    from thelmic.live_channel import LiveChannel
    ch = LiveChannel(lower_priority=False)
    ch.start()
    try:
        print("== main breaks")
        ensure_main_breaks(ch)
        print("== variant pads")
        ensure_variant_pads(ch)
        print("== spines")
        spine_map = ensure_spines(ch)
        with open(MAP_PATH, "w") as fh:
            json.dump({"variants": {m: {str(k): list(v) for k, v in VARIANTS[m].items()} for m in VARIANTS},
                       "spines": spine_map}, fh, indent=1)
        print(f"== wrote {MAP_PATH}")
    finally:
        ch.stop()


if __name__ == "__main__":
    main()
