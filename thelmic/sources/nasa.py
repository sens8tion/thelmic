"""NASA audio library adapter.

Public domain. https://images-api.nasa.gov/
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlencode

from ._base import Sound, SourceError
from ._cache import cache_path, download, http_get_json

_SEARCH = "https://images-api.nasa.gov/search"


def available() -> bool:
    return True


def search(query: str, *, limit: int = 10, **filters) -> list[Sound]:
    params = {"q": query, "media_type": "audio", "page_size": min(limit, 100)}
    data = http_get_json(f"{_SEARCH}?{urlencode(params)}")
    items = ((data.get("collection") or {}).get("items")) or []
    out = []
    for it in items[:limit]:
        d = (it.get("data") or [{}])[0]
        nasa_id = d.get("nasa_id")
        if not nasa_id:
            continue
        out.append(
            Sound(
                source="nasa",
                id=nasa_id,
                title=d.get("title", nasa_id),
                url=f"https://images.nasa.gov/details-{nasa_id}",
                download_url=None,  # resolved via asset manifest in fetch()
                duration=None,
                license="NASA / public domain",
                tags=tuple(d.get("keywords") or ()),
                extra={"asset_url": it.get("href")},
            )
        )
    return out


def fetch(sound: Sound) -> Path:
    asset_url = sound.extra.get("asset_url")
    if not asset_url:
        raise SourceError(f"no asset manifest URL for {sound.id}")
    manifest = http_get_json(asset_url)
    if not isinstance(manifest, list):
        raise SourceError(f"unexpected NASA asset manifest for {sound.id}")
    audio_url = None
    ext = "mp3"
    for u in manifest:
        for cand_ext in ("mp3", "wav", "m4a"):
            if u.lower().endswith("." + cand_ext) and "preview" not in u.lower():
                audio_url, ext = u, cand_ext
                break
        if audio_url:
            break
    if not audio_url:
        raise SourceError(f"no playable audio in {sound.id} manifest")
    dest = cache_path("nasa", f"{sound.id}.{ext}", ext)
    return download(audio_url, dest)
