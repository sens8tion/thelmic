"""JUNGLE COMPOSE - a playable session for the 2026-09-15 jungle track (170 BPM, F minor).

Not a cut track: rows are musical states to move between. Groove rows are 8-bar loops; fill rows
are 1 bar and sit under the groove they belong to. Launch quantization is 1 bar.

  row  name                         bars  what it is
   0   TOPSOIL ONLY                   8   Apache tops + hands
   1   PRE-AMBLE                      8   + FM bell, strings pad
   2   DRONE ON                       8   + reese bed, Amen hats, first lead phrases
   3   WIND-UP MERCHANT               8   build: Amen snares, no kick/sub; rolls into a gap
   4   BOTTOM FEEDER                  8   drop A, lead theme A
   5   BOTTOM FEEDER >> FILL          1   roll + gap
   6   BOTTOM FEEDER II               8   drop A, reordered, second bass phrase
   7   CHOP SUEY                      8   drop, heavy block edits, reese stabs
   8   CHOP SUEY >> FILL              1
   9   HOLE                           1   the bar with no downbeat (launch on a phrase start)
  10   NOBODY HOME                    8   breakdown: reese Fm-Db, lead in front, bell
  11   NOBODY HOME II                 8   breakdown: reese Eb-C, bell, hands return, sub pulse
  12   SWEAT EQUITY                   8   build 2 on Cold Sweat rolls
  13   F-ALL                          8   drop 2: second reese, lead theme B, Cold Sweat tops
  14   F-ALL >> FILL                  1
  15   TERMINAL VELOCITY              8   drop 2, heaviest edits
  16   TERMINAL VELOCITY >> FILL      1   longer roll
  17   EXIT WOUND                     8   plain Amen + kick + sub: mix-out
  18   EXIT WOUND >> TOPS             8   tops + bell + lead

Playing it: a FILL row plays its roll then loops, so launch it in the bar before the phrase you
want and launch the next groove row while it plays. (No automatic return: Live's LOM does not
expose clip follow actions.) A build row's last bar is its roll + gap; launch a drop during it.
Every lane in a row is written for that row, so whole-row launches never cut a lane by accident.

How it is written (so the critique round can argue with it):
  - The Amen chop's home loop is 2 bars, so a UNIT is 2 bars. Edits move whole BLOCKS of slices,
    keeping each slice's offset in its block: the break's micro-timing survives.
  - Inside every 8-bar groove: three units repeat verbatim, the fourth disturbs.
  - Kick and bass: sub and reese HOLD their notes; the kick carves them out through sidechain
    compressors keyed from BOOT-LEG.
  - Harmony: a strings pad (HALO-PERIDOL) voiced high moves Fm9 - Dbmaj9 - Bbm9 - Eb9sus4, four
    bars each, over the sub's F pedal (every chord contains F); fills hold the Eb9sus4 tension.
  - Lyrical line: a Rhodes lead (LIP-SERVICE) plays 16-bar themes that breathe (rests of 2 bars
    between phrases), theme A in drop 1, a higher theme B in drop 2, slower lines in the breakdowns.
  - The FM bell stays a sparse surprise: 16-bar clips, a few different 2-bar motifs, never in the
    drums' disturbance bars, and placed where the lead rests so the two answer each other.
  - Reese: its own line per row (a late glide up a fifth, octave flips, offbeat stabs), and a second
    reese (RASP-UTIN) takes over in drop 2 for a different colour.
  - Space: dub throws (THROW-UP) catch the last snare of a phrase into echo and reverb tails.

    python scripts/jungle_compose.py --dry-run   # note counts + clip checks, no Live
    python scripts/jungle_compose.py             # write the clips into the running set
"""
from __future__ import annotations

import argparse
import os
import sys

os.environ.setdefault("LIVE_CHANNEL_ENABLED", "1")
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(SCRIPTS_DIR))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from jungle_slices import BREAKS, SLICE_ROOT  # noqa: E402

SR = 44100
FILE_BPM = {"AMEN-DMENT": 160.0, "SWEAT-SHOP": 174.0, "TOPSOIL": 174.0}
UNIT = 8.0              # beats: 2 bars, the length of the Amen chop's home loop
BAR = 4.0
GATE_MARGIN = 0.012     # beats (~4 ms at 170): the 3 ms slice Fade Out ends before the next hit
LEGATO_GAP = 0.03       # beats between held notes

# ----------------------------------------------------------------------
# Breaks: slice home positions (beats in the break's own grid) and labels
# ----------------------------------------------------------------------


