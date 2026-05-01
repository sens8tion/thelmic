"""Filesystem-backed patch library — one JSON per patch.

Default location: ~/.thelmic/patches/. Overridable via THELMIC_PATCH_DIR.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from thelmic.sound_design.patch import Patch

_SAFE = re.compile(r"[^A-Za-z0-9._-]+")


def _default_dir() -> Path:
    env = os.environ.get("THELMIC_PATCH_DIR")
    if env:
        return Path(env)
    return Path.home() / ".thelmic" / "patches"


def _ensure_dir(d: Path) -> Path:
    d.mkdir(parents=True, exist_ok=True)
    return d


def _safe_name(name: str) -> str:
    s = _SAFE.sub("_", name).strip("._-") or "patch"
    return s


def save_patch(patch: Patch, *, directory: Path | str | None = None) -> Path:
    d = _ensure_dir(Path(directory) if directory else _default_dir())
    path = d / (_safe_name(patch.name) + ".json")
    path.write_text(patch.to_json(), encoding="utf-8")
    return path


def load_patch(name: str, *, directory: Path | str | None = None) -> Patch:
    d = Path(directory) if directory else _default_dir()
    path = d / (_safe_name(name) + ".json")
    return Patch.from_json(path.read_text(encoding="utf-8"))


def list_patches(*, directory: Path | str | None = None) -> list[str]:
    d = Path(directory) if directory else _default_dir()
    if not d.exists():
        return []
    out = []
    for f in sorted(d.iterdir()):
        if f.suffix == ".json":
            try:
                p = Patch.from_json(f.read_text(encoding="utf-8"))
                out.append(p.name)
            except Exception:
                continue
    return out
