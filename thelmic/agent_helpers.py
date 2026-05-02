"""High-level helpers around LiveChannel.

Designed for LLM-driven agentic music sessions. Wraps the gotchas, name-by-string
lookups, multi-step Live API rituals, and reusable musical patterns we've earned
through hard sessions. Each function does one intent-named thing and handles the
plumbing internally.

Import as:
    from thelmic.agent_helpers import (
        health_check, find_track, arm_arrangement_record,
        hz_to_norm, set_eq_band,
        amen_4bar, gabber_4bar, anticipation_fill,
        fire_arrangement, sidechain_pump,
    )
"""
from __future__ import annotations
import math
import time
from typing import Iterable

# ----------------------------------------------------------------------
# DRUM NOTE CONSTANTS — GM mapping that holds for most kits
# ----------------------------------------------------------------------
KICK = 36
SNARE = 38
HAT_C = 42
HAT_O = 46
RIDE = 51
CRASH = 49
SIDESTICK = 37   # also "snap" on some kits — be careful
HAND_CLAP = 39
LOW_TOM = 41
HI_TOM = 50

# ----------------------------------------------------------------------
# EQ8 FILTER TYPES — only `BELL` (3) and `HIGH_SHELF` (5) are reliable.
# HP/LP types vary by Live version; probe before trusting these.
# ----------------------------------------------------------------------
EQ8_BELL = 3
EQ8_HIGH_SHELF = 5
EQ8_LOW_SHELF_GUESS = 2     # not verified — verify by listening
EQ8_HP_12_GUESS = 1         # may be HP12; if "no bass" check this
EQ8_HP_48_GUESS = 0
EQ8_LP_12_GUESS = 6
EQ8_LP_48_GUESS = 7

# Live's session-default new-project track count
LIVE_DEFAULT_TRACK_COUNT = 4


# ======================================================================
# Health / discovery
# ======================================================================

def health_check(ch, expected_track_names: list[str] | None = None,
                  min_tracks: int = 6) -> tuple[bool, str | dict]:
    """Probe the session — fast-fail when Live is fresh / wrong project / not running.

    Returns (ok, detail). On success detail is {name: index} for found tracks.
    On failure detail is a one-line reason string.
    """
    try:
        ch.ping().result(timeout=3)
    except Exception as e:
        return False, f"Live not responding (port 9878): {e}"
    sess = ch.get_session_info().result(timeout=5)
    n = sess["track_count"]
    if n < min_tracks:
        return False, (f"only {n} tracks — looks like a fresh project (default 2 MIDI + 2 Audio)."
                       f" Open the saved set first.")
    if expected_track_names:
        found = {}
        missing = []
        for name in expected_track_names:
            idx = find_track(ch, name)
            if idx is None:
                missing.append(name)
            else:
                found[name] = idx
        if missing:
            return False, f"missing expected tracks: {missing}"
        return True, found
    # No expected list: just return all tracks by name
    out = {}
    for i in range(n):
        info = ch.get_track_info(i).result(timeout=5)
        out[info["name"]] = i
    return True, out


def find_track(ch, name_match: str) -> int | None:
    """Case-insensitive substring match on track names. Returns first match index."""
    sess = ch.get_session_info().result(timeout=5)
    needle = name_match.lower()
    for i in range(sess["track_count"]):
        info = ch.get_track_info(i).result(timeout=5)
        if needle in info["name"].lower():
            return i
    return None


def find_device(ch, track_index: int, class_name_match: str) -> int | None:
    """Find a device on a track by class_name (e.g. 'Eq8', 'Compressor2', 'Saturator')."""
    info = ch.get_track_info(track_index).result(timeout=5)
    needle = class_name_match.lower()
    for i, d in enumerate(info["devices"]):
        if needle in d["class_name"].lower():
            return i
    return None


def ensure_device(ch, track_index: int, class_name_match: str, browser_uri: str) -> int:
    """Return existing device index for class, or load it from browser_uri and return new idx."""
    idx = find_device(ch, track_index, class_name_match)
    if idx is not None:
        return idx
    ch.load_device(track_index, browser_uri).result(timeout=15)
    info = ch.get_track_info(track_index).result(timeout=5)
    return info["device_count"] - 1


# ======================================================================
# Recording — session→arrangement
# ======================================================================

def arm_arrangement_record(ch, launch_quant_bars: float = 1.0,
                            metronome: bool = False) -> None:
    """Multi-step ritual to arm a clean session-to-arrangement record:
       transport record + session record + follow arrangement + tight launch quant.
       After this, fire scenes during start_playback() and they print to arrangement.
    """
    ch.set_song_time(0).result(timeout=5)
    ch.stop_all_clips().result(timeout=5)
    ch.back_to_arrangement().result(timeout=5)        # follow arrangement playhead
    ch.set_record_mode(True).result(timeout=5)        # transport record (red REC)
    ch.set_session_record(True).result(timeout=5)     # session-to-arrangement capture
    ch.set_metronome(metronome).result(timeout=5)
    ch.set_launch_quantization(launch_quant_bars).result(timeout=5)


