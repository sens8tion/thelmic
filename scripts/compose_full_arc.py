"""Comprehensive composition pipeline for the ragga → Rotterdam arc.

Discovered track inventory:
  T0 TECTONIC      MIDI    Operator + EQ8 + Saturator
  T1 STAB          MIDI    Operator + EQ8 + Auto Pan
  T2 BREAKBEAST    audio   EQ8                              (sample-based break)
  T3 SUBBONK       audio   Compressor + EQ8 + Auto Pan      (sample-based sub)
  T4 ORGAN         audio   EQ8 + Auto Pan + 3 Choppers      (sample-based organ)
  T5 COLD MIST     audio   EQ8 + Auto Pan                   (sample-based pad)
  T6 VOX YO        MIDI    Simpler "yo chargie" + EQ8 + Trash
  T7 HARDKIT       MIDI    909 Core Kit + EQ8
  T8 HARDKIT       MIDI    909 Core Kit + EQ8               (dup — alt voicing)
  T9 AMEN CHOPPED  MIDI    Drum Rack
  T10 VOX BIG      MIDI    Simpler "big up"
  T11 VOX SEL      MIDI    Simpler "selassie i"

Composition passes (each does one layer of the trick):
  PASS 0  Ensure HARDKIT has a Saturator (for drive ramps)
  PASS 1  HARDKIT  S4   ragga jungle drop pattern (with breathing + pull-back)
  PASS 2  HARDKIT  S7   Rotterdam gabber (16th hats → 32nd → 64th tightening)
  PASS 3  AMEN     S9   breakcore peak (16th-note kicks throughout, snare flams)
  PASS 4  HARDKIT  S11  quiet outro (sparse half-time skeleton)
  PASS 5  HARDKIT  S2   build-section drum rolls (rising velocity)
  PASS 6  HARDKIT  S6   rebuild — accelerating snare rolls + tightening hats
  PASS 7  TECTONIC S1   octave-down arp lifting in
  PASS 8  TECTONIC S2,3 octave-walking arp building
  PASS 9  TECTONIC S4,7 full-octave arps for both drops
  PASS 10 STAB     ragga organ chord stabs across the build
  PASS 11 VOX YO   "yo" stabs at scene boundaries
  PASS 12 VOX BIG  "big up" stabs at the drop transitions
  PASS 13 VOX SEL  "selassie i" sustained vocal during D2

After composition, separate scripts handle:
  - pass_freq_separation.py: sound-stage HP/LP per track
  - pass_clip_fades.py:      audio fade-in / fade-out
  - fix_subbonk_loop.py:     loop=False on SUBBONK
  - arrangement_record.py:   prints with anticipation fills + ramps + tempo mod
"""
from __future__ import annotations
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("LIVE_CHANNEL_ENABLED", "1")
from thelmic.mediated_session import open_session
from thelmic.agent_helpers import (
    find_track, find_device, ensure_device,
    breathe_velocity, pull_back_before_drop, to_clip_notes,
)

# Drum pitches (GM)
KICK, SNARE, HAT_C, HAT_O, RIDE, CRASH = 36, 38, 42, 46, 51, 49

# C minor / E♭ major scale (transposable)
SCALE_ROOT = 36
SCALE = [0, 2, 3, 5, 7, 8, 10]                 # natural minor
ARP_NOTES = [0, 7, 12, 15]                      # root-fifth-octave-flat3

SAT_URI = "query:AudioFx#Saturator"


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------

_TRACK_IS_MIDI = {}

def _is_midi(ch, t):
    if t in _TRACK_IS_MIDI: return _TRACK_IS_MIDI[t]
    info = ch.get_track_info(t).result(timeout=3)
    v = bool(info.get("is_midi_track"))
    _TRACK_IS_MIDI[t] = v
    return v


def write_midi_clip(ch, track, slot, length_beats, name, notes_quads,
                     pull_back=True, breathe=False):
    """Write fresh MIDI notes into (track, slot)."""
    if not _is_midi(ch, track):
        return -1
    if breathe:
        notes_quads = breathe_velocity(notes_quads, amplitude=8, period_beats=8.0)
    if pull_back:
        notes_quads = pull_back_before_drop(notes_quads,
                                              drop_at_beat=length_beats - 0.125,
                                              pull_window_beats=4.0,
                                              min_factor=0.65)
    notes_dicts = to_clip_notes([(p, t, dur, vel)
                                  for (p, t, dur, vel) in notes_quads
                                  if 0.0 <= t < length_beats])
    try: ch.clear_clip(track, slot).result(timeout=3)
    except Exception: pass
    ch.create_clip(track, slot, float(length_beats)).result(timeout=10)
    ch.set_clip_name(track, slot, name).result(timeout=3)
    ch.add_notes_to_clip(track, slot, notes_dicts).result(timeout=10)
    return len(notes_dicts)


