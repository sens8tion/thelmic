"""JUNGLE ROWS - playable rows on the jungle scene rules (tracks/2026-09-16_jungle_scene_rules.md).

Three sections, each a pre-drop row and two drop rows. A section holds an identity - the spine's voice,
its signature hits, its main break, its 16th carrier, its sub - and every hit inside it has a CHANCE
(Live's note probability), so each pass deals a fresh bar from the section's distribution rather than
repeating a loop. Between sections everything turns over together.

  rows (Live)  section   spine (1, 2, 4, "and" of 3)   main break           16th carrier          sub
  1-3          arrivals  SPINE-TINGLER (Bonzo Kit)     AMEN-DMENT (Amen)    THROW-UP: Amen hats   F-HOLE
  9-11         court     SPINAL-TAP (Vintage Madman)   COLD-CUTS (Cold Sweat) TOPSOIL: Apache     SUB-POENA
  17-19        print     SPINELESS (909, two-step)     CHOPPER (Apache)     SWEAT-SHOP: Cold Sweat SUB-LIMINAL

- Spine hits play at 100% (the "and" of 3 at the section's chance; the two-step always).
- The main break fills every other 16th at the chance a contrasting reference section shows there: its
  favoured positions are the signature hits. Slices are dealt per bar (A-B-C-D in the 4-bar group).
- Variant pads come in at low chance: pitched snares and kick, a 32nd stutter fill on bar 4, reversed and
  stretched hits (scripts/jungle_kits.py builds them).
- Carriers play the 8ths always and the "e"s and "a"s at 70-80%.
- The sub is in F# minor on the fundamental F#0: struck at the front of the bar, mostly repeats and steps,
  about one change a bar (half under the two-step), phrases dropping to a low "dum" and leaving a gap.
- Only clips whose notes differ are written; playback is never stopped for a clip write.

    python scripts/jungle_rows.py --dry-run
    python scripts/jungle_rows.py [--rows 4,5] [--lanes COLD-CUTS] [--check-voices]
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time

os.environ.setdefault("LIVE_CHANNEL_ENABLED", "1")
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(SCRIPTS_DIR))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from jungle_compose import AMEN, SWEAT, TOP  # noqa: E402

BARS = 4
LEN = BARS * 4.0
VEL = {"kick": 118, "snare": 112, "snare_soft": 96, "ghost": 82, "hat": 90, "bongo": 100, "conga": 104}


def lane(brk, bar_maps, *, soften_off8=14, cap=None, accent_slots=(), accent=0):
    """[{16th slot: slice}] per bar -> notes. Each slice starts exactly on its 16th and rings until the
    next hit in the lane (or its own end); off-8th 16ths sit back, `accent_slots` push forward."""
    hits = sorted((b * 4 + k * 0.25, s) for b, m in enumerate(bar_maps) for k, s in m.items())
    out = []
    for j, (t, s) in enumerate(hits):
        nxt = hits[j + 1][0] if j + 1 < len(hits) else LEN
        dur = min(brk.natural(s), nxt - t) - 0.012
        if cap:
            dur = min(dur, cap)
        slot = round(t * 4) % 16
        vel = max(VEL.get(p, 96) for p in brk.parts[s])
        if slot % 2:
            vel -= soften_off8
        if slot in accent_slots:
            vel += accent
        out.append((36 + s, round(t, 4), round(max(dur, 0.05), 4), max(1, min(127, vel))))
    return out


# ---------------------------------------------------------------- chops (Amen kit, slice indices)
CHOP_A = [  # the approved WAITING ROOM chop
    {0: 0, 2: 1, 4: 2, 6: 3, 7: 13, 8: 5, 10: 7, 12: 21, 14: 22, 15: 23},
    {0: 0, 3: 13, 4: 15, 6: 16, 8: 6, 9: 12, 11: 18, 12: 2, 14: 20, 15: 10},
    {0: 25, 1: 3, 2: 11, 4: 17, 5: 8, 7: 7, 8: 5, 10: 20, 12: 9, 13: 13, 14: 18},
    {0: 0, 2: 16, 4: 21, 6: 1, 7: 22, 8: 19, 10: 12, 12: 15, 13: 23, 14: 24, 15: 4},
]
CHOP_B = [  # busier ghosts, the second kick pushed around
    {0: 0, 1: 13, 2: 3, 4: 2, 5: 13, 6: 12, 8: 16, 10: 7, 11: 14, 12: 21, 14: 5, 15: 23},
    {0: 0, 3: 6, 4: 15, 6: 1, 7: 22, 8: 18, 9: 19, 10: 20, 12: 9, 13: 13, 14: 8, 15: 24},
    {0: 25, 2: 1, 4: 17, 5: 11, 6: 3, 8: 5, 9: 12, 11: 13, 12: 2, 14: 7, 15: 23},
    {0: 0, 1: 3, 2: 12, 4: 21, 6: 16, 7: 14, 8: 19, 10: 0, 11: 13, 12: 15, 13: 24, 14: 4, 15: 9},
]
CHOP_C = [  # no break kicks: the two-step kick takes the floor; sparse, syncopated
    {2: 3, 4: 2, 7: 13, 8: 5, 11: 14, 12: 21, 14: 22},
    {1: 16, 4: 15, 6: 6, 8: 18, 10: 13, 12: 9, 15: 23},
    {3: 13, 4: 17, 6: 8, 9: 19, 12: 2, 13: 13, 14: 10},
    {2: 22, 4: 21, 7: 11, 8: 3, 10: 23, 12: 15, 14: 24, 15: 4},
]

# ---------------------------------------------------------------- 16th carriers
AMEN_HATS = [3, 5, 8, 16, 18, 22]
AMEN_SWAPS = [{}, {7: 13, 15: 23}, {3: 6, 11: 6}, {13: 23, 14: 24, 15: 19}]
CARRIER_AMEN = [{**{k: AMEN_HATS[(k + b) % len(AMEN_HATS)] for k in range(16)}, **AMEN_SWAPS[b]} for b in range(BARS)]

APACHE_HATS = [2, 5, 7, 12, 16, 19, 21, 26]        # hats on the 8ths
APACHE_OFF = [                                      # the 16ths between: ghosts, bongos, congas, re-dealt per bar
    {1: 1, 3: 8, 5: 3, 7: 6, 9: 10, 11: 13, 13: 15, 15: 20},
    {1: 17, 3: 22, 5: 24, 7: 1, 9: 3, 11: 27, 13: 10, 15: 6},
    {1: 15, 3: 13, 5: 1, 7: 20, 9: 24, 11: 8, 13: 3, 15: 22},
    {1: 10, 3: 27, 5: 17, 7: 6, 9: 1, 11: 22, 13: 13, 15: 20},
]
CARRIER_APACHE = [{**{k: APACHE_HATS[(k // 2 + b) % 8] for k in range(0, 16, 2)}, **APACHE_OFF[b]} for b in range(BARS)]

SWEAT_EVEN = [1, 3, 8, 11, 13, 18]                 # ghost+hat slices on the 8ths
SWEAT_OFF = [                                       # ghosts and soft snares between, loudest on the "a"s
    {1: 9, 3: 4, 5: 19, 7: 14, 9: 9, 11: 4, 13: 19, 15: 14},
    {1: 19, 3: 14, 5: 9, 7: 4, 9: 19, 11: 14, 13: 9, 15: 4},
    {1: 9, 3: 14, 5: 19, 7: 4, 9: 9, 11: 14, 13: 19, 15: 4},
    {1: 19, 3: 4, 5: 9, 7: 14, 9: 19, 11: 4, 13: 9, 15: 14},
]
CARRIER_SWEAT = [{**{k: SWEAT_EVEN[(k // 2 + b) % 6] for k in range(0, 16, 2)}, **SWEAT_OFF[b]} for b in range(BARS)]

TWO_STEP = [(36, b * 4 + t, 0.4, v) for b in range(BARS) for t, v in ((0.0, 122), (2.5, 112))]

# ---------------------------------------------------------------- sub basslines (F# minor)
# The bass archetype, as the user described and wrote it and as the reference measures it:
#   - notes struck at the front of the bar; mostly repeats and scale steps, a fourth or fifth now and then
#   - about one pitch change a bar (0.5 under the two-step, where the reference's bass barely moves)
#   - phrases that DROP to a low "dum" on the fundamental and leave a gap. The gap lifts the break ~6 dB
#     against the low end without touching it. About one phrase in two or three ends that way; the rest
#     carry on into the next.
# The dry run checks every note against F# minor.
FS0, GS0, A0, B0, CS1, D1, E1 = 30, 32, 33, 35, 37, 38, 40          # F# minor up from the fundamental F#0 (46.25 Hz)
F_SHARP_MINOR = {6, 8, 9, 11, 1, 2, 4}                               # pitch classes F# G# A B C# D E


def hits(pitch, starts, dur, vel=110):
    """The same note struck at each start (beats), each lasting `dur`."""
    return [(pitch, float(s), float(dur), vel) for s in starts]


def slide(notes, overlap=0.1):
    """Stretch each note into the next wherever the pitch changes, so SUB-LIMINAL's glide slides."""
    notes = sorted(notes, key=lambda n: n[1])
    out = []
    for k, (p, s, d, v) in enumerate(notes):
        if k + 1 < len(notes) and notes[k + 1][0] != p:
            d = max(d, notes[k + 1][1] - s + overlap)
        out.append((p, s, round(d, 4), v))
    return out


