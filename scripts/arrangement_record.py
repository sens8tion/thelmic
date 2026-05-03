"""Print the Live session into a linear arrangement.

Pipeline:
  1. health_check        — verify session is loaded with the expected tracks
  2. clip modifications  — apply arrangement-specific tweaks to session clips:
                           - anticipation fills on pre-drop slots
                           - crash + soft-kick decay tail at outro
                           - staggered ms taper on outro voices (harsh-first)
  3. arm session-record  — back_to_arrangement, set_song_time(0), enable
                           session-to-arrangement capture, tight launch-quant
  4. play scene sequence — fire each scene at its bar boundary, hold for
                           the configured duration, capture into arrangement
  5. tail ring-out       — sleep through crash + reverb tail (~3.6s) before
                           stopping playback, otherwise the printed
                           arrangement chops the natural fall-off

Session clips have already been:
  - frequency-separated (pass_freq_separation.py)
  - given fade_in / loop=False per voice (pass_clip_fades.py + fix_subbonk_loop.py)
  - had TECTONIC slot 0 cleared (sub too dominant in the open intro)
"""
from __future__ import annotations
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from thelmic.live_channel import LiveChannel
from thelmic.agent_helpers import (
    breathe_velocity, pull_back_before_drop,
    crash_decay_tail, low_kick_decay_tail,
    ms_to_beats, OUTRO_INSTRUMENT_STAGGER_MS, OUTRO_LET_REVERB_RING_MS,
    take_start_bar, TAKE_GAP_BARS,
)


