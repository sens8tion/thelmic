"""JUNGLE COMPOSE - a playable session for the 2026-09-15 jungle track (170 BPM, F minor).

Not a cut track: rows are musical states to move between. Groove rows are 8-bar loops; fill rows
are 1 bar and sit under the groove they belong to. Launch quantization is 1 bar.

  row  name                         bars  what it is
   0   TOPSOIL ONLY                   8   Apache tops + hands
   1   PRE-AMBLE                      8   + FM bell motif
   2   DRONE ON                       8   + reese bed, Amen hats
   3   WIND-UP MERCHANT               8   build: Amen snares, no kick/sub; rolls into a gap
   4   BOTTOM FEEDER                  8   drop A
   5   BOTTOM FEEDER >> FILL           1   roll + gap
   6   BOTTOM FEEDER II               8   drop A, reordered, second bass phrase
   7   CHOP SUEY                      8   drop, heavy block edits
   8   CHOP SUEY >> FILL               1
   9   HOLE                           1   the bar with no downbeat (launch on a phrase start)
  10   NOBODY HOME                    8   breakdown: reese Fm-Db, bell half time, no drums
  11   NOBODY HOME II                 8   breakdown: reese Eb-C, bell, hands return, sub pulse
  12   SWEAT EQUITY                   8   build 2 on Cold Sweat rolls
  13   F-ALL                          8   drop 2: brighter bell answer, legato reese, Cold Sweat tops
  14   F-ALL >> FILL                   1
  15   TERMINAL VELOCITY              8   drop 2, heaviest edits
  16   TERMINAL VELOCITY >> FILL       1   longer roll
  17   EXIT WOUND                     8   plain Amen + kick + sub: mix-out
  18   EXIT WOUND >> TOPS              8   tops + bell

Playing it: a FILL row plays its roll then loops, so launch it in the bar before the phrase you
want and launch the next groove row while it plays. (No automatic return: Live's LOM does not
expose clip follow actions.) A build row's last bar is its roll + gap; launch a drop during it.
Every lane in a row is written for that row, so whole-row launches never cut a lane by accident;
single clips can also be swapped between drop rows (same key, same kick grid).

How it is written (so the critique round can argue with it):
  - The Amen chop's home loop is 2 bars, so a UNIT is 2 bars. Edits move whole BLOCKS of slices,
    keeping each slice's offset in its block: the break's micro-timing survives (the snare at
    3.43 stays early) instead of being quantised.
  - Inside every 8-bar groove: three units repeat verbatim, the fourth disturbs. Lanes change
    together (drum edit, sub turn, bell rest), so a disturbance is one surprise, not several.
  - Kick + sub dominate by being legible, not loud: the sine sub starts half a beat after each
    kick and ends a quarter beat before the next, so onsets never coincide. BOOT-LEG doubles the
    break's kicks (the break's own lows are filtered off) but skips fast double kicks.
  - Bass is written half time, one pitch move per unit, around F1 in the E1-G1 sweet spot.
  - Juxtaposition: a dark reese (sub + 12) against a light FM bell motif in Ab5-G6 whose third
    note changes every unit; it resolves to F except before a disturbance, where it rests.

    python scripts/jungle_compose.py --dry-run   # note counts + legibility checks, no Live
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
TEST_SLOTS = (10, 11)   # click-test clips from the de-click pass; cleared before writing

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
    """Events -> (pitch, start, dur, vel). One hit per onset (the louder wins); each note gated to
    end GATE_MARGIN before the slice's own end or the next hit, whichever comes first."""
    ev = sorted((e for e in events if -1e-6 <= e[1] < length - 1e-6), key=lambda e: (e[1], -e[2]))
    kept = []
    for e in ev:
        if kept and abs(e[1] - kept[-1][1]) < 0.02:
            continue
        kept.append(e)
    out = []
    for k, (i, st, vel, want) in enumerate(kept):
        nxt = kept[k + 1][1] if k + 1 < len(kept) else length
        dur = min(brk.natural(i), nxt - st, want if want else 1e9) - GATE_MARGIN
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


# ----------------------------------------------------------------------
# Synth lanes: (pitch, start, dur, vel)
# ----------------------------------------------------------------------
KICK_PITCH = 41                  # F2 body (87 Hz) sits above the sub's F1 (44 Hz)
F1, AB1, BB1, C2, EB1 = 29, 32, 34, 36, 27