# ARRIVALS (F-HOLE) - "da da da daa, da da da da, dum": two 2-bar phrases. The first steps down and carries
# on; the second drops to the fundamental on beat 3 of bar 4 and leaves the rest of the bar to the break.
BASS_ARRIVALS = (hits(CS1, (0.0, 0.5, 1.0), 0.4, 114) + hits(CS1, (1.5,), 1.25, 110)
                 + hits(B0, (4.0, 4.5, 5.0, 5.5), 0.4, 108) + hits(B0, (6.0,), 1.75, 104)
                 + hits(CS1, (8.0, 8.5, 9.0), 0.4, 114) + hits(CS1, (9.5,), 1.25, 110)
                 + hits(B0, (12.0, 12.5), 0.4, 108) + hits(A0, (13.0, 13.5), 0.4, 106)
                 + hits(FS0, (14.0,), 0.9, 120))
# DEPARTURES (F-HOLE) - 8 bars walking round the root on 1 and the "and" of 2 (repeats and steps), a fifth
# leap up in bar 7, and the fall to the fundamental in bar 8 with the rest of that bar empty.
BASS_DEPARTURES = ([n for b, p in enumerate((FS0, GS0, A0, GS0, B0, A0, CS1))
                    for n in hits(p, (b * 4.0, b * 4.0 + 1.5), 1.0, 112 if b % 2 == 0 else 106)]
                   + hits(FS0, (28.0,), 1.5, 120), 32.0)
