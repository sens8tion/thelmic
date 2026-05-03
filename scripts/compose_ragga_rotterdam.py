"""Compose a ragga → Rotterdam arc into the session-view MIDI clips.

Since clip envelopes are silently broken on audio params and we can't
rely on automation tonight, every "tightening" / "filtering" / dynamic
gesture is baked directly into the MIDI patterns themselves:

  - Velocity ramps (rising / pulling-back) → perceived volume curves
  - Note-density acceleration (16th → 32nd → 64th) → tightening hats
  - Pitch-octave shifts written as note-pitch jumps → filter-style sweeps
  - Pre-impact thinning + sacred-impact unison → drop hits land harder
  - Negative-space gaps written as note rests → "void" before impact

Multi-pass build (each pass writes a layer of the trick to a track):

  PASS 1  HARDKIT — ragga drum pattern (drop 1, slot 4)
  PASS 2  HARDKIT — Rotterdam gabber (drop 2, slot 7)
  PASS 3  HARDKIT — breakcore peak (slot 9)
  PASS 4  HARDKIT — quiet outro (slot 11)
  PASS 5  HARDKIT — anticipation slots 3, 6, 13 (handled by arrangement_record)
  PASS 6  SUBBONK — ragga sub then Rotterdam wall
  PASS 7  TECTONIC — mid-bass arpeggios with octave shifts
  PASS 8  STAB — ragga organ stabs synced to snare

After this, run scripts/arrangement_record.py 1 to print the take.
"""
from __future__ import annotations
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("LIVE_CHANNEL_ENABLED", "1")
from thelmic.mediated_session import open_session
from thelmic.agent_helpers import (
    find_track, breathe_velocity, pull_back_before_drop, to_clip_notes,
)

# Drum pitches (GM)
KICK, SNARE, HAT_C, HAT_O, RIDE, CRASH = 36, 38, 42, 46, 51, 49
LOW_TOM, HI_TOM, HAND_CLAP = 41, 50, 39

# Bass synth root note (C minor / A minor — adjust to fit session key)
BASS_ROOT = 36     # low C
BASS_OCT_UP = 48   # +1 octave

# Mid-bass arp notes (cycle of 4 — minor pentatonic-ish)
TECTONIC_ARP = [36, 39, 41, 36]   # C, Eb, F, C


# ----------------------------------------------------------------------
# HARDKIT patterns
# ----------------------------------------------------------------------

def ragga_jungle_4bar(offset=0.0, hat_density="16th"):
    """Ragga-jungle break with skipping kick + ghost snares.
    hat_density: '16th' / '32nd' — 32nd doubles the hat density."""
    notes = []
    for bar in range(4):
        bs = bar * 4 + offset
        # Skipping kick
        notes.append((KICK, bs + 0.0, 0.40, 118))
        notes.append((KICK, bs + 2.5, 0.40, 105))
        # Snare backbeat + ghosts
        notes.append((SNARE, bs + 1.0, 0.30, 110))
        notes.append((SNARE, bs + 3.0, 0.30, 115))
        notes.append((SNARE, bs + 3.75, 0.18,  72))    # late ghost
        # Ride accents on alternating bars (ragga feel)
        if bar % 2 == 1:
            notes.append((RIDE, bs + 0.0, 0.60, 95))
            notes.append((RIDE, bs + 2.0, 0.50, 88))
        # Hats
        if hat_density == "16th":
            for i in range(16):
                t = bs + i * 0.25
                vel = 92 if i % 4 == 0 else 65 if i % 2 == 0 else 72
                notes.append((HAT_C, t, 0.16, vel))
        else:  # 32nd
            for i in range(32):
                t = bs + i * 0.125
                vel = 88 - (i % 8) * 3
                notes.append((HAT_C, t, 0.08, vel))
    return notes


