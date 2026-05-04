"""Idempotent build: reconcile a Session against current Live state.

Build order (each step a no-op if the target state is already present):
  1. tempo
  2. layout setup (8x4 channels + scenes) via pack's MetaLayout, fallback to legacy setup_session
  3. drum-rack pads — per-pad hotswap
  4. role-track samples — kind-aware: AUDIO → load_audio_to_slot(slot 0),
                                       SAMPLER → load_item_at_path (replaces Simpler sample)
  5. preset bindings
"""
from __future__ import annotations
import time
from importlib import import_module
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .session import Session


def build_session(ch, sess: "Session") -> dict:
    counts = {"steps_run": 0, "steps_skipped": 0, "samples_loaded": 0,
              "presets_loaded": 0, "drum_pads_loaded": 0,
              "midi_clips": 0, "audio_clip_dupes": 0}

    # 1. tempo
    bpm = sess.intent.bpm
    if bpm is not None:
        cur = ch.get_session_info().result(timeout=5).get("tempo")
        if abs((cur or 0) - bpm) > 0.01:
            ch.set_tempo(float(bpm)).result(timeout=5)
            counts["steps_run"] += 1
        else:
            counts["steps_skipped"] += 1

    # 2. layout — prefer pack's MetaLayout, fallback to legacy
    pack_pkg = import_module(f"thelmic.aesthetics.{sess.intent.pack}")
    layout = getattr(pack_pkg, "LAYOUT", None)
    if layout is not None:
        from thelmic.bridge.helpers.layout import ensure_layout
        roles = ensure_layout(ch, layout)
        counts["steps_run"] += 1
    else:
        pack_lifecycle = import_module(f"thelmic.aesthetics.{sess.intent.pack}.lifecycle")
        if hasattr(pack_lifecycle, "setup_session"):
            roles = pack_lifecycle.setup_session(ch, bootstrap=True)
            counts["steps_run"] += 1
            layout = None
        else:
            roles = {}
            counts["steps_skipped"] += 1

    # 3. drum-rack pads
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

    # 4. role-track samples — kind-aware
    for sb in sess.bindings.samples:
        if sb.role.startswith("drums."):
            continue
        ti = roles.get(sb.role)
        if ti is None:
            continue
        kind = _channel_kind(layout, sb.role)
        loaded = _channel_already_has_sample(ch, ti, kind, sb.item_name)
        if loaded:
            counts["steps_skipped"] += 1
            continue
        try:
            if kind == "audio":
                ch.load_audio_to_slot(ti, 0, sb.browser_path, sb.item_name).result(timeout=20)
            else:
                # sampler / synth — let Live replace the device or load into selected
                ch.load_item_at_path(ti, sb.browser_path, sb.item_name).result(timeout=20)
            counts["samples_loaded"] += 1
            time.sleep(0.3)
        except Exception as e:
            print(f"  role {sb.role} ({sb.item_name}): {e}")

    # 6. mix — apply CHANNEL_AUDIO (HP/LP per role)
    channel_audio = getattr(pack_pkg, "CHANNEL_AUDIO", None)
    if channel_audio:
        from thelmic.bridge.helpers.mix_apply import apply_channel_audio
        try:
            res = apply_channel_audio(ch, roles, channel_audio)
            counts["eq_set"] = res.get("eq_set", 0)
        except Exception as e:
            print(f"  mix_apply: {e}")

    # 7. compose — fill scene clips per SCENE_PLAN
    scene_plan = getattr(pack_pkg, "SCENE_PLAN", None)
    clip_len = float(getattr(pack_pkg, "CLIP_LENGTH_BEATS", 16.0))
    if scene_plan and layout is not None:
        _compose_scenes(ch, scene_plan, layout, roles, clip_len, counts)

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


# ---- compose phase ----------------

def _compose_scenes(ch, scene_plan, layout, roles, clip_len, counts) -> None:
    """For each (scene, channel) cell in the plan: ensure a clip exists.

    - "audio" entries duplicate slot 0 of the audio track to scene slot.
    - Callable entries create a MIDI clip and write notes.
    """
    scene_index_by_name = {s.name: i for i, s in enumerate(layout.scenes)}
    for scene_name, channel_map in scene_plan.items():
        slot = scene_index_by_name.get(scene_name)
        if slot is None:
            continue
        for role, action in channel_map.items():
            ti = roles.get(role)
            if ti is None:
                continue
            try:
                existing = ch.get_track_clips(ti).result(timeout=3).get("clips", [])
            except Exception:
                existing = []
            if any(c.get("slot") == slot for c in existing):
                counts["steps_skipped"] += 1
                continue

            if action == "audio":
                src = next((c for c in existing if c.get("slot") == 0), None)
                if src is None:
                    continue   # no source clip to duplicate
                try:
                    ch.duplicate_clip(ti, 0, slot).result(timeout=10)
                    counts["audio_clip_dupes"] += 1
                    time.sleep(0.1)
                except Exception as e:
                    print(f"  compose {scene_name}/{role} dupe fail: {e}")
            elif callable(action):
                try:
                    notes = action()
                    ch.create_clip(ti, slot, clip_len).result(timeout=10)
                    time.sleep(0.1)
                    if notes:
                        ch.add_notes_to_clip(ti, slot, notes).result(timeout=10)
                    ch.set_clip_name(ti, slot, scene_name).result(timeout=5)
                    counts["midi_clips"] += 1
                    time.sleep(0.1)
                except Exception as e:
                    print(f"  compose {scene_name}/{role} midi fail: {e}")


# ---- inspection helpers ----------------

def _channel_kind(layout, role: str) -> str:
    """Return 'audio' / 'sampler' / 'synth' / 'drum_rack' for a role."""
    if layout is None:
        return "audio"
    spec = layout.channel_by_role(role)
    return spec.kind.value if spec else "audio"


def _channel_already_has_sample(ch, track_index: int, kind: str, item_name: str) -> bool:
    """Idempotent check: would loading item_name on this track be a no-op?"""
    needle = item_name.rsplit(".", 1)[0].lower()  # strip extension for matching
    if kind == "audio":
        try:
            clips = ch.get_track_clips(track_index).result(timeout=3)
            for c in clips.get("clips", []):
                if c.get("slot") == 0 and needle in c.get("name", "").lower():
                    return True
        except Exception: pass
        return False
    if kind == "sampler":
        try:
            info = ch.get_track_info(track_index).result(timeout=3)
            for d in info.get("devices", []):
                if d.get("class_name") == "OriginalSimpler":
                    name = d.get("name", "").strip()
                    # Default Simpler name is "Simpler"; loaded sample renames the device.
                    if name and name.lower() != "simpler":
                        return True
        except Exception: pass
        return False
    return False


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
