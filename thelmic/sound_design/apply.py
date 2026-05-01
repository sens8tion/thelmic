"""Apply a Patch to a Live track via the LiveChannel.

Modes:
  replace  → snapshot current track, delete chain, build fresh, set params, define macros.
  overlay  → append chain to existing devices, set params, define macros.
  morph    → interpolate parameter values from current to target over N steps.

All modes return only after the bulk lane drains. apply_patch is intended to be
called from a sound-design CLI / REPL, not from the realtime sequencer.
"""

from __future__ import annotations

import logging
import time
from concurrent.futures import Future
from typing import Optional

from thelmic.live_channel import LiveChannel, LANE_BULK, LANE_PRIORITY
from thelmic.sound_design.patch import (
    Patch,
    ResolvedPatch,
    DeviceSpec,
    flatten_lineage,
)

LOG = logging.getLogger("thelmic.sound_design.apply")

MODE_REPLACE = "replace"
MODE_OVERLAY = "overlay"
MODE_MORPH = "morph"


class ApplyError(RuntimeError):
    pass


def apply_patch(
    channel: LiveChannel,
    patch: Patch,
    track_index: int,
    *,
    mode: str = MODE_REPLACE,
    library: dict[str, Patch] | None = None,
    morph_steps: int = 32,
    morph_step_ms: int = 50,
    timeout_per_op: float = 10.0,
) -> dict:
    """Apply a Patch to a track.

    Returns a summary dict {mode, devices_loaded, params_set, macros_defined,
    snapshot}. Raises ApplyError on failure.
    """
    if library is None:
        library = {patch.name: patch}
    elif patch.name not in library:
        library = {**library, patch.name: patch}
    resolved = flatten_lineage(patch, library)

    if mode == MODE_REPLACE:
        return _apply_replace(channel, resolved, track_index, timeout_per_op)
    if mode == MODE_OVERLAY:
        return _apply_overlay(channel, resolved, track_index, timeout_per_op)
    if mode == MODE_MORPH:
        return _apply_morph(
            channel, resolved, track_index, morph_steps, morph_step_ms, timeout_per_op
        )
    raise ApplyError("unknown mode: " + mode)


# ---------------------------------------------------------------------------
# Mode implementations
# ---------------------------------------------------------------------------


def _apply_replace(
    channel: LiveChannel,
    resolved: ResolvedPatch,
    track_index: int,
    timeout: float,
) -> dict:
    snap = _await(channel.snapshot_track(track_index), timeout)
    # delete in reverse so indices remain valid
    info = _await(channel.get_track_info(track_index), timeout)
    for di in reversed(range(info["device_count"])):
        _await(channel.delete_device(track_index, di), timeout)
    # load new chain
    aliases_to_index: dict[str, int] = {}
    for spec in resolved.chain:
        idx = _load_device(channel, track_index, spec, timeout)
        aliases_to_index[spec.alias] = idx
    # set params (bulk lane — they're not territory-driven)
    params_set = _apply_overrides(
        channel, track_index, resolved, aliases_to_index, timeout, lane=LANE_BULK
    )
    # macros
    macros_defined = _apply_macros(channel, track_index, resolved, aliases_to_index, timeout)
    return {
        "mode": MODE_REPLACE,
        "devices_loaded": len(resolved.chain),
        "params_set": params_set,
        "macros_defined": macros_defined,
        "snapshot": snap,
    }


def _apply_overlay(
    channel: LiveChannel,
    resolved: ResolvedPatch,
    track_index: int,
    timeout: float,
) -> dict:
    info = _await(channel.get_track_info(track_index), timeout)
    base = info["device_count"]
    aliases_to_index: dict[str, int] = {}
    for i, spec in enumerate(resolved.chain):
        idx = _load_device(channel, track_index, spec, timeout)
        # When loading appends, idx ~ base + i (new device sits at end of chain).
        aliases_to_index[spec.alias] = idx if idx is not None else base + i
    params_set = _apply_overrides(
        channel, track_index, resolved, aliases_to_index, timeout, lane=LANE_BULK
    )
    macros_defined = _apply_macros(channel, track_index, resolved, aliases_to_index, timeout)
    return {
        "mode": MODE_OVERLAY,
        "devices_loaded": len(resolved.chain),
        "params_set": params_set,
        "macros_defined": macros_defined,
        "snapshot": None,
    }