def rotterdam_gabber_4bar(offset=0.0, double_time=False, hat_tightening=False):
    """Hard Rotterdam — 4 (or 8) on the floor distorted-kick implied by vel127.
    hat_tightening: ramp hats from 16th → 32nd over the 4 bars."""
    notes = []
    for bar in range(4):
        bs = bar * 4 + offset
        # Kick: 4-on-floor or 8-on-floor (double-time)
        n_kicks = 8 if double_time else 4
        rate = 0.5 if double_time else 1.0
        for k in range(n_kicks):
            t = bs + k * rate
            vel = 127 if (k * rate) % 1 == 0 else 122
            notes.append((KICK, t, 0.20 if double_time else 0.30, vel))
        # Snare on 2 and 4 — Rotterdam slam
        notes.append((SNARE, bs + 1.0, 0.25, 122))
        notes.append((SNARE, bs + 3.0, 0.25, 122))
        # Hats — tightening or steady
        if hat_tightening:
            # bars 0..1: 16th, bars 2..3: 32nd (tightening)
            if bar < 2:
                step = 0.25; n = 16
            else:
                step = 0.125; n = 32
        else:
            step = 0.25; n = 16
        for i in range(n):
            t = bs + i * step
            vel = 90 if i % 4 == 0 else 68
            notes.append((HAT_C, t, 0.10, vel))
        # Crash on bar 0 of every section
        if bar == 0:
            notes.append((CRASH, bs + 0.0, 2.0, 115))
    return notes


def breakcore_4bar(offset=0.0):
    """Chaotic 16th-note kicks throughout, snare flams every bar."""
    notes = []
    for bar in range(4):
        bs = bar * 4 + offset
        # 16th kicks all bar
        for i in range(16):
            t = bs + i * 0.25
            vel = 124 if i % 4 == 0 else 110 if i % 2 == 0 else 115
            notes.append((KICK, t, 0.10, vel))
        # Snare flams on 2 and 4 with grace notes
        notes.append((SNARE, bs + 0.96, 0.06, 80))
        notes.append((SNARE, bs + 1.00, 0.20, 118))
        notes.append((SNARE, bs + 2.96, 0.06, 80))
        notes.append((SNARE, bs + 3.00, 0.20, 118))
        # 32nd hats over the top
        for i in range(32):
            t = bs + i * 0.125
            vel = 78 + (i % 4) * 4
            notes.append((HAT_C, t, 0.06, vel))
    return notes


def quiet_outro_4bar(offset=0.0):
    """Sparse half-time skeleton — just kick on 1 + ride wash."""
    notes = []
    for bar in range(4):
        bs = bar * 4 + offset
        # Single kick, decreasing vel each bar
        kvel = 95 - bar * 12
        notes.append((KICK, bs + 0.0, 0.40, max(35, kvel)))
        # Ride sustained
        notes.append((RIDE, bs + 0.0, 4.0, 70 - bar * 8))
        # Single snare ghost on bar 2 and 4
        if bar == 1 or bar == 3:
            notes.append((SNARE, bs + 2.5, 0.20, 50 - bar * 5))
    return notes


# ----------------------------------------------------------------------
# SUBBONK patterns
# ----------------------------------------------------------------------

def sub_ragga_4bar(offset=0.0):
    """Ragga sub — long-held root with octave skip on backbeat."""
    notes = []
    for bar in range(4):
        bs = bar * 4 + offset
        notes.append((BASS_ROOT, bs + 0.0, 1.4, 110))      # root on 1
        notes.append((BASS_ROOT, bs + 2.5, 1.4, 100))      # skipping kick echo
        # Octave-up flick on 3.75 for ragga slide feel
        notes.append((BASS_OCT_UP, bs + 3.75, 0.20, 85))
    return notes


def sub_rotterdam_4bar(offset=0.0, double_time=False):
    """Sub locked to gabber kick — root note every kick hit."""
    notes = []
    n_hits = 32 if double_time else 16
    rate = 0.5 if double_time else 1.0
    for bar in range(4):
        bs = bar * 4 + offset
        for k in range(4 if not double_time else 8):
            t = bs + k * rate
            notes.append((BASS_ROOT, t, 0.4, 118))
    return notes


# ----------------------------------------------------------------------
# TECTONIC mid-bass arpeggio with octave shifts
# ----------------------------------------------------------------------

def tectonic_arp_4bar(offset=0.0, octave_shift=0, density="8th"):
    """Mid-bass arp cycling 4 notes. octave_shift in semitones (12 = +1 oct)."""
    notes = []
    step = 0.5 if density == "8th" else 0.25
    n_per_bar = int(4 / step)
    for bar in range(4):
        bs = bar * 4 + offset
        for i in range(n_per_bar):
            t = bs + i * step
            pitch = TECTONIC_ARP[i % len(TECTONIC_ARP)] + octave_shift
            vel = 95 if i % 4 == 0 else 80
            notes.append((pitch, t, step * 0.85, vel))
    return notes


# ----------------------------------------------------------------------
# Writers — clear + create + add to a slot
# ----------------------------------------------------------------------

_TRACK_IS_MIDI_CACHE = {}