class Break:
    def __init__(self, track: str):
        frames, labels = BREAKS[track]
        spb = 60.0 / FILE_BPM[track]
        self.track = track
        self.home = [f / SR / spb for f in frames]
        self.parts = [lab.split("+") for lab in labels]

    def natural(self, i: int) -> float:
        """Slice length in beats. The Amen is repitched +1 st and the 174s detuned -40 c, so every
        break plays at ~170 and its home grid is the song grid."""
        return self.home[i + 1] - self.home[i] if i + 1 < len(self.home) else 1.0

    def has(self, i: int, drum: str) -> bool:
        return drum in self.parts[i]


AMEN, SWEAT, TOP = Break("AMEN-DMENT"), Break("SWEAT-SHOP"), Break("TOPSOIL")

VEL = {"kick": 118, "snare": 112, "snare_soft": 102, "ghost": 90, "hat": 98, "bongo": 104, "conga": 106}

# A break event is (slice index, start beat, velocity, wanted duration or None).


def block(brk: Break, src: float, length: float, at: float, *, only=None, drop=None, scale=1.0):
    """Every slice whose home is in [src, src+length), placed at `at` with its offset kept."""
    out = []
    for i, h in enumerate(brk.home):
        if not (src - 1e-6 <= h < src + length - 0.02):   # a slice at 7.998 is the NEXT bar's downbeat
            continue
        parts = brk.parts[i]
        if only and not any(p in only for p in parts):
            continue
        if drop and any(p in drop for p in parts):
            continue
        v = max(VEL.get(p, 100) for p in parts) * scale
        out.append((i, at + (h - src), int(round(v)), None))
    return out


def roll(slices, start, end, step, v0, v1):
    """Repeated hits cycling through `slices`, velocity ramping v0 -> v1."""
    n = int(round((end - start) / step))
    return [(slices[k % len(slices)], start + k * step,
             int(round(v0 + (v1 - v0) * k / max(1, n - 1))), step) for k in range(n)]


def before(events, t):
    return [e for e in events if e[1] < t - 1e-6]


def hole(events, a, b):
    """Remove everything starting in [a, b). Works on break events and note quads alike."""
    return [e for e in events if not (a - 1e-6 <= e[1] < b - 1e-6)]


def units(fns):
    out = []
    for n, f in enumerate(fns):
        out += f(n * UNIT)
    return out


def break_notes(brk: Break, events, length: float):
    """Events -> (pitch, start, dur, vel). One hit per onset (the louder wins). Each slice has its own
    drum pad, so hits overlap and ring out: a note runs its slice's full length, or its wanted length
    (roll steps), and is only cut by the next hit on the SAME pad or the clip end."""
    ev = sorted((e for e in events if -1e-6 <= e[1] < length - 1e-6), key=lambda e: (e[1], -e[2]))
    kept = []
    for e in ev:
        if kept and abs(e[1] - kept[-1][1]) < 0.02:
            continue
        kept.append(e)
    out = []
    for k, (i, st, vel, want) in enumerate(kept):
        nxt = next((e[1] for e in kept[k + 1:] if e[0] == i), length)
        dur = min(brk.natural(i), nxt - st, length - st, want if want else 1e9) - GATE_MARGIN
        if dur < 0.03:
            continue
        out.append((SLICE_ROOT + i, round(st, 4), round(dur, 4), max(1, min(127, vel))))
    return out


# ----------------------------------------------------------------------
# AMEN-DMENT units (8 beats each, u = unit start)
#   home kicks 0, 0.48, 2.48 | 4.46, 6.42 ; loud snares 0.99, 1.74, 3.43 | 5.18, 5.66, 6.96
# ----------------------------------------------------------------------
A_SNARE_16 = [21, 9, 21, 15]
A_SNARE_32 = [21, 17, 21, 15]


def a_home(u):
    return block(AMEN, 0, 8, u)


def a_edit1(u):      # bar 2 opens on bar 1's double kick + snare, then bar 2's own ending
    return block(AMEN, 0, 4, u) + block(AMEN, 0, 2, u + 4) + block(AMEN, 6, 2, u + 6)


def a_edit2(u):      # bar 1's back half swapped for bar 2's ending: the snare lands a beat early
    return block(AMEN, 0, 2, u) + block(AMEN, 6, 2, u + 2) + block(AMEN, 4, 4, u + 4)


def a_reorder(u):    # half-bars 1-3-2-4; the kicks stay where home puts them
    return block(AMEN, 0, 2, u) + block(AMEN, 4, 2, u + 2) + block(AMEN, 2, 2, u + 4) + block(AMEN, 6, 2, u + 6)


def a_tops(u, scale=1.0):
    return block(AMEN, 0, 8, u, drop={"kick"}, scale=scale)


def a_hats(u, scale=1.0):
    return block(AMEN, 0, 8, u, only={"hat"}, scale=scale)


