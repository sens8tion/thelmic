"""JUNGLE LEVELS - gain-stage every device, then balance faders, then protect the master.

The user's rule: every stage's OUTPUT sits at unity, not just the final sum - no hot synth into a
saturator, no stacked makeup gain, and no leaning on the master fader. Then the faders set the
balance: kick and sub cut least, the break a little further, everything else further still (but
not by much - a 6 dB-too-far tier has been rejected before).

Live's track meter reads 0..1 on the fader's scale, so 0.85 ~ 0 dBFS. It only exposes the TRACK
output, so a device's own output is measured by bypassing everything after it (the method in
thelmic/bridge/helpers/mix_apply.py). That module's gain table predates Live 12's parameter names
(EQ Eight and Compressor call it "Output", and Saturator's Output is 0..1, not dB), so the stages
here use what Live 12 actually reports. Unit mappings are never trusted: every correction is
measured again and iterated.

  1. device stages: each lane plays its most representative clip alone, fader at 0 dB; each gain
     stage in turn (downstream bypassed) is driven to STAGE_TARGET.
  2. faders: the F-ALL row (every lane playing) is metered and faders iterated to FADER_TARGET.
  3. master: if the master peaks above MASTER_CEILING, every fader comes down by the same amount.
  4. report: master peaks on the drop, breakdown and build rows.

    python scripts/jungle_levels.py
"""
from __future__ import annotations

import os
import sys
import time

os.environ.setdefault("LIVE_CHANNEL_ENABLED", "1")
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(SCRIPTS_DIR))

UNITY = 0.85            # meter value ~ 0 dBFS
STAGE_TARGET = 0.80     # each device output: just under unity (polled meters miss some peaks)
TOL = 0.025             # meter units
MASTER_CEILING = 0.85
POLL_S = 0.04
WARMUP_S = 0.7
WINDOW_S = 3.0
LOOP_S = 32 * 60.0 / 170 + 0.3   # one whole 8-bar loop: every fader pass hears the same material

# Representative clip (session row) per lane: its densest / loudest material.
PROBE_ROW = {"AMEN-DMENT": 15, "SWEAT-SHOP": 12, "TOPSOIL": 0, "BOOT-LEG": 4,
             "F-HOLE": 4, "RASP-BERRY": 4, "RASP-UTIN": 13, "BELL-END": 1,
             "HALO-PERIDOL": 1, "LIP-SERVICE": 4}

# Gain stages in chain order: (device class, param, unit). "db" params move in dB; "norm" params
# are 0..1 with an unknown curve, stepped along the fader curve and re-measured.
STAGES = {
    # break lanes are Drum Racks (a Simpler per slice pad): the EQ after the rack is the trim stage
    "AMEN-DMENT": [("Eq8", "Output", "db"), ("GlueCompressor", "Output", "db")],
    "SWEAT-SHOP": [("Eq8", "Output", "db")],
    "TOPSOIL":    [("Eq8", "Output", "db")],
    # factory instruments on the synth lanes: the patch's own level is left alone and the EQ after it
    # is the trim stage (F-HOLE gets a flat EQ Eight for exactly that)
    "BOOT-LEG":   [("Eq8", "Output", "db")],
    "F-HOLE":     [("Eq8", "Output", "db")],
    "RASP-BERRY": [("Eq8", "Output", "db"), ("Compressor2", "Output", "db")],
    "RASP-UTIN":  [("Eq8", "Output", "db"), ("Compressor2", "Output", "db")],
    "BELL-END":   [("Operator", "Volume", "norm"), ("Eq8", "Output", "db")],
    "HALO-PERIDOL": [("Eq8", "Output", "db")],
    "LIP-SERVICE":  [("Eq8", "Output", "db")],
    # THROW-UP is only echo and reverb tails of a hit or two per loop: no steady stage to meter, so
    # only its fader is balanced
}

BALANCE_ROW = 13        # F-ALL: nearly every lane plays; the master is protected on this row
BALANCE_ROWS = [(13, ["BOOT-LEG", "F-HOLE", "AMEN-DMENT", "RASP-UTIN", "BELL-END", "SWEAT-SHOP", "TOPSOIL",
                      "HALO-PERIDOL", "LIP-SERVICE", "THROW-UP"]),
                (4, ["RASP-BERRY"])]                 # the first reese sits out drop 2
