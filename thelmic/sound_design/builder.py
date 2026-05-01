"""Fluent constructor for Patches."""

from __future__ import annotations

from typing import Optional

from thelmic.sound_design.patch import (
    Patch,
    DeviceSpec,
    MacroSpec,
    MacroMapping,
)
from thelmic.sound_design.knowledge import resolve_param_name


class PatchBuilder:
    """Fluent builder. All methods return self for chaining.

    Example:
        p = (PatchBuilder("reese_oak")
             .target("bass")
             .affinity("oak")
             .load_native("Operator", alias="osc")
             .set("osc.Filter Freq", 800)
             .set("osc.Volume", -6)
             .macro(0, "Brightness",
                    [("osc.Filter Freq", 200, 8000, "exp")])
             .build())
    """

    def __init__(self, name: str, parent: Optional[str] = None):
        self._patch = Patch(name=name, parent=parent)
        self._aliases: set[str] = set()
        # Track class_name per alias so resolve_param_name can be applied at
        # set() time when curated knowledge is available.
        self._alias_class: dict[str, str] = {}

    def target(self, track_hint: str) -> "PatchBuilder":
        self._patch.target_track_hint = track_hint
        return self

    def affinity(self, territory: str) -> "PatchBuilder":
        self._patch.territory_affinity = territory
        return self

    def meta(self, **kwargs) -> "PatchBuilder":
        self._patch.meta.update(kwargs)
        return self

    def load_native(self, class_name: str, *, alias: Optional[str] = None) -> "PatchBuilder":
        a = alias or class_name.lower()
        if a in self._aliases:
            raise ValueError("alias already used: " + a)
        self._aliases.add(a)
        self._alias_class[a] = class_name
        self._patch.chain.append(DeviceSpec(kind="native", ref=class_name, alias=a))
        return self

    def load_preset(
        self,
        ref: str,
        *,
        alias: str,
        class_name: Optional[str] = None,
    ) -> "PatchBuilder":
        if alias in self._aliases:
            raise ValueError("alias already used: " + alias)
        self._aliases.add(alias)
        if class_name:
            self._alias_class[alias] = class_name
        self._patch.chain.append(DeviceSpec(kind="preset", ref=ref, alias=alias))
        return self

    def set(self, key: str, value: float) -> "PatchBuilder":
        """Set an override. key is 'alias.param_name'.

        If the alias's device class is curated, resolve_param_name fuzzy-matches
        the param name against the curated list. Catches typos at build time.
        """
        if "." not in key:
            raise ValueError("override key must be 'alias.param_name': " + key)
        alias, param = key.split(".", 1)
        if alias not in self._aliases:
            raise ValueError("unknown alias: " + alias)
        klass = self._alias_class.get(alias)
        if klass:
            resolved = resolve_param_name(klass, param)
            if resolved is None:
                # Not in curated knowledge — accept as-is, Live will validate at apply time
                resolved = param
            param = resolved
        self._patch.overrides[alias + "." + param] = float(value)
        return self

    def macro(
        self,
        macro_index: int,
        name: str,
        mappings: list[tuple[str, float, float, str]] | None = None,
    ) -> "PatchBuilder":
        ms = []
        for tgt, lo, hi, curve in mappings or []:
            if "." not in tgt:
                raise ValueError("macro mapping target must be 'alias.param': " + tgt)
            alias, _ = tgt.split(".", 1)
            if alias not in self._aliases:
                raise ValueError("unknown alias in macro mapping: " + alias)
            ms.append(MacroMapping(target=tgt, range_min=float(lo), range_max=float(hi), curve=curve))
        self._patch.macros.append(MacroSpec(macro_index=macro_index, name=name, mappings=ms))
        return self

    def build(self) -> Patch:
        return self._patch