# SUB-POENA SERVED (SUB-POENA) - busier and shorter: 16th pairs on the 1, answers on the "and"s, stepping
# down to the fundamental on beat 2 of bar 4, then a long gap.
BASS_SERVED = (hits(E1, (0.0, 0.25), 0.22, 118) + hits(E1, (1.5,), 0.5, 108)
               + hits(D1, (4.0, 4.25), 0.22, 116) + hits(CS1, (5.5, 6.5), 0.5, 108)
               + hits(E1, (8.0, 8.25), 0.22, 118) + hits(B0, (9.5, 10.5), 0.5, 108)
               + hits(B0, (12.0, 12.25), 0.22, 116) + hits(FS0, (13.0,), 0.75, 122))
# COURT OF APPEAL (SUB-POENA) - the reference's short-note recipe (bass.md section 13): 2-3 short notes a bar on
# the 8th grid, in pairs - short on a beat, short on its "and", held on the next beat - and a push from the
# "and" of 3 into a held beat 4. Repeat or step after a short note; move only off held notes. Most short
# notes in bar 1, fewest in bar 4, which drops to the fundamental on beat 2 and leaves the rest open.
SHORT, HELD = 0.3, 1.25


def pair_bar(bar, pitch, push_to=None, lead=True):
    """Short on 1 and its "and" into a held 2 (when `lead`), then a short on the "and" of 3 pushing into a
    held 4 on `push_to` (the same note, or a step)."""
    at = bar * 4.0
    notes = []
    if lead:
        notes += hits(pitch, (at, at + 0.5), SHORT, 110) + hits(pitch, (at + 1.0,), HELD, 116)
    notes += hits(pitch, (at + 2.5,), SHORT, 108) + hits(push_to or pitch, (at + 3.0,), 0.9, 114)
    return notes


