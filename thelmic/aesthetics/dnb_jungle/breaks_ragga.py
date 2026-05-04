"""Native MIDI break patterns — dub / ragga / dancehall flavoured, designed
for full drum-rack kits like Riddim Rager Kit or Selectah Kit (16+ pads).

Each generator returns a list of {pitch, start_time, duration, velocity}
notes spanning 16 beats (4 bars). All swing-friendly — designed to be
auditioned with the 'Swing Reggae' groove applied.

Pad mapping is the General MIDI Drum Rack convention plus the Riddim
Rager extras (toms on 43/45/47, blips on 48/50, ride on 51, alt kick
+ snare on 41/40, clap on 39, perc on 37, alt crash on 49).

Use:
    from thelmic.aesthetics.dnb_jungle.breaks_ragga import (
        BREAK_PATTERNS, CLIP_LENGTH_BEATS,
    )
    notes = BREAK_PATTERNS["rolling_dub_ragga"]()
"""
from __future__ import annotations

# ---- pad map (Riddim Rager / Selectah-compatible) ----------------------
KICK        = 36     # main kick
PERC        = 37
SNARE       = 38     # main snare
CLAP        = 39
SNARE_JAZZ  = 40
KICK_HARD   = 41     # alt heavy kick (Burned / 808 Huge)
HAT_C       = 42
TOM_LO      = 43
CRASH       = 44
TOM_MID     = 45
HAT_O       = 46
TOM_HI      = 47
BLIP_LO     = 48
CRASH_HARD  = 49
BLIP_HI     = 50
RIDE        = 51

CLIP_LENGTH_BEATS = 16.0


def _note(pitch: int, t: float, dur: float, vel: int) -> dict:
    """Build a note dict in the post-restart `start_time` schema."""
    return {
        "pitch": int(pitch),
        "start_time": float(t),
        "duration": float(dur),
        "velocity": float(vel),
    }


# ---- the centerpiece ---------------------------------------------------

def rolling_dub_ragga() -> list[dict]:
    """The main attraction. Rolling dub/ragga break:
      - half-time bones (kick on 1, snare on 3) for that dub gravity
      - 16th-note hat carpet with skipped &-of-3 (the ragga hat skip)
      - syncopated rim / perc filling the kick-snare gaps
      - rolling tom flurry on bar 4 leading into the next loop
      - open hat breath on the &-of-4 each bar
    """
    notes: list[dict] = []
    # bars 0..3 — basic dub stepper
    for bar in range(4):
        b0 = bar * 4
        # kick: heavy on 1, push on 2.5 every other bar
        notes.append(_note(KICK,        b0 + 0.0, 0.4, 118))
        if bar % 2 == 1:
            notes.append(_note(KICK_HARD, b0 + 2.5, 0.3, 102))
        # snare on 3, jazz snare ghost on 2.75 + 3.5 (the dub flavour)
        notes.append(_note(SNARE,       b0 + 2.0, 0.3, 110))
        notes.append(_note(SNARE_JAZZ,  b0 + 1.75, 0.15, 60))   # ghost
        notes.append(_note(SNARE_JAZZ,  b0 + 3.25, 0.15, 70))   # late ghost
        # 16th hat carpet but SKIP the &-of-3 (beat 2.5 → 2.75 silence)
        for s in range(16):
            t = s * 0.25
            if abs(t - 2.5) < 0.01 or abs(t - 2.75) < 0.01:
                continue          # the ragga hat skip
            v = 75 if s % 2 == 0 else 55
            if s % 4 == 0: v += 8
            notes.append(_note(HAT_C, b0 + t, 0.0625, v))
        # open hat breath on &-of-4
        notes.append(_note(HAT_O, b0 + 3.5, 0.5, 90))
        # perc filler on the &-of-1 every bar (the rim-tap groove)
        notes.append(_note(PERC, b0 + 0.5, 0.15, 78))

    # bar 4 special: rolling tom flurry leading into the loop
    # (bar index 3 is the last bar; replace its later half with a fill)
    # remove HAT_C and SNARE_JAZZ events past beat 13 to make room
    notes = [n for n in notes if not (n["start_time"] >= 13.5
              and n["pitch"] in (HAT_C, SNARE_JAZZ))]
    fill_starts = [13.5, 13.75, 14.0, 14.25, 14.5, 14.75, 15.0, 15.25, 15.5, 15.75]
    fill_pads   = [TOM_HI, TOM_MID, TOM_LO, TOM_HI, TOM_MID,
                   TOM_LO, TOM_HI, SNARE_JAZZ, SNARE, SNARE_JAZZ]
    for t, pad in zip(fill_starts, fill_pads):
        v = 80 + int((t - 13.5) * 18)   # crescendo into the loop
        notes.append(_note(pad, t, 0.18, min(120, v)))
    # crash splash hitting on the upcoming 1
    notes.append(_note(CRASH, 0.0, 1.5, 105))
    return notes


# ---- supporting variants -----------------------------------------------

