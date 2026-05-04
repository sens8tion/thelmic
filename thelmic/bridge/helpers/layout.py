"""Idempotently realize a MetaLayout against current Live state.

ensure_layout(ch, layout):
  - Creates missing channel tracks in declared order, named by role (UPPERCASE)
  - Loads each channel's default device on a fresh track
  - Ensures scene_count scenes exist, named per layout
  - Returns {role: track_index} for the builder
"""
from __future__ import annotations
import time

from thelmic.meta import MetaLayout, ChannelSpec, ChannelKind
from .discovery import find_track


def ensure_layout(ch, layout: MetaLayout) -> dict[str, int]:
    roles: dict[str, int] = {}
    info = ch.get_session_info().result(timeout=5)
    track_count = int(info.get("track_count", 0))

    for spec in layout.channels:
        track_name = spec.role.upper()
        existing = find_track(ch, track_name)
        if existing is not None:
            roles[spec.role] = existing
            continue

        ti = _create_channel_track(ch, spec, track_count)
        track_count += 1
        ch.set_track_name(ti, track_name).result(timeout=5)
        time.sleep(0.15)
        _load_default_device(ch, ti, spec)
        roles[spec.role] = ti

    _ensure_scenes(ch, layout)
    return roles


def _create_channel_track(ch, spec: ChannelSpec, expected_index: int) -> int:
    if spec.kind == ChannelKind.AUDIO:
        ch.create_audio_track(-1).result(timeout=5)
    else:
        ch.create_midi_track(-1).result(timeout=5)
    time.sleep(0.2)
    return expected_index


def _load_default_device(ch, track_index: int, spec: ChannelSpec) -> None:
    if spec.kind == ChannelKind.AUDIO or not spec.default_device:
        return
    try:
        ch.load_item_at_path(track_index, spec.default_browser_path or "instruments",
                              spec.default_device).result(timeout=15)
        time.sleep(0.4)
    except Exception as e:
        print(f"  layout: load {spec.default_device} on {spec.role} failed: {e}")


def _ensure_scenes(ch, layout: MetaLayout) -> None:
    info = ch.get_scene_count().result(timeout=5)
    have = int(info.get("scene_count", 0)) if isinstance(info, dict) else 0
    need = layout.scene_count
    while have < need:
        ch.create_scene(-1).result(timeout=5)
        have += 1
        time.sleep(0.1)