BASS_APPEAL = (pair_bar(0, CS1, push_to=B0)                                   # bar 1: 3 short
               + pair_bar(1, B0)                                              # bar 2: 3 short
               + hits(A0, (8.0,), HELD, 116) + hits(A0, (9.5, 10.5), SHORT, 107)   # bar 3: held, 2 short,
               + hits(A0, (11.0,), 0.9, 114)                                       # a held 4
               + hits(GS0, (12.0, 12.5), SHORT, 110) + hits(FS0, (13.0,), 1.0, 122))   # bar 4: 2 short, dum
# SUBLIMINAL MESSAGE (SUB-LIMINAL, over the two-step) - near-still: the root on 1 and the "and" of 2, a slide
# up to A and back in bar 4, a slide up a fifth in bars 6-7 and back down to the fundamental in bar 8, then a gap.
BASS_MESSAGE = (slide([n for b in (0, 1, 2, 4, 5) for n in hits(FS0, (b * 4.0, b * 4.0 + 1.5), 1.25, 112)]
                      + hits(FS0, (12.0,), 1.25, 112) + hits(A0, (13.5,), 1.25, 108)
                      + hits(CS1, (24.0, 25.5), 1.25, 110) + hits(FS0, (28.0,), 1.5, 120)), 32.0)
# COMING DOWN (SUB-LIMINAL) - up then down: F# to A to B, a push up to C# on the "and" of 3 in bar 3, and a
# slide down a fifth onto the fundamental in bar 4, then a gap.
BASS_COMING_DOWN = slide(hits(FS0, (0.0, 1.5), 1.25, 112) + hits(A0, (4.0, 5.5), 1.25, 110)
                         + hits(B0, (8.0, 9.5), 1.0, 110) + hits(CS1, (10.5,), 1.0, 112)
                         + hits(FS0, (12.0,), 1.5, 120))

# ---------------------------------------------------------------- sub signatures (copies of F-HOLE)
SUB_VOICES = {
    "SUB-POENA": [          # driven through Operator's shaper; a sharper, faster drop
        ("Shaper Mix", 100.0), ("Shaper Drive", 8.0),
        ("Pe On", "On"), ("Pe Init", 36.0), ("Pe Peak", 36.0), ("Pe Decay", 40.0),
    ],
    "SUB-LIMINAL": [        # octave-doubled (oscillator B an octave up, just under A), no drop, glides
        ("Algorithm", "Alg. 11"), ("Osc-B On", "On"), ("Osc-B Wave", "Sine"), ("B Coarse", 2.0),
        ("Osc-B Level", -2.0), ("Pe On", "Off"), ("Glide On", "On"), ("Glide Time", 90.0),
    ],
}
SHAPER_TYPE_RAW = 1         # the first non-off shaper curve; its name is read back and reported

# ---------------------------------------------------------------- scene drums (tracks/2026-09-16_jungle_scene_rules.md)
# A scene holds an identity (spine voice, signature hits, main break, 16th carrier); inside it, every hit
# has a CHANCE (Live's note probability), so each pass deals a fresh bar from the scene's distribution.
# Notes here are (pitch, start, duration, velocity, chance).
try:
    with open(os.path.join(SCRIPTS_DIR, "jungle_kit_map.json")) as _fh:
        KIT_MAP = json.load(_fh)
except FileNotFoundError:                   # scripts/jungle_kits.py writes it
    KIT_MAP = {"spines": {}, "variants": {}}

SPINE_SLOTS = (0, 4, 10, 12)                # kick on 1, snare on 2, kick on the "and" of 3, snare on 4
SECTIONS = {
    # section: (spine track, main break track, break slices, 16th carrier track, chance per 16th, "and" of 3 kick)
    # Chance maps are the mid-band occupancy of a contrasting reference section (rhythm.md section 1):
    # the positions it favours are that scene's signature hits. Spine slots are played by the spine lane.
    "arrivals": ("SPINE-TINGLER", "AMEN-DMENT", AMEN, "THROW-UP",
                 [0.97, 0.09, 0.79, 0.43, 0.97, 0.04, 0.88, 0.88, 0.40, 0.51, 0.97, 0.09, 0.99, 0.40, 0.53, 0.78], 0.96),
    "court": ("SPINAL-TAP", "COLD-CUTS", SWEAT, "TOPSOIL",
              [0.76, 0.30, 0.82, 0.46, 0.97, 0.06, 0.81, 0.54, 1.00, 0.07, 0.96, 0.12, 0.93, 0.19, 0.93, 0.13], 0.70),
    "print": ("SPINELESS", "CHOPPER", TOP, "SWEAT-SHOP",
              [0.95, 0.07, 0.45, 0.07, 1.00, 0.00, 0.75, 0.93, 0.95, 0.07, 0.95, 0.09, 0.95, 0.82, 0.82, 0.27], 1.0),
}
# variant pads, the same layout on every main break (scripts/jungle_kits.py)
V_SNARE_UP12, V_SNARE_UP7, V_KICK_DOWN, V_STUTTER, V_REV_SNARE, V_REV_LIGHT, V_STRETCH_2, V_STRETCH_15 = range(72, 80)


