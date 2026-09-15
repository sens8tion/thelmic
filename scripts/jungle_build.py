"""JUNGLE BUILD - infrastructure half of the 2026-09-15 jungle track (170 BPM, F minor).

Builds into the CURRENT Live set through the LOM bridge, idempotently (find-or-create
by exact track name; a track that already has devices is left alone unless --rebuild):

  AMEN-DMENT  Drum Rack(amen, 26 slice pads)   -> Drum Buss -> Redux -> EQ8 -> Glue
  SWEAT-SHOP  Drum Rack(Cold Sweat, 21 pads)   -> Drum Buss -> EQ8
  TOPSOIL     Drum Rack(Apache, 28 pads)       -> EQ8 -> Redux
  BOOT-LEG    Rollin Breaks Kit (Skitter and Step, kick on C1) -> EQ8 -> Utility(mono)
  F-HOLE      Basic Sub Sine (Core Library)    -> Utility(mono) -> EQ8 (flat: level trim) -> Compressor(SC from BOOT-LEG)
  RASP-BERRY  Reese Classic (Core Library)     -> EQ8 -> Utility(bass mono) -> Compressor(SC from BOOT-LEG)
  BELL-END    Bells FM Simple (Operator preset) -> Echo -> Reverb -> EQ8

The synth lanes load factory Suite presets: hand-set synth patches clicked and cut notes short.

Break tracks: slice N plays on MIDI note SLICE_ROOT + N (36 + N). The sliced Simpler is only the
starting point: jungle_drumkits then moves every slice onto its own Drum Rack pad, so hits ring out
per pad (Gate mode: a short note truncates a hit, for roll steps). jungle_sidechain then keys a
Compressor on F-HOLE and RASP-BERRY from the kick, set in real units from Live's displayed values.

Composition is NOT here. After build(), main() runs scripts/jungle_compose.py:compose(ch, tracks)
if that file exists, where tracks = {track name: track index}. A composer can import
`write_clip`, `SLICE_ROOT`, `F1` etc. from this module (scripts/ is on sys.path).

Gain staging (the user's policy): every stage's INPUT stays below clip. Synths come in
conservative and cool into any saturation; no stacked hot synth + saturator + makeup.

    python scripts/jungle_build.py --dry-run       # print the plan; never imports/connects LiveChannel
    python scripts/jungle_build.py                 # build, then compose if a composer exists
    python scripts/jungle_build.py --rebuild       # delete our named tracks and recreate them
    python scripts/jungle_build.py --confident-eq  # avoid the guessed EQ8 low-cut filter types
"""
from __future__ import annotations
import argparse
import math
import os
import re
import sys
import time

os.environ.setdefault("LIVE_CHANNEL_ENABLED", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(SCRIPTS_DIR))          # repo root -> `import thelmic`
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)                        # -> `import jungle_compose`

# NOTE: nothing from `thelmic` is imported at module level, so --dry-run never loads the
# bridge or LiveChannel. Live-touching code fetches the helpers through _helpers().


class Frac(float):
    """A 0..1 value meaning 'this fraction of the param's REAL range' (see gabber_native_kit).
    Plain numbers are absolute values, range-checked and clamped by set_param."""
    __slots__ = ()

    def __repr__(self):
        return f"Frac({float(self):g})"


# ----------------------------------------------------------------------
# Global setup
# ----------------------------------------------------------------------
TEMPO = 170.0
MIN_SCENES = 12
LAUNCH_QUANT_BARS = 1

SLICE_ROOT = 36                 # slice N of a break plays on MIDI note SLICE_ROOT + N
E1, F1, G1 = 28, 29, 31         # F minor; the sub lives on F1 (43.65 Hz), range E1..G1

# Probe / default tracks to purge: "1-TSP_IHD_160_...", "2-MIDI", "3-Audio", "4-Audio".
JUNK_TRACK_RE = re.compile(r"^\d+-(MIDI|Audio|TSP_.*)$")
PLACEHOLDER_NAME = "0-MIDI"     # matches JUNK_TRACK_RE on purpose: the next purge removes it

# Simpler slicing (all VERIFIED)
SIMPLER_CLASS = "OriginalSimpler"
PLAYBACK_SLICING = 2            # device.playback_mode
SLICING_STYLE_MANUAL = 3        # sample.slicing_style
SLICING_PLAYBACK_POLY = 1       # device.slicing_playback_mode: a voice per slice (mono choked every tail)
SLICER_VOICES = 16              # device.voices: room for a busy chop's overlapping tails

