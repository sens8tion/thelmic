"""Sweep + attenuate hot channels to match declared LevelTarget.peak_db.

Iterative: each pass measures peak across all scenes, computes a linear
ratio between declared target and observed peak, multiplies the track's
volume param by that ratio, sleeps for the curve to settle, and re-sweeps.

Live's volume param is non-linear in dB, so a single linear-ratio pass
under-shoots the dB target — but iterating converges quickly. Default is
4 passes, which usually gets within 1 dB.
"""
from __future__ import annotations
import math, os, time

os.environ.setdefault("LIVE_CHANNEL_ENABLED", "1")

from thelmic.live_channel import LiveChannel
from thelmic.bridge.helpers.discovery import find_track
from thelmic.aesthetics.dnb_jungle import LAYOUT, CHANNEL_AUDIO


SAMPLE_INTERVAL_S = 0.1
SAMPLE_SECONDS    = 3.5
WARMUP_SECONDS    = 1.5
MAX_PASSES        = 4
TOLERANCE_DB      = 1.0
# In Live's slider scale 0.85 ≈ 0 dBFS. Use that as the conversion anchor.
UNITY_METER       = 0.85


def db_to_target_meter(db: float) -> float:
    """declared peak_db → equivalent meter reading at unity gain."""
    return UNITY_METER * (10 ** (db / 20.0))


def meter_to_db(meter: float) -> float:
    if meter <= 0: return float("-inf")
    return 20 * math.log10(meter / UNITY_METER)


def sweep_peaks(ch, roles: dict[str, int], layout) -> dict[str, float]:
    """Fire each scene; return {role: max_peak_across_scenes}."""
    peaks_per_role = {role: 0.0 for role in roles}
    for scene_i, scene in enumerate(layout.scenes):
        ch.stop_all_clips().result(timeout=5)
        time.sleep(0.3)
        ch.fire_scene(scene_i).result(timeout=5)
        time.sleep(WARMUP_SECONDS)
        steps = int(SAMPLE_SECONDS / SAMPLE_INTERVAL_S)
        for _ in range(steps):
            meters = ch.get_all_meters().result(timeout=2).get("meters", [])
            by_idx = {m.get("track_index"): m for m in meters}
            for role, ti in roles.items():
                m = by_idx.get(ti)
                if not m: continue
                peak = max(float(m.get("left", 0)), float(m.get("right", 0)))
                if peak > peaks_per_role[role]:
                    peaks_per_role[role] = peak
            time.sleep(SAMPLE_INTERVAL_S)
    ch.stop_all_clips().result(timeout=5)
    return peaks_per_role


def get_volume(ch, ti: int) -> float:
    info = ch.get_track_info(ti).result(timeout=3)
    # get_track_info doesn't include volume; read via the get_session_info path.
    # Safer: use master->per-track via get_track_meter? It doesn't either.
    # Fall back to assuming default 0.85 if not stored.
    return None  # placeholder; replaced by tracking dict below


def main() -> None:
    ch = LiveChannel(); ch.start(); time.sleep(0.6)
    try:
        roles: dict[str, int] = {}
        for spec in LAYOUT.channels:
            ti = find_track(ch, spec.role.upper())
            if ti is not None:
                roles[spec.role] = ti
        if not roles:
            print("no layout tracks found — build the session first")
            return

        # Track volume params we set, since reading them post-set via the
        # main get_session_info doesn't expose mixer values.
        volumes: dict[str, float] = {role: UNITY_METER for role in roles}

        for pass_i in range(1, MAX_PASSES + 1):
            print(f"\n=== pass {pass_i} ===")
            peaks = sweep_peaks(ch, roles, LAYOUT)
            adjustments = []
            all_clean = True
            for role, peak in peaks.items():
                ca = CHANNEL_AUDIO.get(role)
                if ca is None or peak <= 0:
                    continue
                declared_db = ca.level.peak_db
                actual_db = meter_to_db(peak)
                target_meter = db_to_target_meter(declared_db)
                if peak > target_meter * 1.05:
                    ratio = target_meter / peak
                    new_vol = max(0.05, volumes[role] * ratio)
                    adjustments.append((role, peak, actual_db, declared_db, new_vol))
                    all_clean = False
            for role, peak, actual_db, declared_db, new_vol in adjustments:
                old = volumes[role]
                volumes[role] = new_vol
                ti = roles[role]
                ch.set_track_volume(ti, new_vol).result(timeout=3)
                print(f"  {role:>5}  peak={peak:.3f} ({actual_db:+.1f}dB)  "
                      f"declared {declared_db:+.1f}dB  vol {old:.3f} -> {new_vol:.3f}")
            if all_clean:
                print("  all channels within tolerance")
                break
            time.sleep(0.3)

        # Final sweep + report
        print("\n=== final ===")
        peaks = sweep_peaks(ch, roles, LAYOUT)
        for role, peak in sorted(peaks.items(), key=lambda x: -x[1]):
            ca = CHANNEL_AUDIO.get(role)
            declared_db = ca.level.peak_db if ca else None
            actual_db = meter_to_db(peak) if peak > 0 else float("-inf")
            adb = f"{actual_db:+.1f}" if peak > 0 else "silent"
            mark = ""
            if declared_db is not None and peak > 0 and actual_db > declared_db + TOLERANCE_DB:
                mark = " HOT"
            print(f"  {role:>5}  peak={peak:.3f}  ~{adb} dB  "
                  f"declared={declared_db}  vol={volumes[role]:.3f}{mark}")
    finally:
        ch.stop()


if __name__ == "__main__":
    main()
