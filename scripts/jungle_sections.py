"""JUNGLE SECTIONS - one row per section on the six-lane grid, every lane in the row playing.

Simplicity is king (tracks/2026-09-16_jungle_scene_rules.md, and the user's read of the Reaper set): a row
holds one spine, one break, one 16th carrier and one bassline for 16-32 bars. The break is what moves. Drops
are not rows: the user pulls the sub by hand.

No clip on the grid repeats another, and nothing is left to chance: every note plays on every pass. The basslines
and 16ths come from clips the user has heard (tracks/2026-09-16_jungle_boards_clips.json); the chops are whole
blocks of their break, built the way the heard chops were (scripts/jungle_rows.py), with any variant pad written
in at a fixed place. Every spine keeps the kick on 1 and the snares on 2 and 4 in every bar.

  row  scene                spine                           chop                                   bass riff (4 bars)
  1    TRAPDOOR             kick 1, snares 2+4, kick &3     Amen A-B-C-D (the WAITING ROOM chop)    the user's descent, as written
  2    ARRIVALS             snare 4 leads, kick pickup      Amen, busier ghosts (CHOP_B)            C#1 struck x3 bars, falls to F#0
                            on the "a" of 4 in bar 4
  3    SUB-POENA SERVED     kicks on 3 and &3, as the       Cold Sweat A-B-C-D, ghost turnaround    C#1 / B0 C#1 / C#1 / B0 F#0
                            Cold Sweat drummer plays
  4    DEPARTURES           sparse: the &3 kick only in     Cold Sweat B-A-flip, snare up an        B0 / A0 / B0 / A0 F#0, twice
                            bars 2 and 4                    octave to end bar 4
  5    SUBLIMINAL MESSAGE   kick on the "a" of 3            Apache, break kicks dropped,            A0 on 1 and 2& x3 bars, falls
                                                            hand-drum turnaround                   to F#0, twice
  6    COMING DOWN          softer, a snare drag at the     Apache with its kicks, reversed snare   A0 / G#0 / A0 / F#0
                            end of bar 4                    into bar 3, snare-drag turnaround

The bass is a rhythmic device (tracks/2026-09-16_reaper/bass.md sections 11-13, and the user's ear): a 4-bar
riff that repeats exactly, as struck notes on one pitch or long notes a step apart, moving by repeats or 1-2
semitone steps up top, then falling on bar 4 - the riff's thinnest bar - to its lowest note, and jumping back
up when it comes round. Nothing walks bar to bar in one direction (that reads as a riser).

Every row also carries the two OTHER breaks (FILLS), so the crossfader (AMEN + spine on A, COLD-CUTS + CHOPPER
on B) has something on both sides in any row. Each fill is its own chop, suited to the row's spine, and uses the
chop dimensions deterministically - a snare roll, a pitched snare, a reversed snare, a stretched snare, doubled
kicks - never chance:
  AMEN-DMENT  rows 3-6  roll / sparse + stretch / reversed pickups, no kicks / pitched snares
  COLD-CUTS   rows 1,2,5,6  roll / stretch + pitched pickup / ghosts, no kicks / offset-snare drag
  CHOPPER     rows 1-4  straight / pitched / doubled kicks + snare repeats / sparse + stretch, no kicks

Each row's THROW-UP 16ths have their own velocity shape, subtle and the same every bar:
  1 straight   the beat leads, the e and a sit back
  2 lift       the "and" leads: offbeat hats
  3 push       the "a" leads, leaning into the next beat
  4 swell      each bar grows from its first 16th to its last
  5 3-3-2      accents on 16ths 1, 4, 7 of each half bar
  6 fall       each bar starts loud and sinks

The user plays and edits this set by hand, so by default this only fills EMPTY slots: a clip that differs from
what the script would write is kept and reported. --overwrite replaces those (notes in place, envelopes kept).

    python scripts/jungle_sections.py
    python scripts/jungle_sections.py --overwrite
"""
from __future__ import annotations

import json
import os
import sys

os.environ.setdefault("LIVE_CHANNEL_ENABLED", "1")
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(SCRIPTS_DIR)
sys.path.insert(0, REPO)
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from jungle_reset import ARCHIVE, index_of  # noqa: E402
from jungle_rows import (AMEN, CHOP_A, CHOP_B, CHOP_C, SWEAT, TOP, V_REV_SNARE, V_SNARE_UP12, VEL,  # noqa: E402
                         blocks, home_bars)