# ----------------------------------------------------------------------
# Arrangement structure — TWO MASSIVE DROPS edition
# ----------------------------------------------------------------------
#
# Each event is a tuple: (kind, *args) where kind is one of:
#   ("scene",   slot,            bars)        — fire scene, hold N bars
#   ("silence", beats,           tag="")      — stop_all_clips, hold N beats
#                                              (creates anticipatory negative space)
#   ("stutter", slot, interval_beats, count, tag="")
#                                            — sub-bar quant, fire N times at
#                                              interval_beats spacing → tease
#
# The anticipation philosophy:
#   1. Patient build — every bar earns the next
#   2. Anticipation slot (3, 6, 13) lands the thinned-build + impact pattern
#   3. NEGATIVE SPACE just before the drop — silence makes the impact bigger
#   4. For drop 2, a stutter-tease prefix amplifies the suspense
#
ARRANGEMENT = [
    # ── INTRO + PATIENT BUILD ──────────────────────────────
    ("scene",  0, 16),                        # INTRO       — pad alone, sub-free open
    # During INTRO, TECTONIC's Saturator Drive starts at 0 (clean) and
    # nudges in slightly so the synth lifts gradually
    ("ramp", {"track": "TECTONIC", "device_substring": "saturator",
              "param_name": "Drive", "from": 0.0, "to": 0.15,
              "duration_bars": 16, "steps": 32, "curve": "log",
              "tag": "TECTONIC saturator nudge in"}),
    # TECTONIC EQ8 HP filter starts very closed, slowly opens through STIRRING+BUILD
    ("ramp", {"track": "TECTONIC", "device_substring": "eq8",
              "param_name": "1 Frequency A", "from": 0.55, "to": 0.20,
              "duration_bars": 32, "steps": 64, "curve": "log",
              "tag": "TECTONIC HP open over STIRRING+BUILD"}),
    # ORGAN AutoPan (the original one, device 1) Frequency ramp — adds
    # subtle rhythmic stutter as we approach the drop
    ("ramp", {"track": "ORGAN", "device_idx": 1,
              "param_name": "Frequency", "from": 0.20, "to": 0.55,
              "duration_bars": 32, "steps": 32, "curve": "linear",
              "tag": "ORGAN auto-pan rate building"}),
    ("scene",  1, 16),                        # STIRRING    — first pulse
    ("scene",  2, 16),                        # BUILD       — drums lift
    # Pre-RISER: HARDKIT EQ HP starts very low, opens slightly during the riser
    ("ramp", {"track": "HARDKIT", "device_substring": "eq8",
              "param_name": "1 Frequency A", "from": 0.10, "to": 0.05,
              "duration_bars": 16, "steps": 32, "curve": "linear",
              "tag": "HARDKIT HP relaxes into D1"}),
    ("scene",  3, 16),                        # RISER       — thinned + impact pattern
    ("silence", 2, "tiny void"),              # ⏸ 0.5b — false-drop setup
    # ── ⚡ FALSE D1 ─────────────────────────────────────────
    ("scene",  4, 4),                         # FAKE D1     — drop hits for 4 bars
    ("silence", 4, "FAKE-OUT void"),          # ⏸ 1 bar — listener thinks "done"
    ("scene",  1, 4),                         # callback to STIRRING (sudden drop in dynamics)
    ("silence", 4, "real void before D1"),    # ⏸ 1 bar — real anticipation
    # ── ⚡ REAL D1 ─────────────────────────────────────────
    # SUBBONK compressor threshold ramp — sidechain tightens during the drop
    ("ramp", {"track": "SUBBONK", "device_substring": "compressor",
              "param_name": "Threshold", "from": 0.55, "to": 0.30,
              "duration_bars": 24, "steps": 24, "curve": "linear",
              "tag": "SUBBONK comp tightening during D1"}),
    # TECTONIC saturator drive intensifies during D1 (warmth → grit)
    ("ramp", {"track": "TECTONIC", "device_substring": "saturator",
              "param_name": "Drive", "from": 0.15, "to": 0.45,
              "duration_bars": 24, "steps": 24, "curve": "exp",
              "tag": "TECTONIC drive grits up over D1"}),
    ("scene",  4, 24),                        # DROP 1 (real) — full ragga jungle
    # ── PIVOT (throw the listener) ─────────────────────────
    # COLD MIST LP closes during the pivot for tonal contrast
    ("ramp", {"track": "COLD MIST", "device_substring": "eq8",
              "param_name": "8 Frequency A", "from": 0.85, "to": 0.45,
              "duration_bars": 8, "steps": 24, "curve": "exp",
              "tag": "COLD MIST LP close over BREAKDOWN"}),
    # Anti-build: TECTONIC HP rises during the pivot (filter starts cutting bass)
    # Creates a thinning effect that makes D2 feel bigger when the bass returns
    ("ramp", {"track": "TECTONIC", "device_substring": "eq8",
              "param_name": "1 Frequency A", "from": 0.20, "to": 0.55,
              "duration_bars": 16, "steps": 32, "curve": "exp",
              "tag": "TECTONIC HP rises (anti-build during pivot)"}),
    ("scene", 12,  8),                        # FOOTWORK    — different rhythmic feel
    ("scene",  5,  8),                        # BREAKDOWN   — quick recovery
    ("scene", 13,  8),                        # JUNGLE RET  — half-anticipation
    # ── REBUILD into D2 ─────────────────────────────────────
    # TECTONIC HP comes BACK DOWN during the rebuild (bass returning)
    ("ramp", {"track": "TECTONIC", "device_substring": "eq8",
              "param_name": "1 Frequency A", "from": 0.55, "to": 0.10,
              "duration_bars": 8, "steps": 24, "curve": "linear",
              "tag": "TECTONIC HP collapses for D2 (bass slam)"}),
    # TECTONIC pitch slides DOWN an octave during rebuild — when D2 hits
    # the bass is at full sub depth (Transpose 0 → -12)
    ("ramp", {"track": "TECTONIC", "device_substring": "operator",
              "param_name": "Transpose", "from": 0.0, "to": -12.0,
              "duration_bars": 8, "steps": 24, "curve": "exp",
              "tag": "TECTONIC pitch slide DOWN to sub for D2"}),
    # ORGAN Chopper #1 Amount 0→1 over the rebuild
    ("ramp", {"track": "ORGAN", "device_idx": 2,
              "param_name": "Amount", "from": 0.0, "to": 1.0,
              "duration_bars": 8, "steps": 32, "curve": "exp",
              "tag": "Chopper1 amount surge"}),
    ("ramp", {"track": "ORGAN", "device_idx": 3,
              "param_name": "Amount", "from": 0.0, "to": 1.0,
              "duration_bars": 8, "steps": 32, "curve": "exp",
              "tag": "Chopper2 amount surge"}),
    ("ramp", {"track": "ORGAN", "device_idx": 4,
              "param_name": "Amount", "from": 0.0, "to": 1.0,
              "duration_bars": 8, "steps": 32, "curve": "exp",
              "tag": "Chopper3 amount surge"}),
    # Chopper Sync Rate ramps from 1/8 (10) to 1/64 (19) — tightening pulse
    ("ramp", {"track": "ORGAN", "device_idx": 2,
              "param_name": "Sync Rate", "from": 10.0, "to": 19.0,
              "duration_bars": 8, "steps": 18, "curve": "linear",
              "tag": "Chopper1 rate tighten"}),
    ("scene",  6,  8),                        # REBUILD     — tightening
    # Bigger tempo pull-back: 165→145 (more dramatic stretch feel)
    ("tempo", 145.0, "DRAMATIC pull-back"),
    ("silence", 6, "void before Rotterdam"),  # ⏸ 6 beats — void
    ("tempo", 165.0, "snap back at D2"),
    # ── ⚡⚡ DROP 2: ROTTERDAM (gabber → breakcore → sustained gabber) ─
    # SUBBONK comp tightens HARDER during D2
    ("ramp", {"track": "SUBBONK", "device_substring": "compressor",
              "param_name": "Threshold", "from": 0.30, "to": 0.15,
              "duration_bars": 16, "steps": 24, "curve": "exp",
              "tag": "SUBBONK comp peak during gabber"}),
    # TECTONIC drive peaks during the gabber — cranked
    ("ramp", {"track": "TECTONIC", "device_substring": "saturator",
              "param_name": "Drive", "from": 0.45, "to": 0.85,
              "duration_bars": 16, "steps": 24, "curve": "exp",
              "tag": "TECTONIC drive peak gabber (cranked)"}),
    # ORGAN Choppers Amount climbs again during gabber for max stutter
    ("ramp", {"track": "ORGAN", "device_idx": 2,
              "param_name": "Amount", "from": 1.0, "to": 1.0,
              "duration_bars": 16, "steps": 4, "curve": "linear",
              "tag": "Chopper1 hold full during gabber"}),
    ("ramp", {"track": "ORGAN", "device_idx": 3,
              "param_name": "Amount", "from": 1.0, "to": 1.0,
              "duration_bars": 16, "steps": 4, "curve": "linear",
              "tag": "Chopper2 hold full during gabber"}),
    ("scene",  7, 16),                        # GABBER 1    — drop hits
    # During BREAKCORE, ramp HARDKIT Saturator drive up for max density
    ("ramp", {"track": "HARDKIT", "device_substring": "saturator",
              "param_name": "Drive", "from": 0.20, "to": 0.65,
              "duration_bars": 16, "steps": 24, "curve": "exp",
              "tag": "HARDKIT saturator drive up"}),
    ("scene",  9, 16),                        # BREAKCORE   — Rotterdam saturation peak
    ("scene",  7, 24),                        # GABBER 2    — sustained max density
    # ── DESCENT + REPRISE ──────────────────────────────────
    # TECTONIC pitch returns to 0 over the descent (bass ascending out of sub)
    ("ramp", {"track": "TECTONIC", "device_substring": "operator",
              "param_name": "Transpose", "from": -12.0, "to": 0.0,
              "duration_bars": 4, "steps": 16, "curve": "linear",
              "tag": "TECTONIC pitch returns to root"}),
    # On the descent, drop saturator drives back to gentle
    ("ramp", {"track": "HARDKIT", "device_substring": "saturator",
              "param_name": "Drive", "from": 0.65, "to": 0.10,
              "duration_bars": 4, "steps": 16, "curve": "linear",
              "tag": "HARDKIT saturator pull back"}),
    ("ramp", {"track": "TECTONIC", "device_substring": "saturator",
              "param_name": "Drive", "from": 0.75, "to": 0.10,
              "duration_bars": 4, "steps": 16, "curve": "linear",
              "tag": "TECTONIC saturator pull back"}),
    # SUBBONK compression releases on descent
    ("ramp", {"track": "SUBBONK", "device_substring": "compressor",
              "param_name": "Threshold", "from": 0.15, "to": 0.55,
              "duration_bars": 4, "steps": 16, "curve": "linear",
              "tag": "SUBBONK comp release"}),
    ("scene",  5,  4),                        # BREAKDOWN   — sudden cut to air
    ("scene",  1,  8),                        # ⤴ STIRRING reprise — emotional callback
    # ── QUIET CLOSE ────────────────────────────────────────
    # COLD MIST HP rises (closes pad) to thin out the close
    ("ramp", {"track": "COLD MIST", "device_substring": "eq8",
              "param_name": "1 Frequency A", "from": 0.30, "to": 0.65,
              "duration_bars": 16, "steps": 32, "curve": "log",
              "tag": "COLD MIST HP rises into close (thinning)"}),
    # TECTONIC LP closes during outro (mid-bass tucks down too)
    ("ramp", {"track": "TECTONIC", "device_substring": "eq8",
              "param_name": "8 Frequency A", "from": 0.60, "to": 0.30,
              "duration_bars": 16, "steps": 32, "curve": "exp",
              "tag": "TECTONIC LP closes outro"}),
    # ORGAN auto-pan slows back to a gentle wash
    ("ramp", {"track": "ORGAN", "device_idx": 1,
              "param_name": "Frequency", "from": 0.55, "to": 0.15,
              "duration_bars": 16, "steps": 32, "curve": "log",
              "tag": "ORGAN auto-pan slows to wash"}),
    ("scene", 11, 16),                        # OUTRO
]