def kind_of(brk, s):
    parts = brk.parts[s]
    if any(p == "kick" for p in parts):
        return "kick"
    if "snare" in parts:
        return "snare"
    if "snare_soft" in parts:
        return "soft"
    return "light"                          # hats, ghosts, bongos, congas


def spine_lane(section):
    spine, *_, kick_3and = SECTIONS[section]
    pads = KIT_MAP["spines"].get(spine, {"kick": 36, "snare": 38})
    k, sn = pads["kick"], pads["snare"]
    out = []
    for b in range(BARS):
        at = b * 4.0
        out += [(k, at, 0.45, 122, 1.0), (sn, at + 1.0, 0.6, 118, 1.0),
                (k, at + 2.5, 0.4, 112, kick_3and), (sn, at + 3.0, 0.6, 118, 1.0)]
    return out


def home_bars(brk, drop_kicks=False):
    """The break's own two bars on the 16th grid, in the drummer's order: {16th: slice} per bar."""
    bars = [{}, {}]
    for s, h in enumerate(brk.home):
        b, k = divmod(int(round(h * 4)), 16)
        if b < 2 and not (drop_kicks and kind_of(brk, s) == "kick"):
            bars[b].setdefault(k, s)
    return bars


def blocks(brk, turnaround, drop_kicks=False):
    """A-B-C-D from whole blocks of the break: A = its first bar, B = its second, C = A's first half with
    B's second half, D = B with a turnaround in its last beat (slices by index, the snare on 4 kept)."""
    a, b = home_bars(brk, drop_kicks)
    c = {**{k: v for k, v in a.items() if k < 8}, **{k: v for k, v in b.items() if k >= 8}}
    d = {**{k: v for k, v in b.items() if k < 13}, **turnaround}
    return [a, b, c, d]


CHOP_BARS = {
    "arrivals": CHOP_A,                                                      # the approved WAITING ROOM chop
    "court": blocks(SWEAT, {13: 9, 14: 14, 15: 19}),                          # ghost, soft snare, ghost
    "print": blocks(TOP, {13: 13, 14: 20, 15: 27}, drop_kicks=True),          # conga, bongo, conga
}


def chop_lane(section):
    """The scene's chop, legible first: whole blocks of its own break (CHOP_BARS), kicks and snares kept,
    and every core hit at 100%. Chance only decorates - ghosts and hats on the off-16ths at 65%, hands at
    80%, and the variant pads at 25-35% in 16ths the chop leaves empty (bar D's turnaround is the fill). A hit rings until
    the next hit that always plays, so a note that doesn't fire never cuts another one short."""
    _, _, brk, _, _, _ = SECTIONS[section]
    notes = []
    for b, bar in enumerate(CHOP_BARS[section]):
        for slot, s in sorted(bar.items()):
            parts = brk.parts[s]
            kind = kind_of(brk, s)
            vel = max(VEL.get(p, 96) for p in parts) - (12 if slot % 2 else 0)
            if kind == "light" and slot % 2 and not any(p in ("bongo", "conga") for p in parts):
                chance = 0.65
            elif any(p in ("bongo", "conga") for p in parts):
                chance = 0.8
            else:
                chance = 1.0
            notes.append((36 + s, b * 4.0 + slot * 0.25, brk.natural(s), vel, chance))
    variants = [(V_SNARE_UP7, 0, (15, 13, 11), 96, 0.25, 0.25),   # a snare up a fifth, late in bar A
                (V_REV_LIGHT, 1, (14, 13, 9), 90, 0.35, 0.25),     # a reversed hat or hand drum in bar B
                (V_KICK_DOWN, 2, (3, 5, 9), 104, 0.30, 0.5),       # the kick pitched down in bar C
                (V_STRETCH_15, 2, (6, 7, 11), 94, 0.30, 0.5),      # a stretched snare in bar C
                (V_SNARE_UP12, 3, (15, 11, 9), 100, 0.30, 0.25)]   # a snare an octave up to end bar D
    for pad, b, slots, vel, p, natural in variants:
        taken = CHOP_BARS[section][b]
        slot = next((sl for sl in slots if sl not in taken), None)
        if slot is not None:
            notes.append((pad, b * 4.0 + slot * 0.25, natural, vel, p))
    notes.sort(key=lambda n: n[1])
    certain = [n[1] for n in notes if n[4] >= 0.99]
    out = []
    for pad, t, nat, vel, p in notes:
        nxt = next((c for c in certain if c > t + 1e-6), LEN)
        out.append((pad, round(t, 4), round(max(0.05, min(nat, nxt - t) - 0.012), 4), vel, p))
    return out