def disarm_arrangement_record(ch, restore_quant_bars: float = 8.0) -> None:
    """Stop transport, disarm record, restore quant."""
    ch.stop_playback().result(timeout=5)
    ch.set_session_record(False).result(timeout=5)
    ch.set_record_mode(False).result(timeout=5)
    ch.set_launch_quantization(restore_quant_bars).result(timeout=5)


def fire_arrangement(ch, sequence: list[tuple[int, int]], bpm: float,
                      log: bool = True) -> None:
    """Play through a (slot, bars) sequence with arrangement-record on.

    Caller must have already invoked arm_arrangement_record.
    Each slot fires at its bar boundary; the duration is held via real sleep.
    """
    bar_seconds = 60.0 / bpm * 4
    if log:
        total = sum(b for _, b in sequence)
        print(f"firing {len(sequence)} scenes — {total} bars @ {bpm} bpm = {total*bar_seconds:.1f}s")
    ch.fire_scene(sequence[0][0]).result(timeout=5)
    time.sleep(0.1)
    ch.start_playback().result(timeout=5)
    elapsed_bars = 0
    for i, (slot, bars) in enumerate(sequence):
        if i == 0:
            time.sleep(bars * bar_seconds)
            elapsed_bars += bars
            continue
        ch.fire_scene(slot).result(timeout=5)
        if log:
            print(f"  bar {elapsed_bars:>3d}: fired slot {slot} (hold {bars})")
        time.sleep(bars * bar_seconds)
        elapsed_bars += bars
    time.sleep(0.5)


# ======================================================================
# EQ helpers — abstract over normalized frequency + filter type quirks
# ======================================================================

def hz_to_norm(hz: float, low_hz: float = 30.0, high_hz: float = 22000.0) -> float:
    """Convert Hz to EQ8's normalized 0..1 frequency parameter (log mapping)."""
    hz = max(low_hz, min(high_hz, hz))
    return math.log(hz / low_hz) / math.log(high_hz / low_hz)


def set_eq_band(ch, track_index: int, eq_device_index: int, band: int, *,
                ftype: int, hz: float, gain: float = 0.0, q_norm: float = 0.5,
                on: bool = True) -> None:
    """Set one EQ8 band — wraps the param-name lookup + Hz→normalized conversion.

    Use ftype=EQ8_BELL (3) and EQ8_HIGH_SHELF (5) confidently. Other types are
    fragile and may behave differently across Live versions.
    """
    di = ch.get_device_info(track_index, eq_device_index).result(timeout=5)
    idx = {p["name"]: p["index"] for p in di["parameters"]}
    ch.set_device_param(track_index, eq_device_index, idx[f"{band} Filter On A"],
                         1 if on else 0).result(timeout=3)
    if not on:
        return
    ch.set_device_param(track_index, eq_device_index, idx[f"{band} Filter Type A"],
                         ftype).result(timeout=3)
    ch.set_device_param(track_index, eq_device_index, idx[f"{band} Frequency A"],
                         hz_to_norm(hz)).result(timeout=3)
    ch.set_device_param(track_index, eq_device_index, idx[f"{band} Gain A"],
                         gain).result(timeout=3)
    ch.set_device_param(track_index, eq_device_index, idx[f"{band} Resonance A"],
                         q_norm).result(timeout=3)


def disable_all_eq_bands(ch, track_index: int, eq_device_index: int) -> None:
    di = ch.get_device_info(track_index, eq_device_index).result(timeout=5)
    idx = {p["name"]: p["index"] for p in di["parameters"]}
    for b in range(1, 9):
        ch.set_device_param(track_index, eq_device_index, idx[f"{b} Filter On A"],
                             0).result(timeout=3)


# ======================================================================
# Param value helpers — handle normalized vs raw
# ======================================================================

def safe_set_param(ch, track_index: int, device_index: int,
                    param_name: str, value: float) -> dict:
    """Set a param and clamp to its actual range — many Live params are normalized
    0..1 even when their UI shows dB or Hz. set_device_param already clamps but
    this helper logs the clamp for debugging.
    """
    di = ch.get_device_info(track_index, device_index).result(timeout=5)
    p = next((p for p in di["parameters"] if p["name"] == param_name), None)
    if p is None:
        raise ValueError(f"param '{param_name}' not on device")
    target = max(p["min"], min(p["max"], value))
    if abs(target - value) > 1e-6:
        print(f"  [warn] {param_name}: requested {value} clamped to {target} (range {p['min']}..{p['max']})")
    return ch.set_device_param(track_index, device_index, p["index"], target).result(timeout=3)


# ======================================================================
# Sidechain — the multi-step routing dance
# ======================================================================