def a_build1(u):     # hats with a half-time backbeat
    return a_hats(u) + [(2, u + AMEN.home[2], 108, None), (21, u + AMEN.home[21], 112, None)]


def a_build3(u):     # 8th-note snares
    return a_hats(u, 0.9) + roll([2, 21], u, u + 8, 0.5, 90, 112)


def a_build4(u):     # 16ths for a bar, 32nds to beat 6.5, then a beat and a half of silence
    return roll([2, 21], u, u + 4, 0.25, 98, 116) + roll([15, 17], u + 4, u + 6.5, 0.125, 108, 127)


# SWEAT-SHOP (Cold Sweat): kick slices left out so its kick pattern never argues with the Amen's
def s_tops(u, scale=0.8):
    return block(SWEAT, 0, 8, u, drop={"kick"}, scale=scale)


def s_roll8(u):
    return roll([2, 7], u, u + 8, 0.5, 88, 110)


def s_roll_end(u):
    return roll([2, 7, 12, 17], u, u + 4, 0.25, 94, 116) + roll([2, 7], u + 4, u + 6.5, 0.125, 106, 127)


# TOPSOIL (Apache, everything under 400 Hz cut): hats, snare tops, bongo and conga
def t_home(u, scale=0.9):
    return block(TOP, 0, 8, u, scale=scale)


def t_hats(u, scale=0.7):
    return block(TOP, 0, 8, u, only={"hat"}, scale=scale)


def t_hands(u, scale=1.0):
    return block(TOP, 0, 8, u, only={"bongo", "conga"}, scale=scale)


def t_turnaround(u):
    return block(TOP, 4, 4, u + 4, only={"bongo", "conga"})


# THROW-UP: the Amen slices again, but this lane is only heard as echo and reverb tails
THROW_SNARE = 21                 # the loudest backbeat snare


def throws(positions, slice_index=THROW_SNARE, vel=112):
    return [(slice_index, at, vel, 0.5) for at in positions]


# ----------------------------------------------------------------------
# Pitched lanes: (pitch, start, dur, vel)
# ----------------------------------------------------------------------
KICK_PITCH = 36                  # the kick pad (C1) of the factory kit on BOOT-LEG
F1, AB1, BB1, C2, EB1 = 29, 32, 34, 36, 27

SUB_CELLS = {                    # (pitch, start) per 2-bar unit; every note holds to the next one
    "A":  [(F1, 0.0), (F1, 3.0), (F1, 5.0), (AB1, 7.0)],
    "A!": [(F1, 0.0), (AB1, 3.0), (BB1, 5.0), (C2, 7.0)],
    "B":  [(F1, 0.0), (F1, 3.0), (EB1, 5.0), (EB1, 7.0)],
    "B!": [(F1, 0.0), (AB1, 3.0), (C2, 5.0), (BB1, 7.0)],
}


def kick_layer(amen_events, length):
    starts = sorted({round(e[1], 4) for e in amen_events if AMEN.has(e[0], "kick") and 0 <= e[1] < length})
    out, last = [], -9.0
    for st in starts:
        if st - last < 0.6:      # no fast double kicks under the break
            continue
        down = min(st % UNIT, UNIT - st % UNIT) < 0.05
        out.append((KICK_PITCH, st, round(min(0.4, length - st - 0.02), 4), 122 if down else 110))
        last = st
    return out


def hold(starts, length, vel):
    """(pitch, start) pairs -> notes that each hold until the next one starts (or the clip end)."""
    starts = sorted(starts, key=lambda n: n[1])
    return [(p, s, round((starts[k + 1][1] if k + 1 < len(starts) else length) - s - LEGATO_GAP, 4), vel)
            for k, (p, s) in enumerate(starts)]


def sub_line(cells, length, vel=112):
    return hold([(p, n * UNIT + s) for n, c in enumerate(cells) if c for p, s in SUB_CELLS[c]], length, vel)


def reese_line(sub, style, vel=96):
    """The reese follows the sub's roots an octave up, but moves inside each note:
      follow  - holds the root
      slide   - glides up a fifth late in the note (overlapping notes, so the patch's Glide bends)
      octaves - 8ths flipping between the octave and the one above
      stabs   - offbeat stabs on the root, leaving the sub alone underneath"""
    out = []
    for p, s, d, _ in sub:
        r = p + 12
        if style == "follow":
            out.append((r, s, d, vel))
        elif style == "slide":
            cut = round(s + d * 0.6, 4)
            out += [(r, s, round(min(cut - s + 0.12, d), 4), vel), (r + 7, cut, round(s + d - cut, 4), vel - 6)]
        elif style == "octaves":
            k, t = 0, s
            while t < s + d - 0.1:
                out.append((r + (12 if k % 2 else 0), round(t, 4), round(min(0.45, s + d - t), 4), vel - (10 if k % 2 else 0)))
                k, t = k + 1, t + 0.5
        elif style == "stabs":
            out += [(r, round(s + off, 4), 0.2, vel) for off in (0.5, 1.25, 1.75) if off + 0.2 < d]
        else:
            raise ValueError(style)
    return out


