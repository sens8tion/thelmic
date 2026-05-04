"""dnb_jungle anticipation + dynamics transforms.

These embody the pack's aesthetic stance:
  - "the impact is sacred"
  - "the build pulls back to make the drop bigger"
  - "harsh voices need ms-scale tapers; impacts hit hard"
  - "the outro rings out, doesn't cut"
"""
from __future__ import annotations
import math
from .constants import (
    KICK, SNARE, HAT_C, CRASH,
    OUTRO_INSTRUMENT_STAGGER_MS, OUTRO_LET_REVERB_RING_MS,
    TAKE_GAP_BARS, FREQ_SEPARATION, TRACK_LEVELS,
)
from thelmic.bridge.helpers import (
    ms_to_beats, set_eq_band, ensure_device, find_device,
    EQ8_HP_12_GUESS, EQ8_LP_12_GUESS, hz_to_norm, sidechain_pump,
)
from .patterns import anticipation_fill


# ----------------------------------------------------------------------
# Velocity transforms
# ----------------------------------------------------------------------

def breathe_velocity(notes, amplitude=10, period_beats=8.0, phase_offset=0.0):
    """Apply sinusoidal velocity modulation. amplitude in MIDI vel units."""
    out = []
    for p, t, dur, vel in notes:
        delta = int(amplitude * math.sin(2 * math.pi * (t / period_beats) + phase_offset))
        new_vel = max(1, min(127, vel + delta))
        out.append((p, t, dur, new_vel))
    return out


def pull_back_before_drop(notes, drop_at_beat, pull_window_beats=4.0, min_factor=0.65):
    """Linearly attenuate velocities in the window before the drop.
    The note AT drop_at_beat is preserved unchanged (impact is sacred)."""
    out = []
    start = drop_at_beat - pull_window_beats
    for p, t, dur, vel in notes:
        if t == drop_at_beat:
            out.append((p, t, dur, vel))
            continue
        if start <= t < drop_at_beat:
            x = (t - start) / pull_window_beats
            factor = 1.0 - x * (1.0 - min_factor)
            new_vel = max(1, int(vel * factor))
            out.append((p, t, dur, new_vel))
        else:
            out.append((p, t, dur, vel))
    return out


def thin_build_for_massive_drop(notes, drop_at_beat, thin_window_beats=2.0,
                                  keep_pitches=(HAT_C,)):
    """Strip notes in the [drop_at_beat - thin_window_beats, drop_at_beat) range
    except the keep_pitches. The drop_at_beat note is preserved untouched."""
    start = drop_at_beat - thin_window_beats
    out = []
    for n in notes:
        p, t, _, _ = n
        if t == drop_at_beat:
            out.append(n)
        elif start <= t < drop_at_beat:
            if p in keep_pitches:
                out.append(n)
        else:
            out.append(n)
    return out


# ----------------------------------------------------------------------
# Decay tails
# ----------------------------------------------------------------------

def crash_decay_tail(at_beat, vel=70, dur=6.0):
    """Single CRASH note at cut point — rides on its own decay envelope."""
    return (CRASH, at_beat, dur, vel)


def low_kick_decay_tail(at_beat, vel=55, dur=2.5):
    """Soft kick to give bottom-end a graceful fall, not a cliff."""
    return (KICK, at_beat, dur, vel)


# ----------------------------------------------------------------------
# Outro / multi-take helpers
# ----------------------------------------------------------------------

def soft_outro_offsets(voice_order, bpm, stagger_ms=OUTRO_INSTRUMENT_STAGGER_MS):
    """Return list of beat offsets (one per voice) for staggered outro exits."""
    return [ms_to_beats(i * stagger_ms, bpm) for i in range(len(voice_order))]


def take_start_bar(take_index, take_length_bars, gap_bars=TAKE_GAP_BARS):
    return take_index * (take_length_bars + gap_bars)


# ----------------------------------------------------------------------
# Smooth-entry filter sweep (clip envelope on EQ8 freq)
# ----------------------------------------------------------------------