# Browser URIs
OPERATOR = "query:Synths#Operator"
ANALOG = "query:Synths#Analog"
DRUM_BUSS = "query:AudioFx#Drum%20Buss"
REDUX = "query:AudioFx#Redux"
EQ8 = "query:AudioFx#EQ%20Eight"
GLUE = "query:AudioFx#Glue%20Compressor"
UTILITY = "query:AudioFx#Utility"
SATURATOR = "query:AudioFx#Saturator"
ECHO = "query:AudioFx#Echo"
REVERB = "query:AudioFx#Reverb"
COMPRESSOR = "query:AudioFx#Compressor"

SPLICE = "user_library/Samples/Splice"
SEGURA_BREAKS = "user_library/Samples/Imported/segura_breaks"

# Manual slice points (sample frames at 44.1 kHz) and what each slice contains live in
# jungle_slices.py, the single source shared with the composer.
from jungle_slices import AMEN_FRAMES, CS174, AP174  # noqa: E402


# ----------------------------------------------------------------------
# Instruments (params set by name; missing names log [skip])
# ----------------------------------------------------------------------
def fade_raw(ms: float) -> float:
    """Simpler Fade In/Out raw value for a time in ms. The knob maps ms = 2000 * raw**3
    (read off Live's display at two points per knob; the bridge only exposes raw 0..1)."""
    return (ms / 2000.0) ** (1.0 / 3.0)


# In slicing mode, Fade In/Out apply per slice (Fade Out also on a gated note release). The
# defaults (0.1 ms in, 0.25 ms out) are too short to hide a cut; 1 ms in mostly fades the quiet
# gap before the attack, 3 ms out covers the tail's last stretch before the next hit.
SLICE_FADE_IN_MS = 1.0
SLICE_FADE_OUT_MS = 3.0


def op_time_raw(ms: float) -> float:
    """Operator envelope Decay/Release raw value for a time in ms. The knob maps ms = e^(11 * raw)
    (60 s at 1.0; fits five display readings exactly). Attack is on a different curve. Raw values
    that look sensible as linear time are tiny here: 0.30 is 27 ms, 0.12 is 3.7 ms."""
    return math.log(ms) / 11.0


def analog_time_raw(ms: float) -> float:
    """Analog envelope time raw value for a time in ms: ms ~ 5 * e^(8.05 * raw) (fits attack 0.02 = 6 ms,
    release 0.20 = 25 ms, decay 0.60 = 626 ms, read off Live's display)."""
    return math.log(ms / 5.0) / 8.05


def simpler(transpose: float, volume_db: float, detune_cents: float = 0.0) -> dict:
    return {
        "Transpose": transpose,     # [-48..48] st
        "Detune": detune_cents,     # [-50..50] cents
        "Trigger Mode": 1,          # [0..1] 1 = gate: note length can truncate a slice
        "Volume": volume_db,        # [-36..36] dB
        "Ve Attack": 0.0,           # [0..1] hits land on the transient
        "Ve Release": 0.10,         # [0..1] short tail after a gated cut
        "Fade In": fade_raw(SLICE_FADE_IN_MS),
        "Fade Out": fade_raw(SLICE_FADE_OUT_MS),
    }


# Amen at 160 -> 170 BPM is +1.05 st by ratio, so Transpose +1 repitches it up to tempo.
AMEN_SIMPLER = simpler(transpose=1, volume_db=-6.0)
# Cold Sweat / Apache at 174 -> 170: -40 cents plays them at exactly 170 (174 * 2**(-40/1200)).
SWEAT_SIMPLER = simpler(transpose=0, volume_db=-9.0, detune_cents=-40.0)
TOPSOIL_SIMPLER = simpler(transpose=0, volume_db=-12.0, detune_cents=-40.0)

# Factory Suite presets for the synth lanes: (browser path, item name).
KICK_KIT = ("packs/Skitter and Step/Drums", "Rollin Breaks Kit.adg")                 # its kick is pad C1 (36)
SUB_PRESET = ("packs/Core Library/Racks/Instrument Racks/Bass", "Basic Sub Sine.adg")
REESE_PRESET = ("packs/Core Library/Racks/Instrument Racks/Bass", "Reese Classic.adg")
BELL_PRESET = ("packs/Core Library/Devices/Instruments/Operator/Mallets", "Bells FM Simple.adv")