PAD_CHORDS = {                   # voiced Ab4-G5 so the sustain sits in the upper mids; every chord holds an F or its colour
    "Fm9":     [68, 72, 75, 79],   # Ab C Eb G
    "Dbmaj9":  [65, 68, 72, 75],   # F Ab C Eb
    "Bbm9":    [68, 72, 73, 77],   # Ab C Db F
    "Eb9sus4": [68, 70, 73, 77],   # Ab Bb Db F
    "Cm11":    [67, 70, 75, 77],   # G Bb Eb F
}
PROGRESSION = ["Fm9", "Dbmaj9", "Bbm9", "Eb9sus4"]


def pad(spans, vel=84):
    """[(chord, start beat, length beats)] -> (held chord notes, clip length = end of the last chord)."""
    out, end = [], 0.0
    for name, s, n in spans:
        out += [(p, s, round(n - LEGATO_GAP, 4), vel) for p in PAD_CHORDS[name]]
        end = max(end, s + n)
    return out, end


def progression(bars_each=4, chords=PROGRESSION):
    return pad([(c, k * bars_each * BAR, bars_each * BAR) for k, c in enumerate(chords)])


# Rhodes themes over the progression (16 bars = 64 beats). Chord tones on the strong beats, two-bar
# rests between phrases, pickups into the next chord; the last note is left hanging over Eb9sus4.
THEME_A = [
    (72, 0.0, 1.0), (75, 1.5, 0.5), (77, 2.0, 1.5), (75, 3.5, 0.5), (72, 4.0, 2.5),                # Fm9
    (68, 15.0, 0.5), (70, 15.5, 0.5),
    (72, 16.0, 1.5), (68, 17.5, 0.5), (65, 18.0, 2.0), (75, 20.5, 1.0), (73, 21.5, 0.5), (72, 22.0, 2.0),   # Dbmaj9
    (77, 32.0, 1.0), (80, 33.0, 0.5), (77, 33.5, 0.5), (73, 34.0, 1.5), (72, 35.5, 0.5), (70, 36.0, 2.0),   # Bbm9
    (73, 46.5, 0.5), (75, 47.0, 0.5), (77, 47.5, 0.5),
    (80, 48.0, 2.0), (77, 50.0, 1.0), (75, 51.0, 1.0), (73, 52.0, 2.0), (70, 54.5, 1.0),           # Eb9sus4
    (72, 56.0, 3.0),
]
THEME_B = [                      # drop 2: higher, busier, same chords
    (77, 0.0, 0.5), (80, 0.5, 0.5), (84, 1.0, 1.0), (82, 2.5, 0.5), (80, 3.0, 1.0), (77, 4.0, 2.0),
    (75, 14.5, 0.5), (77, 15.0, 1.0),
    (80, 16.0, 1.5), (77, 17.5, 0.5), (75, 18.0, 0.5), (72, 18.5, 1.5), (75, 20.5, 0.5), (77, 21.0, 2.5),
    (85, 32.0, 1.0), (84, 33.0, 0.5), (80, 33.5, 0.5), (77, 34.0, 1.0), (80, 35.0, 1.0), (82, 36.0, 2.0),
    (82, 48.0, 1.0), (80, 49.0, 0.5), (77, 49.5, 0.5), (73, 50.0, 1.0), (75, 51.0, 2.0), (77, 53.5, 0.5), (80, 54.0, 2.0),
    (77, 56.0, 0.5), (75, 56.5, 0.5), (72, 57.0, 3.0),
]
THEME_DOWN_1 = [                 # breakdown over Fm9 (4 bars) then Dbmaj9 (4 bars): long, singing notes
    (72, 0.0, 3.0), (75, 4.0, 2.0), (77, 6.0, 2.0), (80, 8.0, 4.0), (79, 12.0, 2.0), (77, 14.0, 2.0),
    (77, 16.0, 3.0), (75, 19.0, 1.0), (72, 20.0, 4.0),              # bars 7-8 left to the bell
]
THEME_DOWN_2 = [                 # breakdown over Eb9sus4 then Cm11
    (80, 0.0, 2.0), (77, 2.0, 2.0), (73, 6.0, 2.0), (75, 8.0, 6.0),
    (79, 16.0, 2.0), (77, 18.0, 1.0), (75, 19.0, 3.0), (70, 24.0, 2.0), (72, 26.0, 5.5),
]


