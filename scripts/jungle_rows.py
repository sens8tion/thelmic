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
where the programmed kick replaces the break's); no sub before a drop; the sub moves about once a bar
(the two-step section's barely moves); the second bar of a 2-bar riff sits lower; no sidechain.

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

# ---------------------------------------------------------------- sub riffs (F minor)
DB1, EB1, F1, G1, AB1, BB1, C2 = 25, 27, 29, 31, 32, 34, 36


def twice(riff):
    return riff + [(p, s + 8.0, d, v) for p, s, d, v in riff]


def octave_double(riff, home):
    """An on-key octave-crossing double as the pickup back into the loop: the riff's home note on the "e" of
    beat 4, the same note an octave up on the "and" (held an 8th), landing back on the home note on the 1.
    Once per 4 bars: octave moves are rare in the reference (1.8% of bass transitions)."""
    trimmed = [(p, s, round(min(d, 15.0 - s - 0.02), 4), v) for p, s, d, v in riff if s < 15.0]
    return trimmed + [(home, 15.25, 0.22, 112), (home + 12, 15.5, 0.45, 106)]


RIFF_ARRIVALS = octave_double(twice([(F1, 0.0, 1.0, 116), (F1, 1.5, 0.5, 106), (F1, 2.5, 0.75, 110),
                                     (EB1, 4.0, 1.25, 114), (EB1, 5.5, 0.5, 106)]), F1)
RIFF_BAGGAGE = octave_double(twice([(AB1, 0.0, 0.75, 116), (AB1, 0.75, 0.5, 104), (AB1, 2.0, 1.25, 110),
                                    (G1, 4.0, 0.5, 114), (G1, 4.75, 1.0, 106), (G1, 6.5, 0.5, 104)]), AB1)
RIFF_SERVED = octave_double(twice([(F1, 0.0, 0.5, 118), (F1, 0.75, 0.25, 104), (F1, 1.5, 0.5, 110), (AB1, 2.5, 0.5, 112),
                                   (EB1, 4.0, 0.5, 116), (EB1, 4.75, 0.25, 104), (EB1, 5.5, 0.75, 110)]), F1)
RIFF_CONTEMPT = octave_double(twice([(C2, 0.0, 0.5, 118), (C2, 0.75, 0.25, 104), (BB1, 1.5, 0.5, 110), (BB1, 2.5, 0.5, 108),
                                     (AB1, 4.0, 0.5, 116), (AB1, 4.75, 0.25, 104), (AB1, 5.5, 0.5, 110)]), C2)
# barely moving, with overlaps into the changes so the glide slides between them; the octave double here
# overlaps too, so it slides up the octave instead of jumping
RIFF_MESSAGE = [(F1, 0.0, 3.0, 112), (F1, 4.0, 2.0, 106), (F1, 6.5, 1.65, 108),
                (EB1, 8.0, 3.0, 112), (EB1, 12.0, 2.9, 106), (F1, 14.75, 0.65, 108), (F1 + 12, 15.25, 0.7, 104)]
RIFF_CONTROL = [(AB1, 0.0, 3.0, 112), (AB1, 4.0, 2.25, 106), (AB1, 6.5, 1.65, 108),
                (G1, 8.0, 3.0, 112), (G1, 12.0, 2.7, 106), (AB1, 14.75, 0.65, 108), (AB1 + 12, 15.25, 0.7, 104)]

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
    (1, "ARRIVALS", {"AMEN-DMENT": lane(AMEN, CHOP_A), "THROW-UP": "carrier_amen", "F-HOLE": RIFF_ARRIVALS}),
    (2, "BAGGAGE CLAIM", {"AMEN-DMENT": lane(AMEN, CHOP_A), "THROW-UP": "carrier_amen", "F-HOLE": RIFF_BAGGAGE}),
    (3, "THE DOCK", {"AMEN-DMENT": lane(AMEN, CHOP_B), "TOPSOIL": "carrier_apache"}),
    (4, "SUB-POENA SERVED", {"AMEN-DMENT": lane(AMEN, CHOP_B), "TOPSOIL": "carrier_apache", "SUB-POENA": RIFF_SERVED}),
    (5, "CONTEMPT OF COURT", {"AMEN-DMENT": lane(AMEN, CHOP_B), "TOPSOIL": "carrier_apache", "SUB-POENA": RIFF_CONTEMPT}),
    (6, "SMALL PRINT", {"AMEN-DMENT": lane(AMEN, CHOP_C), "SWEAT-SHOP": "carrier_sweat"}),
    (7, "SUBLIMINAL MESSAGE", {"AMEN-DMENT": lane(AMEN, CHOP_C), "SWEAT-SHOP": "carrier_sweat",
                               "BOOT-LEG": TWO_STEP, "SUB-LIMINAL": RIFF_MESSAGE}),
    (8, "MIND CONTROL", {"AMEN-DMENT": lane(AMEN, CHOP_C), "SWEAT-SHOP": "carrier_sweat",
                         "BOOT-LEG": TWO_STEP, "SUB-LIMINAL": RIFF_CONTROL}),
]
CARRIERS = {
    "carrier_amen": [(p, t, min(d, 0.22), v - 8) for p, t, d, v in lane(AMEN, CARRIER_AMEN)],
    "carrier_apache": lane(TOP, CARRIER_APACHE, cap=0.22, soften_off8=10),
    "carrier_sweat": lane(SWEAT, CARRIER_SWEAT, cap=0.22, soften_off8=18, accent_slots=(3, 7, 11, 15), accent=16),
}