# ----------------------------------------------------------------------
# Drum patterns
# ----------------------------------------------------------------------

def ragga_jungle_4bar(offset=0.0, hat_density="16th"):
    notes = []
    for bar in range(4):
        bs = bar * 4 + offset
        # Skipping kick (ragga feel)
        notes.append((KICK,  bs + 0.0, 0.40, 118))
        notes.append((KICK,  bs + 2.5, 0.40, 105))
        # Snare backbeat + ghosts
        notes.append((SNARE, bs + 1.0, 0.30, 110))
        notes.append((SNARE, bs + 3.0, 0.30, 115))
        notes.append((SNARE, bs + 3.75, 0.18, 72))
        # Ride wash on alternating bars
        if bar % 2 == 1:
            notes.append((RIDE, bs + 0.0, 0.60, 95))
            notes.append((RIDE, bs + 2.0, 0.50, 88))
        # Hats
        if hat_density == "16th":
            for i in range(16):
                t = bs + i * 0.25
                vel = 92 if i % 4 == 0 else 65 if i % 2 == 0 else 72
                notes.append((HAT_C, t, 0.16, vel))
        elif hat_density == "32nd":
            for i in range(32):
                t = bs + i * 0.125
                vel = 88 - (i % 8) * 3
                notes.append((HAT_C, t, 0.08, vel))
    return notes


def rotterdam_gabber_4bar(offset=0.0, double_time=False, hat_density="16th"):
    notes = []
    for bar in range(4):
        bs = bar * 4 + offset
        n_kicks = 8 if double_time else 4
        rate = 0.5 if double_time else 1.0
        for k in range(n_kicks):
            t = bs + k * rate
            vel = 127 if (k * rate) % 1 == 0 else 122
            notes.append((KICK, t, 0.20 if double_time else 0.30, vel))
        # Snare on 2 and 4
        notes.append((SNARE, bs + 1.0, 0.25, 122))
        notes.append((SNARE, bs + 3.0, 0.25, 122))
        # Hats
        if hat_density == "16th":
            for i in range(16):
                t = bs + i * 0.25
                notes.append((HAT_C, t, 0.10, 90 if i % 4 == 0 else 68))
        elif hat_density == "32nd":
            for i in range(32):
                t = bs + i * 0.125
                notes.append((HAT_C, t, 0.07, 85 if i % 8 == 0 else 62))
        elif hat_density == "64th":
            for i in range(64):
                t = bs + i * 0.0625
                notes.append((HAT_C, t, 0.04, 80 if i % 16 == 0 else 55))
        if bar == 0:
            notes.append((CRASH, bs + 0.0, 2.0, 115))
    return notes


def breakcore_4bar(offset=0.0):
    """16th-note kicks throughout, polyrhythmic snare flams."""
    notes = []
    for bar in range(4):
        bs = bar * 4 + offset
        # 16th kicks
        for i in range(16):
            t = bs + i * 0.25
            vel = 124 if i % 4 == 0 else 110 if i % 2 == 0 else 115
            notes.append((KICK, t, 0.10, vel))
        # Snare flams on backbeats
        notes.append((SNARE, bs + 0.96, 0.06, 80))
        notes.append((SNARE, bs + 1.00, 0.20, 118))
        notes.append((SNARE, bs + 2.96, 0.06, 80))
        notes.append((SNARE, bs + 3.00, 0.20, 118))
        # 32nd hats
        for i in range(32):
            t = bs + i * 0.125
            vel = 78 + (i % 4) * 4
            notes.append((HAT_C, t, 0.06, vel))
        # 3-against-4 polyrhythm: kick triplets every 1.33 beats too
        for k in range(3):
            tk = bs + k * (4.0/3.0)
            notes.append((LOW_TOM := 41, tk, 0.10, 95))
    return notes


