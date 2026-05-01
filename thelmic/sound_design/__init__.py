"""Sound design subsystem.

A consumer of thelmic.live_channel — not part of it. Patches are data; the
PatchBuilder constructs them; apply_patch reifies them in Live.

Off by default. Enable with env var SOUND_DESIGN_ENABLED=1 (channel must also
be enabled). Currently the env flag is advisory: the module functions work
when called, but server.py / CLI integration should gate on this flag.
"""

from __future__ import annotations

import os

from thelmic.sound_design.patch import (
    Patch,
    DeviceSpec,
    MacroSpec,
    MacroMapping,
    ResolvedPatch,
    flatten_lineage,
)
from thelmic.sound_design.builder import PatchBuilder
from thelmic.sound_design.apply import apply_patch, revise_patch
from thelmic.sound_design.library import save_patch, load_patch, list_patches
from thelmic.sound_design.knowledge import (
    load_device_knowledge,
    resolve_param_name,
)


def is_enabled() -> bool:
    val = os.environ.get("SOUND_DESIGN_ENABLED", "")
    return val.lower() in ("1", "true", "yes", "on")


__all__ = [
    "Patch",
    "DeviceSpec",
    "MacroSpec",
    "MacroMapping",
    "ResolvedPatch",
    "PatchBuilder",
    "apply_patch",
    "revise_patch",
    "save_patch",
    "load_patch",
    "list_patches",
    "load_device_knowledge",
    "resolve_param_name",
    "flatten_lineage",
    "is_enabled",
]