KICK, SNARE = 36, 38


def spine(bars):
    """bars: 4 lists of (beat, 'k' or 's', velocity) -> notes."""
    out = []
    for b, hits in enumerate(bars):
        for beat, drum, vel in hits:
            pad_note, dur = (KICK, 0.45) if drum == "k" else (SNARE, 0.6)
            if beat % 1 in (0.5, 0.75) and drum == "s":
                dur = 0.2
            out.append((pad_note, b * 4.0 + beat, dur if beat % 1 != 0.75 else min(dur, 0.2), vel))
    out.sort(key=lambda n: n[1])
    # a hit ends where the next hit on the same drum starts: Live shortens overlapping notes on one pitch anyway
    trimmed = []
    for i, (note, t, dur, vel) in enumerate(out):
        later = [t2 for n2, t2, _, _ in out[i + 1:] if n2 == note]
        trimmed.append((note, t, round(min(dur, later[0] - t) if later else dur, 4), vel))
    return trimmed


_CANON = [(0, "k", 122), (1, "s", 118), (2.5, "k", 112), (3, "s", 118)]
_LEAD4 = [(0, "k", 122), (1, "s", 108), (2.5, "k", 106), (3, "s", 124)]
_ROLL = [(0, "k", 122), (1, "s", 116), (2, "k", 104), (2.5, "k", 114), (3, "s", 116)]
_SPARSE = [(0, "k", 124), (1, "s", 104), (3, "s", 122)]
_SKIP = [(0, "k", 122), (1, "s", 118), (2.75, "k", 112), (3, "s", 118)]
_SOFT = [(0, "k", 116), (1, "s", 110), (2.5, "k", 102), (3, "s", 110)]
SPINES = [
    ("spine canon", spine([_CANON] * 4)),
    ("spine pickup", spine([_LEAD4] * 3 + [_LEAD4 + [(3.75, "k", 98)]])),
    ("spine roll", spine([_ROLL] * 4)),
    ("spine sparse", spine([_SPARSE, _SPARSE + [(2.5, "k", 108)], _SPARSE, _SPARSE + [(2.5, "k", 108)]])),
    ("spine skip", spine([_SKIP] * 3 + [_SKIP + [(2.5, "k", 100)]])),
    ("spine drag", spine([_SOFT] * 3 + [_SOFT + [(3.5, "s", 92), (3.75, "s", 100)]])),
]


def pad(note):
    return ("pad", note)


def _sweat_flip():
    a, b = home_bars(SWEAT)
    c = {**{k: v for k, v in b.items() if k < 8}, **{k: v for k, v in a.items() if k >= 8}}
    d = {**{k: v for k, v in a.items() if k < 12}, 12: 7, 14: 4, 15: pad(V_SNARE_UP12)}
    return [b, a, c, d]


def _apache_drag():
    bars = blocks(TOP, {12: 18, 13: 20, 14: 18, 15: 13})
    bars[1] = {**bars[1], 14: pad(V_REV_SNARE)}
    return bars


# variant pads (scripts/jungle_kits.py): 72 snare +12, 73 snare +7, 74 kick -3, 75 snare from 30% in, 76 reversed
# snare, 77 reversed hat/hand, 78 snare stretched x2, 79 stretched x1.5
PAD_LEN = {72: 0.25, 73: 0.25, 74: 0.5, 75: 0.25, 76: 0.5, 77: 0.5, 78: 1.0, 79: 0.75}
PAD_VEL = {75: 92}


def chop(brk, bars):
    """Notes from bar maps {16th: slice or pad(note)}: velocity by what the slice holds (off-16ths 12 softer),
    each hit ringing until the next one. Every note plays."""
    hits = []
    for b, bar in enumerate(bars):
        for slot, what in sorted(bar.items()):
            t = b * 4.0 + slot * 0.25
            if isinstance(what, tuple):
                hits.append((what[1], t, PAD_LEN.get(what[1], 0.5), PAD_VEL.get(what[1], 100)))
            else:
                vel = max(VEL.get(part, 96) for part in brk.parts[what]) - (12 if slot % 2 else 0)
                hits.append((36 + what, t, brk.natural(what), vel))
    hits.sort(key=lambda n: n[1])
    out = []
    for i, (note, t, natural, vel) in enumerate(hits):
        nxt = hits[i + 1][1] if i + 1 < len(hits) else 16.0
        out.append((note, round(t, 4), round(max(0.05, min(natural, nxt - t) - 0.012), 4), vel))
    return out