def lead(theme, length, *, window=(0.0, 1e9), vel=96):
    """A theme (or the part of it inside `window`) -> (notes, clip length)."""
    a, b = window
    return [(p, s, d, vel + (8 if s % UNIT == 0 else 0)) for p, s, d in theme if a <= s < b], length


BELL_MOTIFS = {                  # 2-bar shapes (8 beats), F minor, Ab5-G6; no two alike
    "call":    [(80, 0.0, 0.4), (84, 0.75, 0.25), (87, 1.5, 0.4), (85, 2.0, 0.9)],
    "answer":  [(84, 4.75, 0.25), (82, 5.5, 0.4), (77, 6.0, 1.5)],
    "fall":    [(91, 0.0, 0.3), (87, 0.5, 0.3), (84, 1.0, 0.3), (80, 1.5, 1.2)],
    "offbeat": [(82, 0.5, 0.2), (85, 2.5, 0.2), (82, 4.5, 0.2), (89, 6.5, 0.6)],
    "held":    [(89, 0.0, 3.5)],                               # one F6; the Echo does the moving
    "climb":   [(77, 4.0, 0.3), (80, 4.5, 0.3), (84, 5.0, 0.3), (87, 5.5, 0.3), (89, 6.0, 1.5)],
}


def bell_plan(length, windows, vel=104):
    """[(start beat, "motif" or "motif+motif")] -> (notes, clip length). One 2-bar window each."""
    notes = []
    for at, names in windows:
        for name in names.split("+"):
            notes += [(p, at + s, d, vel) for p, s, d in BELL_MOTIFS[name]]
    return [n for n in notes if n[1] < length], length


# ----------------------------------------------------------------------
# Rows: each returns (length in beats, {track name: notes or (notes, own clip length)})
# ----------------------------------------------------------------------


def row_topsoil_only():
    L = 32.0
    return L, {"TOPSOIL": break_notes(TOP, units([t_home] * 4), L)}


def row_preamble():
    L = 32.0
    return L, {"TOPSOIL": break_notes(TOP, units([t_home] * 4), L),
               "BELL-END": bell_plan(64.0, [(8, "call+answer"), (40, "fall")]),
               "HALO-PERIDOL": progression()}


def row_drone_on():
    L = 32.0
    amen = units([lambda u: a_hats(u, 0.8)] * 4)
    return L, {"TOPSOIL": break_notes(TOP, units([t_home] * 4), L),
               "BELL-END": bell_plan(64.0, [(0, "offbeat"), (16, "held")]),
               "AMEN-DMENT": break_notes(AMEN, amen, L),
               "RASP-BERRY": [(41, 0.0, 15.5, 80), (37, 16.0, 15.5, 84)],
               "HALO-PERIDOL": progression(),
               "LIP-SERVICE": lead(THEME_A, 64.0, window=(32.0, 64.0))}


def row_build1():
    L = 32.0
    amen = a_build1(0) + a_tops(8) + a_build3(16) + a_build4(24)
    top = t_home(0) + t_home(8) + t_home(16) + before(t_home(24), 30.5)
    reese = [(41, 0.0, 15.9, 88), (44, 16.0, 7.9, 92), (48, 24.0, 6.4, 96)]   # roots climb, no sub
    return L, {"AMEN-DMENT": break_notes(AMEN, amen, L), "TOPSOIL": break_notes(TOP, top, L),
               "BELL-END": bell_plan(32.0, [(0, "offbeat"), (16, "climb")]), "RASP-BERRY": reese,
               "HALO-PERIDOL": pad([("Fm9", 0.0, 16.0), ("Dbmaj9", 16.0, 8.0), ("Eb9sus4", 24.0, 6.5)])[0],
               "THROW-UP": break_notes(AMEN, throws([30.375], slice_index=17), L)}


def groove_row(amen_fns, sub_cells, bell_windows, *, reese="follow", reese_lane="RASP-BERRY",
               theme=None, theme_window=(0.0, 1e9), throw_at=(30.96,), sweat=False, top_hats=None):
    L = UNIT * 4
    amen = units(amen_fns)
    sub = sub_line(sub_cells, L)
    top = t_turnaround(3 * UNIT)                    # hands on the disturbance unit
    if top_hats:
        top += units([lambda u: t_hats(u, top_hats)] * 4)
    lanes = {"AMEN-DMENT": break_notes(AMEN, amen, L), "BOOT-LEG": kick_layer(amen, L), "F-HOLE": sub,
             reese_lane: reese_line(sub, reese), "BELL-END": bell_plan(64.0, bell_windows),
             "TOPSOIL": break_notes(TOP, top, L), "HALO-PERIDOL": progression(),
             "THROW-UP": break_notes(AMEN, throws(throw_at), L)}
    if theme:
        lanes["LIP-SERVICE"] = lead(theme, 64.0, window=theme_window)
    if sweat:
        lanes["SWEAT-SHOP"] = break_notes(SWEAT, units([lambda u: s_tops(u, 0.75)] * 4), L)
    return L, lanes


