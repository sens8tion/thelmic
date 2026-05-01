"""Patch dataclasses + lineage flattening.

Patches are pure data; serialise/deserialise to JSON. Lineage flattening
merges parent → child by replacing chain (if child non-empty), replacing
macros (if child non-empty), and last-write-wins on overrides.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import Any, Optional

SCHEMA_VERSION = 1


@dataclass
class MacroMapping:
    target: str  # "device_alias.param_name"
    range_min: float
    range_max: float
    curve: str = "linear"  # "linear" | "exp" | "log" | "sCurve"


@dataclass
class MacroSpec:
    macro_index: int  # 0..15
    name: str
    mappings: list[MacroMapping] = field(default_factory=list)


@dataclass
class DeviceSpec:
    """One entry in a Patch's device chain.

    `kind`:
      - "native": `ref` is a Live class name like "Operator". The patch can
        only set parameters; the device must be loaded via the Live browser
        (we don't synthesise device XML).
      - "preset": `ref` is a browser path like "instruments/Operator/Lead.adv"
        OR a browser URI. apply_patch resolves to URI before loading.
    """

    kind: str  # "native" | "preset"
    ref: str
    alias: str  # local name within chain (used in override keys + macro targets)
    params: dict[str, float] = field(default_factory=dict)
    enabled: bool = True


@dataclass
class Patch:
    name: str
    parent: Optional[str] = None
    target_track_hint: Optional[str] = None
    territory_affinity: Optional[str] = None  # "oak" | "nott" | "chaos" | None
    chain: list[DeviceSpec] = field(default_factory=list)
    macros: list[MacroSpec] = field(default_factory=list)
    overrides: dict[str, float] = field(default_factory=dict)  # "alias.param" -> value
    meta: dict[str, Any] = field(default_factory=dict)
    version: int = SCHEMA_VERSION

    def to_json(self) -> str:
        return json.dumps(_patch_to_dict(self), indent=2, sort_keys=True)

    @classmethod
    def from_json(cls, s: str) -> "Patch":
        return _patch_from_dict(json.loads(s))

    def to_dict(self) -> dict:
        return _patch_to_dict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Patch":
        return _patch_from_dict(d)


@dataclass
class ResolvedPatch:
    """Materialised patch after lineage flattening — ready to apply."""

    name: str
    chain: list[DeviceSpec]
    macros: list[MacroSpec]
    overrides: dict[str, float]
    target_track_hint: Optional[str]
    territory_affinity: Optional[str]
    meta: dict[str, Any]


def _patch_to_dict(p: Patch) -> dict:
    return {
        "name": p.name,
        "parent": p.parent,
        "target_track_hint": p.target_track_hint,
        "territory_affinity": p.territory_affinity,
        "chain": [asdict(d) for d in p.chain],
        "macros": [
            {
                "macro_index": m.macro_index,
                "name": m.name,
                "mappings": [asdict(mm) for mm in m.mappings],
            }
            for m in p.macros
        ],
        "overrides": dict(p.overrides),
        "meta": dict(p.meta),
        "version": p.version,
    }


def _patch_from_dict(d: dict) -> Patch:
    chain = [DeviceSpec(**c) for c in d.get("chain", [])]
    macros = []
    for m in d.get("macros", []):
        mappings = [MacroMapping(**mm) for mm in m.get("mappings", [])]
        macros.append(MacroSpec(macro_index=m["macro_index"], name=m["name"], mappings=mappings))
    return Patch(
        name=d["name"],
        parent=d.get("parent"),
        target_track_hint=d.get("target_track_hint"),
        territory_affinity=d.get("territory_affinity"),
        chain=chain,
        macros=macros,
        overrides=dict(d.get("overrides", {})),
        meta=dict(d.get("meta", {})),
        version=d.get("version", SCHEMA_VERSION),
    )


def flatten_lineage(patch: Patch, library: dict[str, Patch]) -> ResolvedPatch:
    """Walk parent chain root→leaf, materialise.

    - chain: child non-empty wins; else inherit nearest ancestor.
    - macros: child non-empty wins; else inherit.
    - overrides: ancestors first, leaf last (last-write-wins).
    - target_track_hint, territory_affinity: child wins if non-None.
    """
    ancestry: list[Patch] = []
    seen: set[str] = set()
    cur: Optional[Patch] = patch
    while cur is not None:
        if cur.name in seen:
            raise ValueError("lineage cycle at " + cur.name)
        seen.add(cur.name)
        ancestry.append(cur)
        if cur.parent is None:
            break
        nxt = library.get(cur.parent)
        if nxt is None:
            raise ValueError("missing parent: " + cur.parent)
        cur = nxt
    ancestry.reverse()  # root → leaf

    chain: list[DeviceSpec] = []
    macros: list[MacroSpec] = []
    overrides: dict[str, float] = {}
    target_hint = None
    aff = None
    meta: dict[str, Any] = {}
    for p in ancestry:
        if p.chain:
            chain = [DeviceSpec(**asdict(d)) for d in p.chain]
        if p.macros:
            macros = [
                MacroSpec(
                    macro_index=m.macro_index,
                    name=m.name,
                    mappings=[MacroMapping(**asdict(mm)) for mm in m.mappings],
                )
                for m in p.macros
            ]
        overrides.update(p.overrides)
        if p.target_track_hint is not None:
            target_hint = p.target_track_hint
        if p.territory_affinity is not None:
            aff = p.territory_affinity
        meta.update(p.meta)

    return ResolvedPatch(
        name=patch.name,
        chain=chain,
        macros=macros,
        overrides=overrides,
        target_track_hint=target_hint,
        territory_affinity=aff,
        meta=meta,
    )
