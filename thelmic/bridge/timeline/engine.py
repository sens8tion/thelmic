"""Timeline event engine — # mechanical, genre-neutral.

Walks a typed event list, firing scenes at bar boundaries, scheduling
ramps, executing tempo changes, and capturing it all into arrangement
automation via session_record.
"""
from __future__ import annotations
import time
from dataclasses import dataclass, field
from typing import Any
from .ramps import RampSpec, schedule_ramp, drain_ramps, resolve_ramp_target


@dataclass
class Timeline:
    """A typed event list ready to walk through session_record."""
    events: list[tuple[str, ...]] = field(default_factory=list)

    def add_scene(self, slot: int, bars: float, tag: str = ""):
        self.events.append(("scene", slot, bars, tag))

    def add_silence(self, beats: float, tag: str = ""):
        self.events.append(("silence", beats, tag))

    def add_ramp(self, ramp: RampSpec):
        self.events.append(("ramp", ramp))

    def add_tempo(self, bpm: float, tag: str = ""):
        self.events.append(("tempo", bpm, tag))

    def add_track_solo(self, keep_tracks: list[str], slot: int, bars: float, tag: str = ""):
        self.events.append(("track_solo", keep_tracks, slot, bars, tag))

    def add_section_marker(self, role: str, duration_bars: float, name: str = ""):
        self.events.append(("section_marker", role, duration_bars, name))

    def total_bars(self) -> float:
        return sum(_event_bars(e) for e in self.events)


def _event_bars(event: tuple) -> float:
    kind = event[0]
    if kind == "scene":           return event[2]
    if kind == "silence":         return event[1] / 4.0
    if kind == "ramp":            return 0.0
    if kind == "tempo":           return 0.0
    if kind == "track_solo":      return event[3]
    if kind == "section_marker":  return event[2]
    raise ValueError(f"unknown event kind: {kind!r}")


def calibrate(ch, beat_seconds: float) -> tuple[float, float]:
    """Read Live's playhead and pair it with a wall-clock anchor."""
    beat_anchor = ch.get_song_time().result(timeout=2)["song_time"]
    wall_anchor = time.monotonic()
    return wall_anchor, beat_anchor


def wait_until_beat(target_beat: float, wall_anchor: float, beat_anchor: float,
                     beat_seconds: float, fire_lead_s: float = 0.70) -> None:
    """Sleep until `fire_lead_s` before target_beat (wall-clock projected
    from calibration). One sleep, no per-iteration RPC."""
    target_wall = wall_anchor + (target_beat - beat_anchor) * beat_seconds
    fire_at = target_wall - fire_lead_s
    delay = fire_at - time.monotonic()
    if delay > 0:
        time.sleep(delay)


def _pre_resolve(ch, n_tracks: int, events: list) -> int:
    """Resolve every ramp target before the print starts so the realtime
    loop doesn't block on RPCs. Returns count of resolved targets."""
    n_resolved = 0
    for ev in events:
        if ev[0] != "ramp":
            continue
        ramp = ev[1]
        tgt = resolve_ramp_target(ch, n_tracks, ramp)
        if tgt is None:
            print(f"  [pre-resolve] FAIL: {ramp.tag!r}")
        else:
            ramp.resolved_target = tgt
            n_resolved += 1
    print(f"  [pre-resolve] {n_resolved} ramp targets cached")
    return n_resolved


