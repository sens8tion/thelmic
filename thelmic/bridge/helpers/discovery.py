"""Track / device discovery — # mechanical, genre-neutral."""
from __future__ import annotations
from typing import Iterable


def find_track(ch, name_match: str) -> int | None:
    """Case-insensitive substring match on track names. Returns first match index."""
    sess = ch.get_session_info().result(timeout=5)
    needle = name_match.lower()
    for i in range(sess["track_count"]):
        info = ch.get_track_info(i).result(timeout=5)
        if needle in info["name"].lower():
            return i
    return None


def find_device(ch, track_index: int, class_name_match: str) -> int | None:
    """Find a device on a track by class_name (e.g. 'Eq8', 'Compressor2', 'Saturator')."""
    info = ch.get_track_info(track_index).result(timeout=5)
    needle = class_name_match.lower()
    for i, d in enumerate(info["devices"]):
        if needle in d["class_name"].lower():
            return i
    return None


def ensure_device(ch, track_index: int, class_name_match: str, browser_uri: str) -> int:
    """Return existing device index for class, or load from browser_uri and return new idx."""
    idx = find_device(ch, track_index, class_name_match)
    if idx is not None:
        return idx
    ch.load_device(track_index, browser_uri).result(timeout=15)
    info = ch.get_track_info(track_index).result(timeout=5)
    return info["device_count"] - 1


def health_check(ch, expected_track_names: list[str] | None = None,
                  min_tracks: int = 4) -> tuple[bool, str | dict]:
    """Probe the session — fast-fail when Live is fresh / wrong project / not running.

    Returns (ok, detail). On success detail is {name: index} for found tracks
    (or all tracks if no expected list given). On failure detail is a one-line reason.
    """
    try:
        ch.ping().result(timeout=3)
    except Exception as e:
        return False, f"Live not responding (port 9878): {e}"
    sess = ch.get_session_info().result(timeout=5)
    n = sess["track_count"]
    if n < min_tracks:
        return False, (f"only {n} tracks — looks like a fresh project (default 2 MIDI + 2 Audio)."
                       f" Open the saved set first.")
    if expected_track_names:
        found = {}
        missing = []
        for name in expected_track_names:
            idx = find_track(ch, name)
            if idx is None:
                missing.append(name)
            else:
                found[name] = idx
        if missing:
            return False, f"missing expected tracks: {missing}"
        return True, found
    out = {}
    for i in range(n):
        info = ch.get_track_info(i).result(timeout=5)
        out[info["name"]] = i
    return True, out
