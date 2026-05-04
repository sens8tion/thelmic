"""Sweep scenes and report per-track peak levels vs declared CHANNEL_AUDIO.

For each layout scene: stop all clips, fire scene, sample meters every
100ms for ~4s, record per-role peak. Print a table flagging channels
that exceed declared LevelTarget.peak_db.

Notes on units: Live's output_meter_left/right is a normalized 0..1
slider-position value. We convert with 20*log10(meter) for an
approximate dBFS readout — diverges from Live's UI numbers near unity
but is fine as a relative metric.
"""
from __future__ import annotations
import math, os, time

os.environ.setdefault("LIVE_CHANNEL_ENABLED", "1")

from thelmic.live_channel import LiveChannel
from thelmic.bridge.helpers.discovery import find_track
from thelmic.aesthetics.dnb_jungle import LAYOUT, CHANNEL_AUDIO


SAMPLE_INTERVAL_S = 0.1
SAMPLE_SECONDS    = 4.0
WARMUP_SECONDS    = 2.0


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

        all_results: list[tuple[str, dict[str, float]]] = []
        for scene_i, scene in enumerate(LAYOUT.scenes):
            ch.stop_all_clips().result(timeout=5)
            time.sleep(0.4)
            ch.fire_scene(scene_i).result(timeout=5)
            time.sleep(WARMUP_SECONDS)
            peaks: dict[str, float] = {role: 0.0 for role in roles}
            steps = int(SAMPLE_SECONDS / SAMPLE_INTERVAL_S)
            for _ in range(steps):
                meters = ch.get_all_meters().result(timeout=2).get("meters", [])
                by_idx = {m.get("track_index"): m for m in meters}
                for role, ti in roles.items():
                    m = by_idx.get(ti)
                    if not m:
                        continue
                    peak = max(float(m.get("left", 0)), float(m.get("right", 0)))
                    if peak > peaks[role]:
                        peaks[role] = peak
                time.sleep(SAMPLE_INTERVAL_S)
            all_results.append((scene.name, peaks))

        ch.stop_all_clips().result(timeout=5)

        # Report
        print("\n=== sweep results ===")
        for scene_name, peaks in all_results:
            print(f"\n[{scene_name}]")
            rows = []
            for role, peak in peaks.items():
                ca = CHANNEL_AUDIO.get(role)
                declared = ca.level.peak_db if ca else None
                peak_db = 20 * math.log10(peak) if peak > 0 else float("-inf")
                hot = (declared is not None and peak > 0
                       and peak_db > declared + 0.5)
                marker = " HOT" if hot else ""
                rows.append((role, peak, peak_db, declared, marker))
            for role, peak, peak_db, declared, marker in sorted(
                    rows, key=lambda r: -r[1]):
                pdb = f"{peak_db:>+6.1f}" if peak > 0 else "  silent"
                print(f"  {role:>5}  meter={peak:.3f}  ~{pdb} dB  "
                      f"declared={declared}{marker}")
    finally:
        ch.stop()


if __name__ == "__main__":
    main()