def sidechain_pump(ch, target_track: int, source_track: int,
                    compressor_uri: str,
                    intensity: str = "medium") -> int:
    """Apply sidechain pump on target_track keyed from source_track.

    intensity: 'subtle' | 'medium' | 'heavy'. Adds Compressor if missing.
    Returns the compressor device index.
    """
    cmp_idx = find_device(ch, target_track, "Compressor2")
    if cmp_idx is None:
        ch.load_device(target_track, compressor_uri).result(timeout=15)
        cmp_idx = find_device(ch, target_track, "Compressor2")
    di = ch.get_device_info(target_track, cmp_idx).result(timeout=5)
    idx = {p["name"]: p["index"] for p in di["parameters"]}
    settings = {
        "subtle": dict(threshold=0.55, ratio=0.45, attack=0.06, release=0.30, sc_gain=0.50),
        "medium": dict(threshold=0.45, ratio=0.65, attack=0.04, release=0.22, sc_gain=0.55),
        "heavy":  dict(threshold=0.35, ratio=0.85, attack=0.03, release=0.18, sc_gain=0.65),
    }[intensity]
    ch.set_device_param(target_track, cmp_idx, idx["S/C On"], 1).result(timeout=3)
    ch.set_device_param(target_track, cmp_idx, idx["S/C Listen"], 0).result(timeout=3)
    ch.set_device_param(target_track, cmp_idx, idx["Threshold"], settings["threshold"]).result(timeout=3)
    ch.set_device_param(target_track, cmp_idx, idx["Ratio"], settings["ratio"]).result(timeout=3)
    ch.set_device_param(target_track, cmp_idx, idx["Attack"], settings["attack"]).result(timeout=3)
    ch.set_device_param(target_track, cmp_idx, idx["Release"], settings["release"]).result(timeout=3)
    ch.set_device_param(target_track, cmp_idx, idx["S/C Gain"], settings["sc_gain"]).result(timeout=3)
    if "LookAhead" in idx:
        ch.set_device_param(target_track, cmp_idx, idx["LookAhead"], 2).result(timeout=3)  # 10ms
    ch.set_device_sidechain_source(target_track, cmp_idx, source_track).result(timeout=10)
    return cmp_idx


# ======================================================================
# Drum pattern generators — return list of (pitch, start_time, duration, velocity)
# ======================================================================

def amen_4bar(offset: float = 0.0) -> list[tuple[int, float, float, int]]:
    """Classic Amen-style breakbeat. 4 bars × 4 beats = 16 beats."""
    base = [
        (KICK, 0.0, 0.4, 110), (SNARE, 1.0, 0.35, 100),
        (KICK, 1.5, 0.4, 95),  (SNARE, 3.0, 0.35, 105),
        (KICK, 4.0, 0.4, 110), (SNARE, 5.0, 0.35, 100),
        (SNARE, 5.5, 0.2, 75), (SNARE, 6.5, 0.3, 95),
        (KICK, 7.5, 0.35, 90),
        (KICK, 8.0, 0.4, 110), (SNARE, 9.0, 0.35, 100),
        (KICK, 10.5, 0.35, 95),(SNARE, 11.0, 0.35, 105),
        (KICK, 12.0, 0.4, 110),(SNARE, 13.0, 0.3, 95),
        (SNARE, 13.5, 0.2, 75),(SNARE, 14.0, 0.35, 100),
        (KICK, 14.5, 0.35, 90),(SNARE, 15.0, 0.3, 95),
        (SNARE, 15.5, 0.25, 80),
    ]
    notes = [(p, t + offset, dur, vel) for (p, t, dur, vel) in base]
    # 16th-note hats
    for i in range(64):
        t = i * 0.25 + offset
        slot = i % 4
        notes.append((HAT_C, t, 0.18, {0: 92, 1: 65, 2: 78, 3: 65}[slot]))
    return notes


def gabber_4bar(offset: float = 0.0, double: bool = False) -> list[tuple[int, float, float, int]]:
    """Gabber 4-on-the-floor. double=True gives 8th-note kicks (double pace)."""
    notes = []
    rate_beats = 0.5 if double else 1.0
    n_kicks = int(16 / rate_beats)
    for i in range(n_kicks):
        t = offset + i * rate_beats
        vel = 122 if (i * rate_beats) % 1 == 0 else 110
        notes.append((KICK, t, 0.18 if double else 0.4, vel))
    # Snares on backbeats (1 and 3 of each bar)
    for bar in range(4):
        for sb in (1.0, 3.0):
            notes.append((SNARE, offset + bar * 4.0 + sb, 0.35, 110))
    # 16th hats locked to kicks
    for i in range(64):
        t = offset + i * 0.25
        slot = i % 4
        notes.append((HAT_C, t, 0.14, {0: 88, 1: 60, 2: 75, 3: 60}[slot]))
    return notes


def breakcore_4bar(offset: float = 0.0) -> list[tuple[int, float, float, int]]:
    """16th-note kicks throughout (4x density vs gabber). Industrial chaos."""
    notes = []
    for i in range(64):  # 16 beats × 4 sixteenths
        t = offset + i * 0.25
        slot = i % 4
        vel = {0: 124, 1: 110, 2: 117, 3: 110}[slot]
        notes.append((KICK, t, 0.10, vel))
    for bar in range(4):
        for sb in (1.0, 3.0):
            notes.append((SNARE, offset + bar * 4.0 + sb, 0.3, 115))
    return notes


