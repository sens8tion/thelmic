"""BBC Sound Effects (RemArc) adapter.

License: PERSONAL / EDUCATIONAL / RESEARCH USE ONLY. Not for commercial use.
See https://sound-effects.bbcrewind.co.uk/licensing

The site backs onto an undocumented Elasticsearch service at
``sound-effects-api.bbcrewind.co.uk``. No API key required. May break if BBC
restructure the service.
"""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path

from ._base import Sound, SourceError
from ._cache import cache_path, download

_API = "https://sound-effects-api.bbcrewind.co.uk/api/sfx/search"
_MEDIA = "https://sound-effects-media.bbcrewind.co.uk/mp3/{id}.mp3"
_PAGE = "https://sound-effects.bbcrewind.co.uk/search?q={id}"
_UA = "Mozilla/5.0 (compatible; thelmic/1.0)"


def available() -> bool:
    return True


def search(query: str, *, limit: int = 10, **filters) -> list[Sound]:
    body = {
        "criteria": {
            "from": 0,
            "size": min(limit, 50),
            "query": query,
            "tags": None,
            "categories": None,
            "continents": None,
            "countries": None,
            "recordists": None,
            "habitats": None,
            "durationFrom": None,
            "durationTo": None,
            "source": None,
        }
    }
    req = urllib.request.Request(
        _API,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": _UA,
            "Origin": "https://sound-effects.bbcrewind.co.uk",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read().decode("utf-8"))
    except Exception as e:
        raise SourceError(f"bbc search: {e}") from e
    out: list[Sound] = []
    for hit in (data.get("results") or [])[:limit]:
        sid = str(hit.get("id") or "")
        if not sid:
            continue
        # duration in the API is milliseconds.
        dur_ms = hit.get("duration")
        duration = (dur_ms / 1000.0) if isinstance(dur_ms, (int, float)) else None
        cats = hit.get("categories") or []
        cat_names = tuple(c.get("className", "") for c in cats if isinstance(c, dict))
        out.append(
            Sound(
                source="bbc",
                id=sid,
                title=hit.get("description") or sid,
                url=_PAGE.format(id=sid),
                download_url=_MEDIA.format(id=sid),
                duration=duration,
                license="BBC RemArc (personal/educational/research only)",
                tags=tuple(hit.get("tags") or ()) + cat_names,
                extra={
                    "cd": (hit.get("additionalMetadata") or {}).get("cdName"),
                    "location": (hit.get("location") or {}).get("continent"),
                    "source": hit.get("source"),
                },
            )
        )
    return out


def fetch(sound: Sound) -> Path:
    if not sound.download_url:
        raise SourceError(f"no download URL for {sound.id}")
    dest = cache_path("bbc", sound.id, "mp3")
    return download(sound.download_url, dest, headers={"User-Agent": _UA})