CHOPS = [
    ("amen A-B-C-D", chop(AMEN, CHOP_A)),
    ("amen busy", chop(AMEN, CHOP_B)),
    ("cold sweat A-B-C-D", chop(SWEAT, blocks(SWEAT, {13: 9, 14: 14, 15: 19}))),
    ("cold sweat flip", chop(SWEAT, _sweat_flip())),
    ("apache no kicks", chop(TOP, blocks(TOP, {13: 13, 14: 20, 15: 27}, drop_kicks=True))),
    ("apache drag", chop(TOP, _apache_drag())),
]

V_KICK_DOWN, V_OFFSET, V_REV_LIGHT, V_STRETCH_2, V_STRETCH_15, V_SNARE_UP7 = 74, 75, 77, 78, 79, 73


def _cold_roll():
    a, b = home_bars(SWEAT)
    return [a, b, a, {**{k: v for k, v in b.items() if k < 12}, 12: 17, 13: 12, 14: 17, 15: 12}]


def _cold_stretch():
    a, b = home_bars(SWEAT)
    c = {**{k: v for k, v in a.items() if k < 8}, **{k: v for k, v in b.items() if k >= 8}}
    d = {**{k: v for k, v in b.items() if k < 13}, 13: 9, 14: pad(V_SNARE_UP7), 15: 4}
    return [a, {**b, 14: pad(V_STRETCH_15)}, c, d]


def _cold_ghosts():
    bars = blocks(SWEAT, {13: 19, 14: 4, 15: 14}, drop_kicks=True)
    bars[1] = {**bars[1], 6: pad(V_REV_LIGHT)}
    return bars


def _cold_offset():
    a, b = home_bars(SWEAT)
    return [b, a, b, {**{k: v for k, v in a.items() if k < 12}, 12: 7, 14: pad(V_OFFSET), 15: pad(V_OFFSET)}]


def _apache_pitched():
    bars = blocks(TOP, {12: 25, 14: 22, 15: pad(V_SNARE_UP7)})
    bars[1] = {**bars[1], 14: pad(V_SNARE_UP12)}
    return bars


def _apache_doubles():
    a, b = home_bars(TOP)
    a2, b2 = {**a, 8: 0}, {**b, 8: 14}
    return [a2, b2, a2, {**{k: v for k, v in b2.items() if k < 12}, 12: 18, 13: 25, 14: 18, 15: 25}]


def _apache_sparse():
    ghosts = {s_ for s_, parts in enumerate(TOP.parts) if parts == ["ghost"]}
    bars = blocks(TOP, {12: pad(V_STRETCH_2)}, drop_kicks=True)
    return [{k: v for k, v in bar.items() if isinstance(v, tuple) or v not in ghosts} for bar in bars]


# Amen: the file is itself a chop, so the bars are written from its slice labels - kicks 0 1 7 12 20 25,
# snares 2 4 9 15 17 21, soft snares 6 11 14 19 23 24, hats 3 5 8 10 16 18 22, ghost 13
AMEN_ROLL = [{0: 0, 2: 3, 4: 2, 6: 16, 7: 13, 8: 7, 10: 12, 12: 21, 14: 5, 15: 24},
             {0: 0, 2: 8, 3: 13, 4: 15, 6: 10, 8: 20, 10: 1, 12: 9, 13: 13, 14: 18},
             {0: 25, 2: 3, 4: 17, 5: 13, 6: 16, 8: 7, 10: 12, 11: 14, 12: 21, 14: 22},
             {0: 0, 2: 5, 4: 2, 6: 18, 8: 12, 10: 20, 12: 21, 13: 21, 14: 21, 15: 21}]
AMEN_REVERSE = [{2: 3, 4: 2, 6: 5, 7: 13, 8: 16, 10: 10, 12: 9, 14: 22},
                {2: 8, 4: 15, 6: 18, 8: 5, 9: 13, 10: 3, 12: 21, 14: pad(V_REV_SNARE)},
                {2: 16, 4: 17, 6: 22, 7: 13, 8: 3, 10: 8, 12: 21, 14: 5},
                {2: 3, 4: 4, 6: 10, 8: 18, 10: 16, 11: 14, 12: 9, 14: pad(V_REV_SNARE)}]