def anticipation_fill(bs: float = 0.0) -> list[tuple[int, float, float, int]]:
    """Last bar pre-drop fill: tightening ticks → snare flam → drop-out → impact."""
    out = []
    # Beats 0-1.5: accelerating closed-hat ticks
    for i in range(6):
        out.append((HAT_C, bs + i * 0.25, 0.10, 80 + i * 4))
    # Beats 1.5-3: 32nd-note hat ticks
    for i in range(12):
        out.append((HAT_C, bs + 1.5 + i * 0.125, 0.05, 90 + i * 2))
    # Beat 3-3.5: snare flam
    for i in range(4):
        out.append((SNARE, bs + 3.0 + i * 0.125, 0.08, 100 + i * 6))
    # Beat 3.5-3.875: silence (drop-out — anticipation gap)
    # Beat 3.875: impact (kick + snare + crash unison)
    out.append((KICK, bs + 3.875, 0.2, 127))
    out.append((SNARE, bs + 3.875, 0.2, 127))
    out.append((CRASH, bs + 3.875, 4.0, 127))
    return out


def hat_acceleration(bs: float = 0.0, span_beats: float = 4.0) -> list[tuple[int, float, float, int]]:
    """Hat roll accelerating 8th → 16th → 32nd → 64th, rising velocity."""
    out = []
    # 1/4 of span: 8ths
    n8 = max(1, int(span_beats * 0.25 / 0.5))
    for i in range(n8):
        out.append((HAT_C, bs + i * 0.5, 0.10, 80 + i * 5))
    # 1/4: 16ths
    s16 = bs + span_beats * 0.25
    for i in range(int(span_beats * 0.25 / 0.25)):
        out.append((HAT_C, s16 + i * 0.25, 0.08, 92 + i * 3))
    # 1/4: 32nds
    s32 = bs + span_beats * 0.5
    for i in range(int(span_beats * 0.25 / 0.125)):
        out.append((HAT_C, s32 + i * 0.125, 0.06, 102 + i * 2))
    # 1/4: 64ths
    s64 = bs + span_beats * 0.75
    for i in range(int(span_beats * 0.25 / 0.0625)):
        out.append((HAT_C, s64 + i * 0.0625, 0.05, min(115 + i, 127)))
    return out


# ======================================================================
# Note-list utilities
# ======================================================================

def to_clip_notes(quads: Iterable[tuple[int, float, float, int]]) -> list[dict]:
    """Convert (pitch, start_time, duration, velocity) tuples to add_notes_to_clip dicts."""
    return [{"pitch": p, "start_time": float(t), "duration": float(dur), "velocity": int(vel)}
             for (p, t, dur, vel) in quads]


def repeat_pattern(pattern_fn, n_repeats: int, period_beats: float = 16.0,
                    offset: float = 0.0) -> list[tuple[int, float, float, int]]:
    """Tile a pattern N times. pattern_fn is called with (offset + rep * period)."""
    out = []
    for rep in range(n_repeats):
        out.extend(pattern_fn(offset + rep * period_beats))
    return out


# ======================================================================
# Master bus recipes
# ======================================================================

def configure_master_glue(ch, threshold_db: float = -2.0,
                           makeup_db: float = 0.0,
                           dry_wet: float = 0.6) -> None:
    """Find or assume Glue Comp on master and set gentle bus-glue values."""
    for di in range(8):
        try:
            info = ch.get_master_device_info(di).result(timeout=3)
            if info["class_name"] == "GlueCompressor":
                idx = {p["name"]: p["index"] for p in info["parameters"]}
                ch.set_master_device_param(di, idx["Threshold"], threshold_db).result(timeout=3)
                ch.set_master_device_param(di, idx["Makeup"], makeup_db).result(timeout=3)
                ch.set_master_device_param(di, idx["Dry/Wet"], dry_wet).result(timeout=3)
                return
        except Exception:
            return