def with_chance(notes, off8=0.85):
    """Carrier 16ths: the 8th positions always play; the "e"s and "a"s play at `off8` chance."""
    return [(p, t, d, v, off8 if round(t * 4) % 2 else 1.0) for p, t, d, v in notes]


def drums(section, carrier):
    spine, chop_track, _, carrier_track, _, _ = SECTIONS[section]
    return {spine: spine_lane(section), chop_track: chop_lane(section), carrier_track: carrier}


# ---------------------------------------------------------------- rows: (scene, name, {track: notes})
ROWS = [
    (0, "WAITING ROOM", drums("arrivals", "carrier_amen")),
    (1, "ARRIVALS", {**drums("arrivals", "carrier_amen"), "F-HOLE": BASS_ARRIVALS}),
    (2, "DEPARTURES", {**drums("arrivals", "carrier_amen"), "F-HOLE": BASS_DEPARTURES}),
    (8, "THE DOCK", drums("court", "carrier_apache")),
    (9, "SUB-POENA SERVED", {**drums("court", "carrier_apache"), "SUB-POENA": BASS_SERVED}),
    (10, "COURT OF APPEAL", {**drums("court", "carrier_apache"), "SUB-POENA": BASS_APPEAL}),
    (16, "SMALL PRINT", drums("print", "carrier_sweat")),
    (17, "SUBLIMINAL MESSAGE", {**drums("print", "carrier_sweat"), "SUB-LIMINAL": BASS_MESSAGE}),
    (18, "COMING DOWN", {**drums("print", "carrier_sweat"), "SUB-LIMINAL": BASS_COMING_DOWN}),
]
CARRIERS = {
    "carrier_amen": with_chance([(p, t, min(d, 0.22), v - 8) for p, t, d, v in lane(AMEN, CARRIER_AMEN)]),
    "carrier_apache": with_chance(lane(TOP, CARRIER_APACHE, cap=0.22, soften_off8=10), off8=0.9),
    "carrier_sweat": with_chance(lane(SWEAT, CARRIER_SWEAT, cap=0.22, soften_off8=18,
                                      accent_slots=(3, 7, 11, 15), accent=16)),
}
# clips the previous drum model left on lanes these rows no longer use (the Amen chops B and C, the old
# two-step kick lane - the spine carries it now)
STALE: list = []   # the old-model clips were cleared on 2026-09-16, before the rows moved into octaves


def lane_value(value):
    """A lane is a carrier name, a note list (4-bar clip), or (notes, clip length)."""
    if isinstance(value, str):
        return CARRIERS[value], LEN
    return value if isinstance(value, tuple) else (value, LEN)


def changes_per_bar(riff, length=LEN):
    pitches = [p for p, *_ in sorted(riff, key=lambda n: n[1])]
    moves = sum(1 for a, b in zip(pitches, pitches[1:] + pitches[:1]) if a != b)
    return moves / (length / 4.0)