def changes_per_bar(riff):
    pitches = [p for p, *_ in sorted(riff, key=lambda n: n[1])]
    moves = sum(1 for a, b in zip(pitches, pitches[1:] + pitches[:1]) if a != b)
    return moves / BARS


def dry_run():
    for scene, name, lanes in ROWS:
        parts = []
        for track, notes in lanes.items():
            notes = CARRIERS.get(notes, notes) if isinstance(notes, str) else notes
            extra = f", {changes_per_bar(notes):.2f} changes/bar" if track in ("F-HOLE", *SUB_VOICES) else ""
            parts.append(f"{track} {len(notes)}{extra}")
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


def ensure_sub_voices(ch):
    from jungle_space import set_number, set_string, _param
    from jungle_build import write_clip
    scenes = ch.get_scene_count().result(timeout=5)["count"]
    for voice, settings in SUB_VOICES.items():
        idx = names(ch)
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
        write_clip(ch, t, test_slot, "test", [(29, 0.0, 3.5, 120)], 4.0)
        peak = meter(ch, voice, t, test_slot)
        ch.clear_clip(t, test_slot).result(timeout=5)
        print(f"  {voice}: F1 test note meters {peak:.3f} | {summary}")
        if peak <= 0.01:
            raise SystemExit(f"{voice} is silent - stopping before writing rows")


def build():
    from jungle_build import write_clip
    from thelmic.live_channel import LiveChannel
    ch = LiveChannel(lower_priority=False)
    ch.start()
    try:
        ch.set_launch_quantization(0).result(timeout=3)
        ensure_sub_voices(ch)
        idx = names(ch)
        for scene, name, lanes in ROWS:
            for track, notes in lanes.items():
                notes = CARRIERS[notes] if isinstance(notes, str) else notes
                t = idx[track]
                try:
                    ch.clear_clip(t, scene).result(timeout=5)
                except Exception:
                    pass
                write_clip(ch, t, scene, name.lower(), notes, LEN)
            ch.set_scene_name(scene, name).result(timeout=3)
            print(f"  row {scene + 1}: {name}")
    finally:
        try:
            ch.stop_all_clips().result(timeout=3)
            ch.set_launch_quantization(1).result(timeout=3)
        finally:
            ch.stop()


def main(argv=None):
    ap = argparse.ArgumentParser(description="Write the adopted-rules jungle rows into the session.")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    dry_run()
    if not args.dry_run:
        build()


if __name__ == "__main__":
    main()