AMEN_PITCHED = [{0: 0, 2: 3, 4: 4, 6: 5, 8: 7, 10: 1, 12: 9, 14: 16},
                {0: 0, 2: 8, 3: 13, 4: 21, 6: 10, 8: 12, 12: 17, 14: 22, 15: pad(V_SNARE_UP7)},
                {0: 25, 2: 3, 4: 2, 6: 18, 8: 7, 10: 20, 12: 15, 14: 5},
                {0: 0, 2: 8, 4: 4, 6: 10, 8: 12, 12: 21, 13: 24, 14: pad(V_SNARE_UP12), 15: 23}]
AMEN_SPARSE = [dict(bar) for bar in CHOP_C]
AMEN_SPARSE[1] = {**AMEN_SPARSE[1], 14: pad(V_STRETCH_2)}

# (row, break track) -> (clip name, notes): the breaks that aren't a row's own
FILLS = {
    (0, "COLD-CUTS"): ("cold sweat roll", chop(SWEAT, _cold_roll())),
    (0, "CHOPPER"): ("apache straight", chop(TOP, blocks(TOP, {13: 8, 14: 11, 15: 13}))),
    (1, "COLD-CUTS"): ("cold sweat stretch", chop(SWEAT, _cold_stretch())),
    (1, "CHOPPER"): ("apache pitched", chop(TOP, _apache_pitched())),
    (2, "AMEN-DMENT"): ("amen roll", chop(AMEN, AMEN_ROLL)),
    (2, "CHOPPER"): ("apache doubles", chop(TOP, _apache_doubles())),
    (3, "AMEN-DMENT"): ("amen sparse stretch", chop(AMEN, AMEN_SPARSE)),
    (3, "CHOPPER"): ("apache sparse stretch", chop(TOP, _apache_sparse())),
    (4, "AMEN-DMENT"): ("amen reverse", chop(AMEN, AMEN_REVERSE)),
    (4, "COLD-CUTS"): ("cold sweat ghosts", chop(SWEAT, _cold_ghosts())),
    (5, "AMEN-DMENT"): ("amen pitched", chop(AMEN, AMEN_PITCHED)),
    (5, "COLD-CUTS"): ("cold sweat offset", chop(SWEAT, _cold_offset())),
}


def check_chops():
    """Every chop on the grid is its own, and every bar keeps the break's snare on 2."""
    every = [n for _, n in CHOPS] + [n for _, n in FILLS.values()]
    assert len({tuple(n) for n in every}) == len(every), "two chops are the same"
    for name, notes in list(CHOPS) + list(FILLS.values()):
        for b in range(4):
            on_two = [n for n in notes if abs(n[1] - (b * 4 + 1.0)) < 1e-6]
            assert on_two, f"{name}: bar {b + 1} has nothing on 2"

BREAK_LANES = ("AMEN-DMENT", "COLD-CUTS", "CHOPPER")
# the sub lane: BOO-MERANGUE, the 808 chosen 2026-09-17 (F-HOLE, TONE-DEAF and WOBBLE-BOARD were dropped)
SUB_LANES = ("BOO-MERANGUE",)
VARIANT_FROM = 72
FS0, GS0, A0, B0, CS1 = 30, 32, 33, 35, 37
SHORT, HELD = 100, 110


def struck(pitch):
    """A bar of one pitch: short on 1 and 1&, held on 2, short on 3&, held into 4."""
    return [(pitch, 0.0, 0.4, SHORT), (pitch, 0.5, 0.4, SHORT), (pitch, 1.0, 1.25, HELD),
            (pitch, 2.5, 0.4, SHORT), (pitch, 3.0, 0.75, HELD)]


