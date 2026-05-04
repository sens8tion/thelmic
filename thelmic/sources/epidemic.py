"""Epidemic Sound — stubbed.

Epidemic is a SUBSCRIPTION service, not royalty-free. The 2500 free credits
attach to a personal account and let you download tracks via the website,
but the licensing terms require an active subscription to keep using a
downloaded track in published content. Their API is paywalled and
contractually out of bounds for this project.

If you do download tracks manually, drop the .wav/.mp3 files into
``~/.thelmic/samples/epidemic/`` and they'll be visible via
:func:`thelmic.sources.local_scan` (TODO).
"""

from __future__ import annotations

from pathlib import Path

from ._base import Sound, SourceError


def available() -> bool:
    return False


def search(query: str, *, limit: int = 10, **filters) -> list[Sound]:
    return []


def fetch(sound: Sound) -> Path:
    raise SourceError("Epidemic adapter is disabled (subscription API)")