# ----------------------------------------------------------------------
# EQ band specs (bands assigned 1, 2, 3... in list order)
# ----------------------------------------------------------------------
def low_cut(hz: float, steep: bool = False):
    return ("low_cut", float(hz), bool(steep))


def bell(hz: float, gain: float, q: float = 0.5):
    return ("bell", float(hz), float(gain), float(q))


def high_shelf(hz: float, gain: float):
    return ("high_shelf", float(hz), float(gain))


# ----------------------------------------------------------------------
# Roles. fx entry = (uri, expected class substring, {param: value} | [eq band specs])
# ----------------------------------------------------------------------
ROLES = [
    dict(name="AMEN-DMENT", kind="simpler", sample=(SPLICE, "TSP_IHD_160_drum_break_amen_chop_4bar.wav"),
         frames=AMEN_FRAMES, file_bpm=160.0, instrument=AMEN_SIMPLER,
         fx=[(DRUM_BUSS, "DrumBuss", {"Drive": 0.25, "Crunch": 0.15, "Transients": 0.20,
                                      "Boom Amt": 0.0, "Output": 0.85}),
             # parallel grit: Redux mostly dry
             (REDUX, "Redux2", {"Bit Depth": 12, "Sample Rate": 0.80, "Dry/Wet": 0.35}),
             (EQ8, "Eq8", [low_cut(120), bell(300, -3.0), high_shelf(10000, -2.0)]),
             # Ratio/Attack/Release are enum indices. Believed: Ratio 1 = 4:1, Attack 5 = 10 ms
             # (lets the transients through), Release 1 = 0.2 s.
             (GLUE, "GlueCompressor", {"Threshold": -10.0, "Ratio": 1, "Attack": 5, "Release": 1,
                                       "Output": 2.0, "Dry/Wet": 1.0})],
         volume=0.80, sends={0: 0.10, 1: 0.0}),

    dict(name="SWEAT-SHOP", kind="simpler",
         sample=(SEGURA_BREAKS, "KCSB1_174_ColdSweatBreak_01_HighToneFortified_NoRide_Saturated_Wide.wav"),
         frames=CS174, file_bpm=174.0, instrument=SWEAT_SIMPLER,
         fx=[(DRUM_BUSS, "DrumBuss", {"Drive": 0.15, "Transients": 0.10, "Boom Amt": 0.0, "Output": 0.85}),
             (EQ8, "Eq8", [low_cut(150), bell(300, -3.0)])],
         volume=0.72, sends={0: 0.08}),

    dict(name="TOPSOIL", kind="simpler",
         sample=(SEGURA_BREAKS, "KAPB1_174_ApacheBreak_01_HighTone_Normal.wav"),
         frames=AP174, file_bpm=174.0, instrument=TOPSOIL_SIMPLER,
         fx=[(EQ8, "Eq8", [low_cut(400, steep=True)]),          # bongos and ride only
             (REDUX, "Redux2", {"Bit Depth": 10, "Dry/Wet": 0.30})],
         volume=0.65, sends={0: 0.15}),

    dict(name="BOOT-LEG", kind="preset", preset=KICK_KIT, klass="InstrumentGroupDevice",
         fx=[(EQ8, "Eq8", [low_cut(40, steep=True), bell(90, 2.0)]),
             (UTILITY, "StereoGain", {"Mono": 1})],
         volume=0.78),

    dict(name="F-HOLE", kind="preset", preset=SUB_PRESET, klass="InstrumentGroupDevice",
         fx=[(UTILITY, "StereoGain", {"Mono": 1}),             # keep the sub clean: mono only
             (EQ8, "Eq8", [])],                                # flat: the level-trim stage for jungle_levels
         volume=0.82),

    dict(name="RASP-BERRY", kind="preset", preset=REESE_PRESET, klass="InstrumentGroupDevice",
         # no Saturator: the factory rack is already driven, and stacking more is what the gain rule forbids
         fx=[(EQ8, "Eq8", [low_cut(120, steep=True), bell(300, -3.0)]),   # the sub owns the bottom
             (UTILITY, "StereoGain", {"Bass Mono": 1})],
         volume=0.62),                                 # sidechain: jungle_sidechain, after the tracks exist

    dict(name="BELL-END", kind="preset", preset=BELL_PRESET, klass="Operator",
         fx=[(ECHO, "Echo", {"Link": 1, "L Sync": 1, "L 16th": 3,       # 3 sixteenths = dotted 8th
                             "Feedback": 0.35,
                             "Filter On": 1,                            # HP/LP below only act when on
                             "HP Freq": 0.35, "LP Freq": 0.65, "Dry Wet": 0.25}),
             (REVERB, "Reverb", {"Decay Time": 0.60, "In Lo Cut On": 1, "Dry/Wet": 0.30}),
             (EQ8, "Eq8", [low_cut(350, steep=True)])],
         volume=0.55, sends={1: 0.0}),
]
ROLE_NAMES = tuple(r["name"] for r in ROLES)