def bass_report(notes, length):
    """The archetype checks: in key, pitch changes a bar, the move mix, and whether it drops to the
    fundamental and leaves a gap before the loop."""
    notes = sorted(notes, key=lambda n: n[1])
    off_key = sorted({p for p, *_ in notes if p % 12 not in F_SHARP_MINOR})
    pitches = [p for p, *_ in notes]
    moves = [abs(b - a) for a, b in zip(pitches, pitches[1:] + pitches[:1])]
    rep = sum(m == 0 for m in moves) / len(moves)
    step = sum(1 <= m <= 2 for m in moves) / len(moves)
    leap = sum(m >= 5 for m in moves) / len(moves)
    last = notes[-1]
    gap16 = (length - (last[1] + last[2])) * 4
    lands = last[0] == min(pitches) and last[0] % 12 == 6
    return (f"{changes_per_bar(notes, length):.2f} changes/bar, repeats {rep:.0%} steps {step:.0%} leaps {leap:.0%}, "
            f"{'drops to F#0' if lands else 'ends elsewhere'}, gap {gap16:.0f}/16ths"
            + (f", OFF KEY {off_key}" if off_key else ""))


def dry_run():
    for scene, name, lanes in ROWS:
        parts = []
        for track, value in lanes.items():
            notes, length = lane_value(value)
            extra = f" ({length / 4:g} bars)" if length != LEN else ""
            parts.append(f"{track} {len(notes)}{extra}")
            if track in ("F-HOLE", *SUB_VOICES):
                parts.append(bass_report(notes, length))
        print(f"  row {scene + 1:<2} {name:<20} | " + " | ".join(parts))


# ---------------------------------------------------------------- Live
def names(ch):
    n = ch.get_session_info().result(timeout=5)["track_count"]
    out = {}
    for i in range(n):
        out.setdefault(ch.get_track_info(i).result(timeout=5)["name"], i)
    return out


def meter(ch, track_name, t, slot, secs=2.0):
    ch.stop_all_clips().result(timeout=3)
    time.sleep(0.3)
    ch.fire_clip(t, slot).result(timeout=3)
    time.sleep(0.3)
    peak = 0.0
    end = time.monotonic() + secs
    while time.monotonic() < end:
        for m in ch.get_all_meters().result(timeout=2)["meters"]:
            if m["name"] == track_name:
                peak = max(peak, m.get("left", 0.0), m.get("right", 0.0))
        time.sleep(0.04)
    ch.stop_all_clips().result(timeout=3)
    return peak


def ensure_sub_voices(ch, check=False):
    """Create any missing sub voice (a copy of F-HOLE), set it and meter a test note. Voices that already
    exist are left alone unless `check`: re-applying settings and metering stops playback and is slow."""
    from jungle_space import set_number, set_string, _param
    from jungle_build import write_clip
    scenes = ch.get_scene_count().result(timeout=5)["count"]
    for voice, settings in SUB_VOICES.items():
        idx = names(ch)
        if voice in idx and not check:
            continue
        ch.set_launch_quantization(0).result(timeout=3)
        if voice not in idx:
            src = idx["F-HOLE"]
            ch.duplicate_track(src).result(timeout=60)
            t = src + 1
            ch.set_track_name(t, voice).result(timeout=3)
            for s in range(scenes):
                try:
                    ch.clear_clip(t, s).result(timeout=5)
                except Exception:
                    pass
            print(f"  {voice}: copied from F-HOLE to track {t}")
        t = names(ch)[voice]
        for pname, target in settings:
            try:
                (set_string if isinstance(target, str) else set_number)(ch, t, 0, pname, target)
            except Exception as e:
                print(f"  [skip] {voice} {pname}: {e!r}")
        if voice == "SUB-POENA":
            p = _param(ch, t, 0, "Shaper Type")
            ch.set_device_param(t, 0, p["index"], float(SHAPER_TYPE_RAW)).result(timeout=3)
        summary = {k: _param(ch, t, 0, k)["display"] for k in
                   ("Shaper Type", "Shaper Drive", "Algorithm", "Osc-B On", "B Coarse", "Osc-B Level",
                    "Pe On", "Pe Init", "Pe Decay", "Glide On", "Glide Time")}
        test_slot = scenes - 1
        write_clip(ch, t, test_slot, "test", [(FS0, 0.0, 3.5, 120)], 4.0)
        peak = meter(ch, voice, t, test_slot)
        ch.clear_clip(t, test_slot).result(timeout=5)
        print(f"  {voice}: F1 test note meters {peak:.3f} | {summary}")
        if peak <= 0.01:
            raise SystemExit(f"{voice} is silent - stopping before writing rows")