# Pre-drop slots that get anticipation fills written into HARDKIT
ANTICIPATION_SLOTS = (3, 6, 13)

# Drop slots — impact-is-sacred. Used by pass_clip_fades.py for short
# 60ms fades and by this script to skip any future smoothing on these.
DROP_SLOTS = (4, 7, 9)

# Where the outro lives — soften_outro and decay_tail target this slot
OUTRO_SLOT = 11

# Track names we expect; health_check fails fast if missing
EXPECTED_TRACKS = ("TECTONIC", "STAB", "BREAKBEAST", "SUBBONK",
                    "ORGAN", "COLD MIST", "VOX", "HARDKIT")

# Standard MIDI drum pitches (GM)
KICK, SNARE, HAT_C, CRASH = 36, 38, 42, 49


# ----------------------------------------------------------------------
# Discovery helpers
# ----------------------------------------------------------------------

def find_track(ch, sess_count, name_match):
    """First track whose name contains name_match (case-insensitive)."""
    for i in range(sess_count):
        info = ch.get_track_info(i).result(timeout=5)
        if name_match.lower() in info["name"].lower():
            return i
    return None


def health_check(ch):
    """Probe session — fast-fail on empty / wrong project / no Live."""
    try:
        ch.ping().result(timeout=3)
    except Exception as e:
        return False, f"Live not responding: {e}"
    sess = ch.get_session_info().result(timeout=5)
    n = sess["track_count"]
    if n < 6:
        return False, f"only {n} tracks — load the jungle set first"
    found = []; missing = []
    for needle in EXPECTED_TRACKS:
        idx = find_track(ch, n, needle)
        (found if idx is not None else missing).append(
            (needle, idx) if idx is not None else needle)
    if missing:
        return False, f"missing tracks: {missing}"
    return True, found


