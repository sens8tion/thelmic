"""Curated device-knowledge JSON loader + parameter name resolver.

The JSON files under thelmic/sound_design/devices/ describe parameter names,
ranges, and musical groupings for stock Live devices. This is OUR map of the
device — not Live's source of truth. Used to:
  - validate parameter names before round-tripping to Live (catch typos)
  - power fuzzy resolution when a patch refers to a parameter by approximate name
  - drive the LLM's revise_patch prompt (next phase)
"""

from __future__ import annotations

import difflib
import json
import os
from functools import lru_cache
from typing import Optional

_DEVICES_DIR = os.path.join(os.path.dirname(__file__), "devices")


@lru_cache(maxsize=None)
def load_device_knowledge(class_name: str) -> Optional[dict]:
    """Load the JSON for a device class. Returns None if not curated yet."""
    path = os.path.join(_DEVICES_DIR, class_name + ".json")
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def list_curated_devices() -> list[str]:
    if not os.path.isdir(_DEVICES_DIR):
        return []
    return sorted(
        os.path.splitext(f)[0]
        for f in os.listdir(_DEVICES_DIR)
        if f.endswith(".json")
    )


def resolve_param_name(
    class_name: str,
    query: str,
    *,
    live_param_names: list[str] | None = None,
) -> Optional[str]:
    """Map a fuzzy query to a canonical parameter name.

    Order:
      1. Exact match against curated knowledge (if loaded).
      2. Case-insensitive match against curated knowledge.
      3. If `live_param_names` provided, exact + case-insensitive there.
      4. difflib closest match against curated, threshold 0.7.
      5. difflib closest match against `live_param_names`, threshold 0.7.
    Returns None if no confident match.
    """
    if not query:
        return None
    knowledge = load_device_knowledge(class_name) or {}
    curated = [p["name"] for p in knowledge.get("params", [])]
    pools: list[list[str]] = []
    if curated:
        pools.append(curated)
    if live_param_names:
        pools.append(list(live_param_names))

    q_lower = query.lower()
    for pool in pools:
        for name in pool:
            if name == query:
                return name
        for name in pool:
            if name.lower() == q_lower:
                return name
    for pool in pools:
        matches = difflib.get_close_matches(query, pool, n=1, cutoff=0.7)
        if matches:
            return matches[0]
    return None


def bootstrap_device_knowledge(
    channel,
    track_index: int,
    device_index: int,
    *,
    summary: str = "",
    groups: dict | None = None,
    musical_archetypes: dict | None = None,
    notes: str = "",
    overwrite: bool = False,
) -> str:
    """Introspect a live device and write a curated JSON with REAL ranges.

    Returns the absolute path of the file written. Refuses to overwrite an
    existing file unless `overwrite=True`.
    """
    di = channel.get_device_info(track_index, device_index).result(timeout=10)
    class_name = di["class_name"]
    path = os.path.join(_DEVICES_DIR, class_name + ".json")
    if os.path.exists(path) and not overwrite:
        raise FileExistsError(path + " already exists; pass overwrite=True to replace.")

    params = []
    for p in di["parameters"]:
        params.append({
            "name": p["name"],
            "min": p["min"],
            "max": p["max"],
            "default": p["value"],
            "is_quantized": p.get("is_quantized", False),
            "groups": [],
        })
    payload = {
        "class": class_name,
        "summary": summary or ("Auto-generated from " + class_name + " introspection."),
        "params": params,
        "groups": groups or {},
        "musical_archetypes": musical_archetypes or {},
        "notes": notes,
        "_bootstrapped": True,
    }
    os.makedirs(_DEVICES_DIR, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    # Bust the lru_cache so subsequent loads see the fresh JSON.
    load_device_knowledge.cache_clear()
    return path


def param_range(class_name: str, param_name: str) -> Optional[tuple[float, float]]:
    knowledge = load_device_knowledge(class_name)
    if not knowledge:
        return None
    for p in knowledge.get("params", []):
        if p["name"] == param_name:
            return float(p["min"]), float(p["max"])
    return None