def fill_row(first, *, roll_from=2.0, reese_lane="RASP-BERRY", sweat=False, top_hats=None):
    """One bar: `first` (break events up to roll_from), 16th snares for a beat, 32nds to 3.5, gap.
    The pad holds the Eb9sus4 tension; the last roll hit is thrown into the echo."""
    L = BAR
    amen = (before(first, roll_from) + roll(A_SNARE_16, roll_from, roll_from + 1.0, 0.25, 96, 112)
            + roll(A_SNARE_32, roll_from + 1.0, 3.5, 0.125, 112, 127))
    sub = [(F1, 0.0, round(roll_from - 0.05, 4), 112)]   # holds, then lets go for the roll
    top = before(block(TOP, 0, 4, 0, only={"bongo", "conga"}), roll_from)
    if top_hats:
        top += before(t_hats(0, top_hats), roll_from)
    lanes = {"AMEN-DMENT": break_notes(AMEN, amen, L), "BOOT-LEG": kick_layer(amen, L), "F-HOLE": sub,
             reese_lane: reese_line(sub, "follow"), "TOPSOIL": break_notes(TOP, top, L),
             "HALO-PERIDOL": pad([("Eb9sus4", 0.0, L)]),
             "THROW-UP": break_notes(AMEN, throws([3.375]), L)}
    if sweat:
        lanes["SWEAT-SHOP"] = break_notes(SWEAT, before(s_tops(0, 0.75), roll_from), L)
    return L, lanes


def row_hole():
    """The bar with no downbeat: every lane silent until the snare at 0.99, which is thrown."""
    L = BAR
    amen = hole(block(AMEN, 0, 4, 0), 0.0, 0.95)
    sub = [(F1, 1.0, round(L - 1.0 - LEGATO_GAP, 4), 112)]
    top = hole(t_home(0), 0.0, 0.95)
    return L, {"AMEN-DMENT": break_notes(AMEN, amen, L), "BOOT-LEG": kick_layer(amen, L), "F-HOLE": sub,
               "RASP-BERRY": reese_line(sub, "follow"), "TOPSOIL": break_notes(TOP, before(top, L), L),
               "HALO-PERIDOL": pad([("Fm9", 1.0, L - 1.0)]),
               "THROW-UP": break_notes(AMEN, throws([AMEN.home[2]], slice_index=2), L)}


def row_breakdown1():
    L = 32.0
    return L, {"RASP-BERRY": [(41, 0.0, 15.5, 90), (37, 16.0, 15.5, 90)],          # Fm, Db
               "BELL-END": bell_plan(32.0, [(24, "call+answer")]),                # answers the lead
               "HALO-PERIDOL": pad([("Fm9", 0.0, 16.0), ("Dbmaj9", 16.0, 16.0)]),
               "LIP-SERVICE": lead(THEME_DOWN_1, 32.0)}


def row_breakdown2():
    L = 32.0
    top = t_hands(0, 0.9) + t_hands(8, 0.9) + t_home(16, 0.85) + t_home(24, 0.85)
    return L, {"RASP-BERRY": [(39, 0.0, 15.5, 92), (36, 16.0, 15.5, 94)],          # Eb, C
               "BELL-END": bell_plan(64.0, [(14, "held")]),                      # in the lead's rest
               "TOPSOIL": break_notes(TOP, top, L),
               "F-HOLE": [(F1, 16.0 + 4 * k, 0.5, 100) for k in range(4)],       # the floor, just a pulse
               "HALO-PERIDOL": pad([("Eb9sus4", 0.0, 16.0), ("Cm11", 16.0, 16.0)]),
               "LIP-SERVICE": lead(THEME_DOWN_2, 32.0),
               "THROW-UP": break_notes(AMEN, throws([30.96]), L)}


def row_build2():
    L = 32.0
    sweat = s_tops(0) + s_tops(8) + s_roll8(16) + s_roll_end(24)
    amen = a_hats(8, 0.8) + a_hats(16, 0.8)
    top = t_hats(0) + t_hats(8) + t_hats(16) + before(t_hats(24), 30.5)
    reese = [(41, 0.0, 15.9, 88), (37, 16.0, 7.9, 92), (39, 24.0, 6.4, 96)]   # F Db Eb -> F on the drop
    return L, {"SWEAT-SHOP": break_notes(SWEAT, sweat, L), "AMEN-DMENT": break_notes(AMEN, amen, L),
               "TOPSOIL": break_notes(TOP, top, L), "BELL-END": bell_plan(32.0, [(8, "climb")]),
               "RASP-BERRY": reese,
               "HALO-PERIDOL": pad([("Dbmaj9", 0.0, 16.0), ("Eb9sus4", 16.0, 14.5)])[0],   # clip = row length
               "THROW-UP": break_notes(AMEN, throws([30.375], slice_index=17), L)}