# ----------------------------------------------------------------------
# Drum-pattern generators
# ----------------------------------------------------------------------

def amen_4bar(start_offset=0.0):
    """Classic 4-bar amen breakbeat with 16th-note hats."""
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
    notes = [(p, t + start_offset, dur, vel) for p, t, dur, vel in base]
    # 16th-note hats with accent pattern (kick-aligned positions louder)
    for i in range(64):
        t = i * 0.25 + start_offset
        vel = {0: 92, 1: 65, 2: 78, 3: 65}[i % 4]
        notes.append((HAT_C, t, 0.18, vel))
    return notes


def fill_anticipation(bs):
    """Last bar of a pre-drop scene — tightening ticks → flam → drop-out → impact.

    bs = the beat at which this single-bar fill begins.
    """
    out = []
    # 0–1.5b: accelerating closed-hat 16ths
    for i in range(6):
        out.append((HAT_C, bs + i * 0.25, 0.10, 80 + i * 4))
    # 1.5–3b: 32nd-note hat ticks (tighter)
    for i in range(12):
        out.append((HAT_C, bs + 1.5 + i * 0.125, 0.05, 90 + i * 2))
    # 3–3.5b: snare flam
    for i in range(4):
        out.append((SNARE, bs + 3.0 + i * 0.125, 0.08, 100 + i * 6))
    # 3.5–3.875b: silence (anticipation gap)
    # 3.875b: impact (kick + snare + crash unison) — sacred
    out.append((KICK,  bs + 3.875, 0.20, 127))
    out.append((SNARE, bs + 3.875, 0.20, 127))
    out.append((CRASH, bs + 3.875, 4.00, 127))
    return out


def write_with_anticipation(ch, hardkit_idx, slot, name):
    """Write a 16-bar HARDKIT clip: 3 bars amen + 1 bar (thinned + fill).
    Adds breathing velocity modulation + pull-back ramp before the impact."""
    notes = []
    # 3 bars of amen
    for rep in range(3):
        notes.extend(amen_4bar(rep * 16.0))
    # 4th bar: amen up to beat 62, then only hats survive into the drop
    for n in amen_4bar(48.0):
        p, t, dur, vel = n
        if t < 62.0:
            notes.append(n)
        elif p == HAT_C and t < 63.875:
            notes.append(n)
    # Anticipation fill on the last bar (bs=60). Skip its pre-impact
    # content in the thinned window except hats and the impact itself.
    for n in fill_anticipation(60.0):
        p, t, _, _ = n
        if t >= 63.875 or p == HAT_C or t < 62.0:
            notes.append(n)

    # Subtle breathing on the steady section (±8 vel, 8-beat period)
    notes = breathe_velocity(notes, amplitude=8, period_beats=8.0)
    # Pull-back over the last 4 beats — impact at 63.875 stays untouched
    notes = pull_back_before_drop(notes, drop_at_beat=63.875,
                                    pull_window_beats=4.0, min_factor=0.6)

    notes_dicts = [{"pitch": p, "start_time": t, "duration": dur, "velocity": vel}
                   for (p, t, dur, vel) in notes if 0.0 <= t < 64.0]
    try: ch.clear_clip(hardkit_idx, slot).result(timeout=3)
    except Exception: pass
    ch.create_clip(hardkit_idx, slot, 64.0).result(timeout=10)
    ch.set_clip_name(hardkit_idx, slot, name).result(timeout=3)
    ch.add_notes_to_clip(hardkit_idx, slot, notes_dicts).result(timeout=10)
    return len(notes_dicts)


# ----------------------------------------------------------------------
# Outro shaping (targets OUTRO_SLOT)
# ----------------------------------------------------------------------

def _clip_notes_or_none(ch, track, slot):
    """Return list of notes for a MIDI clip, or None if empty/audio/missing."""
    try:
        return ch.get_clip_notes(track, slot).result(timeout=3).get("notes", [])
    except Exception:
        return None


