"""Realtime parameter ramping — # mechanical.

Captured into arrangement automation by Live's session_record. Pre-resolve
targets at print start, fire-and-forget through the BULK queue lane so
ramps never block priority sync RPCs.

Supports:
  - per-track param ramps  (track="MyTrack")
  - master-bus ramps       (track="MASTER" → tidx=-1)
  - semantic-param targeting (resolve via DEVICE_PARAM_MAP) OR
  - direct param-name targeting
"""
from __future__ import annotations
import time
from dataclasses import dataclass, field
from typing import Optional
from ..helpers.discovery import find_track
from ..helpers.params    import resolve_semantic_param, SemanticParam


@dataclass
class RampSpec:
    """Declarative ramp specification."""
    track: str                                       # "MyTrack" or "MASTER"
    param_name: Optional[str] = None                 # explicit Live param name
    semantic: Optional[SemanticParam] = None         # OR semantic intent
    device_idx: Optional[int] = None
    device_substring: Optional[str] = None           # e.g. "saturator", "eq8"
    from_value: float = 0.0
    to_value: float = 1.0
    duration_bars: float = 4.0
    steps: int = 24
    curve: str = "linear"                            # "linear" | "exp" | "log"
    start_beat: Optional[float] = None               # filled at schedule time
    tag: str = ""
    resolved_target: Optional[tuple[int, int, int]] = None    # (tidx, dev, pidx)


def resolve_ramp_target(ch, n_tracks: int, ramp: RampSpec) -> Optional[tuple[int, int, int]]:
    """Resolve a ramp's target → (track_index, device_index, param_index).
    track='MASTER' / 'MAIN' returns tidx=-1."""
    is_master = ramp.track is not None and ramp.track.upper() in ("MASTER", "MAIN")

    if is_master:
        tidx = -1
        dev_idx = ramp.device_idx
        if dev_idx is None and ramp.device_substring:
            substr = ramp.device_substring.lower()
            for di in range(8):
                try:
                    minfo = ch.get_master_device_info(di).result(timeout=3)
                except Exception:
                    break
                nm = (minfo.get("name") or "") + " " + (minfo.get("class_name") or "")
                if substr in nm.lower():
                    dev_idx = di
                    break
        if dev_idx is None: return None
        di = ch.get_master_device_info(dev_idx).result(timeout=3)
        device_class = di.get("class_name", "")
    else:
        tidx = find_track(ch, ramp.track) if ramp.track else None
        if tidx is None: return None
        dev_idx = ramp.device_idx
        if dev_idx is None and ramp.device_substring:
            info = ch.get_track_info(tidx).result(timeout=3)
            substr = ramp.device_substring.lower()
            for di_, d in enumerate(info.get("devices", [])):
                nm = (d.get("name") or "") + " " + (d.get("class_name") or "")
                if substr in nm.lower():
                    dev_idx = di_
                    break
        if dev_idx is None: return None
        di = ch.get_device_info(tidx, dev_idx).result(timeout=3)
        device_class = ""
        info = ch.get_track_info(tidx).result(timeout=3)
        for d_idx, d in enumerate(info.get("devices", [])):
            if d_idx == dev_idx:
                device_class = d.get("class_name", "")
                break

    # Determine param name (explicit or via semantic resolution)
    pname = ramp.param_name
    if pname is None and ramp.semantic is not None:
        pname = resolve_semantic_param(device_class, ramp.semantic)
    if pname is None: return None

    pidx = next((p["index"] for p in di["parameters"] if p["name"] == pname), None)
    if pidx is None: return None
    return (tidx, dev_idx, pidx)


def schedule_ramp(ch, ramp: RampSpec, wall_anchor: float, beat_anchor: float,
                   beat_seconds: float, pending: list) -> None:
    """Plan a ramp: append (when_wall, tidx, dev, pidx, value) entries to pending.
    Uses pre-resolved target if RampSpec.resolved_target is set."""
    tgt = ramp.resolved_target or resolve_ramp_target(ch, 0, ramp)
    if tgt is None:
        print(f"    [ramp] could not resolve target {ramp.tag!r}")
        return
    tidx, dev_idx, pidx = tgt
    start_beat = ramp.start_beat or 0.0
    duration_beats = ramp.duration_bars * 4
    for k in range(1, ramp.steps + 1):
        frac = k / ramp.steps
        if ramp.curve == "exp":
            frac = frac ** 2
        elif ramp.curve == "log":
            frac = frac ** 0.5
        v = ramp.from_value + (ramp.to_value - ramp.from_value) * frac
        target_beat = start_beat + frac * duration_beats
        when = wall_anchor + (target_beat - beat_anchor) * beat_seconds
        pending.append((when, tidx, dev_idx, pidx, float(v)))


def drain_ramps(ch, pending: list) -> None:
    """Pop and execute ramp steps whose deadline has passed.
    Fire-and-forget through the BULK queue lane so ramps never block
    priority sync RPCs (stop_all_clips, fire_scene, set_tempo)."""
    if not pending: return
    now = time.monotonic()
    remaining = []
    for entry in pending:
        when, tidx, dev, pidx, v = entry
        if when <= now:
            try:
                if tidx == -1:
                    ch._enqueue("set_master_device_param",
                                  {"device_index": dev, "param_index": pidx,
                                   "value": float(v)}, lane="bulk")
                else:
                    ch._enqueue("set_device_param",
                                  {"track_index": tidx, "device_index": dev,
                                   "param_index": pidx, "value": float(v)},
                                  lane="bulk")
            except Exception:
                pass
        else:
            remaining.append(entry)
    pending[:] = remaining