def row_exit():
    L = 32.0
    amen = units([a_home] * 4)
    return L, {"AMEN-DMENT": break_notes(AMEN, amen, L), "BOOT-LEG": kick_layer(amen, L),
               "F-HOLE": sub_line(["A", "A", "A", "A"], L), "TOPSOIL": break_notes(TOP, units([t_home] * 4), L),
               "HALO-PERIDOL": pad([("Fm9", 0.0, 32.0)], vel=72),
               "THROW-UP": break_notes(AMEN, throws([30.96]), L)}


def row_exit_tops():
    L = 32.0
    amen = a_tops(0) + a_tops(8) + a_tops(16, 0.9) + a_tops(24, 0.8)
    return L, {"AMEN-DMENT": break_notes(AMEN, amen, L), "TOPSOIL": break_notes(TOP, units([t_home] * 4), L),
               "BELL-END": bell_plan(64.0, [(40, "held")]),
               "HALO-PERIDOL": progression(),
               "LIP-SERVICE": lead(THEME_A, 64.0, window=(0.0, 32.0))}


ROWS = [
    ("TOPSOIL ONLY", row_topsoil_only),
    ("PRE-AMBLE", row_preamble),
    ("DRONE ON", row_drone_on),
    ("WIND-UP MERCHANT", row_build1),
    ("BOTTOM FEEDER", lambda: groove_row([a_home, a_home, a_home, a_edit1], ["A", "A", "A", "A!"],
                                         [(8, "call+answer"), (40, "fall")], reese="slide", theme=THEME_A)),
    ("BOTTOM FEEDER >> FILL", lambda: fill_row(block(AMEN, 0, 2, 0))),
    ("BOTTOM FEEDER II", lambda: groove_row([a_home, a_home, a_reorder, a_edit1], ["B", "B", "B", "B!"],
                                            [(16, "offbeat"), (48, "climb")], reese="octaves",
                                            throw_at=(14.96, 30.96))),
    ("CHOP SUEY", lambda: groove_row([a_reorder, a_reorder, a_reorder, a_edit2], ["B", "B", "B", "B!"],
                                     [(32, "held")], reese="stabs", top_hats=0.6, throw_at=(22.96, 30.96))),
    ("CHOP SUEY >> FILL", lambda: fill_row(block(AMEN, 4, 2, 0), top_hats=0.6)),
    ("HOLE", row_hole),
    ("NOBODY HOME", row_breakdown1),
    ("NOBODY HOME II", row_breakdown2),
    ("SWEAT EQUITY", row_build2),
    ("F-ALL", lambda: groove_row([a_home, a_reorder, a_home, a_edit1], ["A", "A", "A", "A!"],
                                 [(8, "fall"), (40, "climb")], reese="slide", reese_lane="RASP-UTIN",
                                 theme=THEME_B, sweat=True, top_hats=0.6)),
    ("F-ALL >> FILL", lambda: fill_row(block(AMEN, 0, 2, 0), reese_lane="RASP-UTIN", sweat=True, top_hats=0.6)),
    ("TERMINAL VELOCITY", lambda: groove_row([a_edit2, a_reorder, a_edit2, a_edit1], ["B", "B", "B", "B!"],
                                             [(0, "offbeat"), (40, "held")], reese="octaves", reese_lane="RASP-UTIN",
                                             theme=THEME_B, theme_window=(32.0, 64.0), sweat=True, top_hats=0.6,
                                             throw_at=(14.96, 30.96))),
    ("TERMINAL VELOCITY >> FILL", lambda: fill_row(block(AMEN, 0, 2, 0), roll_from=1.5, reese_lane="RASP-UTIN",
                                                   sweat=True, top_hats=0.6)),
    ("EXIT WOUND", row_exit),
    ("EXIT WOUND >> TOPS", row_exit_tops),
]

LANES = ["AMEN-DMENT", "SWEAT-SHOP", "TOPSOIL", "BOOT-LEG", "F-HOLE", "RASP-BERRY", "RASP-UTIN",
         "BELL-END", "HALO-PERIDOL", "LIP-SERVICE", "THROW-UP"]
NICK = {"AMEN-DMENT": "amen", "SWEAT-SHOP": "sweat", "TOPSOIL": "tops", "BOOT-LEG": "boot",
        "F-HOLE": "sub", "RASP-BERRY": "rasp", "RASP-UTIN": "rasputin", "BELL-END": "bell",
        "HALO-PERIDOL": "pad", "LIP-SERVICE": "lead", "THROW-UP": "throw"}

