"""Freesound.org adapter.

Reads ``FREESOUND_API_KEY`` from the environment. Get one at
https://freesound.org/apiv2/apply/ — free, instant.

Token-auth gives metadata + 30s previews. To download the FULL original file
you need OAuth2 — set ``FREESOUND_OAUTH_TOKEN`` (a user access token) and
:func:`fetch` will use that. Otherwise it falls back to the high-quality
preview MP3 (still very usable for sample chopping).
"""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlencode

from ._base import Sound, SourceError
from ._cache import cache_path, download, http_get_json

_BASE = "https://freesound.org/apiv2"
_FIELDS = "id,name,url,previews,duration,license,tags,download,type"


def _key() -> str | None:
    return os.environ.get("FREESOUND_API_KEY")


def _oauth() -> str | None:
    return os.environ.get("FREESOUND_OAUTH_TOKEN")


def available() -> bool:
    return _key() is not None


def search(query: str, *, limit: int = 10, **filters) -> list[Sound]:
    if not available():
        raise SourceError("FREESOUND_API_KEY not set")
    params = {
        "query": query,
        "page_size": min(limit, 150),
        "fields": _FIELDS,
    }
    fq_parts = []
    if "max_duration" in filters:
        fq_parts.append(f"duration:[0 TO {filters['max_duration']}]")
    if "license" in filters:
        fq_parts.append(f'license:"{filters["license"]}"')
    if fq_parts:
        params["filter"] = " ".join(fq_parts)
    headers = {"Authorization": f"Token {_key()}"}
    data = http_get_json(f"{_BASE}/search/text/?{urlencode(params)}", headers=headers)
    out = []
    have_oauth = _oauth() is not None
    for r in data.get("results", []):
        previews = r.get("previews") or {}
        preview_url = previews.get("preview-hq-mp3") or previews.get("preview-lq-mp3")
        if have_oauth:
            download_url = r.get("download") or preview_url
        else:
            download_url = preview_url or r.get("download")
        out.append(
            Sound(
                source="freesound",
                id=str(r["id"]),
                title=r.get("name", ""),
                url=r.get("url", f"https://freesound.org/s/{r['id']}/"),
                download_url=download_url,
                duration=r.get("duration"),
                license=r.get("license"),
                tags=tuple(r.get("tags") or ()),
                extra={"type": r.get("type"), "preview_url": preview_url},
            )
        )
    return out


def fetch(sound: Sound) -> Path:
    url = sound.download_url
    ext = (sound.extra.get("type") or "mp3").lower()
    # If we have an OAuth token, prefer the API download endpoint for the full original.
    oauth = _oauth()
    if oauth:
        url = f"{_BASE}/sounds/{sound.id}/download/"
        headers = {"Authorization": f"Bearer {oauth}"}
    else:
        # Token-auth users can still pull preview MP3s, but the freesound CDN
        # now requires the Token header on those URLs too.
        if not _key():
            raise SourceError("FREESOUND_API_KEY not set")
        headers = {"Authorization": f"Token {_key()}"}
    if not url:
        raise SourceError(f"no download URL for {sound.id}")
    if "preview" in url:
        ext = "mp3"
    dest = cache_path("freesound", f"{sound.id}.{ext}", ext)
    return download(url, dest, headers=headers)