FADER_TARGET = {"BOOT-LEG": 0.82, "F-HOLE": 0.82, "AMEN-DMENT": 0.76, "RASP-BERRY": 0.72, "RASP-UTIN": 0.72,
                "BELL-END": 0.70, "LIP-SERVICE": 0.70, "SWEAT-SHOP": 0.66, "TOPSOIL": 0.66,
                "HALO-PERIDOL": 0.64, "THROW-UP": 0.64}
REPORT_ROWS = [(4, "BOTTOM FEEDER"), (10, "NOBODY HOME"), (12, "SWEAT EQUITY"), (13, "F-ALL"),
               (15, "TERMINAL VELOCITY")]


def norm_to_db(v: float) -> float:
    """Live's fader-style curve (0.85 = 0 dB, 1.0 = +6 dB), piecewise approximation."""
    if v >= 1.0:
        return 6.0
    if v >= 0.85:
        return (v - 0.85) / 0.15 * 6.0
    if v >= 0.70:
        return -6 + (v - 0.70) / 0.15 * 6.0
    if v >= 0.55:
        return -12 + (v - 0.55) / 0.15 * 6.0
    if v >= 0.35:
        return -24 + (v - 0.35) / 0.20 * 12.0
    if v >= 0.13:
        return -48 + (v - 0.13) / 0.22 * 24.0
    return -70 + v / 0.13 * 22.0 if v > 0 else -90.0


def db_to_norm(db: float) -> float:
    if db >= 6:
        return 1.0
    if db >= 0:
        return 0.85 + db / 6.0 * 0.15
    if db >= -6:
        return 0.70 + (db + 6) / 6.0 * 0.15
    if db >= -12:
        return 0.55 + (db + 12) / 6.0 * 0.15
    if db >= -24:
        return 0.35 + (db + 24) / 12.0 * 0.20
    if db >= -48:
        return 0.13 + (db + 48) / 24.0 * 0.22
    return max(0.0, (db + 70.0) / 22.0 * 0.13)


def track_index(ch):
    n = ch.get_session_info().result(timeout=5)["track_count"]
    return {ch.get_track_info(i).result(timeout=5)["name"]: i for i in range(n)}


def params(ch, t, d):
    return {p["name"]: p for p in ch.get_device_info(t, d).result(timeout=5)["parameters"]}


def sample_peaks(ch, seconds=WINDOW_S):
    """Max meter per track name (and 'Master') over the window."""
    peaks = {}
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        for m in ch.get_all_meters().result(timeout=2)["meters"]:
            peaks[m["name"]] = max(peaks.get(m["name"], 0.0), m.get("left", 0.0), m.get("right", 0.0))
        time.sleep(POLL_S)
    return peaks


def play_and_measure(ch, t, row, name):
    ch.stop_all_clips().result(timeout=3)
    time.sleep(0.25)
    ch.fire_clip(t, row).result(timeout=3)
    time.sleep(WARMUP_S)
    peak = sample_peaks(ch).get(name, 0.0)
    ch.stop_all_clips().result(timeout=3)
    return peak


def stage_devices(ch, idx):
    changes = []
    for lane, stages in STAGES.items():
        t = idx[lane]
        info = ch.get_track_info(t).result(timeout=5)
        classes = [d["class_name"] for d in info["devices"]]
        on = {d: params(ch, t, d)["Device On"] for d in range(len(classes))}
        old_fader = info["volume"]
        ch.set_track_volume(t, UNITY).result(timeout=3)
        print(f"\n== {lane} (row {PROBE_ROW[lane]}) chain: {' > '.join(classes)}")
        try:
            for cls, pname, unit in stages:
                if cls not in classes:
                    print(f"  [skip] no {cls}")
                    continue
                d = classes.index(cls)
                for dd, p in on.items():                  # this stage and everything before it on
                    ch.set_device_param(t, dd, p["index"], 1.0 if dd <= d else 0.0).result(timeout=3)
                p = params(ch, t, d)[pname]
                start = cur = p["value"]
                peak = 0.0
                for _ in range(5):
                    peak = play_and_measure(ch, t, PROBE_ROW[lane], lane)
                    if peak <= 0.0:
                        print(f"  [warn] {cls}.{pname}: silent, left alone")
                        break
                    if abs(peak - STAGE_TARGET) <= TOL:
                        break
                    err = norm_to_db(STAGE_TARGET) - norm_to_db(peak)
                    new = cur + err if unit == "db" else db_to_norm(norm_to_db(cur) + err)
                    new = max(p["min"], min(p["max"], new))
                    if abs(new - cur) < 1e-4:
                        print(f"  [limit] {cls}.{pname} pinned at {cur:.3g} (peak {peak:.3f})")
                        break
                    ch.set_device_param(t, d, p["index"], new).result(timeout=3)
                    cur = new
                print(f"  {cls}.{pname}: {start:.3g} -> {cur:.3g}   stage peak {peak:.3f}")
                changes.append((lane, f"{cls}.{pname}", start, cur, peak))
        finally:
            for dd, p in on.items():
                ch.set_device_param(t, dd, p["index"], p["value"]).result(timeout=3)
            ch.set_track_volume(t, old_fader).result(timeout=3)
    return changes


