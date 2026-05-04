"""Internet Archive audio adapter.

Public API. No auth. License is per-item (mostly public domain or CC).
Search docs: https://archive.org/advancedsearch.php
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlencode

from ._base import Sound, SourceError
from ._cache import cache_path, download, http_get_json

_SEARCH = "https://archive.org/advancedsearch.php"
_META = "https://archive.org/metadata/{id}"
_UA = "thelmic/1.0"


def available() -> bool:
    return True


def search(query: str, *, limit: int = 10, **filters) -> list[Sound]:
    q = f'({query}) AND mediatype:(audio)'
    params = [
        ("q", q),
        ("fl[]", "identifier"),
        ("fl[]", "title"),
        ("fl[]", "licenseurl"),
        ("fl[]", "subject"),
        ("rows", str(min(limit, 50))),
        ("page", "1"),
        ("output", "json"),
    ]
    data = http_get_json(f"{_SEARCH}?{urlencode(params, doseq=True)}", headers={"User-Agent": _UA})
    docs = (data.get("response") or {}).get("docs") or []
    out = []
    for d in docs:
        ident = d.get("identifier")
        if not ident:
            continue
        subj = d.get("subject")
        if isinstance(subj, str):
            tags = (subj,)
        else:
            tags = tuple(subj or ())
        out.append(
            Sound(
                source="internet_archive",
                id=ident,
                title=str(d.get("title") or ident),
                url=f"https://archive.org/details/{ident}",
                download_url=None,  # resolved lazily in fetch()
                duration=None,
                license=d.get("licenseurl"),
                tags=tags,
            )
        )
    return out


def _pick_audio_file(meta: dict) -> tuple[str, str] | None:
    """Return (filename, ext) for the first reasonable audio file."""
    files = meta.get("files") or []
    # Prefer original; fall back to derivatives.
    prio = ["original", "derivative"]
    audio_exts = (".flac", ".wav", ".aif", ".aiff", ".mp3", ".ogg", ".opus", ".m4a")
    files_sorted = sorted(files, key=lambda f: prio.index(f.get("source", "")) if f.get("source") in prio else 9)
    for f in files_sorted:
        name = f.get("name", "")
        for ext in audio_exts:
            if name.lower().endswith(ext):
                return name, ext.lstrip(".")
    return None


def fetch(sound: Sound) -> Path:
    meta = http_get_json(_META.format(id=sound.id), headers={"User-Agent": _UA})
    server = meta.get("d1") or meta.get("server")
    dir_ = meta.get("dir")
    pick = _pick_audio_file(meta)
    if not (server and dir_ and pick):
        raise SourceError(f"no audio file resolvable for {sound.id}")
    name, ext = pick
    url = f"https://{server}{dir_}/{name}"
    dest = cache_path("internet_archive", f"{sound.id}/{name}", ext)
    return download(url, dest, headers={"User-Agent": _UA})