def _track_is_midi(ch, track):
    if track in _TRACK_IS_MIDI_CACHE:
        return _TRACK_IS_MIDI_CACHE[track]
    info = ch.get_track_info(track).result(timeout=3)
    is_midi = bool(info.get("is_midi_track"))
    _TRACK_IS_MIDI_CACHE[track] = is_midi
    return is_midi


def write_clip(ch, track, slot, length_beats, name, notes_quads,
                tighten_at_end=True, breathe=False):
    """Write a fresh MIDI clip with optional tightening + breathing.

    notes_quads: list of (pitch, start_beat, duration, velocity).
    tighten_at_end: pull-back velocity ramp over last 4 beats (preserves any
                    note exactly at length-0.125 = the impact).
    breathe: sinusoidal velocity breathing over the steady section.

    No-ops on audio tracks (returns -1).
    """
    if not _track_is_midi(ch, track):
        return -1
    if breathe:
        notes_quads = breathe_velocity(notes_quads, amplitude=8, period_beats=8.0)
    if tighten_at_end:
        # Drop is at length_beats - 0.125 (sacred); pull back over last 4 beats
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
# Main composition pipeline
# ----------------------------------------------------------------------

def main():
    with open_session(name="compose-ragga-rotterdam",
                      expected_tracks=["HARDKIT", "SUBBONK", "TECTONIC"]) as sess:
        ch = sess.raw_ch
        T_HK   = find_track(ch, "HARDKIT")
        T_SUB  = find_track(ch, "SUBBONK")
        T_TECT = find_track(ch, "TECTONIC")
        if T_HK is None or T_SUB is None or T_TECT is None:
            print("missing one of HARDKIT/SUBBONK/TECTONIC — abort"); return
        sess.snapshot("before-compose")

        # ── PASS 1: HARDKIT slot 4 — ragga drop 1 ───────────────────
        print("\nPASS 1: HARDKIT S4 — ragga jungle drop (32 bars, tightening)")
        ragga = []
        # 6 bars of standard ragga break
        for r in range(6):
            ragga.extend(ragga_jungle_4bar(r * 4, hat_density="16th"))
        # Then 2 bars with 32nd hats — tightening before scene boundary
        ragga.extend(ragga_jungle_4bar(24, hat_density="32nd"))
        # Final impact unison (kick+snare+crash) at clip end - 0.125
        impact_t = 32 - 0.125
        ragga.append((KICK,  impact_t, 0.20, 127))
        ragga.append((SNARE, impact_t, 0.20, 127))
        ragga.append((CRASH, impact_t, 4.00, 127))
        n = write_clip(ch, T_HK, 4, 32.0, "drop_ragga", ragga, breathe=True)
        print(f"  wrote {n} notes")

        # ── PASS 2: HARDKIT slot 7 — Rotterdam gabber ──────────────
        print("\nPASS 2: HARDKIT S7 — Rotterdam gabber (32 bars, hat tightening)")
        gabber = []
        # 4 bars 16th hats, 4 bars hat tightening
        gabber.extend(rotterdam_gabber_4bar(0,  double_time=False, hat_tightening=False))
        gabber.extend(rotterdam_gabber_4bar(16, double_time=False, hat_tightening=True))
        # Last 8 bars: double-time kick (8-on-floor) — peak Rotterdam
        gabber.extend(rotterdam_gabber_4bar(28, double_time=True,  hat_tightening=True))
        impact_t = 32 - 0.125
        gabber.append((KICK,  impact_t, 0.20, 127))
        gabber.append((CRASH, impact_t, 4.00, 127))
        n = write_clip(ch, T_HK, 7, 32.0, "drop_rotterdam", gabber, breathe=False)
        print(f"  wrote {n} notes")

        # ── PASS 3: HARDKIT slot 9 — breakcore peak ────────────────
        print("\nPASS 3: HARDKIT S9 — breakcore peak (32 bars chaos)")
        bc = []
        for r in range(8):
            bc.extend(breakcore_4bar(r * 4))
        n = write_clip(ch, T_HK, 9, 32.0, "breakcore_peak", bc,
                        tighten_at_end=False, breathe=False)
        print(f"  wrote {n} notes")

        # ── PASS 4: HARDKIT slot 11 — quiet outro ──────────────────
        print("\nPASS 4: HARDKIT S11 — quiet outro (16 bars sparse)")
        outro = []
        for r in range(4):
            outro.extend(quiet_outro_4bar(r * 4))
        n = write_clip(ch, T_HK, 11, 16.0, "outro_quiet", outro,
                        tighten_at_end=False, breathe=False)
        print(f"  wrote {n} notes")

        # ── PASS 5: HARDKIT anticipation slots — handled by arrangement_record
        print("\nPASS 5: HARDKIT S3/S6/S13 — anticipation (skipped, will run via arrangement_record)")

        # ── PASS 6: SUBBONK (skipped if audio track) ─────────────
        print("\nPASS 6: SUBBONK lanes")
        if _track_is_midi(ch, T_SUB):
            sub4 = []
            for r in range(8):
                sub4.extend(sub_ragga_4bar(r * 4))
            n = write_clip(ch, T_SUB, 4, 32.0, "sub_ragga", sub4)
            print(f"  S4: {n}")
            sub7 = []
            for r in range(7):
                sub7.extend(sub_rotterdam_4bar(r * 4))
            sub7.extend(sub_rotterdam_4bar(28, double_time=True))
            n = write_clip(ch, T_SUB, 7, 32.0, "sub_rotterdam", sub7,
                            tighten_at_end=False)
            print(f"  S7: {n}")
            sub9 = []
            for r in range(8):
                for i in range(8):
                    sub9.append((BASS_ROOT, r*4 + i*0.5, 0.3, 100 + (i % 3) * 8))
            n = write_clip(ch, T_SUB, 9, 32.0, "sub_breakcore", sub9,
                            tighten_at_end=False)
            print(f"  S9: {n}")
        else:
            print("  SUBBONK is audio — relying on its existing sample clips")

        # ── PASS 7: TECTONIC mid-bass with octave shifts ──────────
        print("\nPASS 7: TECTONIC mid-bass arps (octave-shifted across sections)")
        # S1 — octave-down arp (ragga build)
        tect1 = tectonic_arp_4bar(0,  octave_shift=-12, density="8th")
        for r in range(1, 4):
            tect1.extend(tectonic_arp_4bar(r * 4, octave_shift=-12, density="8th"))
        n = write_clip(ch, T_TECT, 1, 16.0, "mid_arp_low", tect1,
                        tighten_at_end=False, breathe=True)
        print(f"  S1: {n}")
        # S2 — base octave (lifting)
        tect2 = []
        for r in range(4):
            tect2.extend(tectonic_arp_4bar(r * 4, octave_shift=0, density="8th"))
        n = write_clip(ch, T_TECT, 2, 16.0, "mid_arp_base", tect2,
                        tighten_at_end=False, breathe=True)
        print(f"  S2: {n}")
        # S4 — full octave-up during drop 1
        tect4 = []
        for r in range(8):
            tect4.extend(tectonic_arp_4bar(r * 4, octave_shift=12, density="16th"))
        n = write_clip(ch, T_TECT, 4, 32.0, "mid_arp_drop", tect4,
                        tighten_at_end=False, breathe=False)
        print(f"  S4: {n}")
        # S7 — gabber territory: dense + extreme
        tect7 = []
        for r in range(8):
            tect7.extend(tectonic_arp_4bar(r * 4, octave_shift=12, density="16th"))
        n = write_clip(ch, T_TECT, 7, 32.0, "mid_arp_rotterdam", tect7,
                        tighten_at_end=False, breathe=False)
        print(f"  S7: {n}")

        # ── PASS 8: STAB — ragga-organ stabs synced to snare ──────
        T_STAB = find_track(ch, "STAB")
        if T_STAB is not None:
            print("\nPASS 8: STAB ragga organ stabs")
            stab_root = 60   # middle C
            stab_chord = [stab_root, stab_root + 3, stab_root + 7]   # minor triad
            stab2 = []
            for r in range(4):
                bs = r * 4
                # Stab on every backbeat (beats 1 and 3 — i.e. snare hits)
                for beat in (1.0, 3.0):
                    for p in stab_chord:
                        stab2.append((p, bs + beat, 0.3, 100))
                # Plus an off-beat ghost on 3.75 (ragga feel)
                for p in stab_chord:
                    stab2.append((p, bs + 3.75, 0.15, 75))
            n = write_clip(ch, T_STAB, 2, 16.0, "stab_ragga", stab2,
                            tighten_at_end=False, breathe=True)
            print(f"  S2: {n}")

        sess.snapshot("after-compose")
        print("\n" + "=" * 56)
        print("composition complete — now run:")
        print("  python scripts/arrangement_record.py 1")
        print("(arrangement_record will auto-apply the anticipation fills")
        print(" to S3/S6/S13 before the print)")


if __name__ == "__main__":
    main()