# ======================================================================
# PARAMETER RANGE REGISTRY — Live's params are MOSTLY normalized 0..1
# even when the UI shows dB / Hz / ms. Read .min/.max from get_device_info
# before sending values. The table below is what we've verified the hard way.
# ======================================================================
#
# DEVICE              PARAM                       RANGE              NOTES
# ------------------- --------------------------- ------------------ --------------------------------
# Track               Volume                      0..1               0.85 ≈ 0 dB unity, 1.0 = +6 dB
# Track               Pan                         -1..+1             negative = left
# Track               Sends                       0..1               post-fader
# Operator            Volume / Tone               0..1               normalized
# Operator            <Op> Coarse                 0..48              FREQUENCY MULTIPLIER, not semitones
# Operator            <Op> Fine                   -50..+50           cents
# Operator            Filter Freq                 0..1               normalized log mapping
# Operator            Filter Res                  0..1.25            (yes, above 1)
# Saturator           Drive                       0..1               NOT -36..+36 dB. Drive=14 → max
# Saturator           Output / Dry-Wet / Color    0..1
# Drum Buss           Drive / Crunch / Boom Decay 0..1
# Drum Buss           Transients                  -1..+1             one of the few signed params
# Drum Buss           Output Gain                 0..1               NOT dB — sending -1 silences
# Compressor          Threshold / Ratio / Attack  0..1               normalized (UI shows dB/ms)
# Compressor          Release / Knee / S/C Gain   0..1
# Compressor          LookAhead                   0..2 (enum)        0=0ms, 1=1ms, 2=10ms
# Compressor          gain_reduction              <NOT EXPOSED>      use A/B meter compare
# EQ8                 N Filter On A               0/1
# EQ8                 N Filter Type A             0..7 (enum)        only 3=Bell, 5=HighShelf verified
# EQ8                 N Frequency A               0..1               log-mapped 30Hz..22kHz — use hz_to_norm
# EQ8                 N Gain A                    -15..+15 dB        actually raw dB
# EQ8                 N Resonance A               0..1
# Limiter             Gain / Ceiling              0..1               clamps bass — avoid on master
# Glue Compressor     Threshold                   -36..+10 dB        raw
# Glue Compressor     Makeup                      0..30 dB           raw
# Glue Compressor     Dry/Wet                     0..1
# Simpler             playback_mode               0..2 (PROPERTY)    NOT a param — set via property; 2=Slicing
# Pitch (audio)       Coarse                      -48..+48 semitones audio clips only
#
# Rule: If a value silences the channel or pushes a chart "to the rails" you
# probably handed a raw dB to a 0..1 param. Read di["parameters"][i]["min"/"max"]
# and use safe_set_param() to log clamps.

# ======================================================================
# GAIN STAGING — discipline checklist (call on every new track)
# ======================================================================

def gain_stage_track(ch, track_index: int, target_volume: float = 0.78,
                      pan: float = 0.0) -> None:
    """Set sane defaults: vol below unity, centered. Use after loading anything.

    Volume guidance (Live's 0..1 fader):
      0.55  : sub / pad sitting under
      0.65  : melodic bus
      0.78  : present but not slamming (default)
      0.85  : ≈ 0 dB unity (lead, kick)
      0.92+ : pushing — only with master headroom
    """
    ch.set_track_volume(track_index, target_volume).result(timeout=3)
    ch.set_track_pan(track_index, pan).result(timeout=3)


# Role-keyed level defaults — pick by intent rather than guessing
TRACK_LEVELS = {
    "kick":      0.85,
    "snare":     0.80,
    "hat":       0.65,
    "perc":      0.70,
    "sub":       0.55,
    "bass":      0.72,
    "lead":      0.78,
    "pad":       0.55,
    "fx":        0.60,
    "vox":       0.78,
    "perc_bus":  0.80,
    "melo_bus":  0.78,
}


# ======================================================================
# KNOWN GOTCHAS — surface them as named constants/booleans so future code
# can branch on them or at least find them via grep.
# ======================================================================

# Loading via selected_drum_pad + load_item only populates the FIRST pad;
# subsequent loads overwrite pad 36. Use bulk_load_drum_pads RPC instead,
# or per-pad chains via separate Simpler tracks.
DRUM_PAD_INDIVIDUAL_LOAD_BROKEN = True

# Simpler's slicing mode is a PROPERTY, not a parameter. Set via:
#   ch.set_device_property(track, dev, "playback_mode", 2)
SIMPLER_SLICING_VIA_PROPERTY = True

# Live's Compressor doesn't expose gain_reduction over the API.
# Measure pump by metering source vs target (A/B with sidechain off/on).
COMPRESSOR_GAIN_REDUCTION_NOT_EXPOSED = True

# A Limiter on the master clamps mid-bass — avoid. Use a gentle Glue Comp.
LIMITER_ON_MASTER_KILLS_BASS = True

# Sidechain isn't a parameter — it's audio_input_routing_type on the device.
# Use ch.set_device_sidechain_source(track, dev, source_track).
SIDECHAIN_VIA_ROUTING_TYPE = True

# Fresh project ships with 2 MIDI + 2 Audio. Loading instruments on audio
# tracks silently spawns new MIDI tracks. Always check is_midi_track first.
LIVE_DEFAULTS_TO_4_TRACKS = True

# Adding new RPCs to live_remote_script requires Live to reload the script
# (toggle the Control Surface dropdown twice in Preferences > Link/MIDI).
RELOAD_SCRIPT_AFTER_RPC_ADD = True

# Windows: console writes break on non-ASCII unless PYTHONIOENCODING=utf-8.
# Set in env or use sys.stdout.reconfigure(encoding='utf-8').
WINDOWS_NEEDS_UTF8_ENV = True

# 24/7 Kit (and many GM kits) trigger a snap/sidestick at note 37 layered
# with snare 38. If you hear unwanted snap, only use 38 — never 37.
SNAP_LAYERED_AT_37 = True