def fire_arrangement(ch, timeline: Timeline, start_bar: float = 0.0,
                      bar_seconds: float = 1.455) -> float:
    """Walk timeline events, firing each at its target bar.

    Calibrates wall-clock against Live's playhead at print start. Ramps
    fire-and-forget through BULK queue. Returns elapsed_bars actually
    completed.
    """
    beat_seconds = bar_seconds / 4.0
    n_tracks = ch.get_session_info().result(timeout=3)["track_count"]

    # Pre-resolve ramps
    _pre_resolve(ch, n_tracks, timeline.events)

    # First event must be a scene to anchor playback
    first = timeline.events[0]
    assert first[0] == "scene", "Timeline must start with a scene event"

    ch.fire_scene(first[1]).result(timeout=5)
    time.sleep(0.1)
    ch.start_playback().result(timeout=5)
    time.sleep(0.05)

    wall_anchor, beat_anchor = calibrate(ch, beat_seconds)
    print(f"  calibrate: beat={beat_anchor:.3f} wall={wall_anchor:.3f}")

    pending_ramps: list = []
    elapsed_bars = _event_bars(first)

    for event in timeline.events[1:]:
        target_beat = elapsed_bars * 4.0

        # Drain ramps until we're near the target
        while True:
            drain_ramps(ch, pending_ramps)
            now_b = (time.monotonic() - wall_anchor) / beat_seconds + beat_anchor
            if target_beat - now_b <= 0.5:
                break
            time.sleep(0.005)

        kind = event[0]
        if kind == "scene":
            slot, bars = event[1], event[2]
            tag = event[3] if len(event) > 3 else ""
            ch.fire_scene(slot).result(timeout=5)
            try:
                drift = ch.get_song_time().result(timeout=2)["song_time"] / 4.0 - elapsed_bars
            except Exception:
                drift = 0.0
            print(f"  bar {start_bar + elapsed_bars:>6.1f}: scene S{slot:>2} "
                  f"(hold {bars:>4.1f}b)  drift {drift:+.3f}  — {tag}")

        elif kind == "silence":
            beats = event[1]
            tag = event[2] if len(event) > 2 else ""
            try: ch.stop_all_clips().result(timeout=10)
            except Exception as e: print(f"    silence stop_all_clips fail: {e}")
            print(f"  bar {start_bar + elapsed_bars:>6.1f}: ⏸ silence ({beats:>4.1f}b) — {tag}")

        elif kind == "ramp":
            ramp = event[1]
            ramp.start_beat = target_beat
            schedule_ramp(ch, ramp, wall_anchor, beat_anchor, beat_seconds,
                           pending_ramps)
            print(f"  bar {start_bar + elapsed_bars:>6.1f}: ↗ ramp scheduled — {ramp.tag}")

        elif kind == "tempo":
            new_bpm = event[1]
            tag = event[2] if len(event) > 2 else ""
            try: ch.set_tempo(float(new_bpm)).result(timeout=10)
            except Exception as e: print(f"    tempo set fail: {e!r}")
            print(f"  bar {start_bar + elapsed_bars:>6.1f}: ♩ tempo → {new_bpm:.1f} bpm — {tag}")

        elif kind == "track_solo":
            keep_tracks, slot, bars = event[1], event[2], event[3]
            tag = event[4] if len(event) > 4 else ""
            try: ch.stop_all_clips().result(timeout=3)
            except Exception: pass
            from ..helpers.discovery import find_track
            for tname in keep_tracks:
                ti = find_track(ch, tname)
                if ti is not None:
                    try: ch.fire_clip(ti, slot).result(timeout=3)
                    except Exception as e: print(f"    fire_clip {tname} S{slot}: {e}")
            print(f"  bar {start_bar + elapsed_bars:>6.1f}: ◐ track_solo S{slot} "
                  f"keep={keep_tracks} — {tag}")

        elif kind == "section_marker":
            role, _, name = event[1], event[2], (event[3] if len(event) > 3 else "")
            print(f"  bar {start_bar + elapsed_bars:>6.1f}: § {role} ({name})")

        elapsed_bars += _event_bars(event)

    # Final wait + drain remaining ramps
    final_target = elapsed_bars * 4.0
    while True:
        drain_ramps(ch, pending_ramps)
        now_b = (time.monotonic() - wall_anchor) / beat_seconds + beat_anchor
        if final_target - now_b <= 0.0:
            break
        time.sleep(0.005)
    drain_ramps(ch, pending_ramps)
    return elapsed_bars