def stepper_half_time() -> list[dict]:
    """Sparse half-time stepper — kick 1, snare 3, ride on 8ths,
    open hat breath on 4&. Designed to sit UNDER the rolling break in
    A/B layering, or as a quieter scene's drum bed."""
    notes: list[dict] = []
    for bar in range(4):
        b0 = bar * 4
        notes.append(_note(KICK,  b0 + 0.0, 0.4, 110))
        notes.append(_note(SNARE, b0 + 2.0, 0.3, 105))
        # ride on 8ths
        for s in range(8):
            v = 70 if s % 2 == 0 else 55
            notes.append(_note(RIDE, b0 + s * 0.5, 0.25, v))
        notes.append(_note(HAT_O, b0 + 3.5, 0.5, 80))
        # snare ghost on 2.75 every other bar
        if bar % 2 == 0:
            notes.append(_note(SNARE_JAZZ, b0 + 2.75, 0.15, 65))
    return notes


def skank_carpet() -> list[dict]:
    """16th-note carpet with snare-on-the-& syncopation. The skank
    pattern is the closed hats, NOT chord stabs — drum-only skank.
    Lighter than rolling_dub_ragga, more momentum."""
    notes: list[dict] = []
    for bar in range(4):
        b0 = bar * 4
        # Hat carpet — 16ths with accent on every 8th
        for s in range(16):
            v = 78 if s % 2 == 0 else 58
            if s % 4 == 0: v += 10
            notes.append(_note(HAT_C, b0 + s * 0.25, 0.0625, v))
        # Kick: 1 + bar-end pickup
        notes.append(_note(KICK, b0 + 0.0, 0.3, 110))
        if bar < 3:
            notes.append(_note(KICK, b0 + 3.75, 0.15, 90))
        # Snare: on the & (1.5 / 3.5) — the skank
        notes.append(_note(SNARE, b0 + 1.5, 0.25, 105))
        notes.append(_note(SNARE, b0 + 3.5, 0.25, 105))
        # Clap doubles snare on the second skank for thickness
        notes.append(_note(CLAP, b0 + 3.5, 0.2, 90))
    return notes


def dub_minimal_space() -> list[dict]:
    """Sparse dub — kick on 1 only, snare on 3, lots of space for delay
    tails to sound. Use when reverb / dub fx are dominant."""
    notes: list[dict] = []
    for bar in range(4):
        b0 = bar * 4
        notes.append(_note(KICK,  b0 + 0.0, 0.4, 108))
        notes.append(_note(SNARE, b0 + 2.0, 0.3, 100))
        # Single closed hat on the &-of-4 only
        notes.append(_note(HAT_C, b0 + 3.5, 0.125, 75))
        # Once per 2 bars, a single perc tap on 2.5 to keep the pulse
        if bar % 2 == 1:
            notes.append(_note(PERC, b0 + 2.5, 0.15, 70))
    # Single crash splash on the 1 of bar 1 only
    notes.insert(0, _note(CRASH, 0.0, 1.5, 95))
    return notes


def double_time_dnb() -> list[dict]:
    """Drum & bass / jungle intensity — 32nd hat carpet, syncopated
    kicks, busy ghost snares. At project tempo 87 bpm this reads as
    174 bpm dnb feel. The 'fast' variant for drop scenes."""
    notes: list[dict] = []
    for bar in range(4):
        b0 = bar * 4
        # 32nd-note hat carpet
        for s in range(32):
            v = 72 if s % 2 == 0 else 52
            if s % 4 == 0: v += 8
            if s % 8 == 0: v += 6
            notes.append(_note(HAT_C, b0 + s * 0.125, 0.0625, v))
        # Syncopated kicks (amen-flavour)
        for t, v in [(0.0, 115), (1.75, 100), (2.5, 105)]:
            notes.append(_note(KICK, b0 + t, 0.2, v))
        # Snares: on 2 + 4 plus ghosts
        notes.append(_note(SNARE,      b0 + 1.0, 0.18, 110))
        notes.append(_note(SNARE_JAZZ, b0 + 1.875, 0.1, 60))
        notes.append(_note(SNARE,      b0 + 3.0, 0.18, 110))
        notes.append(_note(SNARE_JAZZ, b0 + 3.625, 0.1, 70))
        # Open-hat breath on the &-of-4
        notes.append(_note(HAT_O, b0 + 3.5, 0.25, 88))
    return notes


# ---- registry ----------------------------------------------------------

BREAK_PATTERNS: dict[str, callable] = {
    "rolling_dub_ragga": rolling_dub_ragga,
    "stepper_half_time": stepper_half_time,
    "skank_carpet":      skank_carpet,
    "dub_minimal_space": dub_minimal_space,
    "double_time_dnb":   double_time_dnb,
}

BREAK_DESCRIPTIONS = {
    "rolling_dub_ragga": "centerpiece — half-time bones, ragga hat skip, tom-flurry roll-out",
    "stepper_half_time": "sparse stepper bed — kick 1, snare 3, ride 8ths, hat breath 4&",
    "skank_carpet":      "16th hat carpet, snare-on-& skank, clap thickening",
    "dub_minimal_space": "kick 1 + snare 3 only — leaves room for delay tails",
    "double_time_dnb":   "32nd hat carpet, syncopated kicks, busy ghosts — dnb intensity",
}
