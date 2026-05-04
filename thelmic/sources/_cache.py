from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
import urllib.request
from pathlib import Path

from ._base import SourceError


def cache_root() -> Path:
    override = os.environ.get("THELMIC_CACHE")
    if override:
        root = Path(override)
    else:
        from ._config import config_dir
        root = config_dir() / "samples"
    root.mkdir(parents=True, exist_ok=True)
    return root


def cache_path(source: str, key: str, ext: str) -> Path:
    safe = hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]
    ext = ext.lstrip(".") or "bin"
    d = cache_root() / source
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{safe}.{ext}"


def http_get_json(url: str, *, headers: dict[str, str] | None = None, timeout: int = 20):
    import json
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:
        raise SourceError(f"GET {url}: {e}") from e


def download(url: str, dest: Path, *, headers: dict[str, str] | None = None, timeout: int = 60) -> Path:
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    req = urllib.request.Request(url, headers=headers or {})
    fd, tmp_name = tempfile.mkstemp(prefix="thelmic_", dir=dest.parent)
    os.close(fd)  # Windows: close the fd from mkstemp before opening it again
    tmp = Path(tmp_name)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r, tmp.open("wb") as f:
            shutil.copyfileobj(r, f)
        tmp.replace(dest)
    except Exception as e:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        raise SourceError(f"download {url}: {e}") from e
    return dest