def check_frames(name: str, frames) -> list[int]:
    """Slice points must be plain ints, start at 0 and strictly increase."""
    out = [int(f) for f in frames]
    if out != list(frames) or any(type(f) is not int for f in frames):
        raise ValueError(f"{name}: frames must be plain Python ints")
    if not out or out[0] != 0:
        raise ValueError(f"{name}: first slice must be at frame 0")
    if any(b <= a for a, b in zip(out, out[1:])):
        raise ValueError(f"{name}: frames must strictly increase")
    return out


# ----------------------------------------------------------------------
# Param / EQ writes
# ----------------------------------------------------------------------
def _helpers():
    import thelmic.bridge.helpers as h
    return h


def _set(ch, t, dev_idx, name, val):
    """Range-aware write: Frac -> fraction of real range, else absolute (checked)."""
    h = _helpers()
    if isinstance(val, Frac):
        h.set_param(ch, t, dev_idx, name, frac=float(val))
    else:
        h.set_param(ch, t, dev_idx, name, value=float(val))


def apply_params(ch, t, dev_idx, params: dict, label: str):
    for name, val in params.items():
        try:
            _set(ch, t, dev_idx, name, val)
        except Exception as e:
            print(f"    [skip] {label} '{name}': {e}")


def apply_eq(ch, t, dev_idx, bands, *, confident_eq: bool):
    h = _helpers()
    for band, spec in enumerate(bands, start=1):
        kind = spec[0]
        try:
            if kind == "bell":
                _, hz, gain, q = spec
                h.set_eq_band(ch, t, dev_idx, band, ftype=h.EQ8_BELL, hz=hz, gain=gain, q_norm=q)
                print(f"      band {band}: bell {gain:+g} dB @ {hz:g} Hz")
            elif kind == "high_shelf":
                _, hz, gain = spec
                h.set_eq_band(ch, t, dev_idx, band, ftype=h.EQ8_HIGH_SHELF, hz=hz, gain=gain)
                print(f"      band {band}: high shelf {gain:+g} dB @ {hz:g} Hz")
            elif kind == "low_cut":
                _, hz, steep = spec
                if not confident_eq:
                    # GUESS: eq.py marks the EQ8 low-cut type indices as unverified on Live 12
                    # (0 = 48 dB/oct, 1 = 12 dB/oct). BELL=3 and HIGH_SHELF=5 do fit Live's menu
                    # order (LC48, LC12, LoShelf, Bell, Notch, HiShelf, HC12, HC48), so these are
                    # probably right. Eyeball the band's filter icon; --confident-eq avoids them.
                    ftype = h.EQ8_HP_48_GUESS if steep else h.EQ8_HP_12_GUESS
                    h.set_eq_band(ch, t, dev_idx, band, ftype=ftype, hz=hz)
                    print(f"      band {band}: low cut {'48' if steep else '12'} dB/oct @ {hz:g} Hz (type guessed)")
                elif hz >= 80:
                    # confident types only: a wide, deep bell under the cut point
                    h.set_eq_band(ch, t, dev_idx, band, ftype=h.EQ8_BELL, hz=hz * 0.6,
                                  gain=-12.0, q_norm=0.15)
                    print(f"      band {band}: wide bell -12 dB @ {hz * 0.6:g} Hz (stands in for low cut {hz:g})")
                else:
                    print(f"      band {band}: skipped low cut @ {hz:g} Hz (no confident way to cut that low)")
            else:
                raise ValueError(f"unknown band kind {kind!r}")
        except Exception as e:
            print(f"    [skip] eq band {band} {spec}: {e}")