def smooth_clip_entry(ch, track_index, slot, *, sweep_ms=400,
                       sweep_from_hz=2000, sweep_to_hz=180,
                       eq_device_index=None, eq_band=1, bpm=None):
    """Write a clip envelope on EQ8 band frequency that sweeps from
    sweep_from_hz down to sweep_to_hz over sweep_ms. Returns True/False."""
    if bpm is None:
        sess = ch.get_session_info().result(timeout=5)
        bpm = sess.get("tempo", 120.0)
    sweep_beats = ms_to_beats(sweep_ms, bpm)
    if eq_device_index is None:
        eq_device_index = find_device(ch, track_index, "Eq8")
        if eq_device_index is None:
            raise RuntimeError(f"track {track_index}: no EQ8")
    sweep_breakpoints = [
        (0.0, hz_to_norm(sweep_from_hz)),
        (sweep_beats, hz_to_norm(sweep_to_hz)),
    ]
    try:
        ch.set_clip_envelope(track_index, slot,
                              target_track=track_index,
                              target_device=eq_device_index,
                              target_param=f"{eq_band} Frequency A",
                              breakpoints=sweep_breakpoints).result(timeout=5)
        return True
    except Exception:
        return False


# ----------------------------------------------------------------------
# Mix recipes
# ----------------------------------------------------------------------

def gain_stage_track(ch, track_index, target_volume=0.78, pan=0.0):
    """Set sane defaults: vol below unity, centered."""
    ch.set_track_volume(track_index, target_volume).result(timeout=3)
    ch.set_track_pan(track_index, pan).result(timeout=3)


def apply_freq_separation(ch, track_index, role,
                           eq_uri="query:AudioFx#EQ%20Eight"):
    """Carve frequency space for a track based on its role.
    Adds an EQ8 if missing, sets band 1 = HP and band 8 = LP per role."""
    if role not in FREQ_SEPARATION:
        raise ValueError(f"unknown role '{role}', valid: {list(FREQ_SEPARATION)}")
    hp, lp = FREQ_SEPARATION[role]
    eq = ensure_device(ch, track_index, "Eq8", eq_uri)
    set_eq_band(ch, track_index, eq, 1, ftype=EQ8_HP_12_GUESS, hz=hp,
                gain=0.0, q_norm=0.5, on=True)
    if lp is not None:
        set_eq_band(ch, track_index, eq, 8, ftype=EQ8_LP_12_GUESS, hz=lp,
                    gain=0.0, q_norm=0.5, on=True)
    return eq


def midbass_thump_recipe(ch, master_saturator_idx):
    """Master Saturator Color section tuned for mid-bass thump (~120 Hz)."""
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


def sub_track_recipe(ch, sub_track, perc_source_track,
                     compressor_uri, eq_uri):
    """Sub-bass channel: HP@30, LP@700, sidechain to perc."""
    eq_idx = ensure_device(ch, sub_track, "Eq8", eq_uri)
    set_eq_band(ch, sub_track, eq_idx, 1, ftype=EQ8_HP_12_GUESS, hz=30, on=True)
    set_eq_band(ch, sub_track, eq_idx, 8, ftype=EQ8_LP_12_GUESS, hz=700, on=True)
    sidechain_pump(ch, sub_track, perc_source_track, compressor_uri, intensity="medium")
    ch.set_track_volume(sub_track, TRACK_LEVELS["sub"]).result(timeout=3)


def drop_anticipation_recipe(ch, drum_track, slot, clip_length_beats=64.0,
                              clip_name="anticipation"):
    """Write 3 bars of amen + 1 bar anticipation_fill into a slot."""
    from .patterns import amen_4bar
    from thelmic.bridge.helpers import to_clip_notes
    notes = []
    for rep in range(3):
        notes.extend(amen_4bar(rep * 16.0))
    notes.extend(anticipation_fill(60.0))
    notes_filtered = [n for n in notes if 0.0 <= n[1] < clip_length_beats]
    try: ch.clear_clip(drum_track, slot).result(timeout=3)
    except Exception: pass
    ch.create_clip(drum_track, slot, clip_length_beats).result(timeout=10)
    ch.set_clip_name(drum_track, slot, clip_name).result(timeout=3)
    ch.add_notes_to_clip(drum_track, slot, to_clip_notes(notes_filtered)).result(timeout=10)
    return len(notes_filtered)


def configure_master_glue(ch, threshold_db=-2.0, makeup_db=0.0, dry_wet=0.6):
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