# Hats placed on .25/.75 16ths only sound BEHIND the beat. Always include
# the kick-aligned 0/0.5/1.0 positions and accent them.
HATS_MUST_LOCK_TO_KICK_GRID = True


# ======================================================================
# STUDIO ENGINEER PRINCIPLES — practical advice as code, not folklore
# ======================================================================
#
# "Less is more before the impact." The drop only sounds massive because
# the bar before it sounded thin. Don't keep all instruments running into
# the impact — strip the build, then slam.
#
# Two core ideas:
#   1. Stagger entry/exit by milliseconds, not bars. Hard cuts on bar
#      boundaries flatten the perceived attack — a few ms of taper or a
#      few ms of stagger between simultaneous instrument cuts gives the
#      ear a transient to lock onto. NEVER taper the IMPACT itself —
#      that's the moment the drop lives or dies.
#   2. Identify "harsh" voices (saturated leads, top-heavy stabs, ride
#      cymbals, FM bells) and ramp their entry/exit gently. Kicks, snares,
#      sub, the impact crash — those should hit hard, not be tapered.

# Tracks/voices safe to hard-cut. Anything not in this set should fade
# in/out by ms (not bars) when entering or leaving an arrangement.
HARD_CUT_SAFE_VOICES = {
    "kick", "snare", "sub", "impact", "perc_bus",
    # the IMPACT (drop hit) is sacred — never taper
}

# Voices that need ms-scale taper on entry/exit to avoid edge harshness.
HARSH_VOICES_NEED_TAPER = {
    "saturated_lead", "stab", "ride", "crash_loop", "fm_bell",
    "hardkit_loop", "vox_chop", "organ", "noise_riser",
}

# Recommended ms taper per voice category — short enough not to alter
# perceived placement, long enough to round the edge. NEVER use these
# on the impact transient itself.
TAPER_MS = {
    "soft":   8,    # barely-there edge round — most ms-stagger work
    "medium": 25,   # noticeable taper, harsh saturator/lead exits
    "long":   60,   # only for full-stack exits to silence
}

# Stagger between simultaneous cuts — offset each voice by a few ms so
# the ear gets a transient instead of a wall.
STAGGER_MS_BETWEEN_VOICES = (3, 12)


def staggered_exit_offsets(n_voices: int, base_ms: int = 5) -> list[float]:
    """Generate small ms offsets for n voices exiting together.
       Returns offsets in BEATS (assuming caller knows bpm) — use ms_to_beats."""
    return [i * base_ms for i in range(n_voices)]


def ms_to_beats(ms: float, bpm: float) -> float:
    return (ms / 1000.0) * (bpm / 60.0)


# ----------------------------------------------------------------------
# DROP-BUILD PHILOSOPHY — anticipation by REMOVAL, not just addition
# ----------------------------------------------------------------------
#
# Bigger drop ⇒ thinner build. Counterintuitive but bulletproof: the
# perceived size of an impact is set by the contrast with the bar before
# it. Stack everything into the build and the drop just sounds like
# "more of the same"; strip it back and the same drop sounds enormous.
#
# Stripping rules for the bar(s) before a massive drop:
#   - Drop the kick on the last 1-2 beats (silence is loud)
#   - Mute pads / harmonic content for the last 2 beats
#   - Keep one tightening element (hat ticks, snare flam, riser)
#   - The impact lands into near-silence
#
# Use thin_build_for_massive_drop() to stamp this principle on a clip.

# ----------------------------------------------------------------------
# END / OUTRO — never hard-cut the final bar
# ----------------------------------------------------------------------
#
# A hard cut at end-of-track is jarring on a system. Always taper the
# final 1-2 bars: instruments exit staggered, master fades over ~250ms+,
# crash/reverb tail allowed to ring. Outro is the opposite of impact:
# impact wants silence-then-slam, outro wants slam-then-air.

OUTRO_FADE_MS_DEFAULT = 350      # master taper to silence
OUTRO_INSTRUMENT_STAGGER_MS = 40  # space between voice exits
OUTRO_LET_REVERB_RING_MS = 800    # don't truncate tail


def soft_outro_offsets(voice_order: list[str], bpm: float,
                        stagger_ms: int = OUTRO_INSTRUMENT_STAGGER_MS
                        ) -> list[float]:
    """Return list of beat offsets (one per voice) for staggered outro exits.
       voice_order is exit order — typically: harsh leads first, perc next,
       sub/kick last so the bottom-end falls away gently."""
    return [ms_to_beats(i * stagger_ms, bpm) for i in range(len(voice_order))]


# ----------------------------------------------------------------------
# DECAY TAILS — never let a loud voice cut into silence
# ----------------------------------------------------------------------
#
# When HARDKIT or a saturated lead drops out into a quiet section, a hard
# stop is jarring. Give it a tail: a low-velocity crash hit at the cut
# point rings out naturally via the device's reverb/release, providing
# auditory continuity without competing with the new section.