# ----------------------------------------------------------------------
# Tracks
# ----------------------------------------------------------------------
def _track_names(ch) -> list[str]:
    n = ch.get_session_info().result(timeout=5)["track_count"]
    return [ch.get_track_info(i).result(timeout=5)["name"] for i in range(n)]


def track_index_by_name(ch) -> dict[str, int]:
    """{track name: index} across the set. First occurrence wins; duplicates are reported."""
    out: dict[str, int] = {}
    for i, name in enumerate(_track_names(ch)):
        if name in out:
            print(f"  [warn] duplicate track name {name!r} at {out[name]} and {i}; using {out[name]}")
            continue
        out[name] = i
    return out


def purge_tracks(ch, *, ours_too: bool = False) -> int:
    """Delete junk tracks (JUNK_TRACK_RE), plus every track named like a role when ours_too.
    Highest index first, so earlier indices stay valid while deleting.

    Live refuses to delete a set's last track. If every track is doomed the lowest one
    survives, renamed to PLACEHOLDER_NAME if it was ours (so find-or-create won't reuse it);
    the purge that runs after our tracks exist removes it."""
    names = _track_names(ch)
    doomed = [i for i, nm in enumerate(names)
              if JUNK_TRACK_RE.match(nm) or (ours_too and nm in ROLE_NAMES)]
    if not doomed:
        return 0
    if len(doomed) == len(names):
        keep = doomed.pop(0)
        if names[keep] in ROLE_NAMES:
            ch.set_track_name(keep, PLACEHOLDER_NAME).result(timeout=3)
        print(f"  [keep] track {keep} {names[keep]!r} survives for now (a set can't be empty)")
    for i in sorted(doomed, reverse=True):
        ch.delete_track(i).result(timeout=10)
        print(f"  deleted track {i}: {names[i]}")
    return len(doomed)


def ensure_tracks(ch) -> list[str]:
    """Create any missing role track (MIDI), in ROLES order, appended at the end of the set."""
    have = track_index_by_name(ch)
    created = []
    for role in ROLES:
        if role["name"] in have:
            print(f"  found   track {have[role['name']]}: {role['name']}")
            continue
        ch.create_midi_track(-1).result(timeout=10)
        t = ch.get_session_info().result(timeout=5)["track_count"] - 1
        ch.set_track_name(t, role["name"]).result(timeout=3)
        created.append(role["name"])
        print(f"  created track {t}: {role['name']}")
    return created


def ensure_scenes(ch, n: int):
    have = ch.get_scene_count().result(timeout=5)["count"]
    for _ in range(max(0, n - have)):
        ch.create_scene(-1).result(timeout=5)
    return ch.get_scene_count().result(timeout=5)["count"]


# ----------------------------------------------------------------------
# Devices
# ----------------------------------------------------------------------
def _wait_for_device(ch, t, count_before: int, timeout_s: float = 6.0) -> dict:
    """Poll get_track_info until the device count grows (browser loads can lag the RPC)."""
    deadline = time.monotonic() + timeout_s
    while True:
        info = ch.get_track_info(t).result(timeout=5)
        if info["device_count"] > count_before or time.monotonic() > deadline:
            return info
        time.sleep(0.2)


def load_device_checked(ch, t, uri: str, klass: str) -> int:
    """Load a browser item onto the end of track t's chain; return its device index."""
    before = ch.get_track_info(t).result(timeout=5)["device_count"]
    ch.load_device(t, uri).result(timeout=20)
    info = _wait_for_device(ch, t, before)
    if info["device_count"] <= before:
        raise RuntimeError(f"{uri} did not appear on track {t}")
    dev_idx = info["device_count"] - 1
    got = info["devices"][dev_idx]["class_name"]
    if klass.lower() not in got.lower():
        print(f"    [warn] expected class ~{klass!r} from {uri}, got {got!r} @dev{dev_idx}")
    return dev_idx