RIFFS = {
    "ARRIVALS": [struck(CS1), struck(CS1), struck(CS1),
                 [(CS1, 0.0, 0.4, SHORT), (CS1, 0.5, 0.4, SHORT), (FS0, 1.0, 1.5, HELD)]],
    "SUB-POENA SERVED": [[(CS1, 0.0, 3.5, HELD)],
                         [(B0, 0.0, 1.5, HELD), (CS1, 2.0, 1.5, HELD)],
                         [(CS1, 0.0, 3.5, HELD)],
                         [(B0, 0.0, 1.0, HELD), (FS0, 1.0, 1.5, HELD)]],
    "DEPARTURES": [[(B0, 0.0, 3.5, HELD)], [(A0, 0.0, 3.5, HELD)], [(B0, 0.0, 3.5, HELD)],
                   [(A0, 0.0, 1.5, HELD), (FS0, 1.5, 1.5, HELD)]],
    "SUBLIMINAL MESSAGE": [[(A0, 0.0, 1.25, HELD), (A0, 1.5, 2.25, HELD)]] * 3
                          + [[(FS0, 0.0, 2.0, HELD)]],
    "COMING DOWN": [[(A0, 0.0, 3.5, HELD)], [(GS0, 0.0, 3.5, HELD)], [(A0, 0.0, 3.5, HELD)],
                    [(FS0, 0.0, 2.0, HELD)]],
}
# scene name, break track, bass: ("as is", archive track, key) | ("riff", clip bars)
ROWS = [
    ("TRAPDOOR", "AMEN-DMENT", ("as is", "F-HOLE", 21)),
    ("ARRIVALS", "AMEN-DMENT", ("riff", 4)),
    ("SUB-POENA SERVED", "COLD-CUTS", ("riff", 4)),
    ("DEPARTURES", "COLD-CUTS", ("riff", 8)),
    ("SUBLIMINAL MESSAGE", "CHOPPER", ("riff", 8)),
    ("COMING DOWN", "CHOPPER", ("riff", 4)),
]


def check_riff(scene, bars):
    """Up top only repeats and 1-2 semitone steps; bar 4 sounds the least and ends on the riff's lowest note."""
    notes = [n for b, bar in enumerate(bars) for n in [(p, b * 4.0 + st) for p, st, _, _ in bar]]
    pitches = [p for p, _ in notes]
    exit_from = next(i for i, (_, t) in enumerate(notes) if t >= 12.0)
    for a, b in zip(pitches[:exit_from], pitches[1:exit_from]):
        assert abs(b - a) <= 2, f"{scene}: a hop of {abs(b - a)} before the exit bar"
    assert pitches[-1] == min(pitches), f"{scene}: bar 4 doesn't end on the lowest note"
    sounding = [sum(d for _, _, d, _ in bar) for bar in bars]
    assert sounding[3] < min(sounding[:3]), f"{scene}: bar 4 isn't the thinnest bar ({sounding})"