def crash_decay_tail(at_beat: float, vel: int = 70, dur: float = 6.0
                     ) -> tuple[int, float, float, int]:
    """Single CRASH note at cut point — rides on its own decay envelope.
       Use vel=60..80 (less than impact crash 127), dur ≥ 4 beats."""
    return (CRASH, at_beat, dur, vel)


def low_kick_decay_tail(at_beat: float, vel: int = 55, dur: float = 2.5
                        ) -> tuple[int, float, float, int]:
    """Soft kick to give bottom-end a graceful fall, not a cliff."""
    return (KICK, at_beat, dur, vel)


# ----------------------------------------------------------------------
# AMPLITUDE BREATHING — modulate velocity to enhance impact/anticipation
# ----------------------------------------------------------------------
#
# Subtle (±10-15 vel) breathing on a held pattern adds life without
# changing perceived placement. Pre-drop: progressive velocity decrease
# = "pulling back" → makes the impact relatively bigger. Post-drop:
# breathing-out swell = sustains hype.

def breathe_velocity(notes: list[tuple[int, float, float, int]],
                      amplitude: int = 10,
                      period_beats: float = 8.0,
                      phase_offset: float = 0.0
                      ) -> list[tuple[int, float, float, int]]:
    """Apply sinusoidal velocity modulation. amplitude in MIDI vel units."""
    out = []
    for p, t, dur, vel in notes:
        delta = int(amplitude * math.sin(2 * math.pi * (t / period_beats) + phase_offset))
        new_vel = max(1, min(127, vel + delta))
        out.append((p, t, dur, new_vel))
    return out


def pull_back_before_drop(notes: list[tuple[int, float, float, int]],
                           drop_at_beat: float,
                           pull_window_beats: float = 4.0,
                           min_factor: float = 0.65
                           ) -> list[tuple[int, float, float, int]]:
    """Linearly attenuate velocities in the window before the drop.
       At drop_at_beat - pull_window_beats velocities are full;
       at drop_at_beat - 0 they're scaled by min_factor.
       The note AT drop_at_beat is preserved unchanged (impact is sacred)."""
    out = []
    start = drop_at_beat - pull_window_beats
    for p, t, dur, vel in notes:
        if t == drop_at_beat:
            out.append((p, t, dur, vel))
            continue
        if start <= t < drop_at_beat:
            x = (t - start) / pull_window_beats   # 0..1
            factor = 1.0 - x * (1.0 - min_factor)  # 1 → min_factor
            new_vel = max(1, int(vel * factor))
            out.append((p, t, dur, new_vel))
        else:
            out.append((p, t, dur, vel))
    return out


# ----------------------------------------------------------------------
# MULTIPLE TAKES — print N variations onto the arrangement timeline
# ----------------------------------------------------------------------
#
# Live's arrangement is one timeline. To save multiple takes without
# overwriting, offset each take's start time by total_bars + gap. After
# the run, each take sits side-by-side and you can solo any of them.
# The .als file holds them all; user saves manually with File>Save As to
# checkpoint a particular take set.

TAKE_GAP_BARS = 4  # bars of silence between takes for visual separation


def take_start_bar(take_index: int, take_length_bars: int,
                    gap_bars: int = TAKE_GAP_BARS) -> int:
    return take_index * (take_length_bars + gap_bars)


def thin_build_for_massive_drop(notes: list[tuple[int, float, float, int]],
                                  drop_at_beat: float,
                                  thin_window_beats: float = 2.0,
                                  keep_pitches: tuple[int, ...] = (HAT_C,)
                                  ) -> list[tuple[int, float, float, int]]:
    """Strip notes in the [drop_at_beat - thin_window_beats, drop_at_beat) range
    except the keep_pitches (typically just the hat ticks for tension).

    The drop_at_beat note itself is preserved untouched (impact is sacred).
    """
    start = drop_at_beat - thin_window_beats
    out = []
    for n in notes:
        p, t, dur, vel = n
        if t == drop_at_beat:
            out.append(n)             # impact — keep
        elif start <= t < drop_at_beat:
            if p in keep_pitches:
                out.append(n)         # tightening element only
            # else: dropped (silence creates anticipation)
        else:
            out.append(n)
    return out


# ======================================================================
# MIX RECIPES — bundled multi-step setups that we've tuned to taste
# ======================================================================

def midbass_thump_recipe(ch, master_saturator_idx: int) -> None:
    """Master Saturator Color section tuned for mid-bass thump (≈120 Hz).
       Parallel-blend via Dry/Wet so the punch sits on top, doesn't replace.
       Use after a Saturator is on the master.
    """
    info = ch.get_master_device_info(master_saturator_idx).result(timeout=3)
    idx = {p["name"]: p["index"] for p in info["parameters"]}
    ch.set_master_device_param(master_saturator_idx, idx["Color"], 1).result(timeout=3)
    if "Freq" in idx:
        ch.set_master_device_param(master_saturator_idx, idx["Freq"], 0.42).result(timeout=3)
    if "Width" in idx:
        ch.set_master_device_param(master_saturator_idx, idx["Width"], 0.45).result(timeout=3)
    if "Depth" in idx:
        ch.set_master_device_param(master_saturator_idx, idx["Depth"], 0.55).result(timeout=3)
    ch.set_master_device_param(master_saturator_idx, idx["Drive"], 0.18).result(timeout=3)
    ch.set_master_device_param(master_saturator_idx, idx["Dry/Wet"], 0.35).result(timeout=3)