def quiet_outro_4bar(offset=0.0):
    notes = []
    for bar in range(4):
        bs = bar * 4 + offset
        kvel = max(35, 95 - bar * 12)
        notes.append((KICK, bs + 0.0, 0.40, kvel))
        notes.append((RIDE, bs + 0.0, 4.0, max(40, 70 - bar * 8)))
        if bar in (1, 3):
            notes.append((SNARE, bs + 2.5, 0.20, max(35, 50 - bar * 5)))
    return notes


def build_drum_roll_4bar(offset=0.0, accent_bar=3):
    """Build pattern with rising rolls. accent_bar gets a bigger fill."""
    notes = []
    for bar in range(4):
        bs = bar * 4 + offset
        notes.append((KICK,  bs + 0.0, 0.30, 95))
        notes.append((SNARE, bs + 1.0, 0.25, 90))
        notes.append((SNARE, bs + 3.0, 0.25, 95))
        # 16th hats
        for i in range(16):
            t = bs + i * 0.25
            vel = 75 + bar * 4
            notes.append((HAT_C, t, 0.12, vel))
        # In the last bar — a snare roll
        if bar == accent_bar:
            for i in range(8):
                t = bs + 2.0 + i * 0.25
                vel = 80 + i * 5
                notes.append((SNARE, t, 0.10, min(127, vel)))
    return notes


def rebuild_4bar(offset=0.0, hat_acceleration=False):
    """Pre-D2 rebuild — tightening."""
    notes = []
    for bar in range(4):
        bs = bar * 4 + offset
        # Kick on 1, 3
        notes.append((KICK,  bs + 0.0, 0.30, 105))
        notes.append((KICK,  bs + 2.0, 0.30, 100))
        # Snare on 2, 4
        notes.append((SNARE, bs + 1.0, 0.25, 105))
        notes.append((SNARE, bs + 3.0, 0.25, 110))
        # Tightening hats: bar 0 = 16th, bar 1 = 32nd, bar 2 = 32nd, bar 3 = 64th
        if hat_acceleration:
            density = [16, 32, 32, 64][bar]
        else:
            density = 16
        step = 4.0 / density
        for i in range(density):
            t = bs + i * step
            vel = 80 + (i % 8) * 2
            notes.append((HAT_C, t, max(0.04, step*0.7), vel))
        # Rising snare rolls in bar 3
        if bar == 3:
            for i in range(16):
                t = bs + 2.0 + i * 0.125
                vel = min(127, 80 + i * 3)
                notes.append((SNARE, t, 0.06, vel))
    return notes


# ----------------------------------------------------------------------
# Bass / harmonic
# ----------------------------------------------------------------------

def tectonic_arp_4bar(offset=0.0, octave_shift=0, density="8th"):
    notes = []
    step = 0.5 if density == "8th" else 0.25
    n_per_bar = int(4 / step)
    for bar in range(4):
        bs = bar * 4 + offset
        for i in range(n_per_bar):
            t = bs + i * step
            note_idx = ARP_NOTES[i % len(ARP_NOTES)]
            pitch = SCALE_ROOT + note_idx + octave_shift
            vel = 95 if i % 4 == 0 else 80
            notes.append((pitch, t, step * 0.85, vel))
    return notes


def stab_chord_4bar(offset=0.0, root_shift=0):
    """Minor chord stabs on backbeats. root_shift transposes for harmonic motion."""
    notes = []
    chord = [60 + root_shift, 63 + root_shift, 67 + root_shift]   # min triad
    for bar in range(4):
        bs = bar * 4 + offset
        for beat in (1.0, 3.0):
            for p in chord:
                notes.append((p, bs + beat, 0.30, 100))
        # Off-beat ghost
        for p in chord:
            notes.append((p, bs + 3.75, 0.15, 75))
    return notes


# ----------------------------------------------------------------------
# Vocal stabs (Simpler triggers — single-note fires at scheduled points)
# ----------------------------------------------------------------------

def vocal_pulse(offset=0.0, hits=None, vel=110):
    """Schedule single-shot vocal triggers at given beat offsets within a 16-bar clip.
       hits: list of beat times (relative to offset)."""
    if hits is None: return []
    return [(60, offset + t, 0.5, vel) for t in hits]


# ----------------------------------------------------------------------
# Composition pipeline
# ----------------------------------------------------------------------