def add_decay_tail(ch, hardkit_idx, slot, clip_len_beats=16.0):
    """Append a low-vel CRASH that rings + a soft KICK so HARDKIT's exit
    into a quieter outro is a graceful fall, not a cliff. Only meaningful
    for the HARDKIT MIDI track — silent no-op if clip is empty."""
    notes = _clip_notes_or_none(ch, hardkit_idx, slot)
    if notes is None:
        print(f"    decay tail S{slot}: no clip — skipped")
        return
    cut_at = max(0.0, clip_len_beats - 8.0)   # tail starts 2 bars before end
    cp, ct, cd, cv = crash_decay_tail(cut_at, vel=72, dur=6.0)
    kp, kt, kd, kv = low_kick_decay_tail(cut_at + 1.0, vel=55, dur=2.5)
    extra = [
        {"pitch": cp, "start_time": ct, "duration": cd, "velocity": cv},
        {"pitch": kp, "start_time": kt, "duration": kd, "velocity": kv},
    ]
    ch.add_notes_to_clip(hardkit_idx, slot, extra).result(timeout=10)
    print(f"    decay tail S{slot}: crash@{ct}b (vel{cv}, {cd}b) + soft kick@{kt}b")


def soften_outro_midi(ch, sess_count, bpm, slot, clip_len_beats=16.0):
    """Stagger ms-level cuts on MIDI tracks' outro clips, harsh-first.
    Audio tracks are skipped — we'd need a clip-volume envelope RPC for those.
    The reverb tail is kept by trimming notes only, not clip length."""
    exit_order = ["STAB", "ORGAN", "VOX", "COLD MIST",
                  "BREAKBEAST", "TECTONIC", "SUBBONK", "HARDKIT"]
    offsets_ms = [i * OUTRO_INSTRUMENT_STAGGER_MS for i in range(len(exit_order))]
    print(f"  outro stagger on S{slot}: {offsets_ms} ms (MIDI tracks only)")

    for name, off_ms in zip(exit_order, offsets_ms):
        idx = find_track(ch, sess_count, name)
        if idx is None:
            continue
        notes = _clip_notes_or_none(ch, idx, slot)
        if not notes:                                  # empty / audio / missing
            continue
        cut_at = clip_len_beats - ms_to_beats(off_ms, bpm)
        new_notes = []
        for n in notes:
            t, dur = n["start_time"], n["duration"]
            if t >= cut_at:
                continue
            if t + dur > cut_at:
                dur = max(0.05, cut_at - t)
            new_notes.append({"pitch": n["pitch"], "start_time": t,
                               "duration": dur, "velocity": n["velocity"]})
        try:
            ch.clear_clip(idx, slot).result(timeout=3)
            ch.create_clip(idx, slot, clip_len_beats).result(timeout=5)
            ch.set_clip_name(idx, slot, f"outro_{name.lower()}_taper").result(timeout=3)
            if new_notes:
                ch.add_notes_to_clip(idx, slot, new_notes).result(timeout=10)
            print(f"    {name}: cut at beat {cut_at:.3f} ({off_ms}ms taper)")
        except Exception as e:
            print(f"    {name}: skip ({e})")


# ----------------------------------------------------------------------
# Transport ritual
# ----------------------------------------------------------------------

def hard_reset(ch):
    """Wipe lingering record/session state from any prior run; playhead 0."""
    for fn in (lambda: ch.stop_playback(),
               lambda: ch.set_record_mode(False),
               lambda: ch.set_session_record(False)):
        try: fn().result(timeout=3)
        except Exception: pass
    ch.stop_all_clips().result(timeout=3)
    ch.back_to_arrangement().result(timeout=3)
    ch.set_song_time(0.0).result(timeout=3)


def arm_take(ch, start_bar):
    """Position playhead, arm transport-record + session-record, kill metro,
    tighten launch-quant. Run hard_reset first."""
    ch.stop_playback().result(timeout=3)
    ch.stop_all_clips().result(timeout=3)
    ch.back_to_arrangement().result(timeout=3)
    ch.set_song_time(start_bar * 4.0).result(timeout=5)   # 4 beats per bar
    ch.set_record_mode(True).result(timeout=5)
    ch.set_session_record(True).result(timeout=5)
    ch.set_metronome(False).result(timeout=5)
    ch.set_launch_quantization(1).result(timeout=5)        # 1-bar quant


def disarm_take(ch):
    ch.stop_playback().result(timeout=5)
    ch.set_session_record(False).result(timeout=5)
    ch.set_record_mode(False).result(timeout=5)


# ----------------------------------------------------------------------
# Play loop
# ----------------------------------------------------------------------

def _song_beats(ch):
    """Live's song_time in beats (4 beats per bar)."""
    return ch.get_song_time().result(timeout=2)["song_time"]