def _apply_morph(
    channel: LiveChannel,
    resolved: ResolvedPatch,
    track_index: int,
    steps: int,
    step_ms: int,
    timeout: float,
) -> dict:
    """Param-only morph. Requires the chain on the track ALREADY matches the
    resolved chain (by class_name + alias mapping). Errors otherwise — morph
    does not change device structure.
    """
    info = _await(channel.get_track_info(track_index), timeout)
    if info["device_count"] != len(resolved.chain):
        raise ApplyError(
            "morph requires identical chain length: have %d devices, patch has %d"
            % (info["device_count"], len(resolved.chain))
        )
    aliases_to_index: dict[str, int] = {}
    for i, spec in enumerate(resolved.chain):
        live_dev = info["devices"][i]
        if spec.kind == "native" and live_dev["class_name"] != spec.ref:
            raise ApplyError(
                "morph chain mismatch at slot %d: want %s, have %s"
                % (i, spec.ref, live_dev["class_name"])
            )
        aliases_to_index[spec.alias] = i

    # Read current values for everything we plan to set.
    targets: list[tuple[int, str, float, float]] = []  # (device_idx, param_name, start, end)
    for key, target_v in resolved.overrides.items():
        alias, pname = key.split(".", 1)
        di = aliases_to_index.get(alias)
        if di is None:
            continue
        cur = _await(channel.get_device_param(track_index, di, pname), timeout)
        targets.append((di, pname, float(cur["value"]), float(target_v)))

    # Linear trajectory; bulk lane.
    for step in range(1, steps + 1):
        t = step / float(steps)
        for di, pname, start, end in targets:
            v = start + (end - start) * t
            channel.submit_bulk("set_device_param", {
                "track_index": track_index,
                "device_index": di,
                "param_name": pname,
                "value": v,
            })
        # Pace the dispatch so Live UI doesn't choke.
        time.sleep(step_ms / 1000.0)

    return {
        "mode": MODE_MORPH,
        "devices_loaded": 0,
        "params_set": len(targets) * steps,
        "macros_defined": 0,
        "snapshot": None,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _await(fut: Future, timeout: float):
    try:
        return fut.result(timeout=timeout)
    except Exception as e:
        raise ApplyError(str(e)) from e


def _load_device(
    channel: LiveChannel,
    track_index: int,
    spec: DeviceSpec,
    timeout: float,
) -> Optional[int]:
    """Load a device described by `spec` onto the track. Returns the new
    device's index in the track chain (best-effort: for `kind=native` we walk
    the browser to find the URI; for `kind=preset` we accept either a URI or
    a path and convert path → URI by walking)."""
    if spec.kind == "native":
        uri = _native_uri(channel, spec.ref, timeout)
    elif spec.kind == "preset":
        if spec.ref.startswith("query:"):
            uri = spec.ref[6:]
        elif "/" in spec.ref or spec.ref.endswith(".adv"):
            # path → URI walk
            res = _await(channel.get_browser_items_at_path(_dirname(spec.ref)), timeout)
            target_name = _basename(spec.ref)
            uri = None
            for item in res.get("items", []):
                if (item.get("name") or "").lower() == target_name.lower():
                    uri = item.get("uri")
                    break
            if uri is None:
                raise ApplyError("preset not found: " + spec.ref)
        else:
            uri = spec.ref  # assume already a URI
    else:
        raise ApplyError("unknown DeviceSpec.kind: " + spec.kind)

    _await(channel.load_device(track_index, uri), timeout)
    info = _await(channel.get_track_info(track_index), timeout)
    return info["device_count"] - 1


_NATIVE_URI_CACHE: dict[str, str] = {}


def _native_uri(channel: LiveChannel, class_name: str, timeout: float) -> str:
    """Find a native device by walking the browser tree. Cached per process.

    Strategy: look under instruments/, audio_effects/, midi_effects/ for a
    folder/item whose name matches `class_name`. The URI we get back from
    Live's browser is what load_browser_item expects.
    """
    if class_name in _NATIVE_URI_CACHE:
        return _NATIVE_URI_CACHE[class_name]
    candidates = ["instruments", "audio_effects", "midi_effects", "drums"]
    target_lower = class_name.lower()
    for cat in candidates:
        try:
            res = _await(channel.get_browser_items_at_path(cat), timeout)
        except ApplyError:
            continue
        for item in res.get("items", []):
            nm = (item.get("name") or "").lower()
            if nm == target_lower and item.get("uri"):
                _NATIVE_URI_CACHE[class_name] = item["uri"]
                return item["uri"]
        # second pass: descend into folders one level
        for item in res.get("items", []):
            if not item.get("is_folder"):
                continue
            try:
                sub = _await(
                    channel.get_browser_items_at_path(cat + "/" + item["name"]), timeout
                )
            except ApplyError:
                continue
            for sit in sub.get("items", []):
                if (sit.get("name") or "").lower() == target_lower and sit.get("uri"):
                    _NATIVE_URI_CACHE[class_name] = sit["uri"]
                    return sit["uri"]
    raise ApplyError("native device not found in browser: " + class_name)


def _dirname(path: str) -> str:
    if "/" not in path:
        return ""
    return path.rsplit("/", 1)[0]


def _basename(path: str) -> str:
    if "/" not in path:
        return path
    return path.rsplit("/", 1)[1]


def _apply_overrides(
    channel: LiveChannel,
    track_index: int,
    resolved: ResolvedPatch,
    aliases_to_index: dict[str, int],
    timeout: float,
    *,
    lane: str,
) -> int:
    futs = []
    for key, value in resolved.overrides.items():
        alias, pname = key.split(".", 1)
        di = aliases_to_index.get(alias)
        if di is None:
            LOG.warning("override skipped, alias not loaded: %s", alias)
            continue
        if lane == LANE_BULK:
            futs.append(
                channel.submit_bulk("set_device_param", {
                    "track_index": track_index,
                    "device_index": di,
                    "param_name": pname,
                    "value": float(value),
                })
            )
        else:
            futs.append(channel.set_device_param(track_index, di, pname, float(value)))
    # await all
    for f in futs:
        try:
            f.result(timeout=timeout)
        except Exception as e:
            LOG.warning("override apply failed: %s", e)
    return len(futs)


def _apply_macros(
    channel: LiveChannel,
    track_index: int,
    resolved: ResolvedPatch,
    aliases_to_index: dict[str, int],
    timeout: float,
) -> int:
    n = 0
    for ms in resolved.macros:
        # Macros live on a Rack device. Find the FIRST rack in the chain that
        # contains our patched devices. If no rack present, skip with warning.
        info = _await(channel.get_track_info(track_index), timeout)
        rack_idx = None
        for d in info["devices"]:
            if d["class_name"] in ("InstrumentGroupDevice", "AudioEffectGroupDevice", "MidiEffectGroupDevice", "DrumGroupDevice"):
                rack_idx = d["index"]
                break
        if rack_idx is None:
            LOG.warning("macro %s skipped — no rack on track", ms.name)
            continue
        _await(
            channel.define_rack_macro(
                track_index,
                rack_idx,
                ms.macro_index,
                ms.name,
                [
                    {
                        "target": mm.target,
                        "range_min": mm.range_min,
                        "range_max": mm.range_max,
                        "curve": mm.curve,
                    }
                    for mm in ms.mappings
                ],
            ),
            timeout,
        )
        n += 1
    return n


# ---------------------------------------------------------------------------
# revise_patch — interface only (LLM call deferred to next phase).
# ---------------------------------------------------------------------------


def revise_patch(
    patch: Patch,
    feedback: str,
    *,
    llm: object | None = None,
) -> Patch:
    """Return a new patch derived from `patch` reflecting the user's feedback.

    Implementation in this phase:
      - If `llm` is None, raise NotImplementedError with guidance.
      - If `llm` is supplied, it must be a callable taking (system_prompt, user_prompt)
        and returning a JSON string of {"overrides": {...}}. We apply that as a new
        override layer on a child patch with parent=patch.name.

    Real LLM wiring (claude-api skill) lands in the next phase.
    """
    if llm is None:
        raise NotImplementedError(
            "revise_patch needs an llm callable. Wiring deferred to next phase."
        )
    raise NotImplementedError(
        "revise_patch with llm provided: stub. Implement against claude-api in next phase."
    )