def same_clip(ch, t, scene, notes, length):
    """True when the slot already holds exactly these notes at this length, so it needn't be rewritten."""
    try:
        props = ch.get_clip_props(t, scene).result(timeout=5)
        if props.get("length") is None or abs(float(props["length"]) - length) > 1e-3:
            return False
        got = ch.get_clip_notes(t, scene).result(timeout=10)
    except Exception:
        return False
    got = got.get("notes", got) if isinstance(got, dict) else got
    key = lambda p, s, d, v, c=1.0: (int(p), round(float(s), 3), round(float(d), 3), int(round(float(v))), round(float(c), 2))
    have = sorted(key(x["pitch"], x["start_time"], x["duration"], x["velocity"], x.get("probability", 1.0)) for x in got)
    return have == sorted(key(*n) for n in notes)


def write_notes(ch, t, slot, name, notes, length):
    """Write a clip whose notes may carry a chance (5th field): Live 12 note probability."""
    from jungle_build import ensure_scenes
    ensure_scenes(ch, slot + 1)
    try:
        ch.create_clip(t, slot, float(length)).result(timeout=8)
    except Exception as e:
        print(f"    [warn] create_clip(track {t}, slot {slot}): {e}")
    ch.set_clip_name(t, slot, name).result(timeout=3)
    specs = [{"pitch": int(n[0]), "start_time": float(n[1]), "duration": float(n[2]), "velocity": int(n[3]),
              "probability": float(n[4]) if len(n) > 4 else 1.0} for n in notes]
    ch.add_notes_to_clip(t, slot, specs, replace=True).result(timeout=10)


def build(rows=None, lanes=None, check_voices=False):
    """Write only what differs: rows limited to `rows` (Live row numbers), tracks limited to `lanes`, and any
    clip that already holds the same notes is skipped. Playback is never stopped unless voices are metered."""
    from jungle_build import write_clip
    from thelmic.live_channel import LiveChannel
    ch = LiveChannel(lower_priority=False)
    ch.start()
    metered = False
    try:
        if check_voices or any(v not in names(ch) for v in SUB_VOICES):
            ensure_sub_voices(ch, check=check_voices)
            metered = True
        idx = names(ch)
        written = skipped = 0
        for scene, name, row_lanes in ROWS:
            if rows and scene + 1 not in rows:
                continue
            for track, value in row_lanes.items():
                if lanes and track not in lanes:
                    continue
                notes, length = lane_value(value)
                t = idx[track]
                if same_clip(ch, t, scene, notes, length):
                    skipped += 1
                    continue
                try:
                    ch.clear_clip(t, scene).result(timeout=5)
                except Exception:
                    pass
                write_notes(ch, t, scene, name.lower(), notes, length)
                written += 1
                print(f"  row {scene + 1} {name}: wrote {track}")
            ch.set_scene_name(scene, name).result(timeout=3)
        cleared = 0
        for track, scene in STALE:
            if (rows and scene + 1 not in rows) or (lanes and track not in lanes) or track not in idx:
                continue
            try:
                ch.get_clip_notes(idx[track], scene).result(timeout=5)
            except Exception:
                continue                        # already empty
            ch.clear_clip(idx[track], scene).result(timeout=5)
            cleared += 1
        print(f"  {written} clip(s) written, {skipped} already up to date, {cleared} stale clip(s) cleared")
    finally:
        try:
            if metered:
                ch.stop_all_clips().result(timeout=3)
                ch.set_launch_quantization(1).result(timeout=3)
        finally:
            ch.stop()


def main(argv=None):
    ap = argparse.ArgumentParser(description="Write the adopted-rules jungle rows into the session.")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--rows", help="comma-separated Live row numbers to write (default: all)")
    ap.add_argument("--lanes", help="comma-separated track names to write (default: all)")
    ap.add_argument("--check-voices", action="store_true",
                    help="re-apply the sub voices' settings and meter them (stops playback)")
    args = ap.parse_args(argv)
    dry_run()
    if not args.dry_run:
        rows = {int(r) for r in args.rows.split(",")} if args.rows else None
        lanes = set(args.lanes.split(",")) if args.lanes else None
        build(rows, lanes, args.check_voices)


if __name__ == "__main__":
    main()
