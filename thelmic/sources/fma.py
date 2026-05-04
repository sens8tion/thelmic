"""Free Music Archive — disabled.

The original FMA API was decommissioned in 2018. The site has been through
several rebuilds since; there is no stable public search endpoint as of
2026-05. Left as a no-op so the unified ``find()`` doesn't break.

If you need CC-licensed *music* (not just sound effects), Internet Archive
already covers most of what FMA hosted, and freesound has a "music" type
filter via ``search(..., type='music')``.
"""

from __future__ import annotations

from pathlib import Path

from ._base import Sound, SourceError


def available() -> bool:
    return False


def search(query: str, *, limit: int = 10, **filters) -> list[Sound]:
    return []


def fetch(sound: Sound) -> Path:
    raise SourceError("FMA adapter is disabled (API decommissioned)")