def setup_simpler(ch, t, role) -> int:
    """Sample -> Simpler at device 0, manual slices at known frames, mono slice playback."""
    frames = check_frames(role["name"], role["frames"])
    path, item = role["sample"]
    before = ch.get_track_info(t).result(timeout=5)["device_count"]
    ch.load_item_at_path(t, path, item).result(timeout=30)
    info = _wait_for_device(ch, t, before)
    got = info["devices"][0]["class_name"] if info["devices"] else None
    if got != SIMPLER_CLASS:
        raise RuntimeError(f"{role['name']}: expected {SIMPLER_CLASS} at dev0 after loading {item}, got {got!r}")
    print(f"   + {SIMPLER_CLASS} @dev0 <- {item}")

    ch.set_device_property(t, 0, "playback_mode", PLAYBACK_SLICING).result(timeout=5)
    ch.set_sample_property(t, 0, "slicing_style", SLICING_STYLE_MANUAL).result(timeout=5)
    res = ch.set_sample_slices(t, 0, times=frames).result(timeout=20)
    if res.get("failed"):
        print(f"    [warn] {len(res['failed'])} slice insert(s) failed, first: {res['failed'][:3]}")
    ch.set_device_property(t, 0, "slicing_playback_mode", SLICING_PLAYBACK_POLY).result(timeout=5)
    ch.set_device_property(t, 0, "voices", SLICER_VOICES).result(timeout=5)
    ch.set_device_property(t, 0, "retrigger", True).result(timeout=5)

    si = ch.get_sample_info(t, 0).result(timeout=10)
    n = si.get("slice_count")
    if n != len(frames):        # explicit so `python -O` can't strip the check
        raise AssertionError(
            f"{role['name']}: slice_count {n} != {len(frames)} frames "
            f"(slices_error={si.get('slices_error')!r}). Slice N -> note {SLICE_ROOT}+N is "
            f"broken; fix, then re-run with --rebuild")
    print(f"     slices: {n} (notes {SLICE_ROOT}..{SLICE_ROOT + n - 1})")

    apply_params(ch, t, 0, role["instrument"], "simpler")
    return 0


def apply_mixer(ch, t, role, return_count: int):
    try:
        ch.set_track_volume(t, role["volume"]).result(timeout=3)
    except Exception as e:
        print(f"    [skip] volume: {e}")
    for send_idx, val in role.get("sends", {}).items():
        if send_idx >= return_count:
            print(f"    [skip] send {'AB'[send_idx]}: only {return_count} return track(s)")
            continue
        try:
            ch.set_send(t, send_idx, val).result(timeout=3)
        except Exception as e:
            print(f"    [skip] send {'AB'[send_idx]}: {e}")


def build_role(ch, t, role, tracks: dict, *, confident_eq: bool, return_count: int):
    info = ch.get_track_info(t).result(timeout=5)
    if info["device_count"]:
        classes = ", ".join(d["class_name"] for d in info["devices"])
        print(f"  [keep] already has {info['device_count']} device(s) ({classes}); --rebuild to reload")
    else:
        if role["kind"] == "simpler":
            setup_simpler(ch, t, role)
        elif role["kind"] == "preset":
            path, item = role["preset"]
            before = ch.get_track_info(t).result(timeout=5)["device_count"]
            ch.load_item_at_path(t, path, item).result(timeout=30)
            info = _wait_for_device(ch, t, before, timeout_s=15.0)
            got = info["devices"][0]["class_name"] if info["devices"] else None
            if got != role["klass"]:
                print(f"    [warn] expected {role['klass']} at dev0 after loading {item}, got {got!r}")
            print(f"   + {item} @dev0")
        else:
            raise ValueError(f"unknown role kind {role['kind']!r}")

        for uri, klass, params in role["fx"]:
            try:
                dev = load_device_checked(ch, t, uri, klass)
            except Exception as e:
                print(f"    [skip] fx {klass}: {e}")
                continue
            print(f"   + {klass} @dev{dev}")
            if isinstance(params, list):
                apply_eq(ch, t, dev, params, confident_eq=confident_eq)
            else:
                apply_params(ch, t, dev, params, f"fx {klass}")

        src_name = role.get("sidechain_from")
        if src_name:
            try:
                src = tracks[src_name]
                cmp_idx = _helpers().sidechain_pump(ch, t, src, COMPRESSOR, intensity="subtle")
                print(f"   + Compressor2 @dev{cmp_idx} sidechain <- {src_name} (track {src}), subtle")
            except Exception as e:
                print(f"    [skip] sidechain from {src_name}: {e}")

    apply_mixer(ch, t, role, return_count)


