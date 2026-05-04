"""Lightweight env loader for ``<repo>/.thelmic/.env``.

Called once at import time. Only sets keys that aren't already in os.environ
(real env vars always win). Format: ``KEY=value`` per line, ``#`` comments OK.
"""

from __future__ import annotations

import os
from pathlib import Path


def _repo_root() -> Path:
    p = Path(__file__).resolve()
    for parent in p.parents:
        if (parent / "pyproject.toml").is_file() or (parent / ".git").exists():
            return parent
    return p.parent


def config_dir() -> Path:
    return _repo_root() / ".thelmic"


def _load() -> None:
    path = config_dir() / ".env"
    if not path.is_file():
        return
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            k, v = k.strip(), v.strip().strip('"').strip("'")
            if k and k not in os.environ:
                os.environ[k] = v
    except OSError:
        pass


_load()