def sub_track_recipe(ch, sub_track: int, perc_source_track: int,
                     compressor_uri: str, eq_uri: str) -> None:
    """Sub-bass channel: HP@30, LP@700 to keep below mids, sidechain to perc."""
    eq_idx = ensure_device(ch, sub_track, "Eq8", eq_uri)
    set_eq_band(ch, sub_track, eq_idx, 1, ftype=EQ8_HP_12_GUESS, hz=30, on=True)
    set_eq_band(ch, sub_track, eq_idx, 8, ftype=EQ8_LP_12_GUESS, hz=700, on=True)
    sidechain_pump(ch, sub_track, perc_source_track, compressor_uri, intensity="medium")
    ch.set_track_volume(sub_track, TRACK_LEVELS["sub"]).result(timeout=3)


def drop_anticipation_recipe(ch, drum_track: int, slot: int,
                              clip_length_beats: float = 64.0,
                              clip_name: str = "anticipation") -> int:
    """Write 3 bars of amen + 1 bar anticipation_fill into a slot."""
    notes = []
    for rep in range(3):
        notes.extend(amen_4bar(rep * 16.0))
    notes.extend(anticipation_fill(60.0))   # last bar
    notes_filtered = [n for n in notes if 0.0 <= n[1] < clip_length_beats]
    try: ch.clear_clip(drum_track, slot).result(timeout=3)
    except Exception: pass
    ch.create_clip(drum_track, slot, clip_length_beats).result(timeout=10)
    ch.set_clip_name(drum_track, slot, clip_name).result(timeout=3)
    ch.add_notes_to_clip(drum_track, slot, to_clip_notes(notes_filtered)).result(timeout=10)
    return len(notes_filtered)


# ======================================================================
# Standard scene-arrangement template — easy to override
# ======================================================================

# bars per scene mapping for a 16-bar-per-clip arrangement
DEFAULT_ARRANGEMENT = [
    (0, 16),  (1, 16),  (2, 16),  (3, 16),
    (4, 32),  (5, 16),  (6, 16),  (7, 32),
    (9, 32),  (10, 8),  (12, 16), (13, 16),
    (14, 32), (15, 32), (16, 16),
]


__all__ = [
    # constants
    "KICK", "SNARE", "HAT_C", "HAT_O", "RIDE", "CRASH",
    "SIDESTICK", "HAND_CLAP", "LOW_TOM", "HI_TOM",
    "EQ8_BELL", "EQ8_HIGH_SHELF",
    "DEFAULT_ARRANGEMENT",
    # discovery
    "health_check", "find_track", "find_device", "ensure_device",
    # recording
    "arm_arrangement_record", "disarm_arrangement_record", "fire_arrangement",
    # eq
    "hz_to_norm", "set_eq_band", "disable_all_eq_bands",
    # param
    "safe_set_param",
    # sidechain
    "sidechain_pump",
    # patterns
    "amen_4bar", "gabber_4bar", "breakcore_4bar",
    "anticipation_fill", "hat_acceleration",
    # utilities
    "to_clip_notes", "repeat_pattern",
    # master
    "configure_master_glue",
    # gain staging
    "gain_stage_track", "TRACK_LEVELS",
    # recipes
    "midbass_thump_recipe", "sub_track_recipe", "drop_anticipation_recipe",
    # studio engineer principles
    "HARD_CUT_SAFE_VOICES", "HARSH_VOICES_NEED_TAPER", "TAPER_MS",
    "STAGGER_MS_BETWEEN_VOICES", "staggered_exit_offsets", "ms_to_beats",
    "thin_build_for_massive_drop",
    "crash_decay_tail", "low_kick_decay_tail",
    "breathe_velocity", "pull_back_before_drop",
    "TAKE_GAP_BARS", "take_start_bar",
    "OUTRO_FADE_MS_DEFAULT", "OUTRO_INSTRUMENT_STAGGER_MS",
    "OUTRO_LET_REVERB_RING_MS", "soft_outro_offsets",
    # gotcha flags
    "DRUM_PAD_INDIVIDUAL_LOAD_BROKEN", "SIMPLER_SLICING_VIA_PROPERTY",
    "COMPRESSOR_GAIN_REDUCTION_NOT_EXPOSED", "LIMITER_ON_MASTER_KILLS_BASS",
    "SIDECHAIN_VIA_ROUTING_TYPE", "LIVE_DEFAULTS_TO_4_TRACKS",
    "RELOAD_SCRIPT_AFTER_RPC_ADD", "WINDOWS_NEEDS_UTF8_ENV",
    "SNAP_LAYERED_AT_37", "HATS_MUST_LOCK_TO_KICK_GRID",
]
