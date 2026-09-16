"""JUNGLE BALANCE - fader levels for the section boards, so each role can be heard.

Each section is balanced on its drop row, with its four lanes playing together (their clips are launched
on the same bar; the whole scene isn't, because some rows also hold RAW-DEAL audio clips). Every track
meter is read over a full 4-bar loop, since chance notes change the peaks from pass to pass. Faders only.

  role targets (track meter, 0.85 ~ 0 dBFS)   sub 0.80   spine 0.77   main break 0.72   16ths 0.62
  master ceiling on each drop                 0.85

    python scripts/jungle_balance.py
"""
from __future__ import annotations

import os
import sys
import time

os.environ.setdefault("LIVE_CHANNEL_ENABLED", "1")
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(SCRIPTS_DIR))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from jungle_levels import db_to_norm, norm_to_db  # noqa: E402
from jungle_sidechain import parse_display as parse  # noqa: E402

TARGET = {"sub": 0.80, "spine": 0.77, "break": 0.72, "16ths": 0.62}
STAGE = 0.80                # a sub alone at unity fader
MASTER_CEILING = 0.85
TOL_DB = 0.75
PASSES = 3
LOOP_S = 16 * 60.0 / 170 + 0.4
POLL_S = 0.04
# section: drop row (scene index), {track: role}
SECTIONS = [
    ("arrivals", 1, {"F-HOLE": "sub", "SPINE-TINGLER": "spine", "AMEN-DMENT": "break", "THROW-UP": "16ths"}),
    ("court", 9, {"SUB-POENA": "sub", "SPINAL-TAP": "spine", "COLD-CUTS": "break", "TOPSOIL": "16ths"}),
    ("print", 17, {"SUB-LIMINAL": "sub", "SPINELESS": "spine", "CHOPPER": "break", "SWEAT-SHOP": "16ths"}),
]


def names(ch):
    n = ch.get_session_info().result(timeout=5)["track_count"]
    out = {}
    for i in range(n):
        out.setdefault(ch.get_track_info(i).result(timeout=5)["name"], i)
    return out


def play_and_measure(ch, idx, row, tracks):
    ch.stop_all_clips().result(timeout=3)
    time.sleep(0.4)
    for tr in tracks:
        ch.fire_clip(idx[tr], row).result(timeout=3)       # launch quantization 1 bar: they start together
    time.sleep(60.0 / 170 * 4 + 0.3)                      # wait out the launch bar
    peaks = {}
    end = time.monotonic() + LOOP_S
    while time.monotonic() < end:
        for m in ch.get_all_meters().result(timeout=2)["meters"]:
            peaks[m["name"]] = max(peaks.get(m["name"], 0.0), m.get("left", 0.0), m.get("right", 0.0))
        time.sleep(POLL_S)
    return peaks


def stage_subs(ch, idx):
    """Gain staging before faders: each sub's Operator Volume is set so the sub alone reads ~0.80 at unity
    fader. Fresh Operators come in at -18 dB, which left the faders pinned at +6 dB and still short. Any
    leftover EQ trim on the sub track is reset to 0 dB first."""
    from jungle_space import find_device, set_number, _param
    for section, row, roles in SECTIONS:
        sub = next(tr for tr, role in roles.items() if role == "sub")
        t = idx[sub]
        eq = find_device(ch, t, "EQ Eight")
        if eq is not None and abs(float(_param(ch, t, eq, "Output")["value"])) > 0.05:
            set_number(ch, t, eq, "Output", 0.0)
        ch.set_track_volume(t, 0.85).result(timeout=3)
        for _ in range(3):
            pk = play_and_measure(ch, idx, row, [sub]).get(sub, 0.0)
            vol = float(parse(_param(ch, t, 0, "Volume")["display"]))
            err = norm_to_db(STAGE) - norm_to_db(pk)
            if abs(err) <= TOL_DB:
                break
            new = min(0.0, vol + err)
            set_number(ch, t, 0, "Volume", new)
            if new >= 0.0:
                break
        print(f"  {sub}: Operator Volume {_param(ch, t, 0, 'Volume')['display']}, alone at unity {pk:.2f}")


def main():
    from thelmic.live_channel import LiveChannel
    ch = LiveChannel(lower_priority=False)
    ch.start()
    summary = []
    try:
        ch.set_launch_quantization(1).result(timeout=3)
        idx = names(ch)
        print("== sub gain staging")
        stage_subs(ch, idx)
        for section, row, roles in SECTIONS:
            print(f"== {section} (row {row + 1})")
            faders = {tr: ch.get_track_info(idx[tr]).result(timeout=5)["volume"] for tr in roles}
            before = dict(faders)
            for n in range(PASSES):
                peaks = play_and_measure(ch, idx, row, roles)
                worst = 0.0
                for tr, role in roles.items():
                    pk = peaks.get(tr, 0.0)
                    if pk <= 0.01:
                        print(f"  [warn] {tr} is silent on row {row + 1}")
                        continue
                    err = norm_to_db(TARGET[role]) - norm_to_db(pk)
                    worst = max(worst, abs(err))
                    if abs(err) > TOL_DB:
                        faders[tr] = max(0.05, min(1.0, db_to_norm(norm_to_db(faders[tr]) + err)))
                        ch.set_track_volume(idx[tr], faders[tr]).result(timeout=3)
                print(f"  pass {n + 1}: master {peaks.get('Master', 0):.2f} | "
                      + "  ".join(f"{roles[tr]} {tr} {peaks.get(tr, 0):.2f}" for tr in roles)
                      + f" | worst {worst:.1f} dB")
                if worst <= TOL_DB:
                    break
            peaks = play_and_measure(ch, idx, row, roles)
            master = peaks.get("Master", 0.0)
            if master > MASTER_CEILING:
                trim = norm_to_db(MASTER_CEILING - 0.02) - norm_to_db(master)
                for tr in roles:
                    faders[tr] = max(0.05, db_to_norm(norm_to_db(faders[tr]) + trim))
                    ch.set_track_volume(idx[tr], faders[tr]).result(timeout=3)
                master = play_and_measure(ch, idx, row, roles).get("Master", 0.0)
                print(f"  master over the ceiling: all four {trim:+.1f} dB -> {master:.2f}")
            for tr in roles:
                summary.append((section, roles[tr], tr, before[tr], faders[tr]))
            print(f"  master on the drop: {master:.2f}")
    finally:
        try:
            ch.stop_all_clips().result(timeout=3)
        finally:
            ch.stop()
    print("\n== faders")
    for section, role, tr, a, b in summary:
        print(f"  {section:<9} {role:<6} {tr:<14} {a:.2f} -> {b:.2f}  ({norm_to_db(b) - norm_to_db(a):+.1f} dB)")


if __name__ == "__main__":
    main()