def _calibrate(ch, beat_seconds):
    """Read Live's playhead and pair it with a wall-clock anchor — one
    RPC roundtrip up front. Returns (wall_anchor, beat_anchor) so future
    target-beats can be projected to wall time without further polling."""
    beat_anchor = _song_beats(ch)
    wall_anchor = time.monotonic()
    return wall_anchor, beat_anchor


def _wait_until_beat_wallclock(target_beat, wall_anchor, beat_anchor,
                                  beat_seconds, fire_lead_s=0.70):
    """Sleep on the wall clock until we're `fire_lead_s` before target_beat
    (projected from the calibration anchor). One sleep, no per-iteration
    RPC. fire_lead_s gives fire_scene's RPC roundtrip time to deliver the
    command BEFORE the bar boundary, so launch_quantization=1 snaps to the
    correct bar (not the next one)."""
    target_wall = wall_anchor + (target_beat - beat_anchor) * beat_seconds
    fire_at = target_wall - fire_lead_s
    delay = fire_at - time.monotonic()
    if delay > 0:
        time.sleep(delay)


def _event_bars(event):
    """Compute the bar duration of an arrangement event."""
    kind = event[0]
    if kind == "scene":      return event[2]
    if kind == "silence":    return event[1] / 4.0          # beats → bars
    if kind == "scene_solo": return event[3]                # solo'd scene hold in bars
    if kind == "ramp":       return 0.0                     # spawns parallel ramp; consumes no bars
    if kind == "tempo":      return 0.0                     # immediate tempo set; no bars
    if kind == "stutter":
        _, _slot, interval, count = event[:4]
        return (count * interval) / 4.0
    raise ValueError(f"unknown event kind: {kind!r}")


# ----------------------------------------------------------------------
# Realtime parameter ramping (captured into arrangement automation by
# session_record). Each ramp is a list of (deadline_wall, fn) entries
# that get drained as the wall clock crosses each deadline.
# ----------------------------------------------------------------------

def _resolve_ramp_target(ch, n_tracks, ramp):
    """Resolve a ramp's target track / device / param indices."""
    tname = ramp.get("track")
    tidx = find_track(ch, n_tracks, tname) if tname else None
    if tidx is None: return None
    dev_idx = ramp.get("device_idx")
    if dev_idx is None and ramp.get("device_substring"):
        info = ch.get_track_info(tidx).result(timeout=3)
        substr = ramp["device_substring"].lower()
        for di, d in enumerate(info.get("devices", [])):
            nm = (d.get("name") or "") + " " + (d.get("class_name") or "")
            if substr in nm.lower():
                dev_idx = di; break
    if dev_idx is None: return None
    pname = ramp.get("param_name")
    if pname is None: return None
    di = ch.get_device_info(tidx, dev_idx).result(timeout=3)
    pidx = next((p["index"] for p in di["parameters"] if p["name"] == pname), None)
    if pidx is None: return None
    return (tidx, dev_idx, pidx)


def _schedule_ramp(ch, n_tracks, ramp, wall_anchor, beat_anchor, beat_seconds,
                    pending_ramps):
    """Plan a ramp: append (when_wall, fn) entries to pending_ramps.
       Uses pre-resolved 'resolved_target' if available; otherwise resolves now."""
    tgt = ramp.get("resolved_target") or _resolve_ramp_target(ch, n_tracks, ramp)
    if tgt is None:
        print(f"    [ramp] could not resolve target {ramp}")
        return
    tidx, dev_idx, pidx = tgt
    start_beat = ramp.get("start_beat", 0.0)
    duration_beats = ramp.get("duration_bars", 4) * 4
    from_v = ramp["from"]
    to_v   = ramp["to"]
    steps  = ramp.get("steps", 24)
    curve  = ramp.get("curve", "linear")    # "linear" | "exp" | "log"
    for k in range(1, steps + 1):
        frac = k / steps
        if curve == "exp":     frac = frac ** 2
        elif curve == "log":   frac = frac ** 0.5
        v = from_v + (to_v - from_v) * frac
        target_beat = start_beat + frac * duration_beats
        when = wall_anchor + (target_beat - beat_anchor) * beat_seconds
        pending_ramps.append((when, tidx, dev_idx, pidx, float(v)))


def _drain_ramps(ch, pending_ramps):
    """Pop and execute ramp steps whose deadline has passed.

    Fire-and-forget through the BULK queue lane so ramp RPCs don't block
    priority-lane sync calls (stop_all_clips, fire_scene, set_tempo).
    Critical for staying in sync with the playhead — blocking-on-result or
    sharing the priority lane would accumulate drift catastrophically."""
    if not pending_ramps: return
    now = time.monotonic()
    remaining = []
    for entry in pending_ramps:
        when, tidx, dev, pidx, v = entry
        if when <= now:
            try:
                ch._enqueue("set_device_param",
                              {"track_index": tidx, "device_index": dev,
                               "param_index": pidx, "value": float(v)},
                              lane="bulk")
            except Exception: pass
        else:
            remaining.append(entry)
    pending_ramps[:] = remaining


