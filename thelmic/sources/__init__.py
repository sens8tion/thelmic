"""Royalty-free / personal-use sample sources.

Unified API:

    from thelmic.sources import find, fetch, list_sources

    hits = find("sub bass drone", limit=20)
    path = fetch(hits[0])     # downloads + caches, returns local Path

Each adapter exposes ``search(query, *, limit, **filters) -> list[Sound]`` and
``fetch(sound) -> Path``. ``find()`` fans out across all enabled adapters.

Licensing (READ THIS):
    freesound        — CC0 / CC-BY / CC-Sampling+ (per-sound; check Sound.license)
    bbc              — Personal / educational / research use only. NOT commercial.
    internet_archive — Per-item; usually public domain or CC. Check Sound.license.
    nasa             — Public domain.
    fma              — Per-item CC. (API was deprecated; adapter is best-effort.)
    epidemic         — Subscription-gated; stubbed. Not royalty-free.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from . import _config  # noqa: F401  — populates os.environ from ~/.thelmic/.env
from ._base import Sound, SourceError
from ._cache import cache_root

from . import freesound, bbc, internet_archive, nasa, fma, epidemic

_ADAPTERS = {
    "freesound": freesound,
    "bbc": bbc,
    "internet_archive": internet_archive,
    "nasa": nasa,
    "fma": fma,
    "epidemic": epidemic,
}


def list_sources() -> list[str]:
    return [name for name, mod in _ADAPTERS.items() if mod.available()]


def find(
    query: str,
    *,
    limit: int = 10,
    sources: Iterable[str] | None = None,
) -> list[Sound]:
    """Fan-out search. Returns up to ``limit`` results per source, interleaved."""
    names = list(sources) if sources else list_sources()
    buckets: list[list[Sound]] = []
    for name in names:
        mod = _ADAPTERS.get(name)
        if mod is None or not mod.available():
            continue
        try:
            buckets.append(list(mod.search(query, limit=limit)))
        except SourceError:
            buckets.append([])
    out: list[Sound] = []
    for i in range(limit):
        for bucket in buckets:
            if i < len(bucket):
                out.append(bucket[i])
    return out


def fetch(sound: Sound) -> Path:
    mod = _ADAPTERS[sound.source]
    return mod.fetch(sound)


__all__ = ["Sound", "SourceError", "find", "fetch", "list_sources", "cache_root"]