# Bars 7-8 and 15-16 (beats 24-32, 56-64) are the drums' disturbance bars: the bell stays out.
DISTURBANCE_WINDOWS = [(24.0, 32.0), (56.0, 64.0)]


def lane_value(value, row_length):
    """A lane is notes (clip = row length) or (notes, its own clip length)."""
    return value if isinstance(value, tuple) else (value, row_length)


def tiled(notes, length, total=64.0):
    """A looping clip's notes repeated out to `total` beats, so clips of different lengths line up."""
    reps = max(1, int(round(total / length)))
    return [(p, s + k * length, d, v) for k in range(reps) for p, s, d, v in notes]


def check(name, L, lanes):
    """Clip hygiene: no note past its clip end; no bell note starting in a groove row's disturbance bars;
    report how often the bell sounds over the lead (they are meant to take turns)."""
    issues, counts = [], []
    for lane in LANES:
        if lane not in lanes:
            continue
        notes, length = lane_value(lanes[lane], L)
        over = sum(1 for _, s, d, _ in notes if s + d > length + 1e-6)
        if over:
            issues.append(f"{NICK[lane]} past clip end x{over}")
        counts.append(f"{NICK[lane]} {len(notes)}" + ("" if length == L else f" ({length / 4:g})"))
    bell = tiled(*lane_value(lanes["BELL-END"], L)) if "BELL-END" in lanes else []
    if "BOOT-LEG" in lanes and bell:
        clash = sum(1 for _, s, _, _ in bell for a, b in DISTURBANCE_WINDOWS if a <= s < b)
        if clash:
            issues.append(f"bell in disturbance bars x{clash}")
    if bell and "LIP-SERVICE" in lanes:
        lead_notes = tiled(*lane_value(lanes["LIP-SERVICE"], L))
        both = sum(1 for _, s, _, _ in bell for _, ls, ld, _ in lead_notes if ls <= s < ls + ld)
        if both > 2:
            issues.append(f"bell over lead x{both}")
    flag = f"   [warn] {', '.join(issues)}" if issues else ""
    print(f"  {name:<26} {L / 4:>4g} bars | {'  '.join(counts)}{flag}")
    return len(issues)


def build_all():
    out, problems = [], 0
    for name, fn in ROWS:
        L, lanes = fn()
        problems += check(name, L, lanes)
        out.append((name, L, lanes))
    print(f"  {len(out)} rows; problems: {problems}")
    return out


def compose(ch, tracks: dict):
    """Write every row's clips. tracks = {track name: index} (jungle_build passes it)."""
    from jungle_build import write_clip
    from thelmic.bridge.helpers import set_param

    rows = build_all()
    for name in ("SWEAT-SHOP", "TOPSOIL"):     # 174-BPM breaks: -40 cents plays them at exactly 170
        try:
            set_param(ch, tracks[name], 0, "Detune", value=-40.0)
        except Exception:
            pass                                # drum kits carry the detune on every pad instead
    for i, (row, L, lanes) in enumerate(rows):
        for lane in LANES:
            t = tracks[lane]
            notes, length = lane_value(lanes[lane], L) if lane in lanes else ([], L)
            try:
                # always clear first: write_clip reuses an existing clip at its OLD length, which
                # would silently truncate a lane whose clip length changed. An empty slot also
                # stops the lane when the row launches.
                ch.clear_clip(t, i).result(timeout=5)
            except Exception:
                pass
            if notes:
                write_clip(ch, t, i, f"{row.lower()} / {NICK[lane]}", notes, length)
        try:
            ch.set_scene_name(i, row).result(timeout=3)
        except Exception as e:
            print(f"  [skip] scene name {row}: {e}")
        print(f"  wrote row {i}: {row}")
    ch.set_launch_quantization(1).result(timeout=3)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Write the jungle session's clips into the running set.")
    ap.add_argument("--dry-run", action="store_true", help="note counts and clip checks only")
    args = ap.parse_args(argv)
    if args.dry_run:
        build_all()
        return
    from thelmic.live_channel import LiveChannel
    ch = LiveChannel(lower_priority=False)
    ch.start()
    try:
        n = ch.get_session_info().result(timeout=5)["track_count"]
        names = {ch.get_track_info(i).result(timeout=5)["name"]: i for i in range(n)}
        missing = [t for t in LANES if t not in names]
        if missing:
            raise SystemExit(f"missing tracks {missing}: run scripts/jungle_space.py (new lanes) first")
        compose(ch, names)
    finally:
        ch.stop()


if __name__ == "__main__":
    main()