def _pre_resolve_ramps(ch, n_tracks):
    """Walk ARRANGEMENT and resolve every ramp event's track/device/param
    indices BEFORE the print starts. Caches the resolved tuple back into
    the ramp dict as 'resolved_target'. Avoids RPC blocking during the
    real-time loop."""
    n_resolved = 0
    for event in ARRANGEMENT:
        if event[0] != "ramp": continue
        ramp = event[1]
        tgt = _resolve_ramp_target(ch, n_tracks, ramp)
        if tgt is None:
            print(f"  [pre-resolve] FAIL: {ramp.get('tag','')}")
        else:
            ramp["resolved_target"] = tgt
            n_resolved += 1
    print(f"  [pre-resolve] {n_resolved} ramp targets cached")


def fire_arrangement(ch, start_bar, bar_seconds):
    """Walk ARRANGEMENT events, firing each at its target bar. Calibrates
    once against Live's playhead, then schedules everything on the wall
    clock. Handles event kinds: scene / silence / scene_solo / ramp /
    tempo / stutter."""
    beat_seconds = bar_seconds / 4.0
    n_tracks = ch.get_session_info().result(timeout=3)["track_count"]
    _pre_resolve_ramps(ch, n_tracks)

    # First event must be a scene — fire it before record starts so
    # session_record catches it, then start playback.
    first = ARRANGEMENT[0]
    assert first[0] == "scene", "ARRANGEMENT must start with a scene event"
    ch.fire_scene(first[1]).result(timeout=5)
    time.sleep(0.1)
    ch.start_playback().result(timeout=5)
    time.sleep(0.05)
    wall_anchor, beat_anchor = _calibrate(ch, beat_seconds)
    print(f"  calibrate: beat={beat_anchor:.3f} wall={wall_anchor:.3f}")

    pending_ramps = []
    elapsed_bars = _event_bars(first)
    for event in ARRANGEMENT[1:]:
        target_beat = elapsed_bars * 4.0
        # Pump ramps while waiting for the next event's beat
        while True:
            _drain_ramps(ch, pending_ramps)
            now_b = (time.monotonic() - wall_anchor) / beat_seconds + beat_anchor
            if target_beat - now_b <= 0.5:
                break
            time.sleep(0.005)
        kind = event[0]

        if kind == "scene":
            slot, bars = event[1], event[2]
            ch.fire_scene(slot).result(timeout=5)
            try:
                drift = _song_beats(ch) / 4.0 - elapsed_bars
            except Exception:
                drift = 0.0
            print(f"  bar {start_bar + elapsed_bars:>5.1f}: scene S{slot:>2} (hold {bars:>4.1f}b)  drift {drift:+.3f}")

        elif kind == "silence":
            beats = event[1]
            tag = event[2] if len(event) > 2 else ""
            try: ch.stop_all_clips().result(timeout=10)
            except Exception as e: print(f"    silence stop_all_clips fail: {e}")
            print(f"  bar {start_bar + elapsed_bars:>5.1f}: ⏸ silence ({beats:>4.1f}b) — {tag}")

        elif kind == "scene_solo":
            keep_tracks, slot, bars = event[1], event[2], event[3]
            tag = event[4] if len(event) > 4 else ""
            ch.stop_all_clips().result(timeout=3)
            for tname in keep_tracks:
                tidx = find_track(ch, n_tracks, tname)
                if tidx is not None:
                    try: ch.fire_clip(tidx, slot).result(timeout=3)
                    except Exception as e: print(f"    fire_clip {tname} S{slot} fail: {e}")
            print(f"  bar {start_bar + elapsed_bars:>5.1f}: ◐ scene_solo S{slot} keep={keep_tracks} (hold {bars}b) — {tag}")

        elif kind == "ramp":
            ramp_dict = event[1]
            ramp_dict.setdefault("start_beat", target_beat)
            _schedule_ramp(ch, n_tracks, ramp_dict, wall_anchor, beat_anchor,
                            beat_seconds, pending_ramps)
            print(f"  bar {start_bar + elapsed_bars:>5.1f}: ↗ ramp scheduled — {ramp_dict.get('tag','')}")

        elif kind == "tempo":
            new_bpm = event[1]
            tag = event[2] if len(event) > 2 else ""
            try: ch.set_tempo(float(new_bpm)).result(timeout=10)
            except Exception as e: print(f"    tempo set fail: {e!r}")
            print(f"  bar {start_bar + elapsed_bars:>5.1f}: ♩ tempo → {new_bpm:.1f} bpm — {tag}")

        elif kind == "stutter":
            slot, interval, count = event[1], event[2], event[3]
            tag = event[4] if len(event) > 4 else ""
            # Sub-bar quant for the stutter — restore after
            ch.set_launch_quantization(0).result(timeout=3)
            for _ in range(count):
                ch.fire_scene(slot).result(timeout=3)
                time.sleep(interval * beat_seconds)
            ch.set_launch_quantization(1).result(timeout=3)
            print(f"  bar {start_bar + elapsed_bars:>5.1f}: ⚡⚡⚡ stutter S{slot:>2} ×{count} @ {interval}b — {tag}")

        else:
            raise ValueError(f"unknown event kind: {kind!r}")

        elapsed_bars += _event_bars(event)

    # Sleep until the end of the final event's hold, draining pending ramps
    final_target = elapsed_bars * 4.0
    while True:
        _drain_ramps(ch, pending_ramps)
        now_b = (time.monotonic() - wall_anchor) / beat_seconds + beat_anchor
        if final_target - now_b <= 0.0:
            break
        time.sleep(0.005)
    # Drain anything remaining (tail margin)
    _drain_ramps(ch, pending_ramps)
    return elapsed_bars


# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------

def main(num_takes=1, max_bars=None):
    ch = LiveChannel(lower_priority=False); ch.start()
    try:
        ok, detail = health_check(ch)
        if not ok:
            print(f"HEALTH CHECK FAILED: {detail}")
            print("Open the saved jungle Live set, then re-run.")
            return
        print(f"health OK — found tracks: {detail}")

        sess = ch.get_session_info().result(timeout=5)
        n = sess["track_count"]
        bpm = sess["tempo"]
        bar_seconds = 60.0 / bpm * 4
        beat_seconds = bar_seconds / 4.0

        T_HARDKIT = find_track(ch, n, "HARDKIT")
        if T_HARDKIT is None:
            print("can't find HARDKIT")
            return

        # ---- 1. Pre-drop anticipation fills (HARDKIT slots 3, 6, 13) ----
        print("\nanticipation fills on pre-drop slots...")
        for slot in ANTICIPATION_SLOTS:
            try:
                n_notes = write_with_anticipation(
                    ch, T_HARDKIT, slot, f"slot{slot}_anticipation")
                print(f"  S{slot}: {n_notes} notes (thinned 2-beat window + impact)")
            except Exception as e:
                print(f"  S{slot} fail: {e}")

        # ---- 2. Outro shaping (targets OUTRO_SLOT, currently 11) ----
        print(f"\noutro shaping on S{OUTRO_SLOT}...")
        try: soften_outro_midi(ch, n, bpm, OUTRO_SLOT)
        except Exception as e: print(f"  soften_outro fail: {e}")
        try: add_decay_tail(ch, T_HARDKIT, OUTRO_SLOT)
        except Exception as e: print(f"  decay tail fail: {e}")

        # ---- 3. Take loop ----
        # Optionally truncate ARRANGEMENT for quick alignment tests
        global ARRANGEMENT
        if max_bars is not None:
            truncated = []
            consumed = 0
            for ev in ARRANGEMENT:
                ev_bars = _event_bars(ev)
                remain = max_bars - consumed
                if remain <= 0: break
                if ev_bars <= remain:
                    truncated.append(ev)
                    consumed += ev_bars
                else:
                    if ev[0] == "scene":
                        truncated.append(("scene", ev[1], remain))
                        consumed += remain
                    break
            ARRANGEMENT = truncated
            print(f"\n[truncated to {max_bars} bars: {len(ARRANGEMENT)} events]")
        total_bars = sum(_event_bars(ev) for ev in ARRANGEMENT)
        print(f"\nbpm={bpm}, 1 bar = {bar_seconds:.3f}s")
        print(f"per take: {total_bars} bars = {total_bars * bar_seconds:.1f}s")
        print(f"takes: {num_takes} (gap {TAKE_GAP_BARS} bars between)")

        print("\nhard reset...")
        hard_reset(ch)

        for take_i in range(num_takes):
            start_bar = take_start_bar(take_i, total_bars, TAKE_GAP_BARS)
            print(f"\n=== take {take_i+1}/{num_takes} starting bar {start_bar} ===")
            arm_take(ch, start_bar)
            fire_arrangement(ch, start_bar, bar_seconds)
            # Tail: crash decay (6b) + reverb tail (~800ms) + 1s margin
            tail_seconds = max(6 * beat_seconds,
                                OUTRO_LET_REVERB_RING_MS / 1000.0) + 1.0
            time.sleep(tail_seconds)
            disarm_take(ch)

        ch.set_launch_quantization(8).result(timeout=5)   # restore session default
        total_arr_bars = num_takes * total_bars + (num_takes - 1) * TAKE_GAP_BARS
        print(f"\nARRANGEMENT COMPLETE — {num_takes} take(s), {total_arr_bars} bars / "
              f"~{total_arr_bars * bar_seconds / 60:.1f} min")
        print("Open Arrangement View. Save As to checkpoint a take you like.")
    finally:
        ch.stop()


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    mb = int(sys.argv[2]) if len(sys.argv) > 2 else None
    main(num_takes=n, max_bars=mb)