def bassline(scene, spec):
    """(shape, notes, length) for a row's bass."""
    if spec[0] == "riff":
        bars = RIFFS[scene]
        check_riff(scene, bars)
        clip_bars = spec[1]
        notes = [(p, round((k * 4 + b) * 4.0 + st, 4), d, v)
                 for k in range(clip_bars // 4) for b, bar in enumerate(bars) for p, st, d, v in bar]
        return f"riff x{clip_bars // 4}", notes, clip_bars * 4.0
    clip = archived(spec[1], spec[2])
    return "as written", plain(clip), float(clip["length"])


def moves(notes):
    pitches = [n[0] for n in sorted(notes, key=lambda n: n[1])]
    return [abs(b - a) for a, b in zip(pitches, pitches[1:] + pitches[:1])]
SIXTEENTHS = ("THROW-UP", "arrivals")


def _straight(step):
    return {0: 10, 1: -8, 2: 2, 3: -8}[step % 4]


def _lift(step):
    return {0: 0, 1: -10, 2: 14, 3: -4}[step % 4]


def _push(step):
    return {0: 4, 1: -10, 2: -4, 3: 12}[step % 4]


def _swell(step):
    return round(-12 + step * 1.6) + (4 if step % 4 == 0 else 0)


def _three_three_two(step):
    return 14 if step % 8 in (0, 3, 6) else -8


def _fall(step):
    return round(12 - step * 1.6) + (4 if step % 4 == 0 else 0)


# row -> (name, velocity offset for 16th step 0..15 of the bar)
SHAPES = [("straight", _straight), ("lift", _lift), ("push", _push), ("swell", _swell), ("3-3-2", _three_three_two),
          ("fall", _fall)]


def shaped(notes, shape):
    out = []
    for p, s, d, v in notes:
        step = int(round(s * 4)) % 16
        out.append((p, s, d, max(1, min(127, v + shape(step)))))
    return out


def archived(track, key):
    with open(ARCHIVE) as fh:
        clips = json.load(fh)
    field = "slot" if isinstance(key, int) else "name"
    return next(c for c in clips if c["track"] == track and c[field] == key)


def plain(clip):
    """(pitch, start, duration, velocity) for every note that isn't a variant pad, all certain."""
    return sorted((int(n["pitch"]), float(n["start_time"]), float(n["duration"]), int(round(n["velocity"])))
                  for n in clip["notes"] if n["pitch"] < VARIANT_FROM)


def no_overlap(notes, length):
    """Each bass note ends by the time the next one starts (the loop wraps). Lines written as slides for a
    gliding voice overlapped by 35 ms; on a sub that doesn't glide, two sines sounding together click."""
    notes = sorted(notes, key=lambda n: n[1])
    out = []
    for i, (p, st, d, v) in enumerate(notes):
        nxt = notes[i + 1][1] if i + 1 < len(notes) else notes[0][1] + length
        out.append((p, st, round(max(0.05, min(d, nxt - st)), 4), v))
    return out


def put(ch, t, slot, name, notes, length):
    """Replace the notes of a clip that already has this length, so its clip envelopes survive; create it
    otherwise."""
    from jungle_build import write_clip, _helpers
    try:
        props = ch.get_clip_props(t, slot).result(timeout=5)
    except Exception:
        props = {}
    if props.get("length") is not None and abs(float(props["length"]) - length) < 1e-3:
        ch.add_notes_to_clip(t, slot, _helpers().to_clip_notes(notes), replace=True).result(timeout=10)
        ch.set_clip_name(t, slot, name).result(timeout=3)
    else:
        write_clip(ch, t, slot, name, notes, length)


def same(ch, t, slot, notes, length):
    try:
        props = ch.get_clip_props(t, slot).result(timeout=5)
        if props.get("length") is None or abs(float(props["length"]) - length) > 1e-3:
            return False
        got = ch.get_clip_notes(t, slot).result(timeout=10)
    except Exception:
        return False
    got = got.get("notes", got) if isinstance(got, dict) else got
    if len(got) != len(notes):
        return False
    have = sorted((int(n["pitch"]), float(n["start_time"]), float(n["duration"]), int(round(float(n["velocity"]))),
                   float(n.get("probability", 1.0))) for n in got)
    want = sorted((p, s, d, v, 1.0) for p, s, d, v in notes)
    return all(a[0] == b[0] and a[3] == b[3] and abs(a[1] - b[1]) < 2e-3 and abs(a[2] - b[2]) < 2e-3
               and abs(a[4] - b[4]) < 1e-3 for a, b in zip(have, want))


def main(argv=None):
    import argparse
    from thelmic.live_channel import LiveChannel
    ap = argparse.ArgumentParser(description="Write the section rows: empty slots only, unless --overwrite.")
    ap.add_argument("--overwrite", action="store_true", help="replace clips that differ from the script")
    args = ap.parse_args(argv)
    check_chops()
    ch = LiveChannel(lower_priority=False)
    ch.start()
    try:
        sixteenths = archived(*SIXTEENTHS)
        from jungle_reset import track_names
        present = set(track_names(ch))
        for row, (scene, brk, bass_spec) in enumerate(ROWS):
            bass_shape, bass_notes, bass_len = bassline(scene, bass_spec)
            shape_name, shape = SHAPES[row]
            lanes = [("SPINE-TINGLER", *SPINES[row], 16.0), (brk, *CHOPS[row], 16.0),
                     ("THROW-UP", f"16ths {shape_name}", shaped(plain(sixteenths), shape), float(sixteenths["length"])),
                     ] + [(track, *FILLS[(row, track)], 16.0) for track in BREAK_LANES if (row, track) in FILLS] \
                + [(sub_lane, scene.lower(), no_overlap(bass_notes, bass_len), bass_len)
                   for sub_lane in SUB_LANES if sub_lane in present]
            wrote, kept = [], []
            for track, name, notes, length in lanes:
                t = index_of(ch, track)
                if ch.get_clip_props(t, row).result(timeout=5).get("length") is None:
                    put(ch, t, row, name, notes, length)
                    wrote.append(track)
                elif same(ch, t, row, notes, length):
                    continue
                elif args.overwrite:
                    put(ch, t, row, name, notes, length)
                    wrote.append(track)
                else:
                    kept.append(track)
            print(f"  row {row + 1} {scene:<19} "
                  + (f"wrote {', '.join(wrote)}" if wrote else "nothing to write")
                  + (f" | kept yours: {', '.join(kept)}" if kept else ""))
    finally:
        ch.stop()


if __name__ == "__main__":
    main()
