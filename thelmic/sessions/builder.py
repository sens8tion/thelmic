"""Idempotent build: reconcile a Session against current Live state.

Build order (each step a no-op if the target state is already present):
  1. tempo
  2. pack setup phase (16-track basis, devices)
  3. drum-rack samples (per-pad hotswap)
  4. role-track samples (audio clip / Simpler)
  5. preset bindings (Operator etc per role)

The pack lifecycle does the heavy lifting for (2)–(5); this module just
parameterizes pack calls with intent + binding overrides and skips work
already done.
"""
from __future__ import annotations
import time
from importlib import import_module
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .session import Session


def build_session(ch, sess: "Session") -> dict:
    counts = {"steps_run": 0, "steps_skipped": 0, "samples_loaded": 0,
              "presets_loaded": 0, "drum_pads_loaded": 0}

    # 1. tempo
    bpm = sess.intent.bpm
    if bpm is not None:
        cur = ch.get_session_info().result(timeout=5).get("tempo")
        if abs((cur or 0) - bpm) > 0.01:
            ch.set_tempo(float(bpm)).result(timeout=5)
            counts["steps_run"] += 1
        else:
            counts["steps_skipped"] += 1

    # 2. pack setup phase — 16-track basis. Idempotent (creates only missing).
    pack_module = import_module(f"thelmic.aesthetics.{sess.intent.pack}.lifecycle")
    if hasattr(pack_module, "setup_session"):
        roles = pack_module.setup_session(ch, bootstrap=True)
        counts["steps_run"] += 1
    else:
        roles = {}
        counts["steps_skipped"] += 1

    # 3. drum-rack samples — per-pad hotswap, idempotent
    drum_track = roles.get("drums")
    drum_pads = sess.bindings.drum_pad_bindings()
    if drum_track is not None and drum_pads:
        _ensure_drum_rack(ch, drum_track)
        existing_pads = _populated_pad_notes(ch, drum_track)
        for sb in drum_pads:
            if sb.pad_note in existing_pads:
                counts["steps_skipped"] += 1
                continue
            try:
                ch.load_sample_to_pad(drum_track, 0, sb.pad_note,
                                      sb.browser_path, sb.item_name).result(timeout=20)
                counts["drum_pads_loaded"] += 1
                time.sleep(0.3)
            except Exception as e:
                print(f"  drum pad {sb.pad_note} ({sb.item_name}): {e}")

    # 4. role-track samples (audio + Simpler)
    for sb in sess.bindings.samples:
        if sb.role.startswith("drums."):
            continue                     # handled in step 3
        ti = roles.get(sb.role)
        if ti is None:
            continue
        # Heuristic: if track has any audio clip in slot 0 OR a Simpler with a sample, skip.
        if _track_has_sample_loaded(ch, ti):
            counts["steps_skipped"] += 1
            continue
        try:
            ch.load_item_at_path(ti, sb.browser_path, sb.item_name).result(timeout=20)
            counts["samples_loaded"] += 1
            time.sleep(0.3)
        except Exception as e:
            print(f"  role {sb.role} ({sb.item_name}): {e}")

    # 5. preset bindings
    for pb in sess.bindings.presets:
        ti = roles.get(pb.role)
        if ti is None:
            continue
        if _track_has_named_device(ch, ti, pb.item_name):
            counts["steps_skipped"] += 1
            continue
        try:
            ch.load_item_at_path(ti, pb.browser_path, pb.item_name).result(timeout=20)
            counts["presets_loaded"] += 1
            time.sleep(0.3)
        except Exception as e:
            print(f"  preset {pb.role} ({pb.item_name}): {e}")

    return counts


# ---- inspection helpers (used to make build idempotent) ----------------

def _ensure_drum_rack(ch, track_index: int) -> None:
    info = ch.get_track_info(track_index).result(timeout=3)
    for d in info.get("devices", []):
        if d.get("class_name") == "DrumGroupDevice":
            return
    ch.load_item_at_path(track_index, "instruments", "Drum Rack").result(timeout=15)
    time.sleep(1.0)


def _populated_pad_notes(ch, track_index: int) -> set[int]:
    try:
        pads = ch.get_drum_pads(track_index, 0).result(timeout=5)
    except Exception:
        return set()
    return {p["note"] for p in pads.get("pads", []) if p.get("chain_count", 0) > 0}


def _track_has_sample_loaded(ch, track_index: int) -> bool:
    try:
        clips = ch.get_track_clips(track_index).result(timeout=3)
        if any(c.get("slot") == 0 for c in clips.get("clips", [])):
            return True
    except Exception:
        pass
    try:
        info = ch.get_track_info(track_index).result(timeout=3)
    except Exception:
        return False
    for d in info.get("devices", []):
        if d.get("class_name") == "OriginalSimpler" and d.get("name", "").strip():
            return True
    return False


def _track_has_named_device(ch, track_index: int, name: str) -> bool:
    try:
        info = ch.get_track_info(track_index).result(timeout=3)
    except Exception:
        return False
    needle = name.lower()
    for d in info.get("devices", []):
        if needle in (d.get("name", "") + " " + d.get("class_name", "")).lower():
            return True
    return False