# ----------------------------------------------------------------------
# Build
# ----------------------------------------------------------------------
def print_table(ch, tracks: dict):
    print(f"\n{'trk':>3}  {'name':<11}  {'slices':>6}  devices")
    print(f"{'---':>3}  {'-' * 11}  {'-' * 6}  {'-' * 40}")
    for role in ROLES:
        t = tracks.get(role["name"])
        if t is None:
            print(f"{'?':>3}  {role['name']:<11}  {'-':>6}  (missing)")
            continue
        info = ch.get_track_info(t).result(timeout=5)
        classes = " > ".join(d["class_name"] for d in info["devices"]) or "(none)"
        slices = "-"
        if role["kind"] == "simpler" and info["device_count"]:
            try:
                slices = str(ch.get_sample_info(t, 0).result(timeout=10).get("slice_count"))
            except Exception:
                slices = "err"
        print(f"{t:>3}  {role['name']:<11}  {slices:>6}  {classes}")


def build(ch, *, rebuild: bool = False, confident_eq: bool = False) -> dict[str, int]:
    """Find-or-create every role track and its chain. Returns {track name: track index}."""
    print("ping:", ch.ping().result(timeout=3))
    ch.set_tempo(TEMPO).result(timeout=3)
    print(f"tempo -> {TEMPO:g}")

    print("\n== purge ==" + (" (junk + our tracks: --rebuild)" if rebuild else " (junk)"))
    purge_tracks(ch, ours_too=rebuild)

    print("\n== tracks ==")
    ensure_tracks(ch)
    purge_tracks(ch)            # clears any track kept back so the set never went empty

    # Deletions shift indices: always resolve by name from here on.
    tracks = {nm: i for nm, i in track_index_by_name(ch).items() if nm in ROLE_NAMES}
    missing = [nm for nm in ROLE_NAMES if nm not in tracks]
    if missing:
        raise RuntimeError(f"role tracks missing after creation: {missing}")
    return_count = int(ch.get_session_info().result(timeout=5).get("return_track_count", 0))

    for role in ROLES:
        t = tracks[role["name"]]
        print(f"\n== {role['name']} (track {t}) ==")
        build_role(ch, t, role, tracks, confident_eq=confident_eq, return_count=return_count)

    import jungle_drumkits
    import jungle_sidechain
    print()
    print("== drum kits: a pad per slice ==")
    for role in ROLES:
        if role["kind"] == "simpler":
            jungle_drumkits.convert(ch, tracks[role["name"]], role["name"])
    print()
    print("== sidechain: sub and reese keyed from the kick ==")
    jungle_sidechain.apply(ch, tracks)

    ch.set_launch_quantization(LAUNCH_QUANT_BARS).result(timeout=3)
    scenes = ensure_scenes(ch, MIN_SCENES)
    print(f"\nlaunch quantization -> {LAUNCH_QUANT_BARS} bar; scenes: {scenes}")

    print_table(ch, tracks)
    return tracks


# ----------------------------------------------------------------------
# Composition hook
# ----------------------------------------------------------------------
def write_clip(ch, track: int, slot: int, name: str, notes, length_beats: float):
    """(Re)write one session clip. notes = iterable of (pitch, start, dur, vel) quads."""
    ensure_scenes(ch, slot + 1)
    try:
        ch.create_clip(track, slot, float(length_beats)).result(timeout=8)
    except Exception as e:
        print(f"    [warn] create_clip(track {track}, slot {slot}): {e}")
    ch.set_clip_name(track, slot, name).result(timeout=3)
    ch.add_notes_to_clip(track, slot, _helpers().to_clip_notes(notes), replace=True).result(timeout=8)


def run_composer(ch, tracks: dict[str, int]):
    try:
        import jungle_compose
    except ImportError as e:
        if getattr(e, "name", None) == "jungle_compose":
            print("\nno composer yet")
        else:
            print(f"\n[fail] scripts/jungle_compose.py exists but an import inside it failed: {e}")
        return
    print("\n== compose: jungle_compose.compose(ch, tracks) ==")
    jungle_compose.compose(ch, tracks)


# ----------------------------------------------------------------------
# Dry run
# ----------------------------------------------------------------------
def _fmt(v) -> str:
    return repr(v) if isinstance(v, Frac) else f"{v:g}"


def _fmt_params(params: dict) -> str:
    return ", ".join(f"{k}={_fmt(v)}" for k, v in params.items())


