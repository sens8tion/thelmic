"""JUNGLE SECTIONS - one row per section on the six-lane grid, every lane in the row playing.

Simplicity is king (tracks/2026-09-16_jungle_scene_rules.md, and the user's read of the Reaper set): a row
holds one spine, one break, one 16th carrier and one bassline for 16-32 bars. The break is what moves. Drops
are not rows: the user pulls the sub by hand.

No clip on the grid repeats another, and nothing is left to chance: every note plays on every pass. The basslines
and 16ths come from clips the user has heard (tracks/2026-09-16_jungle_boards_clips.json); the chops are whole
blocks of their break, built the way the heard chops were (scripts/jungle_rows.py), with any variant pad written
in at a fixed place. Every spine keeps the kick on 1 and the snares on 2 and 4 in every bar.

  row  scene                spine                           chop                                   bass
  1    TRAPDOOR             kick 1, snares 2+4, kick &3     Amen A-B-C-D (the WAITING ROOM chop)    hand-written descent
  2    ARRIVALS             snare 4 leads, kick pickup      Amen, busier ghosts (CHOP_B)            arrivals
                            on the "a" of 4 in bar 4
  3    SUB-POENA SERVED     kicks on 3 and &3, as the       Cold Sweat A-B-C-D, ghost turnaround    sub-poena served,
                            Cold Sweat drummer plays                                               one note on the one
  4    DEPARTURES           sparse: the &3 kick only in     Cold Sweat B-A-flip, snare up an        departures (8 bars)
                            bars 2 and 4                    octave to end bar 4
  5    SUBLIMINAL MESSAGE   kick on the "a" of 3            Apache, break kicks dropped,            subliminal message
                                                            hand-drum turnaround                   (8 bars)
  6    COMING DOWN          softer, a snare drag at the     Apache with its kicks, reversed snare   coming down
                            end of bar 4                    into bar 3, snare-drag turnaround

Each row's THROW-UP 16ths have their own velocity shape, subtle and the same every bar:
  1 straight   the beat leads, the e and a sit back
  2 lift       the "and" leads: offbeat hats
  3 push       the "a" leads, leaning into the next beat
  4 swell      each bar grows from its first 16th to its last
  5 3-3-2      accents on 16ths 1, 4, 7 of each half bar
  6 fall       each bar starts loud and sinks

Writes only clips that differ from what is there.

    python scripts/jungle_sections.py
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
from jungle_rows import (AMEN, CHOP_A, CHOP_B, SWEAT, TOP, V_REV_SNARE, V_SNARE_UP12, VEL,  # noqa: E402
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


def chop(brk, bars):
    """Notes from bar maps {16th: slice or pad(note)}: velocity by what the slice holds (off-16ths 12 softer),
    each hit ringing until the next one. Every note plays."""
    hits = []
    for b, bar in enumerate(bars):
        for slot, what in sorted(bar.items()):
            t = b * 4.0 + slot * 0.25
            if isinstance(what, tuple):
                hits.append((what[1], t, 0.5, 100))
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

BREAK_LANES = ("AMEN-DMENT", "COLD-CUTS", "CHOPPER")
VARIANT_FROM = 72
# scene name, break track, (bass track, bass clip name or slot in the archive)
ROWS = [
    ("TRAPDOOR", "AMEN-DMENT", ("F-HOLE", 21)),
    ("ARRIVALS", "AMEN-DMENT", ("F-HOLE", "arrivals")),
    ("SUB-POENA SERVED", "COLD-CUTS", ("SUB-POENA", "sub-poena served")),
    ("DEPARTURES", "COLD-CUTS", ("F-HOLE", "departures")),
    ("SUBLIMINAL MESSAGE", "CHOPPER", ("SUB-LIMINAL", "subliminal message")),
    ("COMING DOWN", "CHOPPER", ("SUB-LIMINAL", "coming down")),
]
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


def single_on_the_one(notes, length):
    """A 16th double on the one (the same note twice) becomes one note lasting as long as the pair: the user
    didn't like the doubles on SUB-POENA SERVED."""
    notes = sorted(notes, key=lambda n: n[1])
    out, skip = [], set()
    for i, (p, st, d, v) in enumerate(notes):
        if i in skip:
            continue
        nxt = notes[i + 1] if i + 1 < len(notes) else None
        if st % 4 == 0 and nxt and nxt[0] == p and abs(nxt[1] - (st + 0.25)) < 1e-6:
            out.append((p, st, round(nxt[1] + nxt[2] - st, 4), v))
            skip.add(i + 1)
        else:
            out.append((p, st, d, v))
    return out


BASS_EDITS = {"SUB-POENA SERVED": single_on_the_one}


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


def main():
    from thelmic.live_channel import LiveChannel
    ch = LiveChannel(lower_priority=False)
    ch.start()
    try:
        sixteenths = archived(*SIXTEENTHS)
        for row, (scene, brk, (bass_from, bass_key)) in enumerate(ROWS):
            bass = archived(bass_from, bass_key)
            shape_name, shape = SHAPES[row]
            lanes = [("SPINE-TINGLER", *SPINES[row], 16.0), (brk, *CHOPS[row], 16.0),
                     ("THROW-UP", f"16ths {shape_name}", shaped(plain(sixteenths), shape), float(sixteenths["length"])),
                     ("F-HOLE", bass["name"] or "trapdoor",
                      no_overlap(BASS_EDITS.get(scene, lambda n, _: n)(plain(bass), float(bass["length"])),
                                 float(bass["length"])),
                      float(bass["length"]))]
            written = []
            for track, name, notes, length in lanes:
                t = index_of(ch, track)
                if not same(ch, t, row, notes, length):
                    put(ch, t, row, name, notes, length)
                    written.append(track)
            for other in BREAK_LANES:
                if other != brk:
                    t = index_of(ch, other)
                    if ch.get_clip_props(t, row).result(timeout=5).get("length") is not None:
                        ch.clear_clip(t, row).result(timeout=5)
                        written.append(f"-{other}")
            ch.set_scene_name(row, scene).result(timeout=3)
            print(f"  row {row + 1} {scene:<19} {SPINES[row][0]:<13} {CHOPS[row][0]:<19} 16ths {shape_name:<8} "
                  f"bass {bass['name'] or 'hand-written'} "
                  f"({bass['length'] / 4:g} bars) | {'wrote ' + ', '.join(written) if written else 'unchanged'}")
    finally:
        ch.stop()


if __name__ == "__main__":
    main()