def balance_faders(ch, idx):
    lanes = list(FADER_TARGET)
    faders = {lane: ch.get_track_info(idx[lane]).result(timeout=5)["volume"] for lane in lanes}
    before = dict(faders)
    for row, row_lanes in BALANCE_ROWS:
        print(f"  row {row}:")
        for pass_n in range(4):
            ch.stop_all_clips().result(timeout=3)
            time.sleep(0.25)
            ch.fire_scene(row).result(timeout=3)
            time.sleep(WARMUP_S + 0.5)
            peaks = sample_peaks(ch, LOOP_S)
            worst = 0.0
            for lane in row_lanes:
                pk = peaks.get(lane, 0.0)
                if pk <= 0:
                    continue
                err = norm_to_db(FADER_TARGET[lane]) - norm_to_db(pk)
                worst = max(worst, abs(err))
                if abs(err) > 0.5:
                    faders[lane] = max(0.05, min(1.0, db_to_norm(norm_to_db(faders[lane]) + err)))
                    ch.set_track_volume(idx[lane], faders[lane]).result(timeout=3)
            print(f"    pass {pass_n + 1}: master {peaks.get('Master', 0):.3f}; "
                  + "  ".join(f"{lane.split('-')[0][:5]} {peaks.get(lane, 0):.2f}" for lane in row_lanes)
                  + f"   worst error {worst:.1f} dB")
            if worst <= 0.5:
                break
    # master: pull every fader down together until the sum fits
    for _ in range(4):
        ch.stop_all_clips().result(timeout=3)
        time.sleep(0.25)
        ch.fire_scene(BALANCE_ROW).result(timeout=3)
        time.sleep(WARMUP_S + 0.5)
        master = sample_peaks(ch, LOOP_S).get("Master", 0.0)
        if master <= MASTER_CEILING:
            print(f"  master {master:.3f} <= {MASTER_CEILING}")
            break
        trim = norm_to_db(MASTER_CEILING - 0.02) - norm_to_db(master)
        for lane in lanes:
            faders[lane] = max(0.05, db_to_norm(norm_to_db(faders[lane]) + trim))
            ch.set_track_volume(idx[lane], faders[lane]).result(timeout=3)
        print(f"  master {master:.3f}: all faders {trim:+.1f} dB")
    ch.stop_all_clips().result(timeout=3)
    return before, faders


def report(ch):
    print("\n== master peaks per row ==")
    for row, name in REPORT_ROWS:
        ch.stop_all_clips().result(timeout=3)
        time.sleep(0.25)
        ch.fire_scene(row).result(timeout=3)
        time.sleep(WARMUP_S + 0.5)
        peaks = sample_peaks(ch, 4.0)
        loud = sorted(((v, k) for k, v in peaks.items() if k != "Master" and v > 0), reverse=True)[:3]
        print(f"  {name:<18} master {peaks.get('Master', 0):.3f}  loudest: "
              + ", ".join(f"{k} {v:.2f}" for v, k in loud))
    ch.stop_all_clips().result(timeout=3)


def main():
    from thelmic.live_channel import LiveChannel
    ch = LiveChannel(lower_priority=False)
    ch.start()
    try:
        idx = track_index(ch)
        ch.set_launch_quantization(0).result(timeout=3)
        print("== 1. device stages (target meter %.2f) ==" % STAGE_TARGET)
        changes = stage_devices(ch, idx)
        print("\n== 2. faders on row %d ==" % BALANCE_ROW)
        before, after = balance_faders(ch, idx)
        report(ch)
        print("\n== summary ==")
        for lane, what, a, b, pk in changes:
            print(f"  {lane:<11} {what:<24} {a:>7.3g} -> {b:<7.3g} (stage peak {pk:.2f})")
        for lane in FADER_TARGET:
            print(f"  {lane:<11} fader {before[lane]:.3f} -> {after[lane]:.3f}")
    finally:
        try:
            ch.stop_all_clips().result(timeout=3)
            ch.set_launch_quantization(1).result(timeout=3)
        finally:
            ch.stop()


if __name__ == "__main__":
    main()