def _fmt_band(spec) -> str:
    kind = spec[0]
    if kind == "bell":
        return f"bell {spec[2]:+g} dB @ {spec[1]:g} Hz (q {spec[3]:g})"
    if kind == "high_shelf":
        return f"high shelf {spec[2]:+g} dB @ {spec[1]:g} Hz"
    return f"low cut {'48' if spec[2] else '12'} dB/oct @ {spec[1]:g} Hz"


def dry_run(*, rebuild: bool, confident_eq: bool):
    print("DRY RUN: LiveChannel is not imported and nothing connects to Live.\n")
    print("steps:")
    print(f"  1. set_tempo({TEMPO:g}); delete tracks matching {JUNK_TRACK_RE.pattern}"
          + (f" and every track named {list(ROLE_NAMES)}" if rebuild else "") + ", highest index first")
    print("  2. find-or-create MIDI tracks by exact name; purge again; resolve indices by name;"
          " load chains only on device-less tracks")
    print(f"  3. set_launch_quantization({LAUNCH_QUANT_BARS}); ensure >= {MIN_SCENES} scenes")
    print("  4. print track/device/slice table; return {name: index}")
    print(f"  EQ low cuts: {'confident types only (bell stand-ins)' if confident_eq else 'guessed EQ8 low-cut types'}")

    for n, role in enumerate(ROLES, start=1):
        print(f"\n[{n}] {role['name']}")
        if role["kind"] == "simpler":
            frames = check_frames(role["name"], role["frames"])
            path, item = role["sample"]
            st = 12 * math.log2(TEMPO / role["file_bpm"])
            print(f"    Simpler <- {path}/{item}")
            print(f"      file {role['file_bpm']:g} BPM ({st:+.2f} st to {TEMPO:g}); {len(frames)} manual slices,"
                  f" notes {SLICE_ROOT}..{SLICE_ROOT + len(frames) - 1}, last slice @ frame {frames[-1]}")
            print(f"      playback_mode={PLAYBACK_SLICING} slicing_style={SLICING_STYLE_MANUAL}"
                  f" slicing_playback_mode={SLICING_PLAYBACK_POLY} voices={SLICER_VOICES}; assert slice_count == {len(frames)}")
        else:
            print(f"    {role['klass']} <- preset {'/'.join(role['preset'])}")
        if role.get("instrument"):
            print(f"      {_fmt_params(role['instrument'])}")
        for uri, klass, params in role["fx"]:
            print(f"    -> {klass} <- {uri}")
            if isinstance(params, list):
                for band, spec in enumerate(params, start=1):
                    print(f"      band {band}: {_fmt_band(spec)}")
            else:
                print(f"      {_fmt_params(params)}")
        if role.get("sidechain_from"):
            print(f"    -> sidechain_pump(source={role['sidechain_from']}, {COMPRESSOR}, intensity='subtle')")
        sends = ", ".join(f"{'AB'[i]}={v:g}" for i, v in role.get("sends", {}).items()) or "untouched"
        print(f"    mixer: volume {role['volume']:g}; sends {sends}")

    composer = os.path.join(SCRIPTS_DIR, "jungle_compose.py")
    print("\ncompose: " + (f"would call jungle_compose.compose(ch, tracks) from {composer}"
                           if os.path.exists(composer) else "no composer yet"))


def main(argv=None):
    ap = argparse.ArgumentParser(description="Jungle track infrastructure (tracks, instruments, FX).")
    ap.add_argument("--dry-run", action="store_true",
                    help="print the plan; never imports or connects LiveChannel")
    ap.add_argument("--rebuild", action="store_true",
                    help="delete our named tracks and recreate them from scratch")
    ap.add_argument("--confident-eq", action="store_true",
                    help="use only verified EQ8 filter types (bell stand-ins for low cuts)")
    args = ap.parse_args(argv)

    if args.dry_run:
        dry_run(rebuild=args.rebuild, confident_eq=args.confident_eq)
        return

    from thelmic.live_channel import LiveChannel
    ch = LiveChannel(lower_priority=False)
    ch.start()
    try:
        tracks = build(ch, rebuild=args.rebuild, confident_eq=args.confident_eq)
        run_composer(ch, tracks)
    finally:
        ch.stop()


if __name__ == "__main__":
    main()
