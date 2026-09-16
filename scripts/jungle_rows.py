"""JUNGLE ROWS - playable rows built on the adopted jungle rules (tracks/2026-09-16_reaper/archetypes.md).

Three sub-sections, each a pre-drop row and two drop rows. Inside a sub-section the drums and the 16ths
hold while the riff changes (the riff is the fastest clock); between sub-sections the chop, the 16th
carrier and the sub's signature all turn over together.

  rows (Live)  sub-section  chop                        16ths (carrier)                 sub
  1-3          arrivals     Amen chop A                 THROW-UP: Amen hats             F-HOLE: clean sine, +30 st drop
  4-6          court        Amen chop B, busier ghosts  TOPSOIL: Apache hats + hands    SUB-POENA: shaped, sharper drop
  7-9          small print  Amen chop C, no break kick  SWEAT-SHOP: Cold Sweat, "a"s    SUB-LIMINAL: octave-doubled, glides
                                                        + BOOT-LEG two-step in drops

Rules followed: 170 BPM; slices placed exactly on 16ths with the drummer's feel inside each slice; bars
A-B-C-D inside a returning 4-bar group; kick on 1 and snares on 2 and 4 (except the two-step section,
where the programmed kick replaces the break's); no sub before a drop; no sidechain. The sub is in F# minor
on the fundamental F#0: struck at the front of the bar, mostly repeats and steps, about one change a bar
(half that under the two-step), and phrases that drop to a low "dum" on F#0 and leave a gap for the break.

    python scripts/jungle_rows.py --dry-run
    python scripts/jungle_rows.py
"""
from __future__ import annotations

import argparse
import os
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


def eight(pitch, bar, vel=(116, 100)):
    """Eight hits in a bar: every beat and its "a"."""
    return [(pitch, bar * 4.0 + beat + o, 0.4 if o == 0 else 0.2, vel[0] if o == 0 else vel[1])
            for beat in range(4) for o in (0.0, 0.75)]


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
# COURT OF APPEAL (SUB-POENA) - eight hits a bar, stepping down C# B A, then G# on the 1 and its "a" and the
# drop to the fundamental on beat 2, leaving the back of bar 4 open.
BASS_APPEAL = (eight(CS1, 0) + eight(B0, 1) + eight(A0, 2)
               + [(GS0, 12.0, 0.4, 116), (GS0, 12.75, 0.2, 100)] + hits(FS0, (13.0,), 1.0, 122))
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

# ---------------------------------------------------------------- rows: (scene, name, {track: (notes)})
ROWS = [
    (0, "WAITING ROOM", {"AMEN-DMENT": lane(AMEN, CHOP_A), "THROW-UP": "carrier_amen"}),
    (1, "ARRIVALS", {"AMEN-DMENT": lane(AMEN, CHOP_A), "THROW-UP": "carrier_amen", "F-HOLE": BASS_ARRIVALS}),
    (2, "DEPARTURES", {"AMEN-DMENT": lane(AMEN, CHOP_A), "THROW-UP": "carrier_amen", "F-HOLE": BASS_DEPARTURES}),
    (3, "THE DOCK", {"AMEN-DMENT": lane(AMEN, CHOP_B), "TOPSOIL": "carrier_apache"}),
    (4, "SUB-POENA SERVED", {"AMEN-DMENT": lane(AMEN, CHOP_B), "TOPSOIL": "carrier_apache", "SUB-POENA": BASS_SERVED}),
    (5, "COURT OF APPEAL", {"AMEN-DMENT": lane(AMEN, CHOP_B), "TOPSOIL": "carrier_apache", "SUB-POENA": BASS_APPEAL}),
    (6, "SMALL PRINT", {"AMEN-DMENT": lane(AMEN, CHOP_C), "SWEAT-SHOP": "carrier_sweat"}),
    (7, "SUBLIMINAL MESSAGE", {"AMEN-DMENT": lane(AMEN, CHOP_C), "SWEAT-SHOP": "carrier_sweat",
                               "BOOT-LEG": TWO_STEP, "SUB-LIMINAL": BASS_MESSAGE}),
    (8, "COMING DOWN", {"AMEN-DMENT": lane(AMEN, CHOP_C), "SWEAT-SHOP": "carrier_sweat",
                        "BOOT-LEG": TWO_STEP, "SUB-LIMINAL": BASS_COMING_DOWN}),
]
CARRIERS = {
    "carrier_amen": [(p, t, min(d, 0.22), v - 8) for p, t, d, v in lane(AMEN, CARRIER_AMEN)],
    "carrier_apache": lane(TOP, CARRIER_APACHE, cap=0.22, soften_off8=10),
    "carrier_sweat": lane(SWEAT, CARRIER_SWEAT, cap=0.22, soften_off8=18, accent_slots=(3, 7, 11, 15), accent=16),
}


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
    key = lambda p, s, d, v: (int(p), round(float(s), 3), round(float(d), 3), int(round(float(v))))
    have = sorted(key(x["pitch"], x["start_time"], x["duration"], x["velocity"]) for x in got)
    return have == sorted(key(*n) for n in notes)


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
                write_clip(ch, t, scene, name.lower(), notes, length)
                written += 1
                print(f"  row {scene + 1} {name}: wrote {track}")
            ch.set_scene_name(scene, name).result(timeout=3)
        print(f"  {written} clip(s) written, {skipped} already up to date")
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