SUB_CELLS = {                    # one 2-bar unit each; notes answer the kicks at 0, 2.5, 4.5, 6.5
    "A":  [(F1, 0.5, 1.75), (F1, 3.0, 1.25), (F1, 5.0, 1.25), (AB1, 7.0, 0.9)],
    "A!": [(F1, 0.5, 1.75), (AB1, 3.0, 1.25), (BB1, 5.0, 1.25), (C2, 7.0, 0.5)],
    "B":  [(F1, 0.5, 1.75), (F1, 3.0, 1.25), (EB1, 5.0, 1.25), (EB1, 7.0, 0.9)],
    "B!": [(F1, 0.5, 1.75), (AB1, 3.0, 1.25), (C2, 5.0, 1.25), (BB1, 7.0, 0.9)],
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


def sub_line(cells, vel=112):
    out = []
    for n, c in enumerate(cells):
        if c:
            out += [(p, n * UNIT + s, d, vel) for p, s, d in SUB_CELLS[c]]
    return out


def reese_of(sub, *, legato=False, vel=96):
    """The reese doubles the sub an octave up, a touch longer; legato holds into the next note of
    the same unit (a heavier bed for drop 2)."""
    q = sorted(((p + 12, s, d + 0.25, vel) for p, s, d, _ in sub), key=lambda n: n[1])
    if legato:
        q = [(p, s, (q[k + 1][1] - s - 0.05) if k + 1 < len(q) and q[k + 1][1] // UNIT == s // UNIT else d, v)
             for k, (p, s, d, v) in enumerate(q)]
    return q


def fit_to_kicks(notes, kicks, length, *, gap=0.25, over_kicks=False):
    """Trim bass notes so none sounds over a kick (each ends `gap` beats before the next kick, loop
    wrap included) and none runs past the clip end. over_kicks=True only clamps to the clip end."""
    ks = sorted([k[1] for k in kicks] + [k[1] + length for k in kicks])
    out = []
    for p, s, d, v in notes:
        end = min(s + d, length - 0.02)
        if not over_kicks:
            nxt = next((k for k in ks if k > s + 1e-6), None)
            if nxt is not None:
                end = min(end, nxt - gap)
        if end - s >= 0.2:
            out.append((p, s, round(end - s, 4), v))
    return out


BELL_THIRD = [87, 89, 91, 87]    # Eb6 F6 G6 Eb6: the call's third note never sits still


def bell_call(u, n, *, resolve=True, drop2=False):
    notes = [(80, 0.0, 0.4, 110), (84, 0.75, 0.25, 96), (BELL_THIRD[n % 4], 1.5, 0.4, 104), (85, 2.0, 0.9, 100)]
    if drop2:                    # the answer climbs instead of falling
        notes += [(84, 4.75, 0.25, 96), (87, 5.5, 0.4, 102), (89, 6.0, 1.5, 106)]
    else:
        notes += [(84, 4.75, 0.25, 96), (82, 5.5, 0.4, 100), (77 if resolve else 80, 6.0, 1.5, 104)]
    return [(p, u + s, d, v) for p, s, d, v in notes]


def bell_phrase(drop2=False):
    """Three calls then a rest: the third ends unresolved, the rest lines up with the disturbance."""
    return bell_call(0, 0, drop2=drop2) + bell_call(8, 1, drop2=drop2) + bell_call(16, 2, resolve=False, drop2=drop2)


def bell_halftime(u):
    notes = [(80, 0.0, 0.8, 108), (84, 1.5, 0.5, 94), (87, 3.0, 0.8, 102), (85, 4.0, 1.8, 98),
             (84, 9.5, 0.5, 94), (82, 11.0, 0.8, 98), (77, 12.0, 3.0, 102)]
    return [(p, u + s, d, v) for p, s, d, v in notes]


# ----------------------------------------------------------------------
# Rows: each returns (length in beats, {track name: note quads})
# ----------------------------------------------------------------------


def row_topsoil_only():
    L = 32.0
    return L, {"TOPSOIL": break_notes(TOP, units([t_home] * 4), L)}


def row_preamble():
    L = 32.0
    return L, {"TOPSOIL": break_notes(TOP, units([t_home] * 4), L), "BELL-END": bell_phrase()}


def row_drone_on():
    L = 32.0
    amen = units([lambda u: a_hats(u, 0.8)] * 4)
    return L, {"TOPSOIL": break_notes(TOP, units([t_home] * 4), L), "BELL-END": bell_phrase(),
               "AMEN-DMENT": break_notes(AMEN, amen, L),
               "RASP-BERRY": [(41, 0.0, 15.5, 80), (37, 16.0, 15.5, 84)]}


def row_build1():
    L = 32.0
    amen = a_build1(0) + a_tops(8) + a_build3(16) + a_build4(24)
    top = t_home(0) + t_home(8) + t_home(16) + before(t_home(24), 30.5)
    bell = bell_call(0, 0) + bell_call(8, 1) + bell_call(16, 2, resolve=False)
    reese = [(41, 0.0, 15.9, 88), (44, 16.0, 7.9, 92), (48, 24.0, 6.4, 96)]   # roots climb, no sub
    return L, {"AMEN-DMENT": break_notes(AMEN, amen, L), "TOPSOIL": break_notes(TOP, top, L),
               "BELL-END": bell, "RASP-BERRY": reese}


def groove_row(amen_fns, sub_cells, *, drop2=False, sweat=False, top_hats=None, legato=False):
    L = UNIT * 4
    amen = units(amen_fns)
    kick = kick_layer(amen, L)
    sub = fit_to_kicks(sub_line(sub_cells), kick, L)
    top = t_turnaround(3 * UNIT)                    # hands on the disturbance unit
    if top_hats:
        top += units([lambda u: t_hats(u, top_hats)] * 4)
    lanes = {"AMEN-DMENT": break_notes(AMEN, amen, L), "BOOT-LEG": kick, "F-HOLE": sub,
             "RASP-BERRY": fit_to_kicks(reese_of(sub, legato=legato), kick, L, over_kicks=legato),
             "BELL-END": bell_phrase(drop2), "TOPSOIL": break_notes(TOP, top, L)}
    if sweat:
        lanes["SWEAT-SHOP"] = break_notes(SWEAT, units([lambda u: s_tops(u, 0.75)] * 4), L)
    return L, lanes


def fill_row(first, sub_note, *, roll_from=2.0, sweat=False, top_hats=None, legato=False):
    """One bar: `first` (break events up to roll_from), 16th snares for a beat, 32nds to 3.5, gap."""
    L = BAR
    amen = (before(first, roll_from) + roll(A_SNARE_16, roll_from, roll_from + 1.0, 0.25, 96, 112)
            + roll(A_SNARE_32, roll_from + 1.0, 3.5, 0.125, 112, 127))
    kick = kick_layer(amen, L)
    sub = fit_to_kicks([sub_note], kick, L)         # ends before the roll: the floor lets go
    top = before(block(TOP, 0, 4, 0, only={"bongo", "conga"}), roll_from)
    if top_hats:
        top += before(t_hats(0, top_hats), roll_from)
    lanes = {"AMEN-DMENT": break_notes(AMEN, amen, L), "BOOT-LEG": kick, "F-HOLE": sub,
             "RASP-BERRY": fit_to_kicks(reese_of(sub, legato=legato), kick, L, over_kicks=legato),
             "TOPSOIL": break_notes(TOP, top, L)}
    if sweat:
        lanes["SWEAT-SHOP"] = break_notes(SWEAT, before(s_tops(0, 0.75), roll_from), L)
    return L, lanes


def row_hole():
    """The bar with no downbeat: every lane silent until the snare at 0.99."""
    L = BAR
    amen = hole(block(AMEN, 0, 4, 0), 0.0, 0.95)
    kick = kick_layer(amen, L)
    sub = fit_to_kicks([(F1, 3.0, 0.9, 112)], kick, L)
    bell = hole(bell_call(0, 0), 0.0, 0.95)
    top = hole(t_home(0), 0.0, 0.95)
    return L, {"AMEN-DMENT": break_notes(AMEN, amen, L), "BOOT-LEG": kick, "F-HOLE": sub,
               "RASP-BERRY": fit_to_kicks(reese_of(sub), kick, L), "BELL-END": [n for n in bell if n[1] < L],
               "TOPSOIL": break_notes(TOP, before(top, L), L)}


def row_breakdown1():
    L = 32.0
    return L, {"RASP-BERRY": [(41, 0.0, 15.5, 90), (37, 16.0, 15.5, 90)],          # Fm, Db
               "BELL-END": bell_halftime(0) + bell_halftime(16)}


def row_breakdown2():
    L = 32.0
    top = t_hands(0, 0.9) + t_hands(8, 0.9) + t_home(16, 0.85) + t_home(24, 0.85)
    bell = bell_call(0, 0) + bell_call(8, 1) + bell_call(16, 2) + bell_call(24, 3, resolve=False)
    return L, {"RASP-BERRY": [(39, 0.0, 15.5, 92), (36, 16.0, 15.5, 94)],          # Eb, C
               "BELL-END": bell, "TOPSOIL": break_notes(TOP, top, L),
               "F-HOLE": [(F1, 16.0 + 4 * k, 0.5, 100) for k in range(4)]}       # the floor, just a pulse


def row_build2():
    L = 32.0
    sweat = s_tops(0) + s_tops(8) + s_roll8(16) + s_roll_end(24)
    amen = a_hats(8, 0.8) + a_hats(16, 0.8)
    top = t_hats(0) + t_hats(8) + t_hats(16) + before(t_hats(24), 30.5)
    bell = bell_call(0, 0, drop2=True) + bell_call(8, 1, drop2=True) + bell_call(16, 2, drop2=True)
    reese = [(41, 0.0, 15.9, 88), (37, 16.0, 7.9, 92), (39, 24.0, 6.4, 96)]   # F Db Eb -> F on the drop
    return L, {"SWEAT-SHOP": break_notes(SWEAT, sweat, L), "AMEN-DMENT": break_notes(AMEN, amen, L),
               "TOPSOIL": break_notes(TOP, top, L), "BELL-END": bell, "RASP-BERRY": reese}


def row_exit():
    L = 32.0
    amen = units([a_home] * 4)
    kick = kick_layer(amen, L)
    return L, {"AMEN-DMENT": break_notes(AMEN, amen, L), "BOOT-LEG": kick,
               "F-HOLE": fit_to_kicks(sub_line(["A", "A", "A", "A"]), kick, L),
               "TOPSOIL": break_notes(TOP, units([t_home] * 4), L)}


def row_exit_tops():
    L = 32.0
    amen = a_tops(0) + a_tops(8) + a_tops(16, 0.9) + a_tops(24, 0.8)
    bell = bell_call(0, 0) + bell_call(8, 1) + bell_call(16, 2)
    return L, {"AMEN-DMENT": break_notes(AMEN, amen, L), "TOPSOIL": break_notes(TOP, units([t_home] * 4), L),
               "BELL-END": bell}


ROWS = [
    ("TOPSOIL ONLY", row_topsoil_only),
    ("PRE-AMBLE", row_preamble),
    ("DRONE ON", row_drone_on),
    ("WIND-UP MERCHANT", row_build1),
    ("BOTTOM FEEDER", lambda: groove_row([a_home, a_home, a_home, a_edit1], ["A", "A", "A", "A!"])),
    ("BOTTOM FEEDER >> FILL", lambda: fill_row(block(AMEN, 0, 2, 0), (F1, 0.5, 1.25, 112))),
    ("BOTTOM FEEDER II", lambda: groove_row([a_home, a_home, a_reorder, a_edit1], ["B", "B", "B", "B!"])),
    ("CHOP SUEY", lambda: groove_row([a_reorder, a_reorder, a_reorder, a_edit2], ["B", "B", "B", "B!"],
                                     top_hats=0.6)),
    ("CHOP SUEY >> FILL", lambda: fill_row(block(AMEN, 4, 2, 0), (F1, 1.0, 0.9, 112), top_hats=0.6)),
    ("HOLE", row_hole),
    ("NOBODY HOME", row_breakdown1),
    ("NOBODY HOME II", row_breakdown2),
    ("SWEAT EQUITY", row_build2),
    ("F-ALL", lambda: groove_row([a_home, a_reorder, a_home, a_edit1], ["A", "A", "A", "A!"],
                                 drop2=True, sweat=True, top_hats=0.6, legato=True)),
    ("F-ALL >> FILL", lambda: fill_row(block(AMEN, 0, 2, 0), (F1, 0.5, 1.25, 112), sweat=True,
                                      top_hats=0.6, legato=True)),
    ("TERMINAL VELOCITY", lambda: groove_row([a_edit2, a_reorder, a_edit2, a_edit1], ["B", "B", "B", "B!"],
                                             drop2=True, sweat=True, top_hats=0.6, legato=True)),
    ("TERMINAL VELOCITY >> FILL", lambda: fill_row(block(AMEN, 0, 2, 0), (F1, 0.5, 0.75, 112), roll_from=1.5,
                                                  sweat=True, top_hats=0.6, legato=True)),
    ("EXIT WOUND", row_exit),
    ("EXIT WOUND >> TOPS", row_exit_tops),
]

LANES = ["AMEN-DMENT", "SWEAT-SHOP", "TOPSOIL", "BOOT-LEG", "F-HOLE", "RASP-BERRY", "BELL-END"]
NICK = {"AMEN-DMENT": "amen", "SWEAT-SHOP": "sweat", "TOPSOIL": "tops", "BOOT-LEG": "boot",
        "F-HOLE": "sub", "RASP-BERRY": "rasp", "BELL-END": "bell"}


def check(name, L, lanes):
    """Kick/sub legibility, loop wrap included: no sub onset within 35 ms of a kick, no sub note
    sounding over a kick, no note running past the clip end."""
    kicks = [s for _, s, _, _ in lanes.get("BOOT-LEG", [])]
    sub = lanes.get("F-HOLE", [])
    clash = sum(1 for _, s, _, _ in sub for k in kicks + [k + L for k in kicks] if abs(s - k) < 0.1)
    covered = sum(1 for k in kicks + [k + L for k in kicks] for _, s, d, _ in sub if s + 1e-6 < k < s + d - 1e-6)
    overrun = sum(1 for notes in lanes.values() for _, s, d, _ in notes if s + d > L + 1e-6)
    counts = "  ".join(f"{NICK[t]} {len(lanes[t])}" for t in LANES if t in lanes)
    issues = []
    if clash:
        issues.append(f"sub onset near kick x{clash}")
    if covered:
        issues.append(f"sub over kick x{covered}")
    if overrun:
        issues.append(f"notes past clip end x{overrun}")
    flag = f"   [warn] {', '.join(issues)}" if issues else ""
    print(f"  {name:<26} {L / 4:>4g} bars | {counts}{flag}")
    return len(issues)


def build_all():
    out, problems = [], 0
    for name, fn in ROWS:
        L, lanes = fn()
        problems += check(name, L, lanes)
        out.append((name, L, lanes))
    print(f"  {len(out)} rows; legibility problems: {problems}")
    return out


def compose(ch, tracks: dict):
    """Write every row's clips. tracks = {track name: index} (jungle_build passes it)."""
    from jungle_build import write_clip
    from thelmic.bridge.helpers import set_param

    rows = build_all()
    for name in ("SWEAT-SHOP", "TOPSOIL"):     # 174-BPM breaks: -40 cents plays them at exactly 170
        try:
            set_param(ch, tracks[name], 0, "Detune", value=-40.0)
        except Exception as e:
            print(f"  [skip] Detune on {name}: {e}")
    for name in ("AMEN-DMENT", "SWEAT-SHOP", "TOPSOIL"):
        for slot in TEST_SLOTS:
            try:
                ch.clear_clip(tracks[name], slot).result(timeout=5)
            except Exception:
                pass
    for i, (row, L, lanes) in enumerate(rows):
        for lane in LANES:
            t = tracks[lane]
            notes = lanes.get(lane)
            if notes:
                write_clip(ch, t, i, f"{row.lower()} / {NICK[lane]}", notes, L)
            else:
                try:
                    ch.clear_clip(t, i).result(timeout=5)   # an empty slot stops the lane on launch
                except Exception:
                    pass
        try:
            ch.set_scene_name(i, row).result(timeout=3)
        except Exception as e:
            print(f"  [skip] scene name {row}: {e}")
        print(f"  wrote row {i}: {row}")
    ch.set_launch_quantization(1).result(timeout=3)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Write the jungle session's clips into the running set.")
    ap.add_argument("--dry-run", action="store_true", help="note counts and legibility checks only")
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
            raise SystemExit(f"missing tracks {missing}: run scripts/jungle_build.py first")
        compose(ch, names)
    finally:
        ch.stop()


if __name__ == "__main__":
    main()