def main():
    with open_session(name="compose-full-arc") as sess:
        ch = sess.raw_ch

        T = {}
        for nm in ["TECTONIC", "STAB", "BREAKBEAST", "SUBBONK", "ORGAN",
                   "COLD MIST", "VOX YO", "HARDKIT", "AMEN", "VOX BIG", "VOX SEL"]:
            T[nm] = find_track(ch, nm)
            print(f"  {nm}: T{T[nm]}")

        sess.snapshot("before-compose")

        # ── PASS 0: ensure Saturator on HARDKIT (for drive ramp) ──
        print("\nPASS 0: ensure HARDKIT has Saturator")
        if T["HARDKIT"] is not None:
            sat_idx = find_device(ch, T["HARDKIT"], "Saturator")
            if sat_idx is None:
                sat_idx = ensure_device(ch, T["HARDKIT"], "Saturator", SAT_URI)
                # Set initial drive to low
                di = ch.get_device_info(T["HARDKIT"], sat_idx).result(timeout=3)
                drive = next((p for p in di["parameters"] if p["name"] == "Drive"), None)
                if drive:
                    ch.set_device_param(T["HARDKIT"], sat_idx,
                                          drive["index"], 0.20).result(timeout=2)
                print(f"  Saturator added at device {sat_idx}, Drive=0.20")
            else:
                print(f"  Saturator already on HARDKIT at device {sat_idx}")

        # ── PASS 1: HARDKIT S4 — ragga jungle drop ────────────────
        print("\nPASS 1: HARDKIT S4 — ragga jungle drop (32 bars)")
        ragga = []
        for r in range(6):
            ragga.extend(ragga_jungle_4bar(r * 4, hat_density="16th"))
        ragga.extend(ragga_jungle_4bar(24, hat_density="32nd"))
        impact_t = 32 - 0.125
        ragga.append((KICK, impact_t, 0.20, 127))
        ragga.append((SNARE, impact_t, 0.20, 127))
        ragga.append((CRASH, impact_t, 4.00, 127))
        n = write_midi_clip(ch, T["HARDKIT"], 4, 32.0, "drop_ragga", ragga, breathe=True)
        print(f"  S4: {n}")

        # ── PASS 2: HARDKIT S7 — Rotterdam gabber tightening ─────
        print("\nPASS 2: HARDKIT S7 — Rotterdam gabber (16th→32nd→64th hat tightening)")
        gabber = []
        gabber.extend(rotterdam_gabber_4bar(0,  double_time=False, hat_density="16th"))
        gabber.extend(rotterdam_gabber_4bar(16, double_time=False, hat_density="32nd"))
        gabber.extend(rotterdam_gabber_4bar(28, double_time=True,  hat_density="64th"))
        impact_t = 32 - 0.125
        gabber.append((KICK, impact_t, 0.20, 127))
        gabber.append((CRASH, impact_t, 4.00, 127))
        n = write_midi_clip(ch, T["HARDKIT"], 7, 32.0, "drop_rotterdam", gabber)
        print(f"  S7: {n}")

        # ── PASS 3: AMEN slot 9 — breakcore peak ─────────────────
        if T["AMEN"] is not None:
            print("\nPASS 3: AMEN CHOPPED S9 — breakcore peak (32 bars chaos)")
            bc = []
            for r in range(8):
                bc.extend(breakcore_4bar(r * 4))
            n = write_midi_clip(ch, T["AMEN"], 9, 32.0, "breakcore_peak", bc,
                                  pull_back=False)
            print(f"  S9: {n}")
        # Also write to HARDKIT slot 9
        bc = []
        for r in range(8):
            bc.extend(breakcore_4bar(r * 4))
        n = write_midi_clip(ch, T["HARDKIT"], 9, 32.0, "breakcore_peak", bc,
                              pull_back=False)
        print(f"  HARDKIT S9: {n}")

        # ── PASS 4: HARDKIT S11 — quiet outro ────────────────────
        print("\nPASS 4: HARDKIT S11 — quiet outro (16 bars sparse)")
        outro = []
        for r in range(4):
            outro.extend(quiet_outro_4bar(r * 4))
        n = write_midi_clip(ch, T["HARDKIT"], 11, 16.0, "outro_quiet", outro,
                              pull_back=False)
        print(f"  S11: {n}")

        # ── PASS 5: HARDKIT S2 — build-section rolls ─────────────
        print("\nPASS 5: HARDKIT S2 — build (rising rolls each bar)")
        build_drum = []
        for r in range(4):
            build_drum.extend(build_drum_roll_4bar(r * 4, accent_bar=3 if r == 3 else -1))
        n = write_midi_clip(ch, T["HARDKIT"], 2, 16.0, "build_rolls", build_drum)
        print(f"  S2: {n}")

        # ── PASS 6: HARDKIT S6 — pre-D2 rebuild with tightening hats ─
        print("\nPASS 6: HARDKIT S6 — rebuild (hat 16th→32nd→32nd→64th)")
        rb = []
        for r in range(4):
            rb.extend(rebuild_4bar(r * 4, hat_acceleration=True))
        n = write_midi_clip(ch, T["HARDKIT"], 6, 16.0, "rebuild_tighten", rb,
                              pull_back=True, breathe=True)
        print(f"  S6: {n}")

        # ── PASS 7: TECTONIC S1 — octave-down arp lifting in ─────
        print("\nPASS 7: TECTONIC S1 — octave-down arp")
        t1 = []
        for r in range(4):
            t1.extend(tectonic_arp_4bar(r * 4, octave_shift=-12, density="8th"))
        n = write_midi_clip(ch, T["TECTONIC"], 1, 16.0, "mid_arp_low", t1, breathe=True)
        print(f"  S1: {n}")

        # ── PASS 8: TECTONIC S2,S3 — base octave + tightening ────
        print("\nPASS 8: TECTONIC S2/S3 — building")
        t2 = []
        for r in range(4):
            t2.extend(tectonic_arp_4bar(r * 4, octave_shift=0, density="8th"))
        n = write_midi_clip(ch, T["TECTONIC"], 2, 16.0, "mid_arp_base", t2, breathe=True)
        print(f"  S2: {n}")
        # S3 — denser, 16th feel
        t3 = []
        for r in range(4):
            t3.extend(tectonic_arp_4bar(r * 4, octave_shift=0, density="16th"))
        n = write_midi_clip(ch, T["TECTONIC"], 3, 16.0, "mid_arp_riser", t3,
                              pull_back=True, breathe=True)
        print(f"  S3: {n}")

        # ── PASS 9: TECTONIC S4,S6,S7,S9 — full octave during drops ─
        print("\nPASS 9: TECTONIC S4,S6,S7,S9 — full power")
        for slot, length, oct_shift, dens, tag in [
            (4, 32.0, 12, "16th", "mid_arp_drop_ragga"),
            (6, 16.0, 12, "16th", "mid_arp_rebuild"),
            (7, 32.0, 12, "16th", "mid_arp_rotterdam"),
            (9, 32.0,  0, "16th", "mid_arp_breakcore"),    # base octave for chaos
        ]:
            t = []
            n_reps = int(length / 16)
            for r in range(n_reps * 4):
                t.extend(tectonic_arp_4bar(r * 4, octave_shift=oct_shift, density=dens))
            n = write_midi_clip(ch, T["TECTONIC"], slot, length, tag, t,
                                  pull_back=True, breathe=False)
            print(f"  S{slot}: {n}")

        # ── PASS 10: STAB — ragga organ chord stabs ──────────────
        print("\nPASS 10: STAB chord stabs across the build")
        # Write a soft sustained intro pad on STAB slot 0 (since TECTONIC
        # is muted during intro for the sub-free open). Long held chords
        # at low velocity create the patient breath-y opening.
        if T["STAB"] is not None:
            intro_pad = []
            chord = [60, 63, 67]   # Cm minor triad
            # 4 chord changes over 16 bars — each held 4 bars
            for bar_idx, root_off in enumerate([0, 0, -2, 0]):  # Cm, Cm, Bbm, Cm
                bs = bar_idx * 4 * 4   # 16 beats per bar block? wait 4*4=16
                # Actually bs is in beats; each chord block is 4 bars = 16 beats
                bs = bar_idx * 16
                for p in chord:
                    intro_pad.append((p + root_off, bs, 16.0, 55))   # super soft pad
            n = write_midi_clip(ch, T["STAB"], 0, 16.0, "intro_pad", intro_pad,
                                  pull_back=False, breathe=True)
            print(f"  S0: {n} (intro pad)")
        for slot, length, root_shift, tag in [
            (1, 16.0,  0, "stab_intro"),       # Cm
            (2, 16.0, -2, "stab_build"),       # Bbm (down a tone — tension)
            (3, 16.0, -1, "stab_riser"),       # Bm (semitone tension before D1 resolution)
            (4, 32.0,  0, "stab_drop_ragga"),  # back to Cm
            (6, 16.0,  3, "stab_rebuild"),     # Ebm (up a min3rd — different tonal centre for D2)
            (7, 32.0,  0, "stab_rotterdam"),   # back to Cm
            (9, 32.0, -1, "stab_breakcore"),   # Bm (uneasy semitone tension during chaos)
            (11, 16.0, 0, "stab_outro_pad"),   # Cm sustained — gentle harmonic close
        ]:
            if slot == 11:
                # Outro: long sustained chords, very soft
                outro_chord = [60, 63, 67]
                stb = []
                for bar_idx in range(4):
                    bs = bar_idx * 4
                    for p in outro_chord:
                        stb.append((p, bs, 4.0, max(35, 60 - bar_idx * 6)))
            else:
                stb = []
                for r in range(int(length / 4)):
                    stb.extend(stab_chord_4bar(r * 4, root_shift))
            n = write_midi_clip(ch, T["STAB"], slot, length, tag, stb,
                                  pull_back=(slot in (3, 6)),    # tighten before drops
                                  breathe=(slot != 11))
            print(f"  S{slot}: {n}")

        # ── PASS 11: VOX YO ("yo!") — at scene boundaries during build ─
        print("\nPASS 11: VOX YO triggers")
        if T["VOX YO"] is not None:
            for slot, length, hits in [
                (1, 16.0, [0.0, 8.0]),
                (2, 16.0, [0.0, 4.0, 8.0, 12.0]),
                (3, 16.0, [0.0, 4.0, 8.0, 12.0, 14.0, 15.0]),  # tighten into drop
                (6, 16.0, [0.0, 4.0, 8.0, 12.0, 14.0, 15.0]),
                (7, 32.0, [0.0, 16.0]),                        # join impact stack
                (9, 32.0, [0.0, 8.0, 16.0, 24.0]),             # breakcore stabs
            ]:
                n = write_midi_clip(ch, T["VOX YO"], slot, length, f"yo_{slot}",
                                      vocal_pulse(0, hits), pull_back=False)
                print(f"  S{slot}: {n}")

        # ── PASS 12: VOX BIG ("big up!") — at drop transitions ───
        print("\nPASS 12: VOX BIG at drop boundaries")
        if T["VOX BIG"] is not None:
            for slot, length, hits in [
                (4, 32.0, [0.0]),                        # at impact of D1
                (7, 32.0, [0.0, 16.0]),                  # twice in Rotterdam
                (9, 32.0, [0.0, 8.0, 16.0, 24.0]),       # multiple in breakcore
            ]:
                n = write_midi_clip(ch, T["VOX BIG"], slot, length, f"bigup_{slot}",
                                      vocal_pulse(0, hits), pull_back=False)
                print(f"  S{slot}: {n}")

        # ── PASS 13: VOX SEL ("selassie i!") — D2 + breakcore ─────
        print("\nPASS 13: VOX SEL during D2 + breakcore")
        if T["VOX SEL"] is not None:
            sel_hits_d2 = [0.0, 4.0, 8.0, 12.0, 16.0, 20.0, 24.0, 28.0]
            n = write_midi_clip(ch, T["VOX SEL"], 7, 32.0, "selassie_rotterdam",
                                  vocal_pulse(0, sel_hits_d2, vel=120), pull_back=False)
            print(f"  S7: {n}")
            sel_hits_bc = [0.0, 8.0, 16.0, 24.0]
            n = write_midi_clip(ch, T["VOX SEL"], 9, 32.0, "selassie_breakcore",
                                  vocal_pulse(0, sel_hits_bc, vel=110), pull_back=False)
            print(f"  S9: {n}")

        sess.snapshot("after-compose")
        print("\n" + "=" * 60)
        print("composition complete — now run:")
        print("  python scripts/pass_freq_separation.py")
        print("  python scripts/pass_clip_fades.py")
        print("  python scripts/fix_subbonk_loop.py")
        print("  python scripts/arrangement_record.py 1")


if __name__ == "__main__":
    main()
